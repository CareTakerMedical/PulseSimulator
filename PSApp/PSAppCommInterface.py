from PyQt5.QtCore import *
import re, queue
from time import sleep
from PSAppSharedFunctions import PSCommException

class PSAppCommInterfaceWorker(QObject):
    finished = pyqtSignal()
    def __init__(self,cfg_iface,request_queue,return_queue):
        super(PSAppCommInterfaceWorker,self).__init__()
        self.cfg_iface = cfg_iface
        self.request_queue = request_queue
        self.return_queue = return_queue
        self.is_running = False

    def run(self):
        self.is_running = True
        while self.is_running:
            try:
                [cmd,read_response,timeout] = self.request_queue.get(timeout=8)
                retq = True
            except:
                [cmd,read_response,timeout] = [b'V',True,0.5]
                retq = False
            match = False
            self.cfg_iface.timeout = timeout
            print("cmd = {}".format(cmd.decode()))
            for i in range(10):
                self.cfg_iface.write(cmd+b'\n')
                ret = self.cfg_iface.readline()
                while (len(ret) == 0):
                    self.cfg_iface.write(cmd+b'\n')
                    ret = self.cfg_iface.readline()
                rem = re.match(b'^ERR: Busy',ret)
                if (rem):
                    continue
                if (ret.rstrip() == cmd):
                    self.cfg_iface.write(b'\n')
                    match = True
                    break
                else:
                    self.cfg_iface.write(b'!')
            if not match:
                raise PSCommException("Command handshake failed, command = '{}'".format(cmd.decode()))
            else:
                ret = ''
                if read_response:
                    for i in range(10):
                        ret = self.cfg_iface.readline()
                        if (len(ret) > 0):
                            break
                    if (len(ret) == 0):
                        raise PSCommException("Read never returned a valid value.")
                if retq:
                    self.return_queue.put(ret)
        self.finished.emit()

    def shutdown(self):
        self.is_running = False

class PSAppCommInterface(QObject):
    """ Use a unified interface to talk to the configuration interface in firmware.  Communication seems to be spotty, so handshake between the firmware and this script to get rid of possible ambiguities."""
    def __init__(self,cfg_iface):
        """ Initialization function
        """
        super(PSAppCommInterface,self).__init__()
        self.done = False
        self.cfg_iface = cfg_iface
        self.request_queue = queue.Queue()
        self.return_queue = queue.Queue()
        self.comm_thread = QThread()
        self.comm_worker = PSAppCommInterfaceWorker(self.cfg_iface,self.request_queue,self.return_queue)
        self.comm_worker.moveToThread(self.comm_thread)
        self.comm_thread.started.connect(self.comm_worker.run)
        self.comm_thread.start()

    def is_done(self):
        return self.done

    def stop(self):
        self.comm_worker.finished.connect(self._graceful_close)
        self.comm_worker.shutdown()

    def transaction(self,cmd,read_response=False,timeout=0.5):
        """ Originally, this command would just go through its paces, communicate with the firmware, and then return a value.  However, I've implemented a watchdog on the configuration interface so that if the app ever crashes or leaves the firmware in a weird state, the firmware should go ahead and reset itself.
        """
        self.request_queue.put([cmd,read_response,timeout])
        return self.return_queue.get()

    def _graceful_close(self):
        self.thread.quit()
        self.thread.wait()
        self.done = True
