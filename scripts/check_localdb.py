"""Self-check for lib/localdb.py on a temp copy of local_db/ (needs scripts/export_local.py first).
Run after changing localdb.py or sql/functions.sql. Usage: python scripts/check_localdb.py"""
import json, pathlib, shutil, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import lib.localdb as L
tmp = pathlib.Path(tempfile.mkdtemp()); shutil.copytree(L.DIR, tmp / "db"); L.DIR = tmp / "db"
db = L.LocalClient()
kid = db.t["kids"][0]["id"]; other = db.t["kids"][1]["id"]
item = min((i for i in db.t["shop_items"] if i["active"]), key=lambda i: i["price"])
st = db.rpc("kid_state", {"p_kid": kid}).execute().data
bal, bal_other = st["balance"], db.rpc("kid_state", {"p_kid": other}).execute().data["balance"]
assert bal >= item["price"], "the first kid needs coins for one item; adjust local_db/ledger.json"
r = db.rpc("buy_cart", {"p_kid": kid, "p_items": [item["id"]]}).execute().data; assert r["ok"], r
assert db.rpc("buy_cart", {"p_kid": kid, "p_items": [-1]}).execute().data["reason"] == "not_found"
assert db.rpc("buy_cart", {"p_kid": kid, "p_items": [item["id"]] * (item["per_kid_limit"] + 1)}).execute().data["reason"] in ("limit", "sold_out")
pid = db.t["purchases"][-1]["id"]
rows = db.table("purchases").select("id,status,kids(name),shop_items(name,kind)").in_("status", ["owned"]).order("purchased_at").execute().data
assert rows[0]["kids"]["name"] and rows[0]["shop_items"]["kind"], rows
assert db.table("purchases").update({"status": "requested"}).eq("id", pid).eq("status", "owned").execute().data
assert not db.table("purchases").update({"status": "requested"}).eq("id", pid).eq("status", "owned").execute().data, "guarded update no-op"
assert db.rpc("cancel_purchase", {"p_purchase": pid}).execute().data["ok"]
assert not db.rpc("cancel_purchase", {"p_purchase": pid}).execute().data["ok"]
assert db.rpc("kid_state", {"p_kid": kid}).execute().data["balance"] == bal, "refund"
day = db.t["days"][0]
assert db.rpc("claim_day", {"p_kid": kid, "p_secret": day["secret"], "p_today": "2000-01-01"}).execute().data["reason"] == "future"
r = db.rpc("claim_day", {"p_kid": kid, "p_secret": day["secret"], "p_today": "2999-12-31"}).execute().data; assert r["ok"], r
assert db.rpc("claim_day", {"p_kid": kid, "p_secret": day["secret"], "p_today": "2999-12-31"}).execute().data["reason"] == "already"
assert db.rpc("adjust_coins", {"p_kid": kid, "p_amount": -10**6, "p_note": ""}).execute().data["reason"] == "negative"
assert db.rpc("adjust_coins", {"p_kid": kid, "p_amount": 0, "p_note": ""}).execute().data["reason"] == "zero"
coop = next(d for d in db.t["days"] if d["day_type"] == "coop" and d["answer"])
solve = lambda k, ans: db.rpc("record_coop_solve", {"p_kid": k, "p_day": coop["id"], "p_answer": ans, "p_today": "2999-12-31"}).execute().data
assert solve(kid, "nope")["reason"] == "wrong"
assert solve(kid, " " + coop["answer"].upper() + " ")["bonus_paid"] is False, "first solver waits"
st = db.rpc("kid_state", {"p_kid": kid}).execute().data
assert st["coop_solved"] == [coop["id"]] and st["coop_paid"] == [], st
assert solve(other, coop["answer"])["bonus_paid"] is True, "second solver pays both"
assert db.rpc("kid_state", {"p_kid": kid}).execute().data["coop_paid"] == [coop["id"]]
assert solve(other, coop["answer"])["bonus_paid"] is False, "bonus once"
bal_other = db.rpc("kid_state", {"p_kid": other}).execute().data["balance"]
db.table("admin").upsert({"id": 1, "pin_hash": "x"}).execute()
assert db.table("admin").select("pin_hash").execute().data == [{"pin_hash": "x"}]
assert db.rpc("debug_reset_kid", {"p_kid": kid}).execute().data["ok"]
assert db.rpc("kid_state", {"p_kid": kid}).execute().data["balance"] == 0
assert db.rpc("kid_state", {"p_kid": other}).execute().data["balance"] == bal_other, "other kid untouched"
assert L.LocalClient().rpc("kid_state", {"p_kid": other}).execute().data["balance"] == bal_other, "persisted to disk"
assert json.loads((L.DIR / "claims.json").read_text()) == [], "reset persisted"
print("localdb OK")
