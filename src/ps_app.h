// Copyright (c) 2021, XMOS Ltd, All rights reserved

#ifndef PS_APP_H_
#define PS_APP_H_

void ps_config(client interface usb_cdc_interface cdc, chanend c_mode, chanend c_pos_req_cfg, chanend c_wf_mode, chanend c_wf_data, chanend c_wf_params, chanend c_data_mode, chanend c_data_status, chanend c_mm_fault);
void ps_data(client interface usb_cdc_interface cdc, chanend c_data_mode, chanend c_data_status, chanend c_press_data);
void wf_calc(chanend c_wf_mode, chanend c_wf_data, chanend c_wf_params, chanend c_pos_req_wf, chanend c_mm_ready);
void measurement_mgr(client interface i2c_master_if i2c, chanend c_mode, chanend c_pos_req_cfg, chanend c_pos_req_wf, chanend c_press_data, chanend c_mm_ready, chanend c_mm_fault);
#endif /* PS_APP_H_ */
