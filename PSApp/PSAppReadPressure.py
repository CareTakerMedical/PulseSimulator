from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from time import sleep
import re
from PSAppSharedFunctions import convert_mpsi_to_mmhg

class PSAppReadPressureWorker(QObject):
    """ Class that actually does the work for updating the pressure readout text.
    """
    new_reading = pyqtSignal(object)
    reading_error = pyqtSignal()
    comm_error = pyqtSignal()
    finished = pyqtSignal()
    def __init__(self,comm_interface,data_iface):
        super(PSAppReadPressureWorker,self).__init__()
        self.comm_interface = comm_interface
        self.data_iface = data_iface
        self.data_iface["ser"].timeout = 1
        self.is_running = False

    def run(self):
        self.is_running = True
        while (self.is_running):
            success = False
            try:
                cmd_result = self.comm_interface.transaction(b'R',True).rstrip()
                rem = re.match(b'^OK',cmd_result)
                success = True if rem else False
            except:
                self.comm_error.emit()
                success = False
            if success:
                try:
                    res = self.data_iface["ser"].readline()
                    rem = re.match(b'^R,\d+,\d+,(\d+)',res.rstrip())
                    if rem:
                        iret = int(rem.group(1))
                        if (iret > 0):
                        # Must convert mPSI to mmHg
                            self.new_reading.emit(convert_mpsi_to_mmhg(iret))
                    else:
                        self.reading_error.emit()
                except:
                    self.comm_error.emit()
                    self.is_running = False
            else:
                self.reading_error.emit()
            sleep(0.1)
        self.finished.emit()

    def stop(self):
        self.is_running = False

class PSAppReadPressureDialog(QDialog):
    """ Dialog that pops up when we're either just reading the output of the pressure sensor, or priming the system.
    """
    comm_issue = pyqtSignal()
    def __init__(self,comm_interface,data_iface,pmin,pmax):
        """ Initialization function; provide a serial device to read from/write to
        """
        super(PSAppReadPressureDialog,self).__init__()
        self.pmin = pmin
        self.pmax = pmax
        
        # They'll be two buttons:  'Prime' and 'Cancel'.  'Prime' will emit 'accepted' and 'Cancel'
        # will emit 'rejected'.
        self.prime_button = QPushButton("Prime")
        self.prime_button.clicked.connect(self._prime_button_clicked)
        self.prime_button.setEnabled(False)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self._cancel_button_clicked)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.prime_button)
        button_layout.addWidget(cancel_button)
        button_widget = QWidget()
        button_widget.setLayout(button_layout)

        # Create the widget that will display the current pressure.  Make the text nice and big
        self.current_pressure = QLabel("Wait...")
        self.current_pressure.setStyleSheet("font: 24pt;")

        # Lay it all out
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Current pressure reading (mmHg):"))
        layout.addWidget(self.current_pressure)
        layout.addWidget(button_widget)
        self.setLayout(layout)

        # Set up a thread to do the work of communicating the current pressure back and
        # forth.
        self.thread = QThread()
        self.worker = PSAppReadPressureWorker(comm_interface,data_iface)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.new_reading.connect(self._update_pressure_reading)
        self.worker.reading_error.connect(self._indicate_read_error)
        self.worker.comm_error.connect(self._indicate_comm_error)
        self.thread.start()

        # Collect the readings in an array.  We'll read them as fast as we can, but given the
        # general lack of resolution that we get from the sensor, we'll get more accurate
        # readings if we average a bit.
        self.press_readings = list()
        self.timer = QTimer()
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._calc_and_update_press)

    def _calc_and_update_press(self):
        """ Every time the timer goes off, we'll take the number of readings that occurred during the 200ms period and average them together.
        """
        while "ERR" in self.press_readings:
            self.press_readings.remove("ERR")
        if (len(self.press_readings) >= 2):
            press_display = sum(self.press_readings) / len(self.press_readings)
            self.current_pressure.setText("{:.1f}".format(press_display))
            if ((press_display < self.pmin) or (press_display > self.pmax)):
                self.prime_button.setEnabled(False)
                if (press_display < self.pmin):
                    self.current_pressure.setStyleSheet("font-size: 24pt; color: blue; font-style: italic")
                else:
                    if (press_display > 250):
                        # We're really out of range...
                        self.current_pressure.setText("RANGE!")
                        self.current_pressure.setStyleSheet("font-size: 16pt; color: black; font-style: italic")
                    else:
                        self.current_pressure.setStyleSheet("font-size: 24pt; color: red; font-style: italic")
            else:
                self.current_pressure.setStyleSheet("font-size: 24pt; color: black; font-style: normal")
                self.prime_button.setEnabled(True)
        else:
            self.current_pressure.setText("ERR")
            self.prime_button.setEnabled(False)
        QApplication.processEvents()
        self.press_readings = list()

    def _cancel_button_clicked(self):
        """ Stop the thread before exiting.
        """
        self.current_pressure.setStyleSheet("font-size: 12pt; color: black; font-style: normal")
        self.current_pressure.setText("Priming canceled! Closing...")
        QApplication.processEvents()
        try:
            self.timer.stop()
        except:
            self.timer = None
        self.worker.finished.connect(lambda: self._wait_for_thread_exit(False))
        self.worker.stop()

    def _indicate_comm_error(self):
        """ Communication has dropped, send out 'comm_issue' signal, followed by 'rejected' signal.
        """
        self.worker.stop()
        self.thread.quit()
        self.thread.wait()
        self.comm_issue.emit()
        self.reject()

    def _indicate_read_error(self):
        """ We didn't get a pressure number that makes sense, change the text to 'ERR'.
        """
        self.press_readings.append("ERR")

    def _prime_button_clicked(self):
        """ When the prime button is clicked, we'll send out the 'accepted' signal, but first we need to stop the thread.
        """
        self.current_pressure.setStyleSheet("font-size: 12pt; color: black; font-style: normal")
        self.current_pressure.setText("Primed! Closing...")
        QApplication.processEvents()
        try:
            self.timer.stop()
        except:
            self.timer = None
        self.worker.finished.connect(lambda: self._wait_for_thread_exit(True))
        self.worker.stop()

    def _update_pressure_reading(self,val):
        """ Add the value to the press_readings.  Start up the timer if it hasn't been started yet.
        """
        self.press_readings.append(val)
        if not(self.timer.isActive()):
            self.timer.start()

    def _wait_for_thread_exit(self,accept):
        """ Try to do a proper thread shutdown.
        """
        self.thread.quit()
        self.thread.wait()
        if accept:
            self.accept()
        else:
            self.reject()

