import serial

class SerialReader:
    def __init__(self, port, baudrate, queue):
        self.port = port
        self.baudrate = baudrate
        self.queue = queue

    def read_serial(self):
        """Читает данные с COM-порта."""
        ser = serial.Serial(self.port, self.baudrate, timeout=1)
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(line)  # Вывод в консоль
                self.queue.put(line)
