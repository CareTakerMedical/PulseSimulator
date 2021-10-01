from enum import IntEnum

class PlayMode(IntEnum):
    PULSE_TABLE = 0
    WAVEFORM = 1

class PSAppState(object):
    """ Tracks the state of the interaction between the GUI and the firmware running on the pulse simulator hardware (i.e., the XMOS microcontroller).
    """
    def __init__(self):
        """ Initialization function """
        self.state = dict()
        self.state["connected"] = False
        self.state["home"] = False
        self.state["primed"] = False
        self.state["calibrated"] = False
        self.state["playing"] = False
        self.state["systolic"] = 110
        self.state["diastolic"] = 80
        self.state["heart_rate"] = 75
        self.state["respiration_rate"] = 10
        self.state["play_mode"] = PlayMode.PULSE_TABLE
        self.state["pressure_table"] = {"x":list(),"y":list()}

    def clear_pressure_table(self):
        self.state["pressure_table"] = {"x":list(),"y":list()}

    def get_state(self,key):
        return self.state[key]

    def populate_pressure_table(self,x=None,y=None):
        """ Special function to quickly populate the pressure table.
        """
        if x:
            self.state["pressure_table"]["x"] = x
        if y:
            self.state["pressure_table"]["y"] = y

    def set_state(self,key,val):
        if key in self.state.keys():
            self.state[key] = val
        else:
            raise KeyError("Unknown key '{}'.".format(key))
