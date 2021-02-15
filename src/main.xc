// Copyright (c) 2016, XMOS Ltd, All rights reserved

#include <platform.h>
#include <xs1.h>
#include "usb.h"
#include "i2c.h"
#include "xud_cdc.h"
#include "app_virtual_com_extended.h"

// I2C interface ports
on tile[0]: port p_scl = XS1_PORT_1E;
on tile[0]: port p_sda = XS1_PORT_1F;

/* USB Endpoint Defines */
#define XUD_EP_COUNT_OUT   2    //Includes EP0 (1 OUT EP0 + 1 BULK OUT EP)
#define XUD_EP_COUNT_IN    3    //Includes EP0 (1 IN EP0 + 1 INTERRUPT IN EP + 1 BULK IN EP)

int main() {
    //chan c_stepper;
    /* Channels to communicate with USB endpoints */
    chan c_ep_out[XUD_EP_COUNT_OUT], c_ep_in[XUD_EP_COUNT_IN];
    /* Interface to communicate with USB CDC (Virtual Serial) */
    interface usb_cdc_interface cdc_data;
    chan c_pressure;
    chan c_waveform;
    chan c_step;
    chan c_replay;
    chan c_reset;
    chan c_adjust;

    /* I2C interface */
    i2c_master_if i2c[1];

    par
    {
        on USB_TILE: xud(c_ep_out, XUD_EP_COUNT_OUT, c_ep_in, XUD_EP_COUNT_IN,
                         null, XUD_SPEED_HS, XUD_PWR_SELF);

        on USB_TILE: Endpoint0(c_ep_out[0], c_ep_in[0]);

        on USB_TILE: CdcEndpointsHandler(c_ep_in[1], c_ep_out[1], c_ep_in[2], cdc_data);

        on tile[0]: app_virtual_com_extended(cdc_data, c_pressure, c_waveform, c_reset, c_adjust);

        on tile[0]: pressure_reader(c_pressure, c_waveform, c_step, c_replay, i2c[0], c_reset);
        on tile[0]: i2c_master(i2c, 1, p_scl, p_sda, 10);
        on tile[0]: stepper(c_step, c_replay, c_adjust);
    }
    return 0;
}
