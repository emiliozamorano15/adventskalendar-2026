import streamlit as st
import pandas as pd
from lib import auth, economy
from lib.db import table

STATUS = {("voucher", "owned"): "por canjear", ("voucher", "redeemed"): "canjeado ✅",
          ("present", "owned"): "comprado"}

kid = auth.current_kid()
if kid:
    st.title("💰 Monedero")
    st.metric("Monedas", economy.balance(kid["id"]))
    # TODO: saving-goal progress bar (st.progress)

    st.subheader("Mis compras")
    rows = (table("purchases").select("status,purchased_at,shop_items(name,kind)")
            .eq("kid_id", kid["id"]).neq("status", "cancelled").order("purchased_at", desc=True).execute().data)
    if not rows:
        st.caption("Todavía no has comprado nada.")
    for p in rows:
        item = p["shop_items"]
        st.write(f"**{item['name']}** · {STATUS[item['kind'], p['status']]}")

    st.subheader("Historial")
    hist = economy.ledger(kid["id"])
    st.dataframe(pd.DataFrame(hist)[["created_at", "amount", "reason"]] if hist else pd.DataFrame(), hide_index=True)
