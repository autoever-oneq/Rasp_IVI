import RPi.GPIO as GPIO
import time

relay_pin = 26 
relay_active = 0

GPIO.setmode(GPIO.BCM)
GPIO.setup(relay_pin, GPIO.OUT, initial=GPIO.LOW)
time.sleep(2)
GPIO.cleanup()

def update_relay_active(val):
    global relay_active
    
    if val > 24:
        relay_active = 1
    else :
        relay_active = 0
        
    # relay_active = val

    
def relay_on():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(relay_pin, GPIO.OUT, initial=GPIO.LOW) 

    
def relay_off():
    GPIO.cleanup()

def execute_fan(val):
    update_relay_active(val)
    
    if relay_active == 1:
        relay_on()
    else:
        relay_off()  
      
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(relay_pin, GPIO.OUT, initial=GPIO.LOW) 

    

# GPIO.output(relay_pin, GPIO.LOW)  # 릴레이 ON (Low-Active)
# GPIO.output(relay_pin, GPIO.HIGH)  # 릴레이 OFF




