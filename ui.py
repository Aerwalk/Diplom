import os

import serial
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import threading
import re
import sys
import queue
import serial.tools.list_ports
from datetime import datetime, timedelta
import pyperclip
import xml.etree.ElementTree as ET

class LoRaTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LoRa Tracker")
        self.create_ui()
        self.data_queue = queue.Queue()
        self.buffer = {}  # Буфер для временного хранения данных
        self.last_update = {}  # Словарь для отслеживания времени последнего обновления
        self.root.after(100, self.process_serial_data)

    def create_ui(self):
        """Создает интерфейс пользователя."""
        frame_top = tk.Frame(self.root, bg="#FFA500")
        frame_top.pack(fill=tk.X)

        # Создаем Combobox для COM порта с возможностью автопоиска
        self.com_port = ttk.Combobox(frame_top, values=self.get_available_ports())
        self.com_port.current(0)
        self.com_port.pack(side=tk.LEFT, padx=5, pady=5)

        self.connect_button = tk.Button(frame_top, text="Подключиться", command=self.start_reading)
        self.connect_button.pack(side=tk.LEFT, padx=5)

        self.auto_select = tk.Button(frame_top, text="Автовыбор", command=self.auto_select_port)
        self.auto_select.pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(frame_top, text="⭘ Подключено", fg="gray", bg="#FFA500")
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.path_label = tk.Label(frame_top, text="Путь сохранения")
        self.path_label.pack(side=tk.LEFT, padx=5)

        self.path_entry = tk.Entry(frame_top, width=40)
        self.path_entry.insert(0, "C:\\")  # Путь по умолчанию
        self.path_entry.pack(side=tk.LEFT, padx=5)

        self.browse_button = tk.Button(frame_top, text="Обзор", command=self.browse_path)
        self.browse_button.pack(side=tk.LEFT, padx=5)

        self.copy_button = tk.Button(frame_top, text="Копировать", command=self.copy_path)
        self.copy_button.pack(side=tk.LEFT, padx=5)

        self.update_ozi_button = tk.Button(frame_top, text="Обновить Ozi")
        self.update_ozi_button.pack(side=tk.RIGHT, padx=5)

        self.tree = ttk.Treeview(self.root,
                                 columns=("ID", "Позывной", "Широта", "Долгота", "Время получения GPS", "В эфире"),
                                 show='headings')
        for col in ("ID", "Позывной", "Широта", "Долгота", "Время получения GPS", "В эфире"):
            self.tree.heading(col, text=col)
        self.tree.pack(expand=True, fill='both')

        # Настроим контекстное меню
        self.tree.bind("<Button-3>", self.on_right_click)  # ПКМ для контекстного меню
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Копировать координаты", command=self.copy_coordinates)

    def get_available_ports(self):
        """Получаем список доступных COM портов для автопоиска."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            return ports
        else:
            return ["COM1", "COM2", "COM3"]  # Если портов нет, используем эти

    def auto_select_port(self):
        """Автоматически выбирает первый доступный COM порт и подключается к нему."""
        available_ports = self.get_available_ports()
        if available_ports:
            port = available_ports[0]
            self.com_port.set(port)  # Устанавливаем первый доступный порт в комбобокс
            # Запускаем поток для чтения данных с выбранного порта
            threading.Thread(target=self.start_reading_from_auto_port, args=(port,), daemon=True).start()

    def parse_coordinates(self, data):
        """Обрабатывает данные построчно, накапливая в буфере."""
        if "Position reply" in data:
            match = re.search(r'Position reply: time=(\d+) lat=(\d+) lon=(\d+)', data)
            if match:
                self.buffer["time"], self.buffer["lat"], self.buffer["lon"] = match.groups()

        if "Uncompressed device_callsign" in data:
            callsign_match = re.search(r"Uncompressed device_callsign '(.+?)'", data)
            if callsign_match:
                self.buffer["callsign"] = callsign_match.group(1)

        if "Update DB node" in data:
            id_match = re.search(r"Update DB node (0x[0-9a-fA-F]+)", data)
            if id_match:
                self.buffer["id"] = id_match.group(1)

        # Если собраны все данные, обновляем UI
        if all(k in self.buffer for k in ["id", "callsign", "lat", "lon", "time"]):
            # Преобразуем время в читаемый формат
            readable_time = self.convert_time(self.buffer["time"])
            self.update_ui(self.buffer["id"], self.buffer["callsign"],
                           int(self.buffer["lat"]) / 1e7, int(self.buffer["lon"]) / 1e7,
                           readable_time)
            self.buffer.clear()  # Очищаем буфер после обработки

    def convert_time(self, timestamp):
        """Преобразует timestamp в читаемый формат."""
        timestamp = int(timestamp)
        return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    def read_serial(self, port, baudrate):
        """Читает данные с COM-порта и передает в очередь обработки."""
        ser = serial.Serial(port, baudrate, timeout=1)
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(line)  # Вывод в консоль
                self.data_queue.put(line)

    def process_serial_data(self):
        """Обрабатывает входящие данные и обновляет UI."""
        while not self.data_queue.empty():
            line = self.data_queue.get()
            self.parse_coordinates(line)
        self.root.after(100, self.process_serial_data)

    def update_ui(self, board_id, callsign, lat, lon, time):
        """Обновляет таблицу UI новыми координатами и сохраняет их в GPX-файл."""
        current_time = datetime.utcnow()
        self.last_update[board_id] = current_time

        # Формируем путь к GPX-файлу
        track_filename = f'{self.path_entry.get()}\\{board_id}_{callsign}.gpx' if callsign != "Unknown" else f'{self.path_entry.get()}\\{board_id}.gpx'

        # Проверяем, существует ли файл
        file_exists = os.path.exists(track_filename)

        # Открываем файл в режиме добавления
        with open(track_filename, 'a', encoding='utf-8') as f:
            if not file_exists:
                # Если файл не существует, записываем заголовок GPX
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<gpx version="1.1" creator="LoRaTrackerApp">\n')
                f.write('  <trk>\n    <name>LoRa Tracker</name>\n    <trkseg>\n')

            # Записываем новую координату
            f.write(f'      <trkpt lat="{lat}" lon="{lon}">\n')
            f.write(f'        <time>{time}</time>\n')
            f.write(f'      </trkpt>\n')

        # Обновляем UI (отображение в таблице)
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values and values[0] == board_id:
                self.tree.item(item, values=(board_id, callsign, lat, lon, time, "Да"))
                self.highlight_row(item, current_time)
                break
        else:
            item = self.tree.insert('', 'end', values=(board_id, callsign, lat, lon, time, "Да"))
            self.highlight_row(item, current_time)

    def to_gpx(self, board_id, callsign, lat, lon, time):
        """Сохраняет координаты в файл GPX."""
        track_filename = f'{self.path_entry.get()}\\{board_id}_{callsign}.gpx' if callsign != "Unknown" else f'{self.path_entry.get()}\\{board_id}.gpx'

        # Создание структуры GPX
        gpx = ET.Element("gpx", version="1.1", xmlns="http://www.topografix.com/GPX/1/1")
        trk = ET.SubElement(gpx, "trk")
        trkseg = ET.SubElement(trk, "trkseg")

        # Добавляем точку с координатами
        trkpt = ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lon))
        time_element = ET.SubElement(trkpt, "time")
        time_element.text = time

        # Сохраняем файл
        tree = ET.ElementTree(gpx)
        tree.write(track_filename, xml_declaration=True, encoding="UTF-8")

        print(f"Данные сохранены в файл: {track_filename}")
    def highlight_row(self, item, current_time):
        """Выделяет строку в таблице в зависимости от времени последнего обновления."""
        board_id = self.tree.item(item, "values")[0]
        last_update_time = self.last_update.get(board_id)

        if last_update_time:
            time_diff = current_time - last_update_time
            if time_diff > timedelta(minutes=30):
                self.tree.item(item, tags="red")
            elif time_diff > timedelta(minutes=15):
                self.tree.item(item, tags="yellow")
            else:
                self.tree.item(item, tags="green")

    def start_reading(self):
        """Запускает поток чтения из порта."""
        port = self.com_port.get()
        threading.Thread(target=self.read_serial, args=(port, 115200), daemon=True).start()
        self.status_label.config(text="🟢 Подключено", fg="green")

    def auto_select_port(self):
        """Автоматически выбирает первый доступный COM порт и пытается подключиться к нему."""
        available_ports = self.get_available_ports()

        if available_ports:
            self.status_label.config(text="🟠 Идет поиск порта...", fg="orange")
            for port in available_ports:
                try:
                    self.com_port.set(port)  # Устанавливаем текущий COM порт
                    threading.Thread(target=self.start_reading_from_auto_port, args=(port,), daemon=True).start()
                    break  # Если подключение успешно, выходим из цикла
                except Exception as e:
                    print(f"Ошибка подключения к {port}: {e}")
                    continue  # Пытаемся подключиться к следующему порту
            else:
                self.status_label.config(text="🔴 Нет доступных портов", fg="red")
                messagebox.showerror("Ошибка", "Не удалось подключиться к порту.")
        else:
            self.status_label.config(text="🔴 Нет доступных портов", fg="red")
            messagebox.showerror("Ошибка", "Не найдены доступные порты.")

    def start_reading_from_auto_port(self, port):
        """Запускает чтение данных с автоматически выбранного порта."""
        try:
            self.status_label.config(text="🟠 Подключение...", fg="orange")  # Статус подключения
            self.read_serial(port, 115200)  # Чтение данных с порта
            self.status_label.config(text="🟢 Подключено", fg="green")  # Если успешно, обновляем статус на "Подключено"
        except Exception as e:
            self.status_label.config(text="🔴 Ошибка подключения", fg="red")  # Если не удается подключиться
            print(f"Ошибка подключения: {e}")
            messagebox.showerror("Ошибка", f"Ошибка подключения к порту: {e}")

    def browse_path(self):
        """Открывает диалог для выбора пути сохранения файла."""
        path = filedialog.askdirectory(initialdir=self.path_entry.get())  # Показываем текущую папку
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)

    def copy_path(self):
        """Копирует путь сохранения в буфер обмена."""
        path = self.path_entry.get()
        pyperclip.copy(path)
        messagebox.showinfo("Информация", "Путь сохранения скопирован в буфер обмена.")

    def on_right_click(self, event):
        """Обработчик ПКМ для контекстного меню."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def copy_coordinates(self):
        """Копирует последние координаты в буфер обмена."""
        selected_item = self.tree.selection()
        if selected_item:
            values = self.tree.item(selected_item[0], "values")
            lat = values[2]
            lon = values[3]
            coordinates = f"Широта: {lat}, Долгота: {lon}"
            pyperclip.copy(coordinates)  # Копируем координаты в буфер обмена
            messagebox.showinfo("Информация", "Координаты скопированы в буфер обмена.")
