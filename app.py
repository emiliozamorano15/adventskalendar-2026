import streamlit as st

st.set_page_config(page_title="Adviento 2026", page_icon="🕵️", layout="centered")

qp = st.query_params

# Special entry points reached by scanning a QR code
if "claim" in qp:
    page = st.Page("pages/claim.py", title="Reclamar", icon="🔎")
elif "redeem" in qp:
    page = st.Page("pages/admin.py", title="Canjear", icon="🎟️")
else:
    page = None

if page:
    st.navigation([page], position="hidden").run()
else:
    nav = st.navigation([
        st.Page("pages/story.py", title="Historia", icon="📖", default=True),
        st.Page("pages/wallet.py", title="Monedero", icon="💰"),
        st.Page("pages/shop.py", title="Tienda", icon="🛒"),
        st.Page("pages/admin.py", title="Admin", icon="🔐"),
    ])
    nav.run()
