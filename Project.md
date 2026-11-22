
# Adventskalender 2026: Quest & Shop
 
Project design document · v2 · 22 November 2026 (updated to match the app as built)
 
## 1. Overview
 
This year's advent calendar for two kids (11 and 13) combines a **story-driven treasure hunt** with a **coin economy and shop**. Each day (1–24 December) the kids read a short story chapter on a Streamlit web app, solve a riddle that points to a physical hiding spot, and scan a printed QR code found there. The scan credits coins to their personal wallet. They spend coins in a shop on vouchers (experiences, privileges) and presents. When a kid wants to use a voucher, they tap "Usar", the parent gets an email, and the parent confirms it in the app after the activity. On 24 December a finale pays off the story and leads to the big gift.
 
The digital side stays on Streamlit (as in the previous year's app) and uses only free tools.
 
## 2. Goals and constraints
 
**Goals**
 
- A shared story experience with enough individual challenge that neither kid is just tagging along.
- One set of physical QR codes, each kid scanning on their own phone, coins landing in the right wallet.
- A fair shop: limited stock, no race-condition bugs, full tracking of purchases and redemptions.
- Parent-only redemption of vouchers.
- Low maintenance during December: the app should run itself.
**Constraints**
 
- Digital side built with Streamlit.
- Free tools only (hosting, database, code hosting).
- Ready before 1 December 2026 (about 18 days from this document).
- No real user accounts (no emails or passwords); identity is a personal link plus a short PIN.
## 3. The game dynamic
 
### 3.1 Daily loop
 
1. **Morning:** the kid opens their personal link and reads the day's chapter, ending with a riddle (a variant matched to their age and level).
2. **Hunt:** the answer points to a physical spot in the house or garden where a QR code is hidden.
3. **Scan:** scanning the QR code credits the day's coins to the kid's wallet and unlocks the next story beat.
4. **Shop:** whenever they like, they spend coins on vouchers and presents.
5. **Redemption:** when they want to use a voucher, the kid taps "Usar" in *Mis cosas*. The parent gets an email with a link and marks the voucher as done in the admin page after the activity. Presents are marked as handed over the same way.
### 3.2 Day types
 
The story is shared. Roughly:
 
| Day type | How it works | Approx. days |
| --- | --- | --- |
| **Standard** | Same chapter and same hiding spot; each kid gets a riddle variant at their own level (harder cipher or multi-step clue for the older one). Each scans on their own phone and earns their own coins. | \~15 |
| **Split** | Same story beat, but each kid has a different riddle and a different hiding spot. | \~4 |
| **Co-op** | Each kid's page shows half of a clue; they must combine the halves to get the answer. Both receive a bonus only when both have solved it. | \~4 |
| **Finale (24 Dec)** | Needs results collected from the whole month; final chapter and the big gift. | 1 |
 
Only about 24 spots plus a handful of extras for split days need to be hidden.
 
### 3.3 Co-op bonus (the only bonus mechanic)
 
- Each kid submits the combined answer on their own phone.
- A `coop_solves` record is written per kid.
- When both kids have a correct submission for that day, the bonus coins are credited to both, exactly once.
- A kid who solves first sees "waiting for your sibling".
- There are no streak or rivalry bonuses.
### 3.4 Coin economy (draft numbers to tune)
 
- Base reward 20 coins per day, 50 on 24 December.
- Co-op bonus 15 extra coins per kid on each of the 4 co-op days.
- Total over the month: up to 570 coins per kid (23 days × 20 + 50 on the 24th + 4 × 15 co-op).
- Shop price tiers: candy 1, everyday vouchers 20–50 (up to 2 per kid), treats 60–120, family activities 180 (one per kid). Buying one of everything would cost about three times a kid's coins, so they still choose.
- A kid can afford a first voucher on day 1.
- Aim: each kid can afford several small items and one or two big ones, but not everything. A saving-goal progress bar in *Mis cosas* would make saving visible (not built yet).
- The final numbers should be checked against the list of vouchers once the content is written.
### 3.5 Shop, vouchers and presents

- Every item has a **price**, a **kind** (voucher or present), a **stock** and a **per-kid limit**:
  - *Stock* is the number of pieces for all kids together (e.g. 2 cinema trips for the family: whoever buys first gets them).
  - *Per-kid limit* caps how many pieces one kid can buy (default 1).
  - Remaining stock is computed from non-cancelled purchases, so a refund frees the piece.
- Kids fill a cart and buy it in one go. The purchase is atomic: the whole cart succeeds or nothing is bought, and two kids buying the last item at the same moment cannot both succeed.
- Every purchase is tracked per kid: item, price paid, purchase time, status and the time of each status change.

**Purchase states**

| Status | Meaning | Who moves it |
| --- | --- | --- |
| owned | Bought | The shop |
| requested | The kid wants to use the voucher now | The kid ("Usar"); "Deshacer" takes it back |
| redeemed | Voucher used or present handed over | The parent ("Hecho" / "Entregado") |
| cancelled | Refunded; coins and stock come back | The parent ("Reembolsar") |

The original draft planned a QR code per voucher that the parent scans. The built app replaces it with the email link, which needs no printing and works from the parent's phone.

### 3.6 Fairness rules
 
- Base coins are equal for both kids; harder riddles may pay slightly more, but not enough to feel unfair.
- Sharing an answer is allowed: each kid still has to scan with their own login to get coins.
- A kid can claim each day only once.
## 4. Architecture
 
```
Kid's phone  ──►  Streamlit app (Community Cloud)  ──►  Supabase Postgres
Parent phone ──►  (same app, admin pages + PIN)          (all data and content)
Printed QR codes = URLs carrying a per-day secret
```
 
The kids' browsers talk only to the Streamlit app. Streamlit runs server-side and is the only component that talks to the database, so database credentials never reach the kids' devices.
 
### 4.1 Components
 
| Need | Tool | Notes |
| --- | --- | --- |
| Hosting | Streamlit Community Cloud | Free. Apps sleep after about 12 hours without traffic. Unlimited public apps but only one private app. About 1 GB memory. |
| Database | Supabase (Postgres) | Free plan: 500 MB database, 2 active projects. Projects pause after a week of inactivity. |
| Code | GitHub | Required by Streamlit Cloud. |
| QR codes | Python `segno` or `qrcode`, run locally | No hosting; PNGs are printed. |
| Development | Claude Code | Same approach as the previous Streamlit apps. |
 
Free-tier limits can change, so they should be re-checked before launch on the Streamlit and Supabase pricing and docs pages.
 
### 4.2 Free-tier behaviours to plan around
 
- **Streamlit sleeps after about 12 quiet hours.** Visitors see a "wake this app" button and a wait of around half a minute. Mitigation: accept the wake-up click, or the parent opens the app at breakfast time. An automated wake-up (scheduled GitHub Actions job) is possible but not planned.
- **Supabase free projects pause after one week of inactivity.** The kids' daily use prevents this in December, but a development project left idle for 7+ days can pause and needs a manual restore.
- **No automatic daily backups on the free plan.** An admin "export CSV" function is built in and should be run periodically.
### 4.3 Secrets and repository exposure
 
On the free plan only one app can be private; other apps need a public repo. Therefore:
 
- All content (chapters, riddles, answers, QR secrets) lives in the **database**, loaded by a seed script from a local file that is never committed.
- Keys live in `st.secrets` (Streamlit Cloud dashboard) and a git-ignored local `secrets.toml`.
- Row-level security is enabled on every table with no public policies; only the Streamlit server uses the service key.
- If the one private-app slot is free, it can be used for this app, but the design is safe either way.
### 4.4 Environments

Supabase's free plan has no branching, so there is one live project. For testing, `DEBUG = true` in the local `secrets.toml` makes the app read and write a JSON copy of the database (`local_db/`, filled by `scripts/export_local.py`) instead of Supabase. The Streamlit Cloud secrets never set `DEBUG`.

Debug mode adds a sidebar panel: a simulated date (e.g. 24 December opens every door, and claims use that date), switching kid without a PIN, adding or removing coins, scanning the simulated day's code, and resetting one kid's scans, purchases and coins. The whole flow, from claim to shop to voucher redemption, can be tested in November.

## 5. Identity and flows
 
### 5.1 Identity
 
- Each kid has a **personal link** `app-url/?kid=<long-random-token>`, saved as a bookmark or home-screen shortcut, plus a 4-digit **PIN**.
- The QR code carries only the day's secret: `app-url/?claim=<day-secret>`.
- If a scan opens in a browser that doesn't know the kid, the page shows "Who are you?" (name dropdown) and asks for the PIN, then claims the coins. A dropdown without a PIN would let one sibling claim as the other, so the PIN stays.
- PIN attempts are rate-limited (e.g. 10-minute lockout after 5 failures).
### 5.2 Claim flow
 
1. Scan opens `?claim=<secret>`.
2. Identify the kid (token or dropdown + PIN).
3. Look up the day by secret. Reject if the day's date is in the future (server time, Europe/Berlin).
4. Reject if the kid already claimed that day (unique constraint on kid + day).
5. Insert the claim and a ledger row with the day's coins.
6. Open the calendar with the reward; the day's door turns ✅.
Claims for past days remain valid, so a missed scan is not lost.
 
### 5.3 Co-op flow
 
1. Each kid sees their half of the clue.
2. Each submits the combined answer; the server checks it.
3. A correct submission inserts a `coop_solves` row.
4. When both kids have a row for that day and the bonus has not been paid, two ledger rows are written (one per kid) in one transaction.
### 5.4 Purchase flow

The shop calls a single database function `buy_cart(kid, items[])` (see section 6.3). On success the items appear in *Mis cosas*.

### 5.5 Redemption flow

1. In *Mis cosas*, the kid taps **Usar** on a voucher. Its status becomes `requested`, and the parent gets an email with a link `app-url/?redeem=<purchase_id>`. A mistaken tap can be taken back with **Deshacer**.
2. The link opens the admin page (admin PIN) with that voucher on top. The *Pendiente* tab lists every requested voucher and every present not yet handed over.
3. After the activity, the parent taps **Hecho** (or **Entregado** for a present). Status becomes `redeemed` with a timestamp.
4. **Reembolsar** cancels a purchase that is still open and books a refund row in the ledger.
## 6. Data structure
 
### 6.1 Tables
 
| Table | Columns (main) | Purpose |
| --- | --- | --- |
| `kids` | id, name, token, pin\_hash, level (easy / hard), lockout fields | Identity of the two kids |
| `days` | id, date, day\_type, chapter\_text, riddle\_easy, riddle\_hard, answer, coop\_half\_a, coop\_half\_b, secret, base\_coins, coop\_bonus | All daily content and settings |
| `claims` | id, kid\_id, day\_id, claimed\_at; unique (kid\_id, day\_id) | One scan per kid per day |
| `coop_solves` | id, kid\_id, day\_id, solved\_at; unique (kid\_id, day\_id) | Co-op submissions |
| `shop_items` | id, name (unique), description, price, kind (voucher / present), stock (shared), per\_kid\_limit, active, image\_url | Shop catalogue |
| `purchases` | id, kid\_id, item\_id, price\_paid, status (owned / requested / redeemed / cancelled), purchased\_at, requested\_at, redeemed\_at | Every purchase |
| `admin` | id (always 1), pin\_hash | Admin PIN once changed in the app |
| `ledger` | id, kid\_id, amount, reason, ref, created\_at | Every coin movement |
 
### 6.2 The ledger
 
A kid's balance is the **sum of their ledger rows**. Claims, co-op bonuses, purchases (negative), refunds and admin adjustments each add one row. This gives a full history, makes mistakes reversible and avoids balance drift.
 
### 6.3 Atomic purchase

A Postgres function `buy_cart(kid_id, item_ids[])` runs in one transaction, with one id per piece. It:

1. Locks the kid, then the items in id order, so two carts cannot deadlock.
2. Checks every item: active, enough stock for all kids together, within the per-kid limit.
3. Computes the kid's balance from the ledger and checks it covers the cart total.
4. Only then inserts one `purchases` row and one negative `ledger` row per piece.
5. Returns success or a clear reason for failure (not found, sold out, limit, not enough coins).

Because every check runs before the first insert, a refused cart writes nothing.

### 6.4 Other database functions

- `claim_day`, `record_coop_solve`: book a scan or a co-op answer (section 5).
- `cancel_purchase`: refund an open purchase.
- `adjust_coins`: admin correction, never below a zero balance.
- `kid_state`: everything a kid page shows (balance, scanned days, shop stock, purchases) in one call, for speed on a phone.
- `debug_reset_kid`: test database only.

All of them are callable only with the service key.

## 7. Technical details
 
### 7.1 Date lock and time
 
"Today" is computed on the server in the Europe/Berlin timezone. Chapters for future days are never sent to the browser, so changing the device date or editing the URL reveals nothing. Past chapters stay readable.
 
### 7.2 QR secrets
 
- Each day has a random secret of at least 8 characters, stored in the database.
- QR codes encode only the claim URL with that secret; the secret is useless before its date.
- The voucher email uses the purchase ID in a redeem URL; the admin PIN is what authorises redemption.
### 7.3 Repository layout

```
app.py                # router; ?claim and ?redeem entry points; debug panel
pages/                # story.py, shop.py, mine.py, claim.py, admin.py
lib/                  # db.py, auth.py, clock.py, economy.py, ui.py, debug.py, notify.py
sql/                  # schema.sql, functions.sql, test_functions.sql
scripts/              # seed_content.py, make_qr.py, print_kid_links.py
.gitignore            # secrets.toml, content/, qr_out/
```

### 7.4 Pages

The app is designed for a phone first: a tab bar at the bottom (Calendario, Tienda, Mis cosas), the kid's coins on every page, grids that reflow to 2–4 columns, and one database call per page.

- **Calendario:** today's chapter and riddle (kid-specific variant) on top, then 24 doors to reread past days.
- **Tienda:** item cards with a picture, price, remaining stock and "Añadir"; a cart bar at the bottom; buying in one step.
- **Mis cosas:** vouchers with "Usar", presents still to come, used items, coin history, PIN change.
- **Admin (PIN-protected, linked from Mis cosas and from the voucher email):** pending vouchers and presents, per-kid balance with coin adjustments and purchases, the riddle overview, PINs, CSV backup.

### 7.5 Backups
 
The free Supabase plan has no daily backups, so the admin page includes a CSV export of all tables. Run it weekly and before any manual database change.
 
## 8. Implementation plan: digital
 
The timeline starts mid-November, leaving about 18 days before 1 December.
 
| Phase | Days | Work |
| --- | --- | --- |
| 1. Foundation | 1–6 | Accounts (GitHub, Streamlit Cloud, Supabase dev + prod); schema; seed script; auth (token + PIN, lockout); claim flow with date lock |
| 2. Core features | 7–12 | Ledger; wallet page; shop and `buy_item` function; vouchers with QR; admin page and redemption; co-op logic |
| 3. Content and test | 13–16 | Load story and riddles (two difficulty variants); generate QR codes; full dress rehearsal on dev with dummy kids; test race conditions (two phones buying the last item) and sleeping-app behaviour |
| 4. Launch prep | 17–18 | Set real PINs; reset and seed prod; deploy; export first backup; final test scan from each kid's phone |
 
## 9. Implementation plan: physical
 
| Step | When | Work |
| --- | --- | --- |
| 1. Story outline | Before content writing | Choose the theme and plot arc; define which days are standard, split, co-op and the finale |
| 2. Hiding spots | With the story | List about 24 spots plus extras for split days; vary difficulty and avoid spots the kids check by habit |
| 3. Print QR codes | After content is final | Generate PNGs per day; print on stickers or paper; laminate or protect against water if a spot is outside; label the back with the day number so the right code goes in the right place |
| 4. Hiding schedule | Set up | Decide whether all codes are hidden in advance or each is placed the evening before (safer against peeking, more work) |
| 5. Vouchers | Before launch | Design the voucher cards; vouchers themselves are digital, with printed versions optional |
| 6. Finale prep | By mid-December | Prepare the big gift and its hiding place, and the final physical element (e.g. a lockbox if the finale uses a code) |
| 7. Daily routine | 1–24 Dec | Check the app is awake in the morning, confirm that day's code is in place, check redemptions in the admin page |
| 8. Spare codes | Before launch | Keep a duplicate of each QR code in case one is damaged or taken |
 
## 10. Risks and mitigations
 
| Risk | Mitigation |
| --- | --- |
| App asleep when kids open it | Accept the wake-up click or open it yourself in the morning |
| Supabase project paused | Daily use in December; check the dev project during development; know how to restore from the dashboard |
| Content exposed in a public repo | All content in the database; keys in `st.secrets` |
| Sibling guesses the other's PIN | PIN lockout after repeated failures |
| Two kids buy the last item at once | Atomic `buy_cart` function with locking |
| Testing in November shows nothing | Debug mode on a local copy of the database: simulated date, coins, scans, reset |
| Data loss or mistake | Ledger-based balances; refund rows; CSV exports |
| A printed QR code is damaged or lost | Duplicates; claims can be done late |
| Free-tier limits change | Re-check Streamlit and Supabase limits before launch |
 
## 11. Open decisions
 
- Story theme (spy agency, detective case, fantasy quest, sci-fi mission) and the 24-day outline.
- Final coin numbers and the voucher catalogue with prices and stock.
- Whether the repo is public or uses the one free private-app slot.
- Whether QR codes are hidden all at once or placed the evening before.
- Saving-goal progress bar in *Mis cosas*.
- Whether to automate waking the app or just open it each morning.
- What the big finale gift and its hiding place are.
