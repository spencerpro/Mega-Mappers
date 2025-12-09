import json
import random
import os
from codex_engine.config import DATA_DIR

class BuildingGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.bp_path = DATA_DIR / "blueprints"

    def generate(self, parent_node, marker, campaign_id):
        bp_id = marker['metadata'].get('blueprint_id')
        blueprint = self._load_blueprint(bp_id)
        
        if not blueprint:
            print(f"Error: Blueprint {bp_id} missing.")
            return None

        if blueprint.get('type') == 'compound':
            return self._generate_compound(blueprint, parent_node, marker, campaign_id, {})
        else:
            # For single structures, just return the interior node directly (skip yard)
            entries = self._generate_structure(blueprint, parent_node, marker, campaign_id)
            # Return the first node in the registry (usually ground floor)
            return list(entries.values())[0]['node_id'] if entries else None

    def _load_blueprint(self, bp_id):
        for folder in ["structures", "compounds"]:
            path = self.bp_path / folder / f"{bp_id}.json"
            if path.exists():
                with open(path, 'r') as f: return json.load(f)
        return None

    def _resolve_dim(self, dim_data):
        if isinstance(dim_data, int): return dim_data
        return random.randint(dim_data['min'], dim_data['max'])

    def _structure_to_compound(self, structure_bp):
        """Convert a single structure blueprint into a compound with one building."""
        # Resolve dimensions
        w = self._resolve_dim(structure_bp['dimensions']['width'])
        h = self._resolve_dim(structure_bp['dimensions']['height'])
        
        # Add padding around the building
        padding = 5
        plot_w = w + (padding * 2)
        plot_h = h + (padding * 2)
        
        return {
            "id": f"{structure_bp['id']}_compound",
            "type": "compound",
            "name": structure_bp['name'],
            "plot_size": {
                "width": plot_w,
                "height": plot_h
            },
            "components": [
                {
                    "blueprint_id": structure_bp['id'],
                    "offset": {"x": padding, "y": padding},
                    "connections": [
                        {"entry_key": entry['key']} 
                        for entry in structure_bp.get('external_entries', [])
                    ]
                }
            ]
        }

    def _generate_compound(self, bp, parent_node, marker, campaign_id, bp_cache=None):
        """Generate a compound with multiple buildings on a shared yard.
        
        Args:
            bp_cache: Optional dict of {blueprint_id: blueprint_data} to avoid re-loading
        """
        if bp_cache is None:
            bp_cache = {}
            
        print(f"=== GENERATING COMPOUND: {bp.get('name')} ===")
        
        # 1. Generate the Yard (Parent Node)
        w, h = self._resolve_dim(bp['plot_size']['width']), self._resolve_dim(bp['plot_size']['height'])
        
        yard_id = self.db.create_node(
            campaign_id, "tactical_map", parent_node['id'],
            marker['world_x'], marker['world_y'], bp['name']
        )
        # Will be updated after placing buildings
        yard_grid = [[0]*w for _ in range(h)]

        # 2. Place Components
        for comp in bp['components']:
            # Try cache first, then load from disk
            sub_bp = bp_cache.get(comp['blueprint_id']) or self._load_blueprint(comp['blueprint_id'])
            
            if not sub_bp:
                print(f"ERROR: Could not load blueprint {comp['blueprint_id']}")
                continue
            
            print(f"Found blueprint: {sub_bp['name']}, dimensions: {sub_bp['dimensions']}")
            
            # Resolve building dimensions
            bw = self._resolve_dim(sub_bp['dimensions']['width'])
            bh = self._resolve_dim(sub_bp['dimensions']['height'])
            
            print(f"Drawing building: {sub_bp['name']} at offset ({comp['offset']['x']}, {comp['offset']['y']}) with size {bw}x{bh}")
            print(f"Yard grid size: {w}x{h}")
            
            # Draw building footprint onto yard grid
            ox, oy = comp['offset']['x'], comp['offset']['y']
            for by in range(bh):
                for bx in range(bw):
                    grid_y = oy + by
                    grid_x = ox + bx
                    if 0 <= grid_y < h and 0 <= grid_x < w:
                        # Draw walls on perimeter, floor inside
                        if bx == 0 or bx == bw-1 or by == 0 or by == bh-1:
                            yard_grid[grid_y][grid_x] = 2  # Wall
                        else:
                            yard_grid[grid_y][grid_x] = 1  # Floor
            
            print(f"Building drawn. Sample yard_grid[{oy}][{ox}] = {yard_grid[oy][ox]}")
            
            # Generate the building's floors (Children of the Yard)
            entry_data = self._generate_structure(
                sub_bp, self.db.get_node(yard_id), 
                {"world_x": comp['offset']['x'], "world_y": comp['offset']['y'], "title": sub_bp['name']}, 
                campaign_id
            )

            # 3. Link Doors
            for conn in comp.get('connections', []):
                key = conn['entry_key']
                data = entry_data.get(key) # Contains node_id, local_x, local_y
                
                if data:
                    print(f"Connecting door: key={key}, interior coords=({data['local_x']}, {data['local_y']}), node={data['node_id']}")
                    
                    # Door coordinates on the building's footprint (not interior coords)
                    # We need to recalculate the door position on the yard grid
                    entry_def = next((e for e in sub_bp.get('external_entries', []) if e['key'] == key), None)
                    if entry_def:
                        door_x, door_y = self._calculate_entry_coords(bw, bh, entry_def)
                        # Apply component offset to get yard coordinates
                        yx = comp['offset']['x'] + door_x
                        yy = comp['offset']['y'] + door_y
                        
                        print(f"Placing door on yard at ({yx}, {yy})")
                        
                        # Marker in Yard -> To House Interior
                        self.db.add_marker(yard_id, yx, yy, "door", f"Enter {sub_bp['name']}", "", metadata={"portal_to": data['node_id']})
                        # Marker in House Interior -> Back to Yard
                        self.db.add_marker(data['node_id'], data['local_x'], data['local_y'], "door_out", "Exit to Yard", "", metadata={"portal_to": yard_id})

        # Update yard with final grid showing all buildings
        print(f"Updating yard node {yard_id} with grid {w}x{h}")
        print(f"Grid sample: {yard_grid[0][:10]}")  # Show first 10 tiles of first row
        self.db.update_node_data(yard_id, geometry={"grid": yard_grid, "width": w, "height": h})
        
        return yard_id

    def _generate_structure(self, bp, parent_node, marker, campaign_id):
        # 1. Dimensions
        w = self._resolve_dim(bp['dimensions']['width'])
        h = self._resolve_dim(bp['dimensions']['height'])
        
        # 2. Dynamic Map Size (Padding + Min Size)
        PADDING = 20
        MIN_SIZE = 60
        map_w = max(MIN_SIZE, w + (PADDING * 2))
        map_h = max(MIN_SIZE, h + (PADDING * 2))
        
        # 3. Center Offset
        off_x = (map_w - w) // 2
        off_y = (map_h - h) // 2
        
        floor_nodes = {}
        entry_registry = {}

        # 4. Generate Floors
        for floor in bp['floors']:
            node_id = self.db.create_node(
                campaign_id, "building_interior", parent_node['id'],
                marker['world_x'], marker['world_y'], f"{bp['name']} ({floor['name']})"
            )
            
            # PURE FLOOR GRID (No Walls in the grid data)
            grid = [[1 for _ in range(map_w)] for _ in range(map_h)]
            
            # Define the Footprint (Metadata for drawing the blue line)
            footprints = [{
                "x": off_x, "y": off_y, 
                "w": w, "h": h, 
                "color": "blue"
            }]
            
            # Save grid AND footprints
            self.db.update_node_data(node_id, geometry={
                "grid": grid, 
                "width": map_w, 
                "height": map_h,
                "footprints": footprints
            })
            
            floor_nodes[floor['id']] = node_id

        # 5. Internal Stairs
        for link in bp.get('internal_links', []):
            f_a, f_b = floor_nodes.get(link['from']), floor_nodes.get(link['to'])
            if f_a and f_b:
                sx, sy = off_x + (w // 2), off_y + (h // 2)
                self.db.add_marker(f_a, sx, sy, "stairs_up", "Stairs", "", metadata={"portal_to": f_b})
                self.db.add_marker(f_b, sx, sy, "stairs_down", "Stairs", "", metadata={"portal_to": f_a})

        # 6. Entries
        for entry in bp.get('external_entries', []):
            fid = entry['floor_id']
            nid = floor_nodes.get(fid)
            if nid:
                lx, ly = self._calculate_entry_coords(w, h, entry)
                entry_registry[entry['key']] = {
                    "node_id": nid, 
                    "local_x": lx + off_x, 
                    "local_y": ly + off_y
                }

        return entry_registry

    def _generate_structure_old(self, bp, parent_node, marker, campaign_id):
        from PIL import Image, ImageDraw
        import os
        
        # Resolve dimensions once per structure
        w = self._resolve_dim(bp['dimensions']['width'])
        h = self._resolve_dim(bp['dimensions']['height'])
        
        # --- DYNAMIC MAP SIZING ---
        PADDING = 20  # Tiles of open space around the building
        MIN_SIZE = 60 # Minimum map dimensions to fill screen
        
        map_w = max(MIN_SIZE, w + (PADDING * 2))
        map_h = max(MIN_SIZE, h + (PADDING * 2))
        
        # Calculate Offset to center structure
        off_x = (map_w - w) // 2
        off_y = (map_h - h) // 2
        
        # Pixel scale
        TILE_SIZE = 40
        img_width = map_w * TILE_SIZE
        img_height = map_h * TILE_SIZE
        
        floor_nodes = {}
        entry_registry = {}

        # 1. Generate Floors
        for floor in bp['floors']:
            node_id = self.db.create_node(
                campaign_id, "building_interior", parent_node['id'],
                marker['world_x'], marker['world_y'], f"{bp['name']} ({floor['name']})"
            )
            
            # CREATE THE FUCKING IMAGE
            img = Image.new('RGB', (img_width, img_height), color='tan')
            draw = ImageDraw.Draw(img)
            
            # DRAW THE FUCKING GRID LINES
            for x in range(0, img_width, TILE_SIZE):
                draw.line([(x, 0), (x, img_height)], fill='black', width=1)
            for y in range(0, img_height, TILE_SIZE):
                draw.line([(0, y), (img_width, y)], fill='black', width=1)
            
            # Draw building walls as blue rectangle
            building_x = off_x * TILE_SIZE
            building_y = off_y * TILE_SIZE
            building_w = w * TILE_SIZE
            building_h = h * TILE_SIZE
            
            # Draw blue outline (walls)
            draw.rectangle(
                [building_x, building_y, building_x + building_w, building_y + building_h],
                outline='blue',
                width=5
            )
            
            # Save the image
            img_dir = DATA_DIR / "map_images"
            os.makedirs(img_dir, exist_ok=True)
            img_path = img_dir / f"node_{node_id}.png"
            img.save(img_path)
            
            # Save reference to image
            self.db.update_node_data(node_id, geometry={"image": f"node_{node_id}.png", "width": map_w, "height": map_h})
            floor_nodes[floor['id']] = node_id

        # 2. Internal Stairs (Centered in Structure)
        for link in bp.get('internal_links', []):
            f_a, f_b = floor_nodes.get(link['from']), floor_nodes.get(link['to'])
            if f_a and f_b:
                sx, sy = off_x + (w // 2), off_y + (h // 2)
                self.db.add_marker(f_a, sx, sy, "stairs_up", "Stairs", "", metadata={"portal_to": f_b})
                self.db.add_marker(f_b, sx, sy, "stairs_down", "Stairs", "", metadata={"portal_to": f_a})

        # 3. Register Entries
        for entry in bp.get('external_entries', []):
            fid = entry['floor_id']
            nid = floor_nodes.get(fid)
            if nid:
                lx, ly = self._calculate_entry_coords(w, h, entry)
                
                # Apply Offset
                final_x = lx + off_x
                final_y = ly + off_y
                
                entry_registry[entry['key']] = {"node_id": nid, "local_x": final_x, "local_y": final_y}

        return entry_registry

    def _generate_structure_old(self, bp, parent_node, marker, campaign_id):
        # Resolve dimensions once per structure
        w = self._resolve_dim(bp['dimensions']['width'])
        h = self._resolve_dim(bp['dimensions']['height'])
        
        floor_nodes = {}
        entry_registry = {}

        # 1. Generate Floors
        for floor in bp['floors']:
            node_id = self.db.create_node(
                campaign_id, "building_interior", parent_node['id'],
                marker['world_x'], marker['world_y'], f"{bp['name']} ({floor['name']})"
            )
            # Basic Box Room Generation
            grid = [[1 for _ in range(w)] for _ in range(h)]
            # Add simple walls perimeter
            for y in range(h):
                for x in range(w):
                    if x==0 or x==w-1 or y==0 or y==h-1: grid[y][x] = 2
            
            self.db.update_node_data(node_id, geometry={"grid": grid, "width": w, "height": h})
            floor_nodes[floor['id']] = node_id

        # 2. Internal Stairs
        for link in bp.get('internal_links', []):
            f_a, f_b = floor_nodes.get(link['from']), floor_nodes.get(link['to'])
            if f_a and f_b:
                self.db.add_marker(f_a, w//2, h//2, "stairs_up", "Stairs", "", metadata={"portal_to": f_b})
                self.db.add_marker(f_b, w//2, h//2, "stairs_down", "Stairs", "", metadata={"portal_to": f_a})

        # 3. Register Entries for Compound use
        for entry in bp.get('external_entries', []):
            fid = entry['floor_id']
            nid = floor_nodes.get(fid)
            if nid:
                # Resolve dynamic position (e.g. "south", "center")
                lx, ly = self._calculate_entry_coords(w, h, entry)
                entry_registry[entry['key']] = {"node_id": nid, "local_x": lx, "local_y": ly}

        return entry_registry

    def _calculate_entry_coords(self, w, h, entry_def):
        wall = entry_def.get('wall', 'south')
        align = entry_def.get('align', 'center')
        val = 0
        
        if wall in ['north', 'south']:
            limit = w
            val = w // 2 if align == 'center' else int(align)
            return (val, 0) if wall == 'north' else (val, h-1)
        else:
            limit = h
            val = h // 2 if align == 'center' else int(align)
            return (0, val) if wall == 'west' else (w-1, val)

# Add this to the bottom of codex_engine/generators/building_gen.py

def get_available_blueprints():
    """
    Scans the data/blueprints directory and returns a list of available options.
    Returns: [{'id': 'cottage_small', 'name': 'Small Cottage', 'type': 'structure'}, ...]
    """
    options = []
    base = DATA_DIR / "blueprints"
    
    for category in ["structures", "compounds"]:
        path = base / category
        if path.exists():
            for f in path.glob("*.json"):
                try:
                    with open(f, 'r') as fp:
                        data = json.load(fp)
                        options.append({
                            "id": data.get("id", f.stem),
                            "name": data.get("name", f.stem),
                            "type": category
                        })
                except:
                    continue
    # Sort by type then name
    options.sort(key=lambda x: (x['type'], x['name']))
    return options
