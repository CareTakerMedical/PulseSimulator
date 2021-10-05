// Copyright (c) 2021, Caretaker Medical, All rights reserved

#include <stdio.h>
#include <string.h>
#include <timer.h>
#include <platform.h>
#include <print.h>
#include <xs1.h>
#include "i2c.h"
#include "ps_indicators.h"

//void printd(chanend c_channel, const char * msg);

// Pressure
//on tile[0]: out port p_reset = MPR_RESET;
//on tile[0]: in port p_eoc = MPR_INTERRUPT;

// Outputs
on tile[0]: out port p_gecko = GECKO_PORT;
on tile[0]: out port p_ps_ctrl = HSC_POWER_CTRL;

// Inputs
on tile[0]: in port p_flimit = FAR_LIMIT;
on tile[0]: in port p_nlimit = NEAR_LIMIT;

// Limits
int near_limit(void)
{
    int x;
    timer tmr;
    unsigned int t;
    p_nlimit :> x;
    if (x == 0) {
	tmr :> t;
	tmr when timerafter(t + 1000) :> void; // 10us
	p_nlimit :> x;
    }
    return (x==0);
}

int far_limit(void)
{
    int x;
    timer tmr;
    unsigned int t;
    p_flimit :> x;
    if (x == 0) {
	tmr :> t;
	tmr when timerafter(t + 1000) :> void; // 10us
    }
    p_flimit :> x;
    return (x==0);
}

// step in this direction, return true if prevented by a limit
int step(int dir,int speed)
{
    timer tmr;
    unsigned int t0,t;
    if(dir == STEP_NEAR){ // handle near limit switch
         if(near_limit()){
             return 1;
         }
     }
     else {
         if(far_limit()){
             return 1;
         }
    }

    // Do a sanity check on 'speed'
    speed = (speed < MIN_STEP_TIME) ? MIN_STEP_TIME : speed;

    p_gecko <: (dir) ? GECKO_DIR : 0;
    tmr :> t0;
    t = t0;
    t += 50; // 50*10ns = 0.5us
    tmr when timerafter(t) :> void;
    p_gecko <: (dir) ? (GECKO_DIR | GECKO_STEP) : GECKO_STEP;
    t += 400; // 400*10ns = 4.0us
    tmr when timerafter(t) :> void;
    p_gecko <: (dir) ? GECKO_DIR : 0;
    tmr when timerafter(t0 + speed) :> void;
    return 0;
}

int take_measurement(client interface i2c_master_if i2c)//, chanend c_measurement_mgr_debug)
{
	i2c_regop_res_t result;
	char data[2];
	unsigned int t;
	timer tmr;
	int read_attempts = 0;
	unsigned int pressure = 0;

	while (read_attempts < MAX_READ_ATTEMPTS) {
		result = i2c.read(PRESS_SENSE_I2C_ADDR, data, 2, 1);
		// First, check to make sure that the read itself was ok.
		if (result != I2C_ACK) {
			//printd(c_measurement_mgr_debug,"I2C checking measurement status returned an error.\n");
			return (0xFF << 24);
		}
		// If at this point, we can assume that the I2C transaction was successful, so check
		// the status bits.
		if ((data[0] >> 6) > 0) {
			// It's possible we tried to do this too soon...  delay a bit and then try again.
			++read_attempts;
			tmr :> t;
			tmr when timerafter(t + 250000) :> void;
		}
		else {
			// We were successful.  Calculate pressure value and send it off.
			pressure = ((data[0] & 0x3F) << 8) + data[1];
			return pressure;
		}
	}
	// If we got to this point, we exceeded the maximum number of reads without a successful
	// transfer, so return an error value.
	//printd(c_measurement_mgr_debug,"Measurement status never returned 0.\n");
	return (0xFF << 24);
}

void measurement_mgr(client interface i2c_master_if i2c, chanend c_mode, chanend c_pos_req_cfg, chanend c_pos_req_wf, chanend c_press_data, chanend c_mm_ready, chanend c_mm_fault)
{
	// Mode-related variables
	int mode = MODE_IDLE;
	int new_pos = 0;
	int pos_req = 0;
	int pos = 0;
	int speed = 0;
	int count = 0;

	// Stepper-related variables
	int hazard = 0;
	int settling_time = 0;
	p_gecko <: 0;

	// Other variables
	unsigned int t;
	timer tmr;
	int new_reading = 0;

	p_ps_ctrl <: 0;


	// Furthermore, if we're using the Honeywell breakout board, EOC will not be connected.  To
	// be compatible with any board that uses the sensor, enable eoc with a pull-down, and
	// then either wait for a rising edge (if that pin is connected), or 5ms.  One of the events
	// should happen either way.
	//set_port_pull_down(p_eoc);

	while(1){
		select {
			case c_mode :> mode : {
				if (mode == MODE_READ_ONLY) {
					new_reading = 1;
					settling_time = 0;
				}
				break;
			}
			case ((mode > MODE_READ_ONLY) && (mode < MODE_WAVEFORM)) => c_pos_req_cfg :> speed: {
				// Once we have the speed, next we take in the position request
				c_pos_req_cfg :> pos_req;
				c_pos_req_cfg :> settling_time;
				// Based on the mode, calculate where to go to next; if 
				switch (mode) {
					case MODE_SET_HOME: {
					    count = 0;
					    while (count < MAX_STEP_COUNT) {
					        if (step(STEP_NEAR,MIN_STRIDE_TIME))
					            break;
					        count++;
					    }
					    if (count < MAX_STEP_COUNT) {
					        pos = 0;
					        new_pos = pos_req;
					    }
					    else {
					        // We never made it to the home limit, so there's a problem...
					        c_mm_fault <: count;
					    }
					    break;
					}
					case MODE_GO_HOME: { new_pos = pos_req; break; }
					default: { new_pos = pos + pos_req; break; }
				}
				break;
			}
			// Originally, these cases were only valid when in a playback mode; however, leave open the possibility
			// that the waveform calculator will want to send us home in the IDLE state as well.
			case ((mode == MODE_IDLE) || (mode >= MODE_WAVEFORM)) => c_pos_req_wf :> speed: {
			    c_pos_req_wf :> pos_req;
			    c_pos_req_wf :> settling_time;
			    new_pos = pos_req;
			    break;
			}
			default: {
				// Move to where we need to go
			    if (pos != new_pos) {
				    while (pos != new_pos) {
						if (new_pos > pos) {
							hazard = step(STEP_FAR,speed);
							if (hazard)
								break;
							pos++;
						}
						else {
							hazard = step(STEP_NEAR,speed);
							if (hazard)
								break;
							pos--;
						}
					} // ends while
					new_reading = 1;
					if (settling_time > 0) {
						tmr :> t;
						tmr when timerafter(t + settling_time) :> void;
					}
					c_mm_ready <: 1;
				}
				if (new_reading > 0) {
					c_press_data <: (settling_time < 0) ? (-1 * pos) : pos;
					c_press_data <: take_measurement(i2c);//,c_measurement_mgr_debug);
					new_reading = 0;
				}
				break;
			} // ends default
		} // ends select
	} // ends while
} // ends measurement_mgr

