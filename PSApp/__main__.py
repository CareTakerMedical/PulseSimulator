#! python3

from PSApp import PSAppMainWindow
from PyQt5.QtWidgets import QApplication

def main():
    app = QApplication([])
    window = PSAppMainWindow()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()
