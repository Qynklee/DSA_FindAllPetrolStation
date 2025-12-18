import json
import random

# Assume the input file name is 'input.json'. Replace with the actual file name if different.
input_file = 'db_fix.json'
output_file = 'db_random.json'

# Read the existing data from the JSON file
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extract min and max coordinates for random generation
if data:
    lats = [point['coordinates'][0] for point in data]
    lons = [point['coordinates'][1] for point in data]
    min_lat = min(lats)
    max_lat = max(lats)
    min_lon = min(lons)
    max_lon = max(lons)
else:
    raise ValueError("No data in the input file to determine coordinate bounds.")

# Track used coordinates to avoid duplicates (including originals)
used_coords = set(tuple(point['coordinates']) for point in data)

# Prompt user for the number of random points
num_random = int(input("Enter the number of random points to generate: "))

# Generate random points
new_points = []
for _ in range(num_random):
    while True:
        # Generate random coordinates within the bounds
        rand_lat = random.uniform(min_lat, max_lat)
        rand_lon = random.uniform(min_lon, max_lon)
        rand_coord = (rand_lat, rand_lon)
        
        # Check if unique
        if rand_coord not in used_coords:
            used_coords.add(rand_coord)
            break
    
    # Select a random original point to base the new one on
    original = random.choice(data)
    
    # Create new point with [RAND] prefixed to specified fields
    new_point = {
        "name": "[RAND]" + original["name"],
        "brand": "[RAND]" + original["brand"],
        "display_name": "[RAND]" + original["display_name"],
        "ward": "[RAND]" + original["ward"],
        "province": "[RAND]" + original["province"],
        "coordinates": [rand_lat, rand_lon],
        "id": "[RAND]" + original["id"]  # Also prefix id for consistency
    }
    
    new_points.append(new_point)

# Combine original and new points
all_points = data + new_points

# Write to output JSON file
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(all_points, f, indent=4, ensure_ascii=False)

print(f"Generated {num_random} random points and saved total data to {output_file}")