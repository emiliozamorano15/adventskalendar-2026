import streamlit as st
import pandas as pd
from lib import auth, economy
from lib.db import table

kid = auth.current_kid()
if kid:
    st.title("💰 Monedero")
    bal = economy.balance(kid["id"])
    st.metric("Monedas", bal)
    # TODO: saving-goal progress bar (st.progress)

    st.subheader("Mis vales")
    rows = (table("purchases").select("id,status,purchased_at,shop_items(name)")
            .eq("kid_id", kid["id"]).order("purchased_at", desc=True).execute().data)
    for p in rows:
        with st.container(border=True):
            st.write(f"**{p['shop_items']['name']}** · {p['status']}")
            if p["status"] == "owned":
                st.image(economy.qr_png(f"{economy.app_url()}/?redeem={p['id']}"), width=160)

    st.subheader("Historial")
    st.dataframe(pd.DataFrame(economy.ledger(kid["id"]))[["created_at", "amount", "reason"]]
                 if economy.ledger(kid["id"]) else pd.DataFrame(), hide_index=True)
