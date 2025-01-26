from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import serial
from threading import Lock
import time
import traceback
from raspmp3 import DFInit, DFPlayTrack
import requests

app = Flask(__name__)

# sockIO
socketio = SocketIO(app, cors_allowed_origins='*')

thread_lock = Lock()
thread = None
thread_request = None

DIGITAL_KEY_UUID ="ABCDEF00"
power_status  = 1
doors_status = {
    "lock_status": 1,  
    "door_status": {   
        1: 1, 
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

# UART 포트 및 설정
ser = serial.Serial(
    port='/dev/ttyAMA3',      
    baudrate=115200,           
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

# def door_sound(previous_lock_status, previous_open_status, door_lock_status, door_open_status):

#     if previous_lock_status == 1 and previous_open_status == 0 and door_lock_status == 0 and door_open_status == 0:
#         # (1, 0) → (0, 0): 잠금 해제
#         DFPlayTrack(1)
#     elif previous_lock_status == 1 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 1:
#         # (1, 0) → (1, 1): 문 열림
#         DFPlayTrack(3)
#     elif previous_lock_status == 0 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 0:
#         # (0, 0) → (1, 0): 잠금
#         DFPlayTrack(1)
#     elif previous_lock_status == 1 and previous_open_status == 1 and door_lock_status == 1 and door_open_status == 0:
#         # (1, 1) → (1, 0): 문 닫힘
#         DFPlayTrack(4)
#     elif previous_lock_status == 0 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 1:
#         # (0, 0) → (1, 1): 잠금 후 열림
#         DFPlayTrack(1)
#         time.sleep(1)
#         DFPlayTrack(3)
#     elif previous_lock_status == 1 and previous_open_status == 1 and door_lock_status == 0 and door_open_status == 0:
#         # (1, 1) → (0, 0): 닫힘 후 잠금 해제
#         DFPlayTrack(4)
#         time.sleep(1)
#         DFPlayTrack(1)

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

        #door_sound(previous_lock_status, previous_open_status, door_lock_status, door_open_status)
        
        
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
    
    global power_status

    if len(chunk) != 1:
        raise ValueError(f"Invalid chunk length for vehicle_control: {len(chunk)}")
    
    power_command = (chunk[0]) & 0x0F # 0, 1

    if power_command not in [0, 1]:
        raise ValueError(f"Invalid power command: {power_command} (Expected 0 or 1)")

    if power_status == power_command:
        print("power_status == power_command")
        return

    power_status = power_command
    if power_status == 0: # power off
        print("off signal")
    else :                # power on
        DFPlayTrack(2)

    socketio.emit('powerStatusUpdate', {'status': power_status})

def parse_protocol_message(message):
    if len(message) % 2 != 0:
        raise ValueError("입력 메시지의 길이는 짝수여야 합니다.")
    try:
        # 2글자씩 잘라서 16진수로 변환
        chunk = [int(message[i:i+2], 16) for i in range(0, len(message), 2)]
        return chunk
    except ValueError as e:
        raise ValueError(f"메시지 변환 중 오류 발생: {e}")
    
#######################################################################
# backup
APP_SERVER_BASE_URL = "http://192.168.0.90:3000"
APP_SERVER_UUID = "ABCDEF00"
def request_setting():
    while True:
        try:

            url = f"{APP_SERVER_BASE_URL}/setting/{APP_SERVER_UUID}"
            response = requests.get(url)
        
            if response.status_code == 200:
                settings = response.json()
                socketio.emit('updateSettings', settings)

            else:
                print(f"Failed to fetch settings from app-server: {response.status_code}")

        except Exception as e:
            print(f"Error occurred in request_setting: {e}")
            
        time.sleep(5)
        
def test_uart_receive():
    while True:
        try:
            test_message = input("메시지를 입력하세요 (16진수 형식, 예: 200111): ").strip()
            if not test_message:
                continue

            # TEST
            chunk = parse_protocol_message(test_message)

            if chunk:
                first_byte = chunk[0]
                high_4bit = (first_byte >> 4) & 0x0F

                if high_4bit == 0xA:        # 디지털키
                    print("0xA")
                    # handle_digital_key(chunk)
                elif high_4bit == 0x2:      # 차문 상태 정보
                    handle_door_status(chunk)
                elif high_4bit == 0xB:      # 차량 제어
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
            
# def uart_receive():
#     while True:
#         try:
#             if ser.in_waiting > 0:
#                 chunk = ser.read(ser.in_waiting)
            
#                 hex_data = [f"0x{byte:02X}" for byte in chunk]
#                 print(f"[수신] {hex_data}")

#                 if chunk:
#                     first_byte = chunk[0]
#                     high_4bit = (first_byte >> 4) & 0x0F

#                     if high_4bit == 0xA:        # 디지털키
#                         handle_digital_key(chunk)
#                     elif high_4bit == 0x2:      # 차문 상태 정보
#                         handle_door_status(chunk)
#                     elif high_4bit == 0xB:      # 차량 제어
#                         handle_vehicle_control(chunk)
#                     else:
#                         raise ValueError(f"Unknown high_4bit value: 0x{high_4bit:X} in chunk: {hex_data}")

#         except serial.SerialException as e:
#             print(f"SerialException occurred: {e}")
#             print(traceback.format_exc())
#         except ValueError as e:
#             print(f"ValueError occurred: {e}")
#             print(traceback.format_exc())
#         except Exception as e:
#             print(f"An unexpected error occurred: {e}")
#             print(traceback.format_exc())

########################################################################
# {192.168.137.82}:5000/power_off
@app.route('/power_off', methods=['POST'])
def power_off_command_rest():
    
    print("restapi - power_off ")
    
    try:
        command = COMMANDS["power_off"]
        ser.write(bytearray(command))
        
        print(f"Sent command via UART: {bytearray(command)}")
        return jsonify({"status": "success", "message": "Door Lock Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# {192.168.137.82}:5000/power_on
@app.route('/power_on', methods=['POST'])
def power_on_command_rest():
    
    print("rest - power_on")
    
    try:
        command = COMMANDS["power_on"]
        ser.write(bytearray(command))
        
        print(f"Sent command via UART: {bytearray(command)}")
        return jsonify({"status": "success", "message": "Door Lock Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
        print("doors lock")
        return
    
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
    
    if(doors_status["door_status"][1] == 0):
        print("alreay close")
        return
    
    try:
        command = COMMANDS["close_door"](1)
        
        ser.write(bytearray(command))  
        print(f"Sent command via UART: {bytearray(command)}")
        
        return jsonify({"status": "success", "message": "Door close Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# return 용
@app.route('/settings', methods=['POST'])
def setting_data():
    if request.is_json:
        received_data = request.get_json()
        if DIGITAL_KEY_UUID == received_data["uuid"]:
            print("receive_data :",received_data)
            return jsonify({"status": "success", "data": received_data}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    else:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    
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
    global power_status  # 전역 변수 선언

    if power_status == 0: 
        command = COMMANDS["power_on"]
    else:
        command = COMMANDS["power_off"] 

    try:
        ser.write(bytearray(command))  

        print(f"Sent command via UART: {bytearray(command)}")
        socketio.emit('powerCommandSuccess', {'status': power_status, 'command': command})
    except Exception as e:
        socketio.emit('powerCommandError', {'status': 'error', 'message': str(e)})

# connect 
@socketio.on('connect')
def connect():
    print('Client connected')
    global thread, thread_request 
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(test_uart_receive)
            
        if thread_request is None :
            thread_request = socketio.start_background_task(request_setting)

    DFInit()

    initial_data = {
        "power_status": power_status,
        "lock_status": doors_status["lock_status"],
        "door_status": doors_status["door_status"]
    }
    
    socketio.emit('initialize', initial_data)

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected',  request.sid)

@app.route('/')  
def door():
    return render_template('door.html')

if __name__ == '__main__':        
    socketio.run(app=app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)

