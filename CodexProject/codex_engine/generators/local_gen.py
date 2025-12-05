
import numpy as np
from PIL import Image
import uuid
import math
import random
from codex_engine.config import MAPS_DIR

class LocalGenerator:
    def __init__(self, db_manager):
        self.db = db_manager

    def generate_local_map(self, parent_node, marker, campaign_id):
        print(f"Generating Local Map for {marker['title']}...")
        
        # 1. Load Parent Data
        parent_path = MAPS_DIR / parent_node['metadata']['file_path']
        parent_img = Image.open(parent_path)
        parent_data = np.array(parent_img) / 65535.0
        
        # 2. Extract Chunk (e.g. 40x40 world pixels)
        chunk_size = 40
        cx, cy = int(marker['world_x']), int(marker['world_y'])
        
        x1 = max(0, cx - chunk_size//2)
        y1 = max(0, cy - chunk_size//2)
        x2 = min(parent_data.shape[1], cx + chunk_size//2)
        y2 = min(parent_data.shape[0], cy + chunk_size//2)
        
        chunk = parent_data[y1:y2, x1:x2]
        
        # 3. Upscale to 1024x1024 (Local Resolution)
        target_size = 1024
        chunk_pil = Image.fromarray(chunk)
        upscaled = chunk_pil.resize((target_size, target_size), resample=Image.BICUBIC)
        terrain = np.array(upscaled)
        
        # 4. Add High-Freq Noise (Local Texture)
        noise_layer = np.random.rand(target_size, target_size) * 0.05
        terrain += noise_layer

        # 5. Imprint Vectors (Coordinate Transform)
        vectors = self.db.get_vectors(campaign_id)
        
        # Scales
        scale_x = target_size / (x2 - x1) if (x2-x1) > 0 else 1
        scale_y = target_size / (y2 - y1) if (y2-y1) > 0 else 1

        for vec in vectors:
            points = vec['points']
            width = vec['width'] * scale_x * 0.2
            
            for i in range(len(points)-1):
                p1 = points[i]
                p2 = points[i+1]
                
                # Bounding Box Check
                if not (x1 <= p1[0] <= x2 or x1 <= p2[0] <= x2):
                    if not (y1 <= p1[1] <= y2 or y1 <= p2[1] <= y2):
                        continue
                
                # Transform to local
                lx1, ly1 = (p1[0]-x1)*scale_x, (p1[1]-y1)*scale_y
                lx2, ly2 = (p2[0]-x1)*scale_x, (p2[1]-y1)*scale_y
                
                self._draw_line(terrain, lx1, ly1, lx2, ly2, width, vec['type'])

        # 6. Save
        terrain = np.clip(terrain, 0, 1)
        filename = f"local_{uuid.uuid4()}.png"
        
        uint16_data = (terrain * 65535).astype(np.uint16)
        Image.fromarray(uint16_data, mode='I;16').save(MAPS_DIR / filename)
        
        # 7. Create Node & Update DB
        meta = {
            "file_path": filename,
            "width": target_size,
            "height": target_size,
            "real_min": -50.0, "real_max": 150.0,
            "sea_level": parent_node['metadata'].get('sea_level', 0)
        }
        
        node_id = self.db.create_node(campaign_id, "local_map", parent_node['id'], cx, cy, marker['title'])
        self.db.update_node_data(node_id, geometry={}, metadata=meta)
        
        # 8. Create Placeholder Buildings
        self._populate_placeholders(node_id, marker['symbol'])
        
        return node_id

    def _draw_line(self, terrain, x0, y0, x1, y1, width, vtype):
        dist = math.hypot(x1-x0, y1-y0)
        if dist == 0: return
        steps = int(dist)
        
        for i in range(steps):
            t = i / steps
            x = int(x0 + (x1-x0)*t)
            y = int(y0 + (y1-y0)*t)
            
            r = int(width)
            for dy in range(-r, r+1):
                for dx in range(-r, r+1):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < terrain.shape[1] and 0 <= ny < terrain.shape[0]:
                        if vtype == 'river':
                            terrain[ny, nx] -= 0.1 # Dig
                        elif vtype == 'road':
                            terrain[ny, nx] = terrain[y, x] # Flatten

    def _populate_placeholders(self, node_id, symbol):
        # Add basic entities so the map isn't empty
        for i in range(5):
            wx = random.randint(200, 800)
            wy = random.randint(200, 800)
            self.db.add_marker(node_id, wx, wy, "🏠", f"Building #{i+1}", "Unexplored")
