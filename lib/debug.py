"""Debug panel in the sidebar. Shows only when DEBUG = true in secrets, where the app runs on local_db/
instead of Supabase. Simulates the date, switches kids without a PIN, gives coins, scans a day, resets a kid."""
from datetime import date
import streamlit as st
from lib import auth, economy, ui
from lib.clock import now_berlin
from lib.db import table

def _set_date(d: date) -> None:
    st.session_state["debug_today"] = d

def _switch_kid() -> None:
    kid = next((k for k in _kids() if k["name"] == st.session_state["debug_kid"]), None)
    auth.log_out()
    if kid:
        auth.log_in(kid)

# Actions are on_click callbacks: they run before the next script run, so the page below already shows the result.

def _coins(kid: dict) -> None:
    res = economy.adjust_coins(kid["id"], int(st.session_state["debug_amount"]), "debug")
    ui.flash(*(("success", f"Saldo: {res['balance']} 🪙") if res["ok"] else ("error", f"Monedas: {res['reason']}")))

def _scan(kid: dict, day: date) -> None:
    rows = table("days").select("secret").eq("date", day.isoformat()).execute().data
    res = economy.claim(kid["id"], rows[0]["secret"]) if rows else {"ok": False, "reason": "no hay día"}
    ui.flash(*(("success", f"+{res['coins']} 🪙", True) if res["ok"] else ("error", f"Escaneo: {res['reason']}")))

def _reset(kid: dict) -> None:
    economy.debug_reset_kid(kid["id"])
    st.session_state.pop("cart", None)
    ui.flash("success", f"{kid['name']} empieza de cero.")

@st.cache_data(ttl=600, show_spinner=False)
def _kids() -> list[dict]:
    return table("kids").select("*").order("name").execute().data

def panel() -> None:
    year = now_berlin().year
    st.session_state.setdefault("debug_today", now_berlin().date())
    with st.sidebar:
        st.badge("Modo debug", icon=":material/bug_report:", color="red")
        st.caption("Usa la copia local `local_db/`, no Supabase. Nunca pongas `DEBUG` en los secrets publicados.")

        st.date_input("Fecha simulada", key="debug_today", format="DD.MM.YYYY")
        with st.container(horizontal=True):
            st.button("1 dic", on_click=_set_date, args=(date(year, 12, 1),))
            st.button("24 dic", help="Abre todas las puertas", on_click=_set_date, args=(date(year, 12, 24),))
            st.button("Hoy", on_click=_set_date, args=(now_berlin().date(),))

        kid = st.session_state.get("kid")
        names = [k["name"] for k in _kids()]
        st.segmented_control("Entrar como (sin PIN)", names, key="debug_kid", on_change=_switch_kid,
                             default=kid["name"] if kid else None)
        if not kid:
            return

        st.subheader("Probar con " + kid["name"], anchor=False)
        st.number_input("Monedas (+/-)", value=50, step=10, key="debug_amount")
        st.button("Ajustar monedas", width="stretch", on_click=_coins, args=(kid,))
        today = st.session_state["debug_today"]
        st.button(f"Escanear el código del {today:%d.%m.}", width="stretch", on_click=_scan, args=(kid, today))
        sure = st.checkbox(f"Sí, borrar todo lo de {kid['name']}", key="debug_sure")
        st.button("Reiniciar niño/a", disabled=not sure, width="stretch", on_click=_reset, args=(kid,),
                  help="Borra escaneos, compras y monedas. Mantiene el niño/a, el PIN y el contenido.")
