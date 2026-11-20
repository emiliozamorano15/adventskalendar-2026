import streamlit as st

st.set_page_config(page_title="Adviento 2026", page_icon="🎄", layout="centered")

# A scanned claim QR opens ?claim=<secret>. The claim page is hidden from the nav but registered with
# the others, so it can switch to the shop after booking the coins.
claiming = "claim" in st.query_params
st.navigation([
    st.Page("pages/story.py", title="Calendario de Adviento", icon="🎄", default=not claiming),
    st.Page("pages/shop.py", title="Tienda", icon="🛒"),
    st.Page("pages/admin.py", title="Admin", icon="🔐"),
    st.Page("pages/claim.py", title="Reclamar", icon="🔎", visibility="hidden", default=claiming),
], position="top").run()
