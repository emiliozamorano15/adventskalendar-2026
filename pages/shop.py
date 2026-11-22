from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import io
import httpx
from PIL import Image, ImageOps
import streamlit as st
from lib import auth, economy, ui
from lib.ui import KIND_ICON

REASONS = {"no_coins": "No tienes suficientes monedas.", "sold_out": "Ya no quedan suficientes de:",
           "limit": "Ya tienes el máximo de:", "not_found": "Ya no está en la tienda:"}

@st.cache_data(show_spinner=False, max_entries=200)
def card_image(url: str) -> bytes | None:
    """Same 16:9 crop for every card picture, fetched once per server. None: the card shows the emoji."""
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "adventskalender-app/1.0"})
        r.raise_for_status()
        img = ImageOps.fit(Image.open(io.BytesIO(r.content)).convert("RGB"), (400, 225))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80)
        return out.getvalue()
    except Exception:
        return None

def add_one(cart: Counter, item: dict) -> None:
    cart.update([item["id"]])
    st.toast(f"{item['name']} → carrito", icon="🛒")   # visible feedback, so a slow page doesn't get a second tap

def take_one(cart: Counter, item_id: int) -> None:
    cart[item_id] -= 1
    if cart[item_id] <= 0:
        del cart[item_id]

kid = auth.current_kid()
if kid and auth.pin_confirmed(kid):
    state = economy.state(kid["id"])
    coins = state["balance"]
    items = {it["id"]: it for it in state["items"]}
    cart = st.session_state.setdefault("cart", Counter())
    for item_id in [i for i in cart if i not in items]:   # item went inactive since it landed in the cart
        del cart[item_id]
    total = sum(items[i]["price"] * n for i, n in cart.items())

    # on_dismiss="rerun": closing the dialog redraws the page, so the cart bar and the buttons catch up.
    @st.dialog("Carrito", icon=":material/shopping_cart:", on_dismiss="rerun")
    def cart_dialog():
        if not cart:
            st.caption("Tu carrito está vacío.")
            return
        for item_id, n in list(cart.items()):
            it = items[item_id]
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"{KIND_ICON[it['kind']]} **{it['name']}** × {n}  \n{it['price'] * n} 🪙", width="stretch")
                st.button("", key=f"take{item_id}", icon=":material/remove:", help="Quitar uno",
                          on_click=take_one, args=(cart, item_id))
        total = sum(items[i]["price"] * n for i, n in cart.items())
        st.markdown(f"**Total: {total} 🪙** · tienes {coins} 🪙")
        if total > coins:
            st.warning("No tienes suficientes monedas para todo el carrito.")
        if st.button("Comprar", type="primary", icon=":material/check:", disabled=total > coins, width="stretch"):
            res = economy.buy_cart(kid["id"], cart)
            if res["ok"]:
                cart.clear()
                ui.flash("success", "¡Compra hecha! Tus cosas están en «Mis cosas».", celebrate=True)
                st.rerun()   # closes the dialog
            st.error(f"{REASONS[res['reason']]} {items.get(res.get('item_id'), {}).get('name', '')}")

    ui.header("Tienda", kid, coins)
    if not items:
        st.caption("La tienda está vacía.")

    # Fetch all pictures at once on a cold cache: one by one took ~10 s and invited double taps.
    with ThreadPoolExecutor(8) as pool:
        pictures = dict(zip(items, pool.map(lambda it: it.get("image_url") and card_image(it["image_url"]), items.values())))

    # Two cards per row on a phone, more on a wide screen; row_height makes every card the same size.
    with st.grid("auto", min_column_width=150, gap="small", row_height=400):
        for it in items.values():
            in_cart = cart[it["id"]]
            can_add = min(it["remaining"], it["per_kid_limit"] - it["mine"]) - in_cart > 0
            with st.container(border=True, height="stretch", horizontal_alignment="center"):
                if picture := pictures[it["id"]]:
                    st.image(picture, width="stretch")
                else:
                    st.title(KIND_ICON[it["kind"]], anchor=False, text_alignment="center")
                st.markdown(f"**{it['name']}**", text_alignment="center")
                if it["description"]:
                    st.caption(it["description"], text_alignment="center")
                st.badge(f"{it['price']}", icon="🪙", color="orange")
                if it["remaining"] <= 0:
                    note = "Agotado"
                elif it["mine"] >= it["per_kid_limit"]:
                    note = "Ya tienes el máximo"
                else:
                    note = f"Quedan {it['remaining']}"
                st.caption(note + (f" · {in_cart} en el carrito" if in_cart else ""), text_alignment="center")
                st.space("stretch")
                st.button("Añadir", key=f"add{it['id']}", icon=":material/add_shopping_cart:", width="stretch",
                          disabled=not can_add, on_click=add_one, args=(cart, it))

    # Cart bar pinned to the bottom of the screen while something is in it.
    if cart:
        with st.bottom, st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{cart.total()}** en el carrito · **{total} 🪙**", width="stretch")
            if st.button("Ver carrito", type="primary", icon=":material/shopping_cart:"):
                cart_dialog()
if kid:
    ui.nav_bar()
