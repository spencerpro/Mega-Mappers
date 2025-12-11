import sys
import warnings
import os
import multiprocessing

warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

def player_window_process(image_queue):
    """Separate process for the player display window."""
    import pygame
    
    pygame.init()

    #pygame.event.set_allowed([pygame.QUIT])
    
    # Attempt to open on second display, otherwise create a large window
    try:
        if pygame.display.get_num_displays() > 1:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.NOFRAME, display=1)
        else:
            raise pygame.error("Only one display detected.")
    except pygame.error as e:
        print(f"Player Window: Falling back to windowed mode. Reason: {e}")
        screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

    pygame.display.set_caption("Player View")
    screen.fill((0, 0, 0))
    pygame.display.flip()
    
    clock = pygame.time.Clock()
    running = True
    
    initial_image = None
    current_image_surface = None

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                # Force a redraw on resize
                if current_image_surface:
                    scaled_image = pygame.transform.smoothscale(current_image_surface, screen.get_size())
                    screen.blit(scaled_image, (0, 0))
                    pygame.display.flip()

        if not image_queue.empty():
            data = image_queue.get()
            
            if data == "QUIT":
                running = False
            elif data == "REVERT":
                if initial_image:
                    current_image_surface = initial_image
                    scaled_image = pygame.transform.smoothscale(initial_image, screen.get_size())
                    screen.blit(scaled_image, (0, 0))
                    pygame.display.flip()
            elif isinstance(data, tuple):
                image_string, size = data
                try:
                    new_image = pygame.image.fromstring(image_string, size, 'RGB')
                    if not initial_image:
                        initial_image = new_image
                    
                    current_image_surface = new_image
                    scaled_image = pygame.transform.smoothscale(new_image, screen.get_size())
                    screen.blit(scaled_image, (0, 0))
                    pygame.display.flip()
                    pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
                except Exception as e:
                    print(f"Player Window Error: Failed to display surface: {e}")
        
        clock.tick(30)
    
    pygame.quit()

# Main process Pygame import
import pygame

from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT
from codex_engine.core.db_manager import DBManager
from codex_engine.core.theme_manager import ThemeManager
from codex_engine.ui.campaign_menu import CampaignMenu
from codex_engine.ui.map_viewer import MapViewer
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.local_gen import LocalGenerator
from codex_engine.generators.tactical_gen import TacticalGenerator

class CodexApp:
    def __init__(self):
        self.image_queue = multiprocessing.Queue()
        self.player_process = multiprocessing.Process(target=player_window_process, args=(self.image_queue,))
        self.player_process.start()
        
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("The Codex Engine - Alpha")
        self.clock = pygame.time.Clock()
        
        self.db = DBManager()
        self.theme_manager = ThemeManager()
        
        self.state = "MENU"
        self.current_campaign = None
        
        self.menu_screen = CampaignMenu(self.screen, self.db)
        self.map_viewer = None
        
        try:
            standby = pygame.image.load("data/player_standby.jpg").convert()
            self.update_player_image(standby)
        except Exception as e:
            print(f"Could not load standby image: {e}")
            self.update_player_image(pygame.Surface((1,1)))

    def update_player_image(self, image_surface):
        if not self.player_process.is_alive(): return
        image_string = pygame.image.tostring(image_surface, 'RGB')
        size = image_surface.get_size()
        self.image_queue.put((image_string, size))

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.VIDEORESIZE:
                     self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

                if self.state == "MENU":
                    self._handle_menu_input(event)
                elif self.state == "GAME_WORLD":
                    self._handle_game_input(event)

            if self.state == "MENU":
                self.menu_screen.draw()
            elif self.state == "GAME_WORLD":
                if self.map_viewer:
                    self.map_viewer.draw()
                
            pygame.display.flip()
            self.clock.tick(60)

        if self.map_viewer: 
            self.map_viewer.save_current_state()
        
        self.image_queue.put("QUIT")
        self.player_process.join(timeout=2)
        if self.player_process.is_alive():
            self.player_process.terminate()
        
        pygame.quit()
        sys.exit()

    def _handle_menu_input(self, event):
        result = self.menu_screen.handle_input(event)
        if result and result.get("action") == "load_campaign":
            self.load_campaign(result["id"], result["theme"])

    def _handle_game_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.go_up_level()
                return

        if event.type == pygame.MOUSEWHEEL:
            if self.map_viewer:
                self.map_viewer.handle_zoom(event.y, pygame.mouse.get_pos())
            return 

        if self.map_viewer:
            result = self.map_viewer.handle_input(event)
            if result:
                if result.get("action") == "update_player_view":
                    self.render_and_update_player_view()
                    return

                if result.get("action") == "enter_marker":
                    marker = result['marker']
                    if marker.get('metadata', {}).get('is_view_marker'):
                        is_active = not marker['metadata'].get('is_active', False)
                        marker['metadata']['is_active'] = is_active
                        self.db.update_marker(marker['id'], metadata=marker['metadata'])
                        
                        if is_active:
                            self.render_and_update_player_view()
                        else:
                            self.image_queue.put("REVERT")
                        return

                    current_type = self.map_viewer.current_node['type']
                    if current_type == 'world_map':
                        self.enter_local_map(marker)
                    elif current_type == 'local_map':
                        self.enter_tactical_map(marker)
                    else: 
                        self.transition_tactical_map(marker)

                elif result.get("action") == "go_up_level":
                    self.go_up_level()
                elif result.get("action") == "reset_view":
                    self.reset_tactical_view()
                elif result.get("action") == "regenerate_tactical":
                    self.regenerate_tactical_map()
                elif result.get("action") == "transition_node":
                    self.transition_to_node(result['node_id'])

    def render_and_update_player_view(self):
        print("\n--- RENDER PLAYER VIEW ---")
        if not self.map_viewer:
            print("  [ERROR] MapViewer not initialized. Aborting.")
            return
        if not self.map_viewer.controller:
            print("  [ERROR] Controller not initialized. Aborting.")
            return

        print("  [1] Calling controller's render_player_view_surface()...")
        player_surface = self.map_viewer.controller.render_player_view_surface()
        
        if player_surface:
            print(f"  [4] Controller returned a surface of size {player_surface.get_size()}.")
            self.update_player_image(player_surface)
            print("  [5] Surface sent to player window process.")
        else:
            print("  [4] Controller returned None. No update sent.")
        print("--- END RENDER ---")

    def render_and_update_player_view_old(self):
        if self.map_viewer and self.map_viewer.controller:
            player_surface = self.map_viewer.controller.render_player_view_surface()
            if player_surface:
                self.update_player_image(player_surface)

    def go_up_level(self):
        if not self.map_viewer or not self.map_viewer.current_node:
            self.state = "MENU"; return
        current_node = self.map_viewer.current_node
        parent_id = current_node.get('parent_node_id')
        if not parent_id:
            self.state = "MENU"; return
        
        source_marker_id = current_node['metadata'].get('source_marker_id')
        if source_marker_id:
             parent_markers = self.db.get_markers(parent_id)
             marker = next((m for m in parent_markers if m['id'] == source_marker_id), None)
             if marker:
                 current_meta = marker.get('metadata', {})
                 current_meta['portal_to'] = current_node['id']
                 self.db.update_marker(source_marker_id, metadata=current_meta)
        self.transition_to_node(parent_id)

    def transition_to_node(self, node_id):
        node = self.db.get_node(node_id)
        if node:
            if self.map_viewer: self.map_viewer.save_current_state()
            self.map_viewer.set_node(node)

    def transition_tactical_map(self, marker):
        portal_id = marker.get('metadata', {}).get('portal_to')
        if portal_id: self.transition_to_node(portal_id)

    def enter_local_map(self, marker):
        current_node = self.map_viewer.current_node
        target_x = int(marker['world_x']); target_y = int(marker['world_y'])
        existing_node = self.db.get_node_by_coords(self.current_campaign['id'], parent_id=current_node['id'], x=target_x, y=target_y)
        if existing_node:
            self.transition_to_node(existing_node['id'])
        else:
            self.display_loading_screen()
            gen = LocalGenerator(self.db)
            new_id = gen.generate_local_map(current_node, marker, self.current_campaign['id'])
            if new_id: self.transition_to_node(new_id)

    def enter_tactical_map(self, marker):
        portal_id = marker.get('metadata', {}).get('portal_to')
        if portal_id:
            self.transition_to_node(portal_id); return

        self.display_loading_screen()
        gen = TacticalGenerator(self.db)
        new_id = gen.generate_tactical_map(self.map_viewer.current_node, marker, self.current_campaign['id'])
        if new_id:
            new_meta = marker.get('metadata', {}); new_meta['portal_to'] = new_id
            self.db.update_marker(marker['id'], metadata=new_meta)
            self.transition_to_node(new_id)

    def reset_tactical_view(self):
        if not self.map_viewer: return
        node = self.map_viewer.current_node; geo = node.get('geometry_data', {})
        self.map_viewer.cam_x = geo.get('width', 30) / 2
        self.map_viewer.cam_y = geo.get('height', 30) / 2
        self.map_viewer.zoom = 1.0

    def regenerate_tactical_map(self):
        if not self.map_viewer or self.map_viewer.current_node['type'] not in ['dungeon_level', 'building_interior', 'tactical_map']: return
        current_node = self.map_viewer.current_node
        source_marker_id = current_node['metadata'].get('source_marker_id')
        parent_id = current_node['parent_node_id']
        if not source_marker_id or not parent_id:
            print("Cannot regenerate: Node is missing source marker link."); return
        
        # Delete all siblings
        siblings = self.db.get_structure_tree(current_node['id'])
        for sibling in siblings:
            self.db.delete_node_and_children(sibling['id'])
        
        # Reset source marker
        markers = self.db.get_markers(parent_id)
        source_marker = next((m for m in markers if m['id'] == source_marker_id), None)
        if source_marker:
            meta = source_marker.get('metadata', {})
            if 'portal_to' in meta: del meta['portal_to']
            self.db.update_marker(source_marker['id'], metadata=meta)
            self.transition_to_node(parent_id)
        else: self.go_up_level()

    def load_campaign(self, campaign_id, theme_id):
        self.current_campaign = self.db.get_campaign(campaign_id)
        self.theme_manager.load_theme(theme_id)
        if not self.map_viewer:
            self.map_viewer = MapViewer(self.screen, self.theme_manager)
        
        world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)
        if not world_node:
            self.display_loading_screen()
            generator = WorldGenerator(self.theme_manager, self.db)
            generator.generate_world_node(campaign_id)
            world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)

        if world_node:
            self.map_viewer.set_node(world_node)
            self.state = "GAME_WORLD"
        else:
            self.state = "MENU"

    def display_loading_screen(self, message="Generating..."):
        self.screen.fill((20, 20, 30))
        font = pygame.font.Font(None, 48)
        text = font.render(message, True, (200, 200, 200))
        rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
        self.screen.blit(text, rect)
        pygame.display.flip()

if __name__ == "__main__":
    # Required for macOS and Windows to use multiprocessing with Pygame
    if sys.platform.startswith('win') or sys.platform.startswith('darwin'):
        multiprocessing.set_start_method('spawn', force=True)
    app = CodexApp()
    app.run()
