"""Identity: personal link token + 4-digit PIN, with lockout."""
import hashlib, hmac, os
from datetime import datetime, timedelta, timezone
import streamlit as st
from lib.db import table

MAX_ATTEMPTS = 5
LOCKOUT_MIN = 10

def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dig = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000)
    return salt.hex() + "$" + dig.hex()

def _check_pin(pin: str, stored: str) -> bool:
    salt_hex, dig_hex = stored.split("$")
    dig = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(dig.hex(), dig_hex)

def kid_by_token(token: str):
    rows = table("kids").select("*").eq("token", token).execute().data
    return rows[0] if rows else None

def list_kid_names() -> list[str]:
    return [r["name"] for r in table("kids").select("name").order("name").execute().data]

def login_with_pin(name: str, pin: str) -> tuple[dict | None, str]:
    """Returns (kid, error_message)."""
    rows = table("kids").select("*").eq("name", name).execute().data
    if not rows:
        return None, "Usuario no encontrado."
    kid = rows[0]
    now = datetime.now(timezone.utc)
    if kid["locked_until"] and datetime.fromisoformat(kid["locked_until"]) > now:
        return None, "Demasiados intentos. Espera unos minutos."
    if _check_pin(pin, kid["pin_hash"]):
        table("kids").update({"failed_attempts": 0, "locked_until": None}).eq("id", kid["id"]).execute()
        return kid, ""
    fails = kid["failed_attempts"] + 1
    upd = {"failed_attempts": fails}
    if fails >= MAX_ATTEMPTS:
        upd = {"failed_attempts": 0, "locked_until": (now + timedelta(minutes=LOCKOUT_MIN)).isoformat()}
    table("kids").update(upd).eq("id", kid["id"]).execute()
    return None, "PIN incorrecto."

def current_kid() -> dict | None:
    """Resolve the kid from session, ?kid=<token>, or show the PIN form."""
    if "kid" in st.session_state:
        return st.session_state["kid"]
    token = st.query_params.get("kid")
    if token:
        kid = kid_by_token(token)
        if kid:
            st.session_state["kid"] = kid
            return kid
    st.subheader("¿Quién eres?")
    name = st.selectbox("Nombre", list_kid_names())
    pin = st.text_input("PIN", type="password", max_chars=4)
    if st.button("Entrar"):
        kid, err = login_with_pin(name, pin)
        if kid:
            st.session_state["kid"] = kid
            st.session_state["pin_ok"] = kid["id"]
            st.rerun()
        st.error(err)
    return None

def pin_confirmed(kid: dict) -> bool:
    """PIN gate for the shop: a personal-link login alone can't spend coins."""
    if st.session_state.get("pin_ok") == kid["id"]:
        return True
    pin = st.text_input("Tu PIN", type="password", max_chars=4)
    if st.button("Abrir tienda"):
        ok, err = login_with_pin(kid["name"], pin)
        if ok:
            st.session_state["pin_ok"] = kid["id"]
            st.rerun()
        st.error(err)
    return False

def admin_ok() -> bool:
    if st.session_state.get("is_admin"):
        return True
    pin = st.text_input("PIN de administrador", type="password")
    if st.button("Entrar como admin"):
        if hmac.compare_digest(pin, str(st.secrets["ADMIN_PIN"])):
            st.session_state["is_admin"] = True
            st.rerun()
        st.error("PIN incorrecto.")
    return False
