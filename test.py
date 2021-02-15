import serial
import time

ser = serial.Serial('COM5', timeout=0.1) # open serial port
print(ser.name)             # check which port was really used


ser.write(b'R')
s=ser.readline()
print(s)
