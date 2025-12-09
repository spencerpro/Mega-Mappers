import pygame
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT
from codex_engine.core.db_manager import DBManager
from codex_engine.controllers.geo_controller import GeoController
from codex_engine.controllers.tactical_controller import TacticalController

class MapViewer:
    def __init__(self, screen, theme_manager):
        self.screen = screen
        self.theme = theme_manager
        self.db = DBManager()
        
        self.cam_x, self.cam_y, self.zoom = 0, 0, 1.0
        self.current_node = None
        self.controller = None
        
        self.show_ui = True
        self.font_title = pygame.font.Font(None, 32)
        self.font_ui = pygame.font.Font(None, 24)

    def set_node(self, node_data):
        if self.controller:
            self.save_current_state()
            self.controller.cleanup()
            
        self.current_node = node_data
        metadata = node_data.get('metadata', {})
        geo = node_data.get('geometry_data', {})
        node_type = node_data.get('type', 'world_map')
        
        if node_type in ['dungeon_level', 'building_interior', 'tactical_map']:
            self.controller = TacticalController(self.db, node_data, self.theme)
            if 'cam_x' in metadata:
                self.cam_x, self.cam_y = metadata['cam_x'], metadata['cam_y']
                self.zoom = metadata.get('zoom', 1.0)
            else:
                self.cam_x = geo.get('width', 30) / 2
                self.cam_y = geo.get('height', 30) / 2
                self.zoom = 1.0
        else:
            self.controller = GeoController(self.db, node_data, self.theme)
            if 'cam_x' in metadata:
                self.cam_x, self.cam_y = metadata['cam_x'], metadata['cam_y']
                self.zoom = metadata.get('zoom', 1.0)
            else:
                self.cam_x, self.cam_y, self.zoom = 0, 0, 1.0

    def handle_zoom(self, direction, mouse_pos):
        """Zooms into the center of the screen, using the controller's speed."""
        if not self.controller: return

        # Get the zoom speed from the active controller
        zoom_speed = getattr(self.controller, 'zoom_factor', 1.2)
        
        if direction > 0: # Scroll up
            self.zoom = min(20.0, self.zoom * zoom_speed)
        else: # Scroll down
            self.zoom = max(0.05, self.zoom / zoom_speed)

    def save_current_state(self):
        if not self.current_node or not self.controller: return
        updates = self.controller.get_metadata_updates()
        updates['cam_x'] = self.cam_x
        updates['cam_y'] = self.cam_y
        updates['zoom'] = self.zoom
        current_meta = self.current_node.get('metadata', {})
        current_meta.update(updates)
        self.db.update_node_data(self.current_node['id'], metadata=current_meta)

    def handle_input(self, event):
        if not self.controller: return

        # RESTORED: Keyboard zoom works again
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFTBRACKET:
                self.zoom = max(0.1, self.zoom * 0.9)
                return
            if event.key == pygame.K_RIGHTBRACKET:
                self.zoom = min(20.0, self.zoom * 1.1)
                return
            if event.key == pygame.K_h: self.show_ui = not self.show_ui; return
            if event.key == pygame.K_s: self.save_current_state(); return

        result = self.controller.handle_input(event, self.cam_x, self.cam_y, self.zoom)
        
        if result:
            if result.get("action") == "pan":
                self.cam_x, self.cam_y = result['pos']
            elif result.get("action") == "reload_node":
                updated_node = self.db.get_node(self.current_node['id'])
                self.set_node(updated_node)
            return result 

    def draw(self):
        self.screen.fill((10, 10, 15))
        if not self.controller: return
        self.controller.update()
        self.controller.draw_map(self.screen, self.cam_x, self.cam_y, self.zoom, SCREEN_WIDTH, SCREEN_HEIGHT)
        if self.show_ui: self._draw_sidebar()
        self.controller.draw_overlays(self.screen, self.cam_x, self.cam_y, self.zoom)
        self._draw_scale_bar()

    def _draw_sidebar(self):
        pygame.draw.rect(self.screen, (30,30,40), (0,0,260, SCREEN_HEIGHT))
        pygame.draw.rect(self.screen, (100,100,100), (0,0,260, SCREEN_HEIGHT), 2)
        if self.current_node: 
            title = self.current_node.get('name', 'Unknown')
            type_str = self.current_node.get('type', 'unknown').replace('_', ' ').title()
            self.screen.blit(self.font_title.render(f"{title}", True, (255,255,255)), (20,15))
            self.screen.blit(self.font_ui.render(f"({type_str})", True, (150,150,150)), (20,45))

        if self.controller:
            for widget in self.controller.widgets: widget.draw(self.screen)
            if hasattr(self.controller, 'active_vector') and self.controller.active_vector:
                lbl = self.font_ui.render(f"EDIT: {self.controller.active_vector['type'].upper()}", True, (255,200,100))
                self.screen.blit(lbl, (20, 370))

    def _draw_scale_bar(self):
        map_width_m = self.current_node.get('geometry_data', {}).get('width', 100)
        if self.current_node['type'] == 'world_map': unit, scale_factor = "km", 1000
        else: unit, scale_factor = "m", map_width_m
        
        units_per_pixel = (scale_factor / self.current_node.get('metadata',{}).get('width', 1024)) / self.zoom
        bar_width_px = 100
        bar_units = bar_width_px * units_per_pixel

        text = f"{bar_units:.1f} {unit}"
        ts = self.font_ui.render(text, True, (200,200,200))
        
        bg_rect = pygame.Rect(SCREEN_WIDTH - 140, SCREEN_HEIGHT - 40, 120, 30)
        pygame.draw.rect(self.screen, (0,0,0,150), bg_rect, border_radius=5)
        
        line_y = bg_rect.centery + 5
        pygame.draw.line(self.screen, (200,200,200), (bg_rect.x + 10, line_y), (bg_rect.x + 10 + bar_width_px, line_y), 2)
        
        text_rect = ts.get_rect(midbottom=(bg_rect.centerx, line_y - 2))
        self.screen.blit(ts, text_rect)
