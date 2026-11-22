import streamlit as st
from lib.clock import debug_on

st.set_page_config(page_title="Adviento 2026", page_icon="🎄", layout="centered")

# A scanned claim QR opens ?claim=<secret>. The claim page is hidden from the nav but registered with
# the others, so it can switch to the calendar after booking the coins.
# The voucher email links to ?redeem=<purchase_id>, which opens Admin on that purchase.
claiming = "claim" in st.query_params
redeeming = "redeem" in st.query_params
page = st.navigation([
    st.Page("pages/story.py", title="Calendario", icon=":material/calendar_month:", default=not (claiming or redeeming)),
    st.Page("pages/shop.py", title="Tienda", icon=":material/storefront:"),
    st.Page("pages/mine.py", title="Mis cosas", icon=":material/backpack:"),
    st.Page("pages/admin.py", title="Admin", icon=":material/lock:", default=redeeming and not claiming),
    st.Page("pages/claim.py", title="Reclamar", icon=":material/qr_code_scanner:", visibility="hidden", default=claiming),
], position="hidden")   # kid pages draw their own bottom tab bar (lib/ui.nav_bar); Admin is linked from Mis cosas
if debug_on():
    from lib import debug
    debug.panel()
page.run()
