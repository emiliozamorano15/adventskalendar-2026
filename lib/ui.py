"""Shared page pieces: header with the coin balance, and flash messages across reruns."""
import streamlit as st
from lib.clock import debug_on

KIND_ICON = {"present": "🎁", "voucher": "🎟️"}

def flash(kind: str, text: str, celebrate: bool = False) -> None:
    """Message that survives st.rerun() / st.switch_page(). st.success right before a rerun never shows."""
    st.session_state["flash"] = (kind, text, celebrate)

def show_flash() -> None:
    if msg := st.session_state.pop("flash", None):
        kind, text, celebrate = msg
        getattr(st, kind)(text)
        if celebrate:
            st.balloons()

def header(title: str, kid: dict, coins: int) -> None:
    """Page title, the kid's name and the balance, so the coins are visible on every page."""
    with st.container(horizontal=True, vertical_alignment="center"):
        st.header(title, anchor=False, width="stretch")
        st.badge(f"{coins}", icon="🪙", color="orange")
    st.caption(f"Hola, **{kid['name']}**" + (" · :red-badge[MODO DEBUG]" if debug_on() else ""))
    show_flash()

def nav_bar() -> None:
    """Tab bar pinned to the bottom of the screen. Streamlit's own top nav hides behind a menu on a phone.
    Call it last, so a page's own st.bottom content (the cart bar) sits above it."""
    with st.bottom, st.container(horizontal=True, horizontal_alignment="distribute", gap=None):
        st.page_link("pages/story.py", label="Calendario", icon=":material/calendar_month:")
        st.page_link("pages/shop.py", label="Tienda", icon=":material/storefront:")
        st.page_link("pages/mine.py", label="Mis cosas", icon=":material/backpack:")
