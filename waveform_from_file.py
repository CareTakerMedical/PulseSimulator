import struct



low=50
high=100

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
        #print("maxb, ", maxb)
    
    if(b<minb):
        minb=b
        #print("minb, ", minb)

print(minb, maxb)
span=maxb-minb

runs=4
mmhg=[]
for i in range(runs):
    for b in v:
        x=(b-minb)/span*(high-low)+low
        #print(x)
        mmhg.append(x)

f=open("integrated%d_%d.bin" % (low,high), "wb")
for x in mmhg:
    s=struct.pack("f", x)
    f.write(s)
f.close()
    


