import time
import os.path
import re
import exifread
from python_tsl2591 import tsl2591
import statistics
from sigfig import round

#settings for hq cam
max_shutter_speed = 200 * 1000000 #200 seconds for the hq cam
image_x = 4056 #hq cam max res
image_y = 3040

ideal_exposure=110
delta=5


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


def get_lux():
    gains = [0x00, 0x10, 0x20, 0x30]
    integrations = [0x00, 0x02, 0x03, 0x04, 0x05]

    tsl = tsl2591() #start up light sensor

    lux_clean = []

    for gain in gains:
        tsl.set_gain(gain)
        for integration in integrations:
            tsl.set_timing(integration)
            data = tsl.get_current()

            #remove the garbage values:
            #no lux under zero
            #no raw values over 65535, sensor saturates at 65535
            #no raw values of zero
            #no raw values over 37888 in integration mode 0x00, sensor saturates at 37888 in mode 0x00    

            if data['lux'] >= 0 and data['full'] < 65535 and data['ir'] < 65535 and  data['ir'] != 0 and data['full'] != 0:
                if integration != 0x00 and data['full'] != 37888 and data['ir'] != 37888:
                    lux_clean.append(data['lux'])

    lux = statistics.median(lux_clean)
    lux = round(lux, sigfigs=5)
    return lux



print(f"shutter speed,\tlux,\t\texposure,\tadjustment,\tfull shutter speed")

lux = get_lux()
shoot_photo_auto(1296, 976,False,'test.jpg')
shutter_speed = get_exif_shutter_speed('test.jpg') * 1000000 #convert shutter speed to microseconds
exposure = check_exposure('test.jpg')

print(f"{round(shutter_speed/1000000,decimals=3)},\t\t{lux},\t\t{exposure},\t\t0,\t\t{int(shutter_speed)}")


adjustment = ajustment_factor(exposure)

while exposure < (ideal_exposure-delta) or exposure > (ideal_exposure+delta) and shutter_speed < (max_shutter_speed - 1): #or iso-- add code to push iso if max shutter speed hit
    
    if exposure < ideal_exposure:
        shutter_speed = int(shutter_speed * adjustment) #longer shutter speed
    else:
        shutter_speed = int(shutter_speed / adjustment) #longer shorter speed


    if shutter_speed>max_shutter_speed: #make sure we don't go past the longest shutter speed
        shutter_speed = max_shutter_speed

    lux = get_lux()
    shoot_photo(shutter_speed , 100, 1296, 976,False,'test.jpg')
    exposure = check_exposure('test.jpg')

    adjustment = ajustment_factor(exposure)

    print(f"{round(shutter_speed/1000000,decimals=3)},\t\t{lux},\t\t{exposure},\t\t{round(adjustment,decimals=3)},\t\t{int(shutter_speed)}")





exif_shutter = get_exif_shutter_speed('test.jpg')

filename_time = int(time.time())
filename = f"{filename_time}.jpg"
os.system(f"mv test.jpg {filename}")


#shoot full image
#shoot_photo(shutter_speed, 100, image_x, image_y,true,filename)


log_line = f"{filename_time},{round(shutter_speed/1000000,3)},{exif_shutter},{lux},{exposure},{round(adjustment,decimals=2)},{round(shutter_speed,decimals=0)}"
print(f"\n\nlog data:\n{log_line}")

f=open("calibrate_cam_data.txt", "a+")
f.write(f"{log_line}\n")
f.close()
