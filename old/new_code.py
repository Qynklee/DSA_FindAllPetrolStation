import json
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import requests

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
        """Mở rộng bounding box để chứa điểm mới"""
        lat, lon = point
        return BoundingBox(
            min(self.min_lat, lat),
            max(self.max_lat, lat),
            min(self.min_lon, lon),
            max(self.max_lon, lon)
        )
    
    def contains_point(self, point: Tuple[float, float]) -> bool:
        """Kiểm tra điểm có nằm trong box không"""
        lat, lon = point
        return (self.min_lat <= lat <= self.max_lat and 
                self.min_lon <= lon <= self.max_lon)
    
    def intersects_circle(self, center: Tuple[float, float], radius_km: float) -> bool:
        """Kiểm tra box có giao với hình tròn không"""
        # Tìm điểm gần nhất trong box với tâm
        lat, lon = center
        closest_lat = max(self.min_lat, min(lat, self.max_lat))
        closest_lon = max(self.min_lon, min(lon, self.max_lon))
        
        # Tính khoảng cách từ tâm đến điểm gần nhất
        dist = haversine_distance(center, (closest_lat, closest_lon))
        return dist <= radius_km

class RTreeNode:
    """Node của R-Tree"""
    def __init__(self, max_entries=4, is_leaf=True):
        self.max_entries = max_entries
        self.is_leaf = is_leaf
        self.entries = []  # [(bbox, data/child_node)]
        self.bbox: Optional[BoundingBox] = None
    
    def compute_bbox(self):
        """Tính bounding box cho node"""
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
    """R-Tree implementation"""
    def __init__(self, max_entries=4):
        self.max_entries = max_entries
        self.root = RTreeNode(max_entries, is_leaf=True)
    
    def insert(self, point: Tuple[float, float], data: Dict):
        """Chèn một điểm vào R-Tree"""
        bbox = BoundingBox(point[0], point[0], point[1], point[1])
        self._insert(self.root, bbox, data)
    
    def _insert(self, node: RTreeNode, bbox: BoundingBox, data: Dict):
        """Chèn đệ quy"""
        if node.is_leaf:
            node.entries.append((bbox, data))
            node.compute_bbox()
            
            if len(node.entries) > self.max_entries:
                self._split_node(node)
        else:
            # Tìm child node tốt nhất để chèn
            best_child = self._choose_subtree(node, bbox)
            self._insert(best_child, bbox, data)
            node.compute_bbox()
    
    def _choose_subtree(self, node: RTreeNode, bbox: BoundingBox) -> RTreeNode:
        """Chọn subtree tốt nhất để chèn"""
        min_enlargement = float('inf')
        best_child = None
        
        for child_bbox, child_node in node.entries:
            # Tính độ mở rộng cần thiết
            original_area = child_bbox.area()
            new_bbox = self._merge_bbox(child_bbox, bbox)
            new_area = new_bbox.area()
            enlargement = new_area - original_area
            
            if enlargement < min_enlargement:
                min_enlargement = enlargement
                best_child = child_node
        
        return best_child
    
    def _merge_bbox(self, bbox1: BoundingBox, bbox2: BoundingBox) -> BoundingBox:
        """Gộp hai bounding box"""
        return BoundingBox(
            min(bbox1.min_lat, bbox2.min_lat),
            max(bbox1.max_lat, bbox2.max_lat),
            min(bbox1.min_lon, bbox2.min_lon),
            max(bbox1.max_lon, bbox2.max_lon)
        )
    
    def _split_node(self, node: RTreeNode):
        """Chia node khi quá nhiều entries (simplified split)"""
        # Đơn giản hóa: chia làm đôi theo latitude
        node.entries.sort(key=lambda x: x[0].min_lat)
        mid = len(node.entries) // 2
        
        # Giữ nửa đầu trong node hiện tại
        node.entries = node.entries[:mid]
        node.compute_bbox()
    
    def search(self, center: Tuple[float, float], radius_km: float) -> List[Dict]:
        """Tìm kiếm các điểm trong bán kính"""
        results = []
        self._search(self.root, center, radius_km, results)
        return results
    
    def _search(self, node: RTreeNode, center: Tuple[float, float], 
                radius_km: float, results: List[Dict]):
        """Tìm kiếm đệ quy"""
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
    """Tính khoảng cách Haversine giữa 2 tọa độ (km)"""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    R = 6371  # Bán kính Trái Đất (km)
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def get_location_info(lat: float, lon: float) -> Dict:
    """Lấy thông tin địa điểm từ OpenStreetMap Nominatim API"""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'addressdetails': 1,
        'zoom': 18
    }
    headers = {
        'User-Agent': 'GasStationFinder/1.0'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            return {
                'ward': address.get('suburb') or address.get('neighbourhood') or address.get('hamlet'),
                'province': address.get('state') or address.get('province') or address.get('city')
            }
    except Exception as e:
        print(f"Lỗi khi gọi API: {e}")
    
    return {'ward': None, 'province': None}

class GasStationFinder:
    """Hệ thống tìm kiếm trạm xăng với R-Tree phân cấp"""
    def __init__(self, json_file: str):
        self.stations = self._load_data(json_file)
        self.province_index = {}  # {province: {ward: [stations]}}
        self.rtrees = {}  # {(province, ward): RTree}
        self._build_index()
    
    def _load_data(self, json_file: str) -> List[Dict]:
        """Load dữ liệu từ file JSON"""
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _build_index(self):
        """Xây dựng index theo province/ward và R-Tree"""
        print("Đang xây dựng R-Tree index...")
        
        # Nhóm stations theo province và ward
        for station in self.stations:
            province = station.get('province', 'Unknown')
            ward = station.get('ward', 'Unknown')
            
            if province not in self.province_index:
                self.province_index[province] = {}
            if ward not in self.province_index[province]:
                self.province_index[province][ward] = []
            
            self.province_index[province][ward].append(station)
        
        # Tạo R-Tree cho mỗi (province, ward)
        for province, wards in self.province_index.items():
            for ward, stations in wards.items():
                rtree = RTree(max_entries=10)
                for station in stations:
                    coords = tuple(station['coordinates'])
                    rtree.insert(coords, station)
                self.rtrees[(province, ward)] = rtree
        
        print(f"Đã xây dựng {len(self.rtrees)} R-Tree cho các province/ward")
    
    def find_relevant_areas(self, center: Tuple[float, float], 
                           radius_km: float) -> List[Tuple[str, str]]:
        """Tìm các (province, ward) nằm trong bán kính"""
        relevant = []
        
        for (province, ward), rtree in self.rtrees.items():
            if rtree.root.bbox and rtree.root.bbox.intersects_circle(center, radius_km):
                relevant.append((province, ward))
        
        return relevant
    
    def search(self, lat: float, lon: float, radius_km: float) -> List[Dict]:
        """Tìm kiếm trạm xăng theo tọa độ và bán kính"""
        center = (lat, lon)
        
        # Tìm các province/ward liên quan
        print(f"\nTìm kiếm trong bán kính {radius_km}km từ ({lat}, {lon})")
        relevant_areas = self.find_relevant_areas(center, radius_km)
        print(f"Tìm thấy {len(relevant_areas)} khu vực liên quan")
        
        # Tìm kiếm trong các R-Tree liên quan
        all_results = []
        for province, ward in relevant_areas:
            rtree = self.rtrees[(province, ward)]
            results = rtree.search(center, radius_km)
            all_results.extend(results)
        
        # Sắp xếp theo khoảng cách
        all_results.sort(key=lambda x: x['distance_km'])
        
        return all_results

def main():
    # Đường dẫn file dữ liệu
    json_file = 'db_fix.json'
    
    # Khởi tạo hệ thống
    try:
        finder = GasStationFinder(json_file)
    except FileNotFoundError:
        print(f"Không tìm thấy file {json_file}")
        print("Vui lòng tạo file với cấu trúc như mô tả")
        return
    
    # Nhập tọa độ và bán kính
    print("\n=== TÌM KIẾM TRẠM XĂNG ===")
    
    try:
        lat = float(input("Nhập vĩ độ (latitude): "))
        lon = float(input("Nhập kinh độ (longitude): "))
        radius = float(input("Nhập bán kính tìm kiếm (km): "))
        
        # Lấy thông tin địa điểm (tùy chọn)
        print("\nĐang lấy thông tin địa điểm từ OpenStreetMap...")
        location_info = get_location_info(lat, lon)
        if location_info['province']:
            print(f"Vị trí: {location_info['ward']}, {location_info['province']}")
        
        # Tìm kiếm
        results = finder.search(lat, lon, radius)
        
        # Hiển thị kết quả
        print(f"\n=== KẾT QUẢ: Tìm thấy {len(results)} trạm xăng ===\n")
        
        for i, station in enumerate(results, 1):
            print(f"{i}. {station['name']} ({station['brand']})")
            print(f"   Địa chỉ: {station['ward']}, {station['province']}")
            print(f"   Khoảng cách: {station['distance_km']}km")
            print(f"   Tọa độ: {station['coordinates']}")
            print()
        
        # Xuất JSON
        output_file = 'search_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Kết quả đã được lưu vào {output_file}")
        
    except ValueError:
        print("Lỗi: Vui lòng nhập số hợp lệ")
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == '__main__':
    main()