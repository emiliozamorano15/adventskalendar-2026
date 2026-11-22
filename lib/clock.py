from datetime import date, datetime
from zoneinfo import ZoneInfo
import streamlit as st

TZ = ZoneInfo("Europe/Berlin")

def now_berlin() -> datetime:
    return datetime.now(TZ)

def debug_on() -> bool:
    """DEBUG = true in secrets: debug panel, and lib/db serves local_db/ instead of Supabase. Never on the deployed app."""
    try:
        return st.secrets.get("DEBUG", False) is True
    except Exception:   # no secrets file: scripts and tests
        return False

def debug_today() -> date | None:
    """The simulated date from the debug panel, or None outside debug mode."""
    return st.session_state.get("debug_today") if debug_on() else None

def today_berlin() -> date:
    return debug_today() or now_berlin().date()
