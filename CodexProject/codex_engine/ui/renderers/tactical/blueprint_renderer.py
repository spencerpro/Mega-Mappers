import pygame
from .base_renderer import BaseTacticalRenderer, COLOR_GRID

class BlueprintRenderer(BaseTacticalRenderer):
    def render(self):
        surface = super().render()
        sc = self.cell_size

        # Draw thin grid lines everywhere
        for y in range(self.height):
            for x in range(self.width):
                pygame.draw.rect(surface, COLOR_GRID, (x * sc, y * sc, sc, sc), 1)
        
        # Draw the blue box outlines from the footprints data
        footprints = self.geometry.get('footprints', [])
        for fp in footprints:
            fx = fp['x'] * sc
            fy = fp['y'] * sc
            fw = fp['w'] * sc
            fh = fp['h'] * sc
            color = fp.get('color', 'blue') # Allow blueprint to define color
            pygame.draw.rect(surface, color, (fx, fy, fw, fh), 2)
            
        return surface
