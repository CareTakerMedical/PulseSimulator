// Copyright (c) 2021, Caretaker Medical, All rights reserved

#include <stdio.h>
#include <string.h>
#include <timer.h>
#include <print.h>
#include "xud_cdc.h"
#include "ps_indicators.h"

void ps_data(client interface usb_cdc_interface cdc, chanend c_data_mode, chanend c_data_status, chanend c_press_data)
{
	unsigned int t = 0;
	unsigned int tms = 0;
	int timer_on = 0;
	int ready = 0;
	timer tmr;
	int mode = MODE_IDLE;
	int data = 0;
	int store_pos = 0;
	int index = 0;
	int pos = 0;
	unsigned int pressure = 0;
	char mode_header;
	char packet[32];
	unsigned length = 0;
	int wlen = 0;
	while(1){
		select{
			case timer_on => tmr when timerafter(t + 100000) :> t: {
				tms++;
				break;
			}
			case c_data_mode :> mode : {
				ready = 1;
				store_pos = 0;
				if (mode != MODE_WAVEFORM) {
				    timer_on = 0;
				    tms = 0;
				}
				switch (mode) {
					case MODE_SET_HOME:
						mode_header = 'H';
						store_pos = 1;
						break;
					case MODE_GO_HOME:
					case MODE_READ_ONLY:
						mode_header = 'R';
						break;
					case MODE_INCREMENT:
						mode_header = 'I';
						store_pos = 1;
						break;
					case MODE_OVERRIDE:
						mode_header = 'O';
						break;
					case MODE_WAVEFORM:
						mode_header = 'W';
						store_pos = 1;
						break;
					default:
						ready = 0;
						mode_header = '0';
						break;
				}
				break;
			}
			case ready => c_press_data :> pos : {
				// Package up a header and send it on its way; if 'write' comes back
				// with fewer bytes than we sent, than we're overflowing and we
				// probably need to shut down anything that might be running.  First
				// thing that needs to happen though is we need to wait for the data
				// to come in on the next transaction.  At that point, we check the
				// 'status' portion of the returned value and make sure everything
				// is ok.  If not, we change the mode_header on the packet we send out
				// and we let 'ps_config' know that there was a problem.

				c_press_data :> data;

				// Check the status
				if ((data >> 24) == 0xFF) {
				    // We've got ourselves an error...
				    c_data_status <: -1;
				}
				else {

				    // We'll do the pressure conversion here;  breakout board MUST be the
				    // following in order for this to work:  MPRLS0300YG00001BB.  See page
				    // 19 for the equations on how to calculate pressure.  The calculation
				    // is performed in steps so as to not overflow.
				    pressure = data - HSC_OUTPUT_MIN; // First step
				    pressure *= HSC_RANGE; // Second step
				    pressure /= (HSC_OUTPUT_MAX - HSC_OUTPUT_MIN); // Last step

				    // Ok, so now that we have all of the information, we grab the
				    // timestamp.
				    length = sprintf(packet,"%c,%d,%d,%d\n",mode_header,((store_pos) ? pos : index++),tms,pressure);
				    wlen = cdc.write(packet,length);
				    if (wlen < length)
				        c_data_status <: wlen + 1;
				    // Depending on mode, and if tms was 0, we'll start up a timer here.
				    if (mode_header == 'W') {
				        if (timer_on == 0) {
				            timer_on = 1;
				            tmr :> t;
				        }
				        if (pos < 0)
				            c_data_status <: 0;
				    }
				    else {
				        // These other modes inform 'ps_config' when new data has been
				        // collected and sent; must send '0' to open back up the
				        // communication interface.
				        c_data_status <: 0;
				    }
				}
				break;
			}
			default: {
				// Check to see if there are any commands that have come in over the
				// interface.
				if (cdc.available_bytes()) {
					packet[0] = cdc.get_char();
					if (packet[0] == '?') {
						length = sprintf(packet,"Interface: data\n");
						cdc.write(packet,length);
					}
				}
				break;
			}
		} // ends select
	} // ends while
} // ends function
