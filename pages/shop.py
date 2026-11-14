import streamlit as st
from lib import auth, economy
from lib.db import table

REASONS = {"no_coins": "No tienes suficientes monedas.", "sold_out": "¡Agotado!",
           "not_found": "Artículo no encontrado."}

kid = auth.current_kid()
if kid:
    st.title("🛒 Tienda")
    st.metric("Tus monedas", economy.balance(kid["id"]))
    for it in table("shop_items").select("*").eq("active", True).order("price").execute().data:
        with st.container(border=True):
            st.markdown(f"**{it['name']}** — {it['price']} 🪙")
            st.caption(it["description"] or "")
            # TODO: show remaining stock
            if st.button("Comprar", key=f"buy{it['id']}"):
                res = economy.buy(kid["id"], it["id"])
                if res["ok"]:
                    st.success("¡Comprado! Lo encuentras en tu monedero.")
                    st.rerun()
                else:
                    st.error(REASONS.get(res["reason"], "Error"))
