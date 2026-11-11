import calendar
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from ..config import MONTHS_RU, WEEKDAYS_RU
from ..services.document_service import load_document
from ..services.settings_service import get_year_month, get_setting
from ..services.employee_service import get_signatory
from ..core.calculations import (calc_security_schedule,
                                  calc_security_timesheet,
                                  calc_transport_timesheet)


class _Row:
    pass


class _Cell:
    def __init__(self, d, c):
        self.day = d
        self.code = c


def _proxy(row):
    p = _Row()
    p.employee_name = row["employee_name"]
    p.employee_position = row["employee_position"]
    p.cells = [_Cell(d, c) for d, c in row["cells"].items()]
    return p


def export_document_to_excel(doc_id, path):
    data = load_document(doc_id)
    if not data:
        raise ValueError("Документ не найден")

    year = data["year"]
    month = data["month"]
    group = data["group"]
    doc_type = data["doc_type"]
    last_day = calendar.monthrange(year, month)[1]
    norm_hours, holidays = get_year_month(year, month)
    use_7h = get_setting("use_7h", "1") == "1"
    weekend_color = get_setting("weekend_color", "#FFE0B2").replace("#", "")
    manual_mode = data["manual_mode"]

    if doc_type == "schedule":
        title = (f"График группы по охранному обеспечению "
                 f"на {MONTHS_RU[month - 1]} {year} г.")
        summary = ["Факт. работы", "Отпуск", "Всего", "Норма", "Ознакомлен"]
    elif group == "security":
        title = (f"Табель группы по охранному обеспечению "
                 f"на {MONTHS_RU[month - 1]} {year} г.")
        summary = ["Факт. работы", "Медицинский осмотр", "Болезнь",
                   "Справка", "Отпуск", "Прогул",
                   "Отпуск без сохранения з/п", "Всего", "Норма",
                   "Переработка", "Работа в ночь",
                   "Работа в праздничные дни"]
    else:
        title = (f"Табель транспортной группы "
                 f"на {MONTHS_RU[month - 1]} {year} г.")
        summary = ["Факт. работы, дни", "Командировка, дни",
                   "Разъездной характер работы", "Расчет по среднему",
                   "Медицинский осмотр", "Болезнь", "Отпуск",
                   "Отпуск без сохранения з/п", "Прогул",
                   "Факт. время, часов", "Норма, часов"]

    wb = Workbook()
    ws = wb.active
    total_cols = 2 + last_day + len(summary)

    # Стили
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    weekend_fill = PatternFill(start_color=weekend_color, end_color=weekend_color, fill_type="solid")

    # Заголовок
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    c = ws.cell(row=1, column=1, value=title)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.font = Font(bold=True, size=12)
    ws.row_dimensions[1].height = 25

    # Шапка
    ws.cell(row=3, column=1, value="ФИО")
    ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    ws.cell(row=3, column=2, value="Должность")
    ws.merge_cells(start_row=3, start_column=2, end_row=4, end_column=2)

    for d in range(1, last_day + 1):
        col = 2 + d
        dow = date(year, month, d).weekday()
        
        c1 = ws.cell(row=3, column=col, value=WEEKDAYS_RU[dow])
        c2 = ws.cell(row=4, column=col, value=d)
        
        c1.alignment = center_align
        c2.alignment = center_align
        c1.border = thin_border
        c2.border = thin_border
        
        if dow >= 5:
            c1.fill = weekend_fill
            c2.fill = weekend_fill

    for i, key in enumerate(summary):
        col = 2 + last_day + i + 1
        h = ws.cell(row=3, column=col, value=key)
        ws.merge_cells(start_row=3, start_column=col, end_row=4, end_column=col)
        h.alignment = center_align
        h.border = thin_border

    # Строки данных
    row_num = 5
    for row in data["rows"]:
        c_name = ws.cell(row=row_num, column=1, value=row["employee_name"])
        c_pos = ws.cell(row=row_num, column=2, value=row["employee_position"])
        c_name.border = thin_border
        c_pos.border = thin_border

        proxy = _proxy(row)
        if doc_type == "schedule":
            res = calc_security_schedule(proxy, year, month, norm_hours, holidays, use_7h)
        elif group == "security":
            res = calc_security_timesheet(proxy, year, month, norm_hours, holidays, use_7h)
        else:
            res = calc_transport_timesheet(proxy, year, month, norm_hours, holidays, use_7h)

        for d in range(1, last_day + 1):
            col = 2 + d
            code = row["cells"].get(d, "")
            cc = ws.cell(row=row_num, column=col, value=code)
            cc.alignment = center_align
            cc.border = thin_border

        for i, key in enumerate(summary):
            col = 2 + last_day + i + 1
            if manual_mode and key in row["overrides"]:
                val = row["overrides"][key]
            else:
                val = res.get(key, "")
            cc = ws.cell(row=row_num, column=col, value=val)
            cc.alignment = center_align
            cc.border = thin_border

        row_num += 1

    # Легенда
    row_num += 2
    legend = ["В - выходной", "Б - Болезнь", "О - отпуск",
              "С - справка", "П - прогул", "СЗ - средний заработок",
              "МО - мед.осмотр", "А - отпуск без сохранения З/П",
              "К - командировка", "Р - разъездной"]
    col = 1
    for item in legend:
        ws.cell(row=row_num, column=col, value=item)
        col += 4

    # Подпись
    sig_name, sig_pos = get_signatory(group)
    if sig_name:
        row_num += 3
        ws.cell(row=row_num, column=2, value=sig_pos or "Главный механик")
        ws.cell(row=row_num, column=12, value=sig_name)

    # Ширина колонок
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 25
    for d in range(1, last_day + 1):
        ws.column_dimensions[get_column_letter(2 + d)].width = 5
    for i in range(len(summary)):
        ws.column_dimensions[get_column_letter(2 + last_day + i + 1)].width = 12

    wb.save(path)
