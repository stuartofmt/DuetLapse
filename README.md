# DuetLapse
Time Lapse camera support for Duet based 3D printers.  Extending the work of Danal Estes

# FORK CHANGES
- Added ability to capture from raspberry pi camera when it is already being used by another process (avoids ENOSPC errors)
  A new camera type *ffmpeg*.  Takes a url to identify the video stream (in the example it is stream.mjpg)
  
  *e.g.  /usr/bin/python3 <path>/DuetLapse.py -duet <ip address> -camera ffmpeg -weburl http://camera <IP:port>/stream.mjpg -detect layer*
  
- Added code to prevent two instances of DuetLapse.py running
 
- Added support for sending SIGINT to the process id and gracefully stop (and create video) when DuetLapse.py is running in the background (CTL+C cannot so this)
  e.g. kill -2 <pid>
  
 - Added configurable directory for the resultant video.   -basedir  <absolute path without trailing / >  the default is ~
 e.g. -basedir /home/pi/Lapse
 
 - Added ability to extend the end of the video by repeating the last frame -extratime n in seconds default is 0
 
 - Changed from print commands to logging option   -logtype [console, file, both] default is both. If console then only written to the console. If file or both then a logfile is written to basedir with the name DuelLapse.log  If both then written to the console and the logfile.  Messages are prefixed by the ip address set by -duet.  This is to distinguish between printers if multiple are used (see also -instances (below) 
 
 - added a switch for inhibiting multiple instances -instances [single, oneip, many] default is single.  If single then the highlander principle applies. If oneip then only one instance per duet ip address (set by the -duet ip address).  If many then it's the wild west.
 
# ORIGINAL follows

Designed to run on a Raspberry Pi, may be adaptable to other platforms. Supports cameras via USB, Pi (ribbon cable), and Webcam.  May support DSLR triggering in the future. Produces a video with H.264 encoding in an MP4 container. Does not, at this time, manage a library of videos, it simply drops the vid in home directory. 

Triggers images based on time, layer change, or pause.  Works with existing pauses in G-Code, or can force pauses at other trigger events. Optionally moves head to a specified position before capturing paused images. 

## Status

As of April 14, 2020, moving to Beta test status.  I believe the Alpha testers have helped clear out the funadmental issues, thank you for your feedback. ~~As of April 2, 2020, ready for Alpha testing.~~ Feedback via issues on Github or at Duet forum https://forum.duet3d.com/


Status of Features.  Unchecked features are planned, coming soon:

Cameras:
- [X] USB Cam
- [X] Web Cam
- [X] Pi Cam
- [ ] DSLR Cam via USB
- [ ] GPIO pin to trigger any kind of camera

Other Features:
- [X] Detect Layer change
- [X] Intervals in seconds
- [ ] Detect Pauses
- [X] Force Pauses
- [X] Position Head during Pauses
- [X] Video output in H264 MP4
- [X] Unique names for Videos
- [ ] Add a timestamp in one corner of vid. Analog or Digital? Or option. 
- [ ] While gathering stills, skip frames that cause errors, without terminating entire script. 
- [ ] Run in a daemon like status, supporting multiple print jobs, one after another. 
- [X] Allow override of command line switches for still capture programs. (fswebcam, raspistill, wget)
- [X] Allow override of command line switches for ffmpeg 

## Installation
* mkdir DuetLapse
* cd DuetLapse
* wget https://raw.githubusercontent.com/DanalEstes/DuetLapse/master/DuetLapse.py
* chmod 744 DuetLapse.py
* wget https://raw.githubusercontent.com/DanalEstes/DuetWebAPI/master/DuetWebAPI.py


## Corequisites 

* Python3 (already installed on most Pi images)
* Duet printer must be RRF V2, RRF V3, or RRF V3 + Pi
* May run on, but NOT required to run on, the printer's Pi in a RRF V3 + Pi configuration
* Duet printer must be reachable via network
* ffmpeg (always)
* Depending on camera type, one of
  * fswebcam (for USB cameras)
  * raspistill (for Pi cam or Ardu cam)
  * wget (for Web cameras)
  
## Usage

Start the script, usually *./DuetLapse \[options\]*, before starting a print.  It will connect to the printer and wait for the printer to change status from "Idle" to "Processing" and then begin capturing still images per the flag settings.  When the printer then goes "idle" again (i.e. end of print), it will process the still images into a video. 

```
usage: DuetLapse.py [-h] -duet DUET [-camera {usb,pi,web,dslr}]
                    [-seconds SECONDS] [-detect {layer,pause,none}]
                    [-pause {yes,no}] [-movehead MOVEHEAD MOVEHEAD]
                    [-weburl WEBURL] [-dontwait]
                    {camparms,vidparms} ...

Program to create time lapse video from camera pointed at Duet3D based
printer.

optional arguments:
  -h, --help            show this help message and exit
  -duet DUET            Name or IP address of Duet printer.
  -camera {usb,pi,web,dslr}
  -seconds SECONDS
  -detect {layer,pause,none}
  -pause {yes,no}
  -movehead MOVEHEAD MOVEHEAD
  -weburl WEBURL
  -dontwait             Capture images immediately.

subcommands:
  {camparms,vidparms}   DuetLapse camparms -h or vidparms -h for more help
```

## Usage Notes

This script is in rapid development, and runnith ./DuetLapse.py -h is likely to give more recent usage information. 

The only required flag is -duet to specify the printer to which the script will connect.  If not specified, camera defaults to "USB" and detection defaults to "layer". Example:
```
./DuetLapse.py -duet 192.168.7.101 
```

Many options can be combined.  For example, the script can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options. 

Example: Use a webcam that requires a UserId and Password, trigger every 30 seconds, do not detect any other triggers:
```
./DuetLapse.py -camera web -weburl http://userid:password@192.168.7.140/cgi-bin/currentpic.cgi -duet 192.168.7.101 -seconds 20 -detect none
```
Example: Default to USB camera and detecting layer changes, force pauses (at layer change) and move head to X10 Y10 before taking picture.
```
./DuetLapse.py -duet 192.168.7.101 -pause yes -movehead 10 10
```


  

