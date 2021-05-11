import struct
f=open('pulse256.dat', 'rb')

a=f.read()
f.close()

w=struct.unpack("256h", a)

print(w)

f=open('src/pulse_table.xc','wb')
f.write(b"signed short pulse_table[256]={\n")
for a in w:
    s="%d,\n" % a
    f.write(s.encode('utf-8'))
f.write(b"};\n")
f.close()
