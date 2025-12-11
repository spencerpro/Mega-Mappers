import pygame
import math
import random
from .base_renderer import BaseTacticalRenderer, COLOR_INK, COLOR_GRID, COLOR_PARCHMENT

# --- CONSTANTS ---
LINE_THICKNESS = 3
HATCH_SPACING = 12

def draw_hand_drawn_line(surface, start_pos, end_pos, color, thickness=1, wobble=2):
    distance = math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])
    if distance == 0: return
    segments = max(2, int(distance / 10))
    points = []
    for i in range(segments + 1):
        t = i / segments
        x = start_pos[0] * (1 - t) + end_pos[0] * t
        y = start_pos[1] * (1 - t) + end_pos[1] * t
        if 0 < i < segments:
            angle = math.atan2(end_pos[1] - start_pos[1], end_pos[0] - start_pos[0]) + math.pi / 2
            x += random.uniform(-wobble, wobble) * math.cos(angle)
            y += random.uniform(-wobble, wobble) * math.sin(angle)
        points.append((x, y))
    for _ in range(thickness):
        stroke_points = [(p[0] + random.uniform(-wobble/2, wobble/2), p[1] + random.uniform(-wobble/2, wobble/2)) for p in points]
        pygame.draw.aalines(surface, color, False, stroke_points)

def draw_straight_line(surface, start_pos, end_pos, color, thickness=1):
    pygame.draw.line(surface, color, start_pos, end_pos, thickness)

class TacticalRenderer(BaseTacticalRenderer):
    def __init__(self, node_data, cell_size, style='hand_drawn'):
        super().__init__(node_data, cell_size)
        self.style = style
        self.rooms = [pygame.Rect(r) for r in self.geometry.get('rooms', [])]
        self.footprints = self.geometry.get('footprints', [])

    def render(self):
        # 1. Base Surface (Parchment)
        surface = super().render()
        sc = self.cell_size
        
        # 2. Config based on Style
        is_blueprint = (self.style == 'blueprint')
        line_color = (0, 0, 255) if is_blueprint else COLOR_INK
        draw_line_func = draw_straight_line if is_blueprint else draw_hand_drawn_line
        
        # 3. Draw Grid Lines
        grid_color = COLOR_GRID if not is_blueprint else (200, 200, 255)
        for y in range(self.height):
             draw_straight_line(surface, (0, y * sc), (self.width * sc, y * sc), grid_color, 1)
        for x in range(self.width):
             draw_straight_line(surface, (x * sc, 0), (x * sc, self.height * sc), grid_color, 1)

        # 4. Draw Geometry: GRIDS (Dungeons)
        # We only draw walls if the grid has data
        for y in range(self.height):
            for x in range(self.width):
                if self.grid_data[y][x] != 0:
                    sx, sy = x * sc, y * sc
                    # Draw walls based on neighbors
                    if y == 0 or self.grid_data[y-1][x] == 0: 
                        draw_line_func(surface, (sx, sy), (sx+sc, sy), line_color, LINE_THICKNESS)
                    if y == self.height-1 or self.grid_data[y+1][x] == 0: 
                        draw_line_func(surface, (sx, sy+sc), (sx+sc, sy+sc), line_color, LINE_THICKNESS)
                    if x == 0 or self.grid_data[y][x-1] == 0: 
                        draw_line_func(surface, (sx, sy), (sx, sy+sc), line_color, LINE_THICKNESS)
                    if x == self.width-1 or self.grid_data[y][x+1] == 0: 
                        draw_line_func(surface, (sx+sc, sy), (sx+sc, sy+sc), line_color, LINE_THICKNESS)

        # 5. Draw Geometry: FOOTPRINTS (Buildings)
        for fp in self.footprints:
            fx = fp['x'] * sc
            fy = fp['y'] * sc
            fw = fp['w'] * sc
            fh = fp['h'] * sc
            
            # Draw Outline
            if is_blueprint:
                pygame.draw.rect(surface, (0, 0, 255), (fx, fy, fw, fh), 4)
            else:
                # Hand-drawn box
                tl, tr = (fx, fy), (fx+fw, fy)
                bl, br = (fx, fy+fh), (fx+fw, fy+fh)
                draw_line_func(surface, tl, tr, line_color, 4)
                draw_line_func(surface, tr, br, line_color, 4)
                draw_line_func(surface, br, bl, line_color, 4)
                draw_line_func(surface, bl, tl, line_color, 4)

        # 6. Hatching (Optional: Only for hand-drawn dungeons)
        if not is_blueprint and self.rooms:
             for r in self.rooms:
                screen_rect = pygame.Rect(r.x * sc, r.y * sc, r.width * sc, r.height * sc)
                for i in range(screen_rect.left - screen_rect.height, screen_rect.right, HATCH_SPACING):
                    start_pos = (i, screen_rect.top)
                    end_pos = (i + screen_rect.height, screen_rect.bottom)
                    clipped = screen_rect.clipline(start_pos, end_pos)
                    if clipped:
                        pygame.draw.aaline(surface, (225, 215, 195), clipped[0], clipped[1])

        return surface
