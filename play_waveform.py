from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt
import math

play=True

plt.ion()

pressure=Pressure()
pressure.calibrate()

w=2.0*math.pi
A=pressure.steps/4

i=0
t=0;
dt=20e-3
ts=[]
ys=[]
while(t<=2.0):
    ts.append(t)
    y=pressure.steps/2+A*math.sin(0.5*w*t)
    print(y)
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

if(play):
    pressure.play_waveform()
    

