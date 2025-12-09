from .building_gen import BuildingGenerator
from .dungeon_gen import DungeonGenerator

class TacticalGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.building_gen = BuildingGenerator(db_manager)
        self.dungeon_gen = DungeonGenerator(db_manager)

    def generate_tactical_map(self, parent_node, marker, campaign_id):
        """
        Dispatches generation to the correct module based on marker metadata.
        """
        # 1. Check for Blueprint (Deterministic Building)
        if marker['metadata'].get('blueprint_id'):
            print(f"--- Dispatching {marker['title']} to BuildingGenerator ---")
            return self.building_gen.generate(parent_node, marker, campaign_id)
        
        # 2. Check for Dungeon Tags (Procedural Dungeon)
        elif "skull" in marker['symbol'] or "dungeon" in marker['title'].lower():
            print(f"--- Dispatching {marker['title']} to DungeonGenerator ---")
            # Default to 3 levels for now, or read from metadata
            depth = marker['metadata'].get('dungeon_depth', 3) 
            return self.dungeon_gen.generate_dungeon_complex(parent_node, marker, campaign_id, levels=depth)

        # 3. Fallback / Default
        else:
            print("--- Unknown type, defaulting to simple generic room ---")
            return self.dungeon_gen.generate_single_room(parent_node, marker, campaign_id)
