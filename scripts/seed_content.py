"""Load kids, shop items and days from content/days.json (git-ignored) into Supabase.
Kid PINs come from [kid_pins] in .streamlit/secrets.toml. Usage: python scripts/seed_content.py [--reset]"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts._client import client
from lib.auth import hash_pin

sb, cfg = client()
data = json.loads((pathlib.Path(__file__).resolve().parent.parent / "content" / "days.json").read_text())

# Validate before --reset so a missing PIN can't leave an empty database behind.
pins = {k["name"]: str(cfg.get("kid_pins", {}).get(k["name"], "")) for k in data["kids"]}
bad = [name for name, pin in pins.items() if not (pin.isdigit() and len(pin) == 4)]
if bad:
    sys.exit(f"Missing or invalid PIN for {bad}: add a 4-digit entry per kid under [kid_pins] in .streamlit/secrets.toml")

if "--reset" in sys.argv:
    for t in ["ledger", "purchases", "coop_solves", "claims", "shop_items", "days", "kids"]:
        sb.table(t).delete().not_.is_("id", "null").execute()

# default_to_null=False: a key missing from one row gets the column default instead of NULL.
for k in data["kids"]:
    sb.table("kids").upsert({"name": k["name"], "pin_hash": hash_pin(pins[k["name"]]), "level": k.get("level", "easy")},
                            on_conflict="name").execute()
if data.get("shop_items"):
    sb.table("shop_items").upsert(data["shop_items"], on_conflict="name", default_to_null=False).execute()
sb.table("days").upsert(data["days"], on_conflict="date", default_to_null=False).execute()
print("Seed OK")
