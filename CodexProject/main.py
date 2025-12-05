
import sys
import warnings
import os

warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame

from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT
from codex_engine.core.db_manager import DBManager
from codex_engine.core.theme_manager import ThemeManager
from codex_engine.ui.campaign_menu import CampaignMenu
from codex_engine.ui.map_viewer import MapViewer
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.local_gen import LocalGenerator # NEW

class CodexApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("The Codex Engine - Alpha")
        self.clock = pygame.time.Clock()
        
        self.db = DBManager()
        self.theme_manager = ThemeManager()
        
        self.state = "MENU"
        self.current_campaign = None
        
        self.menu_screen = CampaignMenu(self.screen, self.db)
        self.map_viewer = None 

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
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

        pygame.quit()
        sys.exit()

    def _handle_menu_input(self, event):
        result = self.menu_screen.handle_input(event)
        if result and result.get("action") == "load_campaign":
            self.load_campaign(result["id"], result["theme"])

    def _handle_game_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Check if we can go up a level
                if self.map_viewer and self.map_viewer.current_node.get('parent_node_id'):
                    self.go_up_level()
                else:
                    print("Returning to Menu...")
                    self.state = "MENU"
                    self.current_campaign = None
                    self.menu_screen.refresh_list()
                return

        if self.map_viewer:
            result = self.map_viewer.handle_input(event)
            # Handle Transition Signal
            if result and result.get("action") == "enter_marker":
                self.enter_local_map(result['marker'])

    def go_up_level(self):
        parent_id = self.map_viewer.current_node['parent_node_id']
        # Load Parent Node
        # We need a method to get node by ID easily, for now re-use campaign loader logic or specific query
        # Hack for DB simplicity: we iterate or add query
        # Let's add a specific query in DBManager if not exists, or just use coords query with None parent
        # Actually DBManager has query by coords. 
        # But we have the ID. Let's just fetch by ID. 
        # Since DBManager doesn't expose get_node_by_id explicitly in provided file, we use existing query logic or add one.
        # Wait, get_node_by_coords uses parent_id. 
        # Let's just assume we reload the world map for now if parent is null.
        # For prototype: Just load world map again.
        print("Going up to World Map...")
        world_node = self.db.get_node_by_coords(self.current_campaign['id'], None, 0, 0)
        self.map_viewer.set_node(world_node)

    def enter_local_map(self, marker):
        print(f"Entering {marker['title']}...")
        
        # 1. Check if node exists (Search by exact coords and parent)
        existing_node = self.db.get_node_by_coords(
            self.current_campaign['id'], 
            parent_id=self.map_viewer.current_node['id'], 
            x=int(marker['world_x']), 
            y=int(marker['world_y'])
        )
        
        if existing_node:
            self.map_viewer.set_node(existing_node)
        else:
            # 2. Generate New Local Map
            self.display_loading_screen()
            gen = LocalGenerator(self.db)
            gen.generate_local_map(self.map_viewer.current_node, marker, self.current_campaign['id'])
            
            # Fetch newly created
            new_node = self.db.get_node_by_coords(
                self.current_campaign['id'], 
                parent_id=self.map_viewer.current_node['id'], 
                x=int(marker['world_x']), 
                y=int(marker['world_y'])
            )
            self.map_viewer.set_node(new_node)

    def load_campaign(self, campaign_id, theme_id):
        print(f"--- Loading Campaign ID: {campaign_id} ---")
        self.current_campaign = self.db.get_campaign(campaign_id)
        self.theme_manager.load_theme(theme_id)
        self.map_viewer = MapViewer(self.screen, self.theme_manager)
        
        world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)
        
        if not world_node:
            self.display_loading_screen()
            print("No world map found. Initializing World Generator...")
            generator = WorldGenerator(self.theme_manager, self.db)
            generator.generate_world_node(campaign_id)
            world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)

        if world_node:
            print(f"Loaded Node: {world_node.get('name')}")
            self.map_viewer.set_node(world_node)
            self.state = "GAME_WORLD"
        else:
            print("CRITICAL ERROR: Failed to load or generate world node.")
            self.state = "MENU"

    def display_loading_screen(self):
        self.screen.fill((20, 20, 30))
        font = pygame.font.Font(None, 48)
        text = font.render("Generating Terrain...", True, (200, 200, 200))
        rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
        self.screen.blit(text, rect)
        pygame.display.flip()

if __name__ == "__main__":
    app = CodexApp()
    app.run()
