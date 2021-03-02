from finger import Pressure
import time
import numpy as np
import matplotlib
#matplotlib.use('TKAgg', force=True)
from matplotlib import pyplot as plt
import math
import sys
import struct
import pickle
import keyboard

play=True
psi=False

systolic=140.0
diastolic=90.0
bprange=systolic-diastolic
bpmean=(systolic+diastolic)*0.5


home=100 # so that this is 14psi, and 3000 can be a bit higher.

plt.ion()

pressure=Pressure()
lsteps=50
hsteps=1500
(steps0,psi0,mmHg0)=pressure.calibrate_curve(lsteps, hsteps, 25)
steps=np.array(steps0)
psis=np.array(psi0)
mmHgs=np.array(mmHg0)

atmospheric=14.5





#f=open("ideal.bin", "rb")
#f=open("integrated80_120.bin", "rb")
#f=open("integrated90_140.bin", "rb")
#f=open("integrated50_100.bin", "rb")

#s=f.read()
#l=len(s)/4
#f.close()
#v0=struct.unpack("%df" % l, s)
#print(v0)

f=open('TestPulses.dat', 'rb')
a=f.readlines()
f.close()
values=[]
for l in a:
    x=float(l)
    values.append(x)

v=values[:-20]
minb=50000
maxb=-50000
for b in v:
    if(b>maxb):
        maxb=b
    if(b<minb):
        minb=b
print(minb, maxb)
span=maxb-minb

runs=1
v0=[]
for i in range(runs):
    for b in v:
        x=(b-minb)/span*(systolic-diastolic)+diastolic
        v0.append(x)




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
    i=i+25
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
    
    
fig, ax=plt.subplots()
t0=[];
p0=[];
mx=[];
mn=[];
N=500;
for i in range(N):
    t0.append(i*20e-3)
    p0.append(25+i/N*100.0);
    mx.append(120)
    mn.append(80)
line1, = ax.plot(t0,p0)
line2, = ax.plot(t0,mx)
line3, = ax.plot(t0,mn)
plt.show()
T0=t0;

ax.set_ylim(25,150)
ax.set_ylabel('Pressure (mmHg)')
ax.set_title('Blood Pressure Graph')
ax.set_xlabel('Time (s)')

print(ys)
print("about to write waveform")
pressure.write_waveform(ys)
print("Wrote waveform")
#wf=pressure.read_waveform()
#print(wf)
#print("Read waveform")
print("hsteps=%d, home=%d" % (hsteps, home))

pressure.play_waveform(-1, hsteps, home)
before=time.time()
threshold=before+60.0
t=[]
p=[]
pressure.start_reading()
i=0
mean=pressure.meansteps
meanMMHg=np.interp(mean, steps, mmHgs) # MMHg at the mean steps
stepsUp=np.interp(meanMMHg+0.5, mmHgs, steps)
stepsDown=np.interp(meanMMHg-0.5, mmHgs, steps)
slope=stepsUp-stepsDown # steps to change by 1 mmHg

sei=0 # span error integral
span_kp=0.9
span_ki=0.1;

mei=0 # mean error integral
mid_kp=0.85;
mid_ki=0.1;
RNG=7500;
MID=mean
stop=0
while(i<N): # up until N, keep appending to the list
    s=pressure.one_read()
    i=i+1
    now=time.time()
    t.append(now-before)
    p1=pressure.psi2mmHg(int(s)*0.001)
    p.append(p1)
    if((i%10)==0):
        line1.set_data(T0[0:i], p[0:i])
        data=np.array(p)
        m0=np.amin(data)
        m1=np.amax(data)
        line2.set_data([0, T0[i-1]], [m1, m1])
        line3.set_data([0, T0[i-1]], [m0, m0])
        ax.legend((line1,line2,line3), ('BP', 'MAX:%3.1f' % m1, 'MIN:%3.1f' % m0),loc='lower center')
        fig.canvas.draw()    

while(1): # Now we have N, retire the last one and then append
    s=pressure.one_read()
    i=i+1
    now=time.time()
    t=t[1:] # lose the oldest time
    t.append(now-before)
    p1=pressure.psi2mmHg(int(s)*0.001)
    p=p[1:] # lose th oldest pressure       
    p.append(p1)
    if((i%10)==0):
        line1.set_data(T0[0:N], p[0:N])
        data=np.array(p[0:N])
        m0=np.amin(data)
        m1=np.amax(data)
        line2.set_data([0, 10.0], [m1, m1])
        line3.set_data([0, 10.0], [m0, m0])
        ax.legend((line1,line2,line3), ('BP', 'MAX:%3.1f' % m1, 'MIN:%3.1f' % m0),loc='lower center')
        if(False and ((i%N)==0)): # feedback every few seconds, disabled for now
            mid=(m0+m1)*0.5
            span=(m1-m0)
            miderror=mid-bpmean
            mei=mei+miderror
            MID=(MID-slope*(mid_kp*miderror+mid_ki*mei))
            print(bpmean, mid, miderror, mean, MID, slope)
            spanerror=(span-bprange)/span # fraction
            sei=sei+spanerror
            RNG=RNG*(1.0-span_kp*spanerror-span_ki*sei)
            print("SPAN:", span, bprange, RNG)
            pressure.set_params(MID, RNG, stop)
        fig.canvas.draw()
         
        if(keyboard.is_pressed(' ') and (stop==0)):
            print("Keyboard break")
            stop=1
        if(p1<30.0):
            break
        
for i in range(100): # drain any old readings
        s=pressure.one_read()
pressure.stop_reading()

import pickle
s=pickle.dumps([t,p])
f=open('data.bin', 'wb')
f.write(s)
f.close()

    

