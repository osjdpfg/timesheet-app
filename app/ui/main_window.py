from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRectF
from .tabs.security_tab import SecurityTab
from .tabs.transport_tab import TransportTab
from .tabs.settings_tab import SettingsTab
from .tabs.employees_tab import EmployeesTab


def _make_calendar_icon() -> QIcon:
    """Программно рисует иконку-календарик."""
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)

        s = size / 64.0  # масштаб

        # Корпус календаря (белый с серым контуром)
        p.setPen(QPen(QColor("#90A4AE"), max(1.0, 1.5 * s)))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(7 * s, 11 * s, 50 * s, 46 * s), 4 * s, 4 * s)

        # Синяя шапка
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1E88E5"))
        p.drawRoundedRect(QRectF(7 * s, 11 * s, 50 * s, 13 * s), 4 * s, 4 * s)
        p.drawRect(QRectF(7 * s, 18 * s, 50 * s, 6 * s))

        # Кольца-петельки
        p.setBrush(QColor("#37474F"))
        p.drawRoundedRect(QRectF(17 * s, 5 * s, 4 * s, 11 * s), 2 * s, 2 * s)
        p.drawRoundedRect(QRectF(43 * s, 5 * s, 4 * s, 11 * s), 2 * s, 2 * s)

        # Сетка дней (4 колонки x 3 строки)
        start_x = 13 * s
        start_y = 28 * s
        cell_w = 7 * s
        cell_h = 6 * s
        gap = 3 * s
        for row in range(3):
            for col in range(4):
                x = start_x + col * (cell_w + gap)
                y = start_y + row * (cell_h + gap)
                if row == 1 and col == 2:
                    color = QColor("#E53935")  # выделенный день
                else:
                    color = QColor("#B0BEC5")
                p.setBrush(color)
                p.drawRoundedRect(QRectF(x, y, cell_w, cell_h), 1.2 * s, 1.2 * s)

        p.end()
        icon.addPixmap(pm)

    return icon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Учёт рабочих дней")
        self.resize(1100, 700)
        # Устанавливаем иконку календаря
        self.setWindowIcon(_make_calendar_icon())

        tabs = QTabWidget()
        tabs.addTab(SecurityTab(), "Группа по охранному обеспечению")
        tabs.addTab(TransportTab(), "Транспортная группа")
        tabs.addTab(SettingsTab(), "Общие настройки")
        tabs.addTab(EmployeesTab(), "Сотрудники")
        self.setCentralWidget(tabs)
