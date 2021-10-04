from PyQt5.QtCore import * 
from PyQt5.QtGui import * 
from PyQt5.QtWidgets import * 
from serial.tools.list_ports import comports
import serial
import re

XMOS_VID = 0x20B1
XMOS_PID = 0x0401

class PSAppFindInterfaces(QObject):
    """ Thread for finding the configuration and data interfaces.
    """
    cfg_iface_found = pyqtSignal(object)
    data_iface_found = pyqtSignal(object)
    parsing_finished = pyqtSignal()
    def __init__(self):
        super(PSAppFindInterfaces,self).__init__()

    def run(self):
        # Look for comports with the XMOS VID/PID
        try:
            for lpi in comports():
                if (lpi.vid == XMOS_VID) and (lpi.pid == XMOS_PID):
                    # Odds are that this is one of our ports; open it and query it.
                    ser = serial.Serial(lpi.name,timeout=0.5)
                    ser.write(b'?')
                    # Now try to match the correct interface
                    rem = re.match(b'^Interface:\s+(config|data)',ser.readline())
                    if rem:
                        if (rem.group(1) == b'config'):
                            self.cfg_iface_found.emit({"ser":ser, "lpi":lpi})
                        if (rem.group(1) == b'data'):
                            self.data_iface_found.emit({"ser":ser, "lpi":lpi})
        except:
             pass
        self.parsing_finished.emit()

class PSAppConnectionManager(QDialog):
    """ Class for creating a dialog used to connect to a firmware instance (i.e. XMOS).
    """
    # Custom signals for informing the main app of connections and connection status.
    config_iface_signal = pyqtSignal(object)
    data_iface_signal = pyqtSignal(object)
    def __init__(self,parent=None):
        """ Initialization function.
        """
        super(PSAppConnectionManager,self).__init__()

        # Going to try to first show a message box saying that we're looking at the COM ports and
        # trying to connect to them, in case something goes wrong and we're hanging
        self.setWindowTitle("Communication Manager")
        self.message = QLabel("Looking for Pulse Simulator hardware...")

        # Buttons to do stuff; 'Refresh' will try to connect again, 'Continue' will close the dialog
        # and send the 'accept' signal, 'Quit' will close the dialog and send the 'reject' signal
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_clicked)
        self.refresh_button.setEnabled(False)
        self.continue_button = QPushButton("Continue")
        self.continue_button.clicked.connect(self._accept)
        self.continue_button.setEnabled(False)
        self.quit_button = QPushButton("Quit")
        self.quit_button.clicked.connect(self._reject)
        # Put the buttons in a layout of its own
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.continue_button)
        button_layout.addWidget(self.quit_button)
        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.message)
        layout.addWidget(button_widget)
        self.setLayout(layout)

        # Interfaces we're looking for
        self.cfg_iface = None;
        self.data_iface = None;

        # Show the box, and then launch a thread and worker to try to get everything identified
        self._launch_thread()

    def _accept(self):
        """ Gotta shutdown the thread before we go.
        """
        self.thread.quit()
        self.thread.wait()
        self.accept()

    def _cfg_iface_found(self,ser_obj):
        """ Pass both the serial connection and the port object so that we can do periodic checking as to whether or not the port is still there; it'll get sent over as a dict.
        """
        self.cfg_iface = ser_obj
        self.config_iface_signal.emit(self.cfg_iface)

    def _check_connect_status(self):
        """ See if we have all of the interfaces that we need.  Alert the user either way.
        """
        self.quit_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        if (self.cfg_iface is None) or (self.data_iface is None):
            msg = "Error: cannot find the following interfaces:\n"
            if self.cfg_iface is None:
                msg += "   Configuration Interface\n"
            if self.data_iface is None:
                msg += "   Data Interface\n"
            self.message.setText(msg)
            return
        self.message.setText("Interfaces successfully identified.")
        self.continue_button.setEnabled(True)
        self.continue_button.setDefault(True)
        self.refresh_button.setEnabled(False)

    def _data_iface_found(self,ser_obj):
        """ Pass both the serial connection and the port object so that we can do periodic checking as to whether or not the port is still there; it'll get sent over as a dict.
        """
        self.data_iface = ser_obj
        self.data_iface_signal.emit(self.data_iface)

    def _launch_thread(self):
        """ Launch the thread and check for presence.
        """
        self.quit_button.setEnabled(False)
        self.thread = QThread()
        self.worker = PSAppFindInterfaces()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.cfg_iface_found.connect(self._cfg_iface_found)
        self.worker.data_iface_found.connect(self._data_iface_found)
        self.worker.parsing_finished.connect(self._check_connect_status)
        self.thread.start()

    def _refresh_clicked(self):
        """ Try launching the thread again.
        """
        self.refresh_button.setEnabled(False)
        self.thread.quit()
        self.thread.wait()
        self.message.setText("Looking for Pulse Simulator hardware...")
        self._launch_thread()

    def _reject(self):
        """ Gotta shutdown the thread before we go.
        """
        self.thread.quit()
        self.thread.wait()
        self.reject()

