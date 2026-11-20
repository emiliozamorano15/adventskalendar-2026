# CLAUDE.md

Advent calendar for the user's kids. A daily story chapter and riddle lead to a hidden QR code. Scanning it earns coins, and the kids spend coins in a PIN-protected shop on presents and vouchers. Parents redeem vouchers offline and tick them off on the admin page. Streamlit app on Community Cloud, Supabase Postgres backend. UI text is Spanish; docs and code comments are English.

## Environment

All code runs inside the uv venv at `.venv` (Python 3.13). The Bash tool starts a fresh shell each call, so prefix commands:

```bash
source .venv/bin/activate && <command>
```

- Install/update deps: `uv pip install -r requirements.txt` (`requirements.txt` is the single dependency source; Streamlit Cloud reads it, so there is no pyproject or lock file)
- Run app: `streamlit run app.py`
- Seed DB: `python scripts/seed_content.py [--reset]`
- Claim QR PNGs per day: `python scripts/make_qr.py` (writes `qr_out/`)
- Kid login links: `python scripts/print_kid_links.py`
- Syntax check: `python -m compileall -q app.py lib pages scripts`

Anything that touches the DB needs `.streamlit/secrets.toml` (git-ignored, mode 600). Keys: `APP_URL`, `ADMIN_PIN`, `[supabase] url`, `[supabase] service_key`, and `[kid_pins]` (kid name to 4-digit PIN string). Never print or echo its values. The local file exists, but `[supabase]` and the `[kid_pins]` names hold placeholders until the user fills them in.

Local network quirks on the user's WSL machine (corporate network). Streamlit Cloud has neither:

- TLS inspection re-signs HTTPS traffic. httpx (used by supabase-py) trusts only certifi and fails with `CERTIFICATE_VERIFY_FAILED`. Prefix commands with `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`; the system bundle holds the corporate root.
- The WSL DNS proxy (`10.255.255.254`) never answers AAAA queries for `*.supabase.co`, so every dual-stack lookup (Python `getaddrinfo` with `AF_UNSPEC`, curl without `-4`) stalls 15 s, while IPv4 lookups return at once. Forcing IPv4 inside one process works. A persistent hook in `.venv` (`.pth`/`sitecustomize`) was refused, so the real fix is the WSL DNS config, which is the user's call.

## Testing

- SQL: `sql/test_functions.sql` asserts the behavior of every function inside `begin ... rollback`. On Supabase, paste it into the SQL editor. Locally there is no Postgres or Docker; use `pgserver` in a separate Python 3.12 venv outside the repo (it has no cp313 wheels and does not belong in `requirements.txt`). Before running `schema.sql` there, create roles `anon` and `authenticated` and stub `gen_random_bytes(int)`, because pgserver ships without pgcrypto. Run `schema.sql`, `functions.sql`, then `test_functions.sql`, and look for `functions.sql self-check OK`.
- Pages: `streamlit.testing.v1.AppTest` with `lib.db.get_client` monkeypatched to a fake client renders pages without Supabase. Pass absolute paths to `AppTest.from_file`. No such test is committed.

## Architecture

- `app.py`: router. `?claim=<secret>` opens `pages/claim.py` with hidden nav. Otherwise a nav with story / wallet / shop / admin.
- `lib/db.py`: `@st.cache_resource` Supabase client with the service-role key. `table(name)` and `rpc(name, params)` helpers.
- `lib/auth.py`:
  - `current_kid()` resolves from `st.session_state["kid"]`, then `?kid=<token>`, else renders the name + PIN form and returns `None`.
  - `pin_confirmed(kid)` gates the shop. It passes when `st.session_state["pin_ok"] == kid["id"]`, which a PIN login sets; a token-link login has to enter the PIN.
  - PINs are PBKDF2-SHA256 (200k rounds, `salt_hex$digest_hex`). 5 failures lock the kid for 10 min.
  - `admin_ok()` compares against `st.secrets["ADMIN_PIN"]`.
- `lib/economy.py`: balance = `sum(ledger.amount)`, RPC wrappers (`claim`, `buy`, `coop_solve`), `unlocked_days()`.
- `lib/clock.py`: `today_berlin()`. Use it for any "today" logic; Cloud servers run in UTC.
- `pages/*.py`: each kid page calls `auth.current_kid()` and renders only if it returns a kid. Shop also requires `auth.pin_confirmed()`. Admin shows a crosstab summary, open purchases (redeem button on vouchers only, refund on all), full history, and a CSV backup.
- Flash messages across `st.rerun()`: stash in `st.session_state`, pop at the top of the page (see `shop_msg`). `st.success` right before `st.rerun()` never shows.
- `scripts/*`: run outside Streamlit. `scripts/_client.py` parses `.streamlit/secrets.toml` with `tomllib`. Scripts prepend the repo root to `sys.path` so they can import `lib`.
- `content/days.json`: real calendar content (kids with name + level, shop_items, days). Git-ignored folder; never commit it.
- Kid PINs: only `scripts/seed_content.py` reads `[kid_pins]`. It validates every kid's PIN before `--reset` runs, then upserts `kids.pin_hash`. The app never reads plaintext kid PINs; login checks the hash in the DB.

## Data model (`sql/schema.sql`, `sql/functions.sql`)

Tables: `kids` (`level` easy|hard), `days`, `claims`, `coop_solves`, `shop_items` (`kind` present|voucher, unique `name`), `purchases` (`status` owned|redeemed|cancelled), `ledger`. RLS enabled with no policies, so only the service key works.

All coin movement goes through `ledger` rows (`claim`, `coop_bonus`, `purchase`, `refund`, `adjustment`). Writes that move coins live in `security definer set search_path = public` plpgsql functions, revoked from `public/anon/authenticated`:

- `claim_day(p_kid, p_secret)`: rejects invalid / future / already-claimed; returns `{ok, reason, coins, day_id}`.
- `record_coop_solve(p_kid, p_day, p_answer)`: only `coop` days up to today; compares `lower(btrim())` of the answer; pays `coop_bonus` to both kids once both solved. Reasons: `invalid`, `future`, `wrong`.
- `buy_item(p_kid, p_item)`: locks item + kid, checks balance and stock. `shared` scope: `stock` is one pool, `per_kid_limit` caps each kid. `per_kid` scope: `stock` caps each kid. Reasons: `not_found`, `no_coins`, `sold_out`, `limit`.
- `cancel_purchase(p_purchase)`: owned to cancelled with refund.

Marking a voucher redeemed is a plain `update purchases` from `pages/admin.py`, guarded by `.eq("status", "owned")`; it moves no coins.

## Rules

- New coin-moving logic goes into a SQL function, never into read-modify-write Python. Python reads balances; Postgres writes them.
- Kid-facing queries must never select `days.answer` or `days.secret`. `unlocked_days()` filters `date <= today_berlin()` so future chapters never reach the browser; keep that filter.
- Schema changes: keep `schema.sql` and `functions.sql` re-runnable (`if not exists`, `create or replace`, an `alter ... add column if not exists` line in the upgrades block at the end of `schema.sql`). The user applies them by hand in the Supabase SQL editor; there is no migration tool. Changing a function's arguments needs a `drop function if exists` of the old signature, or Postgres keeps both overloads.
- plpgsql reads an `IF` condition up to the first `THEN`, so an inline `CASE ... THEN` inside `IF` is a syntax error. Assign the `CASE` to a variable first.
- `qr_out/` holds claim secrets. Keep it git-ignored.
- The seed upserts with `default_to_null=False`, so a key missing from one row gets the column default instead of `NULL`.

## Known issues

- A claim QR scan opens a new browser session, so the kid enters the PIN again unless that browser already has a session.
- Presents stay in the admin "Compras activas" list for good, since only vouchers get a redeemed state.

Open TODOs live in `README.md`.
