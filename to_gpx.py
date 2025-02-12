import xml.etree.ElementTree as ET


def save_to_gpx(self, board_id, callsign, lat, lon, time):
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
