from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTableWidget, QTableWidgetItem, QCheckBox,
                                QDialog, QFormLayout, QLineEdit, QComboBox,
                                QDialogButtonBox, QMessageBox)
from ...services.employee_service import (list_employees, add_employee,
                                           update_employee, delete_employee)


class EmployeeDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Сотрудник")
        self.data = data
        form = QFormLayout(self)
        self.name = QLineEdit(data[1] if data else "")
        self.position = QLineEdit(data[2] if data else "")
        self.group = QComboBox()
        self.group.addItem("Группа по охранному обеспечению", "security")
        self.group.addItem("Транспортная группа", "transport")
        if data:
            self.group.setCurrentIndex(0 if data[3] == "security" else 1)
            
        self.sig = QCheckBox("Подписант (выводится внизу документа)")
        self.sig.setChecked(bool(data[4]) if data else False)
        
        self.auto_7h = QCheckBox("Автоматический учет сокращенного дня (8 → 7)")
        self.auto_7h.setChecked(bool(data[5]) if data and len(data) > 5 else False)

        form.addRow("ФИО:", self.name)
        form.addRow("Должность:", self.position)
        form.addRow("Группа:", self.group)
        form.addRow("", self.sig)
        form.addRow("", self.auto_7h)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def get_data(self):
        return (self.name.text().strip(), self.position.text().strip(),
                self.group.currentData(), self.sig.isChecked(), self.auto_7h.isChecked())


class EmployeesTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        b1 = QPushButton("Добавить")
        b1.clicked.connect(self.add)
        b2 = QPushButton("Изменить")
        b2.clicked.connect(self.edit)
        b3 = QPushButton("Удалить")
        b3.clicked.connect(self.delete)
        top.addWidget(b1)
        top.addWidget(b2)
        top.addWidget(b3)
        top.addStretch()
        lay.addLayout(top)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["ФИО", "Должность", "Группа", "Подписант", "Сокр. день"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit)
        lay.addWidget(self.table)
        self.refresh()

    def refresh(self):
        emps = list_employees()
        self.table.setRowCount(len(emps))
        for i, e in enumerate(emps):
            self.table.setItem(i, 0, QTableWidgetItem(e[1]))
            self.table.setItem(i, 1, QTableWidgetItem(e[2]))
            self.table.setItem(i, 2, QTableWidgetItem("Охранная" if e[3] == "security" else "Транспортная"))
            self.table.setItem(i, 3, QTableWidgetItem("Да" if e[4] else ""))
            self.table.setItem(i, 4, QTableWidgetItem("Да" if e[5] else ""))
            self.table.item(i, 0).setData(0x100, e[0])

    def add(self):
        d = EmployeeDialog(self)
        if d.exec():
            name, pos, grp, sig, auto7 = d.get_data()
            if name:
                add_employee(name, pos, grp, sig, auto7)
                self.refresh()

    def edit(self):
        row = self.table.currentRow()
        if row < 0:
            return
        eid = self.table.item(row, 0).data(0x100)
        data = (eid, self.table.item(row, 0).text(),
                self.table.item(row, 1).text(),
                "security" if self.table.item(row, 2).text() == "Охранная" else "transport",
                self.table.item(row, 3).text() == "Да",
                self.table.item(row, 4).text() == "Да")
        d = EmployeeDialog(self, data)
        if d.exec():
            name, pos, grp, sig, auto7 = d.get_data()
            update_employee(eid, name, pos, grp, sig, auto7)
            self.refresh()

    def delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        eid = self.table.item(row, 0).data(0x100)
        if QMessageBox.question(self, "Удалить", "Удалить сотрудника?") == QMessageBox.Yes:
            delete_employee(eid)
            self.refresh()
