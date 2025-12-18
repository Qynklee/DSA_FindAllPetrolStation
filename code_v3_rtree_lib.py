import json
import math
from rtree import index

def haversine_distance(lat1, lon1, lat2, lon2):
    """Tính khoảng cách giữa 2 điểm theo công thức Haversine (km)"""
    R = 6371  # Bán kính trái đất (km)
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def lat_lon_to_meters(lat, lon, distance_km):
    """Chuyển đổi khoảng cách km sang độ lat/lon gần đúng"""
    # 1 độ latitude ≈ 111 km
    # 1 độ longitude phụ thuộc vào latitude
    lat_offset = distance_km / 111.0
    lon_offset = distance_km / (111.0 * math.cos(math.radians(lat)))
    return lat_offset, lon_offset

def get_tree_stats(idx, properties):
    """Lấy thông tin thống kê về cây R-Tree"""
    stats = idx.get_bounds()
    
    # Đếm số lượng entries
    total_entries = sum(1 for _ in idx.intersection(idx.get_bounds(), objects=True))
    
    return {
        'bounds': stats,
        'total_entries': total_entries,
        'properties': properties
    }

def main():
    # Đọc dữ liệu từ file JSON
    print("Đang đọc dữ liệu từ file db_fix.json...")
    try:
        with open('db_fix.json', 'r', encoding='utf-8') as f:
            gas_stations = json.load(f)
        print(f"Đã đọc thành công {len(gas_stations)} trạm xăng")
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file db_fix.json")
        return
    except json.JSONDecodeError:
        print("Lỗi: File JSON không hợp lệ")
        return
    
    # Nhập giá trị M (số lượng tối đa MBR cho mỗi node)
    while True:
        try:
            M = int(input("\nNhập giá trị M (số lượng tối đa MBR cho mỗi node): "))
            if M > 0:
                break
            print("M phải là số nguyên dương!")
        except ValueError:
            print("Vui lòng nhập một số nguyên hợp lệ!")
    
    # Tạo R-Tree với properties tùy chỉnh
    print(f"\nĐang tạo R-Tree với M = {M}...")
    p = index.Property()
    p.leaf_capacity = M
    p.index_capacity = M  # Capacity cho node nội bộ phải bằng leaf_capacity
    p.fill_factor = 0.7
    p.near_minimum_overlap_factor = min(M // 2, 32)  # Phải nhỏ hơn capacity
    
    idx = index.Index(properties=p)
    
    # Thêm các trạm xăng vào R-Tree
    for i, station in enumerate(gas_stations):
        lat, lon = station['coordinates']
        # R-Tree sử dụng (minx, miny, maxx, maxy)
        # Với điểm, minx=maxx và miny=maxy
        idx.insert(i, (lon, lat, lon, lat), obj=station)
    
    # Thống kê cây R-Tree
    print("\n" + "="*60)
    print("THÔNG TIN CÂY R-TREE")
    print("="*60)
    
    stats = get_tree_stats(idx, p)
    print(f"Tổng số trạm xăng: {stats['total_entries']}")
    print(f"Leaf capacity (M): {M}")
    print(f"Fill factor: {p.fill_factor}")
    
    # Lưu ý: rtree không cung cấp API trực tiếp để đếm số node lá và node nội bộ
    # Thông tin này phụ thuộc vào implementation bên trong
    print(f"\nLưu ý: Thư viện rtree không cung cấp API để truy xuất")
    print(f"chi tiết về chiều cao cây, số node lá và node nội bộ.")
    print(f"Các thông tin này được quản lý nội bộ bởi libspatialindex.")
    
    # Vòng lặp tìm kiếm
    print("\n" + "="*60)
    print("BẮT ĐẦU TÌM KIẾM TRẠM XĂNG")
    print("="*60)
    
    while True:
        print("\n" + "-"*60)
        try:
            # Nhập toạ độ
            lat_input = input("Nhập latitude (hoặc 'q' để thoát): ").strip()
            if lat_input.lower() == 'q':
                print("Kết thúc chương trình!")
                break
            
            lat = float(lat_input)
            lon = float(input("Nhập longitude: ").strip())
            
            # Nhập khoảng cách
            n = float(input("Nhập khoảng cách n (km): ").strip())
            
            if n <= 0:
                print("Khoảng cách phải lớn hơn 0!")
                continue
            
            # Tính bounding box cho hình vuông cạnh 2n
            lat_offset, lon_offset = lat_lon_to_meters(lat, lon, n)
            
            min_lat = lat - lat_offset
            max_lat = lat + lat_offset
            min_lon = lon - lon_offset
            max_lon = lon + lon_offset
            
            # Tìm kiếm trong R-Tree (bounding box)
            print(f"\nĐang tìm kiếm trong vùng hình vuông cạnh {2*n} km...")
            candidates = list(idx.intersection((min_lon, min_lat, max_lon, max_lat), objects=True))
            
            print(f"Tìm thấy {len(candidates)} trạm xăng ứng viên trong vùng")
            
            # Lọc theo khoảng cách thực tế
            results = []
            for item in candidates:
                station = item.object
                st_lat, st_lon = station['coordinates']
                distance = haversine_distance(lat, lon, st_lat, st_lon)
                
                if distance <= n:
                    results.append({
                        'station': station,
                        'distance': distance
                    })
            
            # Sắp xếp theo khoảng cách
            results.sort(key=lambda x: x['distance'])
            
            # In kết quả
            print(f"\n{'='*60}")
            print(f"KẾT QUẢ: Tìm thấy {len(results)} trạm xăng trong bán kính {n} km")
            print(f"{'='*60}")
            
            if results:
                for i, result in enumerate(results, 1):
                    station = result['station']
                    dist = result['distance']
                    print(f"\n{i}. {station['name']}")
                    print(f"   Thương hiệu: {station.get('brand', 'N/A')}")
                    print(f"   Địa chỉ: {station.get('display_name', 'N/A')}")
                    print(f"   Phường/Xã: {station.get('ward', 'N/A')}")
                    print(f"   Tỉnh/Thành: {station.get('province', 'N/A')}")
                    print(f"   Toạ độ: {station['coordinates']}")
                    print(f"   Khoảng cách: {dist:.2f} km")
            else:
                print("Không tìm thấy trạm xăng nào trong khoảng cách này.")
            
        except ValueError:
            print("Lỗi: Vui lòng nhập số hợp lệ!")
        except KeyboardInterrupt:
            print("\n\nKết thúc chương trình!")
            break
        except Exception as e:
            print(f"Lỗi: {e}")

if __name__ == "__main__":
    main()