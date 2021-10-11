from PyQt5.QtCore import * 
from PyQt5.QtGui import * 
from PyQt5.QtWidgets import * 
import re, struct
import numpy as np
from time import sleep

class PSAppLoadWorker(QObject):
    finished = pyqtSignal()
    new_parameter_value = pyqtSignal(object,object)
    point_load_init = pyqtSignal()
    point_load_fail = pyqtSignal()
    point_load_complete = pyqtSignal()
    table_read_error = pyqtSignal()
    def __init__(self,parent,prev_ps_state):
        super(PSAppLoadWorker,self).__init__()
        self.parent = parent
        self.ps_state = parent.get_ps_state()
        self.prev_ps_state = prev_ps_state
        self.comm_interface = parent.get_comm_interface()
        self.is_running = False
        self.cancel_operation = False

    def stop(self):
        self.cancel_operation = True

    def run(self):
        self.is_running = True
        while (self.is_running):
            # First thing to do is to open the pulse data file
            try:
                fh = open(self.parent.get_pulse_table_file(),'rb')
                pts = fh.read()
                fh.close()
                table_init = struct.unpack("256h",pts)
            except:
                self.table_read_error.emit()
                self.is_running = False
                continue
            # Make sure the resulting table is 256 points; any other value is incompatible with the
            # firmware, given its current design.
            if (len(table_init) != 256):
                self.table_read_error.emit()
                self.is_running = False
                continue
            table_span = max(table_init) - min(table_init)
            pressure_table = self.ps_state.get_state("pressure_table")
            motor_locs = np.array(pressure_table["x"])
            mmhg_readings = np.array(pressure_table["y"])
    
            # Second thing to do is to figure out how many loads we're going to do.  If
            # we're currently not playing, then we only do one load.  If we're playing,
            # figure out the maximum number of steps that we need to take, and figure out when/where
            # to update other parameters
            loop = 1
            writes = dict()
            goals = dict()
            params = ["systolic","diastolic","heart_rate","respiration_rate"]
            for p in params:
                writes[p] = self.ps_state.get_state(p)
            deltas = dict()
            if (self.ps_state.get_state("playing")):
                for p in params:
                    writes[p] = int(self.prev_ps_state.get_state(p))
                    goals[p] = int(self.ps_state.get_state(p))
                    deltas[p] = goals[p] - writes[p]
                    if deltas[p]:
                        writes[p] += abs(deltas[p]) / deltas[p]
                for key in deltas.keys():
                    if (abs(deltas[key]) > loop):
                        loop = int(abs(deltas[key]))
            else:
                self.ps_state.set_state("playing",True)
            for j in range(loop):
                if not self.cancel_operation:
                    self.point_load_init.emit()
                    mmhg_vals = []
                    delta = writes["systolic"] - writes["diastolic"]
                    for val in table_init:
                        mmhg_vals.append((int(val) - min(table_init)) / table_span * delta + writes["diastolic"])
                    # Take the pressure values and convert them to positions
                    positions = []
                    for i in range(len(mmhg_vals)):
                        positions.append(round(np.interp(mmhg_vals[i],mmhg_readings,motor_locs)))
                    # Wrap-around
                    positions.append(positions[0])
                    # Write the data to XMOS
                    try:
                        # Indicate that we're loading a new waveform
                        self.comm_interface.transaction(b'W')
                        # Attach a new heart rate and respiration rate. The value that gets sent over to the
                        # firmware is the index value for every 20ms interval.  So, the rates that are entered
                        # in as 'param/minute' need to be converted to the 20ms interval.  Therefore, we multiply
                        # the entered value by:
                        #   * The length of the table
                        #   * 256, because we're sending the value over in 'X.8' format
                        #   * 1/60, because we want to convert 'per minute' to 'per second'
                        #   * 1/50, because we want to convert 'per second' to 'per 20ms'
                        multiplier = len(table_init) * 256.0 / 60.0 / 50.0
                        hr = writes["heart_rate"] * multiplier
                        self.comm_interface.transaction(b'H'+str(round(hr)).encode())
                        rr = writes["respiration_rate"] * multiplier
                        self.comm_interface.transaction(b'B'+str(round(rr)).encode())
                        # Also gotta send calibrated max position
                        cal_max = self.parent.get_cal_max()
                        self.comm_interface.transaction(b'C'+cal_max.encode())
                        for pos in positions:
                            self.comm_interface.transaction(("Y{}".format(pos)).encode())
                        cmd_ret = self.comm_interface.transaction(b'E',True)
                        rem = re.match(b'^OK:\s+Buffer length\s+=\s+(\d+)',cmd_ret)
                        if rem:
                            # Check to make sure that the returned length is the same as what we believe we
                            # wrote
                            if (int(rem.group(1)) != len(positions)):
                                self.point_load_fail.emit()
                                self.is_running = False
                                continue
                            # Tell the firmware to switch over to the new data
                            tret = self.comm_interface.transaction(b'T',read_response=True,timeout=5)
                            res = re.match(b'^OK:\s+Waveform playback has begun',tret)
                            if not res:
                                self.point_load_fail.emit()
                                self.is_running = False
                                continue
                    except:
                        self.point_load_fail.emit()
                        self.is_running = False
                        continue
                    # If we've made it to this point, then we check to see if need to update parameters,
                    # and do so accordingly.
                    self.point_load_complete.emit()
                    if ((j + 1) < loop):
                        for p in params:
                            if (deltas[p]):
                                m = int(loop / deltas[p])
                                if not ((j + 1) % m):
                                    if (writes[p] != goals[p]):
                                        writes[p] += abs(deltas[p]) / deltas[p]
                                        self.new_parameter_value.emit(p,writes[p])
            self.is_running = False
        sleep(0.1)
        self.finished.emit()

class PSAppLoadDialog(QDialog):
    new_parameter_value = pyqtSignal(object,object)
    playback_ack = pyqtSignal()
    def __init__(self,parent,prev_ps_state=None):
        super(PSAppLoadDialog,self).__init__()

        # Get the ps_state from the parent
        self.ps_state = parent.get_ps_state()

        self.load_thread = QThread()
        self.load_worker = PSAppLoadWorker(parent,prev_ps_state)
        self.load_worker.finished.connect(self._load_thread_complete)
        self.load_worker.new_parameter_value.connect(self._process_new_parameter_value)
        self.load_worker.point_load_init.connect(self._point_load_init)
        self.load_worker.point_load_complete.connect(self._point_load_complete)
        self.load_worker.table_read_error.connect(self._indicate_point_read_error)
        self.load_worker.moveToThread(self.load_thread)
        self.load_thread.started.connect(self.load_worker.run)

        # The actual stuff that gets displayed in the dialog
        wf_params_label = QLabel("Current Pulse Parameters:")
        wf_params_label.setStyleSheet("font-size: 14pt; font-weight: bold")
        self.systolic_label = QLabel("Systolic: {}".format(self.ps_state.get_state("systolic")))
        self.diastolic_label = QLabel("Diastolic: {}".format(self.ps_state.get_state("diastolic")))
        self.hr_label = QLabel("Heart Rate: {}".format(self.ps_state.get_state("heart_rate")))
        self.rr_label = QLabel("Respiration Rate: {}".format(self.ps_state.get_state("respiration_rate")))
        if (prev_ps_state):
            self.systolic_label.setText("Systolic: {}".format(prev_ps_state.get_state("systolic")))
            self.diastolic_label.setText("Diastolic: {}".format(prev_ps_state.get_state("diastolic")))
            self.hr_label.setText("Heart Rate: {}".format(prev_ps_state.get_state("heart_rate")))
            self.rr_label.setText("Respiration Rate: {}".format(prev_ps_state.get_state("respiration_rate")))
        self.status_label = QLabel("Status:")
        self.action_button = QPushButton("Cancel")
        self.action_button.clicked.connect(self._cancel_progress)

        # Dialog layout
        layout = QGridLayout()
        layout.addWidget(wf_params_label,0,0,1,3)
        layout.addWidget(self.systolic_label,1,0,1,3)
        layout.addWidget(self.diastolic_label,2,0,1,3)
        layout.addWidget(self.hr_label,3,0,1,3)
        layout.addWidget(self.rr_label,4,0,1,3)
        layout.addWidget(self.status_label,5,0,1,3)
        layout.addWidget(self.action_button,6,1,1,1)
        self.setLayout(layout)

        # Kick it off
        self.load_thread.start()

        self.emit_playback_ack = True

    def _cancel_progress(self):
        self.load_worker.finished.disconnect()
        self.status_label.setText("Status: Closing out load and playback")
        QApplication.processEvents()
        self.action_button.setEnabled(False)
        self.load_worker.finished.connect(lambda: self._graceful_close(False))
        self.load_worker.stop()

    def _graceful_close(self,acc=True):
        try:
            self.close_update_timer = ~QTimer()
        except Exception as e:
            pass
        self.close_update_timer = None
        try:
            self.load_thread.quit()
            self.load_thread.wait()
        except Exception as e:
            pass
        if acc:
            self.accept()
        else:
            self.reject()

    def _indicate_point_read_error(self):
        self.load_worker.finished.disconnect()
        pulse_load_err = QMessageBox()
        pulse_load_err.setText("Error during interrogation of pulse table.")
        pulse_load_err.exec()
        self.load_thread.quit()
        self.load_thread.wait()
        self.reject()

    def _load_thread_complete(self):
        self.load_thread.quit()
        self.load_thread.wait()
        self.status_label.setText("Status: All parameter updates complete, closing dialog automatically in 5 seconds.")
        self.action_button.clicked.disconnect()
        self.seconds = 5
        self.close_update_timer = QTimer()
        self.close_update_timer.setInterval(1000)
        self.close_update_timer.timeout.connect(self._update_timeout_status)
        self.action_button.setText("Ok")
        self.action_button.clicked.connect(lambda: self._graceful_close(True))
        self.close_update_timer.start()
        QApplication.processEvents()

    def _point_load_complete(self):
        self.status_label.setText("Status: Waveform playing back with the parameters listed above.")
        QApplication.processEvents()
        if self.emit_playback_ack:
            self.playback_ack.emit()
            self.emit_playback_ack = False

    def _point_load_init(self):
        self.status_label.setText("Status: Loading waveform points and parameters")
        QApplication.processEvents()

    def _process_new_parameter_value(self,param,val):
        val = int(val)
        self.new_parameter_value.emit(param,val)
        if (param == "systolic"):
            self.systolic_label.setText("Systolic: {}".format(val))
        elif (param == "diastolic"):
            self.diastolic_label.setText("Diastolic: {}".format(val))
        elif (param == "heart_rate"):
            self.hr_label.setText("Heart Rate: {}".format(val))
        elif (param == "respiration_rate"):
            self.rr_label.setText("Respiration Rate: {}".format(val))
        QApplication.processEvents()

    def _update_timeout_status(self):
        self.seconds -= 1
        if (self.seconds > 0):
            self.status_label.setText("Status: All parameter updates complete, closing dialog automatically in {} seconds.".format(self.seconds))
            QApplication.processEvents()
        else:
            self._graceful_close()

