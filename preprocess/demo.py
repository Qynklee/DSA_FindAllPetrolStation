import json
import numpy as np
from math import radians, sin, cos, sqrt, asin
import heapq
import itertools

# Hàm tính khoảng cách Haversine (km)
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Bán kính Trái Đất (km)
    return c * r

# Triển khai R-Tree đơn giản tự viết (cho 2D points)
class RTreeNode:
    def __init__(self, is_leaf=False):
        self.is_leaf = is_leaf
        self.entries = []  # (mbr, child or data_id)
        self.mbr = None

    def update_mbr(self):
        if not self.entries:
            self.mbr = None
            return
        min_lon = min(e[0][0] for e in self.entries)
        min_lat = min(e[0][1] for e in self.entries)
        max_lon = max(e[0][2] for e in self.entries)
        max_lat = max(e[0][3] for e in self.entries)
        self.mbr = (min_lon, min_lat, max_lon, max_lat)

class RTree:
    def __init__(self, max_entries=4, min_entries=2):
        self.root = RTreeNode(is_leaf=True)
        self.max_entries = max_entries
        self.min_entries = min_entries

    def _choose_subtree(self, node, mbr):
        best_enlargement = float('inf')
        best_child = None
        for entry in node.entries:
            enl = self._enlargement(entry[0], mbr)
            if enl < best_enlargement:
                best_enlargement = enl
                best_child = entry[1]
        return best_child

    def _enlargement(self, mbr1, mbr2):
        min_lon = min(mbr1[0], mbr2[0])
        min_lat = min(mbr1[1], mbr2[1])
        max_lon = max(mbr1[2], mbr2[2])
        max_lat = max(mbr1[3], mbr2[3])
        new_area = (max_lon - min_lon) * (max_lat - min_lat)
        old_area = (mbr1[2] - mbr1[0]) * (mbr1[3] - mbr1[1])
        return new_area - old_area

    def _split(self, node):
        # Simple linear split
        if (node.mbr[2] - node.mbr[0]) > (node.mbr[3] - node.mbr[1]):
            axis = 0  # lon
        else:
            axis = 1  # lat
        node.entries.sort(key=lambda e: (e[0][axis] + e[0][axis+2]) / 2)
        mid = len(node.entries) // 2
        new_node = RTreeNode(is_leaf=node.is_leaf)
        new_node.entries = node.entries[mid:]
        node.entries = node.entries[:mid]
        node.update_mbr()
        new_node.update_mbr()
        return new_node

    def _insert(self, node, mbr, data_id):
        if node.is_leaf:
            node.entries.append((mbr, data_id))
            node.update_mbr()
        else:
            child = self._choose_subtree(node, mbr)
            new_child = self._insert(child, mbr, data_id)
            if new_child:
                node.entries.append((new_child.mbr, new_child))
                node.update_mbr()
        if len(node.entries) > self.max_entries:
            return self._split(node)
        return None

    def insert(self, point, data_id):
        mbr = (point[0], point[1], point[0], point[1])
        new_root_child = self._insert(self.root, mbr, data_id)
        if new_root_child:
            new_root = RTreeNode()
            new_root.entries = [(self.root.mbr, self.root), (new_root_child.mbr, new_root_child)]
            new_root.update_mbr()
            self.root = new_root

    def intersection(self, query_mbr):
        results = []
        self._intersection(self.root, query_mbr, results)
        return results

    def _intersection(self, node, query_mbr, results):
        for mbr, item in node.entries:
            if self._overlaps(mbr, query_mbr):
                if node.is_leaf:
                    results.append(item)
                else:
                    self._intersection(item, query_mbr, results)

    def _overlaps(self, mbr1, mbr2):
        return not (mbr1[2] < mbr2[0] or mbr1[0] > mbr2[2] or mbr1[3] < mbr2[1] or mbr1[1] > mbr2[3])

    def _mbr_distance(self, point, mbr):
        lon, lat = point
        closest_lon = max(mbr[0], min(lon, mbr[2]))
        closest_lat = max(mbr[1], min(lat, mbr[3]))
        return haversine(lon, lat, closest_lon, closest_lat)

    def nearest(self, point, k=1):
        pq = []
        counter = itertools.count()
        heapq.heappush(pq, (0, next(counter), self.root))
        results = []
        while pq and len(results) < k:
            dist, _, item = heapq.heappop(pq)
            if isinstance(item, RTreeNode):
                node = item
                for mbr, child_or_id in node.entries:
                    mbr_dist = self._mbr_distance(point, mbr)
                    if node.is_leaf:
                        heapq.heappush(pq, (mbr_dist, next(counter), child_or_id))
                    else:
                        heapq.heappush(pq, (mbr_dist, next(counter), child_or_id))
            else:
                # item is data_id
                results.append(item)
        return results

# Đọc và parse dữ liệu từ GeoJSON
def load_geojson(filename='export.geojson'):
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stations = []
    for i, feature in enumerate(data['features']):
        if feature['geometry']['type'] == 'Polygon':
            # Tính centroid từ coordinates[0] (outer ring của Polygon)
            coords = np.array(feature['geometry']['coordinates'][0])
            centroid_lon = np.mean(coords[:, 0])
            centroid_lat = np.mean(coords[:, 1])
            
            props = feature['properties']
            name = props.get('name', 'Trạm xăng không tên')
            brand = props.get('brand', 'Không rõ')
            note = props.get('note', '')  # Nếu có trường note
            at_id = props.get('@id', 'Không có')  # Thêm @id
            
            stations.append({
                'id': i,
                'name': name,
                'brand': brand,
                'note': note,
                'lat': centroid_lat,
                'lon': centroid_lon,
                'at_id': at_id
            })
    
    print(f'Đã tải {len(stations)} trạm xăng từ file {filename}.')
    return stations

# Xây dựng R-Tree từ list stations
def build_rtree(stations):
    rtree = RTree()
    for station in stations:
        point = (station['lon'], station['lat'])
        rtree.insert(point, station['id'])
    return rtree

# Tìm kiếm chính
def search_stations(stations, rtree, user_lat, user_lon, radius_km):
    # Approximate bounding box cho bán kính (km sang độ approx)
    km_to_deg_lat = radius_km / 111.0
    km_to_deg_lon = radius_km / (111.0 * cos(radians(user_lat)))
    min_lon = user_lon - km_to_deg_lon
    max_lon = user_lon + km_to_deg_lon
    min_lat = user_lat - km_to_deg_lat
    max_lat = user_lat + km_to_deg_lat
    query_mbr = (min_lon, min_lat, max_lon, max_lat)
    
    # Query intersection
    candidates = rtree.intersection(query_mbr)
    
    # Lọc bằng khoảng cách thực tế
    results = []
    for i in candidates:
        station = stations[i]
        dist = haversine(user_lon, user_lat, station['lon'], station['lat'])
        if dist <= radius_km:
            results.append((dist, station))
    
    # Sắp xếp theo khoảng cách
    results.sort(key=lambda x: x[0])
    
    if results:
        return results
    else:
        # Nếu rỗng, tìm 2 trạm gần nhất
        point = (user_lon, user_lat)
        nearest_ids = rtree.nearest(point, 2)
        nearest_results = []
        for i in nearest_ids:
            station = stations[i]
            dist = haversine(user_lon, user_lat, station['lon'], station['lat'])
            nearest_results.append((dist, station))
        return nearest_results

# Main
if __name__ == '__main__':
    geojson_file = 'export.geojson'
    stations = load_geojson(geojson_file)
    rtree = build_rtree(stations)
    
    # Nhập từ người dùng
    try:
        user_lat = float(input("Nhập vĩ độ (lat) của bạn: "))
        user_lon = float(input("Nhập kinh độ (lon) của bạn: "))
        radius_km = float(input("Nhập bán kính tìm kiếm (km): "))
        
        results = search_stations(stations, rtree, user_lat, user_lon, radius_km)
        
        if results:
            print("\nKết quả tìm kiếm:")
            for dist, station in results:
                print(f"- {station['name']} ({station['brand']})")
                print(f"  Tọa độ (centroid): {station['lat']:.6f}, {station['lon']:.6f}")
                print(f"  @id: {station['at_id']}")
                print(f"  Khoảng cách: {dist:.2f} km")
                if station['note']:
                    print(f"  Ghi chú: {station['note']}")
        else:
            print("Không tìm thấy trạm xăng trong bán kính.")
    except ValueError:
        print("Lỗi: Vui lòng nhập số hợp lệ.")
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file {geojson_file}. Vui lòng kiểm tra đường dẫn.")