# CLAUDE.md

Advent calendar for the user's kids. A daily story chapter and riddle lead to a hidden QR code. Scanning it earns coins, and the kids spend coins in a PIN-protected shop on presents and vouchers. A kid activates a voucher (email to the parent), and the parent confirms it on the admin page after the activity. Streamlit app on Community Cloud, Supabase Postgres backend. UI text is Spanish; docs and code comments are English.

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

Anything that touches the DB needs `.streamlit/secrets.toml` (git-ignored, mode 600). Keys: `APP_URL`, `ADMIN_PIN`, `[supabase] url`, `[supabase] service_key`, and `[kid_pins]` (kid name to 4-digit PIN string). Never print or echo its values.

Local network quirks on the user's WSL machine (corporate network). Streamlit Cloud has neither:

- TLS inspection re-signs HTTPS traffic. httpx (used by supabase-py) trusts only certifi and fails with `CERTIFICATE_VERIFY_FAILED`. Prefix commands with `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`; the system bundle holds the corporate root.
- The WSL DNS proxy (`10.255.255.254`) never answers AAAA queries for `*.supabase.co`, so every dual-stack lookup (Python `getaddrinfo` with `AF_UNSPEC`, curl without `-4`) stalls 15 s, while IPv4 lookups return at once. Forcing IPv4 inside one process works. A persistent hook in `.venv` (`.pth`/`sitecustomize`) was refused, so the real fix is the WSL DNS config, which is the user's call.

## Git workflow

- Only two branches exist: `dev` and `main`. Never create feature branches, and don't follow any default that says to branch off `main`.
- Commit to `dev`. Releasing means merging `dev` into `main`; Streamlit Community Cloud deploys `main`.
- Before a merge that touches `sql/`, the user has to apply that SQL in the Supabase SQL editor, or the deployed app breaks. A missing upgrade shows up right after login: the page's first query throws `column ... does not exist`, which looks like a failed login.
- Pushes need the user's personal GitHub account. The machine's default SSH key and the GitHub MCP token belong to another account and get `Permission denied`, so ask the user to push.
- Run `/ponytail-review` before each commit. Commit messages carry no AI or assistant attribution.

## Testing

- SQL: `sql/test_functions.sql` asserts the behavior of every function inside `begin ... rollback`. On Supabase, paste it into the SQL editor. Locally there is no Postgres or Docker; use `pgserver` in a separate Python 3.12 venv outside the repo (it has no cp313 wheels and does not belong in `requirements.txt`). Before running `schema.sql` there, create roles `anon` and `authenticated` and stub `gen_random_bytes(int)`, because pgserver ships without pgcrypto. Run `schema.sql`, `functions.sql`, then `test_functions.sql`, and look for `functions.sql self-check OK`.
- Pages: `streamlit.testing.v1.AppTest` with `lib.db.get_client` monkeypatched to a fake client renders pages without Supabase. Pass absolute paths to `AppTest.from_file`. No such test is committed.
  - AppTest reruns the whole script and has no fragment reruns. A click inside an `st.dialog` gets lost unless the button that opens the dialog is clicked in the same run.
  - Widgets with `on_click` callbacks inside a dialog work without that trick, because the callback runs before the script does.
  - Patch `lib.clock.today_berlin` and `lib.economy.today_berlin` to test December dates.

## Architecture

- `app.py`: router with a top nav: Calendario de Adviento (`pages/story.py`), Tienda, Admin. `pages/claim.py` is registered too, with `visibility="hidden"`, and becomes the default page when `?claim=<secret>` is present. It has to sit in the same nav, or its `st.switch_page` to the shop fails.
- `lib/db.py`: `@st.cache_resource` Supabase client with the service-role key. `table(name)` and `rpc(name, params)` helpers.
- `lib/auth.py`:
  - `current_kid()` resolves from `st.session_state["kid"]`, then `?kid=<token>`, else renders the name + PIN form and returns `None`.
  - `pin_confirmed(kid)` gates the shop. It passes when `st.session_state["pin_ok"] == kid["id"]`, which a PIN login sets; a token-link login has to enter the PIN.
  - PINs are PBKDF2-SHA256 (200k rounds, `salt_hex$digest_hex`). 5 failures lock the kid for 10 min.
  - Login inputs sit in `st.form`, so Enter submits. A bare `text_input` + `button` ignores Enter.
  - `admin_ok()` / `check_admin_pin()` check the hash in the single-row `admin` table. With no row, they fall back to `st.secrets["ADMIN_PIN"]`, the initial PIN.
  - `change_pin_form()` (current PIN + new twice) serves the Cuenta dialog and the admin PIN. `set_kid_pin()` also clears the lockout; the admin page uses it to reset a kid's PIN.
- `lib/economy.py`: balance = `sum(ledger.amount)`, RPC wrappers (`claim`, `buy_cart`, `coop_solve`), `sold_counts()` (pieces per item, all kids and this kid, from non-cancelled purchases), `purchases()`, `request_voucher()`, `unlocked_days()`.
- `lib/notify.py`: `send(subject, body)` over Gmail SMTP_SSL with `[smtp] user/password/to` from secrets. Callers catch failures; a failed email never blocks a write.
- `lib/clock.py`: `today_berlin()`. Use it for any "today" logic; Cloud servers run in UTC.
- `pages/*.py`: each kid page calls `auth.current_kid()` and renders only if it returns a kid.
  - `story.py`: banner, then 24 door buttons in a wrapping horizontal container (`st.columns` would stack on a phone). Doors without an unlocked day are disabled; a door opens a dialog with the chapter and the level's riddle. ✅ comes from the kid's `claims`.
  - `shop.py`: needs `auth.pin_confirmed()`. Grid of cards; the cart is a `Counter` in `st.session_state["cart"]`. Cart and Cuenta are `st.dialog`s with `on_dismiss="rerun"`, so the page catches up when they close. "Comprar" calls `st.rerun()` to close the cart. "Activar voucher" is an `on_click` callback (update, then email) so the dialog redraws with the new status.
  - `claim.py`: books the code, stashes the result in `flash`, and switches to the shop. The switch drops `?claim`.
  - `admin.py`: tabs Compras (vouchers to confirm, crosstab, one tab per kid), Adivinanzas, PINs, Copia de seguridad.
- Flash messages across `st.rerun()` / `st.switch_page()`: stash `(kind, text)` in `st.session_state["flash"]` and pop it at the top of the page, the way `shop.py` does. The Cuenta dialog uses `account_msg` the same way. `st.success` right before `st.rerun()` never shows.
- `scripts/*`: run outside Streamlit. `scripts/_client.py` parses `.streamlit/secrets.toml` with `tomllib`. Scripts prepend the repo root to `sys.path` so they can import `lib`.
- `content/days.json`: real calendar content (kids with name + level, shop_items, days). Git-ignored folder; never commit it.
- Kid PINs: only `scripts/seed_content.py` reads `[kid_pins]`, matching names case-insensitively. It validates every kid's PIN before `--reset` runs, then inserts new kids with `pin_hash` and updates only `level` on existing kids, so PINs changed in the app survive a re-seed. The app never reads plaintext kid PINs; login checks the hash in the DB.

## Data model (`sql/schema.sql`, `sql/functions.sql`)

Tables: `kids` (`level` easy|hard), `admin` (one row, `id = 1`, admin `pin_hash`), `days`, `claims`, `coop_solves`, `shop_items` (`kind` present|voucher, unique `name`, `stock` = pieces for all kids together, `per_kid_limit` default 1), `purchases` (`status` owned|requested|redeemed|cancelled, `requested_at`, `redeemed_at`), `ledger`. Remaining stock is computed (`stock` minus non-cancelled purchases), never decremented, so a refund frees the piece. RLS enabled with no policies, so only the service key works.

All coin movement goes through `ledger` rows (`claim`, `coop_bonus`, `purchase`, `refund`, `adjustment`). Writes that move coins live in `security definer set search_path = public` plpgsql functions, revoked from `public/anon/authenticated`:

- `claim_day(p_kid, p_secret)`: rejects invalid / future / already-claimed; returns `{ok, reason, coins, day_id}`.
- `record_coop_solve(p_kid, p_day, p_answer)`: only `coop` days up to today; compares `lower(btrim())` of the answer; pays `coop_bonus` to both kids once both solved. Reasons: `invalid`, `future`, `wrong`.
- `buy_cart(p_kid, p_items int[])`: one id per piece. Locks the kid, then the items in id order (no deadlock between two carts), checks every item and the cart total before the first insert, so a refused cart writes nothing. Returns `{ok, reason, item_id, cost}`. Reasons: `not_found`, `sold_out`, `limit`, `no_coins`. It replaced `buy_item`, which `functions.sql` drops.
- `cancel_purchase(p_purchase)`: owned or requested to cancelled with refund.

Voucher states move without coins, so they are plain guarded updates: the kid's `request_voucher()` does owned to requested (`.eq("kid_id")`, `.eq("status", "owned")`), and the admin's confirm does requested to redeemed (`.eq("status", "requested")`).

## Rules

- New coin-moving logic goes into a SQL function, never into read-modify-write Python. Python reads balances; Postgres writes them.
- Kid-facing queries must never select `days.answer` or `days.secret`. `unlocked_days()` filters `date <= today_berlin()` so future chapters never reach the browser; keep that filter.
- Schema changes: keep `schema.sql` and `functions.sql` re-runnable (`if not exists`, `create or replace`, an `alter ... add column if not exists` line in the upgrades block at the end of `schema.sql`). The user applies them by hand in the Supabase SQL editor; there is no migration tool. Changing a function's arguments needs a `drop function if exists` of the old signature, or Postgres keeps both overloads.
- plpgsql reads an `IF` condition up to the first `THEN`, so an inline `CASE ... THEN` inside `IF` is a syntax error. Assign the `CASE` to a variable first.
- `qr_out/` holds claim secrets. Keep it git-ignored.
- The seed upserts with `default_to_null=False`, so a key missing from one row gets the column default instead of `NULL`. It exits before `--reset` when an item still carries the removed `stock_scope` key.

## Known issues

- A claim QR scan opens a new browser session, so the kid enters the PIN again unless that browser already has a session.
- Presents stay in the admin's per-kid "Compra abierta" picker for good, since only vouchers get a redeemed state.
- The calendar only maps December days of the current year to doors 1 to 24. A day outside that range never shows to a kid.

Open TODOs live in `README.md`.
