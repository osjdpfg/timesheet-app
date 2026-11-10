from ..database.db import get_session
from ..database.models import Year, MonthSetting, Setting, Document
from ..config import DEFAULT_WEEKEND_COLOR


def get_setting(key, default=""):
    s = get_session()
    try:
        r = s.get(Setting, key)
        return r.value if (r and r.value is not None) else default
    finally:
        s.close()


def set_setting(key, value):
    s = get_session()
    try:
        r = s.get(Setting, key)
        if r:
            r.value = str(value)
        else:
            s.add(Setting(key=key, value=str(value)))
        s.commit()
    finally:
        s.close()


def get_weekend_color():
    return get_setting("weekend_color", DEFAULT_WEEKEND_COLOR)


def use_7h_enabled():
    return get_setting("use_7h", "1") == "1"


def get_year_month(year, month):
    s = get_session()
    try:
        y = s.query(Year).filter_by(year=year).first()
        if not y:
            return 0, ""
        m = s.query(MonthSetting).filter_by(year_id=y.id, month=month).first()
        if not m:
            return 0, ""
        return m.norm_hours or 0, m.holidays or ""
    finally:
        s.close()


def list_years():
    s = get_session()
    try:
        return [y.year for y in s.query(Year).order_by(Year.year).all()]
    finally:
        s.close()


def add_year(year):
    s = get_session()
    try:
        if s.query(Year).filter_by(year=year).first():
            return False
        y = Year(year=year)
        s.add(y)
        s.flush()
        for m in range(1, 13):
            s.add(MonthSetting(year_id=y.id, month=m, norm_hours=0, holidays=""))
        s.commit()
        return True
    finally:
        s.close()


def delete_year(year):
    s = get_session()
    try:
        y = s.query(Year).filter_by(year=year).first()
        if y:
            s.delete(y)
        s.query(Document).filter_by(year=year).delete()
        s.commit()
    finally:
        s.close()


def update_month(year, month, norm, holidays):
    s = get_session()
    try:
        y = s.query(Year).filter_by(year=year).first()
        if not y:
            return
        m = s.query(MonthSetting).filter_by(year_id=y.id, month=month).first()
        if m:
            m.norm_hours = int(norm or 0)
            m.holidays = holidays or ""
            s.commit()
    finally:
        s.close()