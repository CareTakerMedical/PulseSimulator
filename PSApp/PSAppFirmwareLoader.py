from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PSAppVersion import get_psapp_version
from PSAppSharedFunctions import PSAppExitCodes
from hashlib import md5

class PSAppFirmwareLoader(QMainWindow):
    MAGIC_KEY = 0xBC5417FB
    """ Creates the window that will manage the device firmware loading process.
    """
    def __init__(self,parent=None):
        """ Initialization function.
        """
        super(PSAppFirmwareLoader,self).__init__()
        self.setWindowTitle("Pulse Simulator Firmware Loader")
        self.parent = parent
        self.update_complete = False

        # Create central widget
        cwidget = QWidget()

        # Elements
        ptfwf_label = QLabel("Path to Firmware file:  ")
        self.ptfwf_le = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_for_fw_file)
        pwd_label = QLabel("Password:  ")
        pwd_label.setToolTip("Note that password must be eight characters in length")
        self.pwd_le = QLineEdit()
        self.pwd_le.textChanged.connect(self._review_status)
        self.go_button = QPushButton("Go")
        self.go_button.setEnabled(False)
        self.go_button.clicked.connect(self._begin_firmware_process)
        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self._prompt_exit)

        # Layout
        layout = QGridLayout()
        layout.addWidget(ptfwf_label,0,0,1,2)
        layout.addWidget(self.ptfwf_le,0,2,1,5)
        layout.addWidget(browse_button,0,7,1,1)
        layout.addWidget(pwd_label,1,0,1,1)
        layout.addWidget(self.pwd_le,1,1,1,2)
        layout.addWidget(self.go_button,1,3,1,1)
        layout.addWidget(self.exit_button,1,6,1,2)

        cwidget.setLayout(layout)
        self.setCentralWidget(cwidget)

    def _bad_password_msg(self):
        """ Don't give too many clues if the password is bad...
        """
        warn_dlg = QMessageBox()
        warn_dlg.setText("Incorrect Password")
        warn_dlg.exec()

    def _begin_firmware_process(self):
        """ We'll calculate the MD5 sum and XOR it with our magic code to do a poor man's version of compatibility checking.  Then, if that passes, we'll do the actual update.
        """
        try:
            ipwd = int(self.pwd_le.text(),16)
            # Get the MD5 sum and grab the first 8 characters
            code = int(md5(open(self.ptfwf_le.text(),'rb').read()).hexdigest()[:8],16)
            if ((ipwd ^ code) != self.MAGIC_KEY):
                self._bad_password_msg()
                return
        except:
            self._bad_password_msg()
            return

    def _browse_for_fw_file(self):
        """ Bring a file browser to find the location of new firmware.
        """
        fdlg = QFileDialog()
        fdlg.setDefaultSuffix(".bin")
        fdlg.setFileMode(QFileDialog.ExistingFile)
        fdlg.setAcceptMode(QFileDialog.AcceptOpen)
        if fdlg.exec_():
            self.ptfwf_le.setText(fdlg.selectedFiles()[0])
            self._review_status()

    def _graceful_close(self,ec=PSAppExitCodes.EXIT.value):
        """ Try to close gracefully.
        """
        self.parent.exit(ec)

    def _prompt_exit(self):
        """ When exiting, we can either return to the Pulse Simulator GUI, or exit entirely; give the user a choice here.
        """
        prompt_dlg = QMessageBox()
        prompt_dlg.setText("Shall I relaunch the Pulse Simulator application?")
        prompt_dlg.setInformativeText("The firmware update process was {}completed".format("" if self.update_complete else "not "))
        prompt_dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        prompt_dlg.setDefaultButton(QMessageBox.Yes)
        pd_ret = prompt_dlg.exec()
        if (pd_ret == QMessageBox.Yes):
            self._graceful_close(ec=PSAppExitCodes.RETURN.value)
        else:
            self._graceful_close()

    def _review_status(self):
        """ Evaluate that there are values present in both the firmware file line edit and the password line edit.  Note that password checking is not done here yet.
        """
        # First, check to see that the file exists
        try:
            fh = open(self.ptfwf_le.text(),'rb')
        except:
            self.go_button.setEnabled(False)
            return

        # If it does exist, see if the user has supplied any kind of password, and that it is the
        # right length
        self.go_button.setEnabled(len(self.pwd_le.text()) == 8)
