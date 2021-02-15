from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt
import math
import sys
import struct
import pickle

play=True
use_psi=False




home=1500 # so that this is 14psi, and 3000 can be a bit higher.

plt.ion()

pressure=Pressure()
C=pressure.calibrate(1800,3000)


lsteps=C[2]
hsteps=C[3]
lowp=C[0]
highp=C[1]
print("C=", C)
prange=highp-lowp
steprange=hsteps-lsteps



runs=1;

def psi_to_steps(psi):
    s=lsteps+((psi-lowp)/prange*steprange)
    return s


ys=[]
ys0=[]
i=0
t=0;
dt=20e-3
ts=[]
ps=[]
mms=[]


v0=[]
for i in range(50):
    v0.append(50)
for i in range(10):
    for j in range(70):
        v0.append(j+50)
    for j in range(70):
        v0.append(120-j)
for i in range(50):
    v0.append(50)
    

while(i <(len(v0))):
    x=v0[i]
    mms.append(x)
    psi0=pressure.mmHg2psi(x)
    ps.append(psi0)
    #print(x)
    
    s=int(psi_to_steps(psi0))
    #print(s)
    i=i+2
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
    use_psi=False
    fig, ax=plt.subplots()
    
    if(use_psi):
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
#sys.exit(0);
pressure.play_waveform(1, hsteps, home)
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
if(use_psi):
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
if(use_psi):
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
    

