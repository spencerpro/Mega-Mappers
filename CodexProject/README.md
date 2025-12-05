
# Codex Engine - Alpha (Pre-Local Terrain)

A procedural TTRPG campaign management tool designed to allow Game Masters to generate, edit, and manage fractal worlds with high-fidelity terrain and persistent data.

## Current Version Status
**Checkpoint: Pre-Local Terrain**
This version features a fully functional World Map editor with persistent view states, manual vector overlay tools (Roads/Rivers), and interactive markers. The next major phase will involve imprinting these features onto local-scale tactical maps.

---

## Features

### 1. Fractal World Generation
*   **Heightmap Generation:** Uses Diamond-Square noise combined with hydraulic and thermal erosion simulations.
*   **High Precision:** Maps are stored as 16-bit grayscale PNGs to preserve altitude data for realistic lighting.
*   **Dynamic Rendering:** Real-time calculation of Hillshading (shadows), Hypsometric Tinting (biome colors), and Dynamic Water Levels.

### 2. Map Viewer & Controls
*   **Dynamic Lighting:** Sliders to control Sun Direction (Azimuth), Height (Altitude), and Intensity.
*   **Sea Level Control:** Real-time flooding/drying of terrain using a slider.
*   **Grid System:** Toggleable Hex or Square grid with adjustable size.
*   **Persistence:** Camera position, zoom level, lighting settings, and sea level are saved to the database automatically upon exit or map change.

### 3. Vector Overlay Editor (Roads & Rivers)
*   **Manual Drawing:** GM can draw Roads (Brown) and Rivers (Blue) directly onto the map.
*   **Spline Rendering:** Points are automatically smoothed using Catmull-Rom splines for organic curves.
*   **Editing Tools:**
    *   **Select:** Click any existing line to edit it.
    *   **Reshape:** Drag control points to move the line.
    *   **Extend:** Click empty space while a line is active to add new points.
    *   **Delete:** Remove lines entirely from the database.

### 4. Point of Interest Markers
*   **Marker System:** Place icons for Towns, Dungeons, or Landmarks.
*   **Interaction:**
    *   **Create:** Shift + Left Click on empty terrain.
    *   **Move:** Drag and drop markers to new locations.
    *   **Edit:** Context menu to change Title, Icon, and Description.
    *   **Zoom:** Shift + Left Click on an existing marker (Placeholder for entering Local Map).

---

## Controls & Keybinds

| Action | Input |
| :--- | :--- |
| **Pan Camera** | Arrow Keys |
| **Zoom In/Out** | `[` and `]` or Click & Drag (Empty Space) |
| **Toggle UI** | `H` |
| **Toggle Grid** | `G` |
| **Switch Grid Type** | `T` (Hex/Square) |
| **Grid Size** | `-` and `=` |
| **Save View State** | `S` |
| **Cancel Tool** | `ESC` |

### Mouse Interactions

| Context | Action | Result |
| :--- | :--- | :--- |
| **Empty Space** | Left Click | Pan / Zoom to location |
| **Empty Space** | Shift + Left Click | **Create New Marker** |
| **Marker** | Left Click | Select Marker (Opens Edit Menu) |
| **Marker** | Drag | Move Marker |
| **Marker** | Shift + Left Click | **Enter Location** (Signal) |
| **Road/River** | Left Click | Select Vector for Editing |
| **Vector Active** | Left Click (Empty) | Add new point to line |
| **Vector Active** | Drag Point | Move control point |

---

## Technical Architecture

*   **Language:** Python 3.10+
*   **Engine:** Pygame (Rendering), NumPy (Heightmap Math), Pillow (Image IO).
*   **Database:** SQLite (`codex.db`).
    *   `campaigns`: Meta data.
    *   `nodes`: Map files and metadata.
    *   `markers`: POI coordinates and text.
    *   `vectors`: JSON storage of road/river control points.
*   **Rendering Pipeline:**
    *   Raw 16-bit Heightmap -> NumPy Array -> Gradient Calculation -> Lighting Shader -> Pixel Buffer -> Pygame Surface.

## Installation & Run

1.  Ensure dependencies are installed:
    ```bash
    pip install pygame numpy pillow
    ```
2.  Run the application:
    ```bash
    python main.py
    ```

## Development Changelog (Day 3)

### 1. Vector Overlay System
*   **Feature:** Implemented a Spline-based drawing tool for creating Roads and Rivers.
*   **Rationale:** The GM needs to act as the Architect of the world. Procedural terrain is the canvas, but roads and rivers define the flow of civilization and geography. These vectors serve as the "blueprints" that will constrain local map generation in future updates.
*   **Implementation:** Added `vectors` table to SQLite. Created `save_vector` and `delete_vector` logic. Integrated Catmull-Rom splines for smooth rendering.

### 2. View State Persistence
*   **Feature:** The application now saves the Camera Position (X, Y), Zoom Level, Sea Level, and Lighting Settings to the database whenever the user exits a map or presses 'S'.
*   **Rationale:** Campaign management requires continuity. A GM returning to a map weeks later should find it exactly as they left it, without needing to re-adjust sliders or find their place again.

### 3. Unified Interaction Model
*   **Feature:** Overhauled `MapViewer` input handling to support Pixel-Based Hit Detection.
*   **Rationale:** As features grew (Markers, Roads, Zooming), input conflicts arose. We moved to a pixel-read system:
    *   Clicking a **Brown Pixel** selects the Road.
    *   Clicking a **Blue Pixel** selects the River.
    *   Clicking **Empty Space** handles Camera/Zoom.
    *   This removes the need for clunky mode switches and makes interaction intuitive.

### 4. UI Consolidation
*   **Feature:** Grouped all editing tools (Roads, Rivers, Save, Delete) into the sidebar and enforced a strict Z-order to prevent click-through errors.
*   **Rationale:** The UI was floating and allowed clicks to pass through to the map, causing unintended terrain interactions while clicking buttons. Anchoring the UI ensures stable tool usage.


