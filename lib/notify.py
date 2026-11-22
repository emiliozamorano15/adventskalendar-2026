"""Email to the parents through Gmail SMTP. Secrets: [smtp] user, password (Gmail app password), to."""
import smtplib
from email.message import EmailMessage
import streamlit as st

def send(subject: str, body: str) -> None:
    cfg = st.secrets["smtp"]
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, cfg["user"], cfg["to"]
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
        smtp.login(cfg["user"], cfg["password"])
        smtp.send_message(msg)
