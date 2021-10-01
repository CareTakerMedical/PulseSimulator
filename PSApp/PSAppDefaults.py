import os

def get_default_res_path():
    return "{0}{1}res".format(os.getcwd(),os.sep)

def get_default_pulse_table_path():
    return "{0}{1}pulse_256.dat".format(get_default_res_path(),os.sep)

def get_default_waveform_path():
    return "{0}{1}test_pulses.dat".format(get_default_res_path(),os.sep)
