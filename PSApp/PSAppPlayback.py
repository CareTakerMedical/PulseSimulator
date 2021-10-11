from PyQt5.QtCore import * 
from PyQt5.QtGui import * 
from PyQt5.QtWidgets import * 
import re, struct
import numpy as np
from time import sleep
from PSAppSharedFunctions import convert_mpsi_to_mmhg
from PSAppState import *

class PSAppPulsePlaybackWorker(QObject):
    """ Routine for running calibration on the system.
    """
    new_data_point = pyqtSignal(object)
    bad_message_format = pyqtSignal()
    data_read_fail = pyqtSignal()
    finished = pyqtSignal()
    def __init__(self,comm_interface,data_iface):
        super(PSAppPulsePlaybackWorker,self).__init__()
        self.comm_interface = comm_interface
        self.data_iface = data_iface
        self.data_iface["ser"].timeout = 3
        self.keep_playing = False

    def run(self):
        # Sit in a loop grabbing data until we're told otherwise
        self.keep_playing = True
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
                res = self.data_iface["ser"].readline()
                if (len(res) == 0):
                    break
            except:
                break
        self.finished.emit()

    def stop_playback(self):
        self.keep_playing = False
