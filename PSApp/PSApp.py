import pyqtgraph as pg
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PSAppState import *
from PSAppVersion import get_psapp_version
from PSAppDefaults import *
from PSAppConnect import PSAppConnectionManager
from PSAppReadPressure import PSAppReadPressureDialog
from PSAppCalibrate import PSAppCalibrationWorker
from PSAppPlayback import PSAppPulsePlaybackWorker
from PSAppCommInterface import PSAppCommInterface
from serial.tools.list_ports import comports
from time import sleep
import re

class MagicLabel(QLabel):
    """ When this label is double-clicked, it emits a signal letting us know...
    """
    double_clicked = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

class StateAssociatedLineEdit(QLineEdit):
    """ Associate a state variable with the line edit.
    """
    def __init__(self,ps_state,var):
        super(StateAssociatedLineEdit,self).__init__(str(ps_state.get_state(var)))
        self.var = var
        self.valid = True

    def get_valid(self):
        return self.valid

    def get_var(self):
        return self.var

    def set_valid(self,val):
        self.valid = val

class RangeIntLineEdit(QLineEdit):
    """ Set a range on a line edit, and restrict to integers.
    """
    legal_value = pyqtSignal()
    illegal_value = pyqtSignal()
    def __init__(self,val=1,minimum=0,maximum=1e6):
        """ Initialization function.
        """
        # Before doing anything, check to make sure that the values are integers
        for x in [val,minimum,maximum]:
            if not(isinstance(x,int)):
                raise ValueError("Supplied value '{}' is not an integer".format(x))
        # Once we're here, check to make sure that the values make some sense.
        if (maximum < minimum):
            raise ValueError("Maximum {} is less than minimum {}.".format(maximum,minimum))
        if (val > maximum):
            raise ValueError("Value {} is greater than maximum {}.".format(val,maximum))
        if (val < minimum):
            raise ValueError("Value {} is less than minimum {}.".format(val,minimum))
        super(RangeIntLineEdit,self).__init__(str(val))
        self.textChanged.connect(self._check_input)
        self.valid = True
        self.minimum = minimum
        self.maximum = maximum

    def get_valid(self):
        return self.valid

    def _check_input(self,text):
        """ Make sure entered value makes sense; if it doesn't, send out the signal 'illegal_value' and change the text to bold and red.
        """
        try:
            ival = int(text)
            if ((ival < self.minimum) or (ival > self.maximum)):
                self.setStyleSheet("color: red; font-weight: bold")
                self.valid = False
                self.illegal_value.emit()
            else:
                self.setStyleSheet("color: black; font-weight: normal")
                self.valid = True
                self.legal_value.emit()
        except Exception as e:
            self.setStyleSheet("color: red; font-weight: bold")
            self.valid = False
            self.illegal_value.emit()

class FileOpenLineEdit(QLineEdit):
    """ Special class for check for existence of a file.
    """
    legal_value = pyqtSignal()
    illegal_value = pyqtSignal()
    def __init__(self,text):
        """ Initialization function.
        """
        super(FileOpenLineEdit,self).__init__(text)
        self.valid = True
        self.textChanged.connect(self._check_file_exists)
        self._check_file_exists()

    def get_valid(self):
        return self.valid

    def _check_file_exists(self):
        try:
            fh = open(self.text(),'r')
            fh.close()
            self.setStyleSheet("font-weight: normal")
            self.valid = True
            self.legal_value.emit()
        except:
            x.setStyleSheet("font-weight: bold")
            self.valid = False
            self.illegal_value.emit()

class PSAppCheckConnectionStatus(QObject):
    """ Thread that gets kicked off once we've made a connection to check that the device is still connected to the system.
    """
    disconnected = pyqtSignal()
    def __init__(self,lpi_objs):
        """ Update:  There are two COM ports, so make sure we have both connected.
        """
        super(PSAppCheckConnectionStatus,self).__init__()
        self.lpi_objs = lpi_objs
        self.is_running = False

    def run(self):
        self.is_running = True
        while (self.is_running):
            sleep(0.2)
            found_lpi_objs = [False,False]
            i = 0
            for lpi_obj in self.lpi_objs:
                for cd in comports():
                    if (cd == lpi_obj):
                        found_lpi_objs[i] = True
                        break
                i += 1
            if False in found_lpi_objs:
                self.is_running = False
                self.disconnected.emit()

    def stop(self):
        self.is_running = False

class PSAppMainWindow(QMainWindow):
    """ Class for creating the main window that will be visible by the user.
    """
    def __init__(self,parent=None):
        """ Initialization function.
        """
        super(PSAppMainWindow,self).__init__()
        self.setWindowTitle("Pulse Simulator")
        # 'State' object will manage communication channel and other state information between the GUI
        # and the hardware (i.e., XMOS)
        self.ps_state = PSAppState()
        self.timestamp = None
        self.calibration_attempts = 0
        self.max_calibration_attempts = 3

        # Create central widget
        cwidget = QWidget()

        # Create the tab widget that will get placed inside the central widget
        self.twidget = QTabWidget()

        # Create 'interact' widget
        #
        # Start with a box that contains the four buttons that will be used to control activity
        top_button_box = QFrame()
        top_button_box.setLineWidth(1)
        top_button_box.setFrameShape(QFrame.Box)

        # Create the various buttons that go inside the frame
        self.send_home_button = QPushButton("Send Home")
        self.send_home_button.clicked.connect(self._send_home_clicked)
        self.send_home_button.setToolTip("Click this button to send the stepper motor back to its home position.")
        self.read_pressure_button = QPushButton("Read/Prime Pressure")
        self.read_pressure_button.clicked.connect(self._start_read_pressure)
        self.read_pressure_button.setToolTip("Click this button to bring up a dialog allowing you to read the output of the pressure sensor.")
        self.run_cal_button = QPushButton("Run Calibration")
        self.run_cal_button.clicked.connect(self._first_cal_procedure)
        self.run_cal_button.setToolTip("Click this button to run a calibration procedure; the calibration procedure must be performed before a simulation is executed.")

        # Place the elements within the frame.
        top_button_layout = QHBoxLayout()
        top_button_layout.addWidget(self.send_home_button)
        top_button_layout.addWidget(self.read_pressure_button)
        top_button_layout.addWidget(self.run_cal_button)
        top_button_box.setLayout(top_button_layout)

        # Create another frame for waveform parameters
        param_box = QFrame()
        param_box.setLineWidth(1)
        param_box.setFrameShape(QFrame.Box)
        
        # Create the labels and line edits for waveform parameters
        systolic_label = QLabel("Systolic:")
        diastolic_label = QLabel("Diastolic:")
        heart_rate_label = QLabel("Heart Rate:")
        respiration_rate_label = QLabel("Respiration Rate:")
        self.systolic_le = StateAssociatedLineEdit(self.ps_state,"systolic")
        self.systolic_le.textChanged.connect(lambda x: self._eval_param_entry(self.systolic_le))
        self.diastolic_le = StateAssociatedLineEdit(self.ps_state,"diastolic")
        self.diastolic_le.textChanged.connect(lambda x: self._eval_param_entry(self.diastolic_le))
        self.heart_rate_le = StateAssociatedLineEdit(self.ps_state,"heart_rate")
        self.heart_rate_le.textChanged.connect(lambda x: self._eval_param_entry(self.heart_rate_le))
        self.respiration_rate_le = StateAssociatedLineEdit(self.ps_state,"respiration_rate")
        self.respiration_rate_le.textChanged.connect(lambda x: self._eval_param_entry(self.respiration_rate_le))

        # Create a layout for the waveform parameters
        param_layout = QGridLayout()
        param_layout.addWidget(systolic_label,0,0,1,2)
        param_layout.addWidget(self.systolic_le,0,2,1,1)
        param_layout.addWidget(heart_rate_label,0,3,1,2)
        param_layout.addWidget(self.heart_rate_le,0,5,1,1)
        param_layout.addWidget(diastolic_label,1,0,1,2)
        param_layout.addWidget(self.diastolic_le,1,2,1,1)
        param_layout.addWidget(respiration_rate_label,1,3,1,2)
        param_layout.addWidget(self.respiration_rate_le,1,5,1,1)
        param_box.setLayout(param_layout)

        # Create a frame to place mode and control buttons
        mode_control_box = QFrame()
        mode_control_box.setLineWidth(1)
        mode_control_box.setFrameShape(QFrame.Box)

        # Create buttons/slider for choosing waveform type, play/stop, and refresh.  Also include some
        # status text.
        toggle_left_text = QLabel("Pulse Table")
        toggle_right_text = QLabel("Waveform")
        self.play_type_toggle = QSlider(Qt.Horizontal)
        # Create a tight layout
        toggle_widget = QWidget()
        toggle_layout = QHBoxLayout()
        toggle_layout.addWidget(toggle_left_text)
        toggle_layout.addWidget(self.play_type_toggle)
        toggle_layout.addWidget(toggle_right_text)
        toggle_widget.setLayout(toggle_layout)
        self.play_type_toggle.setRange(0,1)
        self.play_type_toggle.setTickInterval(1)
        self.play_type_toggle.setValue(int(self.ps_state.get_state("play_mode")))
        self.play_type_toggle.valueChanged.connect(self._set_widget_status)
        toggle_left_text.mousePressEvent = lambda x: self.play_type_toggle.setValue(0)
        toggle_right_text.mousePressEvent = lambda x: self.play_type_toggle.setValue(1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._eval_refresh)
        self.refresh_button.setEnabled(False)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self._eval_play_stop)
        self.play_button.setEnabled(False)

        # Create a layout for the widgets
        mc_layout = QHBoxLayout()
        mc_layout.addWidget(toggle_widget)
        mc_layout.addWidget(self.refresh_button)
        mc_layout.addWidget(self.play_button)
        mode_control_box.setLayout(mc_layout)

        # Create a frame for the status text
        st_box = QFrame()
        st_box.setLineWidth(1)
        st_box.setFrameShape(QFrame.Box)
        self.wf_status = QLabel("Status: Idle")
        st_layout = QHBoxLayout()
        st_layout.addWidget(self.wf_status)
        st_box.setLayout(st_layout)

        # Create a frame to place the graphing object in to
        plot_box = QFrame()
        plot_box.setLineWidth(1)
        plot_box.setFrameShape(QFrame.Box)

        # For the time-being, just place a grid.  Place fake points off of said grid for now.
        self._initialize_plot()

        plot_layout = QHBoxLayout()
        plot_layout.addWidget(self.plt)
        plot_box.setLayout(plot_layout)

        # Now stack all of the various frames on top of each other
        interact_tab_layout = QVBoxLayout()
        interact_tab_layout.addWidget(top_button_box)
        interact_tab_layout.addWidget(param_box)
        interact_tab_layout.addWidget(mode_control_box)
        interact_tab_layout.addWidget(st_box)
        interact_tab_layout.addWidget(plot_box)
        interact_tab_widget = QWidget()
        interact_tab_widget.setLayout(interact_tab_layout)

        # And now place the 'Interact' widget within the tab widget
        self.twidget.addTab(interact_tab_widget,"Interact")

        # Create 'config' widget
        #
        # Home Position
        home_pos_label = QLabel("Home Position:")
        home_pos_label.setToolTip("Set the home position of the stepper motor.")
        self.home_pos_le = RangeIntLineEdit(1000,minimum=100,maximum=5000)
        self.home_pos_le.illegal_value.connect(lambda: self.twidget.setTabEnabled(0,False))
        self.home_pos_le.legal_value.connect(self._check_config_tab)
        home_pos_limits_label = QLabel("Limits: Min=100, Max=5000")
        home_pos_layout = QHBoxLayout()
        home_pos_layout.addWidget(home_pos_label)
        home_pos_layout.addWidget(self.home_pos_le)
        home_pos_layout.addWidget(home_pos_limits_label)
        hp_widget = QWidget()
        hp_widget.setLayout(home_pos_layout)
        #
        # Calibrated 'maximum' position
        cal_max_label = QLabel("Calibrated Max Position:")
        cal_max_label.setToolTip("Set the maximum position of the stepper motor.")
        self.cal_max_le = RangeIntLineEdit(2000,minimum=200,maximum=6000)
        self.cal_max_le.illegal_value.connect(lambda: self.twidget.setTabEnabled(0,False))
        self.cal_max_le.legal_value.connect(self._check_config_tab)
        cal_max_limits_label = QLabel("Limits: Min=200, Max=6000")
        cal_max_layout = QHBoxLayout()
        cal_max_layout.addWidget(cal_max_label)
        cal_max_layout.addWidget(self.cal_max_le)
        cal_max_layout.addWidget(cal_max_limits_label)
        cm_widget = QWidget()
        cm_widget.setLayout(cal_max_layout)
        #
        # Calibration increments
        cal_inc_label = QLabel("Calibration Increments:")
        cal_inc_label.setToolTip("Increments between home and calibrated max position.")
        self.cal_inc_le = RangeIntLineEdit(25,minimum=1,maximum=500)
        self.cal_inc_le.illegal_value.connect(lambda: self.twidget.setTabEnabled(0,False))
        self.cal_inc_le.legal_value.connect(self._check_config_tab)
        cal_inc_limits = QLabel("Limits: Min=1, Max=500")
        cal_inc_layout = QHBoxLayout()
        cal_inc_layout.addWidget(cal_inc_label)
        cal_inc_layout.addWidget(self.cal_inc_le)
        cal_inc_layout.addWidget(cal_inc_limits)
        ci_widget = QWidget()
        ci_widget.setLayout(cal_inc_layout)
        #
        # 'Primed' region
        prime_min_label = QLabel("Prime Minimum:")
        prime_min_label.setToolTip("If the 'primed' pressure region is below this number, say that priming is invalid.")
        self.prime_min_le = RangeIntLineEdit(50,minimum=25,maximum=75)
        self.prime_min_le.illegal_value.connect(lambda: self.twidget.setTabEnabled(0,False))
        self.prime_min_le.legal_value.connect(self._check_config_tab)
        prime_max_label = QLabel("Prime Maximum:")
        prime_max_label.setToolTip("If the 'primed' pressure region is above this number, say that priming is invalid.")
        self.prime_max_le = RangeIntLineEdit(60,minimum=25,maximum=75)
        self.prime_max_le.illegal_value.connect(lambda: self.twidget.setTabEnabled(0,False))
        self.prime_max_le.legal_value.connect(self._check_config_tab)
        prime_layout = QHBoxLayout()
        prime_layout.addWidget(prime_min_label)
        prime_layout.addWidget(self.prime_min_le)
        prime_layout.addWidget(prime_max_label)
        prime_layout.addWidget(self.prime_max_le)
        prime_widget = QWidget()
        prime_widget.setLayout(prime_layout)
        #
        # Pulse Table Data File
        pt_label = QLabel("Pulse Table File:")
        self.pt_le = FileOpenLineEdit(get_default_pulse_table_path())
        self.pt_le.illegal_value.connect(lambda: self.twidget.setTabEnabled(0,False))
        self.pt_le.legal_value.connect(self._check_config_tab)
        self.pt_browse_button = QPushButton("Browse")
        self.pt_browse_button.clicked.connect(lambda x: self._browse_for_file(self.pt_le))
        pt_layout = QHBoxLayout()
        pt_layout.addWidget(pt_label)
        pt_layout.addWidget(self.pt_le)
        pt_layout.addWidget(self.pt_browse_button)
        pt_widget = QWidget()
        pt_widget.setLayout(pt_layout)
        #
        # Waveform Data File
        wf_label = QLabel("Waveform Data File:")
        self.wf_le = FileOpenLineEdit(get_default_waveform_path())
        self.wf_le.illegal_value.connect(lambda: self.twidget.setTabEnabled(0,False))
        self.wf_le.legal_value.connect(self._check_config_tab)
        self.wf_browse_button = QPushButton("Browse")
        self.wf_browse_button.clicked.connect(lambda x: self._browse_for_file(self.wf_le))
        wf_layout = QHBoxLayout()
        wf_layout.addWidget(wf_label)
        wf_layout.addWidget(self.wf_le)
        wf_layout.addWidget(self.wf_browse_button)
        wf_widget = QWidget()
        wf_widget.setLayout(wf_layout)
        #
        # Apply changes/Set defaults button
        defaults_button = QPushButton("Defaults")
        defaults_button.clicked.connect(self._set_default_values)
        #
        # Final Layout
        cfg_widget = QWidget()
        cfg_layout = QVBoxLayout()
        cfg_layout.addWidget(hp_widget)
        cfg_layout.addWidget(cm_widget)
        cfg_layout.addWidget(ci_widget)
        cfg_layout.addWidget(prime_widget)
        cfg_layout.addWidget(pt_widget)
        cfg_layout.addWidget(wf_widget)
        cfg_layout.addWidget(defaults_button)
        cfg_widget.setLayout(cfg_layout)

        # And add the tab
        self.twidget.addTab(cfg_widget,"Config")

        # Create 'about' widget; just some labels with our own software version, and then some contact
        # information.
        self.about_widget = QWidget()
        self.about_layout = QVBoxLayout()
        self.app_version_label = MagicLabel("Pulse Simulator App Version: {}".format(get_psapp_version()))
        self.app_version_label.double_clicked.connect(self._add_manual_buttons)
        # Magic buttons that don't appear until 'conjured'
        self.move_near = QPushButton("Near")
        self.move_near.setAutoRepeat(True)
        self.move_near.setAutoRepeatDelay(500)
        self.move_near.setAutoRepeatInterval(250)
        self.move_near.clicked.connect(lambda: self._increment(-10))
        self.move_far = QPushButton("Far")
        self.move_far.setAutoRepeat(True)
        self.move_far.setAutoRepeatDelay(500)
        self.move_far.setAutoRepeatInterval(250)
        self.move_far.clicked.connect(lambda: self._increment(10))
        self.about_layout.addWidget(self.app_version_label)
        self.about_layout.addWidget(QLabel("For issues, contact Jake Wegman (jake@caretakermedical.net)"))
        self.about_widget.setLayout(self.about_layout)

        # And add the tab
        self.twidget.addTab(self.about_widget,"About")

        # Create connect state box
        cs_box = QFrame()
        cs_box.setLineWidth(1)
        cs_box.setFrameShape(QFrame.Box)

        # Create connect widget
        self.cs_label = QLabel("Connection status: Not connected")
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self._launch_connect)
        # Also probably want an exit button
        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.close)
        connect_layout = QHBoxLayout()
        connect_layout.addWidget(self.cs_label)
        connect_layout.addWidget(self.connect_button)
        connect_layout.addWidget(exit_button)
        cs_box.setLayout(connect_layout)

        # Add the tab widget and the 'connect state' widget to a central widget
        layout = QVBoxLayout()
        layout.addWidget(self.twidget)
        layout.addWidget(cs_box)
        cwidget.setLayout(layout)
        self.setCentralWidget(cwidget)

        self.show()

        # Interfaces
        self.cfg_iface = None
        self.data_iface = None
        self.comm_interface = None

        # Launch the connection dialog
        self._launch_connect()

    def _add_manual_buttons(self):
        """ Add buttons for incrementing/decrementing system manually, i.e. a kind of manual override.
        """
        # The first thing to do is to make sure this function doesn't get called again.
        self.app_version_label.double_clicked.disconnect()
        # Create a layout for the buttons, and then add that layout to the current layout.
        nf_widget = QWidget()
        nf_layout = QHBoxLayout()
        nf_layout.addWidget(self.move_near)
        nf_layout.addWidget(self.move_far)
        nf_widget.setLayout(nf_layout)
        self.about_layout.addWidget(nf_widget)

    def _bad_message_format_alert(self):
        """ Data that came back from the microcontroller was not formatted as expected.
        """
        warn_dlg = QMessageBox()
        warn_dlg.setText("The returned data was in an unknown format.")
        warn_dlg.exec()
        self._eval_play_stop()

    def _browse_for_file(self,line_edit):
        """ Bring up file browser for searching for files on file system.
        """
        fdialog = QFileDialog()
        fdialog.setDefaultSuffix(".dat")
        fdialog.setFileMode(QFileDialog.ExistingFile)
        fdialog.setAcceptMode(QFileDialog.AcceptOpen)
        fdialog.setDirectory(get_default_res_path())
        if fdialog.exec_():
            line_edit.setText(fdialog.selectedFiles()[0])

    def _check_config_tab(self):
        """ Go through the line edits and check that they all have valid states.  Also, check that the files supplied exist.
        """
        for x in [self.home_pos_le,self.cal_max_le,self.cal_inc_le,self.pt_le,self.wf_le,self.prime_min_le,self.prime_max_le]:
            if not(x.get_valid()):
                self.twidget.setTabEnabled(0,False)
                return
        # Furthermore, 'prime_min' must be less than 'prime_max'
        if not(int(self.prime_min_le.text()) < int(self.prime_max_le.text())):
            self.twidget.setTabEnabled(0,False)
            return
        self.twidget.setTabEnabled(0,True)

    def _clear_plot(self):
        """ Get rid of any data that might be plotted at the moment.  Also set up for plotting pressures.
        """
        self.plt.setLabel('bottom','Relative Time',units='s')
        self.plt.setXRange(0,10)
        self.plt.setYRange(0,250)
        self.plot_x = []
        self.plot_y = []
        self.plot.setData(self.plot_x,self.plot_y)
        QApplication.processEvents()

    def _confirm_pulse_table_end(self):
        """ Confirm that the pulse table thread has ended successfully.
        """
        self.pulse_thread.quit()
        self.pulse_thread.wait()
        self.wf_status.setText("Status: Playback ended.")

    def _data_load_complete(self):
        self.pulse_loading_mb.close()
        self.wf_status.setText("Status:  Playback of pulse table.")
        QApplication.processEvents()

    def _data_read_fail_alert(self):
        """ Probably a timeout from the data readback procedure.
        """
        warn_dlg = QMessageBox()
        warn_dlg.setText("Readback of data from the platform failed.")
        warn_dlg.exec()
        self._eval_play_stop()

    def _disable_buttons(self):
        """ During operations, lock out the user.
        """
        for button in [ self.send_home_button,
                        self.read_pressure_button,
                        self.run_cal_button,
                        self.refresh_button,
                        self.play_button ]:
            button.setEnabled(False)

    def _end_cal_procedure(self):
        """ Once we're finished, change statuses and store the calibration values away.
        """
        # Before we go populating the pressure table, we probably ought to make sure that
        # the numbers that were reported make sense.  As I've thought about this, I think
        # the only check that really needs to be performed as that the pressure always
        # goes up as the motor progresses.  If a number is reported that is wildly too
        # high, then the next datapoint, assuming it was a one-off data error, will fall
        # back on the (roughly) straight line, and subtracting the previous point from the
        # 'next' point will result in a negative number, meaning that we have an error.
        # Essentially the same thing is true if we have a pressure reading of '0' or
        # something else that is erroneously low; subtracting the 'correct' previous
        # value from the incorrect current value will result in a negative result.
        # Therefore, once the error is detected, we can just try the process again.
        # I'll put a message in the 'status' text box and then re-start the process.
        if (self._eval_cal_results):
            self.calibration_attempts = 0
            self.ps_state.populate_pressure_table(x=self.plot_x,y=self.plot_y)
            self.ps_state.set_state("calibrated",True)
            self.wf_status.setText("Status: Idle")
            QApplication.processEvents()
            self.cal_thread.quit()
            self.cal_thread.wait()
            self._set_widget_status()
        else:
            # There was an error.  Wait for the original cal thread to terminate, and then
            # restart it.
            self.calibration_attempts += 1
            if (self.calibration_attempts < self.max_calibration_attempts):
                self.wf_status.setText("Status: Calibration procedure failed, trying again, attempt number {}".format(self.calibration_attempts + 1))
                QApplication.processEvents()
                self.cal_thread.quit()
                self.cal_thread.wait()
                self.cal_worker = None
                self.cal_thread = None
                self._start_cal_procedure()
            else:
                self.calibration_attempts = 0
                self.wf_status.setText("Status: Calibration procedure failed.")
                # Pop up a warning window saying we failed 
                warn_dlg = QMessageBox()
                warn_dlg.setText("Could not perform calibration successfully after {} attempts.  Please check all pneumatic hoses and connections for issues.".format(self.max_calibration_attempts))
                warn_dlg.exec()

    def _eval_cal_results(self):
        """ Check to make sure the points make sense.
        """
        for i in range(1,len(self.plot_y)):
            if ((self.plot_y[i] - self.plot_y[(i - 1)]) <= 0):
                return False
        return True

    def _eval_param_entry(self,le):
        """ For the particular LineEdit that changed, see that the value makes sense.
        """
        enable_refresh = True
        state_var = le.get_var()
        # First, make sure the inputted value is a number
        try:
            fval = float(le.text())
            le.setStyleSheet("color: black")
            le.set_valid(True)
            # If this worked, see if it's different than the stored number
            old_fval = float(self.ps_state.get_state(state_var))
            if (fval != old_fval):
                le.setStyleSheet("font-weight: bold")
                le.set_valid(False)
            else:
                le.setStyleSheet("font-weight: normal")
                enable_refresh = False
            # Need to make sure systolic is greater than diastolic
            if (state_var == "systolic"):
                dval = float(self.diastolic_le.text())
                if (fval <= dval):
                    le.setStyleSheet("font-weight: bold; color: red")
                    enable_refresh = False
                    le.set_valid(False)
            if (state_var == "diastolic"):
                sval = float(self.systolic_le.text())
                if (fval >= sval):
                    le.setStyleSheet("font-weight: bold; color: red")
                    enable_refresh = False
                    le.set_valid(False)
        except:
            le.setStyleSheet("color: red; font-weight: bold")
            enable_refresh = False
            le.set_valid(False)
        self.refresh_button.setEnabled(enable_refresh)
        self._set_widget_status()

    def _eval_play_stop(self):
        """ Look at the various options chosen, and branch off from there on either playing a waveform or a pulse table
        """
        # First, if we're playing, then we stop; if we're stopped, then we start playing
        if self.ps_state.get_state("playing"):
            self.play_button.setText("Play")
            self.ps_state.set_state("playing",False)
            if (self.ps_state.get_state("play_mode") == PlayMode.PULSE_TABLE):
                self.pulse_worker.stop_playback()
                self.wf_status.setText("Status:  Idle")
                QApplication.processEvents()
            else:
                pass
                #self.wf_worker.stop_playback()
        else:
            # In either case, make sure ps_state is properly updated
            self.play_button.setText("Stop")
            self.ps_state.set_state("playing",True)
            self.ps_state.set_state("systolic",int(self.systolic_le.text()))
            self.ps_state.set_state("diastolic",int(self.diastolic_le.text()))
            self.ps_state.set_state("heart_rate",int(self.heart_rate_le.text()))
            self.ps_state.set_state("respiration_rate",int(self.respiration_rate_le.text()))
            # Clear whatever waveform is currently plotted and get us ready to accept new data
            self._clear_plot()
            if (self.play_type_toggle.value() == 0):
                self.ps_state.set_state("play_mode",PlayMode.PULSE_TABLE)
                # Pulse Table; launch in the background the thread that's going to handle everything.  We'll
                # give it the ps_state, and then it will feed us points and any other information we may
                # need as it does its thing.
                self.pulse_thread = QThread()
                self.pulse_worker = PSAppPulsePlaybackWorker(self.pt_le.text(),self.ps_state,self.comm_interface,self.data_iface,self.cal_max_le.text())
                self.pulse_worker.moveToThread(self.pulse_thread)
                self.pulse_worker.table_read_error.connect(self._pulse_table_read_error)
                self.pulse_worker.wf_load_fail.connect(self._pulse_table_wf_load_error)
                self.pulse_worker.new_data_point.connect(self._plot_new_datapoint)
                self.pulse_worker.bad_message_format.connect(self._bad_message_format_alert)
                self.pulse_worker.data_read_fail.connect(self._data_read_fail_alert)
                self.pulse_worker.data_load_complete.connect(self._data_load_complete)
                self.pulse_worker.finished.connect(self._confirm_pulse_table_end)
                self.pulse_thread.started.connect(self.pulse_worker.run)
                # Right before we start, throw up a message box that blocks the user from playing
                # with the GUI, since it can take quite a while to load all of the points into
                # the memory on the firmware.
                self.wf_status.setText("Status:  Loading point into memory.")
                QApplication.processEvents()
                self.pulse_loading_mb = QMessageBox()
                self.pulse_loading_mb.setText("Loading the points into memory.  Please be patient...")
                self.pulse_loading_mb.setWindowModality(Qt.WindowModal)
                self.pulse_thread.start()
                self.pulse_loading_mb.show()
            else:
                self.ps_state.set_state("play_mode",PlayMode.WAVEFORM)
                # Come back to this, there's a lot of heavy lifting IMO that needs to happen with the data.  For now,
                # just change it back
                self.play_button.setText("Play")
                self.ps_state.set_state("playing",False)

    def _eval_refresh(self):
        """ Compare the values with those stored away; at some point, we'll bring up a dialog that asks the user to wait while the new values are written to the firmware.
        """
        self.ps_state.set_state("systolic",float(self.systolic_le.text()))
        self.ps_state.set_state("diastolic",float(self.diastolic_le.text()))
        self.ps_state.set_state("heart_rate",float(self.heart_rate_le.text()))
        self.ps_state.set_state("respiration_rate",float(self.respiration_rate_le.text()))
        # Now go through each of the line edits and 'correct the record', as it were...
        for le in [self.systolic_le,self.diastolic_le,self.heart_rate_le,self.respiration_rate_le]:
            self._eval_param_entry(le)
        self.refresh_button.setEnabled(False)
        self._set_widget_status()

    def _first_cal_procedure(self):
        """ Change the status text appropriately, and then start the calibration procedure.
        """
        self.wf_status.setText("Status: Running calibration procedure.")
        self._start_cal_procedure()

    def _hardware_disconnect_event(self):
        """ We sense that the COM device that we're supposed to use has gone away.
        """
        # Kill the thread completely; if it's not dead already, this will kill it.
        self.worker.stop()
        self.thread.quit()
        self.thread.wait()
        # Update the connection text
        self.cs_label.setText("Connection status:  Not connected")
        self.ps_state.set_state("connected",False)
        self.connect_button.setEnabled(True)
        self._set_widget_status()
        warn_dlg = QMessageBox()
        warn_dlg.setText("The device has disconnected.")
        warn_dlg.exec()

    def _increment(self,val):
        """ Move the motor by 'val' steps.
        """
        # We can only do this if we're connected...
        if not(self.ps_state.get_state("connected")):
            return
        try:
            val = str(int(val)).encode()
            self.cfg_iface["ser"].write(b'O'+val+b'\n')
            rem = re.match(b'^OK',self.cfg_iface["ser"].readline())
            if rem:
                self.data_iface["ser"].readline()
        except:
            pass

    def _initialize_plot(self):
        """ Create a new plot area.
        """
        self.plot_x = []
        self.plot_y = []
        self.plt = pg.PlotWidget()
        self.plot = self.plt.plot(self.plot_x,self.plot_y,pen='r')
        self.plt.setLabel('left','BP',units='mmHg')
        self.plt.setLabel('bottom','Relative Time',units='s')
        self.plt.setXRange(0,10)
        self.plt.setYRange(0,250)
        self.plt.showGrid(x=True,y=True)

    def _launch_connect(self):
        """ Launch a dialog to look for the correct COM ports, both configuration and data.
        """
        self.cnct_dlg = PSAppConnectionManager()
        self.cnct_dlg.config_iface_signal.connect(self._store_config_iface)
        self.cnct_dlg.data_iface_signal.connect(self._store_data_iface)
        self.cnct_dlg.accepted.connect(self._update_connection_status)
        # Gotta wait for the operating system to clear the dialog chaff, so wait 200ms to close the window
        self.cnct_dlg.rejected.connect(lambda: QTimer.singleShot(200,self.close))
        self.cnct_dlg.exec()
        # Once we get to this point, we'll launch the connection checker
        if not(None in [self.cfg_iface,self.data_iface]):
            self.thread = QThread()
            self.worker = PSAppCheckConnectionStatus([self.cfg_iface["lpi"],self.data_iface["lpi"]])
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.disconnected.connect(self._hardware_disconnect_event)
            self.thread.start()

    def _plot_new_datapoint(self,xy):
        """ New set of datapoints has come in, plot them here.
        """
        # If no points are present yet, then then first point is going to define '0', and then all
        # points will be added afterwards until we have 10 seconds worth of data.  Once we have 10
        # seconds worth of data, we'll reset the plot data and start again.  Therefore, the first
        # thing to do is to determine the current length of our data array.  Time reported should be
        # in ms.
        if not(len(self.plot_x)):
            self.timestamp = xy[0]
        new_time = xy[0] - self.timestamp
        self.plot_x.append(new_time / 1000.0)
        self.plot_y.append(xy[1])
        self.plot.setData(self.plot_x,self.plot_y)
        QApplication.processEvents()
        if (new_time >= 10000):
            self.plot_x = []
            self.plot_y = []

    def _pulse_table_read_error(self):
        """ There was bad data in the pulse table file.
        """
        self.pulse_loading_mb.close()
        warn_dlg = QMessageBox()
        warn_dlg.setText("Malformed data in the file {}".format(self.pt_le.text()))
        warn_dlg.exec()
        self._eval_play_stop()

    def _pulse_table_wf_load_error(self):
        """ Communication broke down at some point when loading the pulse table.
        """
        self.pulse_loading_mb.close()
        warn_dlg = QMessageBox()
        warn_dlg.setText("Loading of the pulse table failed.")
        warn_dlg.exec()
        self._eval_play_stop()

    def _rp_comm_issue(self):
        """ Shutdown the dialog if communication breaks down.
        """
        self.rp_dlg.close()
        self.wf_status.setText("Status: Idle")

    def _send_home_clicked(self):
        """ Callback for when the 'Send Home' button is clicked.
        """
        self._disable_buttons()
        self._clear_plot()
        new_pos = self.home_pos_le.text()
        self.wf_status.setText("Status: Sending home to position {}".format(new_pos))
        # If there's data in the plot window, we'll want to clear that out
        QApplication.processEvents()
        success = False
        try:
            gohome_ret = self.comm_interface.transaction(b'Z'+new_pos.encode(),True)
            rem = re.match(b'^OK',gohome_ret)
            success = True if rem else False
        except:
            warn_dlg = QMessageBox()
            warn_dlg.setWindowTitle("Warning")
            warn_dlg.setText("'Send Home' command returned an error.")
            warn_dlg.exec()
        if success:
            # Clean out the data interface
            xyz = self.data_iface["ser"].readline()
        self.ps_state.set_state("home",success)
        # Performing this action will undo any priming/calibrating, so set those variables accordingly
        self.ps_state.set_state("primed",False)
        self.ps_state.set_state("calibrated",False)
        self.wf_status.setText("Status: Idle")
        self._set_widget_status()

    def _set_default_values(self):
        """ Return the various configuration values to their defaults.
        """
        self.home_pos_le.clear()
        self.home_pos_le.insert("1000")
        self.cal_max_le.clear()
        self.cal_max_le.insert("2000")
        self.cal_inc_le.clear()
        self.cal_inc_le.insert("25")
        self.pt_le.clear()
        self.pt_le.insert(get_default_pulse_table_path())
        self.wf_le.clear()
        self.wf_le.insert(get_default_waveform_path())

    def _set_primed(self,status):
        """ Have we successfully primed the system or not?
        """
        self.ps_state.set_state("primed",status)
        self._set_widget_status()

    def _set_widget_status(self):
        """ Set widget disabled/enabled based on state.
        """
        # First do the three buttons at the top
        connect_state = self.ps_state.get_state("connected")
        home_state = self.ps_state.get_state("home")
        primed_state = self.ps_state.get_state("primed")
        cal_state = self.ps_state.get_state("calibrated")
        self.send_home_button.setEnabled(connect_state)
        self.read_pressure_button.setEnabled(connect_state and home_state)
        self.run_cal_button.setEnabled(connect_state and primed_state)

        # The 'play' button is only enabled if:
        #    * All three of the 'steps' buttons above are enabled (i.e., connect_state, home_state,
        #      primed_state, and cal_state are all True
        #    * If we're in 'Waveform' playback mode, the playback file is valid.
        #    * If we're in 'Pulse' playback mode, the pulse data file is valid.
        #    * All of the line edits are valid if we're in 'Pulse' playback mode.
        play_button_enable = connect_state and cal_state
        if play_button_enable:
            if (self.play_type_toggle.value() == PlayMode.PULSE_TABLE):
                play_button_enable &= self.pt_le.get_valid()
                for x in [self.systolic_le,self.diastolic_le,self.heart_rate_le,self.respiration_rate_le]:
                    play_button_enable &= x.get_valid()
            else:
                play_button_enable &= self.wf_le.get_valid()
        self.play_button.setEnabled(play_button_enable)

        # Refresh button 
        self.refresh_button.setEnabled((self.refresh_button.isEnabled() and connect_state))

    def _start_cal_procedure(self):
        """ We'll kick off a thread that will run the routine, and then pass the data back to us via signalling.
        """
        self.cal_thread = QThread()
        xmin = int(self.home_pos_le.text())
        xmax = int(self.cal_max_le.text())
        self.cal_worker = PSAppCalibrationWorker(self.comm_interface,self.data_iface,xmin,xmax,int(self.cal_inc_le.text()))
        self.cal_worker.moveToThread(self.cal_thread)
        self.cal_thread.started.connect(self.cal_worker.run)
        self.cal_worker.new_reading.connect(self._update_calibration_plot)
        self.cal_worker.reading_error.connect(self._terminate_cal_with_error)
        self.cal_worker.finished.connect(self._end_cal_procedure)
        self.plot_x = []
        self.plot_y = []
        self.plt.setXRange(xmin,xmax)
        self.plt.setLabel('bottom','Position')
        QApplication.processEvents()
        self._disable_buttons()
        self.cal_thread.start()

    def _start_read_pressure(self):
        """ Bring up a dialog that reads the current pressure every 200ms.
        """
        self._clear_plot()
        self.wf_status.setText("Status: Reading pressure values")
        QApplication.processEvents()
        self._set_primed(False)
        self._disable_buttons()
        self.rp_dlg = PSAppReadPressureDialog(self.comm_interface,self.data_iface,int(self.prime_min_le.text()),int(self.prime_max_le.text()))
        self.rp_dlg.comm_issue.connect(self._rp_comm_issue)
        self.rp_dlg.accepted.connect(lambda: self._set_primed(True))
        self.rp_dlg.rejected.connect(lambda: self._set_primed(False))
        self.rp_dlg.exec()
        self.wf_status.setText("Status: Idle")
        self._set_widget_status()

    def _store_config_iface(self,ser_obj):
        """ Grab the information from connection manager dialog signal
        """
        self.cfg_iface = ser_obj
        self.comm_interface = PSAppCommInterface(self.cfg_iface["ser"])
        self._update_connection_status()

    def _store_data_iface(self,ser_obj):
        """ Grab the information from connection manager dialog signal
        """
        self.data_iface = ser_obj
        self._update_connection_status()

    def _terminate_cal_with_error(self):
        """ We got an error during the calibration procedure.
        """
        self.wf_status.setText("Status: Calibration failed.")
        QApplication.processEvents()
        warn_dlg = QMessageBox()
        warn_dlg.setText("There was an error during the calibration process.")
        warn_dlg.exec()
        self.ps_state.clear_pressure_table()
        self.ps_state.set_state("calibrated",False)
        self.cal_thread.quit()
        self.cal_thread.wait()
        self._set_widget_status()

    def _update_calibration_plot(self,vals):
        """ Get the x,y points from the calibration worker thread and add them to the plotting instance.
        """
        self.plot_x.append(vals[0])
        self.plot_y.append(vals[1])
        self.plot.setData(self.plot_x,self.plot_y)
        QApplication.processEvents()

    def _update_connection_status(self):
        """ If this function gets called, the dialog should've ensured that we're connected, but do a check here anyway, and then the buttons should be enabled/disabled as required.
        """
        cs_connected = not(None in [self.cfg_iface,self.data_iface])
        self.cs_label.setText("Connection status:  {}".format("Connected" if cs_connected else "Not connected"))
        QApplication.processEvents()
        self.ps_state.set_state("connected",cs_connected)
        self.connect_button.setEnabled(not(cs_connected))
        self._set_widget_status()
