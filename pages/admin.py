import io, zipfile
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from lib import auth
from lib.db import table, rpc

KIND_ICON = {"present": "🎁", "voucher": "🎟️"}

st.title("🔐 Admin")
if auth.admin_ok():
    rows = (table("purchases").select("id,status,purchased_at,redeemed_at,price_paid,kids(name),shop_items(name,kind)")
            .order("purchased_at", desc=True).execute().data)
    df = pd.DataFrame([{"Artículo": p["shop_items"]["name"], "Tipo": p["shop_items"]["kind"], "Niño/a": p["kids"]["name"],
                        "Estado": p["status"], "Precio": p["price_paid"], "Comprado": p["purchased_at"][:16],
                        "Canjeado": (p["redeemed_at"] or "")[:16]} for p in rows])

    st.subheader("Resumen")
    bought = df[df["Estado"] != "cancelled"] if rows else df
    if bought.empty:
        st.caption("Todavía no hay compras.")
    else:
        st.dataframe(pd.crosstab(bought["Artículo"], bought["Niño/a"], margins=True, margins_name="Total"))

    st.subheader("Compras activas")
    for p in (p for p in rows if p["status"] == "owned"):
        item = p["shop_items"]
        with st.container(border=True):
            st.markdown(f"{KIND_ICON[item['kind']]} **{item['name']}** · {p['kids']['name']} · {p['purchased_at'][:10]}")
            c1, c2 = st.columns(2)
            if item["kind"] == "voucher" and c1.button("Marcar como canjeado", key=f"r{p['id']}", type="primary"):
                (table("purchases").update({"status": "redeemed", "redeemed_at": datetime.now(timezone.utc).isoformat()})
                 .eq("id", p["id"]).eq("status", "owned").execute())
                st.rerun()
            if c2.button("Cancelar y reembolsar", key=f"c{p['id']}"):
                rpc("cancel_purchase", {"p_purchase": p["id"]})
                st.rerun()

    st.subheader("Todas las compras")
    st.dataframe(df, hide_index=True)

    # TODO: adjust stock / coins (ledger 'adjustment' row)

    st.subheader("Copia de seguridad")
    if st.button("Preparar export CSV"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for t in ["kids", "days", "claims", "coop_solves", "shop_items", "purchases", "ledger"]:
                z.writestr(f"{t}.csv", pd.DataFrame(table(t).select("*").execute().data).to_csv(index=False))
        st.download_button("Descargar ZIP", buf.getvalue(), "backup.zip", "application/zip")
