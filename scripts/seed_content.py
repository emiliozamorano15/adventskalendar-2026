"""Load kids, shop items and days from content/days.json (git-ignored) into Supabase.
Usage: python scripts/seed_content.py [--reset]"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts._client import client
from lib.auth import hash_pin

sb, _ = client()
data = json.loads((pathlib.Path(__file__).resolve().parent.parent / "content" / "days.json").read_text())

if "--reset" in sys.argv:
    for t in ["ledger", "purchases", "coop_solves", "claims", "shop_items", "days", "kids"]:
        sb.table(t).delete().neq("id" if t != "ledger" else "id", -1 if t in ("ledger","days","shop_items","claims","coop_solves") else "00000000-0000-0000-0000-000000000000").execute()

for k in data["kids"]:
    sb.table("kids").upsert({"name": k["name"], "pin_hash": hash_pin(k["pin"])}, on_conflict="name").execute()
if data.get("shop_items"):
    sb.table("shop_items").insert(data["shop_items"]).execute()
sb.table("days").upsert(data["days"], on_conflict="date").execute()
print("Seed OK")
