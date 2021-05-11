from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()




pressure=Pressure()
pressure.reset_sensor()
for i in range(10000):
    (p,mm, t)=pressure.quick_read()
    print("%2.2f PSI, \t%3.1f mmHg, \t%2.1f C" % (p, mm, t))
    time.sleep(0.1)
    
