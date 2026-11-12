import calendar
import copy
import json
from datetime import date

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTableWidget, QTableWidgetItem, QLabel,
                                QComboBox, QMessageBox, QFileDialog,
                                QAbstractItemView, QWidget, QGridLayout, QCheckBox,
                                QDialogButtonBox)
from PySide6.QtGui import QColor, QBrush, QFont, QKeyEvent, QKeySequence, QPalette
from PySide6.QtCore import Qt, QTimer, Signal, QEvent

from ...config import MONTHS_RU, WEEKDAYS_RU
from ...core.calculations import (calc_security_schedule,
                                   calc_security_timesheet,
                                   calc_transport_timesheet)
from ...core.designations import DESIGNATIONS
from ...services.settings_service import (get_year_month, get_weekend_color,
                                           get_all_colors, get_setting, set_setting,
                                           list_years)
from ...services.document_service import load_document, save_document
from ...services.employee_service import list_employees
from ...services.document_service import get_linked_timesheets, update_document_structure
from ...export.excel_export import export_document_to_excel


def allowed_codes(group, doc_type, position):
    if group == "security":
        return ["15", "9", "8", "7", "В", "О", "Б", "А", "П", "С", "МО", ""]
    return ["8", "7", "Р", "К", "СЗ", "МО", "Б", "О", "А", "П", "В", ""]


class _RowProxy:
    pass


class _CellProxy:
    def __init__(self, day, code):
        self.day = day
        self.code = code


class EditDocumentDialog(QDialog):
    def __init__(self, doc_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактировать документ")
        self.resize(500, 550)
        self.doc_data = doc_data
        
        lay = QVBoxLayout(self)
        grid = QGridLayout()
        
        grid.addWidget(QLabel("Месяц:"), 0, 0)
        self.month_combo = QComboBox()
        for i, m in enumerate(MONTHS_RU):
            self.month_combo.addItem(m, i + 1)
        self.month_combo.setCurrentIndex(doc_data["month"] - 1)
        grid.addWidget(self.month_combo, 0, 1)

        grid.addWidget(QLabel("Год:"), 0, 2)
        self.year_combo = QComboBox()
        for y in list_years():
            self.year_combo.addItem(str(y), y)
        idx = self.year_combo.findData(doc_data["year"])
        if idx >= 0: self.year_combo.setCurrentIndex(idx)
        grid.addWidget(self.year_combo, 0, 3)
        
        lay.addLayout(grid)
        
        lay.addWidget(QLabel("Сотрудники:"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "ФИО", "Должность"])
        
        emps = [e for e in list_employees(doc_data["group"]) if not e[4]]
        active_keys = { (r["employee_name"], r["employee_position"]) for r in doc_data["rows"] }
        
        self.employees_data = emps
        self.table.setRowCount(len(emps))
        for i, e in enumerate(emps):
            cb = QCheckBox()
            if (e[1], e[2]) in active_keys:
                cb.setChecked(True)
            self.table.setCellWidget(i, 0, cb)
            self.table.setItem(i, 1, QTableWidgetItem(e[1]))
            self.table.setItem(i, 2, QTableWidgetItem(e[2]))
        lay.addWidget(self.table)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        
    def get_result(self):
        month = self.month_combo.currentData()
        year = self.year_combo.currentData()
        selected = []
        for i in range(self.table.rowCount()):
            cb = self.table.cellWidget(i, 0)
            if cb and cb.isChecked():
                e = self.employees_data[i]
                selected.append((e[1], e[2], e[5]))
        return year, month, selected


class DocumentWidget(QDialog):
    minimized_signal = Signal()
    restored_signal = Signal()

    def __init__(self, doc_id, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        
        self.is_modified = False
        self._drag_start = None
        self._drag_val = ""
        self.undo_stack = []

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
            self.summary_keys = ["Факт. работы", "Отпуск", "Всего", "Норма", "Ознакомлен"]
        elif self.group == "security":
            self.summary_keys = [
                "Факт. работы", "Медицинский осмотр", "Болезнь", "Справка",
                "Отпуск", "Прогул", "Отпуск без сохранения з/п",
                "Всего", "Норма", "Переработка", "Работа в ночь",
                "Работа в праздничные дни"]
        else:
            self.summary_keys = [
                "Факт. работы, дни", "Командировка, дни",
                "Разъездной характер работы", "Расчет по среднему",
                "Медицинский осмотр", "Болезнь", "Отпуск",
                "Отпуск без сохранения з/п", "Прогул",
                "Факт. время, часов", "Норма, часов"]

        self.resize(1650, 800)
        lay = QVBoxLayout(self)

        self.banner = QLabel("")
        self.banner.setStyleSheet("background:#FFC107; color:black; padding:6px; font-weight:bold;")
        self.banner.setVisible(False)
        lay.addWidget(self.banner)

        self.title_label = QLabel()
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        self.title_label.setFont(f)
        self.title_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title_label)
        self._update_title()

        tools = QHBoxLayout()
        btn_edit_doc = QPushButton("Редактировать")
        btn_edit_doc.clicked.connect(self.edit_document_settings)
        tools.addWidget(btn_edit_doc)

        self.btn_manual = QPushButton()
        self.btn_manual.clicked.connect(self.toggle_manual)
        tools.addWidget(self.btn_manual)

        tools.addWidget(QLabel("Обозначение:"))
        self.code_combo = QComboBox()
        all_codes = set()
        for r in self.data["rows"]:
            for c in allowed_codes(self.group, self.doc_type, r["employee_position"]):
                if c:
                    all_codes.add(c)
        self.code_combo.addItems([""] + sorted(all_codes))
        tools.addWidget(self.code_combo)

        btn_apply = QPushButton("Применить к выделенным")
        btn_apply.clicked.connect(self.apply_code_to_selected)
        tools.addWidget(btn_apply)

        btn_autofill = QPushButton("Автозаполнить")
        btn_autofill.clicked.connect(self.auto_fill_pattern)
        tools.addWidget(btn_autofill)

        tools.addStretch()

        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.save)
        tools.addWidget(btn_save)

        btn_export = QPushButton("Экспорт в Excel")
        btn_export.clicked.connect(self.export_excel)
        tools.addWidget(btn_export)

        lay.addLayout(tools)

        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.table.setStyleSheet("""
            QTableWidget::item:selected {
                border: 2px solid #1E88E5;
                background-color: transparent;
            }
        """)
        
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.mousePressEvent = self._table_mouse_press
        self.table.mouseMoveEvent = self._table_mouse_move
        self.table.mouseReleaseEvent = self._table_mouse_release

        lay.addWidget(self.table)

        legend_text = "  |  ".join([f"<b>{k}</b> — {v}" for k, v in DESIGNATIONS.items()])
        legend_label = QLabel(legend_text)
        legend_label.setWordWrap(True)
        legend_label.setStyleSheet("font-size: 12px; padding-top: 10px;")
        lay.addWidget(legend_label)

        self._build_table()
        self._update_manual_ui()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                self.hide() 
                self.minimized_signal.emit()
            elif event.oldState() & Qt.WindowMinimized:
                self.restored_signal.emit()
        super().changeEvent(event)
        
    def restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _update_title(self):
        inst_num = self.data.get("instance_number", 0)
        suffix = f" ({inst_num})" if inst_num > 0 else ""
        if self.doc_type == "schedule":
            title = f"График группы по охранному обеспечению на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}"
        elif self.group == "security":
            title = f"Табель группы по охранному обеспечению на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}"
        else:
            title = f"Табель транспортной группы на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}"
        self.setWindowTitle(title)
        self.title_label.setText(title)

    def edit_document_settings(self):
        if self.doc_type == "schedule":
            linked = get_linked_timesheets(self.doc_id)
            if linked:
                r = QMessageBox.question(
                    self, "Внимание", 
                    "К этому графику привязан табель.\n\n"
                    "Изменения сотрудников и месяца отразятся и на нём.\n"
                    "Продолжить?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if r != QMessageBox.Yes:
                    return
                    
        d = EditDocumentDialog(self.data, self)
        if d.exec():
            new_year, new_month, employees = d.get_result()
            if update_document_structure(self.doc_id, new_year, new_month, employees):
                self.data = load_document(self.doc_id)
                # Принудительно обновляем год и месяц, чтобы заголовок сменился сразу
                self.data["year"] = new_year
                self.data["month"] = new_month
                self.year = new_year
                self.month = new_month
                self.last_day = calendar.monthrange(self.year, self.month)[1]
                
                self._update_title()
                self._build_table()
                self.is_modified = True

    def _apply_item_color(self, item, code):
        code_colors = get_all_colors()
        if code and code in code_colors:
            bg = QColor(code_colors[code])
            item.setBackground(QBrush(bg))
            r, g, b = bg.red(), bg.green(), bg.blue()
            yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000
            item.setForeground(QBrush(QColor("#000000" if yiq >= 128 else "#FFFFFF")))
        else:
            item.setData(Qt.BackgroundRole, None)
            item.setData(Qt.ForegroundRole, None)

    def _build_table(self):
        self.table.blockSignals(True)
        n_rows = len(self.data["rows"])
        n_days = self.last_day
        n_cols = 3 + n_days + len(self.summary_keys)
        
        self.table.clear()
        self.table.setRowCount(n_rows + 2)
        self.table.setColumnCount(n_cols)

        saved_widths = {}
        raw_widths = get_setting(f"col_widths_{self.doc_id}", "{}")
        try:
            saved_widths = json.loads(raw_widths)
        except Exception:
            pass

        for c in range(n_cols):
            key = str(c)
            if key in saved_widths:
                self.table.setColumnWidth(c, saved_widths[key])
            else:
                if c == 0: self.table.setColumnWidth(c, 50)
                elif c == 1: self.table.setColumnWidth(c, 180)
                elif c == 2: self.table.setColumnWidth(c, 150)
                elif 3 <= c <= 2 + n_days: self.table.setColumnWidth(c, 30)
                else: self.table.setColumnWidth(c, 80)

        self.table.setSpan(0, 0, 2, 1)
        top1 = QTableWidgetItem("Перем.")
        top1.setFlags(top1.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(0, 0, top1)
        
        self.table.setSpan(0, 1, 2, 1)
        top2 = QTableWidgetItem("ФИО")
        top2.setFlags(top2.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(0, 1, top2)
        
        self.table.setSpan(0, 2, 2, 1)
        top3 = QTableWidgetItem("Должность")
        top3.setFlags(top3.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(0, 2, top3)

        base_color = self.table.palette().color(QPalette.Base)
        weekend_header_color = base_color.lighter(135) if base_color.lightness() < 128 else base_color.darker(105)

        for d in range(1, n_days + 1):
            col = 2 + d
            dow = date(self.year, self.month, d).weekday()
            
            wd = QTableWidgetItem(WEEKDAYS_RU[dow])
            wd.setTextAlignment(Qt.AlignCenter)
            wd.setFlags(wd.flags() & ~Qt.ItemIsEditable) 
            self.table.setItem(0, col, wd)
            
            dt = QTableWidgetItem(str(d))
            dt.setTextAlignment(Qt.AlignCenter)
            dt.setFlags(dt.flags() & ~Qt.ItemIsEditable) 
            self.table.setItem(1, col, dt)
            
            if dow >= 5:
                wd.setBackground(QBrush(weekend_header_color))
                dt.setBackground(QBrush(weekend_header_color))

        for i, key in enumerate(self.summary_keys):
            col = 3 + n_days + i
            it = QTableWidgetItem(key)
            it.setTextAlignment(Qt.AlignCenter)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable) 
            self.table.setItem(0, col, it)
            self.table.setSpan(0, col, 2, 1)

        _, holidays_str = get_year_month(self.year, self.month)
        holidays = set(int(x.strip()) for x in holidays_str.split(',') if x.strip().isdigit())

        for r_idx, row in enumerate(self.data["rows"]):
            gr = r_idx + 2
            
            move_widget = QWidget()
            move_layout = QHBoxLayout(move_widget)
            move_layout.setContentsMargins(0, 0, 0, 0)
            move_layout.setSpacing(2)
            
            btn_up = QPushButton("▲")
            btn_down = QPushButton("▼")
            btn_up.setFixedSize(22, 22)
            btn_down.setFixedSize(22, 22)
            btn_style = "font-weight: bold; background-color: #E0E0E0; color: black; border: 1px solid #999; border-radius: 3px;"
            btn_up.setStyleSheet(btn_style)
            btn_down.setStyleSheet(btn_style)
            
            btn_up.clicked.connect(lambda checked, r=r_idx: self.move_row(r, -1))
            btn_down.clicked.connect(lambda checked, r=r_idx: self.move_row(r, 1))
            
            move_layout.addWidget(btn_up)
            move_layout.addWidget(btn_down)
            self.table.setCellWidget(gr, 0, move_widget)

            name_item = QTableWidgetItem(row["employee_name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(gr, 1, name_item)
            
            pos_item = QTableWidgetItem(row["employee_position"])
            pos_item.setFlags(pos_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(gr, 2, pos_item)
            
            for d in range(1, n_days + 1):
                code = row["cells"].get(d, "").upper()
                
                if code == "8" and row.get("auto_7h", False):
                    if (d + 1) in holidays and date(self.year, self.month, d).weekday() < 5:
                        code = "7"
                        row["cells"][d] = "7"
                
                it = QTableWidgetItem(code)
                it.setTextAlignment(Qt.AlignCenter)
                self._apply_item_color(it, code)
                self.table.setItem(gr, 2 + d, it)
            
            res = self._calculate(row)
            for i, key in enumerate(self.summary_keys):
                col = 3 + n_days + i
                if self.manual_mode and key in row["overrides"]:
                    val = row["overrides"][key]
                else:
                    val = str(res.get(key, ""))
                it = QTableWidgetItem(val)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(gr, col, it)

        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _save_widths(self):
        widths = {}
        for c in range(self.table.columnCount()):
            widths[str(c)] = self.table.columnWidth(c)
        set_setting(f"col_widths_{self.doc_id}", json.dumps(widths))

    def _save_undo(self):
        self.undo_stack.append(copy.deepcopy(self.data))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def _undo(self):
        if not self.undo_stack:
            return
        self.data = self.undo_stack.pop()
        self._build_table()
        self.is_modified = True

    def _clear_selected(self):
        sel = self.table.selectedIndexes()
        if not sel:
            return
        self._save_undo()
        self.table.blockSignals(True)
        for idx in sel:
            r, c = idx.row(), idx.column()
            if r < 2 or c < 3 or c > 2 + self.last_day:
                continue
            item = self.table.item(r, c)
            if item:
                item.setText("")
                self._apply_item_color(item, "")
                self.data["rows"][r-2]["cells"][c-2] = ""
        self.table.blockSignals(False)
        
        rows_to_update = set(idx.row() for idx in sel if idx.row() >= 2)
        for r in rows_to_update:
            if not self.manual_mode:
                res = self._calculate(self.data["rows"][r-2])
                for i, key in enumerate(self.summary_keys):
                    self.table.item(r, 3 + self.last_day + i).setText(str(res.get(key, "")))
        self.is_modified = True

    def move_row(self, r_idx, direction):
        new_idx = r_idx + direction
        if 0 <= new_idx < len(self.data["rows"]):
            self._save_undo()
            self.data["rows"][r_idx], self.data["rows"][new_idx] = self.data["rows"][new_idx], self.data["rows"][r_idx]
            self._build_table()
            self.table.selectRow(new_idx + 2)
            self.is_modified = True

    def _table_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            idx = self.table.indexAt(event.pos())
            if idx.isValid():
                rect = self.table.visualRect(idx)
                if event.pos().x() > rect.right() - 10 and event.pos().y() > rect.bottom() - 10:
                    self._save_undo()
                    self._drag_start = (idx.row(), idx.column())
                    self._drag_val = self.table.item(idx.row(), idx.column()).text()
                    return
        self._drag_start = None
        QTableWidget.mousePressEvent(self.table, event)

    def _table_mouse_move(self, event):
        if getattr(self, '_drag_start', None) and event.buttons() & Qt.LeftButton:
            idx = self.table.indexAt(event.pos())
            if idx.isValid():
                r, c = idx.row(), idx.column()
                r0, c0 = self._drag_start
                
                if r == r0 and c != c0:
                    self.table.blockSignals(True)
                    min_c, max_c = min(c0, c), max(c0, c)
                    
                    _, holidays_str = get_year_month(self.year, self.month)
                    holidays = set(int(x.strip()) for x in holidays_str.split(',') if x.strip().isdigit())
                    auto_7h = self.data["rows"][r-2].get("auto_7h", False) if r >= 2 else False
                    
                    for j in range(min_c, max_c + 1):
                        if j > 2 and j <= 2 + self.last_day:
                            day = j - 2
                            val = self._drag_val
                            
                            # Проверяем и меняем 8 на 7 при растягивании
                            if val == "8" and auto_7h:
                                if (day + 1) in holidays and date(self.year, self.month, day).weekday() < 5:
                                    val = "7"
                            
                            item = self.table.item(r, j)
                            item.setText(val)
                            self._apply_item_color(item, val)
                            self.data["rows"][r-2]["cells"][day] = val
                    
                    self.table.blockSignals(False)
                    self.is_modified = True
                    
                    if r > 1 and not self.manual_mode:
                        row_data = self.data["rows"][r-2]
                        res = self._calculate(row_data)
                        for k, key in enumerate(self.summary_keys):
                            col = 3 + self.last_day + k
                            self.table.item(r, col).setText(str(res.get(key, "")))
        else:
            QTableWidget.mouseMoveEvent(self.table, event)

    def _table_mouse_release(self, event):
        self._drag_start = None
        QTableWidget.mouseReleaseEvent(self.table, event)

    def _row_proxy(self, row):
        p = _RowProxy()
        p.employee_name = row["employee_name"]
        p.employee_position = row["employee_position"]
        p.auto_7h = row.get("auto_7h", False)
        p.cells = [_CellProxy(d, c) for d, c in row["cells"].items()]
        return p

    def _calculate(self, row):
        norm_hours, holidays = get_year_month(self.year, self.month)
        proxy = self._row_proxy(row)
        if self.doc_type == "schedule":
            return calc_security_schedule(proxy, self.year, self.month, norm_hours, holidays)
        if self.group == "security":
            return calc_security_timesheet(proxy, self.year, self.month, norm_hours, holidays)
        return calc_transport_timesheet(proxy, self.year, self.month, norm_hours, holidays)

    def on_item_changed(self, item):
        self._save_undo()
        self.is_modified = True
        
        r = item.row()
        c = item.column()
        if r < 2: return

        r_idx = r - 2
        n_days = self.last_day

        if 3 <= c <= 2 + n_days:
            original_text = item.text()
            upper_text = original_text.upper()
            if upper_text != original_text:
                self.table.blockSignals(True)
                item.setText(upper_text)
                self.table.blockSignals(False)

            code = upper_text
            day = c - 2
            
            if code == "8" and self.data["rows"][r_idx].get("auto_7h", False):
                _, holidays_str = get_year_month(self.year, self.month)
                holidays = set(int(x.strip()) for x in holidays_str.split(',') if x.strip().isdigit())
                if (day + 1) in holidays and date(self.year, self.month, day).weekday() < 5:
                    code = "7"
                    self.table.blockSignals(True)
                    item.setText("7")
                    self.table.blockSignals(False)

            self.data["rows"][r_idx]["cells"][day] = code
            
            self.table.blockSignals(True)
            self._apply_item_color(item, code)
            self.table.blockSignals(False)

            if not self.manual_mode:
                res = self._calculate(self.data["rows"][r_idx])
                self.table.blockSignals(True)
                for i, key in enumerate(self.summary_keys):
                    col = 3 + n_days + i
                    self.table.item(r, col).setText(str(res.get(key, "")))
                self.table.blockSignals(False)

        elif c > 2 + n_days and self.manual_mode:
            key = self.summary_keys[c - (3 + n_days)]
            self.data["rows"][r_idx]["overrides"][key] = item.text()

    def auto_fill_pattern(self):
        sel = self.table.selectedRanges()
        if not sel:
            self.show_warning("Выделите диапазон для автозаполнения.")
            return
        
        rng = sel[0]
        rows = rng.rowCount()
        cols = rng.columnCount()
        
        if cols >= 4:
            self._save_undo()
            self.table.blockSignals(True)
            
            _, holidays_str = get_year_month(self.year, self.month)
            holidays = set(int(x.strip()) for x in holidays_str.split(',') if x.strip().isdigit())
            
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                pattern = []
                for c in range(rng.leftColumn(), rng.leftColumn() + 4):
                    pattern.append(self.table.item(r, c).text())
                
                auto_7h = self.data["rows"][r-2].get("auto_7h", False) if r >= 2 else False
                
                for c in range(rng.leftColumn() + 4, 3 + self.last_day):
                    val = pattern[(c - rng.leftColumn()) % 4]
                    day = c - 2
                    
                    if val == "8" and auto_7h:
                        if (day + 1) in holidays and date(self.year, self.month, day).weekday() < 5:
                            val = "7"
                            
                    item = self.table.item(r, c)
                    item.setText(val)
                    self._apply_item_color(item, val)
                    self.data["rows"][r-2]["cells"][day] = val
            
            self.table.blockSignals(False)
            
            rows_to_update = set(range(rng.topRow(), rng.bottomRow() + 1))
            for r in rows_to_update:
                if not self.manual_mode:
                    res = self._calculate(self.data["rows"][r-2])
                    for i, key in enumerate(self.summary_keys):
                        self.table.item(r, 3 + self.last_day + i).setText(str(res.get(key, "")))
            self.is_modified = True
        else:
            self.show_warning("Выделите минимум 4 ячейки по горизонтали.")

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
        self._save_undo()
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
        code = self.code_combo.currentText().upper()
        n_days = self.last_day
        self._save_undo()
        self.table.blockSignals(True)
        for idx in self.table.selectedIndexes():
            r = idx.row() - 2
            c = idx.column()
            if r < 0 or c < 3 or c > 2 + n_days:
                continue
            day = c - 2
            
            final_code = code
            if code == "8" and self.data["rows"][r].get("auto_7h", False):
                _, holidays_str = get_year_month(self.year, self.month)
                holidays = set(int(x.strip()) for x in holidays_str.split(',') if x.strip().isdigit())
                if (day + 1) in holidays and date(self.year, self.month, day).weekday() < 5:
                    final_code = "7"

            self.data["rows"][r]["cells"][day] = final_code
            item = self.table.item(idx.row(), idx.column())
            item.setText(final_code)
            self._apply_item_color(item, final_code)
        self.table.blockSignals(False)
        
        for r_idx in range(len(self.data["rows"])):
            if not self.manual_mode:
                res = self._calculate(self.data["rows"][r_idx])
                for i, key in enumerate(self.summary_keys):
                    col = 3 + n_days + i
                    self.table.item(r_idx + 2, col).setText(str(res.get(key, "")))
        self.is_modified = True

    def save(self):
        self._save_widths()
        n_days = self.last_day
        for r_idx, row in enumerate(self.data["rows"]):
            gr = r_idx + 2
            for d in range(1, n_days + 1):
                it = self.table.item(gr, 2 + d)
                row["cells"][d] = it.text() if it else ""
            if self.manual_mode:
                for i, key in enumerate(self.summary_keys):
                    it = self.table.item(gr, 3 + n_days + i)
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
        elif event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            self._clear_selected()
        elif event.matches(QKeySequence.Undo):
            self._undo()
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
            self._save_widths()
            event.accept()
