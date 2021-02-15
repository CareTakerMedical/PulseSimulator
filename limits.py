from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()




pressure=Pressure()

i=0


while(1):
    p0=pressure.read_limits()
    print(p0)
    time.sleep(0.1)    
