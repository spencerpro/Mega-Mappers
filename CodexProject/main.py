import sys
import warnings
import os

# Filter out the Pygame 'pkg_resources' deprecation warning.
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame

# Configuration
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT

# Core Systems
from codex_engine.core.db_manager import DBManager
from codex_engine.core.theme_manager import ThemeManager

# UI & Rendering
from codex_engine.ui.campaign_menu import CampaignMenu
from codex_engine.ui.map_viewer import MapViewer

# Generators
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.local_gen import LocalGenerator

class CodexApp:
    def __init__(self):
        # 1. Low-Level Initialization
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("The Codex Engine - Alpha")
        self.clock = pygame.time.Clock()
        
        # 2. Data Subsystems
        self.db = DBManager()
        self.theme_manager = ThemeManager()
        
        # 3. Application State
        self.state = "MENU" # States: MENU, GAME_WORLD, LOADING
        self.current_campaign = None
        
        # 4. View Controllers
        self.menu_screen = CampaignMenu(self.screen, self.db)
        self.map_viewer = None # Initialized only when a campaign is loaded

    def run(self):
        """The Main Application Loop"""
        running = True
        
        while running:
            # --- EVENT HANDLING ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                # Route events based on current state
                if self.state == "MENU":
                    self._handle_menu_input(event)
                elif self.state == "GAME_WORLD":
                    self._handle_game_input(event)

            # --- RENDERING ---
            if self.state == "MENU":
                self.menu_screen.draw()
            
            elif self.state == "GAME_WORLD":
                if self.map_viewer:
                    self.map_viewer.draw()
                
            # Update Display
            pygame.display.flip()
            self.clock.tick(60)

        # Cleanup
        pygame.quit()
        sys.exit()

    def _handle_menu_input(self, event):
        """Delegates input to the Menu Controller"""
        result = self.menu_screen.handle_input(event)
        
        # Did the menu ask us to do something?
        if result and result.get("action") == "load_campaign":
            self.load_campaign(result["id"], result["theme"])

    def _handle_game_input(self, event):
        """Delegates input to the Map Viewer"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Hierarchy Navigation
                if self.map_viewer and self.map_viewer.current_node.get('parent_node_id'):
                    self.go_up_level()
                else:
                    # Save state before exiting
                    if self.map_viewer: self.map_viewer.save_current_state()
                    
                    print("Returning to Menu...")
                    self.state = "MENU"
                    self.current_campaign = None
                    self.menu_screen.refresh_list()
                return

        # Pass event to the universal map viewer
        if self.map_viewer:
            result = self.map_viewer.handle_input(event)
            
            # Check for Transition Signals (Zooming into Local Map)
            if result and result.get("action") == "enter_marker":
                self.enter_local_map(result['marker'])

    def go_up_level(self):
        """Returns to the Parent Node (e.g. Battle -> Local -> World)"""
        if not self.map_viewer.current_node.get('parent_node_id'):
            return

        parent_id = self.map_viewer.current_node['parent_node_id']
        print(f"Going up to Parent Node ID: {parent_id}")
        
        # Fetch the actual parent node using the new DB function
        parent_node = self.db.get_node(parent_id)
        
        if parent_node:
            self.map_viewer.save_current_state() # Save current level state
            self.map_viewer.set_node(parent_node)
        else:
            print(f"CRITICAL ERROR: Parent Node {parent_id} not found in database.")

    def go_up_level_old(self):
        """Returns to the Parent Node (e.g. Local Map -> World Map)"""
        parent_id = self.map_viewer.current_node['parent_node_id']
        print(f"Going up to Parent Node ID: {parent_id}")
        
        # We need to find the node by ID.
        # Since DBManager.get_node_by_coords relies on coords/parent logic, 
        # we can just use the coords query with parent=None to find the World Map
        # assuming 1 level of depth for now.
        
        # Better: Query specifically for ID.
        # Since we don't have get_node_by_id exposed in the snippet, we rely on the World Map being at 0,0 root.
        world_node = self.db.get_node_by_coords(self.current_campaign['id'], None, 0, 0)
        
        if world_node:
            self.map_viewer.save_current_state() # Save local state before leaving
            self.map_viewer.set_node(world_node)
        else:
            print("Error: Could not find World Map.")

    def enter_local_map(self, marker):
        """
        Transition Logic:
        1. World Map -> Local Map (Generate/Load)
        2. Local Map -> Battle/Dungeon Map (Create/Load)
        """
        print(f"--- Transition Request: {marker['title']} ---")
        
        current_node = self.map_viewer.current_node
        target_x = int(marker['world_x'])
        target_y = int(marker['world_y'])

        # --- CASE 1: Going from World to Local ---
        if current_node['type'] == 'world_map':
            # Check DB
            existing_node = self.db.get_node_by_coords(
                self.current_campaign['id'], 
                parent_id=current_node['id'], 
                x=target_x, 
                y=target_y
            )
            
            if existing_node:
                print("Loading existing local map...")
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(existing_node)
            else:
                print("Generating NEW local map...")
                self.display_loading_screen()
                
                gen = LocalGenerator(self.db)
                gen.generate_local_map(current_node, marker, self.current_campaign['id'])
                
                new_node = self.db.get_node_by_coords(
                    self.current_campaign['id'], 
                    current_node['id'], 
                    target_x, target_y
                )
                
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(new_node)

        # --- CASE 2: Going from Local to Battle/Dungeon (Layer 3) ---
        elif current_node['type'] == 'local_map':
            # Check DB
            existing_node = self.db.get_node_by_coords(
                self.current_campaign['id'], 
                parent_id=current_node['id'], 
                x=target_x, 
                y=target_y
            )

            if existing_node:
                print("Loading existing battle map...")
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(existing_node)
            else:
                print("Creating NEW battle map node...")
                # Determine type
                node_type = "dungeon" if "dungeon" in marker['symbol'] or "skull" in marker['symbol'] else "building"
                
                # Create Node (No generator yet, just empty node)
                new_id = self.db.create_node(
                    self.current_campaign['id'], 
                    node_type, 
                    current_node['id'], 
                    target_x, target_y, 
                    marker['title']
                )
                
                # Set basic metadata so renderer doesn't crash
                self.db.update_node_data(new_id, geometry={}, metadata={"grid_size": 32, "sea_level": -9999})
                
                new_node = self.db.get_node_by_coords(
                    self.current_campaign['id'], 
                    current_node['id'], 
                    target_x, target_y
                )
                
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(new_node)

    def enter_local_map_old(self, marker):
        """
        Transition Logic:
        1. Checks if a child map already exists for this marker.
        2. If yes, load it.
        3. If no, Generate it (Extract Terrain + Imprint Vectors + Populate).
        """
        print(f"--- Transition Request: {marker['title']} ---")
        
        # Prevent infinite recursion for now
        if self.map_viewer.current_node['type'] == 'local_map':
            print("Already in local map. Nesting limit reached.")
            return

        target_x = int(marker['world_x'])
        target_y = int(marker['world_y'])
        
        # Check DB
        existing_node = self.db.get_node_by_coords(
            self.current_campaign['id'], 
            parent_id=self.map_viewer.current_node['id'], 
            x=target_x, 
            y=target_y
        )
        
        if existing_node:
            print("Loading existing local map...")
            self.map_viewer.save_current_state() # Save world state
            self.map_viewer.set_node(existing_node)
        else:
            print("Generating NEW local map...")
            self.display_loading_screen()
            
            gen = LocalGenerator(self.db)
            # This generates the file, saves it, creates DB vector records, and DB markers
            new_node_id = gen.generate_local_map(self.map_viewer.current_node, marker, self.current_campaign['id'])
            
            # Fetch the newly created node
            new_node = self.db.get_node_by_coords(
                self.current_campaign['id'], 
                self.map_viewer.current_node['id'], 
                target_x, target_y
            )
            
            self.map_viewer.save_current_state() # Save world state
            self.map_viewer.set_node(new_node)

    def load_campaign(self, campaign_id, theme_id):
        """
        The Logic Core:
        1. Loads Campaign Data
        2. Sets the Theme
        3. Checks for existing World Map (Persistence)
        4. If missing, triggers procedural generation
        5. Switches View
        """
        print(f"--- Loading Campaign ID: {campaign_id} ---")
        
        # 1. Setup Data
        self.current_campaign = self.db.get_campaign(campaign_id)
        self.theme_manager.load_theme(theme_id)
        
        # 2. Initialize the Universal Map Viewer
        self.map_viewer = MapViewer(self.screen, self.theme_manager)
        
        # 3. 'Schrödinger's Map' Logic
        world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)
        
        if not world_node:
            self.display_loading_screen()
            
            # GENERATION STEP
            print("No world map found. Initializing World Generator...")
            generator = WorldGenerator(self.theme_manager, self.db)
            
            # This function runs Noise + AI and saves to DB
            generator.generate_world_node(campaign_id)
            
            # Fetch the newly created node
            world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)

        # 4. Inject Data into Viewer
        if world_node:
            print(f"Loaded Node: {world_node.get('name')}")
            self.map_viewer.set_node(world_node)
            self.state = "GAME_WORLD"
        else:
            print("CRITICAL ERROR: Failed to load or generate world node.")
            self.state = "MENU"

    def display_loading_screen(self):
        """Forces a render pass to show loading text."""
        self.screen.fill((20, 20, 30))
        
        font = pygame.font.Font(None, 48)
        text = font.render("Generating Terrain...", True, (200, 200, 200))
        subtext = pygame.font.Font(None, 24).render("Calculating Erosion & Vector Imprints...", True, (150, 150, 150))
        
        rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 20))
        sub_rect = subtext.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 30))
        
        self.screen.blit(text, rect)
        self.screen.blit(subtext, sub_rect)
        pygame.display.flip()

if __name__ == "__main__":
    app = CodexApp()
    app.run()
