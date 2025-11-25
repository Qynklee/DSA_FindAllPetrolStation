f = open("db.json", "r", encoding="utf-8")

import json


data = json.load(f)

ward_unique = []
province_unique = []


for item in data:
    if(item["ward"] not in ward_unique):
        ward_unique.append(item["ward"])

    if(item["province"] not in province_unique):
        province_unique.append(item["province"])



print(f"number of ward: {len(ward_unique)}")

print(ward_unique)

print(f"number of province: {len(province_unique)}")

print(province_unique)




for item in data:
    if(item["province"] == None):
        print("*"*80)
        print(f"Detect None in {item}")
        continue
    if("Đường tỉnh" in item["province"]):
        print("="*80)
        print(f"Detect wrong in : {item}")
        display_name = item["display_name"]
        display_name = str(display_name).replace(item["province"], "")
        temp = display_name.split(",")
        for temp2 in temp:
            if("Tỉnh" in temp2 or "Thành phố" in temp2):
                item["province"] = temp2.strip()
                break


        print(f"FIX to: {item}")







        
f2 = open("db_fix.json", "w", encoding="utf-8")
json.dump(data, f2, ensure_ascii=False, indent=4)
f2.close()