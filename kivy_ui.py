from finger import Pressure
import time
import numpy as np

import math
import sys
import struct
import pickle
import keyboard
import re

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import Graph, MeshLinePlot
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock

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

    def build(self):
        self.state=None
        self.pressure=Pressure()
        superBox = BoxLayout(orientation ='vertical') 
        HB = BoxLayout(orientation ='horizontal')
        cell1=BoxLayout(orientation='vertical')
        self.textinputHomePos = FloatInput(text='100')
        cell1h=BoxLayout(orientation='horizontal')
        label=Label(text='Home Pos')
        cell1h.add_widget(label)
        cell1h.add_widget(self.textinputHomePos)

        self.textinputCalibMax = FloatInput(text='1500')
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
        textinputHR=FloatInput(text='75.0')
        cell3c.add_widget(label)
        cell3c.add_widget(textinputHR)
        cell3.add_widget(cell3c)
        
        cell3d=BoxLayout(orientation='horizontal')
        label=Label(text='RR')
        textinputRR=FloatInput(text='10.0')
        cell3d.add_widget(label)
        cell3d.add_widget(textinputRR)
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

    def default_graph_waveform(self):
        self.graph = Graph(xlabel='X', ylabel='Y', x_ticks_minor=5,
              x_ticks_major=25, y_ticks_major=50,
              y_grid_label=True, x_grid_label=True, padding=5,
              x_grid=True, y_grid=True, xmin=-0, xmax=500, ymin=0, ymax=240)
        self.plot = MeshLinePlot(color=[1, 1, 1, 1])
        self.plot.points = [(x, 5) for x in range(0, 501)]
        self.graph.add_plot(self.plot)
        
    def reset_graph_waveform(self):
        self.graph.xmin=0
        self.graph.xmax=500
        self.graph.x_ticks_major=25
        self.plot.points = [(x, 5) for x in range(0, 501)]

    def read_pressure_callback(self, x):
        (p,mm)=self.pressure.quick_read()
        swp=self.plot.points[self.index]
        copy=(self.index, mm)
        self.plot.points[self.index]=copy
        self.index=(self.index+1)%500
        self.pressure_label.text="%3.1f mmHg" % mm
        
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
            self.pressure.end_calibrate()
            self.state=None
            self.calib_button.text="Calibrate"
            self.calib_button.background_color=[0.7, 0.7, 0.7, 1];
        else:
            self.home_event = Clock.schedule_once(self.calibrate_inc_callback, 0.0)
        print(self.calib_index, self.pressure.calib_mmHg, len(self.plot.points))
        self.plot.points[self.calib_index]=(self.pressure.calib_s[self.calib_index], self.pressure.calib_mmHg[self.calib_index])
        print(self.plot.points)
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

    def play_calibrate_callback(self,x):
        h=int(self.textinputHomePos.text)
        cm=int(self.textinputCalibMax.text)
        ci=int(self.textinputCalibInc.text)
        systolic=float(self.textinputSystolic.text)
        diastolic=float(self.textinputDiastolic.text)
        cd=float(self.textinputCalibDelay.text)
        print("play calibrate %d,%d, %d" % (h,cm,ci))
        print("Sys %f Dia %f" % (systolic, diastolic))
        (steps0, psi0, mmHg0)=self.pressure.calibrate_curve(h, cm, ci)
        self.steps=np.array(steps0)
        self.psis=np.array(psi0)
        self.mmHgs=np.array(mmHg0)
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
            s=round(np.interp(x, self.mmHgs, self.steps))
            i=i+25
            ts.append(t)
            t=t+dt
            ys0.append(s)

        for i in range(runs):
            for y in ys0:
                ys.append(y)
        print(len(ys))
        self.pressure.write_waveform(ys)
        self.pressure.play_waveform(-1, cm, h)
        self.pressure.start_reading()
        self.play_button.background_color=[0.7, 0.7, 0.7, 1];
        self.play_button.text="Stop Playing..."
        self.state="PLAY2"
        return False


        
    def read_pressure(self, button):
        print("READ PRESSURE")
        if(self.state==None):
            self.index=0
            self.state='PRESSURE'
            button.text="Stop Reading\nPressure"
            button.background_color=[1, 0.5, 0.5, 1];
            self.reset_graph_waveform()
            self.pressure_event = Clock.schedule_interval(self.read_pressure_callback, 0.25)
        elif(self.state=='PRESSURE'):
            self.state=None
            button.text="Read\nPressure"
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
        for i in range(250): # drain any old readings
            s=self.pressure.one_read()   
        self.pressure.stop_reading()
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
            self.pressure.set_params(self.pressure.meansteps, 7500, 1)
            self.state=None
            self.play_button.text="Stopping Waveform"
            self.play_button.background_color=[0.5, 0.5, 1, 1];
            self.play_event = Clock.schedule_once(self.play_stop_callback, 0.25)
            
            

    def exit_app(self, button):
        print("EXIT")
        self.stop()
        self.root_window.close()
        
        

        
root=UIApp()
root.run()


    

