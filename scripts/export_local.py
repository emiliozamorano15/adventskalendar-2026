"""Copy every table from Supabase into local_db/*.json for debug mode (DEBUG = true reads only these files).
Overwrites local_db/. Usage: python scripts/export_local.py"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts._client import client
from lib.localdb import DIR, TABLES

sb, _ = client()
DIR.mkdir(exist_ok=True)
for t in TABLES:
    rows = sb.table(t).select("*").execute().data
    (DIR / f"{t}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(t, len(rows))
