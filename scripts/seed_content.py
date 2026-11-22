"""Load kids, shop items and days from content/days.json (git-ignored) into Supabase.
Initial kid PINs come from [kid_pins] in .streamlit/secrets.toml. Usage: python scripts/seed_content.py [--reset]"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts._client import client
from lib.auth import hash_pin, valid_kid_pin

sb, cfg = client()
data = json.loads((pathlib.Path(__file__).resolve().parent.parent / "content" / "days.json").read_text())

# Validate before --reset so bad content can't leave an empty database behind.
# Names match case-insensitively, so "ISABEL" in secrets.toml covers "Isabel" in days.json.
secret_pins = {name.casefold(): str(pin) for name, pin in cfg.get("kid_pins", {}).items()}
pins = {k["name"]: secret_pins.get(k["name"].casefold(), "") for k in data["kids"]}
bad = [name for name, pin in pins.items() if not valid_kid_pin(pin)]
if bad:
    sys.exit(f"Missing or invalid PIN for {bad}: add a 4-digit entry per kid under [kid_pins] in .streamlit/secrets.toml")
old_scope = [i["name"] for i in data.get("shop_items", []) if "stock_scope" in i]
if old_scope:
    sys.exit(f"stock_scope is gone; remove it from {old_scope}. stock now counts pieces for all kids together.")

if "--reset" in sys.argv:
    for t in ["ledger", "purchases", "coop_solves", "claims", "shop_items", "days", "kids"]:
        sb.table(t).delete().not_.is_("id", "null").execute()

# [kid_pins] is only the initial PIN: an existing kid keeps the PIN changed in the app.
existing = {r["name"] for r in sb.table("kids").select("name").execute().data}
for k in data["kids"]:
    level = k.get("level", "easy")
    if k["name"] in existing:
        sb.table("kids").update({"level": level}).eq("name", k["name"]).execute()
    else:
        sb.table("kids").insert({"name": k["name"], "pin_hash": hash_pin(pins[k["name"]]), "level": level}).execute()

# default_to_null=False: a key missing from one row gets the column default instead of NULL.
if data.get("shop_items"):
    sb.table("shop_items").upsert(data["shop_items"], on_conflict="name", default_to_null=False).execute()
sb.table("days").upsert(data["days"], on_conflict="date", default_to_null=False).execute()
print("Seed OK")
