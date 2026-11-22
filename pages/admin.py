import io, zipfile
import pandas as pd
import streamlit as st
from lib import auth, economy, ui
from lib.db import table
from lib.ui import KIND_ICON

STATUS = {"owned": "comprado", "requested": "quiere usarlo", "redeemed": "hecho ✅", "cancelled": "reembolsado"}
PURCHASE_COLS = "id,kid_id,status,purchased_at,requested_at,redeemed_at,price_paid,kids(name),shop_items(name,kind)"

def confirm(pid: str) -> None:
    ui.flash(*(("success", "Marcado como hecho.") if economy.confirm_redeemed(pid) else ("warning", "Ya estaba cerrado.")))
    st.query_params.pop("redeem", None)

def refund(pid: str) -> None:
    ui.flash(*(("success", "Reembolsado.") if economy.cancel_purchase(pid)["ok"] else ("warning", "Ya estaba cerrado.")))
    st.query_params.pop("redeem", None)

def purchase_card(p: dict, done_label: str, key: str = "") -> None:
    """One open purchase with 'done' and 'refund'. Buttons are callbacks, so the list redraws without it."""
    item = p["shop_items"]
    when = (p["requested_at"] or p["purchased_at"])[:10]
    with st.container(border=True):
        st.markdown(f"{KIND_ICON[item['kind']]} **{item['name']}** · {p['kids']['name']}  \n:small[{when} · {p['price_paid']} 🪙]")
        with st.container(horizontal=True):
            st.button(done_label, key=f"ok{key}{p['id']}", type="primary", icon=":material/check:", on_click=confirm, args=(p["id"],))
            st.button("Reembolsar", key=f"rf{key}{p['id']}", icon=":material/undo:", on_click=refund, args=(p["id"],),
                      help="Cancela la compra y devuelve las monedas.")

with st.container(horizontal=True, vertical_alignment="center"):
    st.header("Admin", anchor=False, width="stretch")
    st.page_link("pages/story.py", label="Volver", icon=":material/arrow_back:")
if auth.admin_ok():
    ui.show_flash()
    kids = table("kids").select("id,name").order("name").execute().data

    # Link from the voucher email: show that one purchase first.
    if pid := st.query_params.get("redeem"):
        rows = table("purchases").select(PURCHASE_COLS).eq("id", pid).execute().data
        if rows and rows[0]["status"] in ("owned", "requested"):
            st.subheader("Voucher del email", anchor=False)
            purchase_card(rows[0], "Hecho", key="mail")
        else:
            st.caption("Ese voucher ya está cerrado.")
            st.query_params.pop("redeem", None)

    # on_change="rerun": only the open tab runs its queries.
    t_open, t_kids, t_days, t_settings = st.tabs(["Pendiente", "Niños", "Días", "Ajustes"], on_change="rerun", key="admin_tab")

    if t_open.open:
        with t_open:
            rows = [p for p in table("purchases").select(PURCHASE_COLS).in_("status", ["owned", "requested"])
                    .order("purchased_at").execute().data if p["id"] != st.query_params.get("redeem")]   # shown above
            asked = [p for p in rows if p["status"] == "requested"]
            gifts = [p for p in rows if p["status"] == "owned" and p["shop_items"]["kind"] == "present"]
            unused = [p for p in rows if p["status"] == "owned" and p["shop_items"]["kind"] == "voucher"]
            st.subheader(f"Quieren usar ({len(asked)})", anchor=False)
            if not asked:
                st.caption("Nadie ha pedido usar un voucher.")
            for p in asked:
                purchase_card(p, "Hecho")
            st.subheader(f"Regalos por entregar ({len(gifts)})", anchor=False)
            if not gifts:
                st.caption("Ningún regalo pendiente.")
            for p in gifts:
                purchase_card(p, "Entregado")
            if unused:
                with st.expander(f"Vouchers sin usar ({len(unused)})"):
                    for p in unused:
                        purchase_card(p, "Hecho")

    if t_kids.open:
        with t_kids:
            name = st.segmented_control("Niño/a", [k["name"] for k in kids], default=kids[0]["name"] if kids else None,
                                        key="admin_kid", width="stretch")
            k = next((k for k in kids if k["name"] == name), None)
            if k:
                state = economy.state(k["id"])
                st.metric("Monedas", state["balance"], border=True)
                with st.form("adjust", clear_on_submit=True, border=True):
                    st.markdown("**Ajustar monedas**")
                    amount = st.number_input("Cantidad (negativa para quitar)", value=0, step=5)
                    note = st.text_input("Motivo", placeholder="p. ej. ayudó en casa")
                    if st.form_submit_button("Guardar", type="primary", width="stretch"):
                        res = economy.adjust_coins(k["id"], int(amount), note)
                        if res["ok"]:
                            ui.flash("success", f"Nuevo saldo de {k['name']}: {res['balance']} 🪙")
                            st.rerun()
                        st.error({"zero": "Pon una cantidad distinta de 0.",
                                  "negative": "El saldo no puede quedar por debajo de 0."}.get(res["reason"], res["reason"]))
                st.markdown("**Compras**")
                st.dataframe(pd.DataFrame([{"Artículo": f"{KIND_ICON[p['kind']]} {p['name']}", "Estado": STATUS[p["status"]],
                                            "Precio": p["price_paid"], "Comprado": p["purchased_at"][:10],
                                            "Hecho": (p["redeemed_at"] or "")[:10]} for p in state["purchases"]]),
                             hide_index=True, width="stretch")
                st.caption(f"{len(state['claimed'])} códigos encontrados.")

    if t_days.open:
        with t_days:
            found = {(c["kid_id"], c["day_id"]) for c in table("claims").select("kid_id,day_id").execute().data}
            days = (table("days").select("id,date,day_type,riddle_easy,riddle_hard,answer,base_coins")
                    .order("date").execute().data)
            st.dataframe([{"Fecha": d["date"][8:10] + "." + d["date"][5:7] + ".", "Tipo": d["day_type"],
                           **{k["name"]: "✅" if (k["id"], d["id"]) in found else "" for k in kids},
                           "Respuesta": d["answer"], "Monedas": d["base_coins"],
                           "Adivinanza fácil": d["riddle_easy"], "Adivinanza difícil": d["riddle_hard"]} for d in days],
                         hide_index=True, width="stretch")

    if t_settings.open:
        with t_settings:
            st.subheader("PIN de los niños", anchor=False)
            with st.form("reset_pin", clear_on_submit=True):
                kid = st.selectbox("Niño/a", kids, format_func=lambda k: k["name"])
                new_pin = st.text_input("PIN nuevo (4 cifras)", type="password", max_chars=4)
                reset = st.form_submit_button("Restablecer PIN", width="stretch")
            if reset:
                if auth.valid_kid_pin(new_pin):
                    auth.set_kid_pin(kid["id"], new_pin)
                    st.success(f"PIN de {kid['name']} restablecido y bloqueo quitado.")
                else:
                    st.error("El PIN debe tener 4 cifras.")

            st.subheader("PIN de administrador", anchor=False)
            auth.change_pin_form(lambda pin: "" if auth.check_admin_pin(pin) else "PIN incorrecto.",
                                 auth.set_admin_pin, four_digits=False)

            st.subheader("Copia de seguridad", anchor=False)
            if st.button("Preparar export CSV", icon=":material/download:"):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as z:
                    for t in ["kids", "days", "claims", "coop_solves", "shop_items", "purchases", "ledger"]:
                        z.writestr(f"{t}.csv", pd.DataFrame(table(t).select("*").execute().data).to_csv(index=False))
                st.download_button("Descargar ZIP", buf.getvalue(), "backup.zip", "application/zip")

            st.subheader("Resumen de compras", anchor=False)
            rows = table("purchases").select("status,kids(name),shop_items(name)").neq("status", "cancelled").execute().data
            if rows:
                df = pd.DataFrame([{"Artículo": r["shop_items"]["name"], "Niño/a": r["kids"]["name"]} for r in rows])
                st.dataframe(pd.crosstab(df["Artículo"], df["Niño/a"], margins=True, margins_name="Total"), width="stretch")
            else:
                st.caption("Todavía no hay compras.")
