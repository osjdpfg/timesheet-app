from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QListWidget, QListWidgetItem, QMessageBox)
from ...config import MONTHS_RU
from ...services.document_service import (create_document, list_documents,
                                           delete_document)
from ..widgets.document_widget import DocumentWidget
from .security_tab import NewDocumentDialog, OpenPreviousDialog


class TransportTab(QWidget):
    def __init__(self):
        super().__init__()
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

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.open_selected)
        lay.addWidget(self.list_widget)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        for d in list_documents(group="transport"):
            did, dt, grp, yr, mn = d
            item = QListWidgetItem(f"Табель за {MONTHS_RU[mn - 1]} {yr}")
            item.setData(0x100, did)
            self.list_widget.addItem(item)

    def new_doc(self):
        d = NewDocumentDialog("transport", "timesheet", self)
        if d.exec():
            year, month, employees, _ = d.get_result()
            if not employees:
                QMessageBox.warning(self, "Пусто",
                                    "Не выбрано ни одного сотрудника")
                return
            doc_id = create_document("timesheet", "transport", year, month,
                                     employees)
            self.refresh()
            w = DocumentWidget(doc_id, self)
            w.exec()
            self.refresh()

    def open_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        w = DocumentWidget(item.data(0x100), self)
        w.exec()
        self.refresh()

    def open_previous(self):
        d = OpenPreviousDialog("transport", self)
        if d.exec():
            doc_id = d.get_selected_doc_id()
            if doc_id:
                w = DocumentWidget(doc_id, self)
                w.exec()
                self.refresh()

    def delete_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        if QMessageBox.question(self, "Удалить",
                                "Удалить документ?") == QMessageBox.Yes:
            delete_document(item.data(0x100))
            self.refresh()