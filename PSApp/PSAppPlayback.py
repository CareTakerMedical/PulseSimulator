from PyQt5.QtCore import * 
from PyQt5.QtGui import * 
from PyQt5.QtWidgets import * 
import re, struct
import numpy as np
from time import sleep
from PSAppSharedFunctions import convert_mpsi_to_mmhg
from PSAppState import *

class PSAppPlaybackTools(QObject):
    table_read_error = pyqtSignal()
    wf_load_fail = pyqtSignal()
    new_data_point = pyqtSignal(object)
    bad_message_format = pyqtSignal()
    data_read_fail = pyqtSignal()
    data_load_complete = pyqtSignal()
    finished = pyqtSignal()
    def __init__(self,data_file,ps_state,comm_interface,data_iface,cal_max):
        super(PSAppPlaybackTools,self).__init__()
        self.data_file = data_file
        self.ps_state = ps_state
        self.comm_interface = comm_interface
        self.data_iface = data_iface
        self.cal_max = cal_max
        self.keep_playing = False

'''
class PSAppWfPlaybackWorker(PSAppPlaybackTools):
    def __init__(self,wf_data_file,ps_state,cfg_iface,data_iface):
        super(PSAppWfPlaybackWorker,self).__init__(wf_data_file,ps_state,cfg_iface,data_iface)
        self.wf_data_file = wf_data_file
        self.baseline_hr = 42.252

    def _resample_heartrate(self,pts):
        hr = self.ps_state.get_state("heart_rate")
        if (hr == self.baseline_hr):
            return pts
        ratio = hr / self.baseline_hr 
        pts_len = range(len(pts))
        npts = []
        x = 0
        while (x < (len(pts) - 1)):
            npts.append(np.interp(x,pts_len,pts))
            x += ratio
        return npts

    def run(self):
        """ Launch the command to begin waveform playback and sit here collecting data until told to do otherwise.
        """
        try:
            fh = open(self.wf_data_file,'rb')
            pts = fh.read()
            fh.close()
        except:
            self.table_read_error.emit()
            return 

        table_init = self._resample_heartrate(pts)
'''

class PSAppPulsePlaybackWorker(PSAppPlaybackTools):
    """ Routine for running calibration on the system.
    """
    def __init__(self,pulse_data_file,ps_state,comm_interface,data_iface,cal_max):
        """ Upon initialization, we'll read the data in from the supplied pulse table file, normalize it to the values supplied by the GUI, and then when instructed, we'll kick off the playback.
        """
        super(PSAppPulsePlaybackWorker,self).__init__(pulse_data_file,ps_state,comm_interface,data_iface,cal_max)
        self.pulse_data_file = pulse_data_file

    def run(self):
        """ Launch the command to begin waveform playback and sit here collecting data until told to do otherwise.
        """
        try:
            fh = open(self.pulse_data_file,'rb')
            pts = fh.read()
            fh.close()
            table_init = struct.unpack("256h",pts)
        except:
            self.table_read_error.emit()
            return 

        # Make sure the resulting table is 256 points; any other value is incompatible with the
        # firmware, given its current design.
        if (len(table_init) != 256):
            self.table_read_error.emit()
            return
        # Take the points in the table, and convert them to mmHg
        table_span = max(table_init) - min(table_init)
        mmhg_vals = []
        systolic = self.ps_state.get_state("systolic")
        diastolic = self.ps_state.get_state("diastolic")
        delta = systolic - diastolic
        pressure_table = self.ps_state.get_state("pressure_table")
        motor_locs = np.array(pressure_table["x"])
        mmhg_readings = np.array(pressure_table["y"])
        for val in table_init:
            mmhg_vals.append((float(val) - min(table_init)) / table_span * delta + diastolic)
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
            hr = self.ps_state.get_state("heart_rate") * multiplier
            self.comm_interface.transaction(b'H'+str(round(hr)).encode())
            rr = self.ps_state.get_state("respiration_rate") * multiplier
            self.comm_interface.transaction(b'B'+str(round(rr)).encode())
            # Also gotta send calibrated max position
            self.comm_interface.transaction(b'C'+self.cal_max.encode())
            for pos in positions:
                self.comm_interface.transaction(("Y{}".format(pos)).encode())
            cmd_ret = self.comm_interface.transaction(b'E',True)
            rem = re.match(b'^OK:\s+Buffer length\s+=\s+(\d+)',cmd_ret)
            if rem:
                # Check to make sure that the returned length is the same as what we believe we
                # wrote
                if (int(rem.group(1)) != len(positions)):
                    self.wf_load_fail.emit()
                    return
                # Else, we'll start the waveform playback process, with the next step being
                # reading forever from the data interface
                self.data_load_complete.emit()
                self.keep_playing = True
                self.comm_interface.transaction(b'T')
                self.data_iface["ser"].timeout = 3
        except:
            self.wf_load_fail.emit()
            return

        # Sit in a loop grabbing data until we're told otherwise
        while self.keep_playing:
            try:
                data = self.data_iface["ser"].readline()
                rem = re.match(b'^W,\d+,(\d+),(\d+)',data)
                if rem:
                    mmhg_reading = convert_mpsi_to_mmhg(int(rem.group(2)))
                    self.new_data_point.emit([int(rem.group(1)),mmhg_reading])
                else:
                    self.bad_message_format.emit()
                    self.keep_playing = False
            except:
                self.data_read_fail.emit()
                self.keep_playing = False

        # If we're outside of this loop, we've been told to stop playback.  In order to do this,
        # send the command to the firmware, and then read data from the data interface until we get
        # a timeout.
        self.comm_interface.transaction(b'S')
        self.data_iface["ser"].timeout = 1
        while True:
            try:
                self.data_iface["ser"].readline()
            except:
                break
        self.finished.emit()

    def stop_playback(self):
        self.keep_playing = False
