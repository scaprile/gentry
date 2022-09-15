try:
    import RPi.GPIO as GPIO
except:
    import Mock.GPIO as GPIO
import time

# wiringPI(BOARD): 7, 3, 22, 25; Broadcomm(BCM): 4, 22, 6, 26
relay = [7, 3, 22, 25]

GPIO.setmode(GPIO.BOARD)
for i in range(4):
	GPIO.setup(relay[i], GPIO.OUT)

for i in range(4):
    GPIO.output(relay[i], GPIO.HIGH)
    time.sleep(1.2)
    GPIO.output(relay[i], GPIO.LOW)

GPIO.cleanup()
