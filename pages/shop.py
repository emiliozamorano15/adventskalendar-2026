import streamlit as st
from lib import auth, economy
from lib.db import table

KIND_ICON = {"present": "🎁", "voucher": "🎟️"}
REASONS = {"no_coins": "No tienes suficientes monedas.", "sold_out": "¡Agotado!",
           "limit": "Ya tienes el máximo de este artículo.", "not_found": "Artículo no encontrado."}

st.title("🛒 Tienda")
kid = auth.current_kid()
if kid and auth.pin_confirmed(kid):
    if msg := st.session_state.pop("shop_msg", None):
        st.success(msg)
    st.metric("Tus monedas", economy.balance(kid["id"]))
    for it in table("shop_items").select("*").eq("active", True).order("price").execute().data:
        with st.container(border=True):
            st.markdown(f"{KIND_ICON[it['kind']]} **{it['name']}** — {it['price']} 🪙")
            st.caption(it["description"] or "")
            # TODO: show remaining stock
            if st.button("Comprar", key=f"buy{it['id']}"):
                res = economy.buy(kid["id"], it["id"])
                if res["ok"]:
                    st.session_state["shop_msg"] = f"¡Comprado: {it['name']}! Lo encuentras en tu monedero."
                    st.rerun()
                else:
                    st.error(REASONS.get(res["reason"], "Error"))
