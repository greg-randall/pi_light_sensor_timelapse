import time
import os.path
from os import path
import re
import exifread
from python_tsl2591 import tsl2591
import statistics
from prettytable import PrettyTable
import numpy as np
import json
import collections 
import bisect 
import pickle

###################################################################################
#settings
###################################################################################
max_shutter_speed = 200 * 1000000 #200 seconds for the hq cam
image_x = 4056 #hq cam max res
image_y = 3040
isos = [100, 200, 400, 800] #dropped a few intermediate values

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


def shoot_photo_auto(w,h,shoot_raw,filename):
    if shoot_raw:
        raw = '--raw '
    else:
        raw = ''

    command = f"/home/pi/Desktop/userland/build/bin/raspistill {raw} -n -w {w} -h {h} -o {filename}"
    os.system(command)


def check_exposure(filename): #get an average brightness from an image 0-255
    command = f"convert {filename} -sample 300x300 -resize 1x1 -set colorspace Gray -format %c histogram:info:-"
    exposure = os.popen(command).read()

    exposure = re.search(r'\(\d{1,3}\)',exposure)
    exposure = re.search(r'\d{1,3}',exposure.group())

    return int(exposure.group())


def get_exif_shutter_speed(filename): #get the shutter speed from the exif data on an image
    f = open(filename,'rb')
    data = exifread.process_file(f)
    f.close()

    ss_raw = str(data['EXIF ExposureTime'])
    ss_split = ss_raw.split('/')
    
    return (float(ss_split[0])/float(ss_split[1]))


def ajustment_factor(exposure):
    #adjustment = 4.85641 - 0.05787792*exposure + 0.000227827*exposure**2 #ran a curve fitting on some values I decided were reasonable
    #adjustment= 4.709639 - 0.0563461*exposure + 0.000230955*exposure**2
    

    if exposure > ideal_exposure - (delta * 4) and exposure < ideal_exposure + (delta * 4):
        adjustment = 1.125
    else:
        adjustment = 4.722986 - 0.05614406*exposure + 0.0002296754*exposure**2

    return adjustment


def get_lux(debug=False):
    gains = [0x00, 0x10, 0x20, 0x30]
    integrations = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05]

    tsl = tsl2591() #start up light sensor

    lux_clean = []

    if debug:
        clean = PrettyTable()
        clean.field_names = ["lux", "integration", "gain", "full", "ir"]
        unclean = PrettyTable()
        unclean.field_names = ["lux", "integration", "gain", "full", "ir"]


    for integration in integrations:
        tsl.set_timing(integration)
        for gain in gains:
            tsl.set_gain(gain)
            data = tsl.get_current()
            #data = tsl.get_current()

            data['lux'] = calculate_lux(data['full'], data['ir'], integration, gain)

            
            if debug:
                unclean.add_row([data['lux'],data['integration_time'],data['gain'],data['full'],data['ir']])

            #remove the garbage values:
            #no lux under zero
            #no raw values over 65535, sensor saturates at 65535
            #no raw values of zero
            #no raw values of 37888 & 37889 -- seem to indicate sensor saturation

            if data['lux'] >= 0 and data['full'] < 65535 and data['ir'] < 65535 and  data['ir'] != 0 and data['full'] != 0 and data['full'] != 37888 and data['ir'] != 37888 and data['full'] != 37889 and data['ir'] != 37889:
                    lux_clean.append(data['lux'])
                    if debug:
                        clean.add_row([data['lux'],data['integration_time'],data['gain'],data['full'],data['ir']])

    median_lux = statistics.median(lux_clean)
    mean_lux = statistics.mean(lux_clean)
    lux = round(median_lux, 5)

    if debug:
        print(f"dirty:\n{unclean}")
        print(f"clean:\n{clean}")
        print(f"median:\n{lux}")
        print(f"mean:\n{round(mean_lux, 5)}")
    return lux


def calculate_lux(full, ir, integration_time, gain):
    if full == 0 or ir == 0:
        return 0
    else:
        full = float(full)
        ir = float(ir)
        lux_co = float(408)
        integration_numbers = {0x00 : float(100), 0x01 : float(200), 0x02 : float(300), 0x03 : float(400), 0x04 : float(500), 0x05 : float(600)}
        gain_numbers = {0x00 : float(1), 0x10 : float(25), 0x20 : float(248), 0x30 : float(9876)}
        #print(f"{full}, {ir}, {lux_co}, {integration_numbers[integration_time]}, {gain_numbers[gain]}")
        lux = (full - ir) * (1 - (ir / full)) / (( integration_numbers[integration_time] * gain_numbers[gain] ) / lux_co)

        return lux



###########################################################


debug = True
start_time = int(time.time())

print('Timelapse Started:')   




lux = get_lux(debug)
if debug:
	print(f"get lux seconds elapsed: {int(time.time())-start_time}")

if path.exists("lux-exposure-dict"):
    with open('lux-exposure-dict', 'rb') as handle:
        lux_exposure_dict = pickle.loads(handle.read())
    closest = min(lux_exposure_dict, key=lambda x:abs(x-lux))
    shutter_speed =lux_exposure_dict[closest]
    if shutter_speed >= max_shutter_speed:
        shutter_speed -= 10

    if debug:
	    print(f"open lookup table seconds elapsed: {int(time.time())-start_time}")

    if debug:
        print(f'shooting photo: {round(shutter_speed/1000000,3)} seconds')
    shoot_photo(shutter_speed , 100, 1296, 976,False,'test.jpg')
    exposure = check_exposure('test.jpg')
    
    if debug:
        print(f"from look-up-table:\n  lux reading: {lux}\n  closest lux in dict: {closest}\n  shutter speed from in dict: {shutter_speed}\n")
        print(f"shoot test photo from lookup seconds elapsed: {int(time.time())-start_time}")

else:
    shoot_photo_auto(1296, 976,False,'test.jpg')
    shutter_speed = get_exif_shutter_speed('test.jpg') * 1000000 #convert shutter speed to microseconds
    exposure = check_exposure('test.jpg')
    if debug:
	    print(f"shoot auto photo seconds elapsed: {int(time.time())-start_time}")

#need to get iso from test photo too in the dark the camera auto ups iso, need to use iso value to change shutter speed 


print(f"shutter speed,\tlux,\t\texposure,\tadjustment,\tfull shutter speed")




print(f"{round(shutter_speed/1000000,4)},\t\t{lux},\t\t{exposure},\t\t0,\t\t{int(shutter_speed)}")


adjustment = ajustment_factor(exposure)

if debug:
	print(f"before loop seconds elapsed: {int(time.time())-start_time}")

#test for case where max shutter speed is hit but exposure is ***too*** bright
trials = 0
while exposure < (ideal_exposure-delta) or exposure > (ideal_exposure+delta) and shutter_speed < max_shutter_speed: #or iso-- add code to push iso if max shutter speed hit
    
    if exposure < ideal_exposure:
        shutter_speed = int(shutter_speed * adjustment) #longer shutter speed
    else:
        shutter_speed = int(shutter_speed / adjustment) #longer shorter speed


    if shutter_speed>max_shutter_speed: #make sure we don't go past the longest shutter speed
        shutter_speed = max_shutter_speed

    shoot_photo(shutter_speed , 100, 1296, 976,False,'test.jpg')
    exposure = check_exposure('test.jpg')

    adjustment = ajustment_factor(exposure)

    print(f"{round(shutter_speed/1000000,4)},\t\t{lux},\t\t{exposure},\t\t{round(adjustment,3)},\t\t{int(shutter_speed)}")

    if exposure > (ideal_exposure+delta) and shutter_speed >= (max_shutter_speed): #if the shot image is too bright, and the max shutter speed is exceeded then the loop finishes,
        shutter_speed = max_shutter_speed - 10                                     #this makes sure that the loop continues if the image is 

    if trials >= 10:
        break
    else:
        trials +=1

if shutter_speed >= max_shutter_speed and exposure < (ideal_exposure-delta):
    for iso in isos :
        print(pet)


if debug:
	print(f"finish loop seconds elapsed: {int(time.time())-start_time}")

lux = get_lux(debug)
if debug:
	print(f"get fresh lux for table seconds elapsed: {int(time.time())-start_time}")

exif_shutter = get_exif_shutter_speed('test.jpg')
filename_time = int(time.time())
filename = f"{filename_time}.jpg"
os.system(f"mv test.jpg {filename}")

if debug:
	print(f"rename files seconds elapsed: {int(time.time())-start_time}")


#shoot full image
#shoot_photo(shutter_speed, 100, image_x, image_y,true,filename)


log_line = f"{filename_time},{exposure},{lux},{int(shutter_speed)},{int(time.time())-start_time},{trials}"
print(f"\n\nlog data:\n{log_line}")
f=open("calibrate_cam_data.csv", "a+")
f.write(f"{log_line}\n")
f.close()

if debug:
	print(f"data log seconds elapsed: {int(time.time())-start_time}")

if path.exists("lux-exposure-dict"):
    lux_exposure_dict.update({lux : shutter_speed})
else:
    lux_exposure_dict = {lux : shutter_speed}

with open('lux-exposure-dict', 'wb') as handle:
    pickle.dump(lux_exposure_dict, handle)

if debug:
	print(f"final seconds elapsed: {int(time.time())-start_time}")

