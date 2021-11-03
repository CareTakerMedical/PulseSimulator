// Copyright (c) 2021, Caretaker Medical, All rights reserved

#include <stdio.h>
#include <string.h>
#include <print.h>
#include <quadflash.h>
#include <quadflashlib.h>
#include "xud_cdc.h"
#include "ps_indicators.h"
#include "ps_version.h"

on tile[0]: port p_led = DEBUG_LEDS;

void chip_reset();

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
		case 'F':
		case 'G':
		case 'Q':
		case 'R':
		case 'S':
		case 'T':
		case 'V':
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

fl_QSPIPorts spiPorts = {
        PORT_SQI_CS,
        PORT_SQI_SCLK,
        PORT_SQI_SIO,
        on tile[0]: XS1_CLKBLK_1
};

int perform_dfu(client interface usb_cdc_interface cdc)
{
    char dbuf[256];
    char hsbuf[256];
    int result = 0;
    int i = 0;
    unsigned int length = 0;
    int fw_length = 0;
    int rlen = 256;
    char cksum = 0;
    int npages = 0;
    int nbytes = 0;
    timer tmr;
    unsigned int t = 0;
    fl_BootImageInfo bii;

    // Connect to the flash
    result = fl_connect(spiPorts);
    if (result)
        return FU_ERR_COULD_NOT_OPEN_FLASH;

    // Get the factory boot image info
    result = fl_getFactoryImage(bii);
    if (result) {
        // Disconnect, then return an error
        fl_disconnect();
        return FU_ERR_FACTORY_IMG_ID;
    }

    // Get the next boot image
    tmr :> t;
    i = 0;
    result = 1;
    while (result && (i < 1000)) {
        result = fl_getNextBootImage(bii);
        i++;
        tmr when timerafter(t + 1000000) :> t;
    }
    if (result) {
        fl_disconnect();
        return FU_ERR_BOOT_IMG_ID;
    }

    // First, get the overall length that we should expect.  Use four bytes, even though that would be absurd.
    for (i = 0; i < 5; i++) {
        while (cdc.available_bytes() == 0);
        dbuf[i] = cdc.get_char();
    }

    if (dbuf[4] != '\n') {
        return FU_ERR_INCORRECT_LENGTH_FORMAT;
    }

    // Do handshake on the length, make sure we agree.  Calculate the integer length and send it back
    i = 3;
    while (i >= 0)
        fw_length = (fw_length << 8) + dbuf[i--];
    length = sprintf(hsbuf,"L=%d\n",fw_length);
    cdc.write(hsbuf,length);

    // If we're correct, get a response of 'Y'.  Otherwise, return an error
    while (cdc.available_bytes() == 0);
    hsbuf[0] = cdc.get_char();
    if (hsbuf[0] != 'Y')
        return FU_ERR_LENGTH_DISCREPANCY;

    // Prep the device for writing the image pages.  Set the maximum length to 256 * the number of pages that will
    // be required to write the whole image.
    npages = (fw_length / 256) + 1;
    nbytes = npages * 256;
    result = 1;
    i = 0;
    tmr :> t;
    while (result && (i < 1000)) {
        result = fl_startImageReplace(bii,nbytes);
        i++;
        tmr when timerafter(t + 1000000) :> t;
    }
    if (result) {
        fl_disconnect();
        return FU_ERR_FLASH_IMG_INIT;
    }

    // Once we have the length, we'll start bringing in the data 256 bytes at a time; this is the page size for the flash
    while (fw_length > 0) {
        // If we're below 'fw_length-256', then we'll request 256 bytes; if not, then we'll read the remaining length.
        // While doing this exercise, calculate a checksum.
        rlen = ((fw_length - 256) >= 0) ? 256 : fw_length;
        cksum = 0;
        for (i = 0; i < rlen; i++) {
            while (cdc.available_bytes() == 0);
            dbuf[i] = cdc.get_char();
            cksum += dbuf[i];
            // Through away the carry...
            cksum &= 0x0FF;
        }
        // If rlen did not equal 256, fill the rest of the buffer with 0's.
        for (i = 0; i < (256 - rlen); i++)
            dbuf[(i + rlen)] = 0;
        fw_length -= rlen;
        cksum = ~cksum;
        length = sprintf(hsbuf,"CKSUM=%d\n",cksum);
        cdc.write(hsbuf,length);

        // Again, if we're correct, we'll get a response of 'Y'.  Otherwise, return an error
        while (cdc.available_bytes() == 0);
        hsbuf[0] = cdc.get_char();
        if (hsbuf[0] != 'Y')
            return FU_ERR_CKSUM_DISCREPANCY;

        // We have a page's worth of data at this point
        tmr :> t;
        i = 0;
        result = 1;
        while (result && (i < 1000)) {
            result = fl_writeImagePage(dbuf);
            i++;
            tmr when timerafter(t + 1000000) :> t;
        }
        if (result) {
            printstrln("Got here, bad result from 'fl_writeImagePage'");
            fl_disconnect();
            return FU_ERR_IMG_WRITE_PAGE;
        }
    }
    // Now that we've gotten to this point, everything should be written, so issue a command saying that we've successfully written everything.
    tmr :> t;
    i = 0;
    result = 1;
    while (result && (i < 1000)) {
        result = fl_endWriteImage();
        i++;
        tmr when timerafter(t + 1000000) :> t;
    }
    if (result) {
        printstrln("Got here, bad result from 'fl_endWriteImage'");
        fl_disconnect();
        return FU_ERR_WRITE_TERM;
    }

    // I think this means we're done?
    fl_disconnect();
    return 0;
}

void ps_config(client interface usb_cdc_interface cdc, chanend c_mode, chanend c_pos_req_cfg, chanend c_wf_mode, chanend c_wf_data, chanend c_wf_params, chanend c_data_mode, chanend c_data_status, chanend c_mm_fault, chanend c_wf_switch, chanend c_alive)
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
	int wf_playing = 0;
	int ided = 0;
	int fw_ret = 0;
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
				    wf_playing = 0;
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
					if (ided)
						c_alive <: 1;
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
								wf_playing = 1;
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
							ided = 1;
							length = sprintf(pbuf,"Interface: config\n");
							cdc.write(pbuf,length);
						}
						else if (pbuf[0] == 'V') {
						    if (handshake_cmd(cdc,'V') > 0) {
						        if (DIRTY)
						            length = sprintf(pbuf,"Version: %c%c%c%c%c%c%c%c%c\n",fw_version[0],fw_version[1],fw_version[2],fw_version[3],fw_version[4],fw_version[5],fw_version[6],fw_version[7],'+');
						        else
						            length = sprintf(pbuf,"Version: %c%c%c%c%c%c%c%c\n",fw_version[0],fw_version[1],fw_version[2],fw_version[3],fw_version[4],fw_version[5],fw_version[6],fw_version[7]);
						        cdc.write(pbuf,length);
						    }
						}
						else if (pbuf[0] == 'F') {
						    if (handshake_cmd(cdc,'F') > 0) {
						        c_alive <: 0; // Turn off watchdog
						    	if (wf_playing) {
						    	    pb_stop = 1;
						    	    c_wf_mode <: WF_IDLE;
						    	    while (wf_playing);
						    	}
						    	else {
						    	    c_data_mode <: MODE_IDLE;
						    	    c_mode <: MODE_IDLE;
						    	    c_wf_mode <: WF_IDLE;
						    	}
						    	// Set the LED to be on, and then issue the command to reset the USB interface; the rest of the app should be sitting idle by now.
						    	p_led <: USB_DFU;
						    	fw_ret = perform_dfu(cdc);
						    	if (fw_ret)
						    	    length = sprintf(pbuf,"ERR: %d\n",fw_ret);
						    	else
						    	    length = sprintf(pbuf,"OK: Type 'Q' to reboot\n");
						    	p_led <: USB_NORMAL;
						    	cdc.write(pbuf,length);
						    }
						}
						else if (pbuf[0] == 'Q') {
						    if (handshake_cmd(cdc,'Q') > 0)
						        chip_reset();
						}
						else {
							cdc.flush_buffer();
						} // else
					} // ends cdc.available_bytes
				} // ends busy
				break;
			} // ends default
		} // ends select
	} // ends while
}
