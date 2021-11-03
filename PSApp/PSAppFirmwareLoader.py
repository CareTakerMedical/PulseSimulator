from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PSAppVersion import get_psapp_version
from PSAppSharedFunctions import PSAppExitCodes
from hashlib import md5
from serial.tools.list_ports import comports
from time import sleep
import serial, os, re

XMOS_VID = 0x20B1
XMOS_PID = 0x0401

class PSAppFirmwareLoaderWorker(QObject):
    """ Loader worker; opens the firmware, opens up communication to the microcontroller, programs the FLASH over DFU, and then exits.
    """
    file_open = pyqtSignal()
    cfg_iface_ided = pyqtSignal()
    fsize_calc = pyqtSignal(object)
    fw_mode_begin = pyqtSignal()
    begin_fw_dload = pyqtSignal()
    progress_alert = pyqtSignal(object)
    no_chip_reset = pyqtSignal()
    error = pyqtSignal(object)
    finished = pyqtSignal()
    def __init__(self,file_loc):
        """ Initialization function.
        """
        super(PSAppFirmwareLoaderWorker,self).__init__()
        self.file_loc = file_loc
        self.cfg_iface = None

    def _error(self,msg):
        """ Create a separate function for error reporting, since we'll need to probably also clean out the configuration message buffer.
        """
        for i in range(10):
            ret = self.cfg_iface.readline()
            # Look for error codes
            if (len(ret) > 0):
                rem = re.match(b'^ERR:\s+(\-*\d+)$',ret.rstrip())
                if rem:
                    self.error.emit("DFU aborted with error code: {}".format(rem.group(1)))
                    return
            sleep(0.1)
        self.error.emit(msg)

    def run(self):
        """ Perform the upgrade steps here.
        """
        # As is done with the 'Main' application, we have to identify the configuration interface.
        try:
            for lpi in comports():
                if (lpi.vid == XMOS_VID) and (lpi.pid == XMOS_PID):
                    # Odds are that this is one of our ports; open it and query it.
                    ser = serial.Serial(lpi.name,timeout=0.5)
                    ser.write(b'?')
                    # Now try to match the config interface
                    rem = re.match(b'^Interface:\s+config',ser.readline())
                    if rem:
                        self.cfg_iface = ser
                        self.cfg_iface_found.emit()
                        break
        except:
            pass

        # If at this point, we don't have a serial interface, then we emit an error and return
        if not self.cfg_iface:
            self.error.emit("Could not identify configuration interface.")
            return

        # At this point, the firmware should be waiting for the bytes to write to the flash.  On the
        # application side, we need to open up the firmware file, calculate the length, and send that
        # information over the interface.
        try:
            fsize = os.path.getsize(self.file_loc)
        except:
            try:
                fh = open(self.file_loc,'rb')
                fh.close()
            except:
                self.error.emit("Could not find/open file, {}".format(self.file_loc))
                return
            self.error.emit("Could not calculate file size for file, {}".format(self.file_loc))
            return
        # Check to make sure the file size number makes sense.  At some point, I should come up with
        # a minimum value that makes sense, but in the meantime, I'll just check that it's greater
        # than 0.
        if (fsize <= 0):
            self.error.emit("Calculated file size does not make sense, fsize = {}".format(fsize))
            return
        self.file_open.emit()

        # Once we're to this point, we're going to actually start sending the file one 256 byte chunk
        # at a time.  Every time we send a chunk over, we're going to calculate the checksum and do a
        # handshake between the application and the firmware to ensure that there were no transmission
        # errors.
        try:
            fh = open(self.file_loc,'rb')
            image = fh.read()
            fh.close()
        except:
            self.error.emit("Could not open file {} for image read.".format(self.file_loc))
            return

        # Now that we're here, set up a communication interface.
        match = False
        for i in range(10):
            self.cfg_iface.write(b'F\n')
            ret = self.cfg_iface.readline()
            while (len(ret) == 0):
                self.cfg_iface.write(b'F\n')
                ret = self.cfg_iface.readline()
            rem = re.match(b'^ERR: Busy', ret)
            if rem:
                continue
            if (ret.rstrip() == b'F'):
                self.cfg_iface.write(b'\n')
                match = True
                break
            else:
                self.cfg_iface.write(b'!')
        if not match:
            self.error.emit("Failed handshake, could not enter firmware load mode.")
            return
        self.fw_mode_begin.emit()

        # If I've gotten to this point, I have the file size.  Break this up into four bytes.  It's
        # unlikely, nay, I believe it to be impossible, to have a file size that takes up four bytes,
        # but it's a nice, round number, so that's what we'll do.
        self.cfg_iface.write(fsize.to_bytes(4,'little')+b'\n')
        # Next, we'll get the length back, as an integer, preceded by 'L=' and finished with '\n'
        try:
            for i in range(10):
                ret = self.cfg_iface.readline()
                if (len(ret) > 0):
                    break
                sleep(0.1)
        except:
            self.error.emit("Firmware size calculation failed?")
            return
        self.fsize_calc.emit(fsize)

        # Check the return to see if we got the right value.
        rem = re.match(b'^L=(\d+)$',ret.rstrip())
        if rem is None:
            self._error("Response from firmware to file size calculation was mis-formatted.")
            return

        # If we've gotten to this point, make sure that the size values match
        if (int(rem.group(1)) != fsize):
            self.cfg_iface.write(b'N')
            self._error("File size calculations are different.")
            return

        # Else, send the 'Y' character
        self.cfg_iface.write(b'Y')

        self.begin_fw_dload.emit()
        img_index = 0
        while (img_index < fsize):
            # Bundle up 256 bytes of data and send it off.  If we don't have 256 bytes left, send what
            # we have.
            rlen = fsize - img_index;
            cksum = 0
            if (rlen > 256):
                rlen = 256
            # We'll send the chunk 256 bytes at a time, but before we do, we'll calculate the checksum,
            # which is only a byte wide.
            for i in range(rlen):
                cksum += image[(img_index + i)]
                cksum &= 0x0FF
            cksum ^= 0xFF
            self.cfg_iface.write(image[img_index:(img_index + rlen)])
            # This is where we request the checksum
            try:
                for i in range(10):
                    ret = self.cfg_iface.readline()
                    if (len(ret) > 0):
                        break
                    sleep(0.1)
            except:
                self.error.emit("Request for checksum failed; the current image index = {}".format(img_index))
                return
            if (len(ret) == 0):
                self.error.emit("Request for checksum returned a 0 length string; the current image index = {}".format(img_index))
                return
            rem = re.match(b'^CKSUM=(\d+)$',ret.rstrip())
            if rem is None:
                self._error("Request for checksum returned a mis-formatted string; the current image index = {}, the response was {}".format(img_index,ret.rstrip()))
                return
            # Check the checksum against our version of it
            ret_cksum = int(rem.group(1))
            if (ret_cksum != cksum):
                self.cfg_iface.write(b'N')
                self._error("Checksums did not match!  Index = {}.  Expecting: {}, Received: {}".format(img_index,cksum,ret_cksum))
                return
            self.cfg_iface.write(b'Y')
            img_index += rlen
            self.progress_alert.emit(img_index)

        # Once we're at this point, we're done!  Check to see that we indeed get the 'OK' message from
        # the firmware, then send over 'Q' to reboot the chip.
        for i in range(10):
            ret = self.cfg_iface.readline()
            if (len(ret) > 0):
                break
            sleep(0.1)
        rem = re.match(b'^OK',ret)
        if rem:
            self.cfg_iface.write(b'Q\n')
            for i in range(10):
                ret = self.cfg_iface.readline()
                if (len(ret) > 0):
                    rex = re.match(b'^Q',ret)
                    if rex:
                        self.cfg_iface.write(b'\n')
                        break
                    else:
                        self.cfg_iface.write(b'!')
            # If we get to this point, then the chip didn't reset itself, probably.  Alert the
            # application to this fact.
        else:
            # Maybe an error?  Probably ought to alert the user that something didn't happen quite right.
            # Let's see if we can find an error code.  If not, there's a bug...
            err_code = '???'
            rem = re.match(b'^ERR:\s+(\-*\d+)$',ret.rstrip())
            if rem:
                err_code = rem.group(1)
            self.error.emit("DFU completed with error code: {}".format(err_code))
        self.finished.emit()

class PSAppFirmwareLoaderDialog(QDialog):
    """ A dialog that runs the loading process and informs the user of progress.  It will mainly run a thread that will do the main work and show status.  It should be as simple as a status message.
    """
    def __init__(self,file_loc):
        """ Initialization function.
        """
        super(PSAppFirmwareLoaderDialog,self).__init__()
        self.status = QLabel("Status: Initializing...")
        self.fsize = 0
        self.chip_reset = True
        layout = QHBoxLayout()
        layout.addWidget(self.status)
        self.setLayout(layout)
        self.load_thread = QThread()
        self.load_worker = PSAppFirmwareLoaderWorker(file_loc)
        self.load_worker.moveToThread(self.load_thread)
        self.load_worker.file_open.connect(lambda: self._update_status("Status: Opening firmware file..."))
        self.load_worker.cfg_iface_ided.connect(lambda: self._update_status("Status: Device identified."))
        self.load_worker.fw_mode_begin.connect(lambda: self._update_status("Status: Firmware load mode started."))
        self.load_worker.fsize_calc.connect(self._store_fsize)
        self.load_worker.begin_fw_dload.connect(lambda: self._update_status("Status: Beginning firmware download..."))
        self.load_worker.progress_alert.connect(self._update_progress)
        self.load_worker.no_chip_reset.connect(self._no_chip_reset)
        self.load_worker.error.connect(self._report_error)
        self.load_worker.finished.connect(self._graceful_close)
        self.load_thread.started.connect(self.load_worker.run)
        self.load_thread.start()
        self.show()

    def _graceful_close(self):
        self.load_thread.quit()
        self.load_thread.wait()
        dlg = QMessageBox()
        if (self.chip_reset):
            dlg.setText("Firmware load complete")
        else:
            dlg.setText("Firmware load completed, but chip did not reset.  You must unplug the USB cable and re-plug in order to activate the firmware changes.")
        dlg.setStandardButtons(QMessageBox.Ok)
        dlg.setDefaultButton(QMessageBox.Ok)
        dlg.exec()
        self.accept()

    def _no_chip_reset(self):
        self.chip_reset = False

    def _report_error(self,err):
        """ Report error """
        self.load_thread.quit()
        self.load_thread.wait()
        dlg = QMessageBox()
        dlg.setText(err)
        dlg.setStandardButtons(QMessageBox.Ok)
        dlg.setDefaultButton(QMessageBox.Ok)
        dlg.exec()
        self.reject()

    def _store_fsize(self,val):
        self.fsize = val
        self._update_status("Status: Calculating file size...")

    def _update_progress(self,val):
        self._update_status("Status: Download progress = {:.1f}%".format((val/self.fsize) * 100))

    def _update_status(self,status):
        self.status.setText(status)
        QApplication.processEvents()


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
        # If we're to this point, we'll do the actual programming.  When using JTAG, the process
        # seems to take a long time, so this probably necessitates a separate dialog that
        # can be updated as we go.
        self.go_button.setEnabled(False)
        self.exit_button.setEnabled(False)
        loader_dlg = PSAppFirmwareLoaderDialog(self.ptfwf_le.text())
        loader_dlg.accepted.connect(self._set_self_update)
        loader_dlg.exec()
        self.exit_button.setEnabled(True)
        self._review_status()

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
        try:
            self.parent.exit(ec)
        except:
            pass

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
        if (len(self.pwd_le.text()) == 8):
            self.go_button.setEnabled(True)
            self.go_button.setDefault(True)
            return
        self.go_button.setEnabled(False)

    def _set_self_update(self):
        self.update_complete = True

