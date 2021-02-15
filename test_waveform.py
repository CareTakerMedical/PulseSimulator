from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()

pressure=Pressure()

i=0
ys=[ 25,6,7]
pressure.write_waveform(ys)

wf=pressure.read_waveform()
print(wf)

