"""Local stand-in for the Supabase client in debug mode: tables live as JSON files in local_db/.
Fill it with `python scripts/export_local.py`. Covers only the query-builder calls and RPCs the app uses.
shortcut: the RPCs below re-implement sql/functions.sql in Python, so a change there must be copied here.
Fine for one local tester; never use it for the deployed app."""
import json, pathlib, re, threading, uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

DIR = pathlib.Path(__file__).resolve().parent.parent / "local_db"
TABLES = ["kids", "admin", "days", "claims", "coop_solves", "shop_items", "purchases", "ledger"]
EMBED_FK = {"kids": "kid_id", "shop_items": "item_id"}   # purchases(kids(name)) follows purchases.kid_id
_lock = threading.Lock()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _res(data):
    return SimpleNamespace(data=data)

class LocalClient:
    def __init__(self):
        missing = [t for t in TABLES if not (DIR / f"{t}.json").exists()]
        if missing:
            raise FileNotFoundError(f"local_db/ lacks {missing}: run `python scripts/export_local.py` first")
        self.t = {t: json.loads((DIR / f"{t}.json").read_text()) for t in TABLES}

    def save(self, *tables: str) -> None:
        for t in tables:
            (DIR / f"{t}.json").write_text(json.dumps(self.t[t], indent=1, ensure_ascii=False))

    def table(self, name: str) -> "Query":
        return Query(self, name)

    def rpc(self, name: str, params: dict):
        def run():
            with _lock:   # Streamlit runs sessions in threads; one RPC at a time, like a row lock
                return _res(getattr(self, "_" + name)(**params))
        return SimpleNamespace(execute=run)

    # --- helpers shared by the RPCs
    def _add(self, table: str, row: dict) -> dict:
        rows = self.t[table]
        if table in ("kids", "purchases"):
            row.setdefault("id", str(uuid.uuid4()))
        else:
            row.setdefault("id", max((r["id"] for r in rows), default=0) + 1)
        rows.append(row)
        return row

    def _ledger(self, kid: str, amount: int, reason: str, ref) -> None:
        self._add("ledger", {"kid_id": kid, "amount": amount, "reason": reason, "ref": ref, "created_at": _now()})

    def _balance(self, kid: str) -> int:
        return sum(r["amount"] for r in self.t["ledger"] if r["kid_id"] == kid)

    def _open(self) -> list[dict]:
        return [p for p in self.t["purchases"] if p["status"] != "cancelled"]

    @staticmethod
    def _today(p_today) -> str:
        return p_today or datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()

    # --- RPCs, same contracts as sql/functions.sql
    def _claim_day(self, p_kid, p_secret, p_today=None):
        d = next((d for d in self.t["days"] if d["secret"] == p_secret), None)
        if not d:
            return {"ok": False, "reason": "invalid"}
        if d["date"] > self._today(p_today):
            return {"ok": False, "reason": "future"}
        if any(c["kid_id"] == p_kid and c["day_id"] == d["id"] for c in self.t["claims"]):
            return {"ok": False, "reason": "already", "day_id": d["id"]}
        self._add("claims", {"kid_id": p_kid, "day_id": d["id"], "claimed_at": _now()})
        self._ledger(p_kid, d["base_coins"], "claim", str(d["id"]))
        self.save("claims", "ledger")
        return {"ok": True, "coins": d["base_coins"], "day_id": d["id"]}

    def _record_coop_solve(self, p_kid, p_day, p_answer, p_today=None):
        d = next((d for d in self.t["days"] if d["id"] == p_day and d["day_type"] == "coop"), None)
        if not d:
            return {"ok": False, "reason": "invalid"}
        if d["date"] > self._today(p_today):
            return {"ok": False, "reason": "future"}
        if d["answer"] is None or (p_answer or "").strip().lower() != d["answer"].strip().lower():
            return {"ok": False, "reason": "wrong"}
        if not any(s["kid_id"] == p_kid and s["day_id"] == p_day for s in self.t["coop_solves"]):
            self._add("coop_solves", {"kid_id": p_kid, "day_id": p_day, "solved_at": _now()})
        solvers = {s["kid_id"] for s in self.t["coop_solves"] if s["day_id"] == p_day}
        paid = any(r["reason"] == "coop_bonus" and r["ref"] == str(p_day) for r in self.t["ledger"])
        if len(solvers) >= 2 and not paid:
            for k in solvers:
                self._ledger(k, d["coop_bonus"], "coop_bonus", str(p_day))
            self.save("coop_solves", "ledger")
            return {"ok": True, "bonus_paid": True, "bonus": d["coop_bonus"]}
        self.save("coop_solves")
        return {"ok": True, "bonus_paid": False}

    def _buy_cart(self, p_kid, p_items):
        items = {i["id"]: i for i in self.t["shop_items"]}
        open_ = self._open()
        cost = 0
        for item_id in sorted(set(p_items)):   # every check before the first write, like the SQL
            it, qty = items.get(item_id), p_items.count(item_id)
            if not it or not it["active"]:
                return {"ok": False, "reason": "not_found", "item_id": item_id}
            if sum(p["item_id"] == item_id for p in open_) + qty > it["stock"]:
                return {"ok": False, "reason": "sold_out", "item_id": item_id}
            if sum(p["item_id"] == item_id and p["kid_id"] == p_kid for p in open_) + qty > it["per_kid_limit"]:
                return {"ok": False, "reason": "limit", "item_id": item_id}
            cost += it["price"] * qty
        if self._balance(p_kid) < cost:
            return {"ok": False, "reason": "no_coins"}
        for item_id in p_items:
            p = self._add("purchases", {"kid_id": p_kid, "item_id": item_id, "price_paid": items[item_id]["price"],
                                        "status": "owned", "purchased_at": _now(), "requested_at": None, "redeemed_at": None})
            self._ledger(p_kid, -p["price_paid"], "purchase", p["id"])
        self.save("purchases", "ledger")
        return {"ok": True, "cost": cost}

    def _cancel_purchase(self, p_purchase):
        p = next((p for p in self.t["purchases"] if p["id"] == p_purchase), None)
        if not p or p["status"] not in ("owned", "requested"):
            return {"ok": False}
        p["status"] = "cancelled"
        self._ledger(p["kid_id"], p["price_paid"], "refund", p_purchase)
        self.save("purchases", "ledger")
        return {"ok": True}

    def _kid_state(self, p_kid):
        open_ = self._open()
        items = {i["id"]: i for i in self.t["shop_items"]}
        return {
            "balance": self._balance(p_kid),
            "claimed": [c["day_id"] for c in self.t["claims"] if c["kid_id"] == p_kid],
            "coop_solved": [s["day_id"] for s in self.t["coop_solves"] if s["kid_id"] == p_kid],
            "coop_paid": [int(r["ref"]) for r in self.t["ledger"] if r["kid_id"] == p_kid and r["reason"] == "coop_bonus"],
            "items": [{**{k: i.get(k) for k in ("id", "name", "description", "price", "kind", "per_kid_limit", "image_url")},
                       "remaining": i["stock"] - sum(p["item_id"] == i["id"] for p in open_),
                       "mine": sum(p["item_id"] == i["id"] and p["kid_id"] == p_kid for p in open_)}
                      for i in sorted(items.values(), key=lambda i: (i["price"], i["id"])) if i["active"]],
            "purchases": [{**{k: p[k] for k in ("id", "status", "price_paid", "purchased_at", "requested_at", "redeemed_at")},
                           "name": items[p["item_id"]]["name"], "kind": items[p["item_id"]]["kind"]}
                          for p in sorted(open_, key=lambda p: p["purchased_at"], reverse=True) if p["kid_id"] == p_kid]}

    def _adjust_coins(self, p_kid, p_amount, p_note):
        if not any(k["id"] == p_kid for k in self.t["kids"]):
            return {"ok": False, "reason": "invalid"}
        if not p_amount:
            return {"ok": False, "reason": "zero"}
        bal = self._balance(p_kid)
        if bal + p_amount < 0:
            return {"ok": False, "reason": "negative", "balance": bal}
        self._ledger(p_kid, p_amount, "adjustment", (p_note or "").strip() or None)
        self.save("ledger")
        return {"ok": True, "balance": bal + p_amount}

    def _debug_reset_kid(self, p_kid):
        for t in ("ledger", "purchases", "coop_solves", "claims"):
            self.t[t] = [r for r in self.t[t] if r["kid_id"] != p_kid]
        self.save("ledger", "purchases", "coop_solves", "claims")
        return {"ok": True}

class Query:
    def __init__(self, db: LocalClient, name: str):
        self.db, self.name, self.cols, self.filters, self.sort = db, name, "*", [], None
        self.op, self.payload = "select", None

    def select(self, cols: str = "*"):
        self.cols = cols; return self
    def update(self, payload: dict):
        self.op, self.payload = "update", payload; return self
    def upsert(self, payload: dict):
        self.op, self.payload = "upsert", payload; return self
    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val); return self
    def neq(self, col, val):
        self.filters.append(lambda r: r.get(col) != val); return self
    def lte(self, col, val):
        self.filters.append(lambda r: r.get(col) is not None and r[col] <= val); return self
    def in_(self, col, vals):
        self.filters.append(lambda r: r.get(col) in vals); return self
    def order(self, col, desc=False):
        self.sort = (col, desc); return self

    def _shape(self, row: dict) -> dict:
        if self.cols.strip() == "*":
            return dict(row)
        out = {}
        for part in re.findall(r"\w+\([^)]*\)|\w+", self.cols):
            if "(" in part:   # embedded relation, e.g. shop_items(name,kind)
                rel, sub = part.rstrip(")").split("(")
                target = next(r for r in self.db.t[rel] if r["id"] == row[EMBED_FK[rel]])
                out[rel] = {c: target.get(c) for c in sub.split(",")}
            else:
                out[part] = row.get(part)
        return out

    def execute(self):
        with _lock:
            rows = [r for r in self.db.t[self.name] if all(f(r) for f in self.filters)]
            if self.op == "update":
                for r in rows:
                    r.update(self.payload)
                self.db.save(self.name)
                return _res([dict(r) for r in rows])
            if self.op == "upsert":   # only admin(id = 1) uses it
                old = next((r for r in self.db.t[self.name] if r["id"] == self.payload["id"]), None)
                old.update(self.payload) if old else self.db.t[self.name].append(dict(self.payload))
                self.db.save(self.name)
                return _res([dict(self.payload)])
            if self.sort:
                col, desc = self.sort
                rows = sorted(rows, key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
            return _res([self._shape(r) for r in rows])
