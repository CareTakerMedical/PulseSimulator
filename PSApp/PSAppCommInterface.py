import re
from time import sleep
class PSAppCommInterface(object):
    """ Use a unified interface to talk to the configuration interface in firmware.  Communication seems to be spotty, so handshake between the firmware and this script to get rid of possible ambiguities."""
    def __init__(self,cfg_iface):
        """ Initialization function
        """
        self.cfg_iface = cfg_iface
        self.cfg_iface.timeout = 0.1

    def transaction(self,cmd,read_response=False):
        """ Send a command, do a handshake with the firmware, wait for a response if one is expected.
        """
        match = False
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
            raise Exception("Command handshake failed, command = '{}'".format(cmd.decode()))
        else:
            if read_response:
                ret = self.cfg_iface.readline()
                while (len(ret) == 0):
                    ret = self.cfg_iface.readline()
                return ret
