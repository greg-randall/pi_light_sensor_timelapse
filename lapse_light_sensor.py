import time
import os.path
from os import path
import re
import exifread
from python_tsl2591 import tsl2591
import statistics
import numpy as np
import json
import collections 
import bisect 
import pickle

###################################################################################
#settings
###################################################################################
max_shutter_speed = 239 * 1000000 #200 seconds for the hq cam, but camera works in millionths of a second
image_x = 4056 #hq cam max res
image_y = 3040
iso = 100 # starting iso
isos = [200, 400, 800] #dropped 100 since that's the default, also dropped a few intermediate values. 
                       #camera seems to respond to higher isos, but the images don't get brighter
                       #camera also seems to respond to isos lower than 100 but 100 is base iso
#0-255 is the exposure range
ideal_exposure=110
#delta is how far from the ideal you're welling to go, ~5 is pretty reasonable, smaller 
#probably requires modifications to the code
delta=5
#####################################################################################

def shoot_photo(ss,iso,w,h,shoot_raw,filename): 
    if shoot_raw:
        raw = '--raw '
    else:
        raw = ''
    if ss<1000000: #it seems like having auto exposure on for exposures longer than about a second takes FOREVER to shoot a photo. below a second doesn't seem to make a difference
        exposure = ''
    else:
        exposure = '-ex off'
    command = f"/home/pi/Desktop/userland/build/bin/raspistill {raw} -md 3 {exposure} -n -ss {ss} -w {w} -h {h} -ISO {iso} -o {filename}"
    os.system(command)

    #debug:
    f=open("log_commands.txt", "a+")
    f.write(f"{command}\n")
    f.close()

def shoot_photo_auto(w,h,shoot_raw,filename):
    #shoot a photo on auto exposure
    if shoot_raw:
        raw = '--raw '
    else:
        raw = ''
    command = f"/home/pi/Desktop/userland/build/bin/raspistill {raw} -n -w {w} -h {h} -o {filename}"
    os.system(command)

def check_exposure(filename): 
    #get an average brightness from an image 0-255
    command = f"convert {filename} -sample 300x300 -resize 1x1 -set colorspace Gray -format %c histogram:info:-" #this order of sample, resize and colorspace seems to be the fastest
    exposure = os.popen(command).read()
    exposure = re.search(r'\(\d{1,3}\)',exposure)
    exposure = re.search(r'\d{1,3}',exposure.group())
    return int(exposure.group())

def get_exif_shutter_speed(filename): 
    #get the shutter speed from the exif data on an image
    f = open(filename,'rb')
    data = exifread.process_file(f)
    f.close()
    ss_raw = str(data['EXIF ExposureTime'])
    ss_split = ss_raw.split('/')
    return (float(ss_split[0])/float(ss_split[1]))

def ajustment_factor(exposure):
    #ran a curve fitting on some values I decided were reasonable for adjustment
    #larger differences from ideal give bigger adjustments
    if exposure > ideal_exposure - (delta * 4) and exposure < ideal_exposure + (delta * 4):
        adjustment = 1.125
    else:
        adjustment = 4.722986 - 0.05614406*exposure + 0.0002296754*exposure**2
    return adjustment
    
def get_lux():
    #the light sensor displays some odd behaivor over it's variaous gain and integration times.
    #this tests all combinations of gain/integration and throws out garbage data, and then returns
    #the median value
    gains = [0x00, 0x10, 0x20, 0x30]
    integrations = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05]
    tsl = tsl2591() #start up light sensor
    lux_clean = []
    for integration in integrations:
        tsl.set_timing(integration)
        for gain in gains:
            tsl.set_gain(gain)
            data = tsl.get_current()
            #data = tsl.get_current()
            data['lux'] = calculate_lux(data['full'], data['ir'], integration, gain)           
            #remove the garbage values:
            #no lux under zero
            #no raw values over 65535, sensor saturates at 65535
            #no raw values of zero
            #no raw values of 37888 & 37889 -- seem to indicate sensor saturation on certain modes
            if data['lux'] >= 0 and data['full'] < 65535 and data['ir'] < 65535 and  data['ir'] != 0 and data['full'] != 0 and data['full'] != 37888 and data['ir'] != 37888 and data['full'] != 37889 and data['ir'] != 37889:
                    lux_clean.append(data['lux'])
    median_lux = statistics.median(lux_clean)
    lux = round(median_lux, 5)
    return lux

def calculate_lux(full, ir, integration_time, gain):
    #the light sensor library calculation for lux is bad.
    #i've implimented the newer calculation based on the adafruit library
    if full == 0 or ir == 0:
        return 0
    else:
        full = float(full)
        ir = float(ir)
        lux_co = float(408)
        integration_numbers = {0x00 : float(100), 0x01 : float(200), 0x02 : float(300), 0x03 : float(400), 0x04 : float(500), 0x05 : float(600)}
        gain_numbers = {0x00 : float(1), 0x10 : float(25), 0x20 : float(248), 0x30 : float(9876)}
        lux = (full - ir) * (1 - (ir / full)) / (( integration_numbers[integration_time] * gain_numbers[gain] ) / lux_co)
        return lux

def pretty_shutter_speed(ss):
    if ss>1000000:
        return str(int(ss/1000000))
    else:
        shutter_speed_fractions = {0.000125 : "8000", 0.00015625 : "6400", 0.0002 : "5000", 0.00025 : "4000", 0.0003125 : "3200", 0.0004 : "2500", 0.0005 : "2000", 0.000625 : "1600", 0.0008 : "1250", 0.001 : "1000", 0.00125 : "800", 0.0015625 : "640", 0.002 : "500", 0.0025 : "400", 0.003125 : "320", 0.004 : "250", 0.005 : "200", 0.00625 : "160", 0.008 : "125", 0.01 : "100", 0.0125 : "80", 0.016666667 : "60", 0.02 : "50", 0.025 : "40", 0.033333333 : "30", 0.04 : "25", 0.05 : "20", 0.066666667 : "15", 0.076923077 : "13", 0.1 : "10", 0.125 : "8", 0.166666667 : "6", 0.2 : "5", 0.25 : "4", 0.333333333 : "3", 0.4 : "2.5", 0.5 : "2", 1.666666667 : "0.6", 3.333333333 : "0.3"}
        closest = min(shutter_speed_fractions, key=lambda x:abs(x-(ss/1000000)))
        shutter_speed_fraction = shutter_speed_fractions[closest]
        return f"1/{shutter_speed_fraction}"



###########################################################
debug = False

if debug:
    f=open("log_commands.txt", "a+")
    f.write(f"{int(time.time())} ------------------------------------------------------------\n")
    f.close()


start_time = int(time.time())
print(f"Shutter Speed,\tLux,\t\tExposure (0-255),\tAdjustment")


lux = get_lux()
if debug:
	print (f"\ndebug get lux Seconds Elapsed: {int(time.time())-start_time}")
if path.exists("lux-exposure-dict"): #if there's a dictonary of lux - shutter speed, use the closest value in the dictonary as a starting point for exposure
    with open('lux-exposure-dict', 'rb') as handle:
        lux_exposure_dict = pickle.loads(handle.read())
    if debug:
	    print (f"\ndebug dict read Seconds Elapsed: {int(time.time())-start_time}")
    #find the closest value in the lux dictonary
    closest = min(lux_exposure_dict, key=lambda x:abs(x-lux))
    shutter_speed = lux_exposure_dict[closest]
    #if exposure from the dictonary is at the maximum the exposure trails loop won't run, so we want to reduce the exposure a bit
    if shutter_speed >= max_shutter_speed:
        shutter_speed -= 10

    #shoot test photo with the shutter speed from the dictonary
    shoot_photo(shutter_speed, iso, image_x, image_y, True, 'test.jpg')
    exposure = check_exposure('test.jpg')    
    if debug:
	    print (f"\ndebug dict test shot Seconds Elapsed: {int(time.time())-start_time}")
else: #if there isn't a dictonary, shoot a photo on auto for the starting point
    shoot_photo_auto(image_x, image_y,True,'test.jpg')
    shutter_speed = get_exif_shutter_speed('test.jpg') * 1000000 #convert shutter speed to microseconds
    exposure = check_exposure('test.jpg')
    if debug:
	    print (f"\ndebug auto exposure Seconds Elapsed: {int(time.time())-start_time}")
#need to get iso from test photo too in the dark the camera auto ups iso, need to use iso value to change shutter speed 
print(f"{pretty_shutter_speed(shutter_speed)},\t\t{lux},\t{exposure},\t\t\t0")
adjustment = ajustment_factor(exposure)
#test for case where max shutter speed is hit but exposure is ***too*** bright


#shoot photos until an appropriate exposure is found
trials = 0 #count the number of trial exposures to limit how long this process takes
if debug:
	print (f"\ndebug starting loop Seconds Elapsed: {int(time.time())-start_time}")
while exposure < (ideal_exposure-delta) or exposure > (ideal_exposure+delta) and shutter_speed < max_shutter_speed:
    #adjust the shutter speed up or down using the adjustment factor number
    if exposure < ideal_exposure:
        shutter_speed = int(shutter_speed * adjustment) #longer shutter speed
    else:
        shutter_speed = int(shutter_speed / adjustment) #longer shorter speed
    if shutter_speed>max_shutter_speed: #make sure we don't go past the longest shutter speed
        shutter_speed = max_shutter_speed
    shoot_photo(shutter_speed , iso, image_x, image_y,True,'test.jpg')
    exposure = check_exposure('test.jpg')
    adjustment = ajustment_factor(exposure)
    print(f"{pretty_shutter_speed(shutter_speed)},\t\t{lux},\t{exposure},\t\t\t{round(adjustment,3)}") #tell the user about the current trail shot
    if exposure > (ideal_exposure+delta) and shutter_speed >= (max_shutter_speed): #if the shot image is too bright, and the max shutter speed is exceeded then the loop would have finished finishes,
        shutter_speed = max_shutter_speed - 10                                     #this makes sure that the loop continues if the image is too bright
    if trials >= 10: #make sure our while loop doesn't do more than ten tirals
        break
    else:
        trials +=1
    if debug:
	    print (f"\ndebug inside loop Seconds Elapsed: {int(time.time())-start_time}")

#if we hit the max shutter speed, and it's still too dark we'll try pushing the iso:
if shutter_speed >= max_shutter_speed and exposure < (ideal_exposure-delta): 
    print('Maximum Shutter Speed Hit, Pushing ISO')
    for iso in isos:
        shoot_photo(shutter_speed , iso, image_x, image_y,True,'test.jpg')
        exposure = check_exposure('test.jpg')
        if exposure > (ideal_exposure-delta): 
            break
    if debug:
	    print (f"\ndebug iso loop Seconds Elapsed: {int(time.time())-start_time}")
    print(f'Pushed to {iso}')

lux=get_lux() #grab a fresh lux reading in case the outdoor lighting has changed
if debug:
	print (f"\ndebug get lux again Seconds Elapsed: {int(time.time())-start_time}")
#rename test shot as the final shot 
filename_time = int(time.time())
filename = f"{filename_time}.jpg"
os.system(f"mv test.jpg {filename}")
if debug:
	print (f"\ndebug rename files Seconds Elapsed: {int(time.time())-start_time}")

#extract raw file from jpg
os.system(f"python3 PyDNG/examples/utility.py {filename}")
if debug:
	print (f"\ndebug extract raws Seconds Elapsed: {int(time.time())-start_time}")
#remove raw from jpg and compress the jpeg a bit
os.system(f"convert {filename} -sampling-factor 4:2:0 -strip -quality 85 {filename}")
if debug:
	print (f"\ndebug compress jpg strip raw Seconds Elapsed: {int(time.time())-start_time}")

print (f"\nSeconds Elapsed: {int(time.time())-start_time}")




#write logging data
#file creation time in unix timestamp, exposure 0-255, lux, shutter speed in millionths of a second, iso, total time taken to shoot the photo, number of test exposures needed to get to a good exposure
log_line = f"{filename_time},{exposure},{lux},{int(shutter_speed)},{iso},{int(time.time())-start_time},{trials}"
f=open("calibrate_cam_data.csv", "a+")
f.write(f"{log_line}\n")
f.close()
if debug:
	print (f"\ndebug write out log Seconds Elapsed: {int(time.time())-start_time}")

#if the exposure from the library took too many tries delete it:
if trials >=3 and path.exists("lux-exposure-dict"):
    del lux_exposure_dict[closest]
    

#make sure we got a good exposure before we save it to the table
if exposure > (ideal_exposure-delta) and exposure < (ideal_exposure+delta):
    if path.exists("lux-exposure-dict"): #if the dictonary already exists we'll add a value to it
        lux_exposure_dict.update({lux : shutter_speed})
    else:
        lux_exposure_dict = {lux : shutter_speed} #if the dictonary doesn't exist we'll need to create a new dictonary
    with open('lux-exposure-dict', 'wb') as handle: #write out the dictonary to a file
        pickle.dump(lux_exposure_dict, handle)


if debug:
	print (f"\ndebug record dict Seconds Elapsed: {int(time.time())-start_time}")
