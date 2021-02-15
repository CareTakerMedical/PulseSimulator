from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt
import math
import sys
import struct
import pickle

play=True
psi=False



home=100 # so that this is 14psi, and 3000 can be a bit higher.

plt.ion()

pressure=Pressure()
lsteps=500
hsteps=2650
(steps0,psi0,mmHg0)=pressure.calibrate_curve(lsteps, hsteps, 25)
steps=np.array(steps0)
psis=np.array(psi0)
mmHgs=np.array(mmHg0)

atmospheric=14.0

runs=1;


#f=open("ideal.bin", "rb")
f=open("integrated80_120.bin", "rb")
#f=open("integrated90_140.bin", "rb")
#f=open("integrated50_100.bin", "rb")
s=f.read()
l=len(s)/4
f.close()
v0=struct.unpack("%df" % l, s)
print(v0)

ys=[]
ys0=[]
i=0
t=0;
dt=20e-3
ts=[]
ps=[]
mms=[]
while(i <(len(v0))):
    x=v0[i]
    s=round(np.interp(x, mmHgs, steps))
    #print(s)
    i=i+10
    ts.append(t)
    t=t+dt
    ys0.append(s)

for i in range(runs):
    for y in ys0:
        ys.append(y)
print(len(ys))


#print(v)
#sys.exit(0)


maxstep=0
for i in range(len(ys)-1):
    ds=abs(ys[i+1]-ys[i])
    if(abs(ds)>maxstep):
        maxstep=abs(ds)

print("Maxstep = %d, length = %d" % (maxstep, len(ys)))
    
    

#sys.exit(0)
if(not play):
    psi=False
    fig, ax=plt.subplots()
    
    if(psi):
        anim1=ax.plot(ts,ps)
        ax.set_ylim(14,19)
        ax.set_ylabel('Pressure (PSI)')
        ax.set_title('Absolute Pressure Graph')

    else:
        f=open('data.bin', 'rb')
        s=f.read()
        f.close()
        [t,p]=pickle.loads(s)
        p2=[]
        t2=[]
        for p0 in p:
            p2.append(p0+60)
        for t0 in t:
            t2.append(t0-0.65)
        anim1=ax.plot(ts,mms, t2, p2)
        ax.set_ylim(25,150)
        ax.set_xlim(0.1,19.0)
        ax.set_ylabel('Pressure (mmHg)')
        ax.set_title('Blood Pressure Graph')
        ax.set_xlabel('Time (s)')
        ax.legend(['Target','Measured'])


    plt.show()
    fig.canvas.flush_events()
    sys.exit(0)


print(ys)
print("about to write waveform")
pressure.write_waveform(ys)
print("Wrote waveform")
wf=pressure.read_waveform()
print(wf)
print("Read waveform")
print("hsteps=%d, home=%d" % (hsteps, home))
#sys.exit(0);
pressure.play_waveform(1, hsteps, home)
before=time.time()
threshold=before+32.0
t=[]
pressure.start_reading()
i=0
while(time.time()<threshold):
        pressure.one_read()
        i=i+1
        if(i==250):
            pressure.set_params(pressure.meansteps+150, 6192)
        now=time.time()
        t.append(now-before)
        #p.append(p0)
pressure.stop_reading()
if(psi):
    p=pressure.get_pressures()
else:
    p=pressure.get_mmHgs()
print("PLOTTING")

import pickle
s=pickle.dumps([t,p])
f=open('data.bin', 'wb')
f.write(s)
f.close()

fig, ax=plt.subplots()
anim1=ax.plot(t,p)
if(psi):
    ax.set_ylim(14,22)
    ax.set_ylabel('Pressure (PSI)')
    ax.set_title('Absolute Pressure Graph')

else:
    ax.set_ylim(25,150)
    ax.set_ylabel('Pressure (mmHg)')
    ax.set_title('Blood Pressure Graph')
ax.set_xlabel('Time (s)')


plt.show()
fig.canvas.flush_events()
print("Done plotting")
    

