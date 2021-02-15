from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt

plt.ion()




pressure=Pressure()

i=0

plt.show()
while(1):
    before=time.time()
    threshold=before+10.0
    t=[]
    p=[]
    pressure.start_reading()
    #while(1):
    #    pressure.dump()
    while(1):
        p0=pressure.try_read_pressure()
        #print(p0)
        now=time.time()
        t.append(now-before)
        p.append(p0)
        if(now>threshold):
            print("PLOTTING")
            if(i):
                anim1[0].set_xdata(t)
                anim1[0].set_ydata(p)
                fig.canvas.flush_events()
            
            else:
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
            break
        break
        
