// Copyright (c) 2016, XMOS Ltd, All rights reserved

#include <platform.h>
#include <xs1.h>
#include <stdio.h>
#include <string.h>
#include <timer.h>
#include "i2c.h"
#include "xud_cdc.h"

/* App specific defines */
#define MENU_MAX_CHARS  30
#define MENU_LIST       11
#define DEBOUNCE_TIME   (1000)
#define BUTTON_PRESSED  0x00

// FXOS8700EQ register address defines - From AN00181
#define FXOS8700EQ_I2C_ADDR 0x1E
#define FXOS8700EQ_XYZ_DATA_CFG_REG 0x0E
#define FXOS8700EQ_CTRL_REG_1 0x2A
#define FXOS8700EQ_DR_STATUS 0x0
#define FXOS8700EQ_OUT_X_MSB 0x1
#define FXOS8700EQ_OUT_X_LSB 0x2
#define FXOS8700EQ_OUT_Y_MSB 0x3
#define FXOS8700EQ_OUT_Y_LSB 0x4
#define FXOS8700EQ_OUT_Z_MSB 0x5
#define FXOS8700EQ_OUT_Z_LSB 0x6

/* PORT_4A connected to the 4 LEDs */
on tile[0]: port p_led = XS1_PORT_4F;

/* PORT_4C connected to the 2 Buttons */
on tile[0]: port p_button = XS1_PORT_4E;

on tile[0]: in port p_eoc = XS1_PORT_1G;
on tile[0]: out port p_reset = XS1_PORT_1H;


on tile[0]: out port p_step = XS1_PORT_1I;  // gecko step pulse 0-1 steps it
on tile[0]: out port p_dir = XS1_PORT_1J;   // gecko direction

on tile[0]: in port p_flimit = XS1_PORT_1N; // near limit switch
on tile[0]: in port p_nlimit = XS1_PORT_1M; // far limit switch

#define WAVE_LEN    4096
#define PULSE_LEN   256
extern int waveform[WAVE_LEN];
extern int waveform2[WAVE_LEN]; // waveform table is aliased so two threads can use it.
extern signed short sine_table_bp[PULSE_LEN+1];
extern signed short sine_table_hr[PULSE_LEN+1];

int adjust_mean;
int adjust_scale;

char app_menu[MENU_LIST][MENU_MAX_CHARS] = {
        {"\n\r-------------------------\r\n"},
        {"XMOS USB Virtual COM Demo\r\n"},
        {"-------------------------\r\n"},
        {"1. Switch to Echo mode\r\n"},
        {"2. Toggle LED 1\r\n"},
        {"3. Toggle LED 2\r\n"},
        {"4. Toggle LED 3\r\n"},
        {"5. Toggle LED 4\r\n"},
        {"6. Read Accelerometer\r\n"},
        {"7. Print timer ticks\r\n"},
        {"8. Pressure read\r\n"},

        {"-------------------------\r\n"},
};

char echo_mode_str[3][30] = {
        {"Entered echo mode\r\n"},
        {"Press Ctrl+Z to exit it\r\n"},
        {"\r\nExit echo mode\r\n"},
};

#define ARRAY_SIZE(x) (sizeof(x)/sizeof(x[0]))

/* Sends out the App menu over CDC virtual port*/
void show_menu(client interface usb_cdc_interface cdc)
{
    unsigned length;
    for(int i = 0; i < MENU_LIST; i++) {
        length = strlen(app_menu[i]);
        cdc.write(app_menu[i], length);
    }
}

/* Function to set LED state - ON/OFF */
void set_led_state(int led_id, int val)
{
  int value;
  /* Read port value into a variable */
  p_led :> value;
  if (!val) {
      p_led <: (value | (1 << led_id));
  } else {
      p_led <: (value & ~(1 << led_id));
  }
}

/* Function to toggle LED state */
void toggle_led(int led_id)
{
    int value;
    p_led :> value;
    p_led <: (value ^ (1 << led_id));
}

/* Function to get button state (0 or 1)*/
int get_button_state(int button_id)
{
    int button_val;
    p_button :> button_val;
    button_val = (button_val >> button_id) & (0x01);
    return button_val;
}

/* Checks if a button is pressed */
int is_button_pressed(int button_id)
{
    if(get_button_state(button_id) == BUTTON_PRESSED) {
        /* Wait for debounce and check again */
        delay_ticks(DEBOUNCE_TIME);
        if(get_button_state(button_id) == BUTTON_PRESSED) {
            return 1; /* Yes button is pressed */
        }
    }
    /* No button press */
    return 0;
}

int up_button(void)
{
    return is_button_pressed(0);
}

int down_button(void)
{
    return is_button_pressed(1);
}

int near_limit(void)
{
    int x;
    p_nlimit :> x;
    return (x==0);
}

int far_limit(void)
{
    int x;
    p_flimit :> x;
    return (x==0);
}



int read_acceleration(client interface i2c_master_if i2c, int reg) {
    i2c_regop_res_t result;
    int accel_val = 0;
    unsigned char data = 0;

    // Read MSB data
    data = i2c.read_reg(FXOS8700EQ_I2C_ADDR, reg, result);
    if (result != I2C_REGOP_SUCCESS) {
      return 0;
    }

    accel_val = data << 2;

    // Read LSB data
    data = i2c.read_reg(FXOS8700EQ_I2C_ADDR, reg+1, result);
    if (result != I2C_REGOP_SUCCESS) {
      return 0;
    }

    accel_val |= (data >> 6);

    if (accel_val & 0x200) {
      accel_val -= 1023;
    }

    return accel_val;
}

#define PRESSURE_I2C_ADDR   0x18

// Note - default address of MCP9808 is 0x18 but we short A0 to VDD to get 0x19
#define TEMP_I2C_ADDR       0x19
#define TEMP_REG            0x05  // ambient temp register


//#define VERSION_A	// 10% to 90% range
#define VERSION_B	// 2.5% to 2.25% range
//#define VERSION_C	// 20% to 80% range

#ifdef VERSION_A
unsigned int low_range=0x19999A; // 10% of 1<<24
unsigned int mult=5;		 // multiplier is 5/4, as 80% of range used, and Python expects 0-(1<<23) to span 0-25 psi
unsigned int div=4;              // divider
int pressure_range=25000; // output in mPSI
#endif

#ifdef VERSION_B
unsigned int low_range=0x66666;  // 2.5% of 1<<24
unsigned int mult=5;		 // multiplier is 5/1, as 20% of range used, and Python expects 0-(1<<23) to span 0-25 psi
unsigned int div=1;              // divider
int pressure_range=5801; // output in mPSI
#endif

#ifdef VERSION_C
unsigned int low_range=0x333333; // 20% of 1<<24
unsigned int mult=5;		 // multiplier is 5/3, as 60% of range used, and Python expects 0-(1<<23) to span 0-25 psi
unsigned int div=3;              // divider
int pressure_range=25000; // output in mPSI
#endif

{unsigned char, int} read_pressure(client interface i2c_master_if i2c) {
    i2c_regop_res_t result;
    int pressure = 0;
    int x;
    uint8_t a_data[3];
    uint8_t data[4];
    size_t n;
    unsigned char status;


    a_data[0]=0xAA;
    a_data[1]=0;
    a_data[2]=0;


    result=i2c.write(PRESSURE_I2C_ADDR, a_data, 3, n, 1);
    if(n!=3){
        return {0xff, n};
    }

#ifdef USE_EOC // use end of conversion flag ?
    while(1){
        p_eoc :> x;
        if(x){
            break;
        }
    }
#else
    delay_ticks(500000); // 5ms
#endif
    data[0]=0xff;
    data[1]=0xfe;
    data[2]=0xfd;
    data[3]=0xfc;


    result=i2c.read(PRESSURE_I2C_ADDR, data,4,1);

    if (result != I2C_ACK) {
      return {0xff, 0};
    }

    pressure=(data[1]<<16)+(data[2]<<8)+data[3];
    pressure=pressure-low_range; // how much above the lowest value
    pressure=pressure*mult/div;  // compensate for fractional usage of full 24-bit range
    status=data[0];
    return {status, pressure};
}


void reset_sensor(void)
{
    // reset the pressure sensor.
        p_reset <: 1;
        delay_ticks(500000);
        p_reset <: 0;
        delay_ticks(500000);
        p_reset <: 1;
        delay_ticks(500000);

}


//inline uint16_t read_reg16_addr8(client interface i2c_master_if i,
//                                   uint8_t device_addr, uint8_t reg,
//                                   i2c_regop_res_t &result)
//  {
int read_temperature(client interface i2c_master_if i2c) {
    i2c_regop_res_t result;
    int t;

    t=i2c.read_reg16_addr8(TEMP_I2C_ADDR, TEMP_REG, result);
    if(result!=I2C_REGOP_SUCCESS){
       t=-100000;
    }else{
        t=t&0xFFF; // 12 bits
    }
    return t;
}

void init_temperature_sensor(client interface i2c_master_if i2c)
{


}

/* Initializes the Application */
void app_init(client interface i2c_master_if i2c)
{
    i2c_regop_res_t result;


    /* Set all LEDs to OFF (Active low)*/
    p_led <: 0x0F;
    reset_sensor();
    init_temperature_sensor(i2c);


}

#define MIN_STEP_TIME   9000


// step in this direction, return true if prevented by a limit
int step(int x)
{
    timer tmr;
    int dir;
    unsigned int t, t0;

    if(x>0){ // handle far limit switch
         if(far_limit()){
             return 1;
         }
     }
     if(x<0){ // handle near limit switch
         if(near_limit()){
             return 1;
         }
    }

    if(x>0){
        dir=0;
    }
    if(x<0){
        dir=1;
    }
    //x=((x+1)>>1); // from -1 to 1, from 1 to 0

    p_dir <: dir;
    tmr :> t;
    t0=t;
    t+=50; // 50*10ns = 0.5us
    tmr when timerafter(t) :> void;
    p_step <: 1;
    t+=400; // 400*10ns = 4.0us
    tmr when timerafter(t) :> void;
    p_step <: 0;

    if(x>0){
        t0+=x;
    }else{
        t0-=x;
    }
    tmr when timerafter(t0) :> void;
    return 0;
}

// step in this direction, return true if prevented by a switch or position limit
int safe_step(int x, int pos, int limit)
{
    timer tmr;
    int dir;
    unsigned int t, t0;

    if(x>0){ // handle far limit switch
         if(far_limit()){
             return 1;
         }
         if((pos+1)>=limit){
             return 1;
         }
     }
     if(x<0){ // handle near limit switch
         if(near_limit()){
             return 1;
         }
         if((pos-1)<=10){
             return 1;
         }
    }

    if(x>0){
        dir=0;
    }
    if(x<0){
        dir=1;
    }

    p_dir <: dir;
    tmr :> t;
    t0=t;
    t+=50; // 50*10ns = 0.5us
    tmr when timerafter(t) :> void;
    p_step <: 1;
    t+=400; // 400*10ns = 4.0us
    tmr when timerafter(t) :> void;
    p_step <: 0;
    if(x>0){
        t0+=x;
    }else{
        t0-=x;
    }
    tmr when timerafter(t0) :> void;
    return 0;
}

// step in this direction, return true if prevented by a switch or position limit
{int, unsigned int } nonblocking_safe_step(int x, int pos, int limit)
{
    timer tmr;
    int dir;
    unsigned int t, t0;

    if(x>0){ // handle far limit switch
         if(far_limit()){
             return {1, 0};
         }
         if((pos+1)>=limit){
             return {1, 0};
         }
     }
     if(x<0){ // handle near limit switch
         if(near_limit()){
             return {1, 0};
         }
         if((pos-1)<=10){
             return {1, 0};
         }
    }

    if(x>0){
        dir=0;
    }
    if(x<0){
        dir=1;
    }

    p_dir <: dir;
    tmr :> t;
    t0=t;
    t+=50; // 50*10ns = 0.5us
    tmr when timerafter(t) :> void;
    p_step <: 1;
    t+=400; // 400*10ns = 4.0us
    tmr when timerafter(t) :> void;
    p_step <: 0;
    if(x>0){
        t0+=x;
    }else{
        t0-=x;
    }
    return {0, t0};
}

#define FULL_SCALE  8192
#define INIT_SCALE  7250 // built in adjustment due to mechanical factors

static inline int transform(int x)
{
    int y;
    y=adjust_mean+((x*adjust_scale)>>13); // scale and add back in the mean
    //y=adjust_mean+x;
    return y;
}

static inline int rr_transform(int x, int rrmod)
{
    int y;
    y=adjust_mean+((x*adjust_scale)>>13); // scale and add back in the mean
    y=y+rrmod;
    return y;
}

void stepper(chanend c_step, chanend c_replay, chanend c_adjust)
{
    timer tmr;
    unsigned int t, t0, tnext;
    int x;
    int r, i;
    int dp;
    int dt;
    int pos;
    int real_pressure;
    int home;
    int limit;
    int sum, mean, scale, max, min, steprange;
    int wave_length=0;
    int mode=0;
    int wave_index=0;
    int resp_index=0;
    int replaying=0;
    int num_cycles=0;
    int stop=0;
    int hrstep;
    int rrstep;
    int nextp;
    int rrbp;
    int rrhr;
    int ind;
    int frac;

    p_step <: 0; // no step to start
    while(1){
        select{
            case c_step :> x:{
                r=step(x);
                c_step <: r;
                break;
            }
            case c_replay :> mode :{ // mode = 1 : waveform play, mode = 2 : pulse table play
                if(mode==1){ // play waveform
                    c_replay :> wave_length;
                    c_replay :> num_cycles;
                    c_replay :> x; // current location in steps from low limit switch
                    limit = x; // do not go past this point
                    c_replay :> home; // where to go to when finished

                    sum=0;
                    for(i=0;i<wave_length;i++){
                        sum=sum+waveform2[i];
                    }
                    mean=sum/wave_length;
                    for(i=0;i<wave_length;i++){
                        waveform2[i]-=mean;
                    }
                    adjust_mean=mean;
                    adjust_scale=INIT_SCALE;
                    // go to first position
                    pos=transform(waveform2[0]);
                    if(x>pos){
                        while(x>pos){
                            safe_step(-100000, x, limit);
                            x=x-1;
                        }
                    }else{
                        if(x<pos){
                            while(x<pos){
                                safe_step(100000, x, limit);
                                x=x+1;
                            }
                        }
                    }
                // now just wait a second to settle
                    tmr :> t;
                    t+=100000000;
                    tmr when timerafter(t) :> void;
                    c_replay <: mean; // handshake
                    replaying=1;
                    wave_index=1;
                    tmr :> t;
                    t0=t;
                    tnext=t+2000000;
                }else{
                    if(mode==2){ // play pulse table
                        c_replay :> hrstep; // heart rate table step in X.8 format
                        c_replay :> rrstep; // resp. rate table step in X.8 format
                        c_replay :> x; // current location in steps from low limit switch
                        limit = x; // do not go past this point
                        c_replay :> home; // where to go to when finished

                        sum=0;
                        max=0;
                        min=1e6;
                        for(i=0;i<(PULSE_LEN+1);i++){
                            sum=sum+waveform2[i];
                            if(waveform2[i]>max){
                                max=waveform2[i];
                            }
                            if(waveform2[i]<min){
                                min=waveform2[i];
                            }
                        }
                        steprange=max-min;
                        mean=sum/(PULSE_LEN+1);
                        for(i=0;i<(PULSE_LEN+1);i++){
                            waveform2[i]-=mean;
                        }
                        adjust_mean=mean;
                        adjust_scale=FULL_SCALE;

                        pos=rr_transform(waveform2[0], 0);
                        if(x>pos){
                            while(x>pos){
                                safe_step(-100000, x, limit);
                                x=x-1;
                            }
                        }else{
                            if(x<pos){
                                while(x<pos){
                                    safe_step(100000, x, limit);
                                    x=x+1;
                                }
                            }
                        }
                        // now just wait a second to settle
                        tmr :> t;
                        t+=100000000;
                        tmr when timerafter(t) :> void;
                        c_replay <: 0; // handshake
                        replaying=1;
                        wave_index=hrstep;
                        resp_index=rrstep;
                        tmr :> t;
                        t0=t;
                        tnext=t+2000000;
                    }
                }
                break;
            }
            default:{
                if(replaying){
                    if(mode==1){
                        if(wave_index<wave_length){
                            dp=transform(waveform2[wave_index])-pos;
                            if(dp>0){
                                dt=(tnext-t0)/dp;
                            }else{
                                if(dp<0){
                                    dt=(tnext-t0)/(-dp);
                                }else{
                                    dt=2000000;
                                }
                            }
                            if(dp==0){
                                delay_ticks(dt);
                            }else{
                                dt=dt-450; // setup time
                                if(dt<MIN_STEP_TIME){ // don't let it go too fast
                                    dt=MIN_STEP_TIME;
                                }
                                while(pos!=transform(waveform2[wave_index])){
                                    if(pos<transform(waveform2[wave_index])){
                                        { r, t0 } = nonblocking_safe_step(dt, pos, limit);
                                        pos++;
                                    }else{
                                        if(pos>transform(waveform2[wave_index])){
                                            { r, t0} = nonblocking_safe_step(-dt, pos, limit);
                                            pos--;
                                        }
                                    }
                                    if(pos==transform(waveform2[wave_index])){
                                        c_adjust <: 1;
                                        c_adjust :> stop;
                                        tmr when timerafter(t0) :> void;
                                        break;
                                    }
                                    if(!r){ // did the step error out ?
                                        tmr :> t0;
                                        t0+=((dt>0)?dt:-dt);
                                    }
                                    tmr when timerafter(t0) :> void;
                                }
                            }
                            tnext=tnext+2000000;
                            tmr :> t0;
                            wave_index++;
                        }else{ // hit the index==wave_length
                            if((num_cycles<0)&&!stop){
                                wave_index=1;
                                pos=transform(waveform2[0]);
                            }else{
                                if(stop){
                                    num_cycles=0;
                                }else{
                                    num_cycles--;
                                }
                                if(num_cycles){
                                    wave_index=1;
                                    pos=transform(waveform2[0]);
                                }else{
                                    replaying=0;
                                    if(pos>home){ // send it home so pressure can be normalized
                                        while(pos>home){
                                            safe_step(-100000, pos, limit);
                                            pos=pos-1;
                                        }
                                    }else{
                                        if(pos<home){
                                            while(pos<home){
                                                safe_step(100000, pos, limit);
                                                pos=pos+1;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }else if(mode==2){
                        ind=wave_index>>8;
                        frac=wave_index&0xFF;
                        nextp=(waveform2[ind]*(256-frac)+waveform2[ind+1]*frac)>>8; // interpolate HR table
                        ind=resp_index>>8;
                        frac=resp_index&0xFF;
                        rrbp=(sine_table_bp[ind]*(256-frac)+sine_table_bp[ind+1]*frac)>>8; // interpolate RR BP sine wave
                        rrhr=(sine_table_hr[ind]*(256-frac)+sine_table_hr[ind+1]*frac)>>8; // interpolate RR HR sine wave

                        rrbp=(steprange*rrbp)>>13;
                        nextp=rr_transform(nextp, rrbp); // handle RR AM modulation
                        dp=nextp-pos;
                        if(dp>0){
                            dt=(tnext-t0)/dp;
                        }else{
                            if(dp<0){
                                dt=(tnext-t0)/(-dp);
                            }else{
                                dt=2000000;
                            }
                        }
                        if(dp==0){
                            delay_ticks(dt);
                        }else{
                            dt=dt-450; // setup time
                            if(dt<MIN_STEP_TIME){ // don't let it go too fast
                                dt=MIN_STEP_TIME;
                            }
                            while(pos!=nextp){
                                if(pos<nextp){
                                    { r, t0 } = nonblocking_safe_step(dt, pos, limit);
                                    pos++;
                                }else{
                                    if(pos>nextp){
                                       { r, t0} = nonblocking_safe_step(-dt, pos, limit);
                                       pos--;
                                    }
                                }
                                if(pos==nextp){
                                     c_adjust <: 1;
                                     c_adjust :> stop;
                                     tmr when timerafter(t0) :> void;
                                     break;
                                }
                                if(!r){ // did the step error out ?
                                    tmr :> t0;
                                    t0+=((dt>0)?dt:-dt);
                                }
                                tmr when timerafter(t0) :> void;
                            }
                        }
                        if(stop){
                            replaying=0;
                            if(pos>home){ // send it home so pressure can be normalized
                                while(pos>home){
                                   safe_step(-100000, pos, limit);
                                   pos=pos-1;
                                }
                            }else{
                                if(pos<home){
                                    while(pos<home){
                                        safe_step(100000, pos, limit);
                                        pos=pos+1;
                                    }
                                }
                            }
                        }else{
                            tnext=tnext+2000000;
                            tmr :> t0;
                            wave_index+=((hrstep*rrhr)>>8); // handle FM modulation
                            wave_index=wave_index&0xFFFF; // wrap around
                            resp_index+=rrstep;
                            resp_index=resp_index&0xFFFF; // wrap around
                        }
                    }
                }else{ // not replaying, just check buttons
                    if(up_button()){
                        step(100000);
                    }else if(down_button()){
                        step(-100000);
                    }
                    break;
                }
                break;
            }
        }
    }
}

void pressure_reader(chanend c_pressure, chanend c_waveform, chanend c_step, chanend c_replay, client interface i2c_master_if i2c, chanend c_reset)
{
    timer tmr;
    unsigned int t;
    int reading;
    int rt_reading;
    unsigned char status;
    int pressure;
    int temp;
    int x;
    int r;
    int i;
    int n;
    int steps;
    int lowsteps, highsteps, lowsteps0, highsteps0;
    int hrstep, rrstep;
    int home;
    int waveforming;
    int wave_index=0;
    int wave_length=0;

    app_init(i2c);
    reading=0; // background reading

    while(1){
        select{
            case c_reset :> x : {
                reset_sensor();
                break;
            }
            case c_pressure :> x : {
                if((reading==0)&&(x==1)){
                    tmr :> t;
                    t+=1;
                    reading=1;
                }else{
                    if((reading==1)&&(x==0)){
                        reading=0;
                    }else{
                        if(x==2){ // start waveform write
                            waveforming=1;
                            wave_index=0;
                        }else{
                            if(x==3){ // end waveform write
                                waveforming=0;
                                wave_length=wave_index;
                            }else{
                                if(x==4){ // calibrate
                                    c_pressure :> lowsteps;
                                    c_pressure :> highsteps;
                                    r=0;
                                    while(r==0){ // move to near limit
                                        c_step <: -100000;
                                        c_step :> r;
                                    }
                                    r=0;
                                    steps=0;
                                    while(1){
                                        c_step <: 100000;
                                        c_step :> r;
                                        steps=steps+1;
                                        if(steps>lowsteps){
                                            break;
                                        }
                                        if(r){
                                            break;
                                        }
                                    }
                                    lowsteps0=steps; // actual steps
                                    { status, pressure} =read_pressure(i2c);
                                    pressure=((pressure>>8)*pressure_range)>>16;
                                    c_pressure <: pressure;
                                    r=0;
                                    while(1){
                                        c_step <: 100000;
                                        c_step :> r;
                                        steps=steps+1;
                                        if(steps>highsteps){
                                            break;
                                        }
                                        if(r){
                                            break;
                                        }
                                    }
                                    highsteps0=steps; // actual steps
                                    { status, pressure} =read_pressure(i2c);
                                    pressure=((pressure>>8)*pressure_range)>>16;
                                    c_pressure <: pressure;
                                    c_pressure <: lowsteps0;
                                    c_pressure <: highsteps0;
                                }else{
                                    if(x==5){ // read waveform

                                        for(i=0;i<wave_length;i++){
                                            c_pressure <: waveform[i];
                                        }
                                        c_pressure <: -1;
                                    }else{
                                        if(x==6){ // GO with waveform replay
                                            c_pressure :> n;
                                            c_pressure :> highsteps;
                                            c_pressure :> home;
                                            c_replay <: 1; // waveform play mode
                                            c_replay <: wave_length;
                                            c_replay <: n;
                                            c_replay <: highsteps;
                                            c_replay <: home;
                                            c_replay :> highsteps;
                                            c_pressure <: highsteps;

                                        }else{
                                            if(x==7){
                                                { status, pressure} =read_pressure(i2c);
                                                if(status==0xff){
                                                    pressure=-1;
                                                }else{
                                                    if(status&0x25){
                                                        pressure=-status;
                                                    }else{
                                                        pressure=((pressure>>8)*pressure_range)>>16;
                                                    }
                                                }
                                                temp = read_temperature(i2c);
                                                c_pressure <: pressure;
                                                c_pressure <: temp;
                                                //c_pressure <: 15000;
                                            }else{
                                                if(x==8){ // home
                                                    c_pressure :> highsteps;
                                                    r=0;
                                                    while(r==0){ // move to near limit
                                                        c_step <: -100000;
                                                        c_step :> r;
                                                     }
                                                     r=0;
                                                     steps=0;
                                                     while(1){
                                                         c_step <: 100000;
                                                         c_step :> r;
                                                         steps=steps+1;
                                                         if(steps>highsteps){
                                                             break;
                                                         }
                                                         if(r){
                                                             break;
                                                         }
                                                     }
                                                     { status, pressure} =read_pressure(i2c);
                                                     pressure=((pressure>>8)*pressure_range)>>16;
                                                     c_pressure <: pressure;
                                                }else{
                                                    if(x==9){ // incremental move
                                                         c_pressure :> highsteps;
                                                         if(highsteps>0){
                                                             n=200000;
                                                         }else{
                                                             n=-200000;
                                                             highsteps=-highsteps;
                                                         }
                                                         for(i=0;i<highsteps;i++){
                                                             c_step <: n;
                                                             c_step :> r;
                                                             if(r){
                                                                 break;
                                                             }
                                                         }
                                                         { status, pressure} =read_pressure(i2c);

                                                         if(status==0xff){
                                                             pressure=-1;
                                                         }else{
                                                             if(status&0x25){
                                                                 pressure=-status;
                                                             }else{
                                                                 pressure=((pressure>>8)*pressure_range)>>16;
                                                             }
                                                         }
                                                         c_pressure <: pressure;
                                                    }else{
                                                        if(x==10){ // GO with pulse table
                                                            c_pressure :> hrstep;
                                                            c_pressure :> rrstep;
                                                            c_pressure :> highsteps;
                                                            c_pressure :> home;
                                                            c_replay <: 2; // pulse table mode
                                                            c_replay <: hrstep;
                                                            c_replay <: rrstep;
                                                            c_replay <: highsteps;
                                                            c_replay <: home;
                                                            c_replay :> highsteps;
                                                            c_pressure <: highsteps;
                                                       }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                break;
            }
            case c_waveform :> x : {
                waveform[wave_index]=x;
                if(wave_index<(WAVE_LEN-1)){ // limit it
                    wave_index++;
                }
                break;
            }
            case reading => tmr when timerafter(t) :> void: {
                t+=2000000; /* 50 Hz */
                { status, pressure} =read_pressure(i2c);
                if(status==0xff){
                    pressure=-1;
                }else{
                    pressure=((pressure>>8)*pressure_range)>>16;
                }
                temp=read_temperature(i2c);
                c_pressure <: pressure;
                c_pressure <: temp;

                break;
            }

            default:{

                break;
            }
        }
    }
}

int readint(client interface usb_cdc_interface cdc)
{
    char value;
    int d=0;
    int neg=0;

    while(1){
        while(!cdc.available_bytes()){};
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
    }
    if(neg){
        d=-d;
    }
    return d;
}

/* Application task */
void app_virtual_com_extended(client interface usb_cdc_interface cdc,  chanend c_pressure, chanend c_waveform, chanend c_reset, chanend c_adjust)
{
    unsigned int length, led_id;

    int x = 0;
    int t=0;

    char value, tmp_string[50];
    unsigned int button_1_valid, button_2_valid;
    timer tmr;
    unsigned int timer_val;
    int d, r;
    //int mean;
    //int scale=INIT_SCALE;
    int stop=0;

    button_1_valid = button_2_valid = 1;
    while(1){
        select{
            case c_pressure :> x : {
                c_pressure :> t;
                length = sprintf(tmp_string, "%d,%d\r\n", x, t);
                cdc.write(tmp_string, length);
                break;
            }
            case c_adjust :> x: {
                c_adjust <: stop;
                break;
            }
            default: {
                /* Check if user has input any character */
                if(cdc.available_bytes()){
                    value = cdc.get_char();
                    if(value=='0'){
                        c_reset <: 1;
                    }
                    if((value == 'R')){ // start reading
                        c_pressure <: 1;
                    }
                    if(value=='r'){ // read once
                        c_pressure <: 7;
                        c_pressure :> x;
                        c_pressure :> t;
                        length = sprintf(tmp_string, "%d,%d\r\n", x, t);
                        cdc.write(tmp_string, length);
                    }

                    if((value == 'D')||(value=='d')) { // waveform data
                        d=0;
                        while(1){
                            while(!cdc.available_bytes()){};
                            value=cdc.get_char();
                            if(value=='\n'){
                                break;
                            }else{
                                if((value>='0')&&(value<='9')){
                                    d=d*10+(value-'0');
                                }
                            }
                        } /* while */
                        c_waveform <: d;
                    }

                    if((value == 'S')||(value=='s')) { // stop reading
                        c_pressure <: 0;
                    }
                    if((value == 'W')||(value=='w')) { // start waveform
                        c_pressure <: 2;
                    }
                    if((value == 'E')||(value=='e')) { // end waveform
                        c_pressure <: 3;
                    }
                    if((value == 'Q')||(value=='q')) { // read waveform
                        c_pressure <: 5;
                        x=0;
                        while(x>=0){
                            c_pressure :> x;
                            length = sprintf(tmp_string, "%d\r\n", x);
                            cdc.write(tmp_string, length);
                        }
                    }
                    if((value == 'G')||(value=='g')) { // GO with waveform (nloops, posnow, home)
                        c_pressure <: 6;
                        d=readint(cdc); // number of loops of the waveform
                        c_pressure <: d;
                        d=readint(cdc); // current position in steps
                        c_pressure <: d;
                        d=readint(cdc); // home position to go to once done
                        c_pressure <: d;
                        c_pressure :> d; // handshake - mean value
                        length = sprintf(tmp_string, "%d\r\n", d);
                        cdc.write(tmp_string, length);
                    }

                    if((value == 'T')||(value=='t')) { // GO with table (HR, RR, posnow, home)
                        c_pressure <: 10;
                        d=readint(cdc); // HR in 8.8 format (up to 255+255/256 BPM)
                        c_pressure <: d;
                        d=readint(cdc); // RR in 8.8 format (up to 255+255/256 RPM)
                        c_pressure <: d;
                        d=readint(cdc); // current position in steps
                        c_pressure <: d;
                        d=readint(cdc); // home position to go to once done
                        c_pressure <: d;
                        c_pressure :> d; // handshake - mean value
                        length = sprintf(tmp_string, "%d\r\n", d);
                        cdc.write(tmp_string, length);
                    }

                    if((value == 'H')||(value=='h')) { // home (go to N steps from home)
                        c_pressure <: 8;
                        d=readint(cdc); // steps to go to
                        c_pressure <: d;
                        c_pressure :> x;
                        length = sprintf(tmp_string, "%d\r\n", x);
                        cdc.write(tmp_string, length);
                    }
                    if((value == 'I')||(value=='i')) { // home (go to N steps from home)
                        c_pressure <: 9;
                        d=readint(cdc); // steps to move
                        c_pressure <: d;
                        c_pressure :> x;
                        length = sprintf(tmp_string, "%d\r\n", x);
                        cdc.write(tmp_string, length);
			            stop = 0; // reset any stop flag
                    }
                    if((value == 'C')||(value=='c')) { // calibrate
                        c_pressure <: 4;
                        d=readint(cdc); // low steps
                        c_pressure <: d;
                        d=readint(cdc); // high steps
                        c_pressure <: d;
                        c_pressure :> x;
                        length = sprintf(tmp_string, "%d\r\n", x);
                        cdc.write(tmp_string, length);
                        c_pressure :> x;
                        length = sprintf(tmp_string, "%d\r\n", x);
                        cdc.write(tmp_string, length);
                        c_pressure :> x;
                        length = sprintf(tmp_string, "%d\r\n", x);
                        cdc.write(tmp_string, length);
                        c_pressure :> x;
                        length = sprintf(tmp_string, "%d\r\n", x);
                        cdc.write(tmp_string, length);
                        stop = 0; // reset any stop flag
                    }
                    if((value == 'L')||(value=='l')) { // limit switches
                    }
                    if((value == 'P')||(value=='p')) { // set params
                        //d=readint(cdc); // mean steps
                        //r=readint(cdc); // scale
                        stop=readint(cdc); // should we stop
                        //mean=d;
                        //scale=r;
                    }
                }
                break;
            }
        } /* end of select{} */
    } /* end of while(1) */
}
