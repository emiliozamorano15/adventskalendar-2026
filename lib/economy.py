from collections import Counter
from datetime import datetime, timezone
import streamlit as st
from lib.db import table, rpc
from lib.clock import debug_today, today_berlin

def state(kid_id: str) -> dict:
    """One round trip: balance, claimed day ids, shop items with remaining stock and this kid's count, purchases."""
    return rpc("kid_state", {"p_kid": kid_id})

def ledger(kid_id: str) -> list[dict]:
    return (table("ledger").select("created_at,amount,reason").eq("kid_id", kid_id)
            .order("created_at", desc=True).execute().data)

def _today_param() -> str | None:
    d = debug_today()
    return d.isoformat() if d else None

def claim(kid_id: str, secret: str) -> dict:
    return rpc("claim_day", {"p_kid": kid_id, "p_secret": secret, "p_today": _today_param()})

def coop_solve(kid_id: str, day_id: int, answer: str) -> dict:
    return rpc("record_coop_solve", {"p_kid": kid_id, "p_day": day_id, "p_answer": answer, "p_today": _today_param()})

def buy_cart(kid_id: str, cart: Counter) -> dict:
    return rpc("buy_cart", {"p_kid": kid_id, "p_items": list(cart.elements())})

def adjust_coins(kid_id: str, amount: int, note: str) -> dict:
    return rpc("adjust_coins", {"p_kid": kid_id, "p_amount": amount, "p_note": note})

def debug_reset_kid(kid_id: str) -> dict:
    """Debug panel only: wipe one kid's claims, purchases and coins."""
    return rpc("debug_reset_kid", {"p_kid": kid_id})

def cancel_purchase(purchase_id: str) -> dict:
    """Refund an owned or requested purchase. Frees the stock."""
    return rpc("cancel_purchase", {"p_purchase": purchase_id})

# Voucher and present states move no coins, so they are guarded updates: the .eq("status") filter makes a
# stale button a no-op instead of a wrong transition.

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def use_voucher(kid_id: str, purchase_id: str) -> bool:
    """Kid: 'I want to use it now'. The admin confirms after the activity."""
    return bool(table("purchases").update({"status": "requested", "requested_at": _now()})
                .eq("id", purchase_id).eq("kid_id", kid_id).eq("status", "owned").execute().data)

def undo_voucher(kid_id: str, purchase_id: str) -> bool:
    """Kid: tapped 'use' by mistake. Back to owned."""
    return bool(table("purchases").update({"status": "owned", "requested_at": None})
                .eq("id", purchase_id).eq("kid_id", kid_id).eq("status", "requested").execute().data)

def confirm_redeemed(purchase_id: str) -> bool:
    """Admin: voucher used or present handed over. Works from owned too, so the parent needn't wait for the kid."""
    return bool(table("purchases").update({"status": "redeemed", "redeemed_at": _now()})
                .eq("id", purchase_id).in_("status", ["owned", "requested"]).execute().data)

@st.cache_data(ttl=600, show_spinner=False)
def unlocked_days(today_iso: str) -> list[dict]:
    """Only days up to today are ever fetched; future chapters never leave the server.
    Cached per date for 10 minutes: content changes only when you re-seed."""
    return (table("days")
            .select("id,date,day_type,chapter_text,riddle_easy,riddle_hard,coop_half_a,coop_half_b,base_coins,coop_bonus")
            .lte("date", today_iso).order("date").execute().data)

def december_days() -> dict[int, dict]:
    """Unlocked December days of the current year, keyed by door number."""
    today = today_berlin()
    return {int(d["date"][-2:]): d for d in unlocked_days(today.isoformat()) if d["date"][:7] == f"{today.year}-12"}
