from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QListWidget, QListWidgetItem, QMessageBox,
                                QDialog, QComboBox, QLabel, QTableWidget,
                                QTableWidgetItem, QCheckBox, QDialogButtonBox,
                                QGridLayout)
from PySide6.QtCore import Qt

from ...config import MONTHS_RU
from ...services.employee_service import list_employees
from ...services.document_service import (create_document, list_documents,
                                           delete_document)
from ...services.settings_service import list_years
from ..widgets.document_widget import DocumentWidget


class DocItemWidget(QWidget):
    def __init__(self, text, on_restore):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.label = QLabel(text)
        self.btn = QPushButton("Развернуть")
        self.btn.setStyleSheet("background-color: #1E88E5; color: white; font-weight: bold; border-radius: 3px; padding: 2px 10px;")
        self.btn.clicked.connect(on_restore)
        self.btn.hide()
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.btn)


class NewDocumentDialog(QDialog):
    def __init__(self, group, doc_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новый документ")
        self.resize(500, 550)
        self.group = group
        self.doc_type = doc_type

        lay = QVBoxLayout(self)
        grid = QGridLayout()
        
        grid.addWidget(QLabel("Месяц:"), 0, 0)
        self.month_combo = QComboBox()
        for i, m in enumerate(MONTHS_RU):
            self.month_combo.addItem(m, i + 1)
        grid.addWidget(self.month_combo, 0, 1)

        grid.addWidget(QLabel("Год:"), 0, 2)
        self.year_combo = QComboBox()
        years = list_years()
        if not years:
            QMessageBox.warning(self, "Нет годов", "Сначала добавьте год в разделе «Общие настройки»")
            self.reject()
            return
        for y in years:
            self.year_combo.addItem(str(y), y)
        grid.addWidget(self.year_combo, 0, 3)

        self.schedule_combo = None
        if doc_type == "timesheet" and group == "security":
            lbl_sched = QLabel("На основе графика:")
            lbl_sched.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(lbl_sched, 1, 0)
            
            self.schedule_combo = QComboBox()
            self.schedule_combo.addItem("(без графика)", None)
            docs = list_documents("schedule", "security")
            docs.sort(key=lambda x: x[0], reverse=True)
            for d in docs:
                did, dt, grp, yr, mn, inst = d
                suffix = f" ({inst})" if inst > 0 else ""
                self.schedule_combo.addItem(f"{MONTHS_RU[mn - 1]} {yr}{suffix}", did)
            
            grid.addWidget(self.schedule_combo, 1, 1, 1, 3)

        lay.addLayout(grid)
        lay.addWidget(QLabel("Сотрудники:"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "ФИО", "Должность"])
        
        emps = [e for e in list_employees(group) if not e[4]]
        self.employees_data = emps
        self.table.setRowCount(len(emps))
        for i, e in enumerate(emps):
            cb = QCheckBox()
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
        src = None
        if self.schedule_combo is not None:
            src = self.schedule_combo.currentData()
        return year, month, selected, src


class OpenPreviousDialog(QDialog):
    def __init__(self, group, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Открыть документ")
        self.resize(400, 400)
        self.group = group
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Год:"))
        self.year_combo = QComboBox()
        for y in list_years():
            self.year_combo.addItem(str(y), y)
        self.year_combo.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.year_combo)
        lay.addLayout(row)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.accept)
        lay.addWidget(self.list_widget)
        btns = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        year = self.year_combo.currentData()
        if not year:
            return
        for d in list_documents(group=self.group):
            did, dt, grp, yr, mn, inst = d
            if yr != year:
                continue
            title = "График" if dt == "schedule" else "Табель"
            suffix = f" ({inst})" if inst > 0 else ""
            item = QListWidgetItem(f"{title} за {MONTHS_RU[mn - 1]}{suffix}")
            item.setData(0x100, did)
            self.list_widget.addItem(item)

    def get_selected_doc_id(self):
        item = self.list_widget.currentItem()
        return item.data(0x100) if item else None


class SecurityTab(QWidget):
    def __init__(self):
        super().__init__()
        self.windows = {}
        self.list_widgets = {}
        
        lay = QVBoxLayout(self)
        tools = QHBoxLayout()
        b1 = QPushButton("Новый график")
        b1.clicked.connect(lambda: self.new_doc("schedule"))
        tools.addWidget(b1)
        b2 = QPushButton("Новый табель")
        b2.clicked.connect(lambda: self.new_doc("timesheet"))
        tools.addWidget(b2)
        b3 = QPushButton("Предыдущий график/табель")
        b3.clicked.connect(self.open_previous)
        tools.addWidget(b3)
        b4 = QPushButton("Удалить")
        b4.clicked.connect(self.delete_selected)
        tools.addWidget(b4)
        tools.addStretch()
        lay.addLayout(tools)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.open_selected)
        lay.addWidget(self.list_widget)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        self.list_widgets.clear()
        
        for d in list_documents(group="security"):
            did, dt, grp, yr, mn, inst = d
            title = "График" if dt == "schedule" else "Табель"
            suffix = f" ({inst})" if inst > 0 else ""
            title_text = f"{title} за {MONTHS_RU[mn - 1]} {yr}{suffix}"
            
            item = QListWidgetItem(self.list_widget)
            item.setData(0x100, did)
            
            w = DocItemWidget(title_text, lambda checked, d_id=did: self.restore_doc(d_id))
            
            if did in self.windows and self.windows[did].isHidden():
                w.btn.show()

            self.list_widget.setItemWidget(item, w)
            self.list_widgets[did] = w

    def open_doc(self, doc_id):
        if doc_id in self.windows:
            self.restore_doc(doc_id)
            return
            
        w = DocumentWidget(doc_id, self)
        self.windows[doc_id] = w
        w.minimized_signal.connect(lambda d=doc_id: self.on_window_minimized(d))
        w.restored_signal.connect(lambda d=doc_id: self.on_window_restored(d))
        w.finished.connect(lambda: self.clean_window(doc_id))
        w.show()

    def restore_doc(self, doc_id):
        if doc_id in self.windows:
            w = self.windows[doc_id]
            w.restore_window()

    def on_window_minimized(self, doc_id):
        if doc_id in self.list_widgets:
            self.list_widgets[doc_id].btn.show()

    def on_window_restored(self, doc_id):
        if doc_id in self.list_widgets:
            self.list_widgets[doc_id].btn.hide()

    def clean_window(self, doc_id):
        if doc_id in self.windows:
            del self.windows[doc_id]
        if doc_id in self.list_widgets:
            self.list_widgets[doc_id].btn.hide()

    def new_doc(self, doc_type):
        d = NewDocumentDialog("security", doc_type, self)
        if d.exec():
            year, month, employees, source = d.get_result()
            if not employees:
                QMessageBox.warning(self, "Пусто", "Не выбрано ни одного сотрудника")
                return
            
            existing = [doc for doc in list_documents(doc_type, "security") if doc[3] == year and doc[4] == month]
            if existing:
                name = "график" if doc_type == "schedule" else "табель"
                r = QMessageBox.question(
                    self, "Документ уже существует",
                    f"За {MONTHS_RU[month-1]} {year} уже есть {name}.\n\nСоздать еще один?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if r != QMessageBox.Yes:
                    return

            doc_id = create_document(doc_type, "security", year, month, employees, source)
            self.refresh()
            self.open_doc(doc_id)

    def open_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        doc_id = item.data(0x100)
        self.open_doc(doc_id)

    def open_previous(self):
        d = OpenPreviousDialog("security", self)
        if d.exec():
            doc_id = d.get_selected_doc_id()
            if doc_id:
                self.open_doc(doc_id)

    def delete_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        doc_id = item.data(0x100)
        if QMessageBox.question(self, "Удалить", "Удалить документ?") == QMessageBox.Yes:
            if doc_id in self.windows:
                self.windows[doc_id].close()
            delete_document(doc_id)
            self.refresh()
