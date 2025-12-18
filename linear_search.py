import math
import time
import json

def distance_km(lat1, lon1, lat2, lon2):
    """
    Tính khoảng cách giữa hai tọa độ (lat1, lon1) và (lat2, lon2) theo km.
    """
    R = 6371.0  # Bán kính Trái đất (km)

    # Chuyển độ sang radian
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Hiệu giữa các toạ độ
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Công thức Haversine
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance



def main():
    import argparse
    parser = argparse.ArgumentParser(description='Linear Search for Gas Stations')
    parser.add_argument('--file', type=str)
    
    args = parser.parse_args()

    file = "db_fix.json"
    if args.file is not None:
        file = args.file

    f = open(file, "r", encoding="utf-8")


    data = json.load(f)

    while True:
        print("="*80)
        lat = float(input("lat = "))
        lon = float(input("lon = "))
        r = float(input("r = "))
        result = []

        start = time.perf_counter()

        for station in data:
            distance = distance_km(lat, lon, station["coordinates"][0], station["coordinates"][1])
            if(distance <= r):
                result.append((station, distance))

        
        #sort result by distance
        result.sort(key=lambda x: x[1])


        
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000
        print(f"Thời gian thực hiện: {elapsed_ms:.3f} ms")

        print(f"Tim thay {len(result)} tram")
        for item in result:
            print("-"*20)
            print(f"Khoang cach den tram: {item[1]}")
            print(item[0])

        


main()