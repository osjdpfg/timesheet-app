from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QComboBox, QTableWidget,
                                QTableWidgetItem, QColorDialog, QMessageBox,
                                QInputDialog)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from ...services.settings_service import (list_years, add_year, delete_year,
                                           update_month, get_year_month,
                                           get_setting, set_setting)
from ...config import MONTHS_RU


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._loading = False
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Год:"))
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self.load_year)
        top.addWidget(self.year_combo)

        btn_add = QPushButton("Добавить год")
        btn_add.clicked.connect(self.add_year_clicked)
        top.addWidget(btn_add)

        btn_del = QPushButton("Удалить год")
        btn_del.clicked.connect(self.delete_year_clicked)
        top.addWidget(btn_del)

        top.addSpacing(20)
        top.addWidget(QLabel("Предпраздничный:"))
        self.hour_mode = QComboBox()
        self.hour_mode.addItems(["Считать 8 часов", "Считать 7 часов"])
        self.hour_mode.currentIndexChanged.connect(self.save_hour_mode)
        top.addWidget(self.hour_mode)

        top.addSpacing(20)
        btn_color = QPushButton("Цвет выходных")
        btn_color.clicked.connect(self.pick_color)
        top.addWidget(btn_color)

        top.addStretch()
        lay.addLayout(top)

        self.table = QTableWidget(12, 3)
        self.table.setHorizontalHeaderLabels(
            ["Месяц", "Норма часов", "Праздничные дни (через запятую)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        for i, m in enumerate(MONTHS_RU):
            it = QTableWidgetItem(m)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, it)
        self.table.itemChanged.connect(self.on_cell_changed)
        lay.addWidget(self.table)

        self.load_hour_mode()
        self.refresh_years()

    def refresh_years(self):
        years = list_years()
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for y in years:
            self.year_combo.addItem(str(y), y)
        if years:
            self.year_combo.setCurrentIndex(len(years) - 1)
        self.year_combo.blockSignals(False)
        self.load_year()

    def load_year(self):
        year = self.year_combo.currentData()
        if year is None:
            return
        self._loading = True
        for m in range(1, 13):
            norm, hol = get_year_month(year, m)
            self.table.setItem(m - 1, 1,
                                QTableWidgetItem(str(norm) if norm else ""))
            self.table.setItem(m - 1, 2, QTableWidgetItem(hol))
        self._loading = False

    def on_cell_changed(self, item):
        if self._loading:
            return
        year = self.year_combo.currentData()
        if year is None:
            return
        month = item.row() + 1
        n = self.table.item(item.row(), 1)
        h = self.table.item(item.row(), 2)
        try:
            norm = int(n.text()) if n and n.text().strip() else 0
        except ValueError:
            norm = 0
        update_month(year, month, norm, h.text() if h else "")

    def add_year_clicked(self):
        year, ok = QInputDialog.getInt(self, "Новый год", "Год:", 2026, 2000, 2100)
        if ok:
            if not add_year(year):
                QMessageBox.warning(self, "Ошибка", "Такой год уже есть")
            else:
                self.refresh_years()

    def delete_year_clicked(self):
        year = self.year_combo.currentData()
        if year is None:
            return
        r = QMessageBox.question(
            self, "Удаление",
            f"Вы уверены? Будут удалены все табели и графики за {year} год.",
            QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            delete_year(year)
            self.refresh_years()

    def pick_color(self):
        current = QColor(get_setting("weekend_color", "#FFE0B2"))
        c = QColorDialog.getColor(current, self, "Цвет выходных")
        if c.isValid():
            set_setting("weekend_color", c.name())

    def load_hour_mode(self):
        v = get_setting("use_7h", "1")
        self.hour_mode.blockSignals(True)
        self.hour_mode.setCurrentIndex(1 if v == "1" else 0)
        self.hour_mode.blockSignals(False)

    def save_hour_mode(self):
        set_setting("use_7h", "1" if self.hour_mode.currentIndex() == 1 else "0")
