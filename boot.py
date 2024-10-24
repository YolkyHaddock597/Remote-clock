import network
import time
import socket
import _thread
from machine import Pin

# Pin setup
stpin = Pin(15, Pin.OUT)  # Step pin
dirpin = Pin(14, Pin.OUT)  # Direction pin
enbpin = Pin(13, Pin.OUT)  # Enable pin (added for reset functionality)
dirpin.value(1)  # Set direction to clockwise (1)

# Constants
STEPS_PER_REV = 6425  # Total steps per full revolution
DELAY = 0.001  # Delay between steps (in seconds)
HOURS_IN_CLOCK = 12  # Clock divided into 12 sections

# Shared state variables
current_position = (6 / HOURS_IN_CLOCK) * STEPS_PER_REV  # Start at 6:00
steps_to_move = 0
movement_ready = False
lock = _thread.allocate_lock()

# Function to move the motor clockwise (to run on core 1)
def move_motor():
    global steps_to_move, movement_ready, current_position

    while True:
        if movement_ready:
            # Acquire the lock before accessing shared variables
            with lock:
                for _ in range(steps_to_move):
                    stpin.value(1)
                    time.sleep(DELAY)
                    stpin.value(0)
                    time.sleep(DELAY)

                # Update position after movement
                current_position = (current_position + steps_to_move) % STEPS_PER_REV

                # Reset the movement flag
                movement_ready = False

# Function to set the clock hand to a specific hour (called from web server)
def set_time(target_hour):
    global steps_to_move, movement_ready, current_position
    
    if target_hour < 1 or target_hour > 12:
        print("Invalid input. Please enter an hour between 1 and 12.")
        return
    
    # Calculate the exact target position in steps
    target_position = (target_hour / HOURS_IN_CLOCK) * STEPS_PER_REV

    # Calculate the steps to move (always clockwise)
    if target_position >= current_position:
        steps_to_move = int(target_position - current_position)
    else:
        steps_to_move = int((STEPS_PER_REV - current_position) + target_position)

    # Set the movement flag and wait for core 1 to process it
    with lock:
        movement_ready = True

# Function to reset the clock time to 6:00
def reset_time():
    global current_position
    enbpin.value(1)  # Disable the stepper driver
    current_position = (6 / HOURS_IN_CLOCK) * STEPS_PER_REV  # Reset position to 6:00
    time.sleep(20)  # Sleep for 20 seconds (to hold position if necessary)
    enbpin.value(0)  # Enable the stepper driver
    return current_position

def web_page():
    html = """<!DOCTYPE html><html><head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Clock Control</title> <style> body { font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; background-color: #f4f4f4; } h1 { color: #333; margin-bottom: 20px; } form { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); margin-bottom: 15px; } label { display: block; margin-bottom: 8px; } input[type="number"] { width: 80px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; } input[type="submit"] { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; } input[type="submit"]:hover { background-color: #45a049; } #1a input[type="submit"] { background-color: #f44336; } #1a input[type="submit"]:hover { background-color: #d32f2f; } </style></head><body> <h1>Set Clock Time</h1> <form action="/time" method="get"> <label for="time">Enter hour (1-12):</label> <input type="number" id="time" name="time" min="1" max="12" required> <input type="submit" value="Set Time"> </form> <div id="1a"> <form action="/reset" method="get"> <input type="submit" value="Unlock Hand"> </form> </div></body></html>"""
  
    return html

def ap_mode(ssid, password):
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=ssid, password=password)
    ap.active(True)

    while ap.active() == False:
        pass
    print('AP Mode Is Active, You can Now Connect')
    print('IP Address To Connect to:: ' + ap.ifconfig()[0])

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80))
    s.listen(5)

    while True:
        conn, addr = s.accept()
        print('Got a connection from %s' % str(addr))
        request = conn.recv(1024)
        request2 = str(request)

        # Extract the time value from the request for setting time
        try:
            if '/time?time=' in request2:
                time_value = int(request2.split('/time?time=')[1].split(' ')[0]) 
                if 1 <= time_value <= 12:
                    print("Setting time to:", time_value)
                    set_time(time_value)  # Call set_time function to move the motor
                else:
                    print("Invalid time value")
            elif '/reset' in request2:  # Check if reset is requested
                print("Resetting time to 6:00")
                reset_time()  # Call reset_time function
                
        except (IndexError, ValueError):
            print("Invalid request format")

        response = web_page()
        conn.send('HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n')
        conn.send(response)
        conn.close()

# Start the motor control thread
_thread.start_new_thread(move_motor, ())

# Start AP mode
ap_mode('SSID', 'Pass')

