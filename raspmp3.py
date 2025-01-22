import serial
import time

# DFPlayer UART 초기화
DF_UART = serial.Serial("/dev/ttyAMA4", baudrate=9600, timeout=1)  # UART4 예제
# UART4가 아닌 다른 UART를 사용할 경우 경로를 수정하세요.

# DFPlayer 명령어 구성 요소
StartByte = 0x7E
Version = 0xFF
CmdLength = 0x06
Feedback = 0x00  # No Feedback
EndByte = 0xEF

# 명령어 전송 함수
def DFSendCmd(cmd, param1=0, param2=0):
    """DFPlayer Mini에 명령어 전송"""
    checksum = Version + CmdLength + cmd + Feedback + param1 + param2
    checksum = 0xFFFF - checksum + 1  # Checksum 계산
    cmd_sequence = [
        StartByte,
        Version,
        CmdLength,
        cmd,
        Feedback,
        param1,
        param2,
        (checksum >> 8) & 0xFF,
        checksum & 0xFF,
        EndByte,
    ]
    DF_UART.write(bytearray(cmd_sequence))  # 명령 전송

# DFPlayer 초기화 함수
def DFInit():
    """DFPlayer 초기화 및 볼륨 설정"""
    DFReset()
    time.sleep(0.2)
    DFSendInitialConfig()  # SD 카드 선택
    time.sleep(1)
    DFSetVolume(10)   # 볼륨 설정 (0~30)
    time.sleep(0.2)

def DFPlay():
   DFSendCmd(0x0D, 0, 0)

def DFStop():
   DFSendCmd(0x0E, 0, 0)

def DFReset():
    DFSendCmd(0x0C, 0x00, 0x00)

def DFSendInitialConfig():
    DFSendCmd(0x3F, 0x00, 0x02)

def DFSetVolume(volume):
    DFSendCmd(0x06, 0x00, volume) 

# 특정 트랙 재생 함수
def DFPlayTrack(track_number):
    """지정된 트랙 번호의 음악 재생"""
 #   time.sleep(0.2)
    DFSendCmd(0x03, 0x00, track_number)
    time.sleep(0.2)
    DFPlay()
# 메인 코드 실행
if __name__ == "__main__":
    
    DFInit()   # 초기화 및 볼륨 설정
 #   time.sleep(0.2)
    DFPlayTrack(4)

