import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def get_client() -> Client:
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["service_key"])

def rpc(name: str, params: dict) -> dict:
    return get_client().rpc(name, params).execute().data

def table(name: str):
    return get_client().table(name)
