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

  // lock 상태 
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

// 문 상태 변경 수신
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


// 파워 상태
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

