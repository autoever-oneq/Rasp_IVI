from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import serial
from threading import Lock
import time
import traceback
from raspmp3 import DFInit, DFPlayTrack

app = Flask(__name__)

# sockIO
socketio = SocketIO(app, cors_allowed_origins='*')
thread = None
thread_lock = Lock()

# val
# doors_status = {
#     "1": [1,0],  # 1번문 잠금 닫혀있음 
#     "2": [1,0],  # 2번문 잠금 닫혀있음 
# }

doors_status = {
    1: [1,0],  # 1번문 잠금 닫혀있음 
    2: [1,0],  # 2번문 잠금 닫혀있음 
}

power_status = 0

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

def door_sound(previous_lock_status, previous_open_status, door_lock_status, door_open_status):

    if previous_lock_status == 1 and previous_open_status == 0 and door_lock_status == 0 and door_open_status == 0:
        # (1, 0) → (0, 0): 잠금 해제
        DFPlayTrack(1)
    elif previous_lock_status == 1 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 1:
        # (1, 0) → (1, 1): 문 열림
        DFPlayTrack(3)
    elif previous_lock_status == 0 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 0:
        # (0, 0) → (1, 0): 잠금
        DFPlayTrack(1)
    elif previous_lock_status == 1 and previous_open_status == 1 and door_lock_status == 1 and door_open_status == 0:
        # (1, 1) → (1, 0): 문 닫힘
        DFPlayTrack(4)
    elif previous_lock_status == 0 and previous_open_status == 0 and door_lock_status == 1 and door_open_status == 1:
        # (0, 0) → (1, 1): 잠금 후 열림
        DFPlayTrack(1)
        time.sleep(1)
        DFPlayTrack(3)
    elif previous_lock_status == 1 and previous_open_status == 1 and door_lock_status == 0 and door_open_status == 0:
        # (1, 1) → (0, 0): 닫힘 후 잠금 해제
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
    
    if(door_id == 0x03):
        
        can_lock_flag = True
        
        ## 1. 모든 문 상태 확인 
        for each_id in [1, 2]:
            
            # 문 열려있을때, 잠금 신호
            if door_lock_status == 0 and door_open_status == 0 and doors_status[each_id][1] == 1:
                can_lock_flag = False
                return
        
        if not can_lock_flag:
            return
        
        ## 2. 상태 업데이트 
        for each_id in [1, 2]:    
            doors_status[each_id] = [door_lock_status, door_open_status]
            print(f"each_id: {each_id}, value: {doors_status[each_id]}")
            
        # 잠금      (0, 0) -> (1, 0)  {0x20 0x03 0x10}
        # 잠금 해제 (1, 0) -> (0, 0)  {0x20 0x03 0x00}
        DFPlayTrack(1)
        
        # 잠금해제 + 문  (0, 0) -> (1, 1) {0x20 0x03 0x11}
        # 잠금해제 + 문  (1, 1) -> (0, 0) {0x20 0x03 0x00}
        
          
    else : # 문 열기 
        if door_id not in doors_status:
            raise ValueError(f"Invalid door_id: {door_id} (Not found in doors_status)")
        
    
    # 현재 상태와 같을 경우
        if doors_status[door_id][0] == door_lock_status and doors_status[door_id][1] == door_open_status:
            return

        previous_lock_status, previous_open_status = doors_status[door_id]

        doors_status[door_id][0] = door_lock_status
        doors_status[door_id][1] = door_open_status

        door_sound(previous_lock_status, previous_open_status, door_lock_status, door_open_status)
        
        print(f"doors_status >> Lock Status: {doors_status[door_id][0]}, Door Status: {doors_status[door_id][1]}")
        print(f"Door ID: {door_id}, Lock Status: {door_lock_status}, Door Status: {door_open_status}")

    socketio.emit('handleDoorStatus', {
        'door_id': door_id,
        'door_lock_status': door_lock_status,
        'door_open_status': door_open_status
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
        return

    power_status = power_command
    if power_status == 0: # power off
        print("off signal")
    else :                # power on
        DFPlayTrack(2)

    socketio.emit('powerStatusUpdate', {'status': power_status})

# uart 수신
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

                    if high_4bit == 0xA:        # 디지털키
                        handle_digital_key(chunk)
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

# {192.168.137.82}:5000/open_door?door_id=1 (1:운전석)
@app.route('/open_door', methods=['POST'])
def open_door_rest():
    
    print("restapi - open door")
    
    try:
        # query ?door_id=1
        door_id = request.args.get('door_id')
        
        if not door_id:
            return jsonify({"status": "error", "message": "Missing door_id"}), 400
        
        command = COMMANDS["open_door"](int(door_id))
        
        ser.write(bytearray(command))  
        print(f"Sent command via UART: {bytearray(command)}")
        
        return jsonify({"status": "success", "message": "Door open Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# {192.168.137.82}:5000/close_door?door_id=1
@app.route('/close_door', methods=['POST'])
def close_door_rest():
    
    print("restapi - close door ")
    
    try:
        door_id = request.args.get('door_id')
        
        if not door_id:
            return jsonify({"status": "error", "message": "Missing door_id"}), 400
        
        command = COMMANDS["close_door"](int(door_id))
        
        ser.write(bytearray(command))  
        print(f"Sent command via UART: {bytearray(command)}")
        
        return jsonify({"status": "success", "message": "Door close Command"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    

# Command
@socketio.on('doorCommand')
def door_command_socketio(data):
    door_id = data.get('door_id')  
    door_id = int(door_id)

    if door_id in doors_status:
        door_lock = doors_status[door_id][0]
        door_status = doors_status[door_id][1]

        if door_lock == 0:  # 문이 잠긴 경우
            socketio.emit('doorCommandError', {'status': 'error', 'message': f'Door {door_id} is locked'})
            return

        if door_status == 0:  # 닫힌 상태 -> 열기 명령
            command = COMMANDS["open_door"](door_id)
        else:                 # 열린 상태 -> 닫기 명령
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
    
    command = COMMANDS["lock"]

    try:
        ser.write(bytearray(command))  

        print(f"Sent command via UART: {bytearray(command)}")
        socketio.emit('lockCommandSuccess', {'status': 'success', 'command': command})
    except Exception as e:
        socketio.emit('lockCommandError', {'status': 'error', 'message': str(e)})

@socketio.on('unlockCommand')
def unlock_command_socketio(data=None):
    
    command = COMMANDS["unlock"]

    try:
        ser.write(bytearray(command))  

        print(f"Sent command via UART: {bytearray(command)}")
        socketio.emit('unlockCommandSuccess', {'status': 'success','command': command})
    except Exception as e:
        socketio.emit('unlockCommandError', {'status': 'error', 'message': str(e)})
    
    

@socketio.on('powerCommand')
def power_command_socketio(data):
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
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(uart_receive)

    DFInit()

    socketio.emit('initialize', doors_status)

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected',  request.sid)

@app.route('/')  
def door():
    return render_template('door.html')

if __name__ == '__main__':        
    socketio.run(app=app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)

