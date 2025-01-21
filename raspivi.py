from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import serial
from threading import Lock
import time
import traceback

app = Flask(__name__)

# sockIO
socketio = SocketIO(app, cors_allowed_origins='*')
thread = None
thread_lock = Lock()

# val
doors_status = {
    "1": [1,0],  # 1번문 잠금 닫혀있음 
    "2": [0,0],  # 2번문 잠금 닫혀있음 
}

power_status = 0

# UART 포트 및 설정
ser = serial.Serial(
    port='/dev/ttyAMA3',       # 실제 사용 중인 UART 포트
    baudrate=115200,           
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

def handle_door_status(chunk):
    #  0x20, 0x00, 0x01

    if len(chunk) != 3: # error 
        raise ValueError(f"Invalid chunk length for door status: {len(chunk)}")

    door_id = str(chunk[1])
    door_lock_status = (chunk[2] >> 4) & 0x0F
    door_open_status = chunk[2] & 0x0F

    if door_id not in doors_status:
        raise ValueError(f"Invalid door_id: {door_id} (Not found in doors_status)")
    if door_lock_status not in [0, 1]:
        raise ValueError(f"Invalid door_lock_status: {door_lock_status} (Expected 0 or 1)")
    if door_open_status not in [0, 1]:
        raise ValueError(f"Invalid door_open_status: {door_open_status} (Expected 0 or 1)")
    if door_lock_status == 0 and door_open_status == 1:
        raise ValueError(f"Invalid status [{door_lock_status}:{door_open_status}] ")

    # 현재 상태와 같을 경우
    if doors_status[door_id][0] == door_lock_status and doors_status[door_id][1] == door_open_status:
        return

    # 문 열려있을때, 잠금 시도하는 경우 고려?   

    doors_status[door_id][0] = door_lock_status
    doors_status[door_id][1] = door_open_status

    socketio.emit('handleDoorStatus', {
        'door_id': door_id,
        'door_lock_status': door_lock_status,
        'door_open_status': door_open_status
    })
    
    print(f"doors_status >> Lock Status: {doors_status[door_id][0]}, Door Status: {doors_status[door_id][1]}")
    print(f"Door ID: {door_id}, Lock Status: {door_lock_status}, Door Status: {door_open_status}")


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
        print("on signal")

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

# Command
@socketio.on('doorCommand')
def handle_door_command(data):
    door_id = data.get('door_id')  
    door_id = str(door_id)

    if door_id in doors_status:
        door_lock = doors_status[door_id][0]
        door_status = doors_status[door_id][1]

        if door_lock == 0:  # 문이 잠긴 경우
            socketio.emit('doorCommandError', {'status': 'error', 'message': f'Door {door_id} is locked'})
            return

        if door_status == 0:  # 닫힌 상태 -> 열기 명령
            command = [0x12, int(door_id)]
        else:                 # 열린 상태 -> 닫기 명령
            command = [0x13, int(door_id)]

        try:
            ser.write(bytearray(command))  

            print(f"Sent command via UART: {bytearray(command)}")
            socketio.emit('doorCommandSuccess', {'status': 'success', 'door_id': door_id, 'command': command})
        except Exception as e:
            socketio.emit('doorCommandError', {'status': 'error', 'message': str(e)})
    else:
        socketio.emit('doorCommandError', {'status': 'error', 'message': f'Invalid door_id: {door_id}'})

@socketio.on('lockCommand')
def handle_lock_command(data):
    door_id = data.get('door_id')
    door_id = str(door_id)

    if door_id in doors_status:
        door_lock = doors_status[door_id][0]

        if door_lock == 0: # lock 
            command = [0x11, int(door_id)]
        else:               # unlock 
            command = [0x10, int(door_id)]

        try:
            ser.write(bytearray(command))  

            print(f"Sent command via UART: {bytearray(command)}")
            socketio.emit('lockCommandSuccess', {'status': 'success', 'door_id': door_id, 'command': command})
        except Exception as e:
            socketio.emit('lockCommandError', {'status': 'error', 'message': str(e)})
    else:
        socketio.emit('lockCommandError', {'status': 'error', 'message': f'Invalid door_id: {door_id}'})

@socketio.on('powerCommand')
def handle_power_command(data):
    global power_status  # 전역 변수 선언

    if power_status == 0: 
        command = [0xB1]  
    else:
        command = [0xB0]  

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

    socketio.emit('initialize', doors_status)

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected',  request.sid)

@app.route('/')  
def door():
    return render_template('door.html')

if __name__ == '__main__':        
    socketio.run(app=app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
