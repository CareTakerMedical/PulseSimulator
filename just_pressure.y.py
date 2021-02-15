from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()




pressure=Pressure()

for i in range(100):
    print(pressure.one_read())
    time.sleep(1.0)
    
