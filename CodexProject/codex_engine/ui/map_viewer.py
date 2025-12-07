import pygame
import math
import json
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT
from codex_engine.ui.renderers.image_strategy import ImageMapStrategy
from codex_engine.ui.widgets import Slider, Button
from codex_engine.ui.editors import NativeMarkerEditor

from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.village_manager import VillageContentManager

from codex_engine.core.db_manager import DBManager
from codex_engine.core.ai_manager import AIManager

# --- COLORS ---
COLOR_ROAD = (160, 82, 45)
COLOR_RIVER = (80, 120, 255)

class MapViewer:
    def __init__(self, screen, theme_manager):
        self.screen = screen
        self.theme = theme_manager
        
        # View State
        self.cam_x, self.cam_y, self.zoom = 0, 0, 1.0
        self.show_grid, self.grid_type, self.grid_size = True, "HEX", 64
        
        self.current_node = None
        self.render_strategy = None
        
        # Interaction State
        self.markers = []
        self.selected_marker = None
        self.dragging_marker = None
        self.drag_offset = (0,0)
        self.hovered_marker = None
        self.active_modal = None
        self.pending_click_pos = None
        
        # Vector State
        self.vectors = []
        self.active_vector = None 
        self.selected_point_idx = None
        self.dragging_point = False
        
        self.font_ui = pygame.font.Font(None, 24)
        self.font_title = pygame.font.Font(None, 32)
        try: self.font_icon = pygame.font.SysFont("segoeuiemoji", 30)
        except: self.font_icon = pygame.font.Font(None, 30)
        self.show_ui = True
        
        # --- UI WIDGETS ---
        self.slider_water = Slider(20, 40, 200, 15, -11000.0, 9000.0, 0.0, "Sea Level (m)")
        self.slider_azimuth = Slider(20, 80, 200, 15, 0, 360, 315, "Light Dir")
        self.slider_altitude = Slider(20, 120, 200, 15, 0, 90, 45, "Light Height")
        self.slider_intensity = Slider(20, 160, 200, 15, 0.0, 2.0, 1.2, "Light Power")
        self.slider_contour = Slider(20, 200, 200, 15, 0, 500, 0, "Contours (m) [0=Off]")
        
        self.btn_grid_minus = Button(140, 240, 30, 30, "-", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.dec_grid)
        self.btn_grid_plus = Button(180, 240, 30, 30, "+", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.inc_grid)
        self.btn_regen = Button(20, 280, 220, 30, "Regenerate World", self.font_ui, (100, 100, 100), (150, 150, 150), (255,255,255), self.regenerate_seed)
        
        # Tools
        self.btn_new_road = Button(20, 320, 105, 30, "+ Road", self.font_ui, (139,69,19), (160,82,45), (255,255,255), lambda: self.start_new_vector("road"))
        self.btn_new_river = Button(135, 320, 105, 30, "+ River", self.font_ui, (40,60,150), (60,80,180), (255,255,255), lambda: self.start_new_vector("river"))
        
        self.btn_gen_village_details = Button(20, 400, 220, 30, "AI Gen Village Details", self.font_ui, (100, 100, 200), (150, 150, 250), (255,255,255), self._generate_village_details)

        # Edit Context Buttons
        self.btn_save_vec = Button(20, 320, 220, 30, "Save Line", self.font_ui, (50,150,50), (80,200,80), (255,255,255), self.save_active_vector)
        self.btn_cancel_vec = Button(20, 360, 105, 30, "Cancel", self.font_ui, (150,50,50), (200,80,80), (255,255,255), self.cancel_vector)
        self.btn_delete_vec = Button(135, 360, 105, 30, "Delete", self.font_ui, (100,0,0), (150,0,0), (255,255,255), self.delete_vector)

        # Marker Context Buttons - Initialized immediately
        self._create_marker_buttons()

        self.db = DBManager()
        self.ai = AIManager() 

    def inc_grid(self): self.grid_size = min(256, self.grid_size + 8)
    def dec_grid(self): self.grid_size = max(16, self.grid_size - 8)

    def _create_marker_buttons(self):
        self.btn_edit_marker = Button(20, SCREEN_HEIGHT - 110, 80, 30, "Edit", self.font_ui, (100,150,200), (150,200,250), (0,0,0), self._open_edit_modal)
        self.btn_delete_marker = Button(110, SCREEN_HEIGHT - 110, 80, 30, "Delete", self.font_ui, (200,100,100), (250,150,150), (0,0,0), self._delete_selected_marker)
        self.btn_center_marker = Button(200, SCREEN_HEIGHT - 110, 80, 30, "Center", self.font_ui, (150,150,150), (200,200,200), (0,0,0), self._center_on_selected_marker)

    def set_node(self, node_data):
        self.current_node = node_data
        metadata = node_data.get('metadata', {})
        
        # Load Settings
        if 'sea_level' in metadata: self.slider_water.value = metadata['sea_level']; self.slider_water.update_handle()
        if 'light_azimuth' in metadata: self.slider_azimuth.value = metadata['light_azimuth']; self.slider_azimuth.update_handle()
        if 'light_altitude' in metadata: self.slider_altitude.value = metadata['light_altitude']; self.slider_altitude.update_handle()
        if 'contour_interval' in metadata: self.slider_contour.value = metadata['contour_interval']; self.slider_contour.update_handle()
        if 'grid_size' in metadata: self.grid_size = metadata['grid_size']
        
        # FIX: Always load data even if no image (for Battle Maps)
        self.vectors = self.db.get_vectors(self.current_node['id'])
        self.markers = self.db.get_markers(self.current_node['id'])
        self.active_vector = None
        self.selected_marker = None

        if 'file_path' in metadata:
            self.render_strategy = ImageMapStrategy(metadata, self.theme)
            map_w, map_h = self.render_strategy.width, self.render_strategy.height
            
            if 'cam_x' in metadata:
                self.cam_x = metadata['cam_x']
                self.cam_y = metadata['cam_y']
                self.zoom = metadata['zoom']
            else:
                self.cam_x, self.cam_y = map_w / 2, map_h / 2
                scale_x, scale_y = (SCREEN_WIDTH - 50) / map_w, (SCREEN_HEIGHT - 50) / map_h
                self.zoom = min(scale_x, scale_y)
        else:
            self.render_strategy = None
            # Reset camera for blank grid
            self.cam_x, self.cam_y = 0, 0
            self.zoom = 1.0

    def save_current_state(self):
        """Persist UI settings to DB"""
        if not self.current_node: return
        meta = self.current_node.get('metadata', {})
        meta['sea_level'] = self.slider_water.value
        meta['light_azimuth'] = self.slider_azimuth.value
        meta['light_altitude'] = self.slider_altitude.value
        meta['contour_interval'] = self.slider_contour.value
        meta['cam_x'] = self.cam_x
        meta['cam_y'] = self.cam_y
        meta['zoom'] = self.zoom
        meta['grid_size'] = self.grid_size
        self.db.update_node_data(self.current_node['id'], metadata=meta)

    def regenerate_seed(self):
        if not self.current_node: return
        cid = self.current_node['campaign_id']
        gen = WorldGenerator(self.theme, self.db)
        nid, metadata = gen.generate_world_node(cid)
        # Carry over settings
        metadata['sea_level'] = self.slider_water.value
        self.db.update_node_data(nid, metadata=metadata)
        node = self.db.get_node_by_coords(cid, None, 0, 0)
        self.set_node(node)
        return True
    
    # --- ACTIONS ---
    def start_new_vector(self, vtype):
        self.selected_marker = None
        self.active_vector = {'points': [], 'type': vtype, 'width': 4 if vtype=='road' else 8, 'id': None}
        self.selected_point_idx = None
        return True 
    
    def save_active_vector(self):
        if self.active_vector and len(self.active_vector['points']) > 1:
            self.db.save_vector(self.current_node['id'], self.active_vector['type'], self.active_vector['points'], self.active_vector['width'], self.active_vector.get('id'))
            self.vectors = self.db.get_vectors(self.current_node['id'])
        self.active_vector = None
        return True
    
    def cancel_vector(self):
        self.active_vector = None
        self.selected_point_idx = None
        return True

    def delete_vector(self):
        if self.active_vector and self.active_vector.get('id'):
            self.db.delete_vector(self.active_vector['id'])
            self.vectors = self.db.get_vectors(self.current_node['id'])
        self.active_vector = None
        return True

    def _open_edit_modal(self):
        # FIX: Use Native Editor
        if self.selected_marker:
            ctx = self.current_node['type'] if self.current_node else "world_map"
            NativeMarkerEditor(
                marker_data=self.selected_marker,
                map_context=ctx,
                on_save=self._save_marker,
                on_ai_gen=self._handle_ai_gen
            )
            self.markers = self.db.get_markers(self.current_node['id'])
        return True

    def _delete_selected_marker(self):
        if self.selected_marker:
            self.db.delete_marker(self.selected_marker['id'])
            self.markers = self.db.get_markers(self.current_node['id'])
            self.selected_marker = None
        return True

    def _center_on_selected_marker(self):
        if self.selected_marker: self.cam_x, self.cam_y = self.selected_marker['world_x'], self.selected_marker['world_y']
        return True


    def _generate_village_details(self):
        try:
            # The UI's only job is to instantiate the manager and call its main method.
            village_manager = VillageContentManager(self.current_node, self.db, self.ai)
            village_manager.generate_details()
            
            # Refresh the view with the new data from the DB
            print("AI Update complete. Refreshing view.")
            reloaded_node = self.db.get_node(self.current_node['id'])
            self.set_node(reloaded_node)

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during village generation: {e}")

        return True # For the button handler

    def _generate_village_details_old5(self):
        try:
            # The UI's only job is to instantiate the manager and call it.
            village_manager = VillageContentManager(self.current_node, self.db, self.ai)
            village_manager.generate_details()
        
            # Refresh the view with the new data
            print("Update complete. Refreshing view.")
            reloaded_node = self.db.get_node(self.current_node['id'])
            self.set_node(reloaded_node)

        except ValueError as e:
            print(f"Error: {e}")

        return True # For the button handler

    def _generate_village_details_old4(self):
        """ Gathers village context, calls AI, and updates DB with full debug output. """
        if not self.ai.is_available():
            print("AI Service Unavailable.")
            return

        if not self.current_node or self.current_node['type'] != 'local_map':
            print("This function only works on a local map (village).")
            return

        print("\n--- START AI VILLAGE GENERATION ---")
        
        # 1. THE CALLER GATHERS ITS CONTEXT
        print("DEBUG: Gathering building list from current markers...")
        building_list = [m['title'] for m in self.markers]
        print(f"DEBUG: Found {len(building_list)} locations: {', '.join(building_list)}")
        
        # 2. THE CALLER BUILDS THE SPECIFIC PROMPT
        prompt = (
            f"You are a TTRPG content generator for a fantasy setting. Given the following village, populate it with rich, interconnected details.\n"
            f"Village Name: {self.current_node['name']}\n"
            f"Key Locations Present: {', '.join(building_list)}\n\n"
            "Return a single JSON object with this exact structure:\n"
            "- 'overview': An atmospheric paragraph about the village's history, atmosphere, and current situation.\n"
            "- 'locations': A dictionary where each key is a location name from the list above, and the value is a one-sentence description for a map tooltip.\n"
            "- 'npcs': A list of 3-4 notable NPC objects. Each NPC object must have these keys: 'name' (string), 'role' (string, e.g., 'Blacksmith'), 'personality' (string), 'hook' (string, a plot hook related to them), and 'location' (string, MUST be one of the Key Locations provided).\n"
            "- 'rumors': A list of 4-6 interesting plot hooks or rumors floating around the village."
        )

        schema = """
        {
            "overview": "...",
            "locations": { "Building Name 1": "description...", "Building Name 2": "description..." },
            "npcs": [ {"name":"...", "role":"...", "personality":"...", "hook":"...", "location":"Building Name 1"} ],
            "rumors": [ "rumor 1", "rumor 2" ]
        }
        """

        # 3. THE CALLER USES THE DUMB PIPE
        print("\n" + "="*20 + " AI PROMPT SENT " + "="*20)
        print(prompt)
        print("="*56 + "\n")
        
        response_data = self.ai.generate_json(prompt, schema)

        if not response_data:
            print("--- AI FAILED: No valid JSON returned. ---")
            return

        # 4. THE CALLER PROCESSES THE RESPONSE
        print("\n" + "="*20 + " AI RESPONSE RECEIVED " + "="*20)
        print(json.dumps(response_data, indent=2))
        print("="*60 + "\n")
        
        print("\n--- DATABASE UPDATE ---")
        
        # Update individual building markers
        locations = response_data.get('locations', {})
        print(f"DEBUG: Processing {len(locations)} location descriptions to update marker tooltips...")
        for marker in self.markers:
            if marker['title'] in locations:
                new_desc = locations[marker['title']]
                print(f"  -> Updating Marker ID {marker['id']} ('{marker['title']}'): new description='{new_desc[:80]}...'")
                # Update only the description, leave all other marker data intact
                self.db.update_marker(marker['id'], marker['world_x'], marker['world_y'], marker['symbol'], marker['title'], new_desc)

        # Update the main village node's metadata with the rich details
        node_meta = self.current_node.get('metadata', {})
        node_meta['overview'] = response_data.get('overview')
        node_meta['npcs'] = response_data.get('npcs', [])
        node_meta['rumors'] = response_data.get('rumors', [])
        
        print(f"\nDEBUG: Storing overview, {len(node_meta['npcs'])} NPCs, and {len(node_meta['rumors'])} rumors in Node ID {self.current_node['id']}'s metadata.")
        
        self.db.update_node_data(self.current_node['id'], metadata=node_meta)
        
        # 5. Refresh view to make new data live
        print("\n--- REFRESHING VIEW ---")
        reloaded_node = self.db.get_node(self.current_node['id'])
        self.set_node(reloaded_node)
        print("--- END AI VILLAGE GENERATION ---\n")

        return True # For the button handler

    def _generate_village_details_old1debug(self):
        """ Gathers village context, calls AI, and updates DB with full debug output. """
        if not self.ai.is_available():
            print("DEBUG: AI Service Unavailable.")
            return

        if not self.current_node or self.current_node['type'] != 'local_map':
            print("DEBUG: This function only works on a local map (village).")
            return

        print("\n--- START AI VILLAGE GENERATION ---")
        
        # 1. GATHER CONTEXT
        print("DEBUG: Gathering building list from current markers...")
        building_list = [f"- {m['title']}" for m in self.markers if m['symbol'] == 'house']
        print(f"DEBUG: Found {len(building_list)} buildings.")
        
        prompt = (
            f"You are a TTRPG content generator. Given the following village, populate it with rich details.\n"
            f"Village Name: {self.current_node['name']}\n"
            f"Buildings:\n"
            f"{'\n'.join(building_list)}\n\n"
            "Return a JSON object with this exact structure:\n"
            "- 'overview': An atmospheric paragraph about the village.\n"
            "- 'locations': A dictionary where each key is a building name from the list above, and the value is a brief description.\n"
            "- 'npcs': A list of 3-5 notable NPC objects, each with 'name', 'role', and 'quirk'.\n"
            "- 'rumors': A list of 4-6 interesting plot hooks or rumors."
        )

        schema = """
        {
            "overview": "...",
            "locations": { "Building Name": "description..." },
            "npcs": [ {"name":"...", "role":"...", "quirk":"..."} ],
            "rumors": [ "rumor 1", "rumor 2" ]
        }
        """

        # 2. SEND TO AI
        print("\n" + "="*20 + " AI PROMPT SENT " + "="*20)
        print(prompt)
        print("="*56 + "\n")
        
        response_data = self.ai.generate_json(prompt, schema)

        if not response_data:
            print("--- AI FAILED: No valid JSON returned. ---")
            return

        # 3. PROCESS RESPONSE
        print("\n" + "="*20 + " AI RESPONSE RECEIVED " + "="*20)
        print(json.dumps(response_data, indent=2))
        print("="*60 + "\n")
        
        print("\n--- DATABASE UPDATE ---")
        
        # Update individual building markers
        locations = response_data.get('locations', {})
        print(f"DEBUG: Processing {len(locations)} location descriptions...")
        for marker in self.markers:
            if marker['title'] in locations:
                new_desc = locations[marker['title']]
                print(f"  -> Updating Marker ID {marker['id']} ('{marker['title']}'): new description='{new_desc[:80]}...'")
                self.db.update_marker(marker['id'], marker['world_x'], marker['world_y'], marker['symbol'], marker['title'], new_desc, marker['metadata'])

        # Update the main village node's metadata
        node_meta = self.current_node.get('metadata', {})
        node_meta['overview'] = response_data.get('overview')
        node_meta['npcs'] = response_data.get('npcs', [])
        node_meta['rumors'] = response_data.get('rumors', [])
        
        print(f"\nDEBUG: Updating Node ID {self.current_node['id']} with new metadata:")
        print(json.dumps(node_meta, indent=2))
        
        self.db.update_node_data(self.current_node['id'], metadata=node_meta)
        
        # 4. Refresh view to show new data
        print("\n--- REFRESHING VIEW ---")
        reloaded_node = self.db.get_node(self.current_node['id'])
        self.set_node(reloaded_node)
        print("--- END AI VILLAGE GENERATION ---\n")

        return True # For the button handler

    def _generate_village_details_no_debug(self):
        """ Gathers village context, calls AI, and updates DB. """
        if not self.ai.is_available():
            print("AI Service Unavailable.")
            return

        if not self.current_node or self.current_node['type'] != 'local_map':
            print("This function only works on a local map (village).")
            return

        print("Gathering village data for AI prompt...")
        # 1. THE CALLER GATHERS ITS CONTEXT
        building_list = [f"- {m['title']} ({m['symbol']})" for m in self.markers if m['symbol'] == 'house']
        
        prompt = (
            f"You are a TTRPG content generator. Given the following village, populate it with rich details.\n"
            f"Village Name: {self.current_node['name']}\n"
            f"Buildings:\n"
            f"{'\n'.join(building_list)}\n\n"
            "Return a JSON object with this exact structure:\n"
            "- 'overview': An atmospheric paragraph about the village.\n"
            "- 'locations': A dictionary where each key is a building name from the list above, and the value is a brief description.\n"
            "- 'npcs': A list of 3-5 notable NPC objects, each with 'name', 'role', and 'quirk'.\n"
            "- 'rumors': A list of 4-6 interesting plot hooks or rumors."
        )

        schema = """
        {
            "overview": "...",
            "locations": { "Building Name": "description..." },
            "npcs": [ {"name":"...", "role":"...", "quirk":"..."} ],
            "rumors": [ "rumor 1", "rumor 2" ]
        }
        """

        # 2. THE CALLER USES THE DUMB PIPE
        print("Sending request to AI...")
        response_data = self.ai.generate_json(prompt, schema)

        if not response_data:
            print("AI generation failed.")
            return

        # 3. THE CALLER PROCESSES THE RESPONSE
        print("AI response received. Updating database...")
        # Update individual building markers
        locations = response_data.get('locations', {})
        for marker in self.markers:
            if marker['title'] in locations:
                new_desc = locations[marker['title']]
                # Update only the description, leave everything else intact
                self.db.update_marker(marker['id'], marker['world_x'], marker['world_y'], marker['symbol'], marker['title'], new_desc, marker['metadata'])

        # Update the main village node's metadata with NPCs and rumors
        node_meta = self.current_node.get('metadata', {})
        node_meta['overview'] = response_data.get('overview')
        node_meta['npcs'] = response_data.get('npcs', [])
        node_meta['rumors'] = response_data.get('rumors', [])
        self.db.update_node_data(self.current_node['id'], metadata=node_meta)
        
        # 4. Refresh view to show new data
        print("Update complete. Refreshing view.")
        reloaded_node = self.db.get_node(self.current_node['id'])
        self.set_node(reloaded_node)

        return True # For the button handler

    def _save_marker(self, marker_id, symbol, title, note, metadata):
        # FIX: Accept Metadata
        if marker_id: 
            m = self.selected_marker
            self.db.update_marker(marker_id, m['world_x'], m['world_y'], symbol, title, note, metadata)
        else: 
            wx, wy = self.pending_click_pos
            self.db.add_marker(self.current_node['id'], wx, wy, symbol, title, note, metadata)
        self.markers = self.db.get_markers(self.current_node['id'])
        self.active_modal, self.selected_marker = None, None

    def _close_modal(self): self.active_modal = None

    # --- INPUT ---
    def handle_input(self, event):
        if self.active_modal:
            # Native windows handle their own loop, so active_modal shouldn't be used
            # But kept if we ever revert to Pygame Modal
            self.active_modal.handle_event(event)
            return

        # 1. UI Handling
        if self.show_ui:
            self.slider_water.handle_event(event)
            self.slider_azimuth.handle_event(event)
            self.slider_altitude.handle_event(event)
            self.slider_intensity.handle_event(event)
            self.slider_contour.handle_event(event)
            self.btn_grid_plus.handle_event(event)
            self.btn_grid_minus.handle_event(event)
            if self.btn_regen.handle_event(event): return
            
            if not self.active_vector:
                if self.btn_new_road.handle_event(event): return
                if self.btn_new_river.handle_event(event): return
            else:
                if self.btn_save_vec.handle_event(event): return
                if self.btn_cancel_vec.handle_event(event): return
                if self.btn_delete_vec.handle_event(event): return

            if self.current_node and self.current_node['type'] == 'local_map':
                if self.btn_gen_village_details.handle_event(event):
                    return

            if self.selected_marker:
                if self.btn_edit_marker.handle_event(event): return

            if self.selected_marker:
                if self.btn_edit_marker.handle_event(event): return
                if self.btn_delete_marker.handle_event(event): return
                if self.btn_center_marker.handle_event(event): return

            if self.render_strategy:
                self.render_strategy.set_light_direction(self.slider_azimuth.value, self.slider_altitude.value)
                self.render_strategy.set_light_intensity(self.slider_intensity.value)

        # 2. Camera
        keys = pygame.key.get_pressed()
        speed = 20 / self.zoom 
        if keys[pygame.K_LSHIFT]: speed *= 3
        if keys[pygame.K_LEFT]: self.cam_x -= speed
        if keys[pygame.K_RIGHT]: self.cam_x += speed
        if keys[pygame.K_UP]: self.cam_y -= speed
        if keys[pygame.K_DOWN]: self.cam_y += speed
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFTBRACKET: self.zoom = max(0.01, self.zoom * 0.9)
            if event.key == pygame.K_RIGHTBRACKET: self.zoom = min(10.0, self.zoom * 1.1)
            if event.key == pygame.K_h: self.show_ui = not self.show_ui
            if event.key == pygame.K_g: self.show_grid = not self.show_grid
            if event.key == pygame.K_s: self.save_current_state()
            if event.key == pygame.K_ESCAPE:
                if self.active_vector: self.cancel_vector()
                else: self.save_current_state()

        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        # 3. MOUSE MOTION
        if event.type == pygame.MOUSEMOTION:
            world_x = ((event.pos[0] - center_x) / self.zoom) + self.cam_x
            world_y = ((event.pos[1] - center_y) / self.zoom) + self.cam_y

            if self.active_vector and self.dragging_point and self.selected_point_idx is not None:
                self.active_vector['points'][self.selected_point_idx] = (world_x, world_y)
                return

            if self.dragging_marker:
                self.dragging_marker['world_x'] = world_x - self.drag_offset[0]
                self.dragging_marker['world_y'] = world_y - self.drag_offset[1]
                return

        # 4. MOUSE UP
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_marker:
                m = self.dragging_marker
                self.db.update_marker(m['id'], m['world_x'], m['world_y'], m['symbol'], m['title'], m['description'])
                self.dragging_marker = None
            if self.dragging_point:
                self.dragging_point = False

        # 5. MOUSE DOWN
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.show_ui and event.pos[0] < 260: return 

            world_x = ((event.pos[0] - center_x) / self.zoom) + self.cam_x
            world_y = ((event.pos[1] - center_y) / self.zoom) + self.cam_y

            # A. Vector Edit
            if self.active_vector:
                hit_point = False
                for i, pt in enumerate(self.active_vector['points']):
                    dist = math.hypot(pt[0]-world_x, pt[1]-world_y)
                    if dist < 10/self.zoom:
                        self.selected_point_idx = i
                        self.dragging_point = True
                        hit_point = True
                        break
                
                if not hit_point:
                    self.active_vector['points'].append((world_x, world_y))
                    self.selected_point_idx = len(self.active_vector['points']) - 1
                return

            # B. Check Markers
            if self.hovered_marker:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    return {"action": "enter_marker", "marker": self.hovered_marker}
                
                self.selected_marker = self.hovered_marker
                self._create_marker_buttons()
                self.dragging_marker = self.selected_marker
                self.drag_offset = (world_x - self.dragging_marker['world_x'], world_y - self.dragging_marker['world_y'])
                return
            
            if self.selected_marker and event.pos[0] < 300 and event.pos[1] > SCREEN_HEIGHT-160: 
                return 

            # C. Pixel Check (Road/River)
            try:
                pixel = self.screen.get_at(event.pos)[:3]
                target_type = None
                if pixel == COLOR_ROAD: target_type = "road"
                elif pixel == COLOR_RIVER: target_type = "river"
                
                if target_type:
                    closest = None
                    min_d = float('inf')
                    for vec in self.vectors:
                        if vec['type'] != target_type: continue
                        for pt in vec['points']:
                            d = math.hypot(pt[0]-world_x, pt[1]-world_y)
                            if d < min_d:
                                min_d = d
                                closest = vec
                    
                    if closest and min_d < 1000: 
                        self.active_vector = closest
                        self.selected_marker = None
                        return
            except: pass

            # D. Default
            self.selected_marker = None
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.pending_click_pos = (world_x, world_y)
                ctx = self.current_node['type'] if self.current_node else "world_map"
                
                # FIX: Use Native Editor for Creation
                new_marker = {'title': 'New Marker', 'description': '', 'metadata': {}, 'symbol': 'star'}
                
                NativeMarkerEditor(
                    marker_data=new_marker,
                    map_context=ctx,
                    on_save=self._save_marker,
                    on_ai_gen=self._handle_ai_gen
                )
                self.markers = self.db.get_markers(self.current_node['id'])
            else:
                self.cam_x, self.cam_y = world_x, world_y
                self.zoom = min(10.0, self.zoom * 2.0)

    def draw(self):
        self.screen.fill((10, 10, 15)) 
        
        if self.render_strategy:
            self.render_strategy.draw(
                self.screen, self.cam_x, self.cam_y, self.zoom, 
                SCREEN_WIDTH, SCREEN_HEIGHT, 
                sea_level_meters=self.slider_water.value, 
                vectors=self.vectors,
                active_vector=self.active_vector,
                selected_point_idx=self.selected_point_idx,
                contour_interval=self.slider_contour.value
            )
            
        if self.show_grid and self.render_strategy:
            center_x, center_y = SCREEN_WIDTH//2, SCREEN_HEIGHT//2
            map_sx, map_sy = center_x-(self.cam_x*self.zoom), center_y-(self.cam_y*self.zoom)
            map_w, map_h = self.render_strategy.width*self.zoom, self.render_strategy.height*self.zoom
            map_rect = pygame.Rect(map_sx, map_sy, map_w, map_h)
            self.screen.set_clip(map_rect)
            if self.grid_type == "HEX": self._draw_hex_grid(map_sx, map_sy)
            else: self._draw_square_grid(map_sx, map_sy)
            self.screen.set_clip(None)
            pygame.draw.rect(self.screen, (255, 255, 255), map_rect, 2)
        
        self._draw_markers()
        self._draw_scale_bar()
        if self.show_ui: self._draw_ui()
        if self.active_modal: self.active_modal.draw(self.screen)

    def _draw_hex_grid(self, start_x, start_y):
        hex_radius = self.grid_size * self.zoom
        if hex_radius < 5: return
        hex_w = math.sqrt(3) * hex_radius; vert_spacing = (2 * hex_radius) * 0.75
        screen_rel_x, screen_rel_y = -start_x, -start_y
        start_col, start_row = int(screen_rel_x/hex_w)-1, int(screen_rel_y/vert_spacing)-1
        cols_vis, rows_vis = int(SCREEN_WIDTH/hex_w)+3, int(SCREEN_HEIGHT/vert_spacing)+3
        color = (255, 255, 255, 30)
        for r in range(start_row, start_row + rows_vis):
            for q in range(start_col, start_col + cols_vis):
                x_off = (r % 2) * (hex_w / 2)
                cx, cy = start_x+(q*hex_w)+x_off, start_y+(r*vert_spacing)
                points = []
                for i in range(6):
                    angle = math.pi/3*i+(math.pi/6)
                    points.append((cx+hex_radius*math.cos(angle), cy+hex_radius*math.sin(angle)))
                pygame.draw.lines(self.screen, color, True, points, 1)

    def _draw_square_grid(self, start_x, start_y):
        size = self.grid_size * self.zoom; color = (255, 255, 255, 30)
        if size < 4: return
        map_w, map_h = self.render_strategy.width*self.zoom, self.render_strategy.height*self.zoom
        x, y = start_x, start_y
        while x <= start_x+map_w:
            if 0<=x<=SCREEN_WIDTH: pygame.draw.line(self.screen, color, (x,start_y), (x,start_y+map_h))
            x+=size
        while y <= start_y+map_h:
            if 0<=y<=SCREEN_HEIGHT: pygame.draw.line(self.screen, color, (start_x,y), (start_x+map_w,y))
            y+=size

    def _draw_markers(self):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_marker = None
        
        for m in self.markers:
            sx, sy = center_x+(m['world_x']-self.cam_x)*self.zoom, center_y+(m['world_y']-self.cam_y)*self.zoom
            
            # Culling
            if not (-50 <= sx <= SCREEN_WIDTH+50 and -50 <= sy <= SCREEN_HEIGHT+50):
                continue
            
            is_selected = self.selected_marker and self.selected_marker['id']==m['id']
            sym = m['symbol'].lower()
            title_lower = m['title'].lower()
            click_rect = None
            
            # Visuals
            if "dungeon" in sym or "skull" in sym or "cave" in title_lower:
                rect_size = 20
                r = pygame.Rect(sx - rect_size//2, sy - rect_size//2, rect_size, rect_size)
                pygame.draw.rect(self.screen, (50, 20, 20), r)
                pygame.draw.rect(self.screen, (255, 100, 100), r, 2)
                click_rect = r
            elif "house" in sym or "village" in title_lower or "inn" in title_lower or "town" in title_lower:
                pts = [(sx, sy - 12), (sx + 10, sy - 4), (sx + 7, sy + 10), (sx - 7, sy + 10), (sx - 10, sy - 4)]
                pygame.draw.polygon(self.screen, (100, 150, 200), pts)
                pygame.draw.polygon(self.screen, (200, 200, 255), pts, 2)
                click_rect = pygame.Rect(sx-10, sy-12, 20, 22)
            else:
                pygame.draw.circle(self.screen, (200, 200, 200), (int(sx), int(sy)), 8)
                pygame.draw.circle(self.screen, (50, 50, 50), (int(sx), int(sy)), 8, 2)
                click_rect = pygame.Rect(sx-8, sy-8, 16, 16)

            if is_selected and not self.dragging_marker:
                pygame.draw.circle(self.screen, (255, 255, 0), (int(sx), int(sy)), 18, 2)

            # Title
            title_surf = self.font_ui.render(m['title'], True, (255, 255, 255))
            bg = pygame.Surface((title_surf.get_width()+4, title_surf.get_height()+2))
            bg.fill((0,0,0)); bg.set_alpha(150)
            t_x, t_y = sx - title_surf.get_width() // 2, sy + 12
            self.screen.blit(bg, (t_x-2, t_y-1))
            self.screen.blit(title_surf, (t_x, t_y))

            if click_rect.collidepoint(mouse_pos) and not self.active_modal and not self.dragging_marker:
                self.hovered_marker = m

        if self.hovered_marker:
            self._draw_tooltip(mouse_pos)

    def _draw_tooltip(self, pos):
        m = self.hovered_marker
        lines = []
        
        # Description only
        desc = m.get('description', '')
        if desc:
            chunk_size = 40
            for i in range(0, len(desc), chunk_size):
                lines.append(desc[i:i+chunk_size])
        else:
            lines.append("No description.")
        
        lines.append("(Shift+Click to Enter)")

        rendered_lines = []
        max_w = 0
        for line in lines:
            surf = self.font_ui.render(line, True, (200, 200, 200))
            rendered_lines.append(surf)
            max_w = max(max_w, surf.get_width())

        bg_rect = pygame.Rect(pos[0]+15, pos[1]+15, max_w+20, len(lines)*20 + 10)
        
        # Clamp to screen
        if bg_rect.right > SCREEN_WIDTH: bg_rect.x -= (bg_rect.width + 30)
        if bg_rect.bottom > SCREEN_HEIGHT: bg_rect.y -= (bg_rect.height + 30)

        pygame.draw.rect(self.screen, (20, 20, 30), bg_rect)
        pygame.draw.rect(self.screen, (100, 100, 150), bg_rect, 1)
        
        y_off = 5
        for surf in rendered_lines:
            self.screen.blit(surf, (bg_rect.x + 10, bg_rect.y + y_off))
            y_off += 20

    def _draw_scale_bar(self):
        km_per_hex = (self.grid_size / self.zoom) * 1.0 # 1px=1km
        text = f"Scale: 1 Hex = {km_per_hex:.2f} km"
        ts = self.font_ui.render(text, True, (200,200,200))
        bg = ts.get_rect(bottomright=(SCREEN_WIDTH-20, SCREEN_HEIGHT-20)); bg.inflate_ip(20,10)
        pygame.draw.rect(self.screen, (0,0,0,150), bg, border_radius=5)
        self.screen.blit(ts, (bg.x+10, bg.y+5))

    def _draw_ui(self):
        # Sidebar Background
        pygame.draw.rect(self.screen, (30,30,40), (0,0,260, SCREEN_HEIGHT))
        pygame.draw.rect(self.screen, (100,100,100), (0,0,260, SCREEN_HEIGHT), 2)
        
        if self.current_node: 
            self.screen.blit(self.font_title.render("World Controls", True, (255,255,255)), (20,15))
        
        self.slider_water.draw(self.screen)
        self.slider_azimuth.draw(self.screen)
        self.slider_altitude.draw(self.screen)
        self.slider_intensity.draw(self.screen)
        self.slider_contour.draw(self.screen)
        
        self.screen.blit(self.font_ui.render(f"Grid Size: {self.grid_size}", True, (200,200,200)), (20,245))
        self.btn_grid_minus.draw(self.screen)
        self.btn_grid_plus.draw(self.screen)
        self.btn_regen.draw(self.screen)
        
        # --- VECTOR TOOLS ---
        if self.active_vector:
            self.btn_save_vec.draw(self.screen)
            self.btn_cancel_vec.draw(self.screen)
            if self.active_vector.get('id'):
                self.btn_delete_vec.draw(self.screen)
            
            lbl = self.font_ui.render(f"EDITING: {self.active_vector['type'].upper()}", True, (255,200,100))
            self.screen.blit(lbl, (20, 360)) # Adjusted Y
        else:
            self.btn_new_road.draw(self.screen)
            self.btn_new_river.draw(self.screen)

        # --- CONTEXTUAL AI BUTTON (Moved outside vector logic) ---
        if self.current_node and self.current_node['type'] == 'local_map':
            self.btn_gen_village_details.draw(self.screen)

        # --- SELECTED MARKER PANEL ---
        if self.selected_marker and not self.dragging_marker:
            panel_y = SCREEN_HEIGHT-160
            pygame.draw.rect(self.screen, (40,40,50), (10,panel_y,240,150), border_radius=5)
            pygame.draw.rect(self.screen, (150,150,150), (10,panel_y,240,150),1,border_radius=5)
            self.screen.blit(self.font_title.render(self.selected_marker['title'], True, (255,255,100)), (20, panel_y+10))
            
            desc = self.selected_marker.get('description', '')
            if len(desc) > 30: desc = desc[:27] + "..."
            self.screen.blit(self.font_ui.render(desc, True, (200,200,200)), (20,panel_y+45))
            
            self.btn_edit_marker.draw(self.screen)
            self.btn_delete_marker.draw(self.screen)
            self.btn_center_marker.draw(self.screen)

    def _draw_ui_old3(self):
        # Sidebar Background
        pygame.draw.rect(self.screen, (30,30,40), (0,0,260, SCREEN_HEIGHT))
        pygame.draw.rect(self.screen, (100,100,100), (0,0,260, SCREEN_HEIGHT), 2)
        
        if self.current_node: 
            self.screen.blit(self.font_title.render("World Controls", True, (255,255,255)), (20,15))
        
        self.slider_water.draw(self.screen)
        self.slider_azimuth.draw(self.screen)
        self.slider_altitude.draw(self.screen)
        self.slider_intensity.draw(self.screen)
        self.slider_contour.draw(self.screen)
        
        self.screen.blit(self.font_ui.render(f"Grid Size: {self.grid_size}", True, (200,200,200)), (20,245))
        self.btn_grid_minus.draw(self.screen)
        self.btn_grid_plus.draw(self.screen)
        self.btn_regen.draw(self.screen)
        
        if self.active_vector:
            self.btn_save_vec.draw(self.screen)
            self.btn_cancel_vec.draw(self.screen)
            if self.active_vector.get('id'):
                self.btn_delete_vec.draw(self.screen)
            
            lbl = self.font_ui.render(f"EDITING: {self.active_vector['type'].upper()}", True, (255,200,100))
            self.screen.blit(lbl, (20, 320))
            
            hint = self.font_ui.render("Left-Click Map to add points", True, (150,150,150))
            self.screen.blit(hint, (20, 420))
            hint2 = self.font_ui.render("Drag points to reshape", True, (150,150,150))
            self.screen.blit(hint2, (20, 440))
        else:
            self.btn_new_road.draw(self.screen)
            self.btn_new_river.draw(self.screen)

        if self.selected_marker and not self.dragging_marker:
            panel_y = SCREEN_HEIGHT-160
            pygame.draw.rect(self.screen, (40,40,50), (10,panel_y,240,150), border_radius=5)
            pygame.draw.rect(self.screen, (150,150,150), (10,panel_y,240,150),1,border_radius=5)
            self.screen.blit(self.font_title.render(self.selected_marker['title'], True, (255,255,100)), (20, panel_y+10))
            
            desc = self.selected_marker.get('description', '')
            if len(desc) > 30: desc = desc[:27] + "..."
            self.screen.blit(self.font_ui.render(desc, True, (200,200,200)), (20,panel_y+45))
            
            self.btn_edit_marker.draw(self.screen)
            self.btn_delete_marker.draw(self.screen)
            self.btn_center_marker.draw(self.screen)

            if self.current_node and self.current_node['type'] == 'local_map':
                self.btn_gen_village_details.draw(self.screen)
