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

socket.on('updateSettings', function (data) {
  console.log("Received settings from server:", data);

  // 값을 슬라이더 범위 내로 제한하는 함수
  function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
  }

  // 데이터를 트랙바와 화면에 반영
  if (data.optimalTemperature !== undefined) {
      const min = parseInt(document.getElementById('optimalTemperatureSlider').min);
      const max = parseInt(document.getElementById('optimalTemperatureSlider').max);
      const value = clamp(data.optimalTemperature, min, max);

      document.getElementById('optimalTemperatureSlider').value = value;
      document.getElementById('optimalTemperature').textContent = `${value}°C`;
  }

  if (data.seatAngle !== undefined) {
      const min = parseInt(document.getElementById('seatAngleSlider').min);
      const max = parseInt(document.getElementById('seatAngleSlider').max);
      const value = clamp(data.seatAngle, min, max);

      document.getElementById('seatAngleSlider').value = value;
      document.getElementById('seatAngle').textContent = `${value}°`;
  }

  if (data.seatTemperature !== undefined) {
      const min = parseFloat(document.getElementById('seatTemperatureSlider').min);
      const max = parseFloat(document.getElementById('seatTemperatureSlider').max);
      const value = clamp(data.seatTemperature, min, max);

      document.getElementById('seatTemperatureSlider').value = value;
      document.getElementById('seatTemperature').textContent = `${value}°C`;
  }

  if (data.seatPosition !== undefined) {
      const min = parseInt(document.getElementById('seatPositionSlider').min);
      const max = parseInt(document.getElementById('seatPositionSlider').max);
      const value = clamp(data.seatPosition, min, max);

      document.getElementById('seatPositionSlider').value = value;
      document.getElementById('seatPosition').textContent = value;
  }
});


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

