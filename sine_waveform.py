from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt
import math
import sys

play=True
psi=False


mmHg2PSI=0.0193368


plt.ion()

pressure=Pressure()
#pressure.calibrate()

f=1.8 # Hz
w=2.0*math.pi*f
steps=4812
lowp=13.75
highp=20.564
prange=highp-lowp
BPL=60.0
BPH=220.0
bpl=14.0+BPL*mmHg2PSI
bph=14.0+BPH*mmHg2PSI
print("bpl,bph", bpl, bph)
lowsteps=(bpl-lowp)/prange*steps
highsteps=(bph-lowp)/prange*steps
midsteps=(highsteps+lowsteps)/2
A=(highsteps-lowsteps)/2
print("low, mid, high steps, A", lowsteps, midsteps, highsteps, A)


#sys.exit(0)


i=0
t=0;
dt=20e-3
ts=[]
ys=[]
while(t<=10.0):
    ts.append(t)
    y=midsteps+A*math.sin(w*t)
    #print(y)
    ys.append(int(y))
    t=t+dt

maxstep=0
for i in range(len(ys)-1):
    ds=abs(ys[i+1]-ys[i])
    if(abs(ds)>maxstep):
        maxstep=abs(ds)

print("Maxstep = %d" % maxstep)
    
    
print(ys)
pressure.write_waveform(ys)
print("Wrote waveform")
wf=pressure.read_waveform()
print(wf)
#sys.exit(0)
if(play):
    pressure.play_waveform(1)
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
if(psi):
    p=pressure.get_pressures()
else:
    p=pressure.get_mmHgs()
print("PLOTTING")
fig, ax=plt.subplots()
anim1=ax.plot(t,p)
if(psi):
    ax.set_ylim(12,22)
    ax.set_ylabel('Pressure (PSI)')
    ax.set_title('Absolute Pressure Graph')

else:
    ax.set_ylim(0,220)
    ax.set_ylabel('Pressure (mmHg)')
    ax.set_title('Blood Pressure Graph')
ax.set_xlabel('Time (s)')


i=i+1
plt.show()
anim1[0].set_xdata(t)
anim1[0].set_ydata(p)
fig.canvas.flush_events()
print("Done plotting")
    

