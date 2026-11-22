# Adventskalender 2026: El misterio de la Navidad

An advent calendar web app for kids. Each day from 1 to 24 December, a new story chapter unlocks with a riddle. The answer points to a spot in the house where a parent hid a QR code. Scanning the code earns coins, and the kids spend coins in a PIN-protected shop on presents and vouchers. A kid activates a voucher when they want to use it, you get an email, and you confirm it on the admin page once you've done the activity together.

The UI is in Spanish. Dates follow the Europe/Berlin timezone.

## How it works

The app is built for a phone. A tab bar at the bottom switches between **Calendario**, **Tienda** and **Mis cosas**, and every page shows the kid's name and coin balance at the top.

1. The kid opens their personal link (`?kid=<token>`) or taps their name and enters a 4-digit PIN. Five wrong PINs lock the account for 10 minutes.
2. **Calendario** shows today's chapter and riddle right under the banner, so opening the app is enough. Below it, 24 doors: 🔒 until their date, then 🎁, and ✅ once the kid has scanned that day's code. A door opens that day's chapter. The app never fetches future days from the database.
3. The kid solves the riddle, finds the printed QR and scans it. The QR opens `?claim=<secret>`, asks the kid to log in if needed, and the `claim_day` database function books the coins once per kid per day. The app then shows the calendar with the reward and the door turned ✅. A second scan of the same code earns nothing, a code scanned before its date earns nothing, and a past day's code still counts.
4. **Tienda** and **Mis cosas** ask for the kid's PIN once per session, even after a personal-link login, so a sibling holding the link can't spend someone else's coins. A PIN login skips that prompt.
   - The shop grid shows each item with its price and the pieces left. "Añadir" puts it in the cart, and a bar at the bottom shows the cart total. "Comprar" sends the whole cart to `buy_cart`, which checks balance, stock and limits in one transaction and buys all of it or nothing.
5. **Mis cosas** lists what the kid bought:
   - A voucher shows **Usar**. Tapping it marks the voucher as requested and emails you a link. **Deshacer** takes a mistaken tap back.
   - A present shows "Pronto" until you hand it over.
   - Used vouchers and received presents move to a collapsed list. The page also has the coin history, the PIN change form, "Salir" and the link to Admin.
6. **Admin** (admin PIN). The link in the voucher email opens Admin on that voucher.
   - *Pendiente*: vouchers the kids want to use, then presents to hand over. "Hecho" or "Entregado" closes one, and "Reembolsar" cancels it and returns the coins. Unused vouchers sit in a collapsed list, and you can close those too.
   - *Niños*: per kid, the balance, a form to add or remove coins with a note, and the purchases.
   - *Días*: every day with the answer, coins, both riddles and who scanned it.
   - *Ajustes*: reset a kid's PIN (also lifts a lockout), change the admin PIN, download a CSV backup, and see a purchase count per item and kid.

The balance lives in a `ledger` table. Every coin movement (claim, co-op bonus, purchase, refund, adjustment) adds one row, and the balance is the sum of those rows.

### Purchase states

| Status | Meaning | Who moves it |
| --- | --- | --- |
| `owned` | Bought | `buy_cart` |
| `requested` | The kid wants to use the voucher now | Kid ("Usar"), back to `owned` with "Deshacer" |
| `redeemed` | Voucher used or present handed over | Admin ("Hecho" / "Entregado") |
| `cancelled` | Refunded, the stock is free again | Admin ("Reembolsar", `cancel_purchase`) |

### Speed

Each kid page loads its data with one database call (`kid_state`: balance, claimed days, shop items with stock, purchases). Day content is cached for 10 minutes, kid names for 10 minutes. Admin tabs only query when opened.

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
# DEBUG = true                                # dev database only, see "Debug mode"

[supabase]
url = "https://your-project.supabase.co"
service_key = "your-service-role-key"

[kid_pins]
"Ana" = "1234"      # one initial 4-digit PIN per kid, keyed by the name in content/days.json
"Martín" = "5678"   # quote names with accents or spaces

[smtp]                                # voucher emails, sent through Gmail
user = "sender@gmail.com"
password = "abcd efgh ijkl mnop"     # a Gmail app password, not the account password
to = "parent@example.com"
```

Use the deployed URL for `APP_URL` before you print QR codes. Codes printed with `http://localhost:8501` only work on your own machine.

Both PIN settings hold starting values only:

- The seed script reads `[kid_pins]` when it creates a kid and stores a salted hash in the database. Name matching ignores case, so `"ISABEL"` covers `Isabel`. Running the seed again leaves existing PINs alone, so a PIN the kid or you changed in the app stays.
- The app checks `ADMIN_PIN` until you change the admin PIN on the admin page. From then on it checks the hash in the database and ignores `ADMIN_PIN`.

The app itself reads `APP_URL`, `ADMIN_PIN`, `[supabase]` and `[smtp]`.

For `[smtp]`, turn on 2-step verification on the sending Google account and create an app password under Security > App passwords. If sending fails, the voucher request still goes through, the kid sees a warning, and the request shows on the admin page anyway. Corporate networks often block SMTP, so test the email on the deployed app.

### Debug mode with a local copy

Debug mode never touches Supabase. It reads and writes a copy of the database in `local_db/*.json`:

1. Copy the live data once (and again whenever you want fresh data): `python scripts/export_local.py`. It overwrites `local_db/`.
2. Add `DEBUG = true` at the top level of `.streamlit/secrets.toml` and start `streamlit run app.py`. Restart the app after a new export.

`local_db/` is git-ignored: it holds the answers, the QR secrets and the PIN hashes. To start a test over, export again.

With `DEBUG = true`, the app shows a red "MODO DEBUG" badge and a panel in the sidebar (the `»` icon on a phone):

- **Fecha simulada** moves "today" for the whole app, including claims. "24 dic" opens every door.
- **Entrar como** switches kid without a PIN.
- **Ajustar monedas** gives or takes coins.
- **Escanear el código** books the simulated day's code, as if the kid had scanned it.
- **Reiniciar niño/a** deletes that kid's scans, purchases and coins (`debug_reset_kid`).

To test the whole voucher flow: switch to a kid, give coins, buy in the Tienda, tap "Usar" in Mis cosas, then confirm it in Admin.

Never set `DEBUG` on the deployed app. The panel skips the PIN, and the app would read the (missing) local files instead of the database.

`lib/localdb.py` re-implements the database functions in Python for this copy. After a change to `sql/functions.sql`, copy the change there too and run `python scripts/check_localdb.py`.

### 3. Content

Write the calendar in `content/days.json`. Git ignores the whole `content/` folder so the kids can't read the answers on GitHub.

```json
{
  "kids": [
    {"name": "Ana", "level": "hard"}
  ],
  "shop_items": [
    {"name": "Cine con papá", "description": "Elige la peli", "price": 40,
     "stock": 2, "kind": "voucher"},
    {"name": "Lego", "price": 80, "stock": 2, "per_kid_limit": 1, "kind": "present"}
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
- `kind` is `voucher` (an experience the kid activates later, the default) or `present`. The shop shows 🎟️ or 🎁.
- `stock` is the number of pieces for all kids together. Each purchase takes one, and a refund puts it back.
- `per_kid_limit` caps how many pieces one kid can buy. It defaults to 1.
- `"active": false` hides an item from the shop.
- `image_url` is the picture on the shop card. Without it, the card shows 🎟️ or 🎁.

An older version had a `stock_scope` key. Remove it: the seed refuses to run while an item still has one, and `stock` now counts the pieces for all kids together.

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

Pick Python 3.12 or newer in the Cloud app settings. The app needs Streamlit 1.67 or newer (`st.grid`, `st.bottom`, tabs with `on_change`).

Work happens on `dev`. To release, merge `dev` into `main`, and Cloud redeploys. If the merge brings SQL changes, run `sql/schema.sql` and `sql/functions.sql` in Supabase first.

The look comes from `.streamlit/config.toml`: Christmas red and fir green, Nunito and Fredoka from Google Fonts, rounded corners, and the developer menu hidden. Replace `assets/banner.png` with your own banner; any wide image works.

## Project layout

```
app.py                  router (hidden nav); ?claim opens the claim page, ?redeem opens Admin; debug panel
assets/banner.png       calendar banner (placeholder, replace it)
.streamlit/config.toml  theme: colors, fonts, radius, padding
lib/auth.py             kid login (link token or name + PIN with lockout), PIN gate, PIN change and reset, admin PIN
lib/db.py               cached Supabase client, table() and rpc() helpers
lib/economy.py          kid_state, ledger, claim/cart/coins/voucher calls, cached unlocked days
lib/ui.py               page header with the balance, bottom tab bar, flash messages
lib/debug.py            debug sidebar panel (DEBUG = true only)
lib/notify.py           voucher email through Gmail SMTP
lib/clock.py            Europe/Berlin "today", debug date override
pages/story.py          Calendario: today's chapter and the door grid
pages/shop.py           Tienda grid, cart bar and cart dialog
pages/mine.py           Mis cosas: vouchers, presents, coin history, PIN change
pages/claim.py          books a scanned code, then opens the calendar
pages/admin.py          admin tabs
lib/localdb.py          debug mode: JSON copy of the database in local_db/, with the database functions in Python
scripts/                seed, QR export, kid links, export_local.py (read .streamlit/secrets.toml directly)
sql/schema.sql          tables, indexes, RLS
sql/functions.sql       claim_day, record_coop_solve, buy_cart, cancel_purchase, kid_state, adjust_coins, debug_reset_kid
sql/test_functions.sql  self-check for the functions, rolls back
```

## Image credits

The shop pictures are thumbnails hotlinked from Wikimedia Commons, under the licenses below.

| Item id | Item | File | License |
| --- | --- | --- | --- |
| 2 | Joker | [Joker (carte de jeu).jpg](https://commons.wikimedia.org/wiki/File:Joker_(carte_de_jeu).jpg) | Public domain |
| 3 | Coche a la escuela | [Car driving along a road surrounded by trees.jpg](https://commons.wikimedia.org/wiki/File:Car_driving_along_a_road_surrounded_by_trees.jpg) | CC0 |
| 4 | Cine | [Popcorn at the cinema.jpg](https://commons.wikimedia.org/wiki/File:Popcorn_at_the_cinema.jpg) | CC BY-SA 4.0 |
| 5 | Cena | [Dinner buffet at restaurant Carusel.jpg](https://commons.wikimedia.org/wiki/File:Dinner_buffet_at_restaurant_Carusel.jpg) | CC BY-SA 4.0 |
| 6 | Tele | [Television remote control - black 01.jpg](https://commons.wikimedia.org/wiki/File:Television_remote_control_-_black_01.jpg) | CC BY-SA 4.0 |
| 7 | 3 € | [Euro coins and banknotes (cropped).jpg](https://commons.wikimedia.org/wiki/File:Euro_coins_and_banknotes_(cropped).jpg) | Public domain |
| 8 | Galletas | [Cherry chocolate chip cookies on a baking sheet.jpg](https://commons.wikimedia.org/wiki/File:Cherry_chocolate_chip_cookies_on_a_baking_sheet.jpg) | CC BY-SA 4.0 |
| 9 | Juego de mesa | [Castles of Burgundy (Board Game).jpg](https://commons.wikimedia.org/wiki/File:Castles_of_Burgundy_(Board_Game).jpg) | CC0 |
| 10 | No bañarse | [Rubber duck in glass bowl crop.jpg](https://commons.wikimedia.org/wiki/File:Rubber_duck_in_glass_bowl_crop.jpg) | Public domain |
| 11 | Paseo | [Family walk in Headwaters Forest Reserve in the Arcata Field Office (32552769627).jpg](https://commons.wikimedia.org/wiki/File:Family_walk_in_Headwaters_Forest_Reserve_in_the_Arcata_Field_Office_(32552769627).jpg) | Public domain |
| 12 | Videojuegos | [Xbox-360-Wireless-Controller-White.jpg](https://commons.wikimedia.org/wiki/File:Xbox-360-Wireless-Controller-White.jpg) | Public domain |
| 13 | Pijamada | [OutDoor 2018, Friedrichshafen (1X7A0298).jpg](https://commons.wikimedia.org/wiki/File:OutDoor_2018,_Friedrichshafen_(1X7A0298).jpg) | CC BY-SA 4.0 |
| 14 | 5 € | [Euro banknotes, First series.png](https://commons.wikimedia.org/wiki/File:Euro_banknotes,_First_series.png) | CC0 |
| 17 | Laser-Tag | [Light Amplification by Stimulated Emission of Radiation.jpg](https://commons.wikimedia.org/wiki/File:Light_Amplification_by_Stimulated_Emission_of_Radiation.jpg) | CC BY-SA 3.0 |
| 18 | Escape Room | [Escape Room - "The Expedition" (Escape Quest Bethesda).jpg](https://commons.wikimedia.org/wiki/File:Escape_Room_-_%22The_Expedition%22_(Escape_Quest_Bethesda).jpg) | CC BY-SA 4.0 |
| 19 | Papás cocinan | [Family cooking activity with kids preparing homemade fries in a cozy kitchen setting.jpg](https://commons.wikimedia.org/wiki/File:Family_cooking_activity_with_kids_preparing_homemade_fries_in_a_cozy_kitchen_setting.jpg) | CC BY 2.0 |
| 20 | Centerschock | [Kaugummis.jpg](https://commons.wikimedia.org/wiki/File:Kaugummis.jpg) | CC BY-SA 2.5 |
| 21 | Tick-tacks | [2024 Tic Tac (4).jpg](https://commons.wikimedia.org/wiki/File:2024_Tic_Tac_(4).jpg) | CC BY-SA 4.0 |
| 22 | Unendlichkeitsstift | [Pencil, propelling (AM 604071-3).jpg](https://commons.wikimedia.org/wiki/File:Pencil,_propelling_(AM_604071-3).jpg) | CC BY 4.0 |

## TODO

- Co-op days: show half A or B to each kid and add the answer form. `economy.coop_solve(kid_id, day_id, answer)` and the database already check the answer.
- Saving-goal progress bar in Mis cosas
- Admin tool to adjust stock (coins are done: Admin > Niños)
