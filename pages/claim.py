import streamlit as st
from lib import auth, economy

st.title("🔎 ¡Pista encontrada!")
kid = auth.current_kid()
if kid:
    res = economy.claim(kid["id"], st.query_params["claim"])
    if res["ok"]:
        st.balloons()
        st.success(f"¡Bien hecho, {kid['name']}! +{res['coins']} monedas")
    elif res["reason"] == "already":
        st.info("Ya reclamaste este día.")
    elif res["reason"] == "future":
        st.warning("Todavía no es el momento de esta pista… 🤫")
    else:
        st.error("Código no válido.")
