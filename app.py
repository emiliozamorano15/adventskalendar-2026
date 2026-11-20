import streamlit as st

st.set_page_config(page_title="Adviento 2026", page_icon="🕵️", layout="centered")

# A scanned claim QR opens ?claim=<secret> on a page without navigation.
if "claim" in st.query_params:
    st.navigation([st.Page("pages/claim.py", title="Reclamar", icon="🔎")], position="hidden").run()
else:
    st.navigation([
        st.Page("pages/story.py", title="Historia", icon="📖", default=True),
        st.Page("pages/wallet.py", title="Monedero", icon="💰"),
        st.Page("pages/shop.py", title="Tienda", icon="🛒"),
        st.Page("pages/admin.py", title="Admin", icon="🔐"),
    ]).run()
