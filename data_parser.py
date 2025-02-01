import re


def parse_coordinates(data):
    """Извлекает координаты и позывной из строки лога."""
    # Ищем позицию по времени, широте и долготе
    match = re.search(r'Position reply: time=(\d+) lat=(\d+) lon=(\d+)', data)
    # Ищем позывной устройства
    callsign_match = re.search(r"Uncompressed device_callsign '(.*?)'", data)

    if match and callsign_match:
        time, lat, lon = match.groups()  # Извлекаем время, широту и долготу
        callsign = callsign_match.group(1)  # Извлекаем позывной
        return callsign, int(lat) / 1e7, int(lon) / 1e7, time
    return None  # Возвращаем None, если данные не были найдены