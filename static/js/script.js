// document.querySelectorAll(".door").forEach(door => {
//   door.addEventListener("click", () => {
//     door.classList.toggle("open");
//   });
// });


// socket
const socket = io.connect();

socket.on('connect', () => {
  console.log('WebSocket connected');
});

socket.on('disconnect', () => {
  console.log('WebSocket disconnected');
});

// setup
socket.on('initialize', function (data) {
  console.log('Initializing UI with door status:', data);

  const powerStatus = data.power_status;
  const lockStatus = data.lock_status;
  const doorStatus = data.door_status;

  const powerButton = document.getElementById('power-button');
  const lockButton = document.getElementById('lock-button');
  const unlockButton = document.getElementById('unlock-button');

  if (powerStatus === 0) {
    powerButton.classList.remove('active');
  } else {
    powerButton.classList.add('active');
  }

  // lock 
  if (lockStatus == 0) {
    lockButton.classList.add('active');
    unlockButton.classList.remove('active');

  } else {

    lockButton.classList.remove('active');
    unlockButton.classList.add('active');

    for (const doorId in doorStatus) {
      
      const doorOpenStatus = doorStatus[doorId];
      const doorElement = document.getElementById(`door-${doorId}`);
     
      if (doorElement) {
        if (doorOpenStatus === 1) {
          doorElement.classList.add("open");
        } else if (doorOpenStatus === 0) {
          doorElement.classList.remove("open");
        }
      } else {
        console.warn(`Door element with ID door-${doorId} not found.`);
      }
    }
  }

  if (data.optimalTemperature !== undefined) {
    document.getElementById('optimalTemperature').textContent = `${data.optimalTemperature}°C`;
  }

  if (data.seatAngle !== undefined) {
    document.getElementById('seatAngle').textContent = `${data.seatAngle}°`;
  }

  if (data.seatTemperature !== undefined) {
    document.getElementById('seatTemperature').textContent = `${data.seatTemperature}°C`;
  }
  
  if (data.seatPosition !== undefined) {
    document.getElementById('seatPosition').textContent = `${data.seatPosition}`;
  }

});

// update door status
socket.on("handleDoorStatus", function (data) {
  console.log("Door status update:", data);

  const doorId = data.door_id;
  const lockStatus = data.door_lock_status;
  const doorOpenStatus = data.door_open_status; // object

  const lockButton = document.getElementById('lock-button');
  const unlockButton = document.getElementById('unlock-button');

  if (doorId != 3) {
    const doorElement = document.getElementById(`door-${doorId}`);
    const doorOpen = doorOpenStatus[doorId];

    if (doorElement) {
      if (doorOpen === 1) {
        doorElement.classList.add("open");
      } else if (doorOpen === 0) {
        doorElement.classList.remove("open");
      }
    } else {
      console.warn(`Door element with ID ${doorId} not found.`);
    }

  }

  if (lockStatus === 0) {
    lockButton.classList.add('active');
    unlockButton.classList.remove('active');
  } else {
    lockButton.classList.remove('active');
    unlockButton.classList.add('active');
  }
  
});

// 설정값의 MIN 및 MAX 정의
const limits = {
  optimalTemperature: { min: 16, max: 30 },
  seatAngle: { min: 0, max: 180 },
  seatTemperature: { min: 20, max: 40 },
  seatPosition: { min: 0, max: 100 }
};

// 서버에서 설정값을 수신
socket.on('updateSettings', function (data) {
  console.log("Received settings from server:", data);

  // 슬라이더 값 및 화면 업데이트
  if (data.optimalTemperature !== undefined) {
    const value = Math.min(
      limits.optimalTemperature.max,
      Math.max(limits.optimalTemperature.min, data.optimalTemperature)
    );
    document.getElementById('optimalTemperature').textContent = `${value}°C`;
  }

  if (data.seatAngle !== undefined) {
    const value = Math.min(
      limits.seatAngle.max,
      Math.max(limits.seatAngle.min, data.seatAngle)
    );
    document.getElementById('seatAngle').textContent = `${value}°`;
  }

  if (data.seatTemperature !== undefined) {
    const value = Math.min(
      limits.seatTemperature.max,
      Math.max(limits.seatTemperature.min, data.seatTemperature)
    );
    document.getElementById('seatTemperature').textContent = `${value}°C`;
  }

  if (data.seatPosition !== undefined) {
    const value = Math.min(
      limits.seatPosition.max,
      Math.max(limits.seatPosition.min, data.seatPosition)
    );
    document.getElementById('seatPosition').textContent = `${value}`;
  }
});

// 버튼 클릭 시 값 변경
function changeValue(key, delta) {
  const display = document.getElementById(key);
  const currentValue = parseFloat(display.textContent);
  const { min, max } = limits[key];

  // 값 업데이트 (범위 내로 제한)
  const newValue = Math.min(max, Math.max(min, currentValue + delta));
  display.textContent = key === 'seatAngle' ? `${newValue}°` : `${newValue}°C`;

  // 서버로 변경된 값 전송
  socket.emit('changeSetting', { [key]: newValue });
}


// power
socket.on('powerStatusUpdate', function (data) {
  console.log('Power status updated:', data);

  const powerElement = document.getElementById('power-button');

  if (data.status === 1) {
    powerElement.classList.add('active');

  } else if (data.status === 0) {
    powerElement.classList.remove('active');
  }
});

function getDoorIdFromElement(elementId) {
  return elementId.split('-')[1];
}

socket.on('updateSettings', function (data) {
  console.log(data)
});

// door click
document.querySelectorAll('.door').forEach(door => {
  door.addEventListener('click', () => {
    const doorId = getDoorIdFromElement(door.id);
    console.log(`Button clicked. Door ID: ${doorId}`);
    socket.emit('doorCommand', { door_id: doorId });
  });
});

// Lock click
document.getElementById('lock-button').addEventListener('click', () => {
  console.log('lock button clicked');
  socket.emit('lockCommand');
});

// Unlock click
document.getElementById('unlock-button').addEventListener('click', () => {
  console.log('Unlock button clicked');
  socket.emit('unlockCommand');
});

// Power click

document.getElementById('power-button').addEventListener('click', () => {
  console.log('power button clicked');
  socket.emit('powerCommand');
});

