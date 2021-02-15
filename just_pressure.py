from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()




pressure=Pressure()
pressure.reset_sensor()
for i in range(10000):
    (p,mm)=pressure.quick_read()
    print("%2.2f PSI, \t%3.1f mmHg" % (p, mm))
    time.sleep(0.1)
    
