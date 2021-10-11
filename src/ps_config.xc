// Copyright (c) 2021, Caretaker Medical, All rights reserved

#include <stdio.h>
#include <string.h>
#include <print.h>
#include "xud_cdc.h"
#include "ps_indicators.h"
#include "ps_version.h"

//void printd(chanend c_channel, const char * msg);

int readint(client interface usb_cdc_interface cdc)
{
    char value;
    int d=0;
    int neg=0;
    int abytes = 0;

    abytes = cdc.available_bytes();
    while(abytes > 0){
    	value=cdc.get_char();
        if(value=='\n'){
            break;
        }else{
            if((value>='0')&&(value<='9')){
                d=d*10+(value-'0');
            }else{
                if(value=='-'){
                    neg=1;
                }
            }
        }
	abytes = cdc.available_bytes();
    }
    if(neg){
        d=-d;
    }
    return d;
}

int perform_handshake(client interface usb_cdc_interface cdc, int timeout)
{
	timer tmr;
	int t = 0;
	int timer_expired = 0;
	int handshake_complete = 0;
	char nbyte = '0';

	tmr :> t;
	while ((!timer_expired) && (!handshake_complete)) {
		select {
			case tmr when timerafter(t + timeout) :> void : { timer_expired = 1; break; }
			default: {
				if (cdc.available_bytes() > 0) {
					nbyte = cdc.get_char();
					if (nbyte == '\n') {
						handshake_complete = 1;
						cdc.flush_buffer();
					}
					else if (nbyte == '!') {
						cdc.flush_buffer();
						return -1;
					}
				}
				break;
			}
		}
	}
	return handshake_complete;  // '0' if timed out, '1' otherwise
}

int handshake_cmd(client interface usb_cdc_interface cdc, char cmd)
{
	char nbuf[128];
	unsigned int len;
	int ret = 0;
	int param = 0;
	switch (cmd) {
		case 'E':
		case 'G':
		case 'R':
		case 'S':
		case 'T':
		case 'W': {
			// Next byte needs to be '\n', otherwise the command is misformed.
			nbuf[0] = cdc.get_char();
			if (nbuf[0] != '\n') 
				return -1;
			len = sprintf(nbuf,"%c\n",cmd);
			cdc.write(nbuf,len);
			ret = perform_handshake(cdc,300000000);
			break;
		}
		case 'B': 
		case 'C': 
		case 'H': 
		case 'I': 
		case 'Y': 
		case 'Z': {
			// Collect bytes until we hit '\n'.
			param = readint(cdc);
			len = sprintf(nbuf,"%c%d\n",cmd,param);
			cdc.write(nbuf,len);
			if (perform_handshake(cdc,300000000) > 0)
				ret = param;
			break;
		}
			
	}
	return ret;
}

void ps_config(client interface usb_cdc_interface cdc, chanend c_mode, chanend c_pos_req_cfg, chanend c_wf_mode, chanend c_wf_data, chanend c_wf_params, chanend c_data_mode, chanend c_data_status, chanend c_mm_fault, chanend c_wf_switch)
{
	int busy = 0;
	int data_status = 0;
	int wf_length = 0;
	int home = 0;
	int thome = 0;
	int tinc = 0;
	int pb_stop = 0;
	int mm_step_count = 0;
	int request_length = 0;
	int crossing_index = 0;
	unsigned int length;
	char pbuf[128];

	while(1){
		select{
		    case c_wf_switch :> crossing_index : {
		        length = sprintf(pbuf,"OK: Waveform playback has begun, crossing_index = %d.\n",crossing_index);
		        cdc.write(pbuf,length);
		        break;
		    }
		    case c_mm_fault :> mm_step_count : {
		        busy = 0;
		        c_mode <: MODE_IDLE;
		        c_data_mode <: MODE_IDLE;
		        length = sprintf(pbuf,"ERR: Maximum step count!\n");
		        cdc.write(pbuf,length);
		        break;
		    }
			case c_data_status :> data_status : {
			    c_mode <: MODE_IDLE;
			    c_data_mode <: MODE_IDLE;
			    if (data_status > 0)
			        length = sprintf(pbuf,"ERR: Overflow detected, waveform playback will stop if playing.\n");
			    else if (data_status < 0)
			        length = sprintf(pbuf,"ERR: Pressure sensor status error.\n");
			    else {
			        if (pb_stop) {
			            pb_stop = 0;
			            length = 0;
			        }
			        else
			            length = sprintf(pbuf,"OK: Data ready\n");
			    }
			    busy = 0;
			    if (length > 0)
			        cdc.write(pbuf,length);
			    break;
			}
			case (request_length > 0) => c_wf_mode :> wf_length : {
				length = sprintf(pbuf,"OK: Buffer length = %d\n",wf_length);
				cdc.write(pbuf,length);
				request_length = 0;
				break;
			}
			default: {
				// Look for characters; don't do anything if we're busy.
				if (cdc.available_bytes()) {
					pbuf[0] = cdc.get_char();
					if (busy != 0) {
					    length = sprintf(pbuf,"ERR: Busy.\n");
					    cdc.write(pbuf,length);
					}
					else {
						if (pbuf[0] == 'G') {
						    	if (handshake_cmd(cdc,'G') > 0) {
						    	    // Go to the home position without going back
						    	    // to '0' first.
						    	    busy = 1;
						    	    c_data_mode <: MODE_GO_HOME;
						    	    c_mode <: MODE_GO_HOME;
						    	    c_pos_req_cfg <: MIN_STRIDE_TIME; // Speed
						    	    c_pos_req_cfg <: home; // Position
						    	    c_pos_req_cfg <: 0; // Settling time
						    	}
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'G'\n");
						}
						// Set home instruction
						else if (pbuf[0] == 'Z') {
							// Need more information, so we'll grab
							// characters until we're out of numbers and
							// create an int.
							thome = handshake_cmd(cdc,'Z');
							if (thome > 0) {
								busy = 1;
								c_data_mode <: MODE_SET_HOME;
								c_mode <: MODE_SET_HOME;
								home = thome;
								c_wf_params <: (home << 4) | HOME_ID;
								c_pos_req_cfg <: MIN_STRIDE_TIME;  // Speed
								c_pos_req_cfg <: home;  // Position
								c_pos_req_cfg <: 0;  // Settling time
							}
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'Z'\n");
						}
						// Read instruction
						else if (pbuf[0] == 'R') {
							if (handshake_cmd(cdc,'R') > 0) {
								busy = 1;
								c_data_mode <: MODE_READ_ONLY;
								c_mode <: MODE_READ_ONLY;
							}
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'R'\n");
						}
						// Increment position instruction
						else if (pbuf[0] == 'I') {
							tinc = handshake_cmd(cdc,'I');
							if (tinc > 0) {
								busy = 1;
								c_data_mode <: MODE_INCREMENT;
								c_mode <: MODE_INCREMENT;
								c_pos_req_cfg <: MIN_STRIDE_TIME; // Speed
								c_pos_req_cfg <: tinc; // Position
								c_pos_req_cfg <: 0; // Settling time
							}
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'I'\n");
						}
						// Signal to wf_calc that a new waveform is to be loaded
						else if (pbuf[0] == 'W') {
							if (handshake_cmd(cdc,'W') > 0) {
								c_wf_mode <: WF_LOAD;
							}
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'W'\n");
						}
						// Waveform "Y" value
						else if (pbuf[0] == 'Y') {
							tinc = handshake_cmd(cdc,'Y');
							if (tinc > 0)
								c_wf_data <: tinc;
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'Y'\n");
						}
						// End the waveform load
						else if (pbuf[0] == 'E') {
							if (handshake_cmd(cdc,'E') > 0) {
								request_length = 1;
								c_wf_mode <: WF_END_LOAD;
							}
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'E'\n");
						}
						// Heartrate parameter load
						else if (pbuf[0] == 'H') {
							tinc = handshake_cmd(cdc,'H');
							if (tinc > 0) 
								c_wf_params <: (tinc << 4) | HR_ID;
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'H'\n");
						}
						// Respiration rate parameter load
						else if (pbuf[0] == 'B') {
							tinc = handshake_cmd(cdc,'B');
							if (tinc > 0)
								c_wf_params <: (tinc << 4) | RR_ID;
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'B'\n");
						}
						// Calibrated maximum parameter load
						else if (pbuf[0] == 'C') {
							tinc = handshake_cmd(cdc,'C');
							if (tinc > 0)
								c_wf_params <: (tinc << 4) | CALMAX_ID;
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'C'\n");
						}
						// Playback the active, loaded waveform
						else if (pbuf[0] == 'T') {
							if (handshake_cmd(cdc,'T') > 0) {
								c_data_mode <: MODE_WAVEFORM;
								c_mode <: MODE_WAVEFORM;
								c_wf_mode <: WF_PLAY_PT;
							}
							//else
								//printd(c_ps_config_debug,"Handshake failed, initial command = 'T'\n");
						}	
						// Stop playback
						else if (pbuf[0] == 'S') {
							if (handshake_cmd(cdc,'S') > 0) {
							    pb_stop = 1;
							    c_wf_mode <: WF_IDLE;
							}
						}	
						else if (pbuf[0] == 'O') {
							busy = 1;
							c_data_mode <: MODE_OVERRIDE;
							c_mode <: MODE_OVERRIDE;
							c_pos_req_cfg <: MIN_STRIDE_TIME;
							c_pos_req_cfg <: readint(cdc);
						}
						else if (pbuf[0] == '?') {
							length = sprintf(pbuf,"Interface: config\n");
							cdc.write(pbuf,length);
							//printd(c_ps_config_debug,"Interface query complete\n");
							//printd(c_ps_config_debug,"Interface query complete again\n");
						}
						else if (pbuf[0] == 'V') {
						    if (DIRTY)
						        length = sprintf(pbuf,"Version: %c%c%c%c%c%c%c%c%c\n",fw_version[0],fw_version[1],fw_version[2],fw_version[3],fw_version[4],fw_version[5],fw_version[6],fw_version[7],'+');
						    else
						        length = sprintf(pbuf,"Version: %c%c%c%c%c%c%c%c\n",fw_version[0],fw_version[1],fw_version[2],fw_version[3],fw_version[4],fw_version[5],fw_version[6],fw_version[7]);
						    cdc.write(pbuf,length);
						}
						else {
							cdc.flush_buffer();
						}
						// Other stuff will come later...
					} // ends cdc.available_bytes
				} // ends busy
				break;
			} // ends default
		} // ends select
	} // ends while
}
