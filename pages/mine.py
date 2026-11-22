import logging
import pandas as pd
import streamlit as st
from lib import auth, economy, notify, ui

REASON = {"claim": "Código encontrado", "coop_bonus": "Bonus cooperativo", "purchase": "Compra",
          "refund": "Devolución", "adjustment": "Ajuste"}

def use_voucher(purchase_id: str, item_name: str) -> None:
    """Button callback: runs before the page redraws, so the list already shows the new status."""
    if not economy.use_voucher(kid["id"], purchase_id):
        return
    ui.flash("success", f"¡Hecho! Papá o mamá saben que quieres usar «{item_name}».")
    try:   # covers a missing APP_URL / [smtp] too, e.g. a local debug run
        link = f"{st.secrets['APP_URL'].rstrip('/')}/?redeem={purchase_id}"
        notify.send(f"🎟️ {kid['name']} quiere usar: {item_name}",
                    f"{kid['name']} quiere usar el voucher «{item_name}».\n\n"
                    f"Cuando lo hayáis disfrutado, confírmalo aquí:\n{link}")
    except Exception:   # the request is saved and shows on the admin page anyway
        logging.exception("voucher email failed")
        ui.flash("warning", f"Pedido «{item_name}». Pero el email a papá/mamá no salió: avísales tú.")

def undo_voucher(purchase_id: str) -> None:
    if economy.undo_voucher(kid["id"], purchase_id):
        ui.flash("info", "Vale, lo guardamos para más tarde.")

def card(p: dict, actions) -> None:
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        st.markdown(f"{ui.KIND_ICON[p['kind']]} **{p['name']}**  \n:small[comprado el {p['purchased_at'][8:10]}.{p['purchased_at'][5:7]}.]",
                    width="stretch")
        actions()

kid = auth.current_kid()
if kid and auth.pin_confirmed(kid):
    state = economy.state(kid["id"])
    ui.header("Mis cosas", kid, state["balance"])
    bought = state["purchases"]
    vouchers = [p for p in bought if p["kind"] == "voucher" and p["status"] != "redeemed"]
    presents = [p for p in bought if p["kind"] == "present" and p["status"] != "redeemed"]
    done = [p for p in bought if p["status"] == "redeemed"]

    if not bought:
        st.caption("Todavía no has comprado nada. Las monedas de cada código se gastan en la Tienda.")

    if vouchers:
        st.subheader("Mis vouchers", anchor=False)
        st.caption("Pulsa «Usar» cuando quieras canjearlo. Papá o mamá lo confirman después.")
        for p in vouchers:
            if p["status"] == "owned":
                card(p, lambda p=p: st.button("Usar", key=f"use{p['id']}", type="primary", icon=":material/redeem:",
                                              on_click=use_voucher, args=(p["id"], p["name"])))
            else:
                def waiting(p=p):
                    with st.container(width="content", horizontal_alignment="right", gap="xsmall"):
                        st.badge("Esperando", icon=":material/schedule:", color="blue")
                        st.button("Deshacer", key=f"undo{p['id']}", type="tertiary", on_click=undo_voucher, args=(p["id"],))
                card(p, waiting)

    if presents:
        st.subheader("Regalos por recibir", anchor=False)
        for p in presents:
            card(p, lambda: st.badge("Pronto", icon=":material/featured_seasonal_and_gifts:", color="violet"))

    if done:
        with st.expander(f"Usados y recibidos ({len(done)})", icon=":material/task_alt:"):
            for p in done:
                st.markdown(f"{ui.KIND_ICON[p['kind']]} {p['name']} · :green-badge[✓ {p['redeemed_at'][8:10]}.{p['redeemed_at'][5:7]}.]")

    # on_change="rerun" + .open: the coin history query only runs while the expander is open.
    hist_box = st.expander("Historial de monedas", icon=":material/receipt_long:", on_change="rerun", key="hist")
    if hist_box.open:
        with hist_box:
            hist = economy.ledger(kid["id"])
            if hist:
                df = pd.DataFrame(hist)
                df["created_at"] = pd.to_datetime(df["created_at"]).dt.tz_convert("Europe/Berlin").dt.strftime("%d.%m. %H:%M")
                df["reason"] = df["reason"].map(REASON).fillna(df["reason"])
                st.dataframe(df, hide_index=True, width="stretch",
                             column_config={"created_at": "Fecha", "amount": "🪙", "reason": "Motivo"})
            else:
                st.caption("Sin movimientos todavía.")

    with st.expander("Cambiar PIN", icon=":material/key:"):
        auth.change_pin_form(lambda pin: auth.login_with_pin(kid["name"], pin)[1],
                             lambda pin: auth.set_kid_pin(kid["id"], pin), four_digits=True)
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button("Salir", icon=":material/logout:", type="tertiary", on_click=auth.log_out)
        st.page_link("pages/admin.py", label="Papá/mamá", icon=":material/lock:")
if kid:
    ui.nav_bar()
