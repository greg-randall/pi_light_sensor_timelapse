import time
from datetime import datetime
import os
import os.path
from os import path
import re
import exifread
import math
import mmap

import json

from python_tsl2591 import tsl2591

from fractions import Fraction

#settings for hq cam
max_shutter_speed = 200 * 1000000 #200 seconds for the hq cam
#image_x = 4056 #hq cam res
#image_y = 3040

ideal_exposure=110
delta=5


tsl = tsl2591()


def shoot_photo(ss,iso,w,h,shoot_raw,filename):
    if shoot_raw:
        raw = '--raw '
    else:
        raw = ''
        
    if ss<1000000:
        exposure = ''
    else:
        exposure = '-ex off'
    
    command = f"/home/pi/Desktop/userland/build/bin/raspistill {raw} -md 3 {exposure} -n -ss {ss} -w {w} -h {h} -ISO {iso} -o {filename}"
    os.system(command)


def shoot_photo_auto(ev,w,h,shoot_raw,filename):
    if shoot_raw:
        raw = '--raw '
    else:
        raw = ''
    command = f"/home/pi/Desktop/userland/build/bin/raspistill {raw} -n -ev {ev} -w {w} -h {h} -o {filename}"
    os.system(command)


def check_exposure (filename):
    command = f"convert {filename} -sample 300x300 -resize 1x1 -set colorspace Gray -format %c histogram:info:-"
    exposure = os.popen(command).read()
    exposure = re.search(r'\(\d{1,3}\)',exposure)
    exposure = re.search(r'\d{1,3}',exposure.group())
    return int(exposure.group())


def get_exif(filename):
    f = open(filename,'rb')
    data = exifread.process_file(f)
    ss_raw = str(data['EXIF ExposureTime'])
    ss_split = ss_raw.split('/')
    f.close()
    return (float(ss_split[0])/float(ss_split[1]))


def get_light():
    light_sensor = tsl.get_current()
    return light_sensor["full"]



print(f"shutter speed,\tlight units,\texposure,\tadjustment,\tfull shutter speed")
light_units = get_light()
#shutter_speed = lux_to_shutter_speed(lux)
shoot_photo_auto(0,1296, 976,False,'test.jpg')
shutter_speed = get_exif('test.jpg') * 1000000
exposure = check_exposure('test.jpg')
print(f"{round(shutter_speed/1000000,3)},\t\t{round(light_units,2)},\t\t{exposure},\t\t0,\t\t{round(shutter_speed)}")




while exposure < (ideal_exposure-delta) or exposure > (ideal_exposure+delta) and (shutter_speed/1000000) <199.9: #or iso
    
    adjustment = 4.85641 - 0.05787792*exposure + 0.000227827*exposure**2

    if exposure < ideal_exposure:
        shutter_speed = round(shutter_speed * adjustment)
    else:
        shutter_speed = round(shutter_speed / adjustment)

    if shutter_speed>max_shutter_speed:
        shutter_speed = max_shutter_speed

    
    shoot_photo(shutter_speed , 100, 1296, 976,False,'test.jpg')
    exposure = check_exposure('test.jpg')
 
    adjustment = 4.85641 - 0.05787792 * exposure + 0.000227827 * exposure**2

    light_units = get_light()
    print(f"{round(shutter_speed/1000000,3)},\t\t{light_units},\t\t{exposure},\t\t{round(adjustment,2)},\t\t{round(shutter_speed)}")




#code for iso

exif_shutter = get_exif('test.jpg')

filename_time = int(time.time())
filename = f"{filename_time}.jpg"
os.system(f"mv test.jpg {filename}")


#shoot full image
#shoot_photo(shutter_speed, 100, image_x, image_y,true,filename)



f=open("calibrate_cam_data.txt", "a+")
timestamp = dateTimeObj = datetime.now()

log_line = f"{filename_time},{round(shutter_speed/1000000,3)},{exif_shutter},{light_units},{exposure},{round(adjustment,2)},{round(shutter_speed)}"
print(f"\n\nlog data:\n{log_line}")
f.write(f"{log_line}\n")
f.close()
