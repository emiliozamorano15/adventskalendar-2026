import streamlit as st
from lib import auth, economy, ui

FLASH = {"already": ("warning", "Ya escaneaste este código. Cada código vale una sola vez."),
         "future": ("warning", "Todavía no es el momento de esta pista… 🤫"),
         "invalid": ("error", "Código no válido.")}

st.header("🔎 ¡Pista encontrada!", anchor=False)
kid = auth.current_kid()
if kid:
    res = economy.claim(kid["id"], st.query_params["claim"])
    if res["ok"]:
        ui.flash("success", f"¡Bien hecho, {kid['name']}! +{res['coins']} monedas 🪙", celebrate=True)
    else:
        ui.flash(*FLASH.get(res["reason"], FLASH["invalid"]))
    st.switch_page("pages/story.py")   # drops ?claim, so a reload can't book twice; the door turns ✅
