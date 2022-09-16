try:
    import RPi.GPIO as GPIO
except:
    import Mock.GPIO as GPIO
import time

# Physical pin number (BOARD): 7, 15, 31, 37
# Chip GPIO pin number, "Broadcomm" (BCM): 4, 22, 6, 26
# anecdotic: wiringPI.h: 7, 3, 22, 25
# 'gpio readall' is your friend
relay = [4, 22, 6, 26]

GPIO.setmode(GPIO.BCM)
for i in range(4):
    GPIO.setup(relay[i], GPIO.OUT)

for i in range(4):
    GPIO.output(relay[i], GPIO.HIGH)
    time.sleep(1.2)
    GPIO.output(relay[i], GPIO.LOW)

GPIO.cleanup()
