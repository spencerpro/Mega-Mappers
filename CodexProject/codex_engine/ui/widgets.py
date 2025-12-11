import pygame

class SimpleDropdown:
    def __init__(self, x, y, w, h, font, options, initial_val=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.options = options # List of strings
        self.is_open = False
        self.selected_idx = -1
        if initial_val and initial_val in options:
            self.selected_idx = options.index(initial_val)
        
        self.color_bg = (60, 60, 80)
        self.color_border = (100, 100, 120)
        self.color_hover = (90, 90, 110)

    def get_selected_id(self):
        return self.options[self.selected_idx]

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_open:
                for i in range(len(self.options)):
                    opt_rect = pygame.Rect(self.rect.x, self.rect.bottom + (i * 30), self.rect.width, 30)
                    if opt_rect.collidepoint(event.pos):
                        self.selected_idx = i
                        self.is_open = False
                        return True
                self.is_open = False
            else:
                if self.rect.collidepoint(event.pos):
                    self.is_open = True
                    return True
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, self.color_bg, self.rect)
        pygame.draw.rect(surface, self.color_border, self.rect, 1)

        if self.selected_idx == -1:
            text = "Choose a Theme..."
            color = (180, 180, 180) # Greyed out
        else:
            text = self.options[self.selected_idx].title()
            color = (255, 255, 255)
        
        surf = self.font.render(text, True, (255, 255, 255))
        surface.blit(surf, (self.rect.x + 10, self.rect.y + 8))
        
        pygame.draw.polygon(surface, (200, 200, 200), [
            (self.rect.right - 20, self.rect.y + 12),
            (self.rect.right - 10, self.rect.y + 12),
            (self.rect.right - 15, self.rect.y + 22)
        ])

        if self.is_open:
            list_h = len(self.options) * 30
            list_rect = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, list_h)
            pygame.draw.rect(surface, (25, 25, 30), list_rect)
            pygame.draw.rect(surface, self.color_border, list_rect, 1)
            mx, my = pygame.mouse.get_pos()
            for i, opt in enumerate(self.options):
                r = pygame.Rect(self.rect.x, self.rect.bottom + (i * 30), self.rect.width, 30)
                if r.collidepoint((mx, my)):
                    pygame.draw.rect(surface, self.color_hover, r)
                txt = self.font.render(opt.title(), True, (220, 220, 220))
                surface.blit(txt, (r.x + 10, r.y + 8))

class Button:
    def __init__(self, x, y, w, h, text, font, base_color, hover_color, text_color, action=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.action = action
        self.is_hovered = False
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION: self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovered and self.action: return self.action()
        return None
    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(surface, (0,0,0), self.rect, 2, border_radius=5)
        txt_surf = self.font.render(self.text, True, self.text_color)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surface.blit(txt_surf, txt_rect)

class InputBox:
    def __init__(self, x, y, w, h, font, text=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.color_inactive = pygame.Color('lightskyblue3')
        self.color_active = pygame.Color('dodgerblue2')
        self.color = self.color_inactive
        self.text = text
        self.font = font
        self.txt_surface = self.font.render(text, True, self.color)
        self.active = False
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos): self.active = not self.active
            else: self.active = False
            self.color = self.color_active if self.active else self.color_inactive
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN: return self.text
                elif event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
                else: self.text += event.unicode
                self.txt_surface = self.font.render(self.text, True, self.color)
    def draw(self, surface):
        surface.blit(self.txt_surface, (self.rect.x+5, self.rect.y+5))
        pygame.draw.rect(surface, self.color, self.rect, 2)

class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, initial_val, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.label = label
        self.font = pygame.font.Font(None, 24)
        self.dragging = False
        self.handle_w = 15
        self.update_handle()
    def update_handle(self):
        if (self.max_val - self.min_val) == 0: ratio = 0
        else: ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.rect.x + (self.rect.width * ratio) - (self.handle_w / 2)
        self.handle_rect = pygame.Rect(handle_x, self.rect.y - 5, self.handle_w, self.rect.height + 10)
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos) or self.rect.collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP: self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                rel_x = event.pos[0] - self.rect.x
                rel_x = max(0, min(rel_x, self.rect.width))
                ratio = rel_x / self.rect.width
                self.value = self.min_val + (ratio * (self.max_val - self.min_val))
                self.update_handle()
    def draw(self, surface):
        lbl = self.font.render(f"{self.label}: {self.value:.2f}", True, (200, 200, 200))
        surface.blit(lbl, (self.rect.x, self.rect.y - 20))
        pygame.draw.rect(surface, (100, 100, 100), self.rect, border_radius=5)
        color = (200, 200, 200) if not self.dragging else (255, 255, 255)
        pygame.draw.rect(surface, color, self.handle_rect, border_radius=3)

class Dropdown:
    def __init__(self, x, y, w, h, font, options, initial_id=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.options = options # List of dicts {'id': 'x', 'name': 'Y'}
        self.is_open = False
        self.selected_idx = -1
        
        # Find initial selection
        if initial_id:
            for i, opt in enumerate(options):
                if opt['id'] == initial_id:
                    self.selected_idx = i
                    break
        
        # Style
        self.color_bg = (30, 30, 40)
        self.color_border = (100, 100, 120)
        self.color_hover = (60, 60, 80)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_open:
                # Check clicks in the dropdown list
                for i in range(len(self.options)):
                    # Calculate rect for this option
                    opt_rect = pygame.Rect(self.rect.x, self.rect.bottom + (i * 30), self.rect.width, 30)
                    if opt_rect.collidepoint(event.pos):
                        self.selected_idx = i
                        self.is_open = False
                        return True
                # Click outside closes it
                self.is_open = False
            else:
                # Toggle open
                if self.rect.collidepoint(event.pos):
                    self.is_open = True
                    return True
        return False

    def get_selected_id(self):
        if self.selected_idx >= 0 and self.selected_idx < len(self.options):
            return self.options[self.selected_idx]['id']
        return None

    def draw(self, surface):
        pygame.draw.rect(surface, self.color_bg, self.rect)
        pygame.draw.rect(surface, self.color_border, self.rect, 1)
        
        text = "Select Blueprint..."
        if self.selected_idx >= 0:
            text = self.options[self.selected_idx]['name']
        
        surf = self.font.render(text, True, (255, 255, 255))
        surface.blit(surf, (self.rect.x + 5, self.rect.y + 8))
        
        pygame.draw.polygon(surface, (200, 200, 200), [
            (self.rect.right - 15, self.rect.y + 10),
            (self.rect.right - 5, self.rect.y + 10),
            (self.rect.right - 10, self.rect.y + 20)
        ])

        if self.is_open:
            list_h = len(self.options) * 30
            list_rect = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, list_h)
            pygame.draw.rect(surface, (25, 25, 30), list_rect)
            pygame.draw.rect(surface, self.color_border, list_rect, 1)
            
            mx, my = pygame.mouse.get_pos()
            
            for i, opt in enumerate(self.options):
                r = pygame.Rect(self.rect.x, self.rect.bottom + (i * 30), self.rect.width, 30)
                if r.collidepoint((mx, my)):
                    pygame.draw.rect(surface, self.color_hover, r)
                
                prefix = ""
                if opt.get('category') == 'Complex': prefix = "[C] "
                elif opt.get('id') is None: prefix = ""
                
                label = prefix + opt['name']
                
                txt = self.font.render(label, True, (220, 220, 220))
                surface.blit(txt, (r.x + 5, r.y + 8))

class ContextMenu:
    def __init__(self, x, y, options, font):
        self.options = options  # List of tuples: ("Label", callback_function)
        self.font = font
        self.item_height = 30
        
        # Calculate dimensions
        max_width = max(font.size(opt[0])[0] for opt in options) + 20
        self.rect = pygame.Rect(x, y, max_width, len(options) * self.item_height)
        
        # Style
        self.bg_color = (40, 40, 50)
        self.border_color = (100, 100, 120)
        self.hover_color = (60, 60, 80)
        self.text_color = (220, 220, 220)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                # Click is inside the menu, find which item
                item_index = (event.pos[1] - self.rect.y) // self.item_height
                if 0 <= item_index < len(self.options):
                    self.options[item_index][1]() # Call the callback function
                return True # Event handled, close menu
            else:
                # Click is outside, close menu
                return True 
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 1)
        
        mx, my = pygame.mouse.get_pos()

        for i, (label, _) in enumerate(self.options):
            item_rect = pygame.Rect(self.rect.x, self.rect.y + i * self.item_height, self.rect.width, self.item_height)
            
            # Skip drawing/interaction for separator
            if label == "":
                continue

            if item_rect.collidepoint(mx, my):
                pygame.draw.rect(surface, self.hover_color, item_rect)
            
            text_surf = self.font.render(label, True, self.text_color)
            surface.blit(text_surf, (item_rect.x + 10, item_rect.y + 7))
        
        """
        for i, (label, _) in enumerate(self.options):
            item_rect = pygame.Rect(self.rect.x, self.rect.y + i * self.item_height, self.rect.width, self.item_height)
            if item_rect.collidepoint(mx, my):
                pygame.draw.rect(surface, self.hover_color, item_rect)
            
            text_surf = self.font.render(label, True, self.text_color)
            surface.blit(text_surf, (item_rect.x + 10, item_rect.y + 7))
"""

class StructureBrowser:
    def __init__(self, x, y, w, h, db, current_node_id, font, on_navigate):
        self.rect = pygame.Rect(x, y, w, h)
        self.db = db
        self.font = font
        self.on_navigate = on_navigate
        self.scroll_y = 0
        
        # Get full tree
        full_data = self.db.get_structure_tree(current_node_id)
        
        self.structure_data = full_data
        
        self.buttons = []
        btn_h = 30
        
        for i, item in enumerate(self.structure_data):
            indent = (item['depth'] - 1) * 15 # Adjust indent since we skipped root
            if indent < 0: indent = 0
            
            bx = x + indent
            bw = w - indent - 10
            by = y + (i * (btn_h + 5))
            
            label = item['name']
            if item['type'] == 'dungeon_level': 
                label = f"💀 {label}"
            elif item['type'] == 'building_interior':
                label = f"└ {label}"
            else: 
                label = f"• {label}"
            
            base_col = (100, 150, 100) if item['is_current'] else (60, 60, 70)
            
            btn = Button(
                bx, by, bw, btn_h, 
                label, font, 
                base_col, (90, 90, 110), (255, 255, 255),
                lambda nid=item['id']: self.on_navigate(nid)
            )
            self.buttons.append(btn)

    def handle_event(self, event):
        for btn in self.buttons:
            res = btn.handle_event(event)
            if res: return res
        return None

    def draw(self, surface):
        surface.set_clip(self.rect)
        for btn in self.buttons:
            btn.draw(surface)
        surface.set_clip(None)

class StructureBrowser_old:
    def __init__(self, x, y, w, h, db, current_node_id, font, on_navigate):
        self.rect = pygame.Rect(x, y, w, h)
        self.db = db
        self.font = font
        self.on_navigate = on_navigate
        self.scroll_y = 0
        
        # Fetch Data
        self.structure_data = self.db.get_structure_tree(current_node_id)
        
        # Create Buttons for each node
        self.buttons = []
        btn_h = 30
        
        for i, item in enumerate(self.structure_data):
            # Indent based on depth
            indent = item['depth'] * 15
            bx = x + indent
            bw = w - indent - 10
            by = y + (i * (btn_h + 5))
            
            # Visuals
            label = item['name']
            if item['type'] == 'compound': label = f"🏠 {label}"
            elif item['type'] == 'dungeon_level': label = f"💀 {label}"
            else: label = f"└ {label}"
            
            # Highlight current node
            base_col = (100, 150, 100) if item['is_current'] else (60, 60, 70)
            
            btn = Button(
                bx, by, bw, btn_h, 
                label, font, 
                base_col, (90, 90, 110), (255, 255, 255),
                lambda nid=item['id']: self.on_navigate(nid)
            )
            # Store relative Y for scrolling later if needed
            btn.rel_y = (i * (btn_h + 5))
            self.buttons.append(btn)

    def handle_event(self, event):
        # (Simple scrolling could be added here similar to InfoPanel)
        for btn in self.buttons:
            res = btn.handle_event(event)
            if res: return res # The lambda triggers navigation
        return None

    def draw(self, surface):
        # Clip to area
        surface.set_clip(self.rect)
        # Optional: draw background
        # pygame.draw.rect(surface, (30,30,35), self.rect)
        for btn in self.buttons:
            btn.draw(surface)
        surface.set_clip(None)

