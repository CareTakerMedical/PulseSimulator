
import math

bpmod=-0.04
hrmod=0.1

f=open('src\\sine_table.xc', 'wb')
v=[]
for i in range(256):
    t=float(i)/256.0*math.pi*2.0
    x=int(8192.0*bpmod*(math.sin(t))) # negative as BP lowers on inspiration
    print(x)
    v.append(x)
f.write(b"short int sine_table_bp[257]={ ")
for a in v:
    f.write(b" %d,\n" % a)
f.write(b" %d,\n" % v[0])

f.write(b"};\n")

v=[]
for i in range(256):
    t=float(i)/256.0*math.pi*2.0
    x=int(8192.0*hrmod*(math.sin(t))) # positive as HR increases on inspiration
    print(x)
    v.append(x)
f.write(b"\n\nshort int sine_table_hr[257]={ ")
for a in v:
    f.write(b" %d,\n" % a)
f.write(b" %d,\n" % v[0])

f.write(b"};\n")


f.close()
