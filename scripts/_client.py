import tomllib, pathlib
from supabase import create_client

def client():
    p = pathlib.Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    cfg = tomllib.loads(p.read_text())
    return create_client(cfg["supabase"]["url"], cfg["supabase"]["service_key"]), cfg
