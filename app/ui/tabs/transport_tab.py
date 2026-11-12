from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView)
from ...config import MONTHS_RU
from ...services.document_service import (create_document, list_documents,
                                           delete_document)
from ..widgets.document_widget import DocumentWidget
from .security_tab import NewDocumentDialog, OpenPreviousDialog


class TransportTab(QWidget):
    def __init__(self):
        super().__init__()
        self.windows = {}
        
        lay = QVBoxLayout(self)
        tools = QHBoxLayout()
        b1 = QPushButton("Новый табель")
        b1.clicked.connect(self.new_doc)
        tools.addWidget(b1)
        b2 = QPushButton("Предыдущий табель")
        b2.clicked.connect(self.open_previous)
        tools.addWidget(b2)
        b3 = QPushButton("Удалить")
        b3.clicked.connect(self.delete_selected)
        tools.addWidget(b3)
        tools.addStretch()
        lay.addLayout(tools)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Документ", "Статус", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 120)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellDoubleClicked.connect(self.open_selected)
        
        lay.addWidget(self.table)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for d in list_documents(group="transport"):
            did, dt, grp, yr, mn, inst = d
            suffix = f" ({inst})" if inst > 0 else ""
            title_text = f"Табель за {MONTHS_RU[mn - 1]} {yr}{suffix}"
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            item = QTableWidgetItem(title_text)
            item.setData(0x100, did)
            self.table.setItem(row, 0, item)
            
            status_item = QTableWidgetItem("Закрыт")
            self.table.setItem(row, 1, status_item)
            
            btn = QPushButton("Развернуть")
            btn.setStyleSheet("background-color: #1E88E5; color: white; font-weight: bold; border-radius: 3px; padding: 4px;")
            btn.setEnabled(False)
            btn.clicked.connect(lambda checked, d_id=did: self.restore_doc(d_id))
            self.table.setCellWidget(row, 2, btn)

    def update_row_status(self, doc_id):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.data(0x100) == doc_id:
                w = self.windows.get(doc_id)
                if w and w.isMinimized():
                    self.table.item(r, 1).setText("Свернут")
                    self.table.cellWidget(r, 2).setEnabled(True)
                elif w:
                    self.table.item(r, 1).setText("Открыт")
                    self.table.cellWidget(r, 2).setEnabled(False)
                else:
                    self.table.item(r, 1).setText("Закрыт")
                    self.table.cellWidget(r, 2).setEnabled(False)
                break

    def open_doc(self, doc_id):
        if doc_id in self.windows:
            self.restore_doc(doc_id)
            return
            
        w = DocumentWidget(doc_id, self)
        self.windows[doc_id] = w
        w.minimized_signal.connect(lambda: self.update_row_status(doc_id))
        w.restored_signal.connect(lambda: self.update_row_status(doc_id))
        w.finished.connect(lambda: self.clean_window(doc_id))
        w.show()
        self.update_row_status(doc_id)

    def restore_doc(self, doc_id):
        if doc_id in self.windows:
            w = self.windows[doc_id]
            w.restore_window()

    def clean_window(self, doc_id):
        if doc_id in self.windows:
            del self.windows[doc_id]
        self.update_row_status(doc_id)

    def new_doc(self):
        d = NewDocumentDialog("transport", "timesheet", self)
        if d.exec():
            year, month, employees, _ = d.get_result()
            if not employees:
                QMessageBox.warning(self, "Пусто", "Не выбрано ни одного сотрудника")
                return
            
            existing = [doc for doc in list_documents("timesheet", "transport") if doc[3] == year and doc[4] == month]
            if existing:
                r = QMessageBox.question(
                    self, "Документ уже существует",
                    f"За {MONTHS_RU[month-1]} {year} уже есть табель.\n\nСоздать еще один?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if r != QMessageBox.Yes:
                    return

            doc_id = create_document("timesheet", "transport", year, month, employees)
            self.refresh()
            self.open_doc(doc_id)

    def open_selected(self, row, col):
        if col == 2: return
        item = self.table.item(row, 0)
        if not item: return
        self.open_doc(item.data(0x100))

    def open_previous(self):
        d = OpenPreviousDialog("transport", self)
        if d.exec():
            doc_id = d.get_selected_doc_id()
            if doc_id:
                self.open_doc(doc_id)

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0: return
        doc_id = self.table.item(row, 0).data(0x100)
        if QMessageBox.question(self, "Удалить", "Удалить документ?") == QMessageBox.Yes:
            if doc_id in self.windows:
                w = self.windows[doc_id]
                w.is_modified = False
                w.close()
                del self.windows[doc_id]
            delete_document(doc_id)
            self.refresh()
