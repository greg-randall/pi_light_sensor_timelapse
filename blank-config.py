#rename file to 'config.py'
#current settings are for hq cam with wide angle lens, but you might be doing something different so be aware

#make sure to add your ftp info at the bottom

###################################################################################
#settings
###################################################################################
max_shutter_speed = 239 * 1000000 #239 seconds for the hq cam, but camera works in millionths of a second
image_x = 4056 #hq cam max res
image_y = 3040
iso = 100 # starting iso
isos = [400, 800] #dropped 100 since that's the default, also dropped a few intermediate values.
                       #camera seems to respond to higher isos, but the images don't get brighter
                       #camera also seems to respond to isos lower than 100 but 100 is base iso
                       
#0-255 is the exposure range
ideal_exposure=110

#delta is how far from the ideal you're welling to go, ~5 is pretty reasonable, smaller
#probably requires modifications to the code
delta=5

#prefix for the image names in case you have multiple cameras
filename_prefix = "camera_1_"

#remote folder prefix
remote_folder_prefix = "time-lapse-camera_"

#exposure trials, how many guesses the software gets at getting a good exposure
exposure_trials = 7

#lens focal lenght-- set so that you can use adobe dng profile corrections
lens_focal_length = 6 #mm

#turn on or off debugging information
debug = False

###################################################################################
#ftp config
###################################################################################
USER = 'username'
PASS = 'password'
SERVER = '192.168.1.0'
PORT = 21