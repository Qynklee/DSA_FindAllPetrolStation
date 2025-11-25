import json
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass
import time

@dataclass
class Point:
    """Đại diện cho một điểm trên bản đồ"""
    lat: float
    lon: float
    data: dict
    
    def distance_to(self, other: 'Point') -> float:
        """Tính khoảng cách Haversine giữa 2 điểm (km)"""
        R = 6371  # Bán kính trái đất (km)
        
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

@dataclass
class MBR:
    """Minimum Bounding Rectangle"""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    
    def area(self) -> float:
        """Tính diện tích MBR"""
        return (self.max_lat - self.min_lat) * (self.max_lon - self.min_lon)
    
    def contains_point(self, point: Point) -> bool:
        """Kiểm tra MBR có chứa điểm không"""
        return (self.min_lat <= point.lat <= self.max_lat and 
                self.min_lon <= point.lon <= self.max_lon)
    
    def intersects_circle(self, center: Point, radius_km: float) -> bool:
        """Kiểm tra MBR có giao với hình tròn không"""
        # Tìm điểm gần nhất trong MBR đến center
        closest_lat = max(self.min_lat, min(center.lat, self.max_lat))
        closest_lon = max(self.min_lon, min(center.lon, self.max_lon))
        
        closest_point = Point(closest_lat, closest_lon, {})
        return center.distance_to(closest_point) <= radius_km
    
    def expand_to_include(self, point: Point) -> 'MBR':
        """Mở rộng MBR để bao gồm điểm mới"""
        return MBR(
            min(self.min_lat, point.lat),
            max(self.max_lat, point.lat),
            min(self.min_lon, point.lon),
            max(self.max_lon, point.lon)
        )
    
    def expand_to_include_mbr(self, other: 'MBR') -> 'MBR':
        """Mở rộng MBR để bao gồm MBR khác"""
        return MBR(
            min(self.min_lat, other.min_lat),
            max(self.max_lat, other.max_lat),
            min(self.min_lon, other.min_lon),
            max(self.max_lon, other.max_lon)
        )
    
    @staticmethod
    def from_point(point: Point) -> 'MBR':
        """Tạo MBR từ một điểm"""
        return MBR(point.lat, point.lat, point.lon, point.lon)
    
    @staticmethod
    def from_points(points: List[Point]) -> 'MBR':
        """Tạo MBR bao quanh danh sách điểm"""
        if not points:
            return MBR(0, 0, 0, 0)
        
        lats = [p.lat for p in points]
        lons = [p.lon for p in points]
        return MBR(min(lats), max(lats), min(lons), max(lons))

class RTreeNode:
    """Node trong R-Tree"""
    def __init__(self, is_leaf: bool = True, parent=None):
        self.is_leaf = is_leaf
        self.mbr: Optional[MBR] = None
        self.entries: List[Tuple[MBR, any]] = []  # (MBR, Point hoặc RTreeNode)
        self.parent = parent
    
    def is_full(self, max_entries: int) -> bool:
        """Kiểm tra node đã đầy chưa"""
        return len(self.entries) >= max_entries
    
    def update_mbr(self):
        """Cập nhật MBR của node"""
        if not self.entries:
            self.mbr = None
            return
        
        mbr = self.entries[0][0]
        for entry_mbr, _ in self.entries[1:]:
            mbr = mbr.expand_to_include_mbr(entry_mbr)
        self.mbr = mbr

class RTree:
    """R-Tree implementation với Linear Split Algorithm"""
    def __init__(self, max_entries: int = 5):
        self.max_entries = max_entries
        self.min_entries = max(2, max_entries // 2)
        self.root = RTreeNode(is_leaf=True)
    
    def insert(self, point: Point):
        """Chèn một điểm vào R-Tree"""
        mbr = MBR.from_point(point)
        
        # Tìm node lá phù hợp
        leaf = self._choose_leaf(self.root, mbr)
        
        # Thêm điểm vào node lá
        leaf.entries.append((mbr, point))
        leaf.update_mbr()
        
        # Xử lý split nếu cần
        if len(leaf.entries) > self.max_entries:
            self._handle_overflow(leaf)
    
    def _choose_leaf(self, node: RTreeNode, mbr: MBR) -> RTreeNode:
        """Chọn node lá phù hợp để chèn"""
        if node.is_leaf:
            return node
        
        # Tìm entry có sự mở rộng diện tích nhỏ nhất
        best_entry = None
        min_enlargement = float('inf')
        
        for entry_mbr, child_node in node.entries:
            enlarged_mbr = entry_mbr.expand_to_include_mbr(mbr)
            enlargement = enlarged_mbr.area() - entry_mbr.area()
            
            if enlargement < min_enlargement:
                min_enlargement = enlargement
                best_entry = child_node
        
        return self._choose_leaf(best_entry, mbr)
    
    def _handle_overflow(self, node: RTreeNode):
        """Xử lý overflow khi node đầy"""
        # Split node
        node1, node2 = self._split_node(node)
        
        if node == self.root:
            # Tạo root mới
            new_root = RTreeNode(is_leaf=False)
            new_root.entries.append((node1.mbr, node1))
            new_root.entries.append((node2.mbr, node2))
            new_root.update_mbr()
            node1.parent = new_root
            node2.parent = new_root
            self.root = new_root
        else:
            # Cập nhật parent
            parent = node.parent
            
            # Xóa entry cũ của node
            parent.entries = [(mbr, child) for mbr, child in parent.entries if child != node]
            
            # Thêm 2 node mới
            parent.entries.append((node1.mbr, node1))
            parent.entries.append((node2.mbr, node2))
            parent.update_mbr()
            
            node1.parent = parent
            node2.parent = parent
            
            # Kiểm tra overflow của parent
            if len(parent.entries) > self.max_entries:
                self._handle_overflow(parent)
    
    def _split_node(self, node: RTreeNode) -> Tuple[RTreeNode, RTreeNode]:
        """Split node sử dụng Linear Split Algorithm"""
        # Linear Pick Seeds
        seed1_idx, seed2_idx = self._linear_pick_seeds(node.entries)
        
        # Tạo 2 node mới
        node1 = RTreeNode(is_leaf=node.is_leaf, parent=node.parent)
        node2 = RTreeNode(is_leaf=node.is_leaf, parent=node.parent)
        
        node1.entries.append(node.entries[seed1_idx])
        node2.entries.append(node.entries[seed2_idx])
        
        # Cập nhật parent pointer cho các child
        if not node.is_leaf:
            node.entries[seed1_idx][1].parent = node1
            node.entries[seed2_idx][1].parent = node2
        
        # Phân phối các entry còn lại
        remaining = [e for i, e in enumerate(node.entries) 
                    if i != seed1_idx and i != seed2_idx]
        
        for entry in remaining:
            node1.update_mbr()
            node2.update_mbr()
            
            # Chọn node có sự mở rộng diện tích nhỏ hơn
            mbr, data = entry
            
            enlarged1 = node1.mbr.expand_to_include_mbr(mbr)
            enlarged2 = node2.mbr.expand_to_include_mbr(mbr)
            
            enlargement1 = enlarged1.area() - node1.mbr.area()
            enlargement2 = enlarged2.area() - node2.mbr.area()
            
            if enlargement1 < enlargement2:
                node1.entries.append(entry)
                if not node.is_leaf:
                    data.parent = node1
            elif enlargement2 < enlargement1:
                node2.entries.append(entry)
                if not node.is_leaf:
                    data.parent = node2
            else:
                # Nếu bằng nhau, chọn node có diện tích nhỏ hơn
                if node1.mbr.area() < node2.mbr.area():
                    node1.entries.append(entry)
                    if not node.is_leaf:
                        data.parent = node1
                else:
                    node2.entries.append(entry)
                    if not node.is_leaf:
                        data.parent = node2
        
        node1.update_mbr()
        node2.update_mbr()
        
        return node1, node2
    
    def _linear_pick_seeds(self, entries: List[Tuple[MBR, any]]) -> Tuple[int, int]:
        """Linear Pick Seeds Algorithm"""
        max_separation = -float('inf')
        seed1_idx = seed2_idx = 0
        
        # Tìm cặp có separation lớn nhất theo lat và lon
        for dim in ['lat', 'lon']:
            if dim == 'lat':
                sorted_entries = sorted(enumerate(entries), 
                                      key=lambda x: x[1][0].min_lat)
                lowest = sorted_entries[0]
                sorted_entries = sorted(enumerate(entries), 
                                      key=lambda x: x[1][0].max_lat, reverse=True)
                highest = sorted_entries[0]
                
                width = max(mbr.max_lat for mbr, _ in entries) - \
                       min(mbr.min_lat for mbr, _ in entries)
                if width == 0:
                    continue
                    
                separation = abs(highest[1][0].max_lat - lowest[1][0].min_lat) / width
            else:
                sorted_entries = sorted(enumerate(entries), 
                                      key=lambda x: x[1][0].min_lon)
                lowest = sorted_entries[0]
                sorted_entries = sorted(enumerate(entries), 
                                      key=lambda x: x[1][0].max_lon, reverse=True)
                highest = sorted_entries[0]
                
                width = max(mbr.max_lon for mbr, _ in entries) - \
                       min(mbr.min_lon for mbr, _ in entries)
                if width == 0:
                    continue
                    
                separation = abs(highest[1][0].max_lon - lowest[1][0].min_lon) / width
            
            if separation > max_separation:
                max_separation = separation
                seed1_idx = lowest[0]
                seed2_idx = highest[0]
        
        return seed1_idx, seed2_idx
    

    
    def search(self, center: Point, radius_km: float) -> List[Tuple[Point, float]]:
        """Tìm kiếm các điểm trong bán kính r từ center"""
        results = []
        self._search_recursive(self.root, center, radius_km, results)
        
        # Sắp xếp theo khoảng cách
        results.sort(key=lambda x: x[1])
        return results
    
    def _search_recursive(self, node: RTreeNode, center: Point, 
                         radius_km: float, results: List[Tuple[Point, float]]):
        """Tìm kiếm đệ quy trong R-Tree"""
        if not node.mbr:
            return
        
        # Kiểm tra MBR có giao với hình tròn không
        if not node.mbr.intersects_circle(center, radius_km):
            return
        
        if node.is_leaf:
            # Node lá - kiểm tra từng điểm
            for mbr, point in node.entries:
                distance = center.distance_to(point)
                if distance <= radius_km:
                    results.append((point, distance))
        else:
            # Node nội bộ - tìm kiếm đệ quy
            for mbr, child_node in node.entries:
                self._search_recursive(child_node, center, radius_km, results)

def main():
    """Chương trình chính"""
    import argparse
    
    parser = argparse.ArgumentParser(description='R-Tree tìm kiếm trạm xăng')
    parser.add_argument('--file', type=str, required=True, 
                       help='Đường dẫn file JSON chứa dữ liệu trạm xăng')
    parser.add_argument('--max-entries', type=int, default=5, 
                       help='Số lượng tối đa MBR cho mỗi node (N)')
    parser.add_argument('--lat', type=float, 
                       help='Vĩ độ điểm tìm kiếm')
    parser.add_argument('--lon', type=float, 
                       help='Kinh độ điểm tìm kiếm')
    parser.add_argument('--radius', type=float, 
                       help='Bán kính tìm kiếm (km)')
    
    args = parser.parse_args()
    
    # Đọc dữ liệu
    print(f"Đang đọc dữ liệu từ {args.file}...")
    with open(args.file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Đã đọc {len(data)} trạm xăng")
    
    # Tạo R-Tree
    print(f"Đang tạo R-Tree với max_entries = {args.max_entries}...")
    rtree = RTree(max_entries=args.max_entries)
    
    for item in data:
        point = Point(
            lat=item['coordinates'][0],
            lon=item['coordinates'][1],
            data=item
        )
        rtree.insert(point)
    
    print("Đã tạo R-Tree thành công!")
    
    # Tìm kiếm nếu có tham số
    if args.lat is not None and args.lon is not None and args.radius is not None:
        print(f"\nTìm kiếm trạm xăng gần điểm ({args.lat}, {args.lon}) "
              f"trong bán kính {args.radius} km...")
        
        search_point = Point(args.lat, args.lon, {})
        results = rtree.search(search_point, args.radius)
        
        print(f"\nTìm thấy {len(results)} trạm xăng:")
        print("-" * 80)
        
        for i, (point, distance) in enumerate(results, 1):
            print(f"{i}. {point.data['name']} ({point.data['brand']})")
            print(f"   Địa chỉ: {point.data['display_name']}")
            print(f"   Khoảng cách: {distance:.2f} km")
            print(f"   Tọa độ: ({point.lat}, {point.lon})")
            print()
    else:
        # Chế độ interactive
        print("\n" + "="*80)
        print("R-TREE ĐÃ SẴN SÀNG - Chế độ tìm kiếm interactive")
        print("="*80)
        
        while True:
            try:
                print("\nNhập thông tin tìm kiếm (hoặc 'q' để thoát):")
                lat_input = input("  Vĩ độ (lat): ").strip()
                if lat_input.lower() == 'q':
                    break
                
                lon_input = input("  Kinh độ (lon): ").strip()
                if lon_input.lower() == 'q':
                    break
                
                radius_input = input("  Bán kính (km): ").strip()
                if radius_input.lower() == 'q':
                    break
                
                lat = float(lat_input)
                lon = float(lon_input)
                radius = float(radius_input)
                
                search_point = Point(lat, lon, {})

                start = time.perf_counter()

                results = rtree.search(search_point, radius)

                end = time.perf_counter()
                elapsed_ms = (end - start) * 1000
                
                print(f"Thời gian thực hiện: {elapsed_ms:.3f} ms")
                
                print(f"\n{'='*80}")
                print(f"Tìm thấy {len(results)} trạm xăng trong bán kính {radius} km:")
                print("="*80)
                
                for i, (point, distance) in enumerate(results, 1):
                    print(f"\n{i}. {point.data['name']} ({point.data['brand']})")
                    print(f"   Địa chỉ: {point.data['display_name']}")
                    print(f"   Khoảng cách: {distance:.2f} km")
                    print(f"   Tọa độ: ({point.lat}, {point.lon})")
                
            except ValueError as e:
                print(f"Lỗi: Vui lòng nhập số hợp lệ! ({e})")
            except KeyboardInterrupt:
                print("\n\nĐã hủy bỏ.")
                break
        
        print("\nCảm ơn bạn đã sử dụng!")

if __name__ == "__main__":
    main()