from PySide6.QtWidgets import QMainWindow, QTabWidget
from .tabs.security_tab import SecurityTab
from .tabs.transport_tab import TransportTab
from .tabs.settings_tab import SettingsTab
from .tabs.employees_tab import EmployeesTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Учёт рабочих дней")
        self.resize(1100, 700)
        tabs = QTabWidget()
        tabs.addTab(SecurityTab(), "Группа по охранному обеспечению")
        tabs.addTab(TransportTab(), "Транспортная группа")
        tabs.addTab(SettingsTab(), "Общие настройки")
        tabs.addTab(EmployeesTab(), "Сотрудники")
        self.setCentralWidget(tabs)