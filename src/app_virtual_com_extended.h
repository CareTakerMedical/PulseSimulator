// Copyright (c) 2016, XMOS Ltd, All rights reserved

#ifndef APP_VIRTUAL_COM_EXTENDED_H_
#define APP_VIRTUAL_COM_EXTENDED_H_

void app_virtual_com_extended(client interface usb_cdc_interface cdc, chanend c_pressure, chanend c_waveform, chanend c_reset, chanend c_adjust);
void pressure_reader(chanend c_pressure, chanend c_waveform, chanend c_step, chanend c_replay, client interface i2c_master_if i2c, chanend c_reset);


void stepper(chanend c_step, chanend c_replay, chanend c_adjust);
#endif /* APP_VIRTUAL_COM_EXTENDED_H_ */
