// Copyright (c) 2021, Caretaker Medical, All rights reserved

#include <platform.h>
#include <print.h>
#include <xs1.h>
#include <timer.h>
#include "ps_indicators.h"

//void printd(chanend c_channel, const char * msg);

extern signed short sine_table_bp[257];
extern signed short sine_table_hr[257];

{int,int} calculate_mean_and_range(int * wf_pts, int wf_size)
{
	int pt;
	int i = 0;
	int sum = 0;
	int min = 0x1FFFFFFF;
	int max = 0;
	int mean, range;
	for (i = 0; i < wf_size; i++) {
		pt = *wf_pts;
		sum += pt;
		if (pt < min)
			min = pt;
		if (pt > max)
			max = pt;
		wf_pts++;
	}
	if ((wf_size > 0) && ((max - min) > 0)) {
	    mean = sum / wf_size;
	    range = max - min;
	    return {mean,range};
	}
	return {0,0};
}

void wf_calc(chanend c_wf_mode, chanend c_wf_data, chanend c_wf_params, chanend c_pos_req_wf, chanend c_mm_ready)// chanend c_wf_calc_debug)
{
	int heart_rate[2];
	int resp_rate[2];
	int calmax[2];
	int home[2];
	int wf_pts[2][1024];
	int wf_size[2] = {0,0};
	int tstate, twf_pt, tcfg;
	int mean, range;
	int wave_index = 0;
	int resp_index = 0;
	timer tmr;
	int mm_ready = 0;
	unsigned int tnext, t0, t;
	int deltat, tstep;
	int ind, frac;
	int currentp, nextp, deltap;
	int rrhr, rrbp;
	int state = WF_IDLE;
	int playing = 0;
	int go_home = 0;
	int load_i = 0;
	int pb_i = 1;

	while (1) {
		select {
		    	case c_mm_ready :> mm_ready : {
		    	mm_ready = 0;
				if (playing) {
					// At some point, I'll need to worry about 'waveform' playback,
					// but for now I'll just deal with the pulse table.
				    while (1) {
				        tnext += 2000000;
				        ind = wave_index >> 8;
				        frac = wave_index & 0xFF;
				        nextp = (wf_pts[pb_i][ind]*(256-frac)+wf_pts[pb_i][(ind + 1)]*frac) >> 8;
				        ind = resp_index >> 8;
				        frac = resp_index & 0xFF;
				        rrbp = (sine_table_bp[ind]*(256-frac)+sine_table_bp[(ind + 1)]*frac) >> 8;
				        rrbp = (rrbp * range) >> 13;
				        nextp += rrbp;
				        rrhr = (sine_table_hr[ind]*(256-frac)+sine_table_hr[(ind + 1)]*frac) >> 8;
				        wave_index += (heart_rate[pb_i] * rrhr) >> 8;
				        wave_index &= 0xFFFF;
				        resp_index += resp_rate[pb_i];
				        resp_index &= 0xFFFF;
				        // Calculate the next time step and indices
				        tmr :> t0;
				        tstep = tnext - t0;
				        if (tstep <= 0) {
				            // Something has taken longer than 20ms, we need to play catch up
				            tnext = t0 + 2000000;
				            tstep = 0;
				        }
				        deltap = nextp - currentp;
				        currentp = nextp;
				        if (deltap == 0) {
				            tmr :> t;
				            tmr when timerafter(t + 2000000) :> void;
				        }
				        else {
				            deltat = (tstep / deltap) * ((deltap > 0) ? 1 : -1);
				            c_pos_req_wf <: deltat;  // Speed
				            c_pos_req_wf <: nextp;  // Position
				            c_pos_req_wf <: 0;  // Settling time
				            break;
				        }
					}
				}// ends if
				else {
				    if (go_home) {
				        c_pos_req_wf <: MIN_STRIDE_TIME; // Speed
				        c_pos_req_wf <: home[pb_i]; // Position
				        c_pos_req_wf <: -1; // We indicate this is the last point by using a negative number
				        go_home = 0;
				    }
				}
				break;
			}
			case c_wf_mode :> tstate : {
				// Going to WF_IDLE will always be legal, so make sure if 'playing' is
				// active, then set it to 0
				if (tstate == WF_IDLE) {
					state = tstate;
					if (playing) {

						playing = 0;
						go_home = 1;
					} // ends if playing
				} // ends if
				else {
				    // Check to make sure that the transition state is legal given our
				    // current state.
				    switch (state) {
					    case WF_IDLE: {
					        // When transitioning from this state, the only valid
					        // next state is 'WF_LOAD'.  Other states will result
					        // in no action.
					        if (tstate == WF_LOAD)
					            state = tstate;
					        break;
					    } // ends case WF_IDLE
					    case WF_LOAD: {
					        // When transitioning from this state, we can go back
					        // to WF_IDLE (kind of pointless), or we can go forward
					        // to WF_END_LOAD.
					        if (tstate == WF_END_LOAD) {
					            state = tstate;
					            c_wf_mode <: wf_size[load_i];
					            pb_i = load_i;
					            load_i = (load_i > 0) ? 0 : 1;
					            // This is also where we'll do some initialization
					            // before diving in to the playback portion.
					            {mean,range} = calculate_mean_and_range(wf_pts[pb_i],wf_size[pb_i]);
					        } // ends tstate == WF_END_LOAD
					        break;
					    } // ends case WF_LOAD
					    case WF_END_LOAD: {
					        // Transitioning from this state to WF_IDLE is pointless,
					        // but legal; transitioning to the playback state will
					        // push us into the playback loop.
					        if ((tstate != WF_LOAD) && (tstate != WF_END_LOAD)) {
					            // The only states left are the playback states.
					            // At this point, set the state and turn on playback
					            state = tstate;
					            playing = 1;
					            currentp = wf_pts[pb_i][0];
					            wave_index = heart_rate[pb_i];
					            resp_index = resp_rate[pb_i];
					            c_pos_req_wf <: MIN_STRIDE_TIME; // Speed
					            c_pos_req_wf <: currentp; // Position
					            c_pos_req_wf <: 100000000; // Settling time
					            tmr :> t0;
					            tnext = t0 + 100000000;  // 20ms window
					        }
					        break;
					    } // ends case WF_END_LOAD
					    default: {
					        // The cases left are the two playback cases.  We can
					        // transition to 'WF_IDLE', which has already been
					        // covered, or we can transition to 'WF_LOAD'.  Other
					        // transitions will be disallowed
					        if (tstate == WF_LOAD)
					            state = tstate;
					        break;
					    } // ends default
				    } // ends switch
				} // ends else
				break;
			} // ends case
			case (state == WF_LOAD) => c_wf_data :> twf_pt : {
				if (wf_size[load_i] < 1024)
					wf_pts[load_i][wf_size[load_i]++] = twf_pt;
				break;
			}
			case ((state == WF_LOAD) || (state == WF_IDLE)) => c_wf_params :> tcfg : {
				// Determine which parameter has come in based on the LSNibble.
				switch (tcfg & 0x0F) {
					case HOME_ID:
						home[load_i] = tcfg >> 4;
						break;
					case HR_ID:
						heart_rate[load_i] = tcfg >> 4;
						break;
					case RR_ID:
						resp_rate[load_i] = tcfg >> 4;
						break;
					case CALMAX_ID:
						calmax[load_i] = tcfg >> 4;
						break;
					default:
						break;
				} // ends switch
				break;
			}// ends case
			// The next part is the behavior if we don't have an event come in
			default: break;
		} // ends select
	} // ends while
}
