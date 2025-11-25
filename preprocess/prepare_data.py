import requests
import json

def get_address_from_coords(lat: float, lon: float):
    # Gọi API
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
    header ={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"}
    response = requests.get(url, headers=header)
    if response.status_code != 200:
        raise Exception("Lỗi khi gọi API.")

    data = response.json()

    # Trích xuất display_name
    display_name = data.get('display_name', '')
    if not display_name:
        raise Exception("Không tìm thấy display_name.")

    # Split bằng dấu phẩy
    parts = [part.strip() for part in display_name.split(',')]

    # Tìm province: phần chứa 'tỉnh' hoặc 'thành phố' (case insensitive)
    province = None
    for part in parts:
        lower_part = part.lower()
        if 'tỉnh' in lower_part or 'thành phố' in lower_part:
            province = part
            break

    # Tìm ward: phần chứa 'xã' hoặc 'phường' (case insensitive)
    ward = None
    for part in parts:
        lower_part = part.lower()
        if 'xã' in lower_part or 'phường' in lower_part:
            ward = part
            break

    # Tạo dict
    result = {
        "province": province,
        "ward": ward,
        "display_name": display_name
    }

    return result



def main():

    # Ví dụ sử dụng
    # coords = "20.8574295,106.6838112"
    # try:
    #     result_json = get_address_from_coords(coords)
    #     print(json.dumps(result_json, ensure_ascii=False, indent=4))
    # except Exception as e:
    #     print(f"Lỗi: {str(e)}")


    #result:

    f2 = open("db.json", "w", encoding="utf-8")
    
    output = []

    try:
        # read geojson
        f = open("export.geojson", "r", encoding="utf-8")
        data = json.load(f)

        gas_stations = data["features"]

        counter = 0

        for i in range(467, len(gas_stations)):

            gas_station = gas_stations[i]

            gas_pos = gas_station["geometry"]["coordinates"][0][0]

            lat = gas_pos[1]
            lon = gas_pos[0]

            print(f"checking {counter}: {lat}, {lon}")

            name = gas_station.get("properties","").get("name", "")
            brand = gas_station.get("properties", "").get("brand", "")
            id = gas_station.get("properties", "").get("@id", "")

            result = get_address_from_coords(lat, lon)

            province = result.get("province", "")
            ward = result.get("ward", "")
            display_name = result.get("display_name", "")

            gas_station_new = {"name": name, "brand": brand, "display_name": display_name,
                                "ward": ward, "province": province, "coordinates":[lat, lon],
                                "id": id
                                }


            output.append(gas_station_new)
            counter += 1
    except Exception as e:
        json.dump(output, f2, ensure_ascii=False, indent=4)
        f2.close()

        
    json.dump(output, f2, ensure_ascii=False, indent=4)
    f2.close()












main()