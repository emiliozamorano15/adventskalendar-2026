import io, zipfile
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from lib import auth, economy
from lib.db import table, rpc

KIND_ICON = {"present": "🎁", "voucher": "🎟️"}
STATUS = {"owned": "comprado", "requested": "pedido ⏳", "redeemed": "canjeado ✅", "cancelled": "cancelado"}

st.title("🔐 Admin")
if auth.admin_ok():
    rows = (table("purchases")
            .select("id,kid_id,status,purchased_at,requested_at,redeemed_at,price_paid,kids(name),shop_items(name,kind)")
            .order("purchased_at", desc=True).execute().data)
    kids = table("kids").select("id,name").order("name").execute().data
    df = pd.DataFrame([{"Artículo": p["shop_items"]["name"], "Tipo": p["shop_items"]["kind"], "Niño/a": p["kids"]["name"],
                        "Estado": STATUS[p["status"]], "Precio": p["price_paid"], "Comprado": p["purchased_at"][:16],
                        "Pedido": (p["requested_at"] or "")[:16], "Canjeado": (p["redeemed_at"] or "")[:16]} for p in rows],
                      columns=["Artículo", "Tipo", "Niño/a", "Estado", "Precio", "Comprado", "Pedido", "Canjeado"])
    t_buy, t_days, t_pins, t_backup = st.tabs(["Compras", "Adivinanzas", "PINs", "Copia de seguridad"])

    with t_buy:
        st.subheader("Vouchers por confirmar")
        pending = [p for p in rows if p["status"] == "requested"]
        if not pending:
            st.caption("Ningún voucher pendiente.")
        for p in pending:
            with st.container(border=True):
                st.markdown(f"🎟️ **{p['shop_items']['name']}** · {p['kids']['name']} · pedido {p['requested_at'][:16]}")
                c1, c2 = st.columns(2)
                if c1.button("Confirmar canje", key=f"r{p['id']}", type="primary"):
                    (table("purchases").update({"status": "redeemed", "redeemed_at": datetime.now(timezone.utc).isoformat()})
                     .eq("id", p["id"]).eq("status", "requested").execute())
                    st.rerun()
                if c2.button("Cancelar y reembolsar", key=f"c{p['id']}"):
                    rpc("cancel_purchase", {"p_purchase": p["id"]})
                    st.rerun()

        st.subheader("Resumen")
        bought = df[df["Estado"] != STATUS["cancelled"]]
        if bought.empty:
            st.caption("Todavía no hay compras.")
        else:
            st.dataframe(pd.crosstab(bought["Artículo"], bought["Niño/a"], margins=True, margins_name="Total"))

        for tab, k in zip(st.tabs([k["name"] for k in kids]), kids):
            with tab:
                st.metric("Monedas", economy.balance(k["id"]))
                mine = df[df["Niño/a"] == k["name"]]
                st.markdown("**Vouchers**")
                st.dataframe(mine[mine["Tipo"] == "voucher"].drop(columns=["Tipo", "Niño/a"]), hide_index=True)
                st.markdown("**Todas las compras**")
                st.dataframe(mine.drop(columns=["Niño/a", "Pedido"]), hide_index=True)
                open_rows = [p for p in rows if p["kid_id"] == k["id"] and p["status"] == "owned"]
                if open_rows:
                    pick = st.selectbox("Compra abierta", open_rows, key=f"pick{k['id']}",
                                        format_func=lambda p: f"{KIND_ICON[p['shop_items']['kind']]} {p['shop_items']['name']} · {p['purchased_at'][:10]}")
                    if st.button("Cancelar y reembolsar", key=f"cancel{k['id']}"):
                        rpc("cancel_purchase", {"p_purchase": pick["id"]})
                        st.rerun()

    with t_days:
        found = {(c["kid_id"], c["day_id"]) for c in table("claims").select("kid_id,day_id").execute().data}
        days = (table("days").select("id,date,day_type,riddle_easy,riddle_hard,answer,base_coins")
                .order("date").execute().data)
        st.dataframe([{"Fecha": d["date"], "Tipo": d["day_type"], "Adivinanza fácil": d["riddle_easy"],
                       "Adivinanza difícil": d["riddle_hard"], "Respuesta": d["answer"], "Monedas": d["base_coins"],
                       **{k["name"]: "✅" if (k["id"], d["id"]) in found else "" for k in kids}} for d in days],
                     hide_index=True)

    # TODO: adjust stock / coins (ledger 'adjustment' row)

    with t_pins:
        st.subheader("PIN de los niños")
        with st.form("reset_pin", clear_on_submit=True):
            kid = st.selectbox("Niño/a", kids, format_func=lambda k: k["name"])
            new_pin = st.text_input("PIN nuevo (4 cifras)", type="password", max_chars=4)
            reset = st.form_submit_button("Restablecer PIN")
        if reset:
            if auth.valid_kid_pin(new_pin):
                auth.set_kid_pin(kid["id"], new_pin)
                st.success(f"PIN de {kid['name']} restablecido y bloqueo quitado.")
            else:
                st.error("El PIN debe tener 4 cifras.")

        st.subheader("PIN de administrador")
        auth.change_pin_form(lambda pin: "" if auth.check_admin_pin(pin) else "PIN incorrecto.",
                             auth.set_admin_pin, four_digits=False)

    with t_backup:
        if st.button("Preparar export CSV"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for t in ["kids", "days", "claims", "coop_solves", "shop_items", "purchases", "ledger"]:
                    z.writestr(f"{t}.csv", pd.DataFrame(table(t).select("*").execute().data).to_csv(index=False))
            st.download_button("Descargar ZIP", buf.getvalue(), "backup.zip", "application/zip")
