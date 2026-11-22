import streamlit as st
from lib import auth, economy, ui
from lib.clock import today_berlin

def coop_block(day: dict, where: str) -> None:
    """Co-op day: each kid sees one half of the clue (first name alphabetically gets A); both type the answer,
    and record_coop_solve pays the bonus to both once both got it right. `where` keeps widget keys unique
    when today's card and the door dialog show the same day."""
    half = day["coop_half_a"] if auth.list_kid_names()[:1] == [kid["name"]] else day["coop_half_b"]
    with st.container(border=True):
        st.markdown(f"**:material/extension: Tu mitad de la pista**\n\n{half or '—'}")
    if day["id"] in state["coop_paid"]:
        st.badge(f"Resuelto en equipo · +{day['coop_bonus']} 🪙", icon=":material/group:", color="green")
        return
    if day["id"] in state["coop_solved"]:
        st.badge("¡Correcto! Falta tu hermano/a", icon=":material/hourglass_top:", color="blue")
        return
    with st.form(f"coop_{where}_{day['id']}", border=False, clear_on_submit=True):
        answer = st.text_input("Respuesta del equipo", placeholder="Junten las dos mitades…")
        sent = st.form_submit_button("Comprobar", type="primary", width="stretch")
    if sent:
        res = economy.coop_solve(kid["id"], day["id"], answer)
        if not res["ok"]:
            st.error("Esa no es. Habla con tu hermano o hermana y prueba otra vez." if res["reason"] == "wrong"
                     else "Este día todavía no se puede resolver.")
            return
        if res["bonus_paid"]:
            ui.flash("success", f"¡Equipo perfecto! +{res['bonus']} 🪙 para los dos.", celebrate=True)
        else:
            ui.flash("info", "¡Correcto! Cuando tu hermano o hermana también acierte, los dos ganan el premio.")
        st.rerun()   # also closes the door dialog, so the header shows the new balance

def show_day(day: dict, found: bool, where: str) -> None:
    st.markdown(day["chapter_text"])
    riddle = day["riddle_hard"] if kid.get("level") == "hard" else day["riddle_easy"]
    if riddle:
        with st.container(border=True):
            st.markdown(f"**:material/psychology: Adivinanza**\n\n{riddle}")
    if day["day_type"] == "coop":
        coop_block(day, where)
    if found:
        st.badge("Código encontrado", icon=":material/check_circle:", color="green")
    else:
        st.caption("Resuelve la adivinanza, busca el código QR escondido y escanéalo con la cámara.")

st.image("assets/banner.png", width="stretch")   # placeholder: drop your own image in at the same path
kid = auth.current_kid()
if not kid:   # the parent starts here too
    st.page_link("pages/admin.py", label="Soy papá/mamá", icon=":material/lock:")
if kid:
    state = economy.state(kid["id"])
    ui.header("Calendario", kid, state["balance"])
    today = today_berlin()
    days = economy.december_days()   # stops at today, so a locked door has no data behind it
    found = set(state["claimed"])

    # Today's chapter sits right on the page: opening the app is enough, no door to find first.
    todays = days.get(today.day) if today.month == 12 else None
    if todays:
        with st.container(border=True):
            st.subheader(f"Hoy, día {today.day}", anchor=False)
            show_day(todays, todays["id"] in found, "today")
    elif not days:
        st.info("La historia empieza el 1 de diciembre. ¡Vuelve entonces!", icon=":material/hourglass_top:")

    if days:
        st.subheader("Todas las puertas", anchor=False)
        st.caption("🎁 abierta · ✅ código encontrado · 🔒 todavía cerrada")
        # st.grid reflows to fewer columns on a narrow phone; st.columns would stack all 24 doors.
        with st.grid(6, min_column_width=64, gap="small"):
            for n in range(1, 25):
                day = days.get(n)
                icon = "🔒" if not day else "✅" if day["id"] in found else "🎁"
                is_today = today.month == 12 and today.day == n
                if st.button(str(n), key=f"day{n}", icon=icon, disabled=not day, width="stretch",
                             type="primary" if is_today else "secondary"):
                    st.dialog(f"Día {n}", width="large")(show_day)(day, day["id"] in found, "door")
    ui.nav_bar()
