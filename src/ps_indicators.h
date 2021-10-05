// Copyright (c) 2021, Caretaker Medical, All rights reserved

#ifndef PS_INDICATORS_H_
#define PS_INDICATORS_H_

#include <xs1.h>

// Messages that get passed between 'ps_config' and 'step_arbiter', and also often between 'ps_config'
// and 'ps_data'
#define MODE_IDLE		0
#define MODE_READ_ONLY		1
#define MODE_GO_HOME		2
#define MODE_SET_HOME		3
#define MODE_INCREMENT		4
#define MODE_OVERRIDE		5
#define MODE_WAVEFORM		6

// Messages that get passed between 'ps_config' and 'wf_calc'
#define WF_IDLE			0
#define WF_LOAD			1
#define WF_END_LOAD		2
#define WF_PLAY_PT		3
#define WF_PLAY_WF		4

// Honeywell MPR pressure sensor
//#define PRESS_SENSE_I2C_ADDR	0x18
// Honeywell HSC pressure sensor
#define PRESS_SENSE_I2C_ADDR	0x28

/*
// Honeywell MPR pressure sensor status bits (all others 0)
#define MPR_POWERED		(1 << 6)
#define MPR_BUSY		(1 << 5)
#define MPR_MEM_ERR		(1 << 2)
#define MPR_MATH_ERR		(1 << 0)
*/

/*
// Scaling/Offset factors for pressure sensor (see page 19 of Honeywell datasheet for more details)
#define MPR_OUTPUT_MIN		0x66666
#define MPR_OUTPUT_MAX		0x399999
#define MPR_RANGE0		580 // The top of the sensor is 300mmHg = 5801mPSI
#define MPR_RANGE1		10 // Break up the range into two multipliers so that we don't overflow
*/

// Scaling/Offset factors for pressure sensor
#define HSC_OUTPUT_MIN		0x666
#define HSC_OUTPUT_MAX		0x3999
#define HSC_RANGE		30000

// I2C Pin Definitions
#define I2C_SCL			XS1_PORT_1E	// Explorer Board pin D12
#define I2C_SDA			XS1_PORT_1F	// Explorer Board pin D13

/*
// Connections between XMOS and pressure sensor;  of course, the "very smart people" who designed the
// breakout board decided that these pins were unnecessary
#define MPR_RESET		XS1_PORT_1H	// Explorer Board pin D23
#define MPR_INTERRUPT		XS1_PORT_1G	// Explorer Board pin D22
*/
// Pin to control power to pressure sensor
#define HSC_POWER_CTRL  XS1_PORT_1G

// Connections between XMOS and the Gecko stepper motor controller
#define GECKO_PORT		XS1_PORT_4D
#define GECKO_STEP		(1 << 1)	// Explorer Board pin D17
#define GECKO_DIR		(1 << 2)	// Explorer Board pin D18
#define GECKO_DISABLE		(1 << 3)	// Explorer Board pin D19

// Connections between XMOS and the limit switches
//#define FAR_LIMIT		XS1_PORT_1M	// Explorer Board pin D36
//#define NEAR_LIMIT		XS1_PORT_1N	// Explorer Board pin D37
#define FAR_LIMIT       XS1_PORT_1O // Explorer Board pin D38
#define NEAR_LIMIT      XS1_PORT_1P // Explorer Board pin D39

// Debug LEDs
#define DEBUG_LEDS      XS1_PORT_4F
//
// UART Ports
#define UART_RX		XS1_PORT_1K // Explorer Board pin D34
#define UART_TX		XS1_PORT_1L // Explorer Board pin D35

// UART Params
#define BAUD_RATE	9600
#define RX_BUFFER_SIZE	64

// Define stepper motor directions here
#define STEP_NEAR		1
#define STEP_FAR		0

// Movement styles
#define INCREMENT		0
#define GOTO_ZERO		1
#define MOVE_ONLY		2
#define OVERRIDE		3

// Parameter IDs
#define HOME_ID			1
#define HR_ID			2
#define RR_ID			3
#define CALMAX_ID		4

// Other parameters
#define FULL_SCALE		8192
#define MIN_STEP_TIME	20000
#define MIN_STRIDE_TIME 80000

// Triggers
#define READ_AFTER_MOVE 1
#define READ_NOW        2

// Read attempts
#define MAX_READ_ATTEMPTS   16

// No motor power detector limit
#define MAX_STEP_COUNT  50000

#endif
