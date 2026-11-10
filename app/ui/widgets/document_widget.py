import calendar
from datetime import date

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTableWidget, QTableWidgetItem, QLabel,
                                QComboBox, QMessageBox, QFileDialog)
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtCore import Qt

from ...config import MONTHS_RU, WEEKDAYS_RU
from ...core.calculations import (calc_security_schedule,
                                   calc_security_timesheet,
                                   calc_transport_timesheet)
from ...services.settings_service import (get_year_month, use_7h_enabled,
                                           get_weekend_color)
from ...services.document_service import load_document, save_document
from ...export.excel_export import export_document_to_excel


def allowed_codes(group, doc_type, position):
    pos = (position or "").lower()
    is_worker = "рабочий" in pos
    if group == "security":
        if is_worker:
            return ["8", "7", "В", "О", "Б", "А", "П", "С", "МО", ""]
        return ["15", "9", "В", "О", "Б", "А", "П", "С", "МО", ""]
    return ["8", "7", "Р", "К", "СЗ", "МО", "Б", "О", "А", "П", "В", ""]


class _RowProxy:
    pass


class _CellProxy:
    def __init__(self, day, code):
        self.day = day
        self.code = code


class DocumentWidget(QDialog):
    def __init__(self, doc_id, parent=None):
        super().__init__(parent)
        self.doc_id = doc_id
        data = load_document(doc_id)
        if not data:
            QMessageBox.critical(self, "Ошибка", "Документ не найден")
            self.close()
            return
        self.data = data
        self.year = data["year"]
        self.month = data["month"]
        self.group = data["group"]
        self.doc_type = data["doc_type"]
        self.manual_mode = data["manual_mode"]
        self.last_day = calendar.monthrange(self.year, self.month)[1]

        if self.doc_type == "schedule":
            title = (f"График группы по охранному обеспечению "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.")
            self.summary_keys = ["Факт. работы", "Отпуск", "Всего",
                                 "Норма", "Ознакомлен"]
        elif self.group == "security":
            title = (f"Табель группы по охранному обеспечению "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.")
            self.summary_keys = [
                "Факт. работы", "Медицинский осмотр", "Болезнь", "Справка",
                "Отпуск", "Прогул", "Отпуск без сохранения з/п",
                "Всего", "Норма", "Переработка", "Работа в ночь",
                "Работа в праздничные дни"]
        else:
            title = (f"Табель транспортной группы "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.")
            self.summary_keys = [
                "Факт. работы, дни", "Командировка, дни",
                "Разъездной характер работы", "Расчет по среднему",
                "Медицинский осмотр", "Болезнь", "Отпуск",
                "Отпуск без сохранения з/п", "Прогул",
                "Факт. время, часов", "Норма, часов"]

        self.setWindowTitle(title)
        self.resize(1500, 750)

        lay = QVBoxLayout(self)

        self.banner = QLabel("")
        self.banner.setStyleSheet(
            "background:#FFC107; color:black; padding:6px; font-weight:bold;")
        self.banner.setVisible(False)
        lay.addWidget(self.banner)

        h = QLabel(title)
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        h.setFont(f)
        h.setAlignment(Qt.AlignCenter)
        lay.addWidget(h)

        tools = QHBoxLayout()
        self.btn_manual = QPushButton()
        self.btn_manual.clicked.connect(self.toggle_manual)
        tools.addWidget(self.btn_manual)

        tools.addWidget(QLabel("Обозначение:"))
        self.code_combo = QComboBox()
        all_codes = set()
        for r in self.data["rows"]:
            for c in allowed_codes(self.group, self.doc_type,
                                    r["employee_position"]):
                if c:
                    all_codes.add(c)
        self.code_combo.addItems([""] + sorted(all_codes))
        tools.addWidget(self.code_combo)

        btn_apply = QPushButton("Применить к выделенным")
        btn_apply.clicked.connect(self.apply_code_to_selected)
        tools.addWidget(btn_apply)

        tools.addStretch()

        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.save)
        tools.addWidget(btn_save)

        btn_export = QPushButton("Экспорт в Excel")
        btn_export.clicked.connect(self.export_excel)
        tools.addWidget(btn_export)

        lay.addLayout(tools)

        self.table = QTableWidget()
        lay.addWidget(self.table)
        self._build_table()
        self._update_manual_ui()

    def _build_table(self):
        n_rows = len(self.data["rows"])
        n_days = self.last_day
        n_cols = 2 + n_days + len(self.summary_keys)
        self.table.clear()
        self.table.setRowCount(n_rows + 2)
        self.table.setColumnCount(n_cols)

        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 150)
        for d in range(1, n_days + 1):
            self.table.setColumnWidth(1 + d, 30)
        for i in range(len(self.summary_keys)):
            self.table.setColumnWidth(2 + n_days + i, 80)

        self.table.setItem(0, 0, QTableWidgetItem("ФИО"))
        self.table.setItem(0, 1, QTableWidgetItem("Должность"))
        self.table.setSpan(0, 0, 2, 1)
        self.table.setSpan(0, 1, 2, 1)

        weekend_color = QColor(get_weekend_color())

        for d in range(1, n_days + 1):
            col = 1 + d
            dow = date(self.year, self.month, d).weekday()
            wd = QTableWidgetItem(WEEKDAYS_RU[dow][:2])
            wd.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, col, wd)
            dt = QTableWidgetItem(str(d))
            dt.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(1, col, dt)
            if dow >= 5:
                wd.setBackground(QBrush(weekend_color))
                dt.setBackground(QBrush(weekend_color))

        for i, key in enumerate(self.summary_keys):
            col = 2 + n_days + i
            it = QTableWidgetItem(key)
            it.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, col, it)
            self.table.setSpan(0, col, 2, 1)

        for r_idx, row in enumerate(self.data["rows"]):
            gr = r_idx + 2
            self.table.setItem(gr, 0, QTableWidgetItem(row["employee_name"]))
            self.table.setItem(gr, 1, QTableWidgetItem(row["employee_position"]))
            for d in range(1, n_days + 1):
                code = row["cells"].get(d, "")
                it = QTableWidgetItem(code)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(gr, 1 + d, it)
            self._recalc_row(r_idx)

        self.table.resizeRowsToContents()

    def _row_proxy(self, row):
        p = _RowProxy()
        p.employee_name = row["employee_name"]
        p.employee_position = row["employee_position"]
        p.cells = [_CellProxy(d, c) for d, c in row["cells"].items()]
        return p

    def _calculate(self, row):
        norm_hours, holidays = get_year_month(self.year, self.month)
        use_7h = use_7h_enabled()
        proxy = self._row_proxy(row)
        if self.doc_type == "schedule":
            return calc_security_schedule(proxy, self.year, self.month,
                                          norm_hours, holidays, use_7h)
        if self.group == "security":
            return calc_security_timesheet(proxy, self.year, self.month,
                                           norm_hours, holidays, use_7h)
        return calc_transport_timesheet(proxy, self.year, self.month,
                                        norm_hours, holidays, use_7h)

    def _recalc_row(self, r_idx):
        row = self.data["rows"][r_idx]
        res = self._calculate(row)
        gr = r_idx + 2
        for i, key in enumerate(self.summary_keys):
            col = 2 + self.last_day + i
            if self.manual_mode and key in row["overrides"]:
                val = row["overrides"][key]
            else:
                val = str(res.get(key, ""))
            it = QTableWidgetItem(val)
            it.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(gr, col, it)

    def _update_manual_ui(self):
        if self.manual_mode:
            self.banner.setText(
                "Включён режим ручного ввода — автоматический пересчёт "
                "граф отключён (кроме ячеек календаря).")
            self.banner.setVisible(True)
            self.btn_manual.setText("Выключить ручной ввод")
        else:
            self.banner.setVisible(False)
            self.btn_manual.setText("Включить ручной ввод")

    def toggle_manual(self):
        if self.manual_mode:
            has = any(r["overrides"] for r in self.data["rows"])
            if has:
                r = QMessageBox.question(
                    self, "Ручной ввод",
                    "В документе есть ручные значения.\n\n"
                    "Да — сохранить\nНет — удалить\nОтмена — не выключать",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                if r == QMessageBox.Cancel:
                    return
                if r == QMessageBox.No:
                    for row in self.data["rows"]:
                        row["overrides"] = {}
            self.manual_mode = False
        else:
            self.manual_mode = True
        self._update_manual_ui()
        for i in range(len(self.data["rows"])):
            self._recalc_row(i)

    def apply_code_to_selected(self):
        code = self.code_combo.currentText()
        n_days = self.last_day
        for idx in self.table.selectedIndexes():
            r = idx.row() - 2
            c = idx.column()
            if r < 0:
                continue
            if c < 2 or c > 1 + n_days:
                continue
            day = c - 1
            self.data["rows"][r]["cells"][day] = code
            self.table.item(idx.row(), idx.column()).setText(code)
        for r_idx in range(len(self.data["rows"])):
            self._recalc_row(r_idx)

    def save(self):
        n_days = self.last_day
        for r_idx, row in enumerate(self.data["rows"]):
            gr = r_idx + 2
            for d in range(1, n_days + 1):
                it = self.table.item(gr, 1 + d)
                row["cells"][d] = it.text() if it else ""
            if self.manual_mode:
                for i, key in enumerate(self.summary_keys):
                    it = self.table.item(gr, 2 + n_days + i)
                    row["overrides"][key] = it.text() if it else ""
        save_document(self.doc_id, self.data["rows"], self.manual_mode)

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в Excel",
            f"{self.doc_type}_{self.year}_{self.month}.xlsx",
            "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.save()
            export_document_to_excel(self.doc_id, path)
            QMessageBox.information(self, "Готово", f"Файл сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", str(e))