import sys
import json
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                             QTextEdit, QSplitter)
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QObject
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

# ============ R-Tree Implementation ============
@dataclass
class BoundingBox:
    """Bounding box cho R-Tree node"""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    
    def area(self) -> float:
        return (self.max_lat - self.min_lat) * (self.max_lon - self.min_lon)
    
    def expand(self, point: Tuple[float, float]) -> 'BoundingBox':
        lat, lon = point
        return BoundingBox(
            min(self.min_lat, lat),
            max(self.max_lat, lat),
            min(self.min_lon, lon),
            max(self.max_lon, lon)
        )
    
    def contains_point(self, point: Tuple[float, float]) -> bool:
        lat, lon = point
        return (self.min_lat <= lat <= self.max_lat and 
                self.min_lon <= lon <= self.max_lon)
    
    def intersects_circle(self, center: Tuple[float, float], radius_km: float) -> bool:
        lat, lon = center
        closest_lat = max(self.min_lat, min(lat, self.max_lat))
        closest_lon = max(self.min_lon, min(lon, self.max_lon))
        dist = haversine_distance(center, (closest_lat, closest_lon))
        return dist <= radius_km

class RTreeNode:
    def __init__(self, max_entries=4, is_leaf=True):
        self.max_entries = max_entries
        self.is_leaf = is_leaf
        self.entries = []
        self.bbox: Optional[BoundingBox] = None
    
    def compute_bbox(self):
        if not self.entries:
            return None
        first_bbox = self.entries[0][0]
        min_lat, max_lat = first_bbox.min_lat, first_bbox.max_lat
        min_lon, max_lon = first_bbox.min_lon, first_bbox.max_lon
        for bbox, _ in self.entries[1:]:
            min_lat = min(min_lat, bbox.min_lat)
            max_lat = max(max_lat, bbox.max_lat)
            min_lon = min(min_lon, bbox.min_lon)
            max_lon = max(max_lon, bbox.max_lon)
        self.bbox = BoundingBox(min_lat, max_lat, min_lon, max_lon)
        return self.bbox

class RTree:
    def __init__(self, max_entries=4):
        self.max_entries = max_entries
        self.root = RTreeNode(max_entries, is_leaf=True)
    
    def insert(self, point: Tuple[float, float], data: Dict):
        bbox = BoundingBox(point[0], point[0], point[1], point[1])
        self._insert(self.root, bbox, data)
    
    def _insert(self, node: RTreeNode, bbox: BoundingBox, data: Dict):
        if node.is_leaf:
            node.entries.append((bbox, data))
            node.compute_bbox()
            if len(node.entries) > self.max_entries:
                self._split_node(node)
        else:
            best_child = self._choose_subtree(node, bbox)
            self._insert(best_child, bbox, data)
            node.compute_bbox()
    
    def _choose_subtree(self, node: RTreeNode, bbox: BoundingBox) -> RTreeNode:
        min_enlargement = float('inf')
        best_child = None
        for child_bbox, child_node in node.entries:
            original_area = child_bbox.area()
            new_bbox = self._merge_bbox(child_bbox, bbox)
            new_area = new_bbox.area()
            enlargement = new_area - original_area
            if enlargement < min_enlargement:
                min_enlargement = enlargement
                best_child = child_node
        return best_child
    
    def _merge_bbox(self, bbox1: BoundingBox, bbox2: BoundingBox) -> BoundingBox:
        return BoundingBox(
            min(bbox1.min_lat, bbox2.min_lat),
            max(bbox1.max_lat, bbox2.max_lat),
            min(bbox1.min_lon, bbox2.min_lon),
            max(bbox1.max_lon, bbox2.max_lon)
        )
    
    def _split_node(self, node: RTreeNode):
        node.entries.sort(key=lambda x: x[0].min_lat)
        mid = len(node.entries) // 2
        node.entries = node.entries[:mid]
        node.compute_bbox()
    
    def search(self, center: Tuple[float, float], radius_km: float) -> List[Dict]:
        results = []
        self._search(self.root, center, radius_km, results)
        return results
    
    def _search(self, node: RTreeNode, center: Tuple[float, float], 
                radius_km: float, results: List[Dict]):
        if node.bbox and not node.bbox.intersects_circle(center, radius_km):
            return
        if node.is_leaf:
            for bbox, data in node.entries:
                point = tuple(data['coordinates'])
                dist = haversine_distance(center, point)
                if dist <= radius_km:
                    results.append({**data, 'distance_km': round(dist, 2)})
        else:
            for bbox, child_node in node.entries:
                if bbox.intersects_circle(center, radius_km):
                    self._search(child_node, center, radius_km, results)

def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def get_location_info(lat: float, lon: float) -> Dict:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'addressdetails': 1,
        'zoom': 18
    }
    headers = {'User-Agent': 'GasStationFinder/1.0'}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            display = data.get('display_name', 'Unknown')
            return {
                'ward': address.get('suburb') or address.get('neighbourhood') or address.get('hamlet'),
                'province': address.get('state') or address.get('province') or address.get('city'),
                'display_name': display
            }
    except Exception as e:
        print(f"API error: {e}")
    return {'ward': None, 'province': None, 'display_name': 'Unknown'}

class GasStationFinder:
    def __init__(self, json_file: str):
        self.stations = self._load_data(json_file)
        self.province_index = {}
        self.rtrees = {}
        self._build_index()
    
    def _load_data(self, json_file: str) -> List[Dict]:
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _build_index(self):
        for station in self.stations:
            province = station.get('province', 'Unknown')
            ward = station.get('ward', 'Unknown')
            if province not in self.province_index:
                self.province_index[province] = {}
            if ward not in self.province_index[province]:
                self.province_index[province][ward] = []
            self.province_index[province][ward].append(station)
        
        for province, wards in self.province_index.items():
            for ward, stations in wards.items():
                rtree = RTree(max_entries=10)
                for station in stations:
                    coords = tuple(station['coordinates'])
                    rtree.insert(coords, station)
                self.rtrees[(province, ward)] = rtree
    
    def find_relevant_areas(self, center: Tuple[float, float], 
                           radius_km: float) -> List[Tuple[str, str]]:
        relevant = []
        for (province, ward), rtree in self.rtrees.items():
            if rtree.root.bbox and rtree.root.bbox.intersects_circle(center, radius_km):
                relevant.append((province, ward))
        return relevant
    
    def search(self, lat: float, lon: float, radius_km: float) -> List[Dict]:
        center = (lat, lon)
        relevant_areas = self.find_relevant_areas(center, radius_km)
        all_results = []
        for province, ward in relevant_areas:
            rtree = self.rtrees[(province, ward)]
            results = rtree.search(center, radius_km)
            all_results.extend(results)
        all_results.sort(key=lambda x: x['distance_km'])
        return all_results

# ============ PyQt5 GUI ============
class MapBridge(QObject):
    """Bridge for communication between Python and JavaScript"""
    coordinateSelected = pyqtSignal(float, float)
    
    def __init__(self):
        super().__init__()

class GasStationMapApp(QMainWindow):
    def __init__(self, json_file='gas_stations.json'):
        super().__init__()
        self.setWindowTitle("Gas Station Finder - R-Tree Search")
        self.setGeometry(100, 100, 1400, 800)
        
        self.selected_point = None
        self.finder = None
        self.json_file = json_file
        
        # Initialize UI first
        self.init_ui()
        
        # Then load data
        self.load_data()
    
    def init_ui(self):
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Left panel - Map
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        self.radius_input = QLineEdit()
        self.radius_input.setPlaceholderText("Bán kính (km)")
        self.radius_input.setText("5")
        self.radius_input.setMaximumWidth(150)
        
        self.search_btn = QPushButton("Tìm kiếm")
        self.search_btn.clicked.connect(self.search_stations)
        self.search_btn.setEnabled(False)
        
        self.clear_btn = QPushButton("Xóa")
        self.clear_btn.clicked.connect(self.clear_map)
        
        self.location_label = QLabel("Nhấn vào bản đồ để chọn vị trí")
        self.location_label.setStyleSheet("font-weight: bold; color: #333;")
        
        control_layout.addWidget(QLabel("Bán kính:"))
        control_layout.addWidget(self.radius_input)
        control_layout.addWidget(self.search_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addWidget(self.location_label)
        control_layout.addStretch()
        
        # Map view
        self.map_view = QWebEngineView()
        self.channel = QWebChannel()
        self.bridge = MapBridge()
        self.bridge.coordinateSelected.connect(self.on_coordinate_selected)
        self.channel.registerObject('bridge', self.bridge)
        self.map_view.page().setWebChannel(self.channel)
        
        # Load map
        self.load_map()
        
        left_layout.addLayout(control_layout)
        left_layout.addWidget(self.map_view)
        
        # Right panel - Log
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        right_layout.addWidget(QLabel("Log:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumWidth(350)
        right_layout.addWidget(self.log_text)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
    
    def load_data(self):
        """Load gas station data"""
        self.log("Đang tải dữ liệu trạm xăng...")
        try:
            self.finder = GasStationFinder(self.json_file)
            self.log(f"Đã tải {len(self.finder.stations)} trạm xăng")
            self.log(f"Đã xây dựng {len(self.finder.rtrees)} R-Tree")
        except Exception as e:
            self.log(f"LỖI: {e}")
            self.finder = None
    
    def load_map(self):
        """Load OpenStreetMap with Leaflet"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>
                body { margin: 0; padding: 0; }
                #map { width: 100%; height: 100vh; }
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                var map = L.map('map').setView([10.8231, 106.6297], 12);
                
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors'
                }).addTo(map);
                
                var selectedMarker = null;
                var stationMarkers = [];
                var radiusCircle = null;
                
                var redIcon = L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    shadowSize: [41, 41]
                });
                
                var blueIcon = L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    shadowSize: [41, 41]
                });
                
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.bridge = channel.objects.bridge;
                    
                    map.on('click', function(e) {
                        var lat = e.latlng.lat;
                        var lng = e.latlng.lng;
                        
                        if (selectedMarker) {
                            map.removeLayer(selectedMarker);
                        }
                        
                        selectedMarker = L.marker([lat, lng], {icon: redIcon}).addTo(map);
                        selectedMarker.bindPopup("<b>Vị trí đã chọn</b><br>Lat: " + lat.toFixed(6) + "<br>Lng: " + lng.toFixed(6)).openPopup();
                        
                        window.bridge.coordinateSelected(lat, lng);
                    });
                });
                
                function clearStations() {
                    stationMarkers.forEach(function(marker) {
                        map.removeLayer(marker);
                    });
                    stationMarkers = [];
                    
                    if (selectedMarker) {
                        map.removeLayer(selectedMarker);
                        selectedMarker = null;
                    }
                    
                    if (radiusCircle) {
                        map.removeLayer(radiusCircle);
                        radiusCircle = null;
                    }
                }
                
                function addStation(lat, lng, name, address, distance) {
                    var marker = L.marker([lat, lng], {icon: blueIcon}).addTo(map);
                    marker.bindPopup("<b>" + name + "</b><br>" + address + "<br>Khoảng cách: " + distance + " km");
                    stationMarkers.push(marker);
                }
                
                function showRadius(lat, lng, radius) {
                    if (radiusCircle) {
                        map.removeLayer(radiusCircle);
                    }
                    radiusCircle = L.circle([lat, lng], {
                        radius: radius * 1000,
                        color: 'red',
                        fillColor: '#f03',
                        fillOpacity: 0.1
                    }).addTo(map);
                }
            </script>
        </body>
        </html>
        """
        self.map_view.setHtml(html_content)
    
    def log(self, message):
        """Add log message"""
        self.log_text.append(f"[{message}]")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def on_coordinate_selected(self, lat, lon):
        """Handle coordinate selection"""
        self.selected_point = (lat, lon)
        self.log(f"Đã chọn tọa độ: ({lat:.6f}, {lon:.6f})")
        
        # Get location info
        self.log("Đang lấy thông tin địa chỉ...")
        location = get_location_info(lat, lon)
        address = location.get('display_name', 'Unknown')
        self.location_label.setText(f"📍 {address}")
        self.log(f"Địa chỉ: {address}")
        
        self.search_btn.setEnabled(True)
    
    def search_stations(self):
        """Search for gas stations"""
        if not self.selected_point or not self.finder:
            return
        
        try:
            radius = float(self.radius_input.text())
        except ValueError:
            self.log("LỖI: Bán kính không hợp lệ")
            return
        
        lat, lon = self.selected_point
        self.log(f"\nBắt đầu tìm kiếm bán kính {radius}km...")
        
        # Search
        results = self.finder.search(lat, lon, radius)
        self.log(f"Tìm thấy {len(results)} trạm xăng")
        
        # Clear old markers
        self.map_view.page().runJavaScript("clearStations();")
        
        # Show radius
        self.map_view.page().runJavaScript(f"showRadius({lat}, {lon}, {radius});")
        
        # Add selected point marker
        self.map_view.page().runJavaScript(f"""
            if (selectedMarker) map.removeLayer(selectedMarker);
            selectedMarker = L.marker([{lat}, {lon}], {{icon: redIcon}}).addTo(map);
            selectedMarker.bindPopup("<b>Vị trí tìm kiếm</b>").openPopup();
        """)
        
        # Add station markers
        for i, station in enumerate(results[:50], 1):  # Limit to 50 stations
            s_lat, s_lon = station['coordinates']
            name = station['name'].replace("'", "\\'")
            addr = f"{station.get('ward', '')}, {station.get('province', '')}".replace("'", "\\'")
            dist = station['distance_km']
            
            self.map_view.page().runJavaScript(
                f"addStation({s_lat}, {s_lon}, '{name}', '{addr}', {dist});"
            )
            
            self.log(f"{i}. {station['name']} - {dist}km")
        
        if len(results) > 50:
            self.log(f"(Hiển thị 50/{len(results)} trạm gần nhất)")
    
    def clear_map(self):
        """Clear all markers"""
        self.map_view.page().runJavaScript("clearStations();")
        self.selected_point = None
        self.location_label.setText("Nhấn vào bản đồ để chọn vị trí")
        self.search_btn.setEnabled(False)
        self.log("Đã xóa bản đồ")

def main():
    app = QApplication(sys.argv)
    window = GasStationMapApp('db_fix.json')
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()