import numpy as np
from PIL import Image
import uuid
import math
import random
from codex_engine.config import MAPS_DIR
from codex_engine.utils.noise import SimpleNoise

# --- CONSTANTS ---
BUILDING_TYPES = {
    "inn": {"icon": "🏨", "near": "road"},
    "tavern": {"icon": "🍺", "near": "road"},
    "temple": {"icon": "⛪", "near": "center"},
    "market": {"icon": "🪙", "near": "center"},
    "house": {"icon": "🏠", "near": "road"},
    "mill": {"icon": "⚙️", "near": "water"},
    "dock": {"icon": "⚓", "near": "water"},
    "smithy": {"icon": "🔨", "near": "road"},
    "stable": {"icon": "🐴", "near": "outskirts"},
    "farm": {"icon": "🌾", "near": "outskirts"},
    "well": {"icon": "🪣", "near": "center"},
    "chapel": {"icon": "✝️", "near": "center"},
}

PREFIXES = ["Old", "Ye", "The", "Green", "Red", "Golden", "Silver", "Bronze", "Stone", "Oak"]
SUFFIXES = ["Dragon", "Griffin", "Rose", "Crown", "Shield", "Sword", "Barrel", "Wheel", "Anchor", "Star"]
PROFESSIONS = ["Thatcher", "Cooper", "Wright", "Smith", "Miller", "Fisher", "Baker", "Chandler"]
FIRST_NAMES = ["Tom", "Mary", "John", "Sarah", "William", "Emma", "James", "Alice", "Robert", "Margaret"]

def generate_building_name(building_type):
    if building_type in ["inn", "tavern"]:
        return f"{random.choice(['The', 'Ye Olde'])} {random.choice(PREFIXES)} {random.choice(SUFFIXES)}"
    elif building_type == "house":
        return f"{random.choice(FIRST_NAMES)} {random.choice(PROFESSIONS)}'s Cottage"
    elif building_type == "smithy":
        return f"{random.choice(FIRST_NAMES)}'s Smithy"
    elif building_type == "mill":
        return f"{random.choice(['Water', 'Wind', 'Stone'])} Mill"
    elif building_type in ["temple", "chapel"]:
        return f"Chapel of {random.choice(['St. Cuthbert', 'the Light', 'Mercy', 'the Dawn'])}"
    elif building_type == "market":
        return "Market Square"
    elif building_type == "well":
        return "Village Well"
    elif building_type == "dock":
        return f"{random.choice(FIRST_NAMES)}'s Dock"
    elif building_type == "stable":
        return f"{random.choice(FIRST_NAMES)}'s Stables"
    elif building_type == "farm":
        return f"{random.choice(FIRST_NAMES)} Family Farm"
    return f"{building_type.title()}"

class LocalGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.noise = SimpleNoise()

    def generate_local_map(self, parent_node, marker, campaign_id):
        print(f"--- FRACTAL ZOOM: Generating {marker['title']} ---")
        
        # 1. LOAD PARENT
        parent_path = MAPS_DIR / parent_node['metadata']['file_path']
        parent_img = Image.open(parent_path)
        parent_data = np.array(parent_img) / 65535.0
        
        chunk_size_world_pixels = 30 
        cx, cy = int(marker['world_x']), int(marker['world_y'])
        
        x1 = max(0, cx - chunk_size_world_pixels//2)
        y1 = max(0, cy - chunk_size_world_pixels//2)
        x2 = min(parent_data.shape[1], cx + chunk_size_world_pixels//2)
        y2 = min(parent_data.shape[0], cy + chunk_size_world_pixels//2)
        
        chunk = parent_data[y1:y2, x1:x2]
        
        # 2. CALCULATE ACTUAL HEIGHT RANGE OF CHUNK
        # Get parent's real height range to map the chunk values
        parent_real_min = parent_node['metadata'].get('real_min', -11000.0)
        parent_real_max = parent_node['metadata'].get('real_max', 9000.0)
        parent_range = parent_real_max - parent_real_min
        
        # Calculate actual min/max heights in the extracted chunk
        chunk_min = chunk.min()
        chunk_max = chunk.max()
        
        # Map chunk's normalized values to real-world heights
        chunk_real_min = parent_real_min + (chunk_min * parent_range)
        chunk_real_max = parent_real_min + (chunk_max * parent_range)
        chunk_real_range = chunk_real_max - chunk_real_min
        
        print(f"  Chunk height range: {chunk_real_min:.1f}m to {chunk_real_max:.1f}m (span: {chunk_real_range:.1f}m)")
        
        # 3. UPSCALE
        target_size = 1024
        chunk_pil = Image.fromarray(chunk)
        upscaled = chunk_pil.resize((target_size, target_size), resample=Image.BICUBIC)
        terrain = np.array(upscaled)
        
        # 4. DETAIL NOISE (add variation within the local range)
        for y in range(target_size):
            for x in range(target_size):
                n = self.noise.get_octave_noise(x/100.0, y/100.0, octaves=4)
                # Scale noise to be proportional to local height range
                noise_amplitude = 0.02  # 2% of local range
                terrain[y, x] += n * noise_amplitude
        
        # 5. INHERIT WORLD VECTORS
        parent_vectors = self.db.get_vectors(parent_node['id'])
        
        width_px = max(1, x2 - x1)
        height_px = max(1, y2 - y1)
        scale_x = target_size / width_px
        scale_y = target_size / height_px

        sea_level = parent_node['metadata'].get('sea_level', 0)
        local_vectors = []

        for vec in parent_vectors:
            points = vec['points']
            local_points = []
            intersects = False
            
            for i in range(len(points)-1):
                px, py = points[i]
                if (x1 - 5 <= px <= x2 + 5) and (y1 - 5 <= py <= y2 + 5):
                    intersects = True
                
                lx = (px - x1) * scale_x
                ly = (py - y1) * scale_y
                local_points.append((lx, ly))
            
            if points:
                lx = (points[-1][0] - x1) * scale_x
                ly = (points[-1][1] - y1) * scale_y
                local_points.append((lx, ly))

            if intersects and len(local_points) > 1:
                zoom_factor = scale_x
                base_width = vec['width'] 
                
                if vec['type'] == 'river':
                    imprint_width = max(60, base_width * zoom_factor * 0.5)
                else:
                    imprint_width = max(30, base_width * zoom_factor * 0.3)

                self._imprint_vector(terrain, local_points, imprint_width, vec['type'], sea_level, 
                                   parent_real_min, parent_range)
                
                local_vectors.append({
                    "type": vec['type'],
                    "points": local_points,
                    "width": int(imprint_width)
                })

        # 6. SAVE
        terrain = np.clip(terrain, 0, 1)
        
        # Calculate final height range after all modifications
        terrain_min = terrain.min()
        terrain_max = terrain.max()
        final_real_min = parent_real_min + (terrain_min * parent_range)
        final_real_max = parent_real_min + (terrain_max * parent_range)
        
        print(f"  Final height range: {final_real_min:.1f}m to {final_real_max:.1f}m")
        
        filename = f"local_{uuid.uuid4()}.png"
        uint16_data = (terrain * 65535).astype(np.uint16)
        Image.fromarray(uint16_data, mode='I;16').save(MAPS_DIR / filename)
        
        # 7. UPDATE DB WITH ACTUAL LOCAL HEIGHT RANGE
        meta = {
            "file_path": filename,
            "width": target_size,
            "height": target_size,
            # USE ACTUAL LOCAL HEIGHT RANGE, NOT GLOBAL
            "real_min": float(final_real_min),
            "real_max": float(final_real_max),
            "sea_level": sea_level
        }
        
        map_name = f"{marker['title']} (Local)"
        new_node_id = self.db.create_node(campaign_id, "local_map", parent_node['id'], cx, cy, map_name)
        self.db.update_node_data(new_node_id, geometry={}, metadata=meta)
        
        # 8. SAVE VECTORS
        for lv in local_vectors:
            self.db.save_vector(new_node_id, lv['type'], lv['points'], lv['width'])

        # 9. POPULATE
        if "Village" in marker['title'] or "Town" in marker['title'] or "City" in marker['title'] or "🏰" in marker['symbol']:
            self._populate_village(new_node_id, target_size, local_vectors)
        elif "Dungeon" in marker['title'] or "Cave" in marker['title'] or "💀" in marker['symbol']:
            self._populate_dungeon_entrance(new_node_id, target_size)
        
        return new_node_id

    def _imprint_vector(self, terrain, points, width, vtype, sea_level, parent_real_min, parent_range):
        h, w = terrain.shape
        
        # Convert sea_level to normalized value in parent's coordinate system
        sea_level_normalized = (sea_level - parent_real_min) / parent_range
        
        for i in range(len(points)-1):
            x0, y0 = points[i]
            x1, y1 = points[i+1]
            dist = math.hypot(x1-x0, y1-y0)
            if dist == 0: continue
            steps = int(dist)
            
            for s in range(steps):
                t = s / steps
                cx = int(x0 + (x1-x0)*t)
                cy = int(y0 + (y1-y0)*t)
                
                # CLAMP
                cx = max(0, min(w - 1, cx))
                cy = max(0, min(h - 1, cy))
                
                r = int(width / 2)
                for dy in range(-r, r+1):
                    for dx in range(-r, r+1):
                        nx, ny = cx+dx, cy+dy
                        
                        if 0 <= nx < w and 0 <= ny < h:
                            if dx*dx + dy*dy <= r*r:
                                if vtype == 'river':
                                    # Calculate depth in normalized space
                                    dist_from_center = math.sqrt(dx*dx + dy*dy) / r
                                    depth_normalized = 0.02 * (1.0 - dist_from_center)
                                    # Force below sea level in normalized space
                                    target_h = sea_level_normalized - 0.002 - depth_normalized
                                    terrain[ny, nx] = min(terrain[ny, nx], target_h)
                                    
                                elif vtype == 'road':
                                    center_h = terrain[cy, cx]
                                    terrain[ny, nx] = center_h

    def _populate_village(self, node_id, size, local_vectors):
        print("Populating Village with Content...")
        
        road_points = []
        water_points = []
        
        for vec in local_vectors:
            if vec['type'] == 'road':
                road_points.extend(vec['points'][::20]) 
            elif vec['type'] == 'river':
                water_points.extend(vec['points'][::20])
        
        center_x, center_y = size // 2, size // 2
        
        building_queue = [
            ("inn", "road"), ("tavern", "road"), ("temple", "center"),
            ("market", "center"), ("well", "center")
        ]
        
        if water_points:
            building_queue.append(("mill", "water"))
            building_queue.append(("dock", "water"))
            
        building_queue.extend([("smithy", "road"), ("chapel", "center")])
        for _ in range(8): building_queue.append(("house", "road"))
        building_queue.extend([("stable", "outskirts"), ("farm", "outskirts")])
        
        placed_buildings = []

        for b_type, preference in building_queue:
            candidate_list = []
            
            if preference == "road" and road_points:
                candidate_list = road_points
            elif preference == "water" and water_points:
                candidate_list = water_points
            elif preference == "outskirts":
                for _ in range(5):
                    ang = random.uniform(0, 6.28)
                    dist = random.uniform(size * 0.3, size * 0.45)
                    candidate_list.append((center_x + math.cos(ang)*dist, center_y + math.sin(ang)*dist))
            else: 
                candidate_list = [(center_x, center_y)]

            if not candidate_list: candidate_list = [(center_x, center_y)]

            placed = False
            attempts = 0
            while not placed and attempts < 10:
                base_x, base_y = random.choice(candidate_list)
                
                jitter = 60
                px = base_x + random.uniform(-jitter, jitter)
                py = base_y + random.uniform(-jitter, jitter)
                
                if not (0 <= px < size and 0 <= py < size):
                    attempts += 1
                    continue

                collision = False
                for bx, by in placed_buildings:
                    if math.hypot(px-bx, py-by) < 40: 
                        collision = True
                        break
                
                if not collision:
                    b_data = BUILDING_TYPES.get(b_type, BUILDING_TYPES["house"])
                    name = generate_building_name(b_type)
                    self.db.add_marker(node_id, px, py, b_data['icon'], name, f"A {b_type}.")
                    placed_buildings.append((px, py))
                    placed = True
                
                attempts += 1

    def _populate_dungeon_entrance(self, node_id, size):
        print("Populating Dungeon...")
        center = size // 2
        self.db.add_marker(node_id, center, center, "💀", "The Entrance", "Beware")
        for _ in range(3):
            ox = random.randint(-100, 100)
            oy = random.randint(-100, 100)
            self.db.add_marker(node_id, center+ox, center+oy, "🔥", "Campfire", "Signs of life.")
