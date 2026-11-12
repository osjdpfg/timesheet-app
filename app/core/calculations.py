import calendar
from datetime import date

def _cells_to_dict(row):
    return {c.day: (c.code or "").strip() for c in row.cells}

def _count(cells, codes):
    return sum(1 for c in cells.values() if c in codes)

def _holidays_set(holidays_str):
    res = set()
    for part in (holidays_str or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            res.add(int(part))
    return res

def _work_days_in_month(year, month):
    last = calendar.monthrange(year, month)[1]
    return [d for d in range(1, last + 1) if date(year, month, d).weekday() < 5]

def _is_preholiday(day, holidays, year, month):
    if (day + 1) not in holidays:
        return False
    return date(year, month, day).weekday() < 5

def _norm_with_vacation(year, month, holidays, cells, auto_7h, absence_codes=("О", "А")):
    norm = 0
    for d in _work_days_in_month(year, month):
        if cells.get(d, "") in absence_codes:
            continue
        h = 8
        if auto_7h and _is_preholiday(d, holidays, year, month):
            h = 7
        norm += h
    return norm

def calc_security_schedule(row, year, month, norm_hours, holidays_str):
    cells = _cells_to_dict(row)
    holidays = _holidays_set(holidays_str)
    auto_7h = getattr(row, "auto_7h", False)
    
    fact = _count(cells, {"15", "9", "8", "7"})
    
    total_hours = (_count(cells, {"15"}) * 15 + _count(cells, {"9"}) * 9 + 
                   _count(cells, {"8"}) * 8 + _count(cells, {"7"}) * 7)
    
    vac = _count(cells, {"О"})
    unpaid = _count(cells, {"А"})
    
    if vac > 0 or unpaid > 0:
        norm = _norm_with_vacation(year, month, holidays, cells, auto_7h)
    else:
        norm = norm_hours
        
    return {"Факт. работы": fact, "Отпуск": vac, "Всего": total_hours, "Норма": norm, "Ознакомлен": ""}

def calc_security_timesheet(row, year, month, norm_hours, holidays_str):
    cells = _cells_to_dict(row)
    holidays = _holidays_set(holidays_str)
    auto_7h = getattr(row, "auto_7h", False)
    
    fact = _count(cells, {"15", "9", "8", "7"})
    
    total_hours = (_count(cells, {"15"}) * 15 + _count(cells, {"9"}) * 9 + 
                   _count(cells, {"8"}) * 8 + _count(cells, {"7"}) * 7)
    
    night = _count(cells, {"15"}) * 2 + _count(cells, {"9"}) * 6
    
    hol_work = 0
    for d, c in cells.items():
        if d in holidays:
            if c == "15": hol_work += 15
            elif c == "9": hol_work += 9
            elif c == "8": hol_work += 8
            elif c == "7": hol_work += 7
        
    mo = _count(cells, {"МО"})
    sick = _count(cells, {"Б"})
    spravka = _count(cells, {"С"})
    vac = _count(cells, {"О"})
    progul = _count(cells, {"П"})
    unpaid = _count(cells, {"А"})
    
    if vac > 0 or unpaid > 0:
        norm = _norm_with_vacation(year, month, holidays, cells, auto_7h)
    else:
        norm = norm_hours
        
    perer = total_hours - norm if total_hours > norm else 0
    
    return {
        "Факт. работы": fact,
        "Медицинский осмотр": mo,
        "Болезнь": sick,
        "Справка": spravka,
        "Отпуск": vac,
        "Прогул": progul,
        "Отпуск без сохранения з/п": unpaid,
        "Всего": total_hours,
        "Норма": norm,
        "Переработка": perer,
        "Работа в ночь": night,
        "Работа в праздничные дни": hol_work
    }

def calc_transport_timesheet(row, year, month, norm_hours, holidays_str):
    cells = _cells_to_dict(row)
    holidays = _holidays_set(holidays_str)
    auto_7h = getattr(row, "auto_7h", False)
    
    fact_days = _count(cells, {"8", "Р", "7"})
    komand = _count(cells, {"К"})
    razezd = _count(cells, {"Р"})
    sz = _count(cells, {"СЗ"}) * 8
    mo = _count(cells, {"МО"})
    sick = _count(cells, {"Б"})
    vac = _count(cells, {"О"})
    unpaid = _count(cells, {"А"})
    progul = _count(cells, {"П"}) * 8
    
    fact_hours = 0
    for c in cells.values():
        if c in ("8", "Р"):
            fact_hours += 8
        elif c == "7":
            fact_hours += 7 if auto_7h else 8
            
    if vac > 0 or unpaid > 0:
        norm = _norm_with_vacation(year, month, holidays, cells, auto_7h)
    else:
        norm = norm_hours
        
    return {
        "Факт. работы, дни": fact_days,
        "Командировка, дни": komand,
        "Разъездной характер работы": razezd,
        "Расчет по среднему": sz,
        "Медицинский осмотр": mo,
        "Болезнь": sick,
        "Отпуск": vac,
        "Отпуск без сохранения з/п": unpaid,
        "Прогул": progul,
        "Факт. время, часов": fact_hours,
        "Норма, часов": norm
    }
