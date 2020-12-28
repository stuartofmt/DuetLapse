#!/usr/bin/env python3
# Python Script to take Time Lapse photographs during a print on 
#   a Duet based 3D printer and convert them into a video. 
#
# Copyright (C) 2020 Danal Estes all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
# Implemented to run on Raspbian on a Raspberry Pi.  May be adaptable to other platforms. 
# For USB or Pi camera, must run on a Raspberry Pi that is attached to camera.
# For dlsr USB cameras, must run on a Raspberry Pi that owns the interface to the camera.  
# For Webcam, the camera must be network reachable and via a defined URL for a still image.
# 
# The Duet printer must be RepRap firmware V2 or V3 and must be network reachable. 
#

import subprocess
import sys
import argparse
import time

 
#DuetLapse Code starts here

try: 
    import DuetWebAPI as DWA
except ImportError:
    logger.info("Python Library Module 'DuetWebAPI.py' is required. ")
    logger.info("Obtain from https://github.com/DanalEstes/DuetWebAPI ")
    logger.info("Place in same directory as script, or in Python libpath.")
    exit(2)

try: 
    import numpy as np
except ImportError:
    logger.info("Python Library Module 'numpy' is required. ")
    logger.info("Obtain via 'sudo python3 -m pip install numpy'")
    logger.info("Obtain pip via 'sudo apt install python-pip'")
    exit(2)


# Globals.
zo = -1                 # Z coordinate old
frame = 0               # Frame counter for file names
printerState  = 0       # State machine for print idle before print, printing, idle after print. 
timePriorPhoto = 0      # Time of last interval based photo, in time.time() format. 
alreadyPaused  = False  # If printer is paused, have we taken our actions yet? 

###########################
# Methods begin here
###########################


def init():
    # parse command line arguments
    parser = argparse.ArgumentParser(description='Program to create time lapse video from camera pointed at Duet3D based printer.', allow_abbrev=False)
    parser.add_argument('-duet',type=str,nargs=1,default=['localhost'],help='Name or IP address of Duet printer.')
    parser.add_argument('-camera',type=str,nargs=1,choices=['usb','pi','ffmpeg','web','dslr'],default=['usb'])
    parser.add_argument('-seconds',type=float,nargs=1,default=[0])
    parser.add_argument('-detect',type=str,nargs=1,choices= ['layer', 'pause', 'none'],default=['layer'])
    parser.add_argument('-pause',type=str,nargs=1,choices= ['yes', 'no'],default=['no'])
    parser.add_argument('-movehead',type=float,nargs=2,default=[0.0,0.0])
    parser.add_argument('-weburl',type=str,nargs=1,default=[''])
    parser.add_argument('-basedir',type=str,nargs=1,default=['~'])
    parser.add_argument('-extratime',type=float,nargs=1,default=[0])
    parser.add_argument('-instances',type=str,nargs=1,choices=['single','oneip','many'],default=['single'])
    parser.add_argument('-logtype',type=str,nargs=1,choices=['console','file','both'],default=['both'])
    parser.add_argument('-dontwait',action='store_true',help='Capture images immediately.')
    #parser.add_argument('--', '-camparm',type=str,nargs=argparse.REMAINDER,default=[''], dest='camparm', help='Extra parms to pass to fswebcam, raspistill, or wget.  Must come last. ')
    subparsers = parser.add_subparsers(title='subcommands',help='DuetLapse camparms -h  or vidparms -h for more help')
    pcamparm   = subparsers.add_parser('camparms',description='camparm -parms xxx where xxx is passed to fswebcam, raspistill, or wget.')
    pcamparm.add_argument('--','-parms', type=str,nargs=argparse.REMAINDER,default=[''], dest='camparms', help='Extra parms to pass to fswebcam, raspistill, or wget.')
    pcamparm   = subparsers.add_parser('vidparms',description='vidparms -parms xxx where xxx is passed to ffmpeg.')
    pcamparm.add_argument('--','-parms', type=str,nargs=argparse.REMAINDER,default=[''], dest='vidparms', help='Extra parms to pass to fswebcam, raspistill, or wget.')
    args=vars(parser.parse_args())

    global duet, camera, seconds, detect, pause, movehead, weburl, basedir, extratime, instances, logtype, dontwait, camparms, vidparms
    duet     = args['duet'][0]
    camera   = args['camera'][0]
    seconds  = args['seconds'][0]
    detect   = args['detect'][0]
    pause    = args['pause'][0]
    movehead = args['movehead']
    weburl   = args['weburl'][0]
    basedir  = args['basedir'] [0]
    extratime = str(args['extratime'] [0])
    instances = args['instances'] [0]
    logtype   = args['logtype'] [0]
    dontwait = args['dontwait']
    camparms = ['']
    if ('camparms' in args.keys()): camparms = args['camparms']
    camparms = ' '.join(camparms)
    vidparms = ['']
    if ('vidparms' in args.keys()): vidparms = args['vidparms']
    vidparms = ' '.join(vidparms)
    
 #Check to see if this instance is allowed to run 
 
    proccount = 0
    allowed = 0
       
    # Check to see if multiple instances allowed
    import psutil
    for p in psutil.process_iter():      
         if 'python3' in p.name() and __file__ in p.cmdline():
              proccount += 1
              if ('single' in instances):
                   allowed += 1
              if ('oneip' in instances):
                   if duet in p.cmdline():
                        allowed += 1
       
    if (allowed > 1):
           print('Process is already running...')
           sys.exit(1)          
    
# Create a custom logger
    import logging
    global logger
    logger = logging.getLogger('DuetLapse')
    logger.setLevel(logging.DEBUG)

# Create handlers and formats
    if ('console' in logtype or 'both' in logtype) : 
        c_handler = logging.StreamHandler()
        c_format = logging.Formatter(duet+' %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)
   
   
    if ('file' in logtype or 'both' in logtype) :
        if (proccount > 1):
             f_handler = logging.FileHandler(basedir+'/DuetLapse.log', mode='a')
        else:
             f_handler = logging.FileHandler(basedir+'/DuetLapse.log', mode='w')        

        f_format = logging.Formatter(duet+' - %(asctime)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
   

    # Warn user if we havent' implemented something yet. 
    if ('dlsr' in camera):
        logger.info('DuetLapse.py: error: Camera type '+camera+' not yet supported.')
        exit(2)

    # Inform regarding valid and invalid combinations
    if ((seconds > 0) and (not 'none' in detect)):
        logger.info('Warning: -seconds '+str(seconds)+' and -detect '+detect+' will trigger on both.')
        logger.info('Specify "-detect none" with "-seconds" to trigger on seconds alone.')

    if ((not movehead == [0.0,0.0]) and ((not 'yes' in pause) and (not 'pause' in detect))):
        logger.info('Invalid Combination: "-movehead {0:1.2f} {1:1.2f}" requires either "-pause yes" or "-detect pause".'.format(movehead[0],movehead[1]))
        exit(2)

    if (('yes' in pause) and ('pause' in detect)):
        logger.info('Invalid Combination: "-pause yes" causes this script to pause printer when')
        logger.info('other events are detected, and "-detect pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These are fundamentally incompatible.')
        exit(2)

    if ('pause' in detect):
        logger.info('************************************************************************************')
        logger.info('* Note "-detect pause" means that the G-Code on the printer already contains pauses,')
        logger.info('* and that this script will detect them, take a photo, and issue a resume.')
        logger.info('* Head position during those pauses is can be controlled by the pause.g macro ')
        logger.info('* on the duet, or by specifying "-movehead nnn nnn".')
        logger.info('*')
        logger.info('* If instead, it is desired that this script force the printer to pause with no')
        logger.info('* pauses in the gcode, specify either:')
        logger.info('* "-pause yes -detect layer" or "-pause yes -seconds nnn".')
        logger.info('************************************************************************************')


    if ('yes' in pause):
        logger.info('************************************************************************************')
        logger.info('* Note "-pause yes" means this script will pause the printer when the -detect or ')
        logger.info('* -seconds flags trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this script detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "-detect pause"')
        logger.info('************************************************************************************')

        
    # Check for requsite commands
    if ('usb' in camera):
        if (20 > len(subprocess.check_output('whereis fswebcam', shell=True))):
            logger.info("Module 'fswebcam' is required. ")
            logger.info("Obtain via 'sudo apt install fswebcam'")
            exit(2)

    if ('pi' in camera):
        if (20 > len(subprocess.check_output('whereis raspistill', shell=True))):
            logger.info("Module 'raspistill' is required. ")
            logger.info("Obtain via 'sudo apt install raspistill'")
            exit(2)

    if ('ffmpeg' in camera):
        if (20 > len(subprocess.check_output('whereis ffmpeg', shell=True))):
            logger.info("Module 'ffmpeg' is required. ")
            logger.info("Obtain via 'sudo apt install ffmpeg'")
            exit(2)

    if ('web' in camera):
        if (20 > len(subprocess.check_output('whereis wget', shell=True))):
            logger.info("Module 'wget' is required. ")
            logger.info("Obtain via 'sudo apt install wget'")
            exit(2)

    if (20 > len(subprocess.check_output('whereis ffmpeg', shell=True))):
        logger.info("Module 'ffmpeg' is required. ")
        logger.info("Obtain via 'sudo apt install ffmpeg'")
        exit(2)




    # Get connected to the printer.

    logger.info('Attempting to connect to printer at '+duet)
    global printer
    printer = DWA.DuetWebAPI('http://'+duet)
    if (not printer.printerType()):
        logger.info('Device at '+duet+' either did not respond or is not a Duet V2 or V3 printer.')
        exit(2)
    printer = DWA.DuetWebAPI('http://'+duet)

    logger.info("Connected to a Duet V"+str(printer.printerType())+" printer at "+printer.baseURL())

    # Tell user options in use. 
    logger.info('')
    logger.info("#####################################")
    logger.info("# Options in force for this run:    #")
    logger.info("# camera      = {0:20s}#".format(camera))
    logger.info("# printer     = {0:20s}#".format(duet))
    logger.info("# seconds     = {0:20s}#".format(str(seconds)))
    logger.info("# detect      = {0:20s}#".format(detect))
    logger.info("# pause       = {0:20s}#".format(pause))
    logger.info("# camparms    = {0:20s}#".format(camparms))
    logger.info("# vidparms    = {0:20s}#".format(vidparms))
    logger.info("# movehead    = {0:6.2f} {1:6.2f}       #".format(movehead[0],movehead[1]))
    logger.info("# dontwait    = {0:20s}#".format(str(dontwait)))
    logger.info("# basedir     = {0:20s}#".format(basedir))
    logger.info("# extratime   = {0:20s}#".format(extratime))
    logger.info("#####################################")
    logger.info('')

    # Clean up directory from past runs.  Be silent if it does not exist. 
    subprocess.call('rm -r /tmp/DuetLapse > /dev/null 2>&1', shell=True)
    subprocess.call('mkdir /tmp/DuetLapse', shell=True)



def checkForcePause():
    # Called when some other trigger has already happend, like layer or seconds.
    # Checks to see if we should pause; if so, returns after pause and head movement complete.
    global alreadyPaused
    if (alreadyPaused): return
    if (not 'yes' in pause): return
    logger.info('Requesting pause via M25')
    printer.gCode('M25')    # Ask for a pause
    printer.gCode('M400')   # Make sure the pause finishes
    alreadyPaused = True 
    if(not movehead == [0.0,0.0]):
        logger.info('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(movehead[0],movehead[1]))
        printer.gCode('G1 X{0:4.2f} Y{1:4.2f}'.format(movehead[0],movehead[1]))
        printer.gCode('M400')   # Make sure the move finishes

def unPause():
    global alreadyPaused
    if (alreadyPaused):
        logger.info('Requesting un pause via M24')
        printer.gCode('M24')

def onePhoto():
    global frame
    frame += 1
    s="{0:08d}".format(int(np.around(frame)))
    fn = '/tmp/DuetLapse/IMG'+s+'.jpeg'

    if ('usb' in camera): 
        if (camparms == ''):
            cmd = 'fswebcam --quiet --no-banner '+fn
        else:
            cmd = 'fswebcam '+camparms+' '+fn
    if ('pi' in camera): 
        if (camparms == ''):
            cmd = 'raspistill -t 1 -ex sports -mm matrix -n -o '+fn
        else:
            cmd = 'raspistill  '+camparms+' -o '+fn
    if ('ffmpeg' in camera): 
        if (camparms == ''):
            cmd = 'ffmpeg -y -i ' +weburl+ ' -vframes 1 ' +fn
        else:
            cmd = 'ffmpeg '+camparms+' '+weburl+ ' -vframes 1 ' +fn

    if ('web' in camera): 
        if (camparms == ''):
            cmd = 'wget --auth-no-challenge -nv -O '+fn+' "'+weburl+'" '
        else:
            cmd = 'wget '+camparms+' -O '+fn+' "'+weburl+'" '

    subprocess.call(cmd, shell=True)
    global timePriorPhoto
    timePriorPhoto = time.time()


def oneInterval():
    global alreadyPaused
    global frame
    if ('layer' in detect):
        global zo
        zn=printer.getLayer()
        if (not zn == zo):
            # Layer changed, take a picture.
            checkForcePause()
            logger.info('Capturing frame {0:5d} at X{1:4.2f} Y{2:4.2f} Z{3:4.2f} Layer {4:d}'.format(int(np.around(frame)),printer.getCoords()['X'],printer.getCoords()['Y'],printer.getCoords()['Z'],zn))
            onePhoto()
        zo = zn
    global timePriorPhoto
    elap = (time.time() - timePriorPhoto)

    if ((seconds) and (seconds < elap)):
        checkForcePause()
        logger.info('Capturing frame {0:5d} after {1:4.2f} seconds elapsed.'.format(int(np.around(frame)),elap))
        onePhoto()

    if (('pause' in detect) and ('paused' in printer.getStatus()) and not alreadyPaused):
            alreadyPaused = True
            logger.info('Pause Detected, capturing frame {0:5d}'.format(int(np.around(frame)),elap))
            onePhoto()
            unPause()   

    if (alreadyPaused and (not 'paused' in printer.getStatus()) ):
        alreadyPaused = False
         

def postProcess():
    logger.info('')
    logger.info("Now making {0:d} frames into a video at 10 frames per second.".format(int(np.around(frame))))
    if (250 < frame): logger.info("This can take a while...")
#    fn = basedir+'/DuetLapse'+time.strftime('%m%d%y%H%M',time.localtime())+'.mp4'
    fn = basedir+'/DuetLapse-'+time.strftime('%a-%H:%M',time.localtime())+'.mp4'
    if (vidparms == ''):
         if extratime == '0':
              cmd  = 'ffmpeg -r 10 -i /tmp/DuetLapse/IMG%08d.jpeg -vcodec libx264 -y -v 8 '+fn
         else:
              cmd  = 'ffmpeg -r 10 -i /tmp/DuetLapse/IMG%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn
    else:
         if extratime == '0':
              cmd  = 'ffmpeg '+vidparms+' -i /tmp/DuetLapse/IMG%08d.jpeg '+fn 
         else:
              cmd  = 'ffmpeg '+vidparms+' -i /tmp/DuetLapse/IMG%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn
        
    subprocess.call(cmd, shell=True)
    logger.info('Video processing complete.')
    logger.info('Video is in file '+fn)
    exit()    

###########################
# Main begins here
###########################
init()
    
if (dontwait):
    logger.info('Not Waiting for print to start on printer '+duet)
    logger.info('Will take pictures from now until a print starts, ')
    logger.info('  continue to take pictures throughout printing, ')
else:
    logger.info('Waiting for print to start on printer '+duet)
    logger.info('Will take pictures when printing starts, ')
logger.info('  and make video when printing ends.')
logger.info('Or, press Ctrl+C one time to move directly to conversion step.')
logger.info('')


timePriorPhoto = time.time()

#Allows process running in background or foreground to be gracefully
# shutdown with SIGINT (kill -2 <pid>
import signal

def quit_gracefully(*args):
    logger.info('Stopped by SIGINT - Post Processing')
    postProcess()
    exit(0);

if __name__ == "__main__":
    signal.signal(signal.SIGINT, quit_gracefully)

try: 
    while(1):
        time.sleep(.77)            # Intentionally not evenly divisible into one second. 
        status=printer.getStatus()

        if (printerState == 0):     # Idle before print started. 
            if (dontwait):
                oneInterval()
            if ('processing' in status):
                logger.info('Print start sensed.')
                logger.info('End of print will be sensed, and frames will be converted into video.')
                logger.info('Or, press Ctrl+C one time to move directly to conversion step.')
                logger.info('')
                printerState = 1

        elif (printerState == 1):   # Actually printing
            oneInterval()
            if ('idle' in status):
                printerState = 2

        elif (printerState == 2):
            postProcess()
except KeyboardInterrupt:
    logger.info('Stopped by Ctl+C - Post Processing')
    postProcess()
   
