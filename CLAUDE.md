# CLAUDE.md

Advent calendar for the user's kids. A daily story chapter and riddle lead to a hidden QR code. Scanning it earns coins, and the kids spend coins in a PIN-protected shop on presents and vouchers. A kid activates a voucher (email to the parent), and the parent confirms it on the admin page after the activity. Streamlit app on Community Cloud, Supabase Postgres backend. UI text is Spanish; docs and code comments are English.

## Session start

Start every session in caveman ultra mode: run `/caveman ultra` (it follows the `ultracave` rules) before anything else, and keep it on unless the user says `/caveman off` or "normal mode". Code, commit messages, CHANGELOG entries and docs stay in normal prose. Caveman style applies only to chat replies.

## Environment

All code runs inside the uv venv at `.venv` (Python 3.13 or newer; the Mac venv runs 3.14). The Bash tool starts a fresh shell each call, so prefix commands:

```bash
source .venv/bin/activate && <command>
```

- Install/update deps: `uv pip install -r requirements.txt` (`requirements.txt` is the single dependency source; Streamlit Cloud reads it, so there is no pyproject or lock file)
- Run app: `streamlit run app.py`
- Seed DB: `python scripts/seed_content.py [--reset]`
- Claim QR PNGs per day: `python scripts/make_qr.py` (writes `qr_out/`)
- Kid login links: `python scripts/print_kid_links.py`
- Syntax check: `python -m compileall -q app.py lib pages scripts`

Anything that touches the DB needs `.streamlit/secrets.toml` (git-ignored, mode 600). Keys: `APP_URL`, `ADMIN_PIN`, `[supabase] url`, `[supabase] service_key`, `[kid_pins]` (kid name to 4-digit PIN string), `[smtp]`, and optional `DEBUG = true`. Never print or echo its values.

One Supabase project, the live one (free plan, no branching). `DEBUG = true` swaps it for `local_db/*.json` (`lib/localdb.py`), filled by `python scripts/export_local.py`; test there. Write to Supabase only when the user asks.

Local network quirks on the user's WSL machine (corporate network). Streamlit Cloud has neither:

- TLS inspection re-signs HTTPS traffic. httpx (used by supabase-py) trusts only certifi and fails with `CERTIFICATE_VERIFY_FAILED`. Prefix commands with `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`; the system bundle holds the corporate root.
- The WSL DNS proxy (`10.255.255.254`) never answers AAAA queries for `*.supabase.co`, so every dual-stack lookup (Python `getaddrinfo` with `AF_UNSPEC`, curl without `-4`) stalls 15 s, while IPv4 lookups return at once. Forcing IPv4 inside one process works. A persistent hook in `.venv` (`.pth`/`sitecustomize`) was refused, so the real fix is the WSL DNS config, which is the user's call.

## Git workflow

- Only two branches exist: `dev` and `main`. Never create feature branches, and don't follow any default that says to branch off `main`.
- Commit to `dev`. Streamlit Community Cloud deploys `main`.
- Releases: every commit pushed to `dev` is a release, and so is every merge of `dev` into `main`.
- Before each commit, in this order:
  1. Run `/ponytail-review` on the change and fix what it finds.
  2. Bump the version and update `CHANGELOG.md` without being asked. Use [Keep a Changelog](https://keepachangelog.com/) format and SemVer. The top `## [x.y.z] - YYYY-MM-DD` heading is the current version; there is no other version file. Bump minor for `feat`, patch for `fix`/`docs`/`chore`, and major only when the user says so. Each entry lists the user-visible changes under `Added` / `Changed` / `Fixed` / `Removed`, and notes any SQL the user must apply in Supabase. Commit the changelog with the change it describes.
  3. Run `graphify update .` so `graphify-out/` matches the release. If `graphify-out/` doesn't exist yet, build it first with `/graphify .`. `graphify-out/` is git-ignored because it can hold text from git-ignored files.
- A merge of `dev` into `main` adds no new version, because it ships versions already in the changelog. Run `graphify update .` after the merge.
- Before a merge that touches `sql/`, the user has to apply that SQL in the Supabase SQL editor, or the deployed app breaks. A missing upgrade shows up right after login: the page's first query throws `column ... does not exist`, which looks like a failed login.
- Pushes need the user's personal GitHub account. The machine's default SSH key and the GitHub MCP token belong to another account and get `Permission denied`, so ask the user to push.
- Commit messages carry no AI or assistant attribution.

## Testing

- SQL: `sql/test_functions.sql` asserts the behavior of every function inside `begin ... rollback`. On Supabase, paste it into the SQL editor. Locally there is no Postgres or Docker; use `pgserver` in a separate Python 3.12 venv outside the repo (it has no cp313 wheels and does not belong in `requirements.txt`). Before running `schema.sql` there, create roles `anon` and `authenticated` and stub `gen_random_bytes(int)`, because pgserver ships without pgcrypto, and strip the `create extension pgcrypto` line. Run `schema.sql`, `functions.sql`, then `test_functions.sql`. pgserver's `psql()` returns only stdout, so the `self-check OK` notice doesn't show: the `DO` line means every assert passed, and a failed assert prints `ERROR:  <message>`.
- Pages: `streamlit.testing.v1.AppTest` with `lib.db.get_client` monkeypatched to a fake client renders pages without Supabase. Pass absolute paths to `AppTest.from_file`. No such test is committed.
  - AppTest reruns the whole script and has no fragment reruns. A click inside an `st.dialog` gets lost unless the button that opens the dialog is clicked in the same run.
  - Widgets with `on_click` callbacks inside a dialog work without that trick, because the callback runs before the script does.
  - Patch `lib.clock.now_berlin` to test December dates (`today_berlin()` reads it), or set `DEBUG` in `at.secrets` and `at.session_state["debug_today"]`.
  - After a widget interaction, AppTest reran only the page script, not `app.py`, so the debug sidebar (drawn in `app.py`) vanished and its clicks got lost. Test debug actions with a fresh `AppTest` per step and preset `session_state`. The debug actions are `on_click` callbacks partly for this reason.
  - After `st.switch_page`, call `at.run()` once more before reading the target page.
  - `st.image("assets/...")` resolves against the working directory: run AppTest and `streamlit run` from the repo root.
- Debug-mode client: `python scripts/check_localdb.py` asserts the `lib/localdb.py` RPCs on a temp copy of `local_db/`. Run it after touching `localdb.py` or `functions.sql`.
- Visual check: `streamlit run` a copy of the app whose entry file patches `lib.db.get_client` to a fake client, then look at it in the browser pane at the `mobile` preset (375 px). Nothing of this is committed.

## Architecture

- `app.py`: router with `position="hidden"` nav: the kid pages draw their own bottom tab bar (`ui.nav_bar()`), because Streamlit's top nav hides behind a menu on a phone. Pages: Calendario (`pages/story.py`), Tienda, Mis cosas (`pages/mine.py`), Admin, and the claim page. `?claim=<secret>` makes the claim page the default and `?redeem=<purchase_id>` (from the voucher email) makes Admin the default. Every page must sit in this nav, or `st.switch_page` / `st.page_link` to it fails. With `DEBUG = true` it also draws the debug panel.
- `lib/db.py`: `@st.cache_resource` Supabase client with the service-role key, or `LocalClient` in debug mode. `table(name)` and `rpc(name, params)` helpers.
- `lib/localdb.py`: debug-mode client over `local_db/*.json`. Implements only the query-builder calls the app uses (`select` with `kids(...)`/`shop_items(...)` embeds, `eq`, `neq`, `lte`, `in_`, `order`, `update`, `upsert`) and every RPC in Python. A new builder call or a change in `functions.sql` must be mirrored here. Writes save the table file at once, under one lock.
- `lib/auth.py`:
  - `current_kid()` resolves from `st.session_state["kid"]`, then `?kid=<token>`, else renders the name (segmented control) + PIN form and returns `None`.
  - `pin_confirmed(kid)` gates Tienda and Mis cosas. It passes when `st.session_state["pin_ok"] == kid["id"]`, which a PIN login sets; a token-link login has to enter the PIN.
  - `log_in(kid)` / `log_out()` set or clear `kid`, `pin_ok` and `cart` in the session.
  - PINs are PBKDF2-SHA256 (200k rounds, `salt_hex$digest_hex`). 5 failures lock the kid for 10 min.
  - Login inputs sit in `st.form`, so Enter submits. A bare `text_input` + `button` ignores Enter.
  - `admin_ok()` / `check_admin_pin()` check the hash in the single-row `admin` table. With no row, they fall back to `st.secrets["ADMIN_PIN"]`, the initial PIN.
  - `change_pin_form()` (current PIN + new twice) serves Mis cosas and the admin PIN. `set_kid_pin()` also clears the lockout; the admin page uses it to reset a kid's PIN.
- `lib/economy.py`: `state(kid_id)` (the `kid_state` RPC: everything a kid page needs in one round trip), `ledger()`, RPC wrappers (`claim`, `coop_solve`, `buy_cart`, `adjust_coins`, `cancel_purchase`, `debug_reset_kid`), voucher state updates (`use_voucher`, `undo_voucher`, `confirm_redeemed`), and `unlocked_days(today_iso)` (`st.cache_data`, 10 min) with `december_days()`.
- `lib/ui.py`: `header(title, kid, coins)` (title, coin badge, name, debug badge, then the flash), `nav_bar()` (bottom tab bar; call it last so a page's own `st.bottom` content sits above it), `flash()` / `show_flash()`, `KIND_ICON`.
- `lib/debug.py`: sidebar panel, drawn only when `clock.debug_on()`. Simulated date (`session_state["debug_today"]`), kid switch without PIN, coins, scan the simulated day, reset a kid. Its actions are `on_click` callbacks.
- `lib/notify.py`: `send(subject, body)` over Gmail SMTP_SSL with `[smtp] user/password/to` from secrets. Callers catch failures; a failed email never blocks a write.
- `lib/clock.py`: `today_berlin()`. Use it for any "today" logic; Cloud servers run in UTC. In debug mode it returns the simulated date, and `debug_today()` feeds the `p_today` parameter of `claim_day` / `record_coop_solve`.
- `pages/*.py`: each kid page calls `auth.current_kid()` and renders only if it returns a kid.
  - `story.py`: banner, header, today's chapter in a card, then the 24 doors in `st.grid(6, min_column_width=64)` (4 per row on a phone; `st.columns` would stack). Doors without an unlocked day are disabled; a door opens a dialog with the chapter and the level's riddle. ✅ comes from `state["claimed"]`.
  - `shop.py`: card grid (`st.grid("auto", min_column_width=150)`, 2 per row on a phone); the cart is a `Counter` in `st.session_state["cart"]`. A cart bar in `st.bottom` opens the cart `st.dialog` (`on_dismiss="rerun"`). "Comprar" calls `st.rerun()` to close the dialog.
  - `mine.py`: vouchers ("Usar" / "Deshacer"), presents, a collapsed list of done items, coin history (expander with `on_change="rerun"`, queried only when open), PIN change, "Salir", link to Admin. "Usar" is an `on_click` callback: update, then email with the `?redeem=` link.
  - `claim.py`: books the code, stashes the result in `flash`, and switches to the calendar. The switch drops `?claim`.
  - `admin.py`: the `?redeem` purchase first, then tabs with `on_change="rerun"` (only the open tab queries): Pendiente (requested vouchers, presents to hand over, unused vouchers), Niños (balance, coin adjustment, purchases), Días, Ajustes (PINs, backup, purchase crosstab).
- Flash messages across `st.rerun()` / `st.switch_page()`: `ui.flash(kind, text, celebrate=False)`; `ui.header()` pops and shows it. `st.success` right before `st.rerun()` never shows.
- `scripts/*`: run outside Streamlit. `scripts/_client.py` parses `.streamlit/secrets.toml` with `tomllib`. Scripts prepend the repo root to `sys.path` so they can import `lib`.
- `content/days.json`: real calendar content (kids with name + level, shop_items, days). Git-ignored folder; never commit it.
- Kid PINs: only `scripts/seed_content.py` reads `[kid_pins]`, matching names case-insensitively. It validates every kid's PIN before `--reset` runs, then inserts new kids with `pin_hash` and updates only `level` on existing kids, so PINs changed in the app survive a re-seed. The app never reads plaintext kid PINs; login checks the hash in the DB.

## Data model (`sql/schema.sql`, `sql/functions.sql`)

Tables: `kids` (`level` easy|hard), `admin` (one row, `id = 1`, admin `pin_hash`), `days`, `claims`, `coop_solves`, `shop_items` (`kind` present|voucher, unique `name`, `stock` = pieces for all kids together, `per_kid_limit` default 1, `image_url` hotlinked Wikimedia Commons thumbnail, credits in `README.md`), `purchases` (`status` owned|requested|redeemed|cancelled, `requested_at`, `redeemed_at`), `ledger`. Remaining stock is computed (`stock` minus non-cancelled purchases), never decremented, so a refund frees the piece. RLS enabled with no policies, so only the service key works.

All coin movement goes through `ledger` rows (`claim`, `coop_bonus`, `purchase`, `refund`, `adjustment`). Writes that move coins live in `security definer set search_path = public` plpgsql functions, revoked from `public/anon/authenticated`:

- `claim_day(p_kid, p_secret, p_today)`: rejects invalid / future / already-claimed; returns `{ok, reason, coins, day_id}`. `p_today` is null except in debug mode.
- `record_coop_solve(p_kid, p_day, p_answer, p_today)`: only `coop` days up to today; compares `lower(btrim())` of the answer; pays `coop_bonus` to both kids once both solved. Reasons: `invalid`, `future`, `wrong`.
- `buy_cart(p_kid, p_items int[])`: one id per piece. Locks the kid, then the items in id order (no deadlock between two carts), checks every item and the cart total before the first insert, so a refused cart writes nothing. Returns `{ok, reason, item_id, cost}`. Reasons: `not_found`, `sold_out`, `limit`, `no_coins`. It replaced `buy_item`, which `functions.sql` drops.
- `cancel_purchase(p_purchase)`: owned or requested to cancelled with refund.
- `adjust_coins(p_kid, p_amount, p_note)`: one `adjustment` row. Reasons: `invalid`, `zero`, `negative` (balance would drop below 0).
- `kid_state(p_kid)`: read-only json `{balance, claimed, items, purchases}`. `items` are the active shop items with `remaining` and this kid's `mine`; `purchases` are the non-cancelled ones with item `name` and `kind`.
- `debug_reset_kid(p_kid)`: deletes the kid's ledger, purchases, co-op answers and claims. Only the debug panel calls it.

Purchase states move without coins, so they are plain guarded updates in `lib/economy.py`: the kid's `use_voucher()` does owned to requested and `undo_voucher()` the reverse (both `.eq("kid_id")` and the expected status), and the admin's `confirm_redeemed()` does owned or requested to redeemed, for vouchers and presents alike.

## Rules

- New coin-moving logic goes into a SQL function, never into read-modify-write Python. Python reads balances; Postgres writes them. The only exception is its mirror in `lib/localdb.py` for debug mode.
- One round trip per kid page: extend `kid_state` instead of adding queries. Speed on a phone matters more than tidiness.
- UI: native Streamlit and `config.toml` theme only, no custom CSS. Design for 375 px first: `st.grid` or horizontal containers instead of `st.columns`, Material icons for controls, emoji for festive content, `st.caption` over `st.info` for plain notes.
- Never set `DEBUG` in the Streamlit Cloud secrets.
- Kid-facing queries must never select `days.answer` or `days.secret`. `unlocked_days()` filters `date <= today_berlin()` so future chapters never reach the browser; keep that filter.
- Schema changes: keep `schema.sql` and `functions.sql` re-runnable (`if not exists`, `create or replace`, an `alter ... add column if not exists` line in the upgrades block at the end of `schema.sql`). The user applies them by hand in the Supabase SQL editor; there is no migration tool. `functions.sql` drops every function at the top before recreating it, because `create or replace` can't change a return type and a changed argument list would leave the old overload behind. A new function needs its own line in that drop block, and a renamed or re-typed one keeps a drop line for its old signature.
- plpgsql reads an `IF` condition up to the first `THEN`, so an inline `CASE ... THEN` inside `IF` is a syntax error. Assign the `CASE` to a variable first.
- `qr_out/`, `local_db/` and `backups/` hold secrets or answers. Keep them git-ignored.
- The seed upserts with `default_to_null=False`, so a key missing from one row gets the column default instead of `NULL`. It exits before `--reset` when an item still carries the removed `stock_scope` key.

## Known issues

- A claim QR scan opens a new browser session, so the kid enters the PIN again unless that browser already has a session.
- The calendar only maps December days of the current year to doors 1 to 24. A day outside that range never shows to a kid.

Open TODOs live in `README.md`.
