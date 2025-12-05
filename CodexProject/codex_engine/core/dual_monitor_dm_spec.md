# Dual Monitor Campaign Manager - Design Specification

## Executive Summary

A comprehensive tabletop RPG campaign management system utilizing procedurally generated fractal world maps, hierarchical location generation, and dual-monitor display architecture. The system separates DM control/private information from player-visible tactical displays, enabling seamless in-person or hybrid gameplay with dynamic map generation, fog of war, and persistent campaign state.

---

## System Architecture

### Core Components

#### 1. **World State Manager** (Central Authority)
- Maintains single source of truth for all campaign data
- Manages hierarchical map structure (World → Region → Town → Dungeon → Room)
- Handles database persistence and state synchronization
- Broadcasts state changes to both display windows
- Manages session state, undo/redo history

#### 2. **DM Control Window** (Primary Display)
- Full-featured interface for campaign management
- Access to all hidden information, notes, and controls
- World generation and editing tools
- NPC/encounter management
- Campaign metadata and session logs

#### 3. **Player Display Window** (Secondary/Projector)
- Clean, UI-minimal tactical view
- Shows only revealed information
- Optimized for readability at distance
- No chrome, buttons, or DM tools visible
- Scales to arbitrary display sizes

#### 4. **Heightmap Extraction Engine**
- Extracts regions from world-scale fractal heightmaps
- Upscales to local detail resolution
- Applies consistent water levels across scales
- Caches regions for performance

#### 5. **Content Generation Service**
- LLM-based procedural generation of locations
- Returns structured JSON for parsing
- Context-aware (uses terrain, nearby locations, campaign themes)
- Maintains consistency through coordinate-based seeding

---

## Display Architecture

### DM Control Window Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [Campaign: The Sundered Realms]    Session: 12    [⚙ Menu] │
├──────────────────┬──────────────────────────────────────────┤
│                  │                                          │
│  SIDEBAR         │         PRIMARY MAP VIEW                 │
│  (250px)         │         (Resizable)                      │
│                  │                                          │
│ [World Controls] │  • Fractal world map with lighting      │
│  - Sea Level     │  • ALL markers visible (public+secret)  │
│  - Light Dir     │  • Hex/square grid overlay              │
│  - Light Height  │  • Camera controls (pan/zoom)           │
│  - Light Power   │  • Right-click context menus            │
│  - Grid Size     │  • Selection tools                      │
│                  │  • Measurement tools                    │
│ [Generation]     │                                          │
│  - New Map       │  [Minimap overlay in corner]            │
│  - Add Marker    │                                          │
│  - Gen Location  │                                          │
│                  │                                          │
│ [Fog of War]     │                                          │
│  - Reveal Mode   │                                          │
│  - Hide Mode     │                                          │
│  - Clear All     │                                          │
│  - Save State    │                                          │
│                  │                                          │
│ [Layer Toggles]  │                                          │
│  ☑ Terrain       │                                          │
│  ☑ Grid          │                                          │
│  ☑ Markers       │                                          │
│  ☑ Tokens        │                                          │
│  ☐ Secret Doors  │                                          │
│  ☐ Traps         │                                          │
│                  │                                          │
│ [Quick Notes]    │                                          │
│  [Text area]     │                                          │
│                  │                                          │
└──────────────────┴──────────────────────────────────────────┘
│ STATUS: World Map | Zoom: 1.5x | Coords: (2048, 1536)      │
│ [< Prev Map] [Next Map >] [Push to Display] [Center View]  │
└─────────────────────────────────────────────────────────────┘
```

### Player Display Window Layout

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                                                             │
│                                                             │
│                                                             │
│                  FULL-SCREEN MAP DISPLAY                    │
│                  (No UI elements)                           │
│                                                             │
│              • Current tactical map only                    │
│              • Fog of war applied                           │
│              • Player tokens visible                        │
│              • Revealed markers only                        │
│              • Grid overlay (optional)                      │
│              • Synchronized with DM view                    │
│                                                             │
│                                                             │
│                                                             │
│                                                             │
│                                                             │
│               [Optional: Scale bar in corner]               │
└─────────────────────────────────────────────────────────────┘
```

---

## Hierarchical Map System

### Map Level Structure

```
Level 0: WORLD MAP (4097x4097 fractal heightmap)
  ├─ Coordinates: (0-4096, 0-4096)
  ├─ 1 pixel = ~1 km
  ├─ Markers for: Cities, Dungeons, Landmarks, Portals
  ├─ Terrain: Fractal-generated with erosion
  └─ Water Level: Global sea level slider
  
Level 1: REGION MAP (Extracted 200x200 → upscaled 2000x2000)
  ├─ Extracted from parent World Map coordinates
  ├─ 1 pixel = ~100 meters
  ├─ Markers for: Districts, Buildings, Dungeon Entrances
  ├─ Terrain: Upscaled parent heightmap + local detail
  └─ Water: Inherited from parent sea level
  
Level 2: LOCAL MAP (Extracted 100x100 → upscaled 1000x1000)
  ├─ Extracted from parent Region Map
  ├─ 1 pixel = ~10 meters
  ├─ Markers for: Rooms, NPCs, Items, Events
  ├─ Terrain: Upscaled with architectural overlays
  └─ Hex/Square grid for tactical play
  
Level 3: ROOM MAP (Procedurally generated or hand-drawn)
  ├─ Grid-based tactical combat map
  ├─ 5ft per square standard D&D scale
  ├─ Markers for: Furniture, Traps, Secret Doors
  ├─ Tokens for: Characters, Monsters
  └─ Fully detailed battle map
```

### Map Transition Flow

```
User clicks marker on World Map
  ↓
System checks if location exists in database
  ↓
  ├─ EXISTS: Load from database
  │   ├─ Load heightmap file
  │   ├─ Load marker data
  │   ├─ Load fog of war state
  │   └─ Display map
  │
  └─ NOT EXISTS: Generate new location
      ├─ Extract heightmap region from parent
      ├─ Upscale to target resolution
      ├─ Send generation request to LLM
      │   ├─ Prompt: "Generate [type] at coords [x,y]"
      │   ├─ Context: Terrain type, nearby locations, theme
      │   └─ Return: Structured JSON
      ├─ Parse JSON response
      ├─ Create markers from JSON locations
      ├─ Save to database
      └─ Display new map
```

---

## Heightmap Extraction System

### Region Extraction Algorithm

```python
def extract_region(parent_heightmap, center_x, center_y, radius, target_size):
    """
    Extract a square region from parent map and upscale to target resolution.
    
    Args:
        parent_heightmap: Full-resolution parent heightmap (numpy array)
        center_x, center_y: Center coordinates in parent map
        radius: Half-width of extraction in parent pixels
        target_size: Output resolution (e.g., 1000x1000)
    
    Returns:
        Upscaled heightmap at target resolution
    """
    # Extract square region with bounds checking
    x_start = max(0, center_x - radius)
    x_end = min(parent_heightmap.shape[1], center_x + radius)
    y_start = max(0, center_y - radius)
    y_end = min(parent_heightmap.shape[0], center_y + radius)
    
    region = parent_heightmap[y_start:y_end, x_start:x_end]
    
    # Upscale using bilinear interpolation (good enough!)
    from PIL import Image
    img = Image.fromarray((region * 65535).astype(np.uint16), mode='I;16')
    upscaled = img.resize((target_size, target_size), Image.BILINEAR)
    
    return np.array(upscaled, dtype=np.float32) / 65535.0
```

### Terrain Consistency Rules

1. **Water Level Inheritance**: Child maps use same normalized sea level as parent
2. **River Continuity**: Rivers on parent map become rivers on child map at same relative positions
3. **Elevation Consistency**: Mountain on world map = mountainous terrain on region map
4. **Biome Matching**: Forest on world map = forested region on local map

---

## Fog of War System

### Data Structure

```python
fog_of_war_state = {
    "map_id": "world_map_uuid",
    "revealed_hexes": set([
        (x1, y1, z1),  # Hex coordinates
        (x2, y2, z2),
        ...
    ]),
    "partially_visible": {
        (x3, y3, z3): 0.5,  # 50% revealed
    },
    "exploration_history": [
        {"timestamp": "2024-01-15T14:30", "hexes": [(x1,y1,z1), ...]},
    ]
}
```

### Fog of War Modes

| Mode | DM View | Player View | Use Case |
|------|---------|-------------|----------|
| **Full Reveal** | All terrain visible | All terrain visible | Exploration, travel montage |
| **Exploration** | All visible | Only revealed hexes | Active dungeon crawling |
| **Hidden** | All visible | Nothing visible | DM prep, secret reveals |
| **Line of Sight** | All visible | Only in token LOS | Tactical combat |
| **Partial** | All visible | Dimmed unrevealed | Show terrain, hide details |

### Reveal Mechanisms

1. **Manual Brush**: DM clicks/drags to reveal hexes
2. **Token Vision**: Auto-reveal based on token sight radius
3. **Area Reveal**: Reveal all hexes in rectangular/circular region
4. **Room Reveal**: Reveal all hexes in a marked room boundary
5. **Conditional**: Reveal when trigger condition met (lever pulled, door opened)

---

## Content Generation System

### LLM Generation Pipeline

```
1. User places marker on map
   ↓
2. System determines context:
   - Marker type (town/dungeon/wilderness)
   - Coordinates on parent map
   - Terrain type under marker (from heightmap)
   - Nearby existing locations (query database)
   - Campaign theme/setting
   ↓
3. Construct LLM prompt:
   "Generate a [type] at coordinates [x,y] on a fantasy world.
    Terrain: [forest/mountain/coast/etc]
    Nearby: [list of nearby locations]
    Theme: [campaign theme]
    Return JSON with: name, description, npcs, locations, rumors, connections"
   ↓
4. Send to Claude API with JSON schema enforcement
   ↓
5. Receive structured JSON response
   ↓
6. Parse and validate JSON
   ↓
7. Create map node in database
   ↓
8. Create child markers from JSON locations
   ↓
9. Extract heightmap region from parent
   ↓
10. Save to database with metadata
   ↓
11. Display generated location
```

### JSON Schema Structure

```json
{
  "location_name": "Forest Clearing",
  "type": "town",
  "theme": "Frontier lumber village",
  "coordinates": {
    "parent_map_id": "world_map_uuid",
    "center_x": 2450,
    "center_y": 1830,
    "radius": 100
  },
  "terrain_info": {
    "primary": "forest",
    "secondary": "river",
    "elevation": "low"
  },
  "description": "A secluded lumber village...",
  "atmosphere": "Woodsmoke and damp earth...",
  "population": 150,
  "government": "Elder council",
  "locations": [
    {
      "name": "The Old Griffin Inn",
      "type": "inn",
      "local_coords": {"x": 45, "y": 67},
      "description": "Rustic, smoky...",
      "services": ["lodging", "food", "drink"],
      "prices": {"room": "5 cp", "meal": "2 cp"}
    },
    {
      "name": "Margaret's Smithy",
      "type": "smithy",
      "local_coords": {"x": 78, "y": 23},
      "description": "A loud workshop...",
      "services": ["repair", "craft"],
      "npc_id": "margaret_smith"
    }
  ],
  "npcs": [
    {
      "id": "margaret_smith",
      "name": "Margaret Smith",
      "role": "Blacksmith",
      "personality": "Gruff, honest, practical",
      "quirk": "Refuses to forge on new moon",
      "location_id": "margarets_smithy",
      "plot_hooks": [
        "Needs rare ore from deep forest for mill repair"
      ]
    }
  ],
  "rumors": [
    {
      "title": "The Whispering Timber",
      "type": "mystery",
      "description": "The Old Griffin's timbers still weep...",
      "truth_level": 0.7
    }
  ],
  "connections": [
    {
      "direction": "north",
      "type": "road",
      "leads_to": {
        "description": "Deep forest",
        "generates": "wilderness_encounter"
      }
    },
    {
      "direction": "south",
      "type": "river",
      "leads_to": {
        "description": "Downstream settlement",
        "coordinates": {"world_x": 2450, "world_y": 1750}
      }
    }
  ],
  "map_generation": {
    "hex_grid": true,
    "grid_size": 64,
    "special_hexes": [
      {"coords": [12, 15], "type": "river", "color": "blue"},
      {"coords": [45, 67], "type": "building", "name": "The Old Griffin"}
    ]
  }
}
```

---

## Token & Combat System

### Token Data Structure

```python
token = {
    "id": "uuid",
    "name": "Thorin Ironforge",
    "type": "player_character",  # or npc, monster
    "owner": "player_1",  # or "dm"
    "map_id": "current_map_uuid",
    "position": {"x": 12, "y": 15, "z": 0},  # Hex or grid coords
    "stats": {
        "hp_current": 45,
        "hp_max": 58,
        "ac": 18,
        "speed": 30,
        "conditions": ["blessed", "hasted"]
    },
    "visibility": {
        "visible_to_players": true,
        "sight_radius": 60,  # feet or hexes
        "darkvision": 60
    },
    "image": "path/to/token.png",
    "size": "medium",  # Affects grid space
    "initiative": 17
}
```

### Combat Mode Features

**DM Control Window:**
- Initiative tracker (drag to reorder)
- HP/status tracking for all tokens
- Hidden monster stats
- Dice roller
- Condition assignment
- AoE template tools

**Player Display Window:**
- Player tokens with visible HP bars
- Monster tokens (only if revealed)
- Grid for movement
- AoE effect visualization
- Turn indicator
- Measurement ruler

---

## State Synchronization

### Event Broadcasting System

```python
class StateManager:
    def __init__(self):
        self.dm_window = None
        self.player_window = None
        self.current_state = {}
    
    def broadcast_event(self, event_type, data):
        """Send state change to both windows"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        }
        
        # Update DM window (full data)
        if self.dm_window:
            self.dm_window.handle_event(event)
        
        # Update player window (filtered data)
        if self.player_window:
            filtered_event = self.filter_for_players(event)
            self.player_window.handle_event(filtered_event)
    
    def filter_for_players(self, event):
        """Remove hidden information from event"""
        if event["type"] == "token_move":
            # Only show visible tokens
            if event["data"]["token"]["visibility"]["visible_to_players"]:
                return event
            return None
        
        elif event["type"] == "fog_reveal":
            # Always show fog reveals
            return event
        
        elif event["type"] == "marker_add":
            # Only show public markers
            if not event["data"]["marker"]["secret"]:
                return event
            return None
        
        return event
```

### Synchronized Events

- **Map Navigation**: When DM changes maps, player display updates
- **Fog of War**: Revealed hexes appear on player display in real-time
- **Token Movement**: Player can move own tokens, DM sees all movement
- **Marker Placement**: Public markers appear on both displays
- **Zoom/Pan**: DM can "push" their view to player display
- **Combat Actions**: Initiative, HP changes, conditions broadcast

---

## Database Schema

### Core Tables

```sql
-- Campaigns
CREATE TABLE campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    theme TEXT,
    created_at TIMESTAMP,
    last_played TIMESTAMP
);

-- Map Nodes (Hierarchical)
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    parent_node_id TEXT REFERENCES nodes(id),  -- NULL for world map
    node_type TEXT,  -- world/region/town/dungeon/room
    name TEXT,
    coords_x INTEGER,
    coords_y INTEGER,
    coords_z INTEGER,  -- For dungeon levels
    heightmap_file TEXT,  -- Path to PNG file
    metadata JSON,  -- Flexible storage for generation data
    created_at TIMESTAMP
);

-- Markers
CREATE TABLE markers (
    id TEXT PRIMARY KEY,
    node_id TEXT REFERENCES nodes(id),
    marker_type TEXT,  -- town/dungeon/npc/item/encounter
    name TEXT,
    local_x INTEGER,
    local_y INTEGER,
    target_node_id TEXT REFERENCES nodes(id),  -- Where this leads
    secret BOOLEAN DEFAULT false,
    metadata JSON,
    created_at TIMESTAMP
);

-- Tokens
CREATE TABLE tokens (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    current_node_id TEXT REFERENCES nodes(id),
    name TEXT,
    token_type TEXT,  -- pc/npc/monster
    owner TEXT,  -- player name or "dm"
    position_x INTEGER,
    position_y INTEGER,
    stats JSON,
    visibility JSON,
    image_path TEXT,
    created_at TIMESTAMP
);

-- Fog of War State
CREATE TABLE fog_of_war (
    node_id TEXT REFERENCES nodes(id),
    hex_x INTEGER,
    hex_y INTEGER,
    hex_z INTEGER,
    revealed BOOLEAN DEFAULT false,
    visibility REAL DEFAULT 0.0,  -- 0.0 to 1.0
    revealed_at TIMESTAMP,
    PRIMARY KEY (node_id, hex_x, hex_y, hex_z)
);

-- Session Log
CREATE TABLE session_log (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    timestamp TIMESTAMP,
    event_type TEXT,
    event_data JSON
);
```

---

## Performance Optimization

### Caching Strategy

1. **Heightmap Cache**: Keep last 5 accessed heightmaps in RAM
2. **Render Cache**: Cache rendered map tiles at current zoom level
3. **Token Sprites**: Pre-load and cache all token images
4. **Fog State**: Cache revealed hex sets for fast lookup
5. **Database**: Index on coordinates and parent relationships

### Rendering Pipeline

```
Frame Update (60 FPS target):
  1. Check if camera moved or zoom changed
     ├─ Yes: Mark visible tiles dirty
     └─ No: Skip terrain rendering
  
  2. Render visible terrain tiles only
     ├─ Use cached tiles if available
     └─ Render new tiles if needed
  
  3. Apply fog of war mask
     ├─ Use cached fog state
     └─ Only recalculate if state changed
  
  4. Render tokens
     ├─ Only tokens in viewport
     └─ Use sprite cache
  
  5. Render UI overlay
     ├─ Grid lines
     └─ Selection highlights
  
  6. Blit to screen
```

### Network Optimization (Future: Remote Players)

- Delta compression for state updates
- Tile-based map streaming
- Token position interpolation
- Lazy loading of non-visible data

---

## User Workflows

### Starting a New Campaign

1. DM clicks "New Campaign"
2. System prompts for campaign name and theme
3. System generates world map (4097x4097 fractal)
4. Applies initial erosion and detail
5. Sets default sea level
6. Saves world to database
7. Opens DM control window at world level

### Placing a New Town

1. DM right-clicks on world map
2. Selects "Add Marker → Town"
3. System extracts terrain under cursor
4. System prompts LLM with context
5. LLM returns town JSON
6. System creates town node in database
7. System extracts and upscales heightmap region
8. Town marker appears on world map
9. DM clicks marker to zoom into town

### Running Combat

1. DM navigates to combat location (room/clearing)
2. DM clicks "Start Combat"
3. System switches to grid mode
4. DM places monster tokens
5. System rolls initiative
6. DM clicks "Push to Display"
7. Player display shows combat map
8. Players see their tokens and revealed enemies
9. DM tracks HP, conditions, turn order
10. Player display updates in real-time

### Exploring a Dungeon

1. Party enters dungeon entrance marker
2. System loads dungeon map
3. Player display shows only entrance room (fog)
4. DM uses reveal brush as party explores
5. Hexes reveal on player display
6. Players discover markers (secret doors, treasure)
7. Clicking exit leads to next level
8. System generates if not exists

---

## Implementation Phases

### Phase 1: Core Dual Window System
- [ ] Implement window manager with two Pygame windows
- [ ] Create state synchronization system
- [ ] Build event broadcasting
- [ ] Basic camera controls in both windows
- [ ] Display same map in both windows

### Phase 2: Heightmap Extraction
- [ ] Implement region extraction algorithm
- [ ] Build upscaling system (PIL bilinear)
- [ ] Test extraction at multiple zoom levels
- [ ] Cache extracted regions
- [ ] Verify water level consistency

### Phase 3: Fog of War
- [ ] Implement fog state storage
- [ ] Build reveal/hide tools for DM
- [ ] Render fog overlay on player display
- [ ] Add manual brush reveal
- [ ] Implement save/load fog state

### Phase 4: LLM Generation
- [ ] Design JSON schema for locations
- [ ] Build prompt templates
- [ ] Implement Claude API integration
- [ ] Parse and validate JSON responses
- [ ] Create markers from generated data
- [ ] Handle generation failures gracefully

### Phase 5: Token System
- [ ] Design token data structure
- [ ] Implement token placement/movement
- [ ] Build drag-and-drop interface
- [ ] Add HP/status tracking
- [ ] Sync tokens between displays
- [ ] Filter hidden tokens from player view

### Phase 6: Combat Mode
- [ ] Build initiative tracker
- [ ] Add grid snapping for tokens
- [ ] Implement AoE templates
- [ ] Create measurement tools
- [ ] Add turn indicator
- [ ] Build condition assignment UI

### Phase 7: Polish & Optimization
- [ ] Implement tile-based rendering
- [ ] Add render caching
- [ ] Optimize fog of war rendering
- [ ] Add keyboard shortcuts
- [ ] Build session logging
- [ ] Create backup/restore system

---

## Technical Requirements

### Hardware
- **Minimum**: Dual-core CPU, 8GB RAM, integrated graphics
- **Recommended**: Quad-core CPU, 16GB RAM, dedicated GPU
- **Display**: Two monitors (any resolution, player display scales)

### Software Dependencies
- Python 3.10+
- Pygame 2.5+
- NumPy 1.24+
- Pillow (PIL) 10.0+
- Anthropic API (Claude)
- SQLite 3

### File Storage
- World heightmaps: ~32MB per 4097x4097 map (16-bit PNG)
- Region heightmaps: ~2MB per 1000x1000 map
- Database: ~100MB per campaign (typical)
- Token images: Variable
- Total: ~1GB per active campaign

---

## Future Enhancements

### Multiplayer Support
- WebSocket server for remote players
- Browser-based player clients
- Shared token control
- Chat/dice rolling integration

### Advanced Generation
- Weather systems
- Time of day lighting
- Seasonal changes
- Dynamic events (fires, floods)

### Content Library
- Pre-generated town templates
- Monster stat blocks database
- Magic item library
- Spell effect visuals

### DM Tools
- Note-taking system
- NPC relationship graphs
- Quest tracking
- Loot tables
- Random encounter generator

### Audio Integration
- Ambient sound based on terrain
- Music zones
- Sound effects for actions
- Voice chat integration

---

## Conclusion

This dual-monitor campaign manager transforms procedurally generated fractal worlds into a comprehensive virtual tabletop system. By separating DM control from player display and leveraging hierarchical heightmap extraction, the system provides seamless zoom from world-scale to tactical grid while maintaining terrain consistency.

The LLM-driven content generation ensures infinite, contextually appropriate locations, while the fog of war and token systems enable classic tabletop gameplay enhanced by digital tools. The result is a system that feels like having an infinitely detailed, pre-made campaign world that generates itself on-demand as players explore.

**Core Philosophy**: Usable beats perfect. Every feature prioritizes functionality and game flow over technical perfection. The system should enhance gameplay, not interrupt it.