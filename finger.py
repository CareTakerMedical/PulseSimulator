import serial
import time
import random



class Pressure:
    def __init__(self):
        self.sensor_version='B' # A is 0-25psi, B is 0-300 mmHg, C is 0-25 psi
        self.ser = serial.Serial('COM3', timeout=0.1) # open serial port
        print(self.ser.name)             # check which port was really used
        self.lastpressure=14.52
        self.lowp=-1
        self.highp=-1
        self.meansteps=-1
        if(self.sensor_version=='B'):
            self.atmosphere=0.0
        else:
            self.atmosphere=14.52

        self.pressure_multiplier=0.001 # output is in mPSI.
        self.mmHg2PSI=0.0193368
        self.PSI2mmHg=1.0/self.mmHg2PSI
        self.temp_multiplier=0.0625 # output steps, degrees C

    def reset_sensor(self):
        self.ser.write(b'0')
        time.sleep(0.1)
        

    def read_pressure(self):
        self.ser.write(b'R')
        s=self.ser.readline()
        #print(s)
        s=s[:-2]
        try:
            pressure=int(s)*self.pressure_multiplier
        except:
            pressure=self.lastpressure
        self.lastpressure=pressure
        #pressure=random.random()
        #time.sleep(0.025)
        return pressure


    # 'Quick' calibrate curve
    def calibrate_curve(self, low, high, inc):
        return self.do_calibrate_curve(low, high, inc, 0.01)

    # 'Slow' calibrate curve with time delay 'pause'
    def slow_calibrate_curve(self, low, high, inc, pause):
        return self.do_calibrate_curve(low, high, inc, pause)

    def do_calibrate_curve(self, low, high, inc, pause):
        s=[]
        p=[]
        mmHg=[]
        pos=low
        self.home(pos)
        print(pos)
        while(pos<=high):
            self.inc(inc)
            time.sleep(pause) # pause now, before reading pressure
            (p0,mm)=self.quick_read()
            print("Pressure @ %d steps = %f PSI, %f mmHg" % (pos, p0, self.psi2mmHg(p0)))
            p.append(p0)
            mmHg.append(self.psi2mmHg(p0))
            pos=pos+inc
            s.append(pos)
            #print(pos)
        return (s, p, mmHg)

    def start_calibrate_curve(self, low, inc):
        self.calib_s=[]
        self.calib_p=[]
        self.calib_mmHg=[]
        self.calib_pos=low-inc
        self.home(self.calib_pos) 

    def one_calibrate(self, inc, pause):
        self.inc(inc)
        time.sleep(pause)
        (p0,mm)=self.quick_read()
        print("Pressure @ %d steps = %f PSI, %f mmHg" % (self.calib_pos, p0, self.psi2mmHg(p0)))
        self.calib_p.append(p0)
        self.calib_mmHg.append(self.psi2mmHg(p0))
        self.calib_pos=self.calib_pos+inc
        self.calib_s.append(self.calib_pos)
        return self.calib_pos

    def end_calibrate(self):
        return (self.calib_s, self.calib_p, self.calib_mmHg)
        
    
    def calibrate(self, l, h): # calibrate between l and h steps
        self.ser.write(b'C');
        s=("G%5d\n" % l).encode()
        self.ser.write(s);
        s=("G%5d\n" % h).encode()
        self.ser.write(s);
        self.lowp=self.readint()*self.pressure_multiplier
        self.highp=self.readint()*self.pressure_multiplier
        self.stepsl=self.readint()
        self.stepsh=self.readint()
        print("Pressure range = [%f - %f] PSI, [%f -%f] mmHg, %d-%d steps" % (self.lowp, self.highp, self.psi2mmHg(self.lowp), self.psi2mmHg(self.highp), self.stepsl, self.stepsh))
        slope=(self.psi2mmHg(self.highp)-self.psi2mmHg(self.lowp))/(self.stepsh-self.stepsl)
        print("slope= %f" % slope)
        return [ self.lowp, self.highp, self.stepsl, self.stepsh ]

    def home(self, n): # go to home + N steps
        self.ser.write(b'H');
        s=("G%5d\n" % n).encode()
        self.ser.write(s);
        p=self.readint()*self.pressure_multiplier
        print("Pressure @ %d steps = %f PSI, %f mmHg" % (n, p, self.psi2mmHg(p)))
        return p

    def inc(self, n): # go to current + N steps
        self.ser.write(b'I');
        s=("G%5d\n" % n).encode()
        self.ser.write(s);
        p=self.readint()*self.pressure_multiplier
        return p

    def start_reading(self):
        self.ser.write(b'R')
        self.reads=[]

    def stop_reading(self):
        self.ser.write(b'S')
        

    def quick_read(self):
        self.ser.write(b'r')
        s=self.ser.readline()
        print("S", s)
        w=s.split(b",")
        
        p=int(w[0])*self.pressure_multiplier
        mmHg=self.psi2mmHg(p)
        t=float(w[1])*self.temp_multiplier
        return (p, mmHg, t)
        

    def get_pressures(self):
        p=[]
        for s in self.reads:
            p0=s*self.pressure_multiplier
            p.append(p0)
        return p

    def psi2mmHg(self, psi):
        return (psi-self.atmosphere)/self.mmHg2PSI

    def mmHg2psi(self, mmHg):
        return mmHg*self.mmHg2PSI+self.atmosphere;

    def get_mmHgs(self):
        p=[]
        for s in self.reads:
            p0=int(s)*self.pressure_multiplier
            p.append(self.psi2mmHg(p0))
        return p
    
    def one_read(self):
        r,s=self.read2ints()
        #self.reads.append(r)
        return r,s

    def readline(self):
        s=self.ser.readline()
        return s

    def readint(self):
        s=b""
        while(len(s)==0):
            s=self.readline()
            #print(s,len(s))
        s=s[:-2]
        return int(s)

    def read2ints(self):
        s=b""
        while(len(s)==0):
            s=self.readline()
            #print(s,len(s))
        s=s[:-2]
        w=s.split(",")
        
        return int(w[0]), int(w[1])


    def try_read_pressure(self):
        #self.ser.write(b'R')
        s=self.ser.readline()
        print(s)
        s=s[:-2]
        try:
            pressure=int(s)*self.pressure_multiplier
        except:
            print("bad reading!")
            pressure=self.lastpressure
        self.lastpressure=pressure
        return pressure

    def dump(self):
        s=self.ser.readline()
        print(s)

    def write_waveform(self, w):
        s=b'W'
        #print(s)
        r=self.ser.write(s)
        print(r)
        for w0 in w:
            #print(w0)
            s=("D%5d\n" % w0).encode() # not sure why have to have a space in here but it avoids a repeated 1st digit
            #s=b'D'
            #print(s)
            r=self.ser.write(s)
            #print(r)
        s=b'E'
        self.ser.write(s)

    def read_waveform(self):
        r=self.ser.write(b'Q')
        #print(r)
        wf=[]
        while(1):
            s=""
            while(len(s)==0):
                s=self.ser.readline()
                #print(s)
            s=s[:-2]
            x=int(s)
            #print(x)
            if(x<0):
                break
            wf.append(x)
        return wf
            
    def play_waveform(self, n, hsteps, home): # n loops, starting at hsteps, home to go to once done
        s=("G%5d\n" % n).encode() # not sure why have to have a space in here but it avoids a repeated 1st digit
        self.ser.write(s)
        s=("G%5d\n" % hsteps).encode() # not sure why have to have a space in here but it avoids a repeated 1st digit
        self.ser.write(s)
        s=("G%5d\n" % home).encode() # not sure why have to have a space in here but it avoids a repeated 1st digit
        self.ser.write(s)
        s=""
        while(len(s)==0):
            s=self.ser.readline()
        self.meansteps=int(s)
        print(s, self.meansteps)

    def set_params(self, mean, scale, stop):
        self.ser.write(b'P');
        s=("G%5d\n" % mean).encode() # not sure why have to have a space in here but it avoids a repeated 1st digit
        self.ser.write(s)
        s=("G%5d\n" % scale).encode() # not sure why have to have a space in here but it avoids a repeated 1st digit
        self.ser.write(s)
        s=("G%5d\n" % stop).encode() # not sure why have to have a space in here but it avoids a repeated 1st digit
        self.ser.write(s)
        #s=self.ser.readline()
        #print("S=", s)
        
        

    def read_limits(self):
        self.ser.write(b'L')
        s=self.ser.readline()
        print(s)


#p=Pressure()
#before=time.time()
#for i in range(500):
#    pressure=p.read_pressure()
    #print(pressure)
#after=time.time()
#print('elapsed %d, rate %d/s' % ((after-before), (500.0/(after-before))))
