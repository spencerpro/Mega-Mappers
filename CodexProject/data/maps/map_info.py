import os
import sqlite3
import json
from pathlib import Path
from PIL import Image
import numpy as np

# This script assumes it is being run from the root of your project
MAPS_DIR = Path(".")
DB_PATH = Path("../codex.db")

def get_node_marker_map():
    """
    Connects to the database and builds a dictionary mapping 
    local map filenames back to the marker that created them.
    """
    node_marker_map = {}
    
    if not DB_PATH.exists():
        return node_marker_map, "DB not found"

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Get all local map nodes
        nodes = conn.execute("SELECT id, name, metadata, parent_node_id, grid_x, grid_y FROM nodes WHERE type = 'local_map'").fetchall()
        
        if not nodes:
            return {}, "No local maps found in DB"
        
        for node in nodes:
            metadata = json.loads(node['metadata'])
            filename = metadata.get('file_path')
            
            if not filename:
                continue

            # Find the marker on the parent node that corresponds to this local map's creation coordinates
            parent_id = node['parent_node_id']
            grid_x = node['grid_x']
            grid_y = node['grid_y']
            
            # Query for markers on the parent node at the location where this local map was generated
            marker_query = "SELECT title FROM markers WHERE node_id = ? AND CAST(world_x AS INTEGER) = ? AND CAST(world_y AS INTEGER) = ?"
            marker = conn.execute(marker_query, (parent_id, grid_x, grid_y)).fetchone()

            if marker:
                node_marker_map[filename] = marker['title']
            else:
                # Fallback to the node name itself if no marker is found (should be rare)
                node_marker_map[filename] = f"(No Marker Found, Node: {node['name']})"

        conn.close()
        return node_marker_map, None
        
    except Exception as e:
        return {}, f"DB Error: {e}"

def analyze_heightmaps():
    """
    Scans maps, links them to their source marker, and prints their value ranges.
    """
    print(f"--- Analyzing Heightmaps in: {MAPS_DIR.resolve()} ---")
    
    if not MAPS_DIR.exists():
        print(f"ERROR: Directory not found. Make sure you run this script from your project root.")
        return

    # 1. Get the mapping from the database
    node_to_marker_title, err = get_node_marker_map()
    if err:
        print(f"WARNING: Could not map files to markers. {err}")
    
    png_files = sorted(list(MAPS_DIR.glob("*.png")))
    
    if not png_files:
        print("No .png files found to analyze.")
        return
        
    for file_path in png_files:
        try:
            img = Image.open(file_path)
            
            if img.mode != 'I;16':
                # print(f"Skipping {file_path.name}: Not a 16-bit grayscale image (Mode: {img.mode})")
                continue
                
            data = np.array(img)
            
            min_val = data.min()
            max_val = data.max()
            
            # Look up the associated marker name
            marker_name = node_to_marker_title.get(file_path.name, " (World Map or Unlinked)")
            
            print(f"File: {file_path.name:<45} Range: [{min_val:<5}, {max_val:>5}]  -->  Marker: {marker_name}")

        except Exception as e:
            print(f"Could not process {file_path.name}: {e}")

if __name__ == "__main__":
    analyze_heightmaps()
