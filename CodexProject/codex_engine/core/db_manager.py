import sqlite3
import json
import logging
from typing import Optional, Dict, List, Any
from codex_engine.config import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DBManager")

class DBManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._initialize_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_tables(self):
        queries = [
            """CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                theme_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""",
            
            """CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                parent_node_id INTEGER,
                type TEXT NOT NULL, 
                name TEXT,
                grid_x INTEGER,
                grid_y INTEGER,
                geometry_data TEXT, 
                metadata TEXT,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(parent_node_id) REFERENCES nodes(id)
            );""",

            """CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,       -- 'global', 'campaign', 'node'
                scope_id INTEGER,          -- NULL for global, campaign_id, or node_id
                key TEXT NOT NULL,
                value TEXT,                -- JSON encoded value
                UNIQUE(scope, scope_id, key)
            );""",

            """CREATE TABLE IF NOT EXISTS markers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER,
                world_x REAL,
                world_y REAL,
                symbol TEXT,
                title TEXT,
                description TEXT,
                metadata TEXT,
                FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );""",

            """CREATE TABLE IF NOT EXISTS vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER,
                type TEXT, 
                points_json TEXT,
                width INTEGER,
                FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );""",
            
            """CREATE TABLE IF NOT EXISTS npcs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                role TEXT,
                personality TEXT,
                hook TEXT,
                location TEXT,
                metadata TEXT,
                FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );"""
        ]

        try:
            with self.get_connection() as conn:
                conn.execute("PRAGMA foreign_keys = ON;")
                for q in queries:
                    conn.execute(q)
                conn.commit()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    # --- CAMPAIGN ---
    def create_campaign(self, name: str, theme_id: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO campaigns (name, theme_id) VALUES (?, ?)", (name, theme_id))
            conn.commit()
            return cursor.lastrowid

    def delete_campaign(self, campaign_id: int):
        """Deletes a campaign and all its nodes, markers, etc."""
        with self.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            
            # Get all nodes for the campaign first
            nodes = conn.execute("SELECT id FROM nodes WHERE campaign_id = ?", (campaign_id,)).fetchall()
            
            # Deleting a node cascades to its markers, vectors, and npcs
            for node_row in nodes:
                conn.execute("DELETE FROM nodes WHERE id = ?", (node_row['id'],))
            
            # Finally, delete the campaign itself
            conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
            conn.commit()
            print(f"DB: Deleted campaign {campaign_id} and all associated data.")

    def get_campaign(self, campaign_id: int) -> dict:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
            return dict(row) if row else None
            
    def get_all_campaigns(self) -> List[dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    # --- NODE ---
    def create_node(self, campaign_id: int, node_type: str, parent_id: Optional[int], x: int, y: int, name: str = "Unknown") -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO nodes (campaign_id, parent_node_id, type, grid_x, grid_y, name, geometry_data, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, '{}', '{}')""",
                (campaign_id, parent_id, node_type, x, y, name)
            )
            conn.commit()
            return cursor.lastrowid

    def get_node_by_coords(self, campaign_id: int, parent_id: Optional[int], x: int, y: int) -> Optional[dict]:
        query = "SELECT * FROM nodes WHERE campaign_id=? AND grid_x=? AND grid_y=?"
        params = [campaign_id, x, y]
        if parent_id is None: query += " AND parent_node_id IS NULL"
        else: query += " AND parent_node_id=?"; params.append(parent_id)

        with self.get_connection() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            if row:
                data = dict(row)
                data['geometry_data'] = json.loads(data['geometry_data']) if data['geometry_data'] else {}
                data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}
                return data
            return None
    
    def get_node(self, node_id: int) -> Optional[dict]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
            if row:
                data = dict(row)
                data['geometry_data'] = json.loads(data['geometry_data']) if data['geometry_data'] else {}
                data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}
                return data
            return None

    def update_node_data(self, node_id: int, geometry: dict = None, metadata: dict = None):
        updates = []
        params = []
        if geometry is not None: updates.append("geometry_data = ?"); params.append(json.dumps(geometry))
        if metadata is not None: updates.append("metadata = ?"); params.append(json.dumps(metadata))
        if not updates: return
        params.append(node_id)
        sql = f"UPDATE nodes SET {', '.join(updates)} WHERE id = ?"
        with self.get_connection() as conn: conn.execute(sql, tuple(params)); conn.commit()

    def delete_node_and_children(self, node_id: int):
        print(f"DB: Deleting node {node_id} and all associated children.")
        with self.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            conn.commit()

    def get_structure_tree(self, current_node_id):
        """
        Returns all nodes that were generated by the same source marker.
        This correctly groups all levels of a dungeon/building complex.
        """
        current_node = self.get_node(current_node_id)
        if not current_node:
            return []

        source_marker_id = current_node['metadata'].get('source_marker_id')
        if not source_marker_id:
            # If for some reason it has no source, just show itself.
            return [{
                "id": current_node['id'], "name": current_node['name'], "type": current_node['type'],
                "depth": 0, "is_current": True
            }]

        structure = []
        with self.get_connection() as conn:
            # We have to query the TEXT metadata field, which is slow but necessary.
            rows = conn.execute("SELECT id, name, type, metadata FROM nodes WHERE parent_node_id = ?", (current_node['parent_node_id'],)).fetchall()

        for r in rows:
            try:
                meta = json.loads(r['metadata'])
                if meta.get('source_marker_id') == source_marker_id:
                    structure.append({
                        "id": r['id'],
                        "name": r['name'],
                        "type": r['type'],
                        "depth": meta.get('depth', 0) -1, # Adjust for display
                        "is_current": (r['id'] == current_node_id)
                    })
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Sort by depth if it exists
        structure.sort(key=lambda x: x.get('depth', 0))
            
        return structure
    
    # --- Settings ---

    def get_setting_raw(self, key: str, scope: str, scope_id: int = None):
        """Gets a specific setting record without cascading."""
        # FIX: Force None to 0 because SQLite UNIQUE constraints fail on NULLs
        if scope_id is None: 
            scope_id = 0
            
        with self.get_connection() as conn:
            # Removed "IS NULL" check, now purely equality based
            query = "SELECT value FROM settings WHERE scope=? AND key=? AND scope_id=?"
            params = (scope, key, scope_id)
                
            row = conn.execute(query, params).fetchone()
            return json.loads(row['value']) if row else None

    def set_setting(self, key: str, value: any, scope: str, scope_id: int = None):
        """Upserts a setting."""
        # FIX: Force None to 0 to ensure ON CONFLICT triggers correctly
        if scope_id is None: 
            scope_id = 0
        
        val_json = json.dumps(value)
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO settings (scope, scope_id, key, value) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scope, scope_id, key) 
                DO UPDATE SET value=excluded.value""",
                (scope, scope_id, key, val_json)
            )
            conn.commit()

    def get_setting_raw_old(self, key: str, scope: str, scope_id: int = None):
        """Gets a specific setting record without cascading."""
        with self.get_connection() as conn:
            query = "SELECT value FROM settings WHERE scope=? AND key=?"
            params = [scope, key]
            if scope_id is not None:
                query += " AND scope_id=?"
                params.append(scope_id)
            else:
                query += " AND scope_id IS NULL"
                
            row = conn.execute(query, tuple(params)).fetchone()
            return json.loads(row['value']) if row else None

    def set_setting_old(self, key: str, value: any, scope: str, scope_id: int = None):
        """Upserts a setting."""
        val_json = json.dumps(value)
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO settings (scope, scope_id, key, value) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scope, scope_id, key) 
                DO UPDATE SET value=excluded.value""",
                (scope, scope_id, key, val_json)
            )
            conn.commit()

    # --- MARKERS ---
    def add_marker(self, node_id, wx, wy, symbol, title, desc="", metadata=None):
        meta_json = json.dumps(metadata if metadata else {})
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO markers (node_id, world_x, world_y, symbol, title, description, metadata) VALUES (?,?,?,?,?,?,?)",
                (node_id, wx, wy, symbol, title, desc, meta_json)
            )
            conn.commit()
    
    def update_marker(self, marker_id, world_x=None, world_y=None, symbol=None, title=None, description=None, metadata=None):
        updates, params = [], []
        if world_x is not None: updates.append("world_x=?"); params.append(world_x)
        if world_y is not None: updates.append("world_y=?"); params.append(world_y)
        if symbol is not None: updates.append("symbol=?"); params.append(symbol)
        if title is not None: updates.append("title=?"); params.append(title)
        if description is not None: updates.append("description=?"); params.append(description)
        if metadata is not None: updates.append("metadata=?"); params.append(json.dumps(metadata))
        if not updates: return
        params.append(marker_id)
        sql = f"UPDATE markers SET {', '.join(updates)} WHERE id = ?"
        with self.get_connection() as conn: conn.execute(sql, tuple(params)); conn.commit()

    def get_markers(self, node_id):
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM markers WHERE node_id = ?", (node_id,)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try: d['metadata'] = json.loads(d['metadata']) if d['metadata'] else {}
                except: d['metadata'] = {}
                results.append(d)
            return results
    
    def delete_marker(self, marker_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM markers WHERE id = ?", (marker_id,))
            conn.commit()

    # --- NPCs ---
    def add_npc(self, node_id: int, npc_data: Dict[str, Any]):
        meta_json = json.dumps(npc_data.get('metadata', {}))
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO npcs (node_id, name, role, personality, hook, location, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (node_id, npc_data.get('name'), npc_data.get('role'), npc_data.get('personality'),
                 npc_data.get('hook'), npc_data.get('location'), meta_json)
            )
            conn.commit()

    def update_npc(self, npc_id: int, npc_data: Dict[str, Any]):
        updates, params = [], []
        for key in ['name', 'role', 'personality', 'hook', 'location', 'metadata']:
            if key in npc_data:
                value = json.dumps(npc_data[key]) if key == 'metadata' else npc_data[key]
                updates.append(f"{key}=?"); params.append(value)
        if not updates: return
        params.append(npc_id)
        sql = f"UPDATE npcs SET {', '.join(updates)} WHERE id = ?"
        with self.get_connection() as conn: conn.execute(sql, tuple(params)); conn.commit()

    def get_npcs_for_node(self, node_id: int) -> List[dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM npcs WHERE node_id = ?", (node_id,)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try: d['metadata'] = json.loads(d['metadata']) if d['metadata'] else {}
                except: d['metadata'] = {}
                results.append(d)
            return results

    # --- VECTORS ---
    def save_vector(self, node_id, vtype, points, width=5, vector_id=None):
        p_json = json.dumps(points)
        with self.get_connection() as conn:
            if vector_id: conn.execute("UPDATE vectors SET points_json=?, width=?, type=? WHERE id=?", (p_json, width, vtype, vector_id))
            else: conn.execute("INSERT INTO vectors (node_id, type, points_json, width) VALUES (?,?,?,?)", (node_id, vtype, p_json, width))
            conn.commit()
    
    def get_vectors(self, node_id):
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM vectors WHERE node_id=?", (node_id,)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d['points'] = json.loads(d['points_json'])
                results.append(d)
            return results

    def delete_vector(self, vector_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM vectors WHERE id=?", (vector_id,))
            conn.commit()

