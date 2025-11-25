import json
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

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
    
    def intersects_square(self, center_lat: float, center_lon: float, 
                          half_side_lat: float, half_side_lon: float) -> bool:
        """
        Kiểm tra MBR có giao với hình vuông không.
        Hình vuông được định nghĩa bởi tâm và nửa cạnh (theo lat/lon).
        """
        # Tính bounds của hình vuông tìm kiếm
        square_min_lat = center_lat - half_side_lat
        square_max_lat = center_lat + half_side_lat
        square_min_lon = center_lon - half_side_lon
        square_max_lon = center_lon + half_side_lon
        
        # Kiểm tra giao nhau giữa 2 hình chữ nhật (MBR và square)
        # Hai hình chữ nhật KHÔNG giao nhau khi:
        # - MBR hoàn toàn ở bên trái square
        # - MBR hoàn toàn ở bên phải square
        # - MBR hoàn toàn ở phía trên square
        # - MBR hoàn toàn ở phía dưới square
        
        if self.max_lat < square_min_lat:  # MBR ở phía dưới square
            return False
        if self.min_lat > square_max_lat:  # MBR ở phía trên square
            return False
        if self.max_lon < square_min_lon:  # MBR ở bên trái square
            return False
        if self.min_lon > square_max_lon:  # MBR ở bên phải square
            return False
        
        # Nếu không rơi vào các trường hợp trên thì có giao nhau
        return True
    
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
        min_area = float('inf')
        
        for entry_mbr, child_node in node.entries:
            enlarged_mbr = entry_mbr.expand_to_include_mbr(mbr)
            enlargement = enlarged_mbr.area() - entry_mbr.area()
            
            # Chọn theo enlargement nhỏ nhất, nếu bằng thì chọn theo area nhỏ nhất
            if enlargement < min_enlargement or (enlargement == min_enlargement and entry_mbr.area() < min_area):
                min_enlargement = enlargement
                min_area = entry_mbr.area()
                best_entry = child_node
        
        return self._choose_leaf(best_entry, mbr)
    
    def _handle_overflow(self, node: RTreeNode):
        """Xử lý overflow khi node đầy"""
        # Split node
        node1, node2 = self._split_node(node)
        
        if node.parent is None:
            # Node này là root, tạo root mới
            new_root = RTreeNode(is_leaf=False, parent=None)
            new_root.entries.append((node1.mbr, node1))
            new_root.entries.append((node2.mbr, node2))
            new_root.update_mbr()
            node1.parent = new_root
            node2.parent = new_root
            self.root = new_root
        else:
            # Cập nhật parent
            parent = node.parent
            
            # Tìm và xóa entry cũ của node trong parent
            new_entries = []
            for mbr, child in parent.entries:
                if child is not node:
                    new_entries.append((mbr, child))
            parent.entries = new_entries
            
            # Thêm 2 node mới vào parent
            parent.entries.append((node1.mbr, node1))
            parent.entries.append((node2.mbr, node2))
            parent.update_mbr()
            
            # Kiểm tra overflow của parent
            if len(parent.entries) > self.max_entries:
                self._handle_overflow(parent)
    
    def _split_node(self, node: RTreeNode) -> Tuple[RTreeNode, RTreeNode]:
        """Split node sử dụng Linear Split Algorithm"""
        # Linear Pick Seeds
        seed1_idx, seed2_idx = self._linear_pick_seeds(node.entries)
        
        # Tạo 2 node mới với parent giống node cũ
        node1 = RTreeNode(is_leaf=node.is_leaf, parent=node.parent)
        node2 = RTreeNode(is_leaf=node.is_leaf, parent=node.parent)
        
        # Thêm seeds vào 2 node mới
        node1.entries.append(node.entries[seed1_idx])
        node2.entries.append(node.entries[seed2_idx])
        
        # Cập nhật parent pointer cho các child (nếu không phải leaf)
        if not node.is_leaf:
            node.entries[seed1_idx][1].parent = node1
            node.entries[seed2_idx][1].parent = node2
        
        # Phân phối các entry còn lại
        remaining = [e for i, e in enumerate(node.entries) 
                    if i != seed1_idx and i != seed2_idx]
        
        for entry in remaining:
            mbr, data = entry
            
            # Cập nhật MBR trước khi tính toán
            node1.update_mbr()
            node2.update_mbr()
            
            # Tính enlargement cho mỗi node
            enlarged1 = node1.mbr.expand_to_include_mbr(mbr)
            enlarged2 = node2.mbr.expand_to_include_mbr(mbr)
            
            enlargement1 = enlarged1.area() - node1.mbr.area()
            enlargement2 = enlarged2.area() - node2.mbr.area()
            
            # Chọn node để thêm entry
            if enlargement1 < enlargement2:
                target_node = node1
            elif enlargement2 < enlargement1:
                target_node = node2
            else:
                # Nếu enlargement bằng nhau, chọn node có diện tích nhỏ hơn
                if node1.mbr.area() < node2.mbr.area():
                    target_node = node1
                elif node2.mbr.area() < node1.mbr.area():
                    target_node = node2
                else:
                    # Nếu diện tích cũng bằng nhau, chọn node có ít entries hơn
                    target_node = node1 if len(node1.entries) <= len(node2.entries) else node2
            
            target_node.entries.append(entry)
            
            # Cập nhật parent pointer nếu không phải leaf
            if not node.is_leaf:
                data.parent = target_node
        
        # Cập nhật MBR cuối cùng
        node1.update_mbr()
        node2.update_mbr()
        
        return node1, node2
    
    def _linear_pick_seeds(self, entries: List[Tuple[MBR, any]]) -> Tuple[int, int]:
        """Linear Pick Seeds Algorithm - chọn 2 entry xa nhau nhất"""
        max_separation = -float('inf')
        seed1_idx = 0
        seed2_idx = 1 if len(entries) > 1 else 0
        
        # Tìm cặp có separation lớn nhất theo từng chiều
        for dim in ['lat', 'lon']:
            if dim == 'lat':
                # Tìm min của max_lat và max của min_lat
                min_of_max = min(mbr.max_lat for mbr, _ in entries)
                max_of_min = max(mbr.min_lat for mbr, _ in entries)
                
                # Tính width tổng thể
                overall_min = min(mbr.min_lat for mbr, _ in entries)
                overall_max = max(mbr.max_lat for mbr, _ in entries)
                width = overall_max - overall_min
                
                if width > 0:
                    # Tính normalized separation
                    separation = (max_of_min - min_of_max) / width
                    
                    if separation > max_separation:
                        max_separation = separation
                        # Tìm index của entry có max_of_min và min_of_max
                        for i, (mbr, _) in enumerate(entries):
                            if mbr.min_lat == max_of_min:
                                seed1_idx = i
                            if mbr.max_lat == min_of_max:
                                seed2_idx = i
            else:  # lon
                min_of_max = min(mbr.max_lon for mbr, _ in entries)
                max_of_min = max(mbr.min_lon for mbr, _ in entries)
                
                overall_min = min(mbr.min_lon for mbr, _ in entries)
                overall_max = max(mbr.max_lon for mbr, _ in entries)
                width = overall_max - overall_min
                
                if width > 0:
                    separation = (max_of_min - min_of_max) / width
                    
                    if separation > max_separation:
                        max_separation = separation
                        for i, (mbr, _) in enumerate(entries):
                            if mbr.min_lon == max_of_min:
                                seed1_idx = i
                            if mbr.max_lon == min_of_max:
                                seed2_idx = i
        
        # Đảm bảo 2 seeds khác nhau
        if seed1_idx == seed2_idx and len(entries) > 1:
            seed2_idx = (seed1_idx + 1) % len(entries)
        
        return seed1_idx, seed2_idx
    
    def search_square(self, center: Point, radius_km: float) -> List[Tuple[Point, float]]:
        """
        Tìm kiếm các điểm trong hình tròn bán kính radius_km.
        
        Thuật toán:
        1. Tìm tất cả điểm trong hình vuông cạnh 2*radius_km (nhanh)
        2. Lọc lại chỉ lấy các điểm có khoảng cách <= radius_km (chính xác)
        
        Args:
            center: Điểm tâm
            radius_km: Bán kính (km)
            
        Returns:
            List các tuple (Point, distance) được sắp xếp theo khoảng cách
        """
        # Chuyển đổi radius_km sang độ lat/lon (xấp xỉ)
        # 1 độ latitude ≈ 111 km
        # 1 độ longitude ≈ 111 * cos(latitude) km
        half_side_lat = radius_km / 111.0
        half_side_lon = radius_km / (111.0 * math.cos(math.radians(center.lat)))
        
        # Bước 1: Tìm tất cả điểm trong hình vuông
        candidates = []
        self._search_square_recursive(
            self.root, 
            center.lat, 
            center.lon,
            half_side_lat, 
            half_side_lon, 
            center,
            candidates
        )
        
        # Bước 2: Lọc lại chỉ lấy các điểm có khoảng cách <= radius_km
        results = []
        for point, distance in candidates:
            if distance <= radius_km:
                results.append((point, distance))
        
        # Sắp xếp theo khoảng cách
        results.sort(key=lambda x: x[1])
        return results
    
    def _search_square_recursive(self, node: RTreeNode, 
                                 center_lat: float, center_lon: float,
                                 half_side_lat: float, half_side_lon: float,
                                 center_point: Point,
                                 results: List[Tuple[Point, float]]):
        """Tìm kiếm đệ quy trong R-Tree với hình vuông"""
        if not node or not node.mbr:
            return
        
        # Kiểm tra MBR có giao với hình vuông không
        if not node.mbr.intersects_square(center_lat, center_lon, 
                                          half_side_lat, half_side_lon):
            return
        
        if node.is_leaf:
            # Node lá - kiểm tra từng điểm
            square_min_lat = center_lat - half_side_lat
            square_max_lat = center_lat + half_side_lat
            square_min_lon = center_lon - half_side_lon
            square_max_lon = center_lon + half_side_lon
            
            for mbr, point in node.entries:
                # Kiểm tra điểm có nằm trong hình vuông không
                if (square_min_lat <= point.lat <= square_max_lat and
                    square_min_lon <= point.lon <= square_max_lon):
                    distance = center_point.distance_to(point)
                    results.append((point, distance))
        else:
            # Node nội bộ - tìm kiếm đệ quy
            for mbr, child_node in node.entries:
                if child_node is not None:
                    self._search_square_recursive(
                        child_node, 
                        center_lat, 
                        center_lon,
                        half_side_lat, 
                        half_side_lon,
                        center_point,
                        results
                    )
    
    def count_nodes(self) -> dict:
        """Đếm số lượng node trong cây (để debug)"""
        counts = {'leaf': 0, 'internal': 0, 'total_entries': 0}
        self._count_recursive(self.root, counts)
        return counts
    
    def _count_recursive(self, node: RTreeNode, counts: dict):
        """Đếm đệ quy"""
        if node.is_leaf:
            counts['leaf'] += 1
            counts['total_entries'] += len(node.entries)
        else:
            counts['internal'] += 1
            for mbr, child in node.entries:
                self._count_recursive(child, counts)
    
    def get_height(self) -> int:
        """Lấy chiều cao của cây"""
        return self._get_height_recursive(self.root)
    
    def _get_height_recursive(self, node: RTreeNode) -> int:
        """Tính chiều cao đệ quy"""
        if node.is_leaf:
            return 1
        if not node.entries:
            return 1
        return 1 + max(self._get_height_recursive(child) for _, child in node.entries)

def main():
    """Chương trình chính"""
    import argparse
    
    parser = argparse.ArgumentParser(description='R-Tree tìm kiếm trạm xăng (Square Search)')
    parser.add_argument('--file', type=str, required=True, 
                       help='Đường dẫn file JSON chứa dữ liệu trạm xăng')
    parser.add_argument('--max-entries', type=int, default=5, 
                       help='Số lượng tối đa MBR cho mỗi node (N)')
    parser.add_argument('--lat', type=float, 
                       help='Vĩ độ điểm tìm kiếm')
    parser.add_argument('--lon', type=float, 
                       help='Kinh độ điểm tìm kiếm')
    parser.add_argument('--radius', type=float, 
                       help='Bán kính tìm kiếm (km) - sẽ tìm trong hình vuông cạnh 2*radius')
    
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
    
    # Hiển thị thông tin về cây
    counts = rtree.count_nodes()
    height = rtree.get_height()
    print(f"Thông tin cây R-Tree:")
    print(f"  - Chiều cao: {height}")
    print(f"  - Số node lá: {counts['leaf']}")
    print(f"  - Số node nội bộ: {counts['internal']}")
    print(f"  - Tổng số entries trong các node lá: {counts['total_entries']}")
    
    # Tìm kiếm nếu có tham số
    if args.lat is not None and args.lon is not None and args.radius is not None:
        print(f"\nTìm kiếm trạm xăng trong bán kính {args.radius} km")
        print(f"Tâm: ({args.lat}, {args.lon})")
        print(f"(Sử dụng hình vuông để tìm kiếm nhanh, sau đó lọc theo bán kính)")
        
        search_point = Point(args.lat, args.lon, {})
        results = rtree.search_square(search_point, args.radius)
        
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
        print("Thuật toán: Tìm trong hình vuông (nhanh) → Lọc theo bán kính (chính xác)")
        
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
                results = rtree.search_square(search_point, radius)
                
                print(f"\n{'='*80}")
                print(f"Tìm thấy {len(results)} trạm xăng trong bán kính {radius} km:")
                print("="*80)
                
                for i, (point, distance) in enumerate(results, 1):
                    print(f"\n{i}. {point.data['name']} ({point.data['brand']})")
                    print(f"   Địa chỉ: {point.data['display_name']}")
                    print(f"   Khoảng cách: {distance} km")
                    print(f"   Tọa độ: ({point.lat}, {point.lon})")
                
            except ValueError as e:
                print(f"Lỗi: Vui lòng nhập số hợp lệ! ({e})")
            except KeyboardInterrupt:
                print("\n\nĐã hủy bỏ.")
                break
        
        print("\nCảm ơn bạn đã sử dụng!")

if __name__ == "__main__":
    main()