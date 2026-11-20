# Adventskalender 2026: El misterio de la Navidad

An advent calendar web app for kids. Each day from 1 to 24 December, a new story chapter unlocks with a riddle. The answer points to a spot in the house where a parent hid a QR code. Scanning the code earns coins, and the kids spend coins in a PIN-protected shop on presents and vouchers. Parents see every purchase on the admin page and tick off vouchers once the kid has used them.

The UI is in Spanish. Dates follow the Europe/Berlin timezone.

## How it works

1. The kid opens their personal link (`?kid=<token>`) or picks their name and enters a 4-digit PIN. Five wrong PINs lock the account for 10 minutes.
2. **Historia** shows every chapter up to today. The app never fetches future days from the database.
3. The kid solves the riddle, finds the printed QR and scans it. The QR opens `?claim=<secret>`, and the `claim_day` database function books the coins once per kid per day. A code scanned before its date earns nothing.
4. **Tienda** asks for the kid's PIN once per session, even after a personal-link login, so a sibling holding the link can't spend someone else's coins. `buy_item` checks balance and stock inside one transaction.
5. **Monedero** shows the balance, the coin history and every purchase with its status. The kid can change their PIN here by typing the current one first.
6. **Admin** (admin PIN) shows a purchase count per item and kid, the open purchases, and the full history. You mark a voucher as redeemed after the kid has used it, or cancel any open purchase with a refund. Presents need no step after purchase. You can also set a new PIN for a kid, which lifts a lockout, and change the admin PIN.

The balance lives in a `ledger` table. Every coin movement (claim, co-op bonus, purchase, refund) adds one row, and the balance is the sum of those rows.

## Stack

- [Streamlit](https://streamlit.io) for the UI, hosted on Streamlit Community Cloud
- [Supabase](https://supabase.com) Postgres for storage. The app talks to it with the service-role key from the server side only. Row Level Security is on with no policies, so the anon key gets nothing.
- [segno](https://segno.readthedocs.io) for the printed claim QR codes

## Local setup

You need [uv](https://docs.astral.sh/uv/) and a Supabase project.

```bash
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Run every command below with the venv active.

### 1. Database

In the Supabase SQL editor, run `sql/schema.sql`, then `sql/functions.sql`. Both files are safe to re-run, and re-running them upgrades a database built from an older version. One catch: if `shop_items` already holds two rows with the same name, the new unique index fails. Delete the duplicates or wipe the data with `seed_content.py --reset` first.

To check the functions, run `sql/test_functions.sql` in the same editor. It exercises claims, purchases, refunds and co-op answers inside a transaction, rolls everything back, and prints `functions.sql self-check OK`.

### 2. Secrets

All secrets live in `.streamlit/secrets.toml`, which git ignores:

```toml
APP_URL = "https://your-app.streamlit.app"   # base URL baked into every claim QR
ADMIN_PIN = "000000"                          # initial admin PIN, see below

[supabase]
url = "https://your-project.supabase.co"
service_key = "your-service-role-key"

[kid_pins]
"Ana" = "1234"      # one initial 4-digit PIN per kid, keyed by the name in content/days.json
"Martín" = "5678"   # quote names with accents or spaces
```

Use the deployed URL for `APP_URL` before you print QR codes. Codes printed with `http://localhost:8501` only work on your own machine.

Both PIN settings hold starting values only:

- The seed script reads `[kid_pins]` when it creates a kid and stores a salted hash in the database. Name matching ignores case, so `"ISABEL"` covers `Isabel`. Running the seed again leaves existing PINs alone, so a PIN the kid or you changed in the app stays.
- The app checks `ADMIN_PIN` until you change the admin PIN on the admin page. From then on it checks the hash in the database and ignores `ADMIN_PIN`.

The app itself reads `APP_URL`, `ADMIN_PIN` and `[supabase]`.

### 3. Content

Write the calendar in `content/days.json`. Git ignores the whole `content/` folder so the kids can't read the answers on GitHub.

```json
{
  "kids": [
    {"name": "Ana", "level": "hard"}
  ],
  "shop_items": [
    {"name": "Cine con papá", "description": "Elige la peli", "price": 40,
     "stock": 1, "stock_scope": "per_kid", "kind": "voucher"},
    {"name": "Lego", "price": 80, "stock": 2, "stock_scope": "shared",
     "per_kid_limit": 1, "kind": "present"}
  ],
  "days": [
    {"date": "2026-12-01", "day_type": "standard",
     "chapter_text": "Capítulo 1...", "riddle_easy": "...", "riddle_hard": "...",
     "base_coins": 10}
  ]
}
```

**Kids:** `level` is `easy` or `hard` and picks which riddle the kid sees. It defaults to `easy`. PINs go in `secrets.toml`, not here; the seed stops before touching the database if a kid has no valid PIN.

**Shop items:** `name` must be unique because the seed matches existing items by name.
- `kind` is `voucher` (an experience you tick off as redeemed later, the default) or `present`.
- `stock_scope: "shared"` puts `stock` units in one pool for all kids, and each kid can buy at most `per_kid_limit` (default 1).
- `stock_scope: "per_kid"` lets each kid buy up to `stock`.
- `"active": false` hides an item from the shop.

**Days:** `date`, `day_type` (`standard`, `split`, `coop`, `finale`), `chapter_text`, `riddle_easy`, `riddle_hard`, `answer`, `coop_half_a`, `coop_half_b`, `base_coins` (default 10), `coop_bonus` (default 0). The database generates each day's QR `secret`. On co-op days, `answer` is what both kids must type; case and surrounding spaces don't matter.

Keys you leave out get the column default.

### 4. Seed and run

```bash
python scripts/seed_content.py           # add --reset to wipe all tables first
streamlit run app.py
```

Running the seed again updates kid levels, shop items and days in place. Existing day secrets stay, so QR codes you already printed keep working.

### 5. Print QR codes and links

```bash
python scripts/make_qr.py          # one PNG per day in qr_out/
python scripts/print_kid_links.py  # personal login link per kid
```

`qr_out/` is git-ignored. Keep it that way: anyone holding those images can claim every day's coins.

## Deploy

On Streamlit Community Cloud, point the app at repo `emiliozamorano15/adventskalendar-2026`, branch `main`, main file `app.py`, and paste the contents of `secrets.toml` into the Secrets box. Cloud installs dependencies from `requirements.txt`.

Work happens on `dev`. To release, merge `dev` into `main`, and Cloud redeploys. If the merge brings SQL changes, run `sql/schema.sql` and `sql/functions.sql` in Supabase first.

## Project layout

```
app.py                  router: ?claim opens the claim page, otherwise the nav bar
lib/auth.py             kid login (link token or PIN with lockout), shop PIN gate, PIN change and reset, admin PIN
lib/db.py               cached Supabase client, table() and rpc() helpers
lib/economy.py          balance, ledger, claim/buy/coop calls, unlocked days
lib/clock.py            Europe/Berlin "today"
pages/                  story, wallet, shop, claim, admin
scripts/                seed, QR export, kid links (read .streamlit/secrets.toml directly)
sql/schema.sql          tables, indexes, RLS
sql/functions.sql       claim_day, record_coop_solve, buy_item, cancel_purchase
sql/test_functions.sql  self-check for the functions, rolls back
```

## TODO

- Co-op days: show half A or B to each kid and add the answer form. `economy.coop_solve(kid_id, day_id, answer)` and the database already check the answer.
- Saving-goal progress bar in the wallet
- Remaining stock in the shop
- Admin tools to adjust stock and coins (an `adjustment` row in the ledger)
