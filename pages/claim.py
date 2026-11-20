import streamlit as st
from lib import auth, economy

FLASH = {"already": ("error", "Ya escaneaste este código. Cada código vale una sola vez."),
         "future": ("warning", "Todavía no es el momento de esta pista… 🤫"),
         "invalid": ("error", "Código no válido.")}

st.title("🔎 ¡Pista encontrada!")
kid = auth.current_kid()
if kid:
    res = economy.claim(kid["id"], st.query_params["claim"])
    st.session_state["flash"] = (("success", f"¡Bien hecho, {kid['name']}! +{res['coins']} monedas") if res["ok"]
                                 else FLASH.get(res["reason"], FLASH["invalid"]))
    st.switch_page("pages/shop.py")   # drops ?claim, so a reload can't book twice
