# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/). The top version is the current one.

## [0.4.0] - 2026-11-22

`kid_state` returns two new fields; already applied to Supabase.

### Added

- Co-op days are playable: each kid sees one half of the clue, both type the team answer, and once both got it right each gets the co-op bonus. The card shows "Falta tu hermano/a" or "Resuelto en equipo".
- Chapter texts for all 24 days (live database; copy in `content/chapters.json`, git-ignored).

## [0.3.0] - 2026-11-22

### Added

- "Soy papá/mamá" link to Admin under the login form on the home page.
- `scripts/make_qr.py` also writes `qr_out/qr_codes.pdf`: all claim codes sorted by day, six per A4 page, each labelled with the day and the hiding place. It refuses a placeholder `APP_URL`.

### Fixed

- The shop loaded its pictures one by one on a cold start (about 10 s), so a tap on "Añadir" seemed lost and a second tap put the item in the cart twice. Pictures now load in parallel (about 0.5 s), and every add shows a toast.

### Changed

- Harder riddles: easy and hard texts now differ every day, no text names its own answer, and the co-op halves no longer give the answer away. Hiding places, answers and story clues are unchanged. Applied to the live database; the texts are in `content/riddles.json` (git-ignored) for `content/days.json`.

- Shop cards all have the same size: pictures are cropped to 16:9 on the server (cached), and the grid uses a fixed row height.
- More coins, same or lower prices: 20 coins per day (was 10), 50 on 24 December, co-op bonus 15 (was 10), so up to 570 coins per kid instead of 280. Family activities cost 180 (was 220) with one per kid; everyday vouchers allow two per kid. Applied to the live database; update `content/days.json` the same way before you seed again.

## [0.2.1] - 2026-11-22

### Added

- `assets/family-portrait.png`, a cartoon family portrait (not shown in the app yet).

## [0.2.0] - 2026-11-22

Already applied to the live Supabase project on 2026-11-22: `sql/schema.sql` and `sql/functions.sql`. `claim_day` and `record_coop_solve` gained a parameter, and `kid_state`, `adjust_coins` and `debug_reset_kid` are new.

### Added

- Shop pictures: `shop_items.image_url`, filled with Wikimedia Commons thumbnails (credits in the README). Cards without one keep the emoji.
- Debug mode (`DEBUG = true` in secrets) works on a local JSON copy of the database (`local_db/`, `scripts/export_local.py`) and never touches Supabase: simulated date that opens every door and applies to claims, kid switch without PIN, coin adjustment, scanning the simulated day, resetting a kid.
- **Mis cosas** page: vouchers with "Usar" and "Deshacer", presents still to come, used items, coin history, PIN change, log out, link to Admin.
- Voucher email links straight to the voucher in Admin (`?redeem=<purchase_id>`).
- Presents can be marked as handed over ("Entregado"), so they no longer stay open forever.
- Admin can add or remove coins per kid with a note (`adjust_coins`; the balance never drops below 0).
- Bottom tab bar on kid pages, coin balance on every page, today's chapter shown on the calendar without opening a door, cart bar at the bottom of the shop.
- `kid_state` database function: one call loads everything a kid page shows.
- `scripts/check_localdb.py`: self-check for the debug-mode database copy.
- `CHANGELOG.md` and the release workflow in `CLAUDE.md`: version bump, ponytail review and graphify update on every release.

### Changed

- Redesigned for phones: door grid with 4 per row, 2 shop cards per row, name buttons on the login, rounded theme with Nunito and Fredoka fonts, developer menu hidden.
- A scanned code now opens the calendar with the reward instead of the shop.
- Admin: tabs Pendiente, Niños, Días, Ajustes; only the open tab queries the database.
- Day content and kid names are cached for 10 minutes.
- Requires Streamlit 1.67 or newer.
- `graphify-out/` is git-ignored.

### Fixed

- `kids.token` and `days.secret` had no default on databases created from an older schema, so the seed failed for any new kid or day. `schema.sql` now sets both defaults.

### Removed

- The Cuenta dialog in the shop, replaced by Mis cosas.

## [0.1.0] - 2026-11-22

First version, covering everything up to commit `c4bd89e`.

### Added

- Door calendar: 24 doors, each opening that day's chapter and riddle.
- QR claim codes that pay coins and redirect to the shop.
- PIN-protected shop with a cart, a Cuenta dialog, presents and vouchers; voucher activation emails the parent.
- Admin page: voucher confirmation, purchases per kid, riddles, PIN reset and change, backup.
- Admin PIN stored as a hash in the database; kid PINs hashed with PBKDF2, with lockout after 5 failures.
- Seed script, QR generator and kid login link script.

### Fixed

- SQL functions are dropped before being recreated, so return-type changes apply.
- Schema updates and faster page loads.
