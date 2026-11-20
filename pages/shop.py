import logging
from collections import Counter
from itertools import batched
import pandas as pd
import streamlit as st
from lib import auth, economy, notify
from lib.db import table

KIND_ICON = {"present": "🎁", "voucher": "🎟️"}
REASONS = {"no_coins": "No tienes suficientes monedas.", "sold_out": "Ya no quedan suficientes de:",
           "limit": "Ya tienes el máximo de:", "not_found": "Ya no está en la tienda:"}
STATUS = {"requested": "esperando a papá/mamá ⏳", "redeemed": "usado ✅"}

def take_one(cart: Counter, item_id: int) -> None:
    cart[item_id] -= 1
    if cart[item_id] <= 0:
        del cart[item_id]

def activate_voucher(purchase_id: str, item_name: str) -> None:
    """Button callback: runs before the dialog redraws, so the list already shows the new status."""
    if not economy.request_voucher(kid["id"], purchase_id):
        return
    st.session_state["account_msg"] = ("success", "¡Pedido! Papá o mamá lo confirmarán.")
    try:
        notify.send(f"🎟️ {kid['name']} quiere usar: {item_name}",
                    f"{kid['name']} ha activado el voucher «{item_name}». "
                    "Confírmalo en la página Admin cuando lo hayáis disfrutado.")
    except Exception:   # the request is saved and shows on the admin page anyway
        logging.exception("voucher email failed")
        st.session_state["account_msg"] = ("warning", "¡Pedido! Pero el email a papá/mamá no salió: avísales tú.")

kid = auth.current_kid()
if kid and auth.pin_confirmed(kid):
    cart = st.session_state.setdefault("cart", Counter())
    items = {it["id"]: it for it in table("shop_items").select("*").eq("active", True).order("price").execute().data}
    for item_id in [i for i in cart if i not in items]:   # item went inactive since it landed in the cart
        del cart[item_id]
    sold, mine = economy.sold_counts(kid["id"])
    coins = economy.balance(kid["id"])

    # on_dismiss="rerun": closing a dialog redraws the page, so the cart badge and the buttons catch up.
    @st.dialog("🛒 Carrito", on_dismiss="rerun")
    def cart_dialog():
        if not cart:
            st.caption("Tu carrito está vacío.")
            return
        for item_id, n in list(cart.items()):
            it = items[item_id]
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"{KIND_ICON[it['kind']]} **{it['name']}** × {n} · {it['price'] * n} 🪙", width="stretch")
                st.button("➖", key=f"take{item_id}", on_click=take_one, args=(cart, item_id))
        total = sum(items[i]["price"] * n for i, n in cart.items())
        st.markdown(f"**Total: {total} 🪙** · tienes {coins} 🪙")
        if total > coins:
            st.warning("No tienes suficientes monedas para todo el carrito.")
        if st.button("Comprar", type="primary", disabled=total > coins, width="stretch"):
            res = economy.buy_cart(kid["id"], cart)
            if res["ok"]:
                cart.clear()
                st.session_state["flash"] = ("success", "¡Compra hecha! Encuentras tus cosas en 👤 Cuenta.")
                st.rerun()   # closes the dialog
            st.error(f"{REASONS[res['reason']]} {items.get(res.get('item_id'), {}).get('name', '')}")

    @st.dialog("👤 Mi cuenta", width="large", on_dismiss="rerun")
    def account_dialog():
        if msg := st.session_state.pop("account_msg", None):
            getattr(st, msg[0])(msg[1])
        st.metric("Monedas", coins)
        st.subheader("Mis compras")
        rows = economy.purchases(kid["id"])
        if not rows:
            st.caption("Todavía no has comprado nada.")
        for p in rows:
            item = p["shop_items"]
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"{KIND_ICON[item['kind']]} **{item['name']}** · {p['purchased_at'][:10]}", width="stretch")
                if item["kind"] == "voucher" and p["status"] == "owned":
                    st.button("Activar voucher", key=f"act{p['id']}", type="primary",
                              on_click=activate_voucher, args=(p["id"], item["name"]))
                elif item["kind"] == "voucher":
                    st.caption(STATUS[p["status"]])
        with st.expander("Historial de monedas"):
            hist = economy.ledger(kid["id"])
            st.dataframe(pd.DataFrame(hist)[["created_at", "amount", "reason"]] if hist else pd.DataFrame(), hide_index=True)
        with st.expander("Cambiar PIN"):
            auth.change_pin_form(lambda pin: auth.login_with_pin(kid["name"], pin)[1],
                                 lambda pin: auth.set_kid_pin(kid["id"], pin), four_digits=True)

    with st.container(horizontal=True, vertical_alignment="center"):
        st.title("🛒 Tienda", anchor=False)
        if st.button(f"🛒 {cart.total()}", help="Carrito"):
            cart_dialog()
        if st.button("👤 Cuenta"):
            account_dialog()
    st.caption(f"Tienes **{coins} 🪙**")

    if flash := st.session_state.pop("flash", None):
        getattr(st, flash[0])(flash[1])
        if flash[0] == "success":
            st.balloons()

    if not items:
        st.caption("La tienda está vacía.")
    for row in batched(items.values(), 3):
        for col, it in zip(st.columns(3), row):
            left = it["stock"] - sold[it["id"]]
            allowed = it["per_kid_limit"] - mine[it["id"]]
            with col.container(border=True):
                st.title(KIND_ICON[it["kind"]], anchor=False, text_alignment="center")
                st.markdown(f"**{it['name']}**")
                if it["description"]:
                    st.caption(it["description"])
                st.markdown(f"{it['price']} 🪙")
                st.caption("Agotado" if left <= 0 else f"Quedan {left}"
                           + (" · ya tienes el máximo" if allowed <= 0 else f" · máx. {it['per_kid_limit']} por niño/a"))
                st.button("Añadir", key=f"add{it['id']}", width="stretch",
                          disabled=min(left, allowed) - cart[it["id"]] <= 0, on_click=cart.update, args=([it["id"]],))
