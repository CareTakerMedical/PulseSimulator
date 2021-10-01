from PyQt5.QtCore import * 
from PyQt5.QtGui import * 
from PyQt5.QtWidgets import * 
import re
from time import sleep
from PSAppSharedFunctions import convert_mpsi_to_mmhg

class PSAppCalibrationWorker(QObject):
    """ Routine for running calibration on the system.
    """
    new_reading = pyqtSignal(object)
    reading_error = pyqtSignal()
    finished = pyqtSignal()
    def __init__(self,comm_interface,data_iface,home,cal_max,cal_inc):
        """ Initialization function.
        """
        super(PSAppCalibrationWorker,self).__init__()
        self.comm_interface = comm_interface
        self.data_iface = data_iface
        self.current_pos = home
        self.range_max = cal_max
        self.step = cal_inc

    def send_comm(self,comm,reply,mode_char=None):
        """ The same procedure is run, but with different commands.
        """
        try:
            cmd_ret = self.comm_interface.transaction(comm,True)
            rem = re.match(reply,cmd_ret)
            if not rem:
                self.reading_error.emit()
                return None
            if mode_char:
                rem = re.match(mode_char+b',\d+,\d+,(\d+)',self.data_iface["ser"].readline())
                if rem:
                    return int(rem.group(1))
                self.reading_error.emit()
                return None
        except:
            self.reading_error.emit()
            return None

    def run(self):
        """ Run through points...
        """
        # Before running increment, run a plain read for the 'Home' point...
        ret_val = self.send_comm(b'R',b'^OK',b'R')
        if not ret_val:
            return
        self.new_reading.emit([self.current_pos,convert_mpsi_to_mmhg(ret_val)])
        while (self.current_pos < self.range_max):
            sleep(0.1)
            ret_val = self.send_comm(b'I'+str(self.step).encode(),b'^OK',b'I')
            if not ret_val:
                return
            self.current_pos += self.step
            self.new_reading.emit([self.current_pos,convert_mpsi_to_mmhg(ret_val)])
        self.send_comm(b'G',b'^OK',b'R')
        self.finished.emit()
