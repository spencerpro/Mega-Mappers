import pygame
import math
import random
from .base_renderer import BaseTacticalRenderer, COLOR_INK, COLOR_GRID

# --- CONSTANTS FOR DUNGEON AESTHETICS ---
LINE_THICKNESS = 3
HATCH_SPACING = 12
WOBBLE = 2

def draw_hand_drawn_line(surface, start_pos, end_pos, color, thickness=1, wobble=WOBBLE):
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

class DungeonRenderer(BaseTacticalRenderer):
    def __init__(self, node_data, cell_size):
        super().__init__(node_data, cell_size)
        # The renderer needs to know about room rectangles for hatching
        self.rooms = [pygame.Rect(r) for r in self.geometry.get('rooms', [])]

    def render(self):
        # 1. Get the base parchment surface with texture from the parent class
        surface = super().render()
        sc = self.cell_size

        # 2. DRAW ROOM HATCHING (The "darkening" inside rooms)
        for r in self.rooms:
            screen_rect = pygame.Rect(r.x * sc, r.y * sc, r.width * sc, r.height * sc)
            for i in range(screen_rect.left - screen_rect.height, screen_rect.right, HATCH_SPACING):
                start_pos = (i, screen_rect.top)
                end_pos = (i + screen_rect.height, screen_rect.bottom)
                clipped = screen_rect.clipline(start_pos, end_pos)
                if clipped:
                    pygame.draw.aaline(surface, (225, 215, 195), clipped[0], clipped[1])

        # 3. DRAW THIN GRID & THICK WALLS
        for y in range(self.height):
            for x in range(self.width):
                sx, sy = x * sc, y * sc
                
                # Draw thin grid lines for all non-void tiles
                if self.grid_data[y][x] > 0:
                    pygame.draw.rect(surface, COLOR_GRID, (sx, sy, sc, sc), 1)
                
                # Draw thick, hand-drawn walls based on neighboring void tiles
                if self.grid_data[y][x] != 0:
                    if y == 0 or self.grid_data[y-1][x] == 0: 
                        draw_hand_drawn_line(surface, (sx, sy), (sx+sc, sy), COLOR_INK, LINE_THICKNESS)
                    if y == self.height-1 or self.grid_data[y+1][x] == 0: 
                        draw_hand_drawn_line(surface, (sx, sy+sc), (sx+sc, sy+sc), COLOR_INK, LINE_THICKNESS)
                    if x == 0 or self.grid_data[y][x-1] == 0: 
                        draw_hand_drawn_line(surface, (sx, sy), (sx, sy+sc), COLOR_INK, LINE_THICKNESS)
                    if x == self.width-1 or self.grid_data[y][x+1] == 0: 
                        draw_hand_drawn_line(surface, (sx+sc, sy), (sx+sc, sy+sc), COLOR_INK, LINE_THICKNESS)
                        
        return surface
