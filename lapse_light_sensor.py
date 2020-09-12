import time
import os.path
import re
import exifread
from python_tsl2591 import tsl2591


#settings for hq cam
max_shutter_speed = 200 * 1000000 #200 seconds for the hq cam
image_x = 4056 #hq cam max res
image_y = 3040

ideal_exposure=110
delta=5


#tsl = tsl2591(integration=0x03) # i don't understand why changing integration time changes light level by 2-4x. seems like it should change a little bit +-10% not like +-400%? 
#tsl = tsl2591(gain=0x30) 
tsl = tsl2591() #start up light sensor


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


def get_light(): #get the raw light value from the sensor
    light_sensor = tsl.get_current()
    return light_sensor["full"]


def ajustment_factor(exposure):
    adjustment = 4.85641 - 0.05787792*exposure + 0.000227827*exposure**2 #ran a curve fitting on some values I decided were reasonable
    return adjustment


print(f"shutter speed,\tlight units,\texposure,\tadjustment,\tfull shutter speed")

light_units = get_light()
shoot_photo_auto(1296, 976,False,'test.jpg')
shutter_speed = get_exif_shutter_speed('test.jpg') * 1000000 #convert shutter speed to microseconds
exposure = check_exposure('test.jpg')

print(f"{round(shutter_speed/1000000,3)},\t\t{round(light_units,2)},\t\t{exposure},\t\t0,\t\t{round(shutter_speed)}")


adjustment = ajustment_factor(exposure)


while exposure < (ideal_exposure-delta) or exposure > (ideal_exposure+delta) and shutter_speed < (max_shutter_speed - 1): #or iso-- add code to push iso if max shutter speed hit
    
    if exposure < ideal_exposure:
        shutter_speed = round(shutter_speed * adjustment) #longer shutter speed
    else:
        shutter_speed = round(shutter_speed / adjustment) #longer shorter speed


    if shutter_speed>max_shutter_speed: #make sure we don't go past the longest shutter speed
        shutter_speed = max_shutter_speed

    light_units = get_light()
    shoot_photo(shutter_speed , 100, 1296, 976,False,'test.jpg')
    exposure = check_exposure('test.jpg')

    adjustment = ajustment_factor(exposure)

    print(f"{round(shutter_speed/1000000,3)},\t\t{light_units},\t\t{exposure},\t\t{round(adjustment,2)},\t\t{round(shutter_speed)}")





exif_shutter = get_exif_shutter_speed('test.jpg')

filename_time = int(time.time())
filename = f"{filename_time}.jpg"
os.system(f"mv test.jpg {filename}")


#shoot full image
#shoot_photo(shutter_speed, 100, image_x, image_y,true,filename)


log_line = f"{filename_time},{round(shutter_speed/1000000,3)},{exif_shutter},{light_units},{exposure},{round(adjustment,2)},{round(shutter_speed)}"
print(f"\n\nlog data:\n{log_line}")

f=open("calibrate_cam_data.txt", "a+")
f.write(f"{log_line}\n")
f.close()
