#! python3

from PSApp import PSAppMainWindow
from PSAppFirmwareLoader import PSAppFirmwareLoader
from PyQt5.QtWidgets import QApplication
from PSAppSharedFunctions import PSAppExitCodes
from time import sleep

# If we're going into DFU mode, we'll shut down the 'main' GUI, and restart
# with a different GUI that only looks for the DFU interface, and runs the
# actual firmware upgrade.

def main():
    app = QApplication([])
    window = PSAppMainWindow(app)
    window.show()
    ret_val = app.exec()
    window.close()
    while True:
        if (ret_val == PSAppExitCodes.EXIT.value):
            break
        elif (ret_val == PSAppExitCodes.FW.value):
            window = PSAppFirmwareLoader(app)
            window.show()
            ret_val = app.exec()
            window.close()
        elif (ret_val == PSAppExitCodes.RETURN.value):
            window = PSAppMainWindow(app)
            window.show()
            ret_val = app.exec()
            window.close()
        else:
            raise SystemExit("Unrecognized application exit code, ret_val = {}".format(ret_val))
    raise SystemExit(0)

if __name__ == "__main__":
    main()
