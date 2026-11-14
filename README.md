# Adventskalender 2026 – El misterio de la Navidad

Streamlit + Supabase advent calendar (story, QR treasure hunt, coins and shop).
See the design doc for full details.

## Setup
1. Supabase SQL editor: run `sql/schema.sql`, then `sql/functions.sql`.
2. `cp .streamlit/secrets.toml.example .streamlit/secrets.toml` and fill in values.
3. `cp content/days.example.json content/days.json` and write the real content (never commit it).
4. `pip install -r requirements.txt`
5. `python scripts/seed_content.py`
6. `streamlit run app.py`
7. `python scripts/make_qr.py` / `python scripts/print_kid_links.py`

## Deploy
Streamlit Community Cloud → repo `emiliozamorano15/adventskalendar-2026`, main file `app.py`,
paste `secrets.toml` into the Secrets box.

## TODO
- kids.level (easy/hard) column + riddle variant selection
- co-op answer form, saving-goal bar, remaining stock display, admin stock/coin adjustments
