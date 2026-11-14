import io, zipfile
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from lib import auth
from lib.db import table, rpc

st.title("🔐 Admin")
if auth.admin_ok():
    rid = st.query_params.get("redeem")
    if rid:
        rows = (table("purchases").select("*,kids(name),shop_items(name)").eq("id", rid).execute().data)
        if rows:
            p = rows[0]
            st.subheader(f"{p['shop_items']['name']} – {p['kids']['name']}")
            st.caption(f"Comprado: {p['purchased_at']} · Estado: {p['status']}")
            if p["status"] == "owned":
                if st.button("Marcar como canjeado", type="primary"):
                    table("purchases").update({"status": "redeemed",
                        "redeemed_at": datetime.now(timezone.utc).isoformat()}).eq("id", rid).execute()
                    st.rerun()
                if st.button("Cancelar y reembolsar"):
                    rpc("cancel_purchase", {"p_purchase": rid}); st.rerun()
        else:
            st.error("Vale no encontrado.")

    st.subheader("Todas las compras")
    data = table("purchases").select("*,kids(name),shop_items(name)").order("purchased_at", desc=True).execute().data
    st.dataframe(pd.json_normalize(data) if data else pd.DataFrame(), hide_index=True)

    # TODO: adjust stock / coins (ledger 'adjustment' row)

    st.subheader("Copia de seguridad")
    if st.button("Preparar export CSV"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for t in ["kids", "days", "claims", "coop_solves", "shop_items", "purchases", "ledger"]:
                z.writestr(f"{t}.csv", pd.DataFrame(table(t).select("*").execute().data).to_csv(index=False))
        st.download_button("Descargar ZIP", buf.getvalue(), "backup.zip", "application/zip")
