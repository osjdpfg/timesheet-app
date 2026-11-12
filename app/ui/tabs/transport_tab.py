from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QListWidget, QListWidgetItem, QMessageBox)
from ...config import MONTHS_RU
from ...services.document_service import (create_document, list_documents,
                                           delete_document)
from ..widgets.document_widget import DocumentWidget
from .security_tab import NewDocumentDialog, OpenPreviousDialog, DocItemWidget


class TransportTab(QWidget):
    def __init__(self):
        super().__init__()
        self.windows = {}
        self.list_widgets = {}
        
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
        self.list_widgets.clear()
        
        for d in list_documents(group="transport"):
            did, dt, grp, yr, mn, inst = d
            suffix = f" ({inst})" if inst > 0 else ""
            title_text = f"Табель за {MONTHS_RU[mn - 1]} {yr}{suffix}"
            
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

    def open_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        doc_id = item.data(0x100)
        self.open_doc(doc_id)

    def open_previous(self):
        d = OpenPreviousDialog("transport", self)
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
