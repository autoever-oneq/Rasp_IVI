from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import serial
from threading import Lock
import time
import traceback
from raspmp3 import DFInit, DFPlayTrack
import requests
from raspfan import update_relay_active, execute_fan
import json

app = Flask(__name__)

# sockIO
socketio = SocketIO(app, cors_allowed_origins='*')

# lock
thread_uart = None
thread_request = None
background_lock = Lock()
settings_lock = Lock()

# digital_key
DIGITAL_KEY_UUID ="ABCDEF00"
latest_settings ={
    "autoDoorClose": False,
    "autoDoorOpen": False,
    "optimalTemperature": 0,
    "seatAngle": 0,
    "seatPosition": 0,
    "seatTemperature": 0,
    "uuid": "ABCDEF00"}

# car 
power_status  = 0
doors_status = {
    "auto_door_open" : 0,
    "auto_door_close" : 0,
    "lock_status": 0,  
    "door_status": {   
        1: 0, 
        2: 0
    }
}

COMMANDS = {
    "lock": [0x10, 0x03, 0xFF],          
    "unlock": [0x11, 0x03, 0xFF],        
    "open_door": lambda door_id: [0x12, door_id, 0xFF],  
    "close_door": lambda door_id: [0x13, door_id, 0xFF], 
    "power_on": [0xB1, 0xFF],       
    "power_off": [0xB0, 0xFF],    
}

# UART setting
ser = serial.Serial(
    port='/dev/ttyAMA3',      
    baudrate=115200,           
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

def door_sound(previous_lock_status, previous_open_status, door_lock_status, door_open_status):

    if previous_lock_status == 1 and previous_open_status == 0 and door_lock_status == 0 and door_open_status == 0:
        # (1, 0) → (0, 0): unlock
        DFPlayTrack(1)
    elif previous_lock_status == 1 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 1:
        # (1, 0) → (1, 1): open
        DFPlayTrack(3)
    elif previous_lock_status == 0 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 0:
        # (0, 0) → (1, 0): lock
        DFPlayTrack(1)
    elif previous_lock_status == 1 and previous_open_status == 1 and door_lock_status == 1 and door_open_status == 0:
        # (1, 1) → (1, 0): close
        DFPlayTrack(4)
    elif previous_lock_status == 0 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 1:
        # (0, 0) → (1, 1): lock -> open
        DFPlayTrack(1)
        time.sleep(1)
        DFPlayTrack(3)
    elif previous_lock_status == 1 and previous_open_status == 1 and door_lock_status == 0 and door_open_status == 0:
        # (1, 1) → (0, 0): close -> lock
        DFPlayTrack(4)
        time.sleep(1)
        DFPlayTrack(1)

def handle_door_status(chunk):
    #  0x20, 0x00, 0x01

    if len(chunk) != 3: # error 
        raise ValueError(f"Invalid chunk length for door status: {len(chunk)}")

    door_id = chunk[1]
    door_lock_status = (chunk[2] >> 4) & 0x0F
    door_open_status = chunk[2] & 0x0F
    
    if door_lock_status not in [0, 1]:
            raise ValueError(f"Invalid door_lock_status: {door_lock_status} (Expected 0 or 1)")
    if door_open_status not in [0, 1]:
        raise ValueError(f"Invalid door_open_status: {door_open_status} (Expected 0 or 1)")
    if door_lock_status == 0 and door_open_status == 1:
            raise ValueError(f"Invalid status [{door_lock_status}:{door_open_status}]")
    
    if doors_status["lock_status"] == door_lock_status and doors_status["door_status"][door_id] == door_open_status:
        print("same")
        return
    
    if(door_id == 0x03): 
        # 10
        # 00 
        
        # unlock { lock : 1, door{ 1:0, 2:0}} -> { lock : 0, door{ 1:0, 2:0}}
        if(door_lock_status == 1 and door_open_status == 0): # unlock
            doors_status["lock_status"] = 1
            
        # lock { lock : 0, door{ 1:0, 2:0}} -> { lock : 1, door{ 1:0, 2:0}}
        elif (door_lock_status == 0 and door_lock_status == 0): 
            doors_status["lock_status"] = 0
          
        DFPlayTrack(1)
        
    else : # 0x01, 0x02
        
        if door_id not in doors_status["door_status"]:
            raise ValueError(f"Invalid door_id: {door_id} (Not found in doors_status)")

        previous_lock_status = doors_status["lock_status"]
        previous_open_status = doors_status["door_status"][door_id]

        doors_status["lock_status"] = door_lock_status
        doors_status["door_status"][door_id] = door_open_status

        door_sound(previous_lock_status, previous_open_status, door_lock_status, door_open_status)
        
        print(f"[Door ID: {door_id} - {previous_lock_status, previous_open_status}] >> [{doors_status['lock_status']}, {doors_status['door_status'][door_id]}]")
        print(f"Lock Status: {doors_status['lock_status']}, Door Status: {doors_status['door_status']}")


    socketio.emit('handleDoorStatus', {
        'door_id': door_id,
        'door_lock_status': doors_status["lock_status"],
        'door_open_status': doors_status["door_status"]
    })
    
    
def handle_digital_key(chunk):
     # 0xA0, 0x12, 0x34, 0x56, 0x78
    
    if len(chunk) != 5:
        raise ValueError(f"Invalid chunk length for digital_key: {len(chunk)}")

def handle_vehicle_control(chunk): # 0xB0
    
    print("handle vehicle_control")
    global power_status

    if len(chunk) != 1:
        raise ValueError(f"Invalid chunk length for vehicle_control: {len(chunk)}")
    
    power_command = (chunk[0]) & 0x0F # 0, 1
    print("power_command:",power_command)

    if power_command not in [0, 1]:
        raise ValueError(f"Invalid power command: {power_command} (Expected 0 or 1)")

    if power_status == power_command:
        print("power_status == power_command")
        return

    power_status = power_command
    if power_status == 0: # power off
        print("power off")
    else :                # power on
        print("power on")
        DFPlayTrack(2)

    socketio.emit('powerStatusUpdate', {'status': power_status})

def parse_protocol_message(message):
    if len(message) % 2 != 0:
        raise ValueError("len(message) % 2 != 0 ")
    try:
        # parse hex
        chunk = [int(message[i:i+2], 16) for i in range(0, len(message), 2)]
        return chunk
    except ValueError as e:
        raise ValueError(f"pare error : {e}")
    
#######################################################################
# backup
APP_SERVER_BASE_URL = "http://192.168.0.90:3000"
APP_SERVER_UUID = "ABCDEF00"

def request_setting():
    global latest_settings
    while True:
        try:
            url = f"{APP_SERVER_BASE_URL}/setting/{APP_SERVER_UUID}"
            response = requests.get(url)
        
            if response.status_code == 200:
                response_settings = response.json()
                
                with settings_lock:
                    if latest_settings != response_settings:
                        
                        latest_settings.update(response_settings)   
                        print("\nsetting change, emit\nlatest_settings:", json.dumps(latest_settings, indent=4))
                        execute_fan(latest_settings["optimalTemperature"]) # fan
                        
                        # autoDoor 
                        doors_status["auto_door_open"] = latest_settings["autoDoorOpen"]
                        doors_status["auto_door_close"] = latest_settings["autoDoorClose"]
                        
                        socketio.emit('updateSettings', latest_settings)
                    
                    else:
                        print("Settings did not change, no emit.")

            else:
                print(f"Failed to fetch settings from app-server: {response.status_code}")

        except Exception as e:
            print(f"Error occurred in request_setting: {e}")
            
        time.sleep(5)
        
# post 
@socketio.on("changeSetting")
def change_setting(data):
    global latest_settings
    print("Received updated setting from client:", data)
    
    with settings_lock:
        key, value = next(iter(data.items()))
        if key in latest_settings and latest_settings[key] == value:
            print(f"No change detected for {key}: {value}. Skipping POST request.")
            return
        
        latest_settings.update(data)  
        url = f"{APP_SERVER_BASE_URL}/setting/{APP_SERVER_UUID}"
        
        try:
            
            response = requests.patch(url, json=latest_settings, headers={"Content-Type": "application/json"})
            
            if response.status_code == 200:
                print("Successfully sent settings to APP_SERVER:", response.json())
            else:
                print(f"Failed to send settings. Status code: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"Error sending settings to APP_SERVER: {e}")
    

        
@app.route('/settings', methods=['POST'])
def setting_data():
    if request.is_json:
        received_data = request.get_json()
        if DIGITAL_KEY_UUID == received_data["uuid"]:
            print("received_data:", json.dumps(received_data, indent=4))
            return jsonify({"status": "success", "data": received_data}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    else:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    
##### 
        
# def test_uart_receive():
#     while True:
#         try:
#             test_message = input("메시지를 입력하세요 (16진수 형식, 예: 200111): ").strip()
#             if not test_message:
#                 continue

#             # TEST
#             chunk = parse_protocol_message(test_message)

#             if chunk:
#                 first_byte = chunk[0]
#                 high_4bit = (first_byte >> 4) & 0x0F

#                 if high_4bit == 0xA:          # digitalkey
#                     print("0xA")
#                     # handle_digital_key(chunk)
#                 elif high_4bit == 0x2:        # door
#                     handle_door_status(chunk)
#                 elif high_4bit == 0xB:        # power 
#                     handle_vehicle_control(chunk)
#                 else:
#                     raise ValueError(f"Unknown high_4bit value: 0x{high_4bit:X} in chunk: ")

#         except serial.SerialException as e:
#             print(f"SerialException occurred: {e}")
#             print(traceback.format_exc())
#         except ValueError as e:
#             print(f"ValueError occurred: {e}")
#             print(traceback.format_exc())
#         except Exception as e:
#             print(f"An unexpected error occurred: {e}")
#             print(traceback.format_exc())
            
def uart_receive():
    while True:
        try:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
            
                hex_data = [f"0x{byte:02X}" for byte in chunk]
                print(f"[수신] {hex_data}")

                if chunk:
                    first_byte = chunk[0]
                    high_4bit = (first_byte >> 4) & 0x0F

                    if high_4bit == 0xA:          # digitalkey
                        handle_digital_key(chunk)
                    elif high_4bit == 0x2:        # door
                        handle_door_status(chunk)
                    elif high_4bit == 0xB:        # power
                        handle_vehicle_control(chunk)
                    else:
                        raise ValueError(f"Unknown high_4bit value: 0x{high_4bit:X} in chunk: {hex_data}")

        except serial.SerialException as e:
            print(f"SerialException occurred: {e}")
            print(traceback.format_exc())
        except ValueError as e:
            print(f"ValueError occurred: {e}")
            print(traceback.format_exc())
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print(traceback.format_exc())

########################################################################
# {192.168.137.82}:5000/power_off
@app.route('/power_off', methods=['POST'])
def power_off_command_rest():
    """REST API - Power Off"""
    global power_status
    
    print("REST API - power_off")
    
    try:
        if power_status == 1:
            command = COMMANDS["power_off"]
            handle_vehicle_control(bytearray([command[0]]))  # 첫 번째 바이트만 전달
            return jsonify({"status": "success", "message": "Power Off Command Executed"}), 200
        else:
            return jsonify({"status": "fail", "message": "Power is already off"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/power_on', methods=['POST'])
def power_on_command_rest():
    """REST API - Power On"""
    global power_status
    
    print("REST API - power_on")

    try:
        if power_status == 0:
            command = COMMANDS["power_on"]
            handle_vehicle_control(bytearray([command[0]]))  # 첫 번째 바이트만 전달
            socketio.emit('powerCommandSuccess', {'status': power_status, 'command': command})
            return jsonify({"status": "success", "power_status": power_status, "message": "Power On Command Executed"}), 200
        else:
            return jsonify({"status": "fail", "power_status": power_status, "message": "Power is already on"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# @app.route('/power_on_nfc', methods=['POST'])
# def power_on_nfc_rest():
    
#     print("rest - power_on_nfc")
    
#     try:
#         command = COMMANDS["power_on"]
#         ser.write(bytearray(command))
        
#         print(f"Sent command via UART: {bytearray(command)}")
#         return jsonify({"status": "success", "message": "Door Lock Command"}), 200
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# {192.168.137.82}:5000/lock
@app.route('/lock', methods=['POST'])
def lock_command_rest():
    
    print("restapi - lock ")
    
    try:
        lock_command_socketio()
        return jsonify({"status": "success", "message": "Door Lock Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
        
# {192.168.137.82}:5000/unlock
@app.route('/unlock', methods=['POST'])
def unlock_command_rest():
    
    try:    
        unlock_command_socketio()
        return jsonify({"status": "success", "message": "Door unlocked"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# {192.168.137.82}:5000/open_door
@app.route('/open_door', methods=['POST'])
def open_door_rest():    
    print("restapi - open door")
    
    if doors_status["lock_status"] == 0:
        print("door lock")
        return jsonify({"status": "fail", "message": "door is already lock"}), 400
    
    if(doors_status["door_status"][1] == 1):
        print("alreay open")
        return jsonify({"status": "fail", "message": "Door is already open"}), 400
    
    try:

        command = COMMANDS["open_door"](1)
        ser.write(bytearray(command))  
        print(f"Sent command via UART: {bytearray(command)}")
        
        return jsonify({"status": "success", "message": "Door open Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# {192.168.137.82}:5000/close_door
@app.route('/close_door', methods=['POST'])
def close_door_rest():
    print("restapi - close door ")
    
    if doors_status["lock_status"] == 0:
        print("door lock")
        return jsonify({"status": "fail", "message": "door is already lock"}), 400
    
    if(doors_status["door_status"][1] == 0):
        print("alreay close")
        return jsonify({"status": "fail", "message": "Door is already closed"}), 400
    
    try:
        command = COMMANDS["close_door"](1)
        
        ser.write(bytearray(command))  
        print(f"Sent command via UART: {bytearray(command)}")
        
        return jsonify({"status": "success", "message": "Door close Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# Command
@socketio.on('doorCommand')
def door_command_socketio(data):
    door_id = int(data.get('door_id'))

    if doors_status["lock_status"] == 0:          # lock
        print("doors lock")
        socketio.emit('doorCommandError', {'status': 'error', 'message': f'Door is locked'})
        return

    if doors_status["door_status"][door_id] == 0: # lock
        command = COMMANDS["open_door"](door_id)
    else:                                         # unlock
        command = COMMANDS["close_door"](door_id)

    try:
        ser.write(bytearray(command))

        print(f"Sent command via UART: {bytearray(command)}")
        socketio.emit('doorCommandSuccess', {'status': 'success', 'door_id': door_id, 'command': command})
    except Exception as e:
        socketio.emit('doorCommandError', {'status': 'error', 'message': str(e)})
    else:
        socketio.emit('doorCommandError', {'status': 'error', 'message': f'Invalid door_id: {door_id}'})

@socketio.on('lockCommand')
def lock_command_socketio(data=None):
    
    # already lock
    if(doors_status["lock_status"] == 0 ):
        print("already lock status")
        return
    
    # open exist
    for door_id, open_status in doors_status["door_status"].items():
        if(open_status  == 1):
            print(f"door - {door_id} is open")
            return

    command = COMMANDS["lock"]
    
    try:
        ser.write(bytearray(command))  

        print(f"Sent command via UART: {bytearray(command)}")
        socketio.emit('lockCommandSuccess', {'status': 'success', 'command': command})
    except Exception as e:
        socketio.emit('lockCommandError', {'status': 'error', 'message': str(e)})

@socketio.on('unlockCommand')
def unlock_command_socketio(data=None):
    
    # already unlock
    if(doors_status["lock_status"] == 1 ):
        print("already unlock status")
        return
    
    command = COMMANDS["unlock"]

    try:
        ser.write(bytearray(command))  

        print(f"Sent command via UART: {bytearray(command)}")
        socketio.emit('unlockCommandSuccess', {'status': 'success','command': command})
    except Exception as e:
        socketio.emit('unlockCommandError', {'status': 'error', 'message': str(e)})

@socketio.on('powerCommand')
def power_command_socketio():
    global power_status  
    
    print("power")
    
    if power_status == 0: 
        command = COMMANDS["power_on"]
    else:
        command = COMMANDS["power_off"]

    try:
        
        handle_vehicle_control(bytearray([command[0]]))
        socketio.emit('powerCommandSuccess', {'status': power_status, 'command': command})
    except Exception as e:
        socketio.emit('powerCommandError', {'status': 'error', 'message': str(e)})

# connect 
@socketio.on('connect')
def connect():
    print('Client connected')
    global thread_uart, thread_request 
    with background_lock:
        if thread_uart is None:
            thread_uart = socketio.start_background_task(uart_receive)
            
        if thread_request is None :
            thread_request = socketio.start_background_task(request_setting)

    DFInit()

    initial_data = {
        "power_status": power_status
    }
    
    initial_data.update(latest_settings)
    initial_data.update(doors_status)
    
    print("initial_data:", json.dumps(initial_data, indent=4))
    
    socketio.emit('initialize', initial_data)

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected',  request.sid)

@app.route('/')  
def door():
    return render_template('door.html')

if __name__ == '__main__':        
    socketio.run(app=app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)

