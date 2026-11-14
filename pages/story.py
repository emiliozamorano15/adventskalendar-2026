import streamlit as st
from lib import auth, economy
from lib.clock import today_berlin

kid = auth.current_kid()
if kid:
    st.title("📖 El misterio de la Navidad")
    days = economy.unlocked_days()
    if not days:
        st.info("La historia empieza el 1 de diciembre.")
    for d in reversed(days):
        is_today = d["date"] == today_berlin().isoformat()
        with st.expander(f"Día {d['date'][-2:]}", expanded=is_today):
            st.markdown(d["chapter_text"])
            # TODO: older kid -> riddle_hard, younger -> riddle_easy (add kids.level)
            riddle = d["riddle_hard"] if kid.get("level") == "hard" else d["riddle_easy"]
            if riddle:
                st.markdown(f"**Adivinanza:** {riddle}")
            if d["day_type"] == "coop":
                # TODO: show half A/B per kid, answer form -> economy.coop_solve
                st.caption("Día cooperativo: combina tu mitad con la de tu hermano/a.")
