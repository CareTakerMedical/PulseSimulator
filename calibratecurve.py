from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()

pressure=Pressure()

i=0

before=time.time()
threshold=before+10.0
(s,p,mmHg)=pressure.calibrate_curve(50, 1500, 10)

fig, ax=plt.subplots(2,1)
anim1=ax[0].plot(s,p)
anim2=ax[1].plot(s,mmHg)

plt.show()
