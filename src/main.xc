// Copyright (c) 2016, XMOS Ltd, All rights reserved

#include <platform.h>
#include <xs1.h>
//#include "uart.h"
#include "usb.h"
#include "i2c.h"
#include "xud_cdc.h"
#include "ps_app.h"
#include "ps_indicators.h"

// I2C interface ports
on tile[0]: port p_scl = I2C_SCL;
on tile[0]: port p_sda = I2C_SDA;

// UART ports
on tile[0]: port p_uart_rx = UART_RX;
on tile[0]: port p_uart_tx = UART_TX;

// Buttons
on tile[0]: port p_button = XS1_PORT_4E;

/* USB Endpoint Defines */
#define XUD_EP_COUNT_OUT   3    //Includes EP0 (1 OUT EP0 + 2 BULK OUT EP)
#define XUD_EP_COUNT_IN    5    //Includes EP0 (1 IN EP0 + 2 INTERRUPT IN EP + 2 BULK IN EP)

void chip_reset()
{
    int button_val;
    timer tmr;
    unsigned int t;
    unsigned int tileId;
    unsigned int pllVal;
    unsigned int tileArrayLength;
    unsigned int localTileId = get_local_tile_id();

    asm volatile ("ldc %0, tile.globound":"=r"(tileArrayLength));

    while (1) {
        p_button :> button_val;
        if ((button_val & 0x1) == 0) {
            // Debounce
            tmr :> t;
            tmr when timerafter(t + 10000000) :> void;
            // Wait for the button to come back up
            p_button :> button_val;
            if ((button_val & 0x1) == 0) {
                while ((button_val & 0x1) == 0) p_button :> button_val;
                for (int i = 0; i < tileArrayLength; i++) {
                    tileId = get_tile_id(tile[1]);
                    if (localTileId != tileId) {
                        read_sswitch_reg(tileId, 6, pllVal);
                        pllVal &= 0x7FFFFFFF;
                        write_sswitch_reg_no_ack(tileId, 6, pllVal);
                    }
                }
                // And now do tile 0
                read_sswitch_reg(localTileId, 6, pllVal);
                pllVal &= 0x7FFFFFFF;
                write_sswitch_reg_no_ack(localTileId, 6, pllVal);
            }
        }
    }
}

// Note that the printed message must be terminated by '\n', and that '\n' must not appear inline
/*
void printd(chanend c_channel, const char * msg)
{
    int len = 0;
    int i = 0;
    while (msg[len++] != '\n');
    c_channel <: len;
    while (i < len)
        c_channel <: msg[i++];
}
*/
/*
void debug_print(client uart_tx_if uart_tx, chanend c_ps_config_debug, chanend c_wf_calc_debug, chanend c_measurement_mgr_debug)
{
    int len = 0;
    int i = 0;
    uint8_t byte;
    const char init_msg[] = "Hello world\n";
    while (init_msg[i] != '\n')
        uart_tx.write((uint8_t)init_msg[i++]);
    uart_tx.write('\n');
    uart_tx.write('\r');
    while (1){
        select {
            case c_ps_config_debug :> len : {
                for (i = 0; i < len; i++) {
                    c_ps_config_debug :> byte;
                    uart_tx.write(byte);
                }
                uart_tx.write('\r');
                break;
            }
            case c_wf_calc_debug :> len : {
                for (i = 0; i < len; i++) {
                    c_wf_calc_debug :> byte;
                    uart_tx.write(byte);
                }
                uart_tx.write('\r');
                break;
            }
            case c_measurement_mgr_debug :> len : {
                for (i = 0; i < len; i++) {
                    c_measurement_mgr_debug :> byte;
                    uart_tx.write(byte);
                }
                uart_tx.write('\r');
                break;
            }
            default: break;
        }
    }
}
*/


int main() {
    /* Channels to communicate with USB endpoints */
    chan c_ep_out[XUD_EP_COUNT_OUT], c_ep_in[XUD_EP_COUNT_IN];
    /* Interface to communicate with USB CDC (Virtual Serial) */
    interface usb_cdc_interface cdc_data[2];	// cdc_data[0] --> configuration, cdc_data[1] --> generated data
    /* Inter-module communication channels */
    chan c_mode;		// ps_config informs the measurement_mgr of its current mode
    chan c_pos_req_cfg;		// Position request from ps_config to the measurement_mgr
    chan c_wf_mode;		// ps_config informs wf_calc of the current system mode
    chan c_wf_data;		// ps_config loads waveform data into wf_calc via this channel
    chan c_wf_params;		// ps_config informs wf_calc of heart rate and respiration rate via this channel
    chan c_data_mode;		// ps_config informs ps_data of the current operational mode
    chan c_data_status;		// ps_data tells ps_config that it has new data, or that an overflow has occurred
    chan c_pos_req_wf;		// Position request from wf_calc to measurement_mgr
    chan c_press_data;		// Raw output from the measurement_mgr to ps_data
    chan c_mm_ready;        // Handshake between the waveform player and the measurement manager
    //chan c_ps_config_debug;
    //chan c_wf_calc_debug;
    //chan c_measurement_mgr_debug;

    /* I2C interface */
    i2c_master_if i2c[1];

    /* UART interface */
    //interface uart_rx_if i_rx;
    //interface uart_tx_if i_tx;
    //input_gpio_if i_gpio_rx;
    //output_gpio_if i_gpio_tx[1];

    par
    {
	/* USB machine stuff */
        on USB_TILE: xud(c_ep_out, XUD_EP_COUNT_OUT, c_ep_in, XUD_EP_COUNT_IN, null, XUD_SPEED_HS, XUD_PWR_SELF);
        on USB_TILE: Endpoint0(c_ep_out[0], c_ep_in[0]);
        on USB_TILE: CdcEndpointsHandler(c_ep_in[CDC_NOTIFICATION_EP_NUM1], c_ep_out[CDC_DATA_RX_EP_NUM1], c_ep_in[CDC_DATA_TX_EP_NUM1], cdc_data[0]);
        on USB_TILE: CdcEndpointsHandler(c_ep_in[CDC_NOTIFICATION_EP_NUM2], c_ep_out[CDC_DATA_RX_EP_NUM2], c_ep_in[CDC_DATA_TX_EP_NUM2], cdc_data[1]);

	/* Pulse Simulator Comms and Playback Stuff */
        on tile[0]: ps_config(cdc_data[0], c_mode, c_pos_req_cfg, c_wf_mode, c_wf_data, c_wf_params, c_data_mode, c_data_status);//, c_ps_config_debug);
        on tile[0]: ps_data(cdc_data[1], c_data_mode, c_data_status, c_press_data);
        on tile[0]: wf_calc(c_wf_mode, c_wf_data, c_wf_params, c_pos_req_wf, c_mm_ready);// c_wf_calc_debug);
        on tile[0]: measurement_mgr(i2c[0], c_mode, c_pos_req_cfg, c_pos_req_wf, c_press_data, c_mm_ready);// c_measurement_mgr_debug);
        //on tile[0]: debug_print(i_tx, c_ps_config_debug, c_wf_calc_debug, c_measurement_mgr_debug);
        on tile[0]: i2c_master(i2c, 1, p_scl, p_sda, 100);
        on tile[0]: chip_reset();

	/* UART Debug stuff */
        //on tile[0]: output_gpio(i_gpio_tx,1,p_uart_tx,null);
        //on tile[0]: uart_tx(i_tx,null,BAUD_RATE,UART_PARITY_NONE,8,1,i_gpio_tx[0]);
        //on tile[0]: input_gpio_1bit_with_events(i_gpio_rx,p_uart_rx);
        //on tile[0]: uart_rx(i_rx,null,RX_BUFFER_SIZE,BAUD_RATE,UART_PARITY_NONE,8,1,i_gpio_rx);
    }
    return 0;
}
