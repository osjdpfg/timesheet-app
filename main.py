import sys
from PySide6.QtWidgets import QApplication
from app.database.db import init_db
from app.ui.main_window import MainWindow


def main():
    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()