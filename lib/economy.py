from collections import Counter
from datetime import datetime, timezone
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

def buy_cart(kid_id: str, cart: Counter) -> dict:
    return rpc("buy_cart", {"p_kid": kid_id, "p_items": list(cart.elements())})

def sold_counts(kid_id: str) -> tuple[Counter, Counter]:
    """Pieces bought per item: by all kids, and by this kid. Cancelled purchases give the stock back."""
    rows = table("purchases").select("item_id,kid_id").neq("status", "cancelled").execute().data
    return Counter(r["item_id"] for r in rows), Counter(r["item_id"] for r in rows if r["kid_id"] == kid_id)

def purchases(kid_id: str) -> list[dict]:
    return (table("purchases").select("id,status,purchased_at,requested_at,redeemed_at,shop_items(name,kind)")
            .eq("kid_id", kid_id).neq("status", "cancelled").order("purchased_at", desc=True).execute().data)

def request_voucher(kid_id: str, purchase_id: str) -> bool:
    """Kid asks to use a voucher; the admin confirms it later. Moves no coins."""
    return bool(table("purchases").update({"status": "requested", "requested_at": datetime.now(timezone.utc).isoformat()})
                .eq("id", purchase_id).eq("kid_id", kid_id).eq("status", "owned").execute().data)

def coop_solve(kid_id: str, day_id: int, answer: str) -> dict:
    return rpc("record_coop_solve", {"p_kid": kid_id, "p_day": day_id, "p_answer": answer})

def unlocked_days() -> list[dict]:
    """Only days up to today are ever fetched; future chapters never leave the server."""
    return (table("days")
            .select("id,date,day_type,chapter_text,riddle_easy,riddle_hard,coop_half_a,coop_half_b,base_coins,coop_bonus")
            .lte("date", today_berlin().isoformat()).order("date").execute().data)
