"""Generate one claim QR PNG per day into qr_out/. Usage: python scripts/make_qr.py"""
import pathlib, sys, segno
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts._client import client

sb, cfg = client()
out = pathlib.Path("qr_out"); out.mkdir(exist_ok=True)
for d in sb.table("days").select("date,secret").order("date").execute().data:
    url = f"{cfg['APP_URL'].rstrip('/')}/?claim={d['secret']}"
    segno.make(url, error="m").save(out / f"dia_{d['date'][-2:]}.png", scale=10, border=2)
    print(d["date"], url)
