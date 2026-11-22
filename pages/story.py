import streamlit as st
from lib import auth, economy, ui
from lib.clock import today_berlin

def show_day(day: dict, found: bool) -> None:
    st.markdown(day["chapter_text"])
    riddle = day["riddle_hard"] if kid.get("level") == "hard" else day["riddle_easy"]
    if riddle:
        with st.container(border=True):
            st.markdown(f"**:material/psychology: Adivinanza**\n\n{riddle}")
    if day["day_type"] == "coop":
        # TODO: show half A/B per kid, answer form -> economy.coop_solve
        st.caption("Día cooperativo: combina tu mitad con la de tu hermano/a.")
    if found:
        st.badge("Código encontrado", icon=":material/check_circle:", color="green")
    else:
        st.caption("Resuelve la adivinanza, busca el código QR escondido y escanéalo con la cámara.")

st.image("assets/banner.png", width="stretch")   # placeholder: drop your own image in at the same path
kid = auth.current_kid()
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
            show_day(todays, todays["id"] in found)
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
                    st.dialog(f"Día {n}", width="large")(show_day)(day, day["id"] in found)
    ui.nav_bar()
