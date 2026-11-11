import calendar
from datetime import date

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTableWidget, QTableWidgetItem, QLabel,
                                QComboBox, QMessageBox, QFileDialog,
                                QAbstractItemView)
from PySide6.QtGui import QColor, QBrush, QFont, QKeyEvent
from PySide6.QtCore import Qt, QTimer

from ...config import MONTHS_RU, WEEKDAYS_RU
from ...core.calculations import (calc_security_schedule,
                                   calc_security_timesheet,
                                   calc_transport_timesheet)
from ...services.settings_service import (get_year_month, use_7h_enabled,
                                           get_weekend_color, get_all_colors)
from ...services.document_service import load_document, save_document
from ...export.excel_export import export_document_to_excel


def allowed_codes(group, doc_type, position):
    is_worker = "рабочий" in (position or "").lower()
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
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.is_modified = False
        self._is_updating = False

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
        
        # Получаем номер копии (1), (2) и т.д.
        inst_num = data.get("instance_number", 0)
        suffix = f" ({inst_num})" if inst_num > 0 else ""

        if self.doc_type == "schedule":
            title = (f"График группы по охранному обеспечению "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}")
            self.summary_keys = ["Факт. работы", "Отпуск", "Всего",
                                 "Норма", "Ознакомлен"]
        elif self.group == "security":
            title = (f"Табель группы по охранному обеспечению "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}")
            self.summary_keys = [
                "Факт. работы", "Медицинский осмотр", "Болезнь", "Справка",
                "Отпуск", "Прогул", "Отпуск без сохранения з/п",
                "Всего", "Норма", "Переработка", "Работа в ночь",
                "Работа в праздничные дни"]
        else:
            title = (f"Табель транспортной группы "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}")
            self.summary_keys = [
                "Факт. работы, дни", "Командировка, дни",
                "Разъездной характер работы", "Расчет по среднему",
                "Медицинский осмотр", "Болезнь", "Отпуск",
                "Отпуск без сохранения з/п", "Прогул",
                "Факт. время, часов", "Норма, часов"]

        self.setWindowTitle(title)
        self.resize(1550, 750)

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

        btn_autofill = QPushButton("Автозаполнить (4 ячейки)")
        btn_autofill.clicked.connect(self.auto_fill_pattern)
        tools.addWidget(btn_autofill)

        # Кнопки перемещения строк
        tools.addSpacing(20)
        self.btn_up = QPushButton("▲ Вверх")
        self.btn_up.clicked.connect(self.move_row_up)
        tools.addWidget(self.btn_up)
        self.btn_down = QPushButton("▼ Вниз")
        self.btn_down.clicked.connect(self.move_row_down)
        tools.addWidget(self.btn_down)

        tools.addStretch()

        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.save)
        tools.addWidget(btn_save)

        btn_export = QPushButton("Экспорт в Excel")
        btn_export.clicked.connect(self.export_excel)
        tools.addWidget(btn_export)

        lay.addLayout(tools)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows) # Выделение строк целиком
        self.table.setSelectionMode(QAbstractItemView.SingleSelection) # Только одна строка
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setDragDropMode(QAbstractItemView.NoDragDrop) # Отключаем Drag&Drop
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.itemSelectionChanged.connect(self.update_move_buttons)

        lay.addWidget(self.table)
        self._build_table()
        self._update_manual_ui()

    def _build_table(self):
        self._is_updating = True
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
        code_colors = get_all_colors()

        for d in range(1, n_days + 1):
            col = 1 + d
            dow = date(self.year, self.month, d).weekday()
            wd = QTableWidgetItem(WEEKDAYS_RU[dow])
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
                
                if code in code_colors:
                    it.setBackground(QBrush(QColor(code_colors[code])))

                self.table.setItem(gr, 1 + d, it)
            
            res = self._calculate(row)
            for i, key in enumerate(self.summary_keys):
                col = 2 + n_days + i
                if self.manual_mode and key in row["overrides"]:
                    val = row["overrides"][key]
                else:
                    val = str(res.get(key, ""))
                it = QTableWidgetItem(val)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(gr, col, it)

        self.table.resizeRowsToContents()
        self._is_updating = False
        self.update_move_buttons()

    def update_move_buttons(self):
        row = self.table.currentRow()
        self.btn_up.setEnabled(row > 2)
        self.btn_down.setEnabled(row > 1 and row < self.table.rowCount() - 1)

    def move_row_up(self):
        row = self.table.currentRow()
        if row <= 2: return
        idx = row - 2
        self.data["rows"][idx], self.data["rows"][idx-1] = self.data["rows"][idx-1], self.data["rows"][idx]
        self._build_table()
        self.table.selectRow(row - 1)
        self.is_modified = True

    def move_row_down(self):
        row = self.table.currentRow()
        if row < 2 or row >= self.table.rowCount() - 1: return
        idx = row - 2
        self.data["rows"][idx], self.data["rows"][idx+1] = self.data["rows"][idx+1], self.data["rows"][idx]
        self._build_table()
        self.table.selectRow(row + 1)
        self.is_modified = True

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
            return calc_security_schedule(proxy, self.year, self.month, norm_hours, holidays, use_7h)
        if self.group == "security":
            return calc_security_timesheet(proxy, self.year, self.month, norm_hours, holidays, use_7h)
        return calc_transport_timesheet(proxy, self.year, self.month, norm_hours, holidays, use_7h)

    def on_item_changed(self, item):
        if self._is_updating:
            return
        self.is_modified = True
        
        r = item.row()
        c = item.column()
        if r < 2: return

        r_idx = r - 2
        n_days = self.last_day

        if 2 <= c <= 1 + n_days:
            code = item.text()
            self.data["rows"][r_idx]["cells"][c - 1] = code
            
            code_colors = get_all_colors()
            if code in code_colors:
                item.setBackground(QBrush(QColor(code_colors[code])))
            else:
                item.setBackground(QBrush(QColor("#FFFFFF")))

            if not self.manual_mode:
                res = self._calculate(self.data["rows"][r_idx])
                self._is_updating = True
                for i, key in enumerate(self.summary_keys):
                    col = 2 + n_days + i
                    self.table.item(r, col).setText(str(res.get(key, "")))
                self._is_updating = False

        elif c > 1 + n_days and self.manual_mode:
            key = self.summary_keys[c - (2 + n_days)]
            self.data["rows"][r_idx]["overrides"][key] = item.text()

    def auto_fill_pattern(self):
        sel = self.table.selectedRanges()
        if not sel:
            self.show_warning("Выделите диапазон для автозаполнения.")
            return
        
        rng = sel[0]
        rows = rng.rowCount()
        cols = rng.columnCount()
        
        pattern = []
        if rows == 1 and cols == 4:
            row = rng.topRow()
            for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                pattern.append(self.table.item(row, c).text())
            
            n_days = self.last_day
            for c in range(rng.rightColumn() + 1, 2 + n_days):
                val = pattern[(c - rng.leftColumn()) % 4]
                self.table.item(row, c).setText(val)
                
        elif rows == 4 and cols == 1:
            col = rng.leftColumn()
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                pattern.append(self.table.item(r, col).text())
            
            for r in range(rng.bottomRow() + 1, self.table.rowCount()):
                val = pattern[(r - rng.topRow()) % 4]
                self.table.item(r, col).setText(val)
        else:
            self.show_warning("Для автозаполнения выделите ровно 4 ячейки по горизонтали или вертикали.")

    def show_warning(self, text):
        self.banner.setText(text)
        self.banner.setVisible(True)
        QTimer.singleShot(4000, lambda: self.banner.setVisible(False))

    def _update_manual_ui(self):
        if self.manual_mode:
            self.banner.setText("Включён режим ручного ввода — графы можно редактировать.")
            self.banner.setStyleSheet("background:#FFC107; color:black; padding:6px; font-weight:bold;")
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
        self._build_table()

    def apply_code_to_selected(self):
        code = self.code_combo.currentText()
        n_days = self.last_day
        self._is_updating = True
        for idx in self.table.selectedIndexes():
            r = idx.row() - 2
            c = idx.column()
            if r < 0 or c < 2 or c > 1 + n_days:
                continue
            day = c - 1
            self.data["rows"][r]["cells"][day] = code
            self.table.item(idx.row(), idx.column()).setText(code)
        self._is_updating = False
        
        for r_idx in range(len(self.data["rows"])):
            if not self.manual_mode:
                res = self._calculate(self.data["rows"][r_idx])
                for i, key in enumerate(self.summary_keys):
                    col = 2 + n_days + i
                    self.table.item(r_idx + 2, col).setText(str(res.get(key, "")))
        self.is_modified = True

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
        self.is_modified = False

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

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.close() 
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.is_modified:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Несохраненные изменения")
            msg.setText("В документе есть несохраненные изменения. Сохранить перед выходом?")
            btn_save = msg.addButton("Сохранить и выйти", QMessageBox.AcceptRole)
            btn_exit = msg.addButton("Выйти без сохранения", QMessageBox.DestructiveRole)
            btn_cancel = msg.addButton("Остаться", QMessageBox.RejectRole)
            msg.exec()

            if msg.clickedButton() == btn_save:
                self.save()
                event.accept()
            elif msg.clickedButton() == btn_exit:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
