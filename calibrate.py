from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()

pressure=Pressure()

i=0

before=time.time()
threshold=before+10.0
t=[]
w=pressure.calibrate(1200,2800)
print(w)

