import time
import serial

ser = serial.Serial(
                    port='/dev/ttyAMA3',         # 시리얼통신에 사용할 포트
                    baudrate=115200,                # 통신속도 지정
                    parity=serial.PARITY_NONE,       # 패리티 비트 설정방식
                    stopbits=serial.STOPBITS_ONE,     # 스톱비트 지정
                    bytesize=serial.EIGHTBITS,        # 데이터 비트수 지정
                    timeout=1                         #타임아웃 설정
                    )


while True:
    # degree = input('input ?\n')
    # if degree.isdigit():
    #     ser.write(degree.encode())
    
    #     print(f"Sent: {degree}")

    # else:
    #     print("you have to pass a number")

    if ser.in_waiting > 0:  # 수신 데이터가 있는지 확인
        data = ser.read(ser.in_waiting)  # 3바이트 읽기 (STM32에서 3바이트 전송하므로)
        print("Received data:", [hex(b) for b in data])
        if len(data) == 3:
            
            if data == b'\x20\x00\x01':
                print("Door Open Command Received")
            elif data == b'\x20\x00\x00':
                print("Door Close Command Received")
            else:
                print("Unknown data received")

        elif len(data) == 5:
            if data == b'\xA0\x12\x34\x56\x78':
                print("DigitalKeyID : UID 0x12345678")