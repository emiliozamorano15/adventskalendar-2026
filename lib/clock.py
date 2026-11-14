from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")

def now_berlin() -> datetime:
    return datetime.now(TZ)

def today_berlin() -> date:
    return now_berlin().date()
