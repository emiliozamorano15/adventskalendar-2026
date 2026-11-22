"""Identity: personal link token + 4-digit PIN, with lockout. Admin PIN lives in the DB once changed."""
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

def valid_kid_pin(pin: str) -> bool:
    return len(pin) == 4 and pin.isascii() and pin.isdigit()

def set_kid_pin(kid_id: str, pin: str) -> None:
    """Store a new PIN and lift any lockout."""
    table("kids").update({"pin_hash": hash_pin(pin), "failed_attempts": 0, "locked_until": None}).eq("id", kid_id).execute()

def kid_by_token(token: str):
    rows = table("kids").select("*").eq("token", token).execute().data
    return rows[0] if rows else None

@st.cache_data(ttl=600, show_spinner=False)
def list_kid_names() -> list[str]:
    return [r["name"] for r in table("kids").select("name").order("name").execute().data]

def log_in(kid: dict) -> None:
    """Session login with PIN confirmed (PIN form, or the debug panel's kid switch)."""
    st.session_state["kid"] = kid
    st.session_state["pin_ok"] = kid["id"]

def log_out() -> None:
    for k in ("kid", "pin_ok", "cart"):
        st.session_state.pop(k, None)

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
    st.header("¿Quién eres?", anchor=False)
    # A form submits on Enter; a bare text_input + button ignores Enter.
    with st.form("login", border=True):
        name = st.segmented_control("Nombre", list_kid_names(), width="stretch")   # one tap on a phone
        pin = st.text_input("PIN", type="password", max_chars=4, placeholder="••••")
        submitted = st.form_submit_button("Entrar", type="primary", width="stretch")
    if submitted:
        kid, err = login_with_pin(name, pin) if name else (None, "Elige tu nombre.")
        if kid:
            log_in(kid)
            st.rerun()
        st.error(err)
    return None

def pin_confirmed(kid: dict) -> bool:
    """PIN gate for the shop: a personal-link login alone can't spend coins."""
    if st.session_state.get("pin_ok") == kid["id"]:
        return True
    st.caption("Para gastar monedas, confirma que eres tú.")
    with st.form("shop_pin", border=True):
        pin = st.text_input("Tu PIN", type="password", max_chars=4, placeholder="••••")
        submitted = st.form_submit_button("Continuar", type="primary", width="stretch")
    if submitted:
        ok, err = login_with_pin(kid["name"], pin)
        if ok:
            st.session_state["pin_ok"] = kid["id"]
            st.rerun()
        st.error(err)
    return False

def check_admin_pin(pin: str) -> bool:
    """The DB hash wins once the admin changed the PIN; until then ADMIN_PIN from secrets is the initial PIN."""
    rows = table("admin").select("pin_hash").execute().data
    if rows:
        return _check_pin(pin, rows[0]["pin_hash"])
    return hmac.compare_digest(pin.encode(), str(st.secrets["ADMIN_PIN"]).encode())

def set_admin_pin(pin: str) -> None:
    table("admin").upsert({"id": 1, "pin_hash": hash_pin(pin)}).execute()

def admin_ok() -> bool:
    if st.session_state.get("is_admin"):
        return True
    with st.form("admin_login", border=True):
        pin = st.text_input("PIN de administrador", type="password")
        submitted = st.form_submit_button("Entrar", type="primary", width="stretch")
    if submitted:
        if check_admin_pin(pin):
            st.session_state["is_admin"] = True
            st.rerun()
        st.error("PIN incorrecto.")
    return False

def change_pin_form(verify, save, four_digits: bool) -> None:
    """Current PIN + new PIN twice. verify(pin) returns an error message or ''; save(pin) stores it."""
    max_chars = 4 if four_digits else None
    with st.form("change_pin", clear_on_submit=True):
        old = st.text_input("PIN actual", type="password", max_chars=max_chars)
        new = st.text_input("Nuevo PIN", type="password", max_chars=max_chars)
        again = st.text_input("Repite el nuevo PIN", type="password", max_chars=max_chars)
        submitted = st.form_submit_button("Cambiar PIN", width="stretch")
    if not submitted:
        return
    if err := verify(old):
        st.error(err)
    elif not (valid_kid_pin(new) if four_digits else len(new) >= 4):
        st.error("El PIN debe tener 4 cifras." if four_digits else "El PIN necesita al menos 4 caracteres.")
    elif new != again:
        st.error("Los PIN nuevos no coinciden.")
    else:
        save(new)
        st.success("PIN cambiado.")
