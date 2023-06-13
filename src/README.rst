Author: Jake Wegman

XMOS Firmware
=============

The firmware for the pulse simulator is run on an XMOS development board.  When the term 'XMOS' is
used, it's referring to the microcontroller on the board that is designed by a company called XMOS.
The unique thing about XMOS microcontrollers is the architecture.  The XMOS has many of
the same peripherals that one would find on a standard microcontroller, but the architecture is
meant to perform operations in real-time.  Like many modern microcontrollers, there are cores
responsible for various tasks.  A further level of division present on the XMOS chip is the concept
of a tile.  A tile is the physical division between the physical cores.  So, when dividing the labor
of your application, you must 'physically' assign a task to a particular tile.  The compiler will
then determine which core to run the task on.

Because of these physical divisions that must communicate and operate in real-time, XMOS devised a
couple of structures that one can introduce into the code to allow information passing between the
physical interfaces.  One is called an 'interface', and another one is called a 'channel'.  An
'interface' uses a server/client arrangement to pass information back and forth; the server may
alert the client to a change in state, while the client may request information from the server.  A
'channel' allows information to be passed back and forth between two ends.

Another unique feature of XMOS microcontrollers is the large number of timers that you have at your
disposal.  These can be used to block activity on a core, or delay an event well into the future.

The unique features of the XMOS chip described above allow engineers to create event-driven systems
without having to use FPGAs, which generally require the knowledge of an HDL like Verilog, and the
ability to use tools to close both internal and external timing constraints.  However, because
ANSI-C knows nothing of these kinds of physical structures that exist within the XMOS, both the code
and the compiler are unique to the XMOS microcontroller.  When writing code for the XMOS, you
currently have two choices:

 1. The supported method is to use standard ANSI-C and include libraries provided by XMOS.  This
    option was not available until a couple of years ago.  You still must use a custom set of build
    tools, since there are no off-the-shelf build tools that will properly compile the program.
 2. The previously supported method was the use of an XMOS created language called xC, which is
    really just ANSI-C with some added-on language elements.

Because the firmware for this project was developed before XMOS made the pivot to using plain C with
special additionally provided libraries, the firwmare currently uses xC.  Language elements that
will seem unfamiliar are as follows:

 * **select**: This is very similar to a *switch* statement in C, except that it is used to indicate
   that the block of code is waiting for one of the listed events to happen, in any order.  You'll
   almost always see this kind of command within an infinite *while* loop.  The *cases* listed
   within the select statement are events that the task is waiting on to happen.  You will often see
   timer events listed in select statements, as they provide timeouts when other events don't occur,
   or provide spacing between events.
 * **par**:  This is used to describe tasks that should be assigned to physical tiles that should
   run in parallel.
 * **chan** and **chanend**:  *chan* is used to describe a channel, while *chanend* is used to
   describe either end of the channel.  A channel object is first created, and then its ends are
   assigned to various tasks.
 * **client interface** and **server interface**:  This works in much the same way that an internet
   server/client works.  The client requests information from the server, which the server then
   provides.
 * **:>** and **<:**:  These are blocking assignment operators.  Whereas a normal assignment
   operator assigns to memory a value whenever that statement is executed, a blocking assignment
   operator will wait to assign a value to memory until certain validity conditions are met.  For
   example, blocking assignment operators are used on channel ends to indicate that a variable will
   not be assigned until the channel hardware has determined that the value is ready.  These
   operators are also used with timers to indicate that a variable should not assigned until the
   timer has expired.

 With that background in hand, hopefully opening the firmware for this project will make a little
 more sense.

Opening And Developing The Firmware
===================================

Because XMOS borrows heavily for their tools from open-source libraries, I've found it easiest to
work with and compile the code on a Linux virtual environment.  I've successfully used the
command-line tools on Linux for building the source code, but even though I don't generally like
IDEs, I use the XMOS provided one because of its ability to assist in debugging.  Here's how my
workflow usually goes:

 * Open up the virtual machine using VMWare.
 * Once Ubuntu has booted, the login password is *xmosxmos*.  That is also the admin password.
 * After login has completed, start up a terminal.  Run the command *xtimecomposer.sh*.  This will
   start up the XMOS IDE, which is a fork of the Eclipse IDE.
 * The name of the project is *PulseSimulator*, and the source code is found under *src*.

Code Organization
=================

The application must do the following:

 * Provide a communication interface between the XMOS and some kind of host.  In this case, the XMOS
   provides a USB CDC interface which a host PC can then connect to.
 * A way to parse the commands that come in over the CDC interface and do something with that
   information.
 * An I2C interface for communicating with a pressure sensor.
 * A way to signal with the stepper motor driver.

The following files are found in this directory, with a description of each included:

 * **main.xc**:  The various ports, channels, and tile assignments are included here, as well as the main
   *par* statement for the application tasks.  The parallel tasks are as follows:
    * **ps_config**:  This is the parser for the CDC interface; commands that are accepted by the
      device are defined here, and then actions are performed based on those commands.
    * **ps_data**:  There are actually two communication channels that are established by the
      firmware; the data channels allows a program separate from the configuration program to
      collect data from the device.
    * **wf_calc**:  This is a 'waveform calculator', which determines how many steps that motor must
      take in what amount of time, based on current time and position.
    * **measurement_mgr**:  This task determines when to take a pressure measurement.
    * **i2c_master**:  The I2C peripheral on the XMOS is controlled via an interface.
    * **watchdog**:  Because this system operates in a high noise environment, communication may
      sometimes drop.  The watchdog will reboot the system in case it loses communication with a
      host so that it doesn't go off and do any unintended operations.
 * **measurement_mgr.xc**:  Controls when a measurement should be taken, and when/how the stepper
   motor should move.
 * **ps_app.h**:  Header file that provides function prototypes.
 * **ps_config.xc**:  Sets up the command parser, as well as provides an interface for re-flashing
   the device.
 * **ps_data.xc**:  Moves data off of the chip.
 * **ps_indicators.h**:  Header file which provides numeric definitions for certain constants that
   are used in multiple places throughout the application.
 * **ps_version.h**:  Provides versioning information that can then be read by a host.  Use the
   'create_version.py' script to generate this file, or use the current file as a template and
   hard-code values.
 * **sine_table.xc**:  Respiration has an effect, roughly sinusoidal, on heart-rate.  The constants
   in this table are used to speed up/slow down the heart-rate, i.e. to simulate a person breathing
   in and out.
 * **wf_calc.xc**:  Calculates the waveform points based on parameters provided via the
   configuration interface.
 * **xud_cdc.h**:  Header file that provides prototypes of the various functions used to provide the
   CDC interface.  This file was slightly modified from the example code provided by XMOS.
 * **xud_cdc.xc**:  Defines the functions that are used for the CDC interface.
