import streamlit as st
from lib import auth, economy
from lib.clock import today_berlin
from lib.db import table

st.image("assets/banner.png", width="stretch")   # placeholder: drop your own image in at the same path

def show_day(day: dict, found: bool) -> None:
    st.markdown(day["chapter_text"])
    riddle = day["riddle_hard"] if kid.get("level") == "hard" else day["riddle_easy"]
    if riddle:
        st.markdown(f"**Adivinanza:** {riddle}")
    if day["day_type"] == "coop":
        # TODO: show half A/B per kid, answer form -> economy.coop_solve
        st.caption("Día cooperativo: combina tu mitad con la de tu hermano/a.")
    if found:
        st.success("✅ Ya encontraste el código de este día.")
    else:
        st.info("🔎 Resuelve la adivinanza, encuentra el código QR escondido y escanéalo.")

kid = auth.current_kid()
if kid:
    st.title("🎄 Calendario de Adviento")
    today = today_berlin()
    # unlocked_days() stops at today, so a locked door has no data behind it.
    days = {int(d["date"][-2:]): d for d in economy.unlocked_days() if d["date"][:7] == f"{today.year}-12"}
    found = {c["day_id"] for c in table("claims").select("day_id").eq("kid_id", kid["id"]).execute().data}
    with st.container(horizontal=True, horizontal_alignment="center"):   # wraps on a phone, st.columns would stack
        for n in range(1, 25):
            day = days.get(n)
            door = "🔒" if not day else "✅" if day["id"] in found else "🎁"
            is_today = today.month == 12 and today.day == n
            if st.button(f"{door} {n}", key=f"day{n}", disabled=not day, width=90,
                         type="primary" if is_today else "secondary"):
                st.dialog(f"Día {n}", width="large")(show_day)(day, day["id"] in found)
    if not days:
        st.info("La historia empieza el 1 de diciembre.")
