"""Print each kid's personal link. Usage: python scripts/print_kid_links.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts._client import client
sb, cfg = client()
for k in sb.table("kids").select("name,token").execute().data:
    print(k["name"], f"{cfg['APP_URL'].rstrip('/')}/?kid={k['token']}")
