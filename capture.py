from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()

pressure=Pressure()

i=0

plt.show()
before=time.time()
threshold=before+10.0
t=[]
pressure.start_reading()
while(time.time()<threshold):
        pressure.one_read()
        now=time.time()
        t.append(now-before)
        #p.append(p0)
pressure.stop_reading()
p=pressure.get_pressures()
print("PLOTTING")
fig, ax=plt.subplots()
anim1=ax.plot(t,p)
ax.set_ylim(10,22)
ax.set_title('Pressure Graph')
ax.set_xlabel('Time (s)')
ax.set_ylabel('Pressure (psi)')
i=i+1
plt.show()
anim1[0].set_xdata(t)
anim1[0].set_ydata(p)
fig.canvas.flush_events()
print("Done plotting")
        
