import httpx
import streamlit as st
from supabase import ClientOptions, create_client, Client
from lib.clock import debug_on

@st.cache_resource
def get_client() -> Client:
    # Debug mode never touches Supabase: it reads and writes the JSON copy in local_db/.
    if debug_on():
        from lib.localdb import LocalClient
        return LocalClient()
    cfg = st.secrets["supabase"]
    # httpx drops idle connections after 5 s, so nearly every click reconnected and paid
    # DNS + TLS again (5-15 s locally behind the WSL DNS proxy). Keep them for 10 minutes.
    http = httpx.Client(http2=True, timeout=120, limits=httpx.Limits(keepalive_expiry=600))
    return create_client(cfg["url"], cfg["service_key"], ClientOptions(httpx_client=http))

def rpc(name: str, params: dict) -> dict:
    return get_client().rpc(name, params).execute().data

def table(name: str):
    return get_client().table(name)
