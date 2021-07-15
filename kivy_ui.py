from finger import Pressure
import time
import numpy as np

import math
import sys
import struct
import pickle
import re

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import Graph, MeshLinePlot
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock

# Note we need to pip install kivy, then pip install kivy_garden as below.
#python -m pip install kivy_garden.graph --extra-index-url https://kivy-garden.github.io/simple/

USE_PULSE_TABLE=True
SAVE_FILE=False
SAVEFILE_NAME="data.dat"

default_bgnd=[0.7,0.7,0.7,1]

class FloatInput(TextInput):

    pat = re.compile('[^0-9]')
    def insert_text(self, substring, from_undo=False):
        pat = self.pat
        if '.' in self.text:
            s = re.sub(pat, '', substring)
        else:
            s = '.'.join([re.sub(pat, '', s) for s in substring.split('.', 1)])
        return super(FloatInput, self).insert_text(s, from_undo=from_undo)

class UIApp(App):

    def init(self):
        self.read_pulse_table()

    def build(self):
        self.savef=None
        self.state=None
        self.baselineHR=42.252 # baseline HR
        self.Ts=1.0/50.0 # sampling period
        self.modulation=0.1 # how much to modulate the pressure wave via RR
        self.pressure=Pressure()
        superBox = BoxLayout(orientation ='vertical') 
        HB = BoxLayout(orientation ='horizontal')
        cell1=BoxLayout(orientation='vertical')
        self.textinputHomePos = FloatInput(text='1000')
        cell1h=BoxLayout(orientation='horizontal')
        label=Label(text='Home Pos')
        cell1h.add_widget(label)
        cell1h.add_widget(self.textinputHomePos)

        self.textinputCalibMax = FloatInput(text='2000')
        cell1bh=BoxLayout(orientation='horizontal')
        label=Label(text='Calib Max')
        cell1bh.add_widget(label)
        cell1bh.add_widget(self.textinputCalibMax)

        self.textinputCalibInc = FloatInput(text='25')
        cell1ch=BoxLayout(orientation='horizontal')
        label=Label(text='Calib Inc')
        cell1ch.add_widget(label)
        cell1ch.add_widget(self.textinputCalibInc)

        self.textinputCalibDelay = FloatInput(text='0.1')
        cell1dh=BoxLayout(orientation='horizontal')
        label=Label(text='Calib Delay')
        cell1dh.add_widget(label)
        cell1dh.add_widget(self.textinputCalibDelay)
        
        self.home_button=Button(text='Home')
        self.home_button.bind(on_press = self.home)
        self.home_button.background_color=default_bgnd
        self.calib_button=Button(text='Calibrate')
        self.calib_button.background_color=default_bgnd
        self.calib_button.bind(on_press = self.calibrate) 
        
        cell1.add_widget(cell1h)
        cell1.add_widget(self.home_button)
        cell1.add_widget(cell1ch)
        cell1.add_widget(cell1bh)
        cell1.add_widget(cell1dh)
        cell1.add_widget(self.calib_button)
        
        HB.add_widget(cell1)
        self.pressure_button=Button(text='Read\nPressure')
        
        self.pressure_button.background_color=default_bgnd
        self.pressure_button.bind(on_press = self.read_pressure) 

        cell1b=BoxLayout(orientation='vertical')
        cell1b.add_widget(self.pressure_button)
        self.pressure_label=Label(text='0.0 mmHg')
        cell1b.add_widget(self.pressure_label)
                         
        HB.add_widget(cell1b)


        cell3=BoxLayout(orientation='vertical')
        cell3a=BoxLayout(orientation='horizontal')
        label=Label(text='Systolic')
        self.textinputSystolic=FloatInput(text='120.0')
        cell3a.add_widget(label)
        cell3a.add_widget(self.textinputSystolic)
        cell3.add_widget(cell3a)
            
        cell3b=BoxLayout(orientation='horizontal')
        label=Label(text='Diastolic')
        self.textinputDiastolic=FloatInput(text='80.0')
        cell3b.add_widget(label)
        cell3b.add_widget(self.textinputDiastolic)
        cell3.add_widget(cell3b)
        
        cell3c=BoxLayout(orientation='horizontal')
        label=Label(text='HR')
        self.textinputHR=FloatInput(text='75.0')
        cell3c.add_widget(label)
        cell3c.add_widget(self.textinputHR)
        cell3.add_widget(cell3c)
        
        cell3d=BoxLayout(orientation='horizontal')
        label=Label(text='RR')
        self.textinputRR=FloatInput(text='10.0')
        cell3d.add_widget(label)
        cell3d.add_widget(self.textinputRR)
        cell3.add_widget(cell3d)
        
        HB.add_widget(cell3)

        self.play_button=Button(text='Play Waveform')
        
        self.play_button.background_color=default_bgnd
        self.play_button.bind(on_press = self.play_waveform) 
        
        HB.add_widget(self.play_button)

        self.exit_button=Button(text='Exit')
        
        self.exit_button.background_color=default_bgnd
        self.exit_button.bind(on_press = self.exit_app) 
        HB.add_widget(self.exit_button)
        
        superBox.add_widget(HB)
        #self.graph = Graph(xlabel='X', ylabel='Y', x_ticks_minor=5,
         #     x_ticks_major=25, y_ticks_major=50,
         #     y_grid_label=True, x_grid_label=True, padding=5,
         #     x_grid=True, y_grid=True, xmin=-0, xmax=500, ymin=0, ymax=200)
        #self.plot = MeshLinePlot(color=[1, 1, 1, 1])
        #self.plot.points = [(x, 50+50*math.sin(x / 10.)) for x in range(0, 501)]
        #self.graph.add_plot(self.plot)
        self.default_graph_waveform()
        superBox.add_widget(self.graph)
        #print(self.plot.points)
        return superBox

    def read_pulse_table(self):
        print("Reading pulse table\n")
        f=open('pulse256.dat', 'rb')
        a=f.read()
        f.close()
        self.pulse256=struct.unpack("256h", a)
        print(self.pulse256)        

    def resample_HR(self, values, heartrate):
        out=[]
        ratio=heartrate/self.baselineHR
        index=range(len(values))
        index0=[]
        x=0
        while(x<(len(values)-1)):
            index0.append(x)
            v=np.interp(x, index, values)
            out.append(v)
            x=x+ratio # advance more slowly in time
        return out

    def default_graph_waveform(self):
        self.graph = Graph(xlabel='t (s) or steps', ylabel='BP (mmHg)', x_ticks_minor=5,
              x_ticks_major=1.0, y_ticks_major=50,
              y_grid_label=True, x_grid_label=True, padding=5,
              x_grid=True, y_grid=True, xmin=-0, xmax=10.0, ymin=0, ymax=240)
        self.plot = MeshLinePlot(color=[1, 1, 1, 1])
        self.plot.points = [(x*0.02, 5) for x in range(0, 501)]
        self.graph.add_plot(self.plot)
        
    def reset_graph_waveform(self):
        self.graph.xmin=0
        self.graph.xmax=10.0
        self.graph.x_ticks_major=1.0
        self.plot.points = [(x*0.02, 5) for x in range(0, 501)]

    def read_pressure_callback(self, x):
        (p,mm,t)=self.pressure.quick_read()
        swp=self.plot.points[self.index]
        copy=(self.index*0.02, mm)
        self.plot.points[self.index]=copy
        self.index=(self.index+1)%500
        self.pressure_label.text="%3.1f mmHg / %2.1f C" % (mm, t)
        
    def home_callback(self,x):
        h=int(self.textinputHomePos.text)
        print("home to %d" % h)
        self.pressure.home(h)
        self.state=None
        self.home_button.text="Home Pos"
        self.home_button.background_color=[0.7, 0.7, 0.7, 1];
        return False

    def calibrate_inc_callback(self,x):
        p=self.pressure.one_calibrate(self.calib_inc, self.calib_delay)
        if(p>=self.calib_max):
            print("End calibrate")
            self.pressure.end_calibrate()
            self.state=None
            self.calib_button.text="Calibrate"
            self.calib_button.background_color=[0.7, 0.7, 0.7, 1];
        else:
            self.home_event = Clock.schedule_once(self.calibrate_inc_callback, 0.0)
        #print(self.calib_index, self.pressure.calib_mmHg, len(self.plot.points))
        self.plot.points[self.calib_index]=(self.pressure.calib_s[self.calib_index], self.pressure.calib_mmHg[self.calib_index])
        #print(self.plot.points)
        self.calib_index=self.calib_index+1
        return False

    def calibrate_start_callback(self,x):
        h=int(self.textinputHomePos.text)
        cm=int(self.textinputCalibMax.text)
        ci=int(self.textinputCalibInc.text)
        
        cd=float(self.textinputCalibDelay.text)
        print("calibrate %d,%d, %d, %f" % (h,cm,ci,cd))
        h0=h;
        x=[h];
        while(h0<=cm):
            h0=h0+ci
            x.append(h0)
        print(x)
        self.graph.xmin=h
        self.graph.xmax=cm
        self.graph.x_ticks_major=100
        self.plot.points = []
        for x0 in x:
            self.plot.points.append((x0, 0))
        #self.graph.add_plot(self.plot)
        
        
        self.pressure.start_calibrate_curve(h, ci)
        self.calib_inc=ci
        self.calib_max=cm
        self.calib_delay=cd
        self.calib_index=0
        self.home_event = Clock.schedule_once(self.calibrate_inc_callback, 0.01)
        return False

    def play_more_callback(self,x):
        out=[]
        for a in range(10):
            R=self.pressure.one_read_timeout()
            if(R is None):
                print("TIMEOUT")
                break
            else:
                s, t, pos = R
                p0=np.interp(pos, self.steps, self.mmHgs)
                
                p1=self.pressure.psi2mmHg(int(s)*self.pressure.pressure_multiplier)
                t1=float(t)*self.pressure.temp_multiplier
                #print(p0,p1)
                out.append(p0)
                out.append(p1)
                self.plot.points[self.play_i]=(self.plot.points[self.play_i][0], p1)
                self.play_i=(self.play_i+1)%500
                self.pressure_label.text="%3.1f mmHg / %2.1f C" % (p1, t1)
        if(self.savef):
            #print(out)
            s=struct.pack("{}f".format(len(out)), *out)
            self.savef.write(s)
        self.play_more_event = Clock.schedule_once(self.play_more_callback, 0.1)   

    def play_calibrate_callback(self,x):
        # first get our waveform parameters
        h=int(self.textinputHomePos.text)
        cm=int(self.textinputCalibMax.text)
        ci=int(self.textinputCalibInc.text)
        systolic=float(self.textinputSystolic.text)
        diastolic=float(self.textinputDiastolic.text)
        heartrate=float(self.textinputHR.text)
        resprate=float(self.textinputRR.text)
         
        cd=float(self.textinputCalibDelay.text)
        print("play calibrate %d,%d, %d" % (h,cm,ci))
        print("Sys %f Dia %f" % (systolic, diastolic))
        (steps0, psi0, mmHg0)=self.pressure.calibrate_curve(h, cm, ci)
        self.steps=np.array(steps0)
        self.psis=np.array(psi0)
        self.mmHgs=np.array(mmHg0)
        # Now branch on whether using pulse_table (single pulse with cyclic indexing),
        # OR - whole waveform repeated. 
        if(USE_PULSE_TABLE):
            print("Down with UPT....")
            v=self.pulse256
            minb=0.0
            maxb=8192.0
            print(minb, maxb)
            span=maxb-minb
            v0=[]
            # now convert to float actual mmHg value cycle
            for b in v:
                x=(float(b)-minb)/span*(systolic-diastolic)+diastolic
                v0.append(x)
            # and now calibrate to the right number of steps
            ys0=[]
            i=0
            while(i <(len(v0))):
                x=v0[i]
                s=round(np.interp(x, self.mmHgs, self.steps))
                ys0.append(s)
                i=i+1
            ys0.append(ys0[0]) # append the first value at the end for wrap-around
            print(ys0)
            self.pressure.write_table(ys0)
            print(heartrate, resprate)
            hrindex=heartrate/60.0*256.0/50.0 # index value per 20ms interval
            rrindex=resprate/60.0*256.0/50.0 # index value per 20ms interval
           # now convert to X.8 format`
            print("Playing table...HR index %f RR index %f\n" % (hrindex, rrindex))
            self.pressure.play_table(round(hrindex*256.0), round(rrindex*256.0), cm, h) 
 

        else: # single recorded waveform sequence, possibly repeated
            print("PLAYING WAVEFORM")
            f=open('TestPulses.dat', 'rb')
            a=f.readlines()
            f.close()
            values=[]
            for l in a:
                x=float(l)
                values.append(x)
       
          
            print("Baseline %f, heartrate %f" % (self.baselineHR, heartrate)) 
            if(not (self.baselineHR==heartrate)):
                print("RESAMPLING @ %f from %f" % (heartrate, self.baselineHR))
                values=self.resample_HR(values, heartrate)
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
                s=round(np.interp(x, self.mmHgs, self.steps))
                i=i+10
                ts.append(t)
                t=t+dt
                ys0.append(s)

            for i in range(runs):
                for y in ys0:
                    ys.append(y)
            print(len(ys))
            print(ys)
            self.pressure.write_waveform(ys)
            self.pressure.play_waveform(-1, cm, h)
            
        #self.pressure.start_reading()
        self.play_i=0
        self.play_button.background_color=[0.7, 0.7, 0.7, 1];
        self.play_button.text="Stop Playing..."
        self.state="PLAY2"
        if(SAVE_FILE):
            self.savef=open(SAVEFILE_NAME, "wb")
        else:
            self.savef=None
        self.play_more_event = Clock.schedule_once(self.play_more_callback, 0)
        return False


        
    def read_pressure(self, button):
        print("READ PRESSURE")
        if(self.state==None):
            self.index=0
            self.state='PRESSURE'
            button.text="Stop Reading\nPressure & Temp"
            button.background_color=[1, 0.5, 0.5, 1];
            self.reset_graph_waveform()
            self.pressure_event = Clock.schedule_interval(self.read_pressure_callback, 0.25)
        elif(self.state=='PRESSURE'):
            self.state=None
            button.text="Read\nPressure & Temp"
            button.background_color=[0.7, 0.7, 0.7, 1];
            self.pressure_event.cancel()


    def home(self, button):
        print("HOME")
        if(self.state==None):
            self.index=0
            self.state='HOME'
            button.text="Going Home"
            button.background_color=[1, 0.5, 0.5, 1];
            self.home_event = Clock.schedule_once(self.home_callback, 0.1)
                 

    def calibrate(self, button):
        print("CALIBRATE")
        if(self.state==None):
            self.state='CALIBRATE'
            button.text="Calibrating..."
            button.background_color=[1, 0.5, 0.5, 1];
            self.home_event = Clock.schedule_once(self.calibrate_start_callback, 0.25)

    def play_stop_callback(self, x):
        print("PLAY STOP CALLBACK")
        if(self.savef):
            self.savef.close()
            self.savef=None
        self.play_more_event.cancel()
        for i in range(10): # drain any old readings
            s=self.pressure.one_read_timeout()
            print(i,s)
            #if(not s):
            #    break
        print("Done draining...")
        #self.pressure.stop_reading()
        self.play_button.text="Play Waveform"
        self.play_button.background_color=[0.7, 0.7, 0.7, 1];
        
        self.play_event.cancel()
        
    def play_waveform(self, button):
        print("PLAY WAVEFORM")
        if(self.state==None):
            self.state='PLAY'
            self.play_button.text="Calibrating..."
            self.play_button.background_color=[1, 0.5, 0.5, 1];
            self.play_event = Clock.schedule_once(self.play_calibrate_callback, 0.25)
        elif(self.state=='PLAY2'):
            print("STOPPING")
            self.pressure.set_params(1)
            print("STOPPING")
            self.state=None
            self.play_button.text="Stopping Waveform"
            self.play_button.background_color=[0.5, 0.5, 1, 1];
            self.play_event = Clock.schedule_once(self.play_stop_callback, 0.25)
            
            

    def exit_app(self, button):
        print("EXIT")
        self.stop()
        self.root_window.close()
        
        

        
root=UIApp()
root.init()
root.run()


    

