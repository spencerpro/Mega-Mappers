import pygame
import json
import math
import random
from codex_engine.controllers.base_controller import BaseController
from codex_engine.ui.renderers.grid_strategy import GridMapStrategy
from codex_engine.ui.renderers.tactical.dungeon_renderer import DungeonRenderer
from codex_engine.ui.renderers.tactical.blueprint_renderer import BlueprintRenderer
from codex_engine.generators.dungeon_content_manager import DungeonContentManager
from codex_engine.ui.editors import get_text_input # IMPORT THE DIALOG

from codex_engine.ui.widgets import Button
from codex_engine.ui.info_panel import InfoPanel
from codex_engine.content.managers import TacticalContent
from codex_engine.core.ai_manager import AIManager
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT

COLOR_PARCHMENT = (245, 235, 215)
COLOR_INK = (40, 30, 20)

class TacticalController(BaseController):
    def __init__(self, db_manager, node_data, theme_manager):
        super().__init__(db_manager, node_data, theme_manager)

        self.dragging_map = False
        self.drag_start_pos = (0, 0)
        self.drag_start_cam = (0, 0)

        self.zoom_factor = 1.05 # Slow, precise zoom for tactical maps
        
        self.ai = AIManager()
        self.render_strategy = GridMapStrategy(self.node, self.theme)
        
        self.grid_data = self.node['geometry_data']['grid']
        self.markers = self.db.get_markers(self.node['id'])
        
        self.active_brush = 1
        self.painting = False
        self.active_tab = "INFO"
        self.hovered_marker = None
        
        self.font_ui = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
        self.content_manager = TacticalContent(self.db, self.node)
        self.info_panel = InfoPanel(self.content_manager, self.db, self.node, self.font_ui, self.font_small)
        
        self.renderer = None
        if self.node['type'] == 'dungeon_level':
            self.renderer = DungeonRenderer(self.node, self.render_strategy.cell_size)
        elif self.node['type'] in ['building_interior', 'tactical_map']:
            self.renderer = BlueprintRenderer(self.node, self.render_strategy.cell_size)
        else:
            self.renderer = BlueprintRenderer(self.node, self.render_strategy.cell_size)

        self.static_map_surf = None
        self._render_static_map()
        
        self._init_ui()

    def _render_static_map(self):
        if self.renderer:
            self.static_map_surf = self.renderer.render()

    def _init_ui(self):
        self.btn_back = Button(20, 50, 60, 25, "<- Up", self.font_ui, (80,80,90), (100,100,120), (255,255,255), self._go_up_level)
        tab_y = 90
        self.btn_tab_info   = Button(20, tab_y, 70, 30, "Info", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("INFO"))
        self.btn_tab_tools  = Button(95, tab_y, 70, 30, "Build", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("TOOLS"))
        self.btn_tab_config = Button(170, tab_y, 70, 30, "Setup", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("CONFIG"))

        self.brushes        = [(20, 140, "Floor", 1), (100, 140, "Corridor", 2), (20, 180, "Void", 0)]
        self.brush_buttons  = []
        for x, y, lbl, val in self.brushes:
            btn = Button(x, y, 70, 30, lbl, self.font_ui, (100,100,100), (150,150,150), (255,255,255), lambda v=val: self._set_brush(v))
            self.brush_buttons.append(btn)
            
        self.btn_reset_view = Button(20, 140, 220, 30, "Reset View", self.font_ui, (100,150,200), (150,200,250), (255,255,255), self._reset_view)
        self.btn_regen      = Button(20, 180, 220, 30, "Regenerate Layout", self.font_ui, (150,100,100), (200,150,150), (255,255,255), self._regenerate_map)
        self.btn_gen_details = Button(20, 220, 220, 30, "AI Gen Content", self.font_ui, (100,100,200), (150,150,250), (255,255,255), self._generate_ai_details)

    def _set_tab(self, t): self.active_tab = t
    def _set_brush(self, val): self.active_brush = val
    def _go_up_level(self): return {"action": "go_up_level"}

    def _generate_ai_details(self):
        """Dispatcher for AI content generation."""
        if self.node['type'] == 'dungeon_level':
            # 1. GET THEME FROM USER
            theme_prompt = get_text_input("Enter a theme for the rooms (e.g., 'Goblin infested'):")
            if not theme_prompt or not theme_prompt.strip():
                print("AI generation cancelled.")
                return None

            # 2. CALL THE MANAGER WITH THE THEME
            manager = DungeonContentManager(self.node, self.db, self.ai)
            success = manager.populate_descriptions(theme=theme_prompt)
            
            if success:
                return {"action": "reload_node"}
        else:
            print(f"AI Content Generation not implemented for node type: {self.node['type']}")
        return None

    def update(self):
        self.widgets = [self.btn_back, self.btn_tab_tools, self.btn_tab_info, self.btn_tab_config]
        ac, ic = (100, 100, 120), (60, 60, 70)
        self.btn_tab_tools.base_color = ac if self.active_tab == "TOOLS" else ic
        self.btn_tab_info.base_color = ac if self.active_tab == "INFO" else ic
        self.btn_tab_config.base_color = ac if self.active_tab == "CONFIG" else ic
        
        if self.active_tab == "TOOLS": self.widgets.extend(self.brush_buttons)
        elif self.active_tab == "INFO": self.widgets.extend(self.info_panel.widgets)
        elif self.active_tab == "CONFIG":
            self.widgets.extend([self.btn_reset_view, self.btn_regen, self.btn_gen_details])

    def handle_input(self, event, cam_x, cam_y, zoom):
        for w in self.widgets:
            res = w.handle_event(event)
            if res: return res if isinstance(res, dict) else None
        if self.active_tab == "INFO" and self.info_panel.handle_event(event): return None

        # --- NEW DRAG LOGIC ---
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and event.pos[0] > 260:
                if self.active_tab == "TOOLS":
                    # Keep painting functionality
                    self.painting = True
                    self._paint_tile(event.pos, cam_x, cam_y, zoom)
                else:
                    # Start dragging the map
                    self.dragging_map = True
                    self.drag_start_pos = event.pos
                    self.drag_start_cam = (cam_x, cam_y)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.painting = False
                self.dragging_map = False

        elif event.type == pygame.MOUSEMOTION:
            if self.painting:
                self._paint_tile(event.pos, cam_x, cam_y, zoom)
            elif self.dragging_map:
                dx = event.pos[0] - self.drag_start_pos[0]
                dy = event.pos[1] - self.drag_start_pos[1]
                # Return a 'pan' action to the main loop
                return {"action": "pan", "pos": (self.drag_start_cam[0] - dx / zoom, self.drag_start_cam[1] - dy / zoom)}
    
        return None
            
    def handle_input_old(self, event, cam_x, cam_y, zoom):
        for w in self.widgets:
            res = w.handle_event(event)
            if res: return res if isinstance(res, dict) else None
        if self.active_tab == "INFO" and self.info_panel.handle_event(event): return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if event.pos[0] > 260:
                if self.active_tab == "TOOLS":
                    self.painting = True; self._paint_tile(event.pos, cam_x, cam_y, zoom)
                else: 
                    return {"action": "click_zoom"}
        if event.type == pygame.MOUSEBUTTONUP: self.painting = False
        if event.type == pygame.MOUSEMOTION and self.painting: self._paint_tile(event.pos, cam_x, cam_y, zoom)
        return None
        
    def _paint_tile(self, screen_pos, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.render_strategy.cell_size * zoom
        c = int((screen_pos[0] - center_x) / sc + cam_x)
        r = int((screen_pos[1] - center_y) / sc + cam_y)
        if 0 <= c < self.render_strategy.width and 0 <= r < self.render_strategy.height:
            if self.grid_data[r][c] != self.active_brush:
                self.grid_data[r][c] = self.active_brush
                self._render_static_map()

    def _reset_view(self): return {"action": "reset_view"}
    def _regenerate_map(self): return {"action": "regenerate_tactical"}

    def draw_map(self, screen, cam_x, cam_y, zoom, screen_w, screen_h):
        if not self.static_map_surf: return
        center_x, center_y = screen_w // 2, screen_h // 2
        sc = self.render_strategy.cell_size
        scaled_w = int(self.static_map_surf.get_width() * zoom)
        scaled_h = int(self.static_map_surf.get_height() * zoom)
        draw_x = center_x - (cam_x * sc * zoom)
        draw_y = center_y - (cam_y * sc * zoom)
        if scaled_w > 0 and scaled_h > 0:
            scaled_surf = pygame.transform.scale(self.static_map_surf, (scaled_w, scaled_h))
            screen.blit(scaled_surf, (draw_x, draw_y))

    def draw_overlays(self, screen, cam_x, cam_y, zoom):
        if self.active_tab == "INFO": self.info_panel.draw(screen)
        self._draw_markers(screen, cam_x, cam_y, zoom)
        if self.hovered_marker: self._draw_tooltip(screen, pygame.mouse.get_pos())
    
    def _draw_markers(self, screen, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.render_strategy.cell_size * zoom
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_marker = None
        
        font_size = max(8, int(40 * zoom))
        try: font_room_num = pygame.font.Font(None, font_size)
        except: font_room_num = self.font_small

        for m in self.markers:
            if m.get('symbol') != 'room_number': continue
            sx = center_x + (m['world_x'] - cam_x) * sc
            sy = center_y + (m['world_y'] - cam_y) * sc
            if not (-sc <= sx <= SCREEN_WIDTH + sc and -sc <= sy <= SCREEN_HEIGHT + sc): continue
            
            surf = font_room_num.render(m['title'], True, COLOR_INK)
            rect = surf.get_rect(topleft=(sx, sy))
            if rect.inflate(10, 10).collidepoint(mouse_pos): self.hovered_marker = m
            screen.blit(surf, rect)

    def _draw_tooltip(self, screen, pos):
        m = self.hovered_marker
        import textwrap
        wrapped_lines = textwrap.wrap(m.get('description', 'No details'), width=40)
        rendered = [self.font_small.render(l, True, (20,20,20)) for l in wrapped_lines]
        mw = max(s.get_width() for s in rendered) if rendered else 0
        mh = sum(s.get_height() for s in rendered) + 10
        bg_rect = pygame.Rect(pos[0]+15, pos[1]+15, mw+20, mh)
        if bg_rect.right > SCREEN_WIDTH: bg_rect.x -= (bg_rect.width+30)
        pygame.draw.rect(screen, COLOR_PARCHMENT, bg_rect)
        pygame.draw.rect(screen, COLOR_INK, bg_rect, 1)
        y_off = 5
        for s in rendered:
            screen.blit(s, (bg_rect.x+10, bg_rect.y+y_off))
            y_off += s.get_height()

    def get_metadata_updates(self): return {}
    
    def cleanup(self):
        self.db.update_node_data(
            self.node['id'], 
            geometry={
                "grid": self.grid_data, 
                "width": self.render_strategy.width, 
                "height": self.render_strategy.height, 
                "footprints": self.node['geometry_data'].get('footprints', []),
                "rooms": [list(pygame.Rect(r)) for r in self.node['geometry_data'].get('rooms', [])]
            }
        )
