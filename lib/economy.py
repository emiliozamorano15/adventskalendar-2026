import io
import segno
import streamlit as st
from lib.db import table, rpc
from lib.clock import today_berlin

def balance(kid_id: str) -> int:
    rows = table("ledger").select("amount").eq("kid_id", kid_id).execute().data
    return sum(r["amount"] for r in rows)

def ledger(kid_id: str) -> list[dict]:
    return (table("ledger").select("*").eq("kid_id", kid_id)
            .order("created_at", desc=True).execute().data)

def claim(kid_id: str, secret: str) -> dict:
    return rpc("claim_day", {"p_kid": kid_id, "p_secret": secret})

def buy(kid_id: str, item_id: int) -> dict:
    return rpc("buy_item", {"p_kid": kid_id, "p_item": item_id})

def coop_solve(kid_id: str, day_id: int) -> dict:
    return rpc("record_coop_solve", {"p_kid": kid_id, "p_day": day_id})

def unlocked_days() -> list[dict]:
    """Only days up to today are ever fetched; future chapters never leave the server."""
    return (table("days")
            .select("id,date,day_type,chapter_text,riddle_easy,riddle_hard,coop_half_a,coop_half_b,base_coins,coop_bonus")
            .lte("date", today_berlin().isoformat()).order("date").execute().data)

def qr_png(url: str) -> bytes:
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=8, border=2)
    return buf.getvalue()

def app_url() -> str:
    return st.secrets["APP_URL"].rstrip("/")
