from .db_manager import DBManager
import json

def log(message, indent=0):
    prefix = "  " * indent
    print(f"[ADAPTER]{prefix} {message}")

class SQLTreeAdapter:
    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    def _format_uid(self, prefix, id_val): return f"{prefix}:{id_val}"
    def _parse_uid(self, uid): 
        parts = uid.split(':')
        return parts[0], int(parts[1])

    # Schemas remain the same
    def _get_campaign_schema(self): return [{"key": "name", "label": "Campaign Name", "type": "text"}, {"key": "theme_id", "label": "Theme", "type": "text"}]
    def _get_map_schema(self): return [{"key": "name", "label": "Map Name", "type": "text"}, {"key": "overview", "label": "DM Overview", "type": "textarea"}, {"key": "rumors", "label": "Local Rumors", "type": "list"}]
    def _get_marker_schema(self): return [{"key": "title", "label": "Location Name", "type": "text"}, {"key": "description", "label": "Description", "type": "textarea"}]
    def _get_npc_schema(self): return [{"key": "name", "label": "Name", "type": "text"}, {"key": "role", "label": "Role", "type": "text"}, {"key": "personality", "label": "Personality", "type": "textarea"}, {"key": "hook", "label": "Quest Hook", "type": "textarea"}]

    def get_roots(self):
        log("get_roots() called.")
        camps = self.db.get_all_campaigns()
        return [{"uid": self._format_uid("campaign", c['id']), "type": "campaign", "name": c['name'], "icon": "🌍"} for c in camps]

    def get_node(self, uid: str):
        print("\n" + "="*70)
        log(f"get_node() called with UID: '{uid}'")
        
        if "-info" in uid:
            original_uid = uid.replace("-info", "")
            node_data = self.get_node(original_uid)
            if not node_data: return None
            node_data['uid'] = uid
            node_data['type'] += "-info"
            node_data['name'] = f"(Details) {node_data['name']}"
            node_data['children'] = []
            return node_data

        type_prefix, pk = self._parse_uid(uid)
        log(f"Parsed UID into type: '{type_prefix}', pk: {pk}", 1)

        if type_prefix == "campaign":
            log("Handling as a CAMPAIGN...", 1)
            data = self.db.get_campaign(pk)
            if not data: return None
            with self.db.get_connection() as conn:
                rows = conn.execute("SELECT id, name, type FROM nodes WHERE campaign_id=? AND parent_node_id IS NULL", (pk,)).fetchall()
            children = []
            children.insert(0, {"uid": f"campaign-info:{pk}", "type": "campaign-info", "name": "(Campaign Details)", "icon": "ℹ️"})
            for r in rows:
                children.append({"uid": self._format_uid(r['type'], r['id']), "type": r['type'], "name": r['name'], "icon": "🗺️"})
            return {"uid": uid, "parent_uid": None, "type": "campaign", "name": data['name'], "data": data, "ui_schema": self._get_campaign_schema(), "children": children}

        elif type_prefix in ["world_map", "local_map", "dungeon", "dungeon_level", "building_interior"]:
            log(f"Handling as a MAP ({type_prefix})...", 1)
            data = self.db.get_node(pk)
            if not data: return None
            flat_data = {"name": data['name'], **data.get('metadata', {})}
            
            children = []
            children.append({"uid": f"{data['type']}-info:{pk}", "type": f"{data['type']}-info", "name": "(Map Details)", "icon": "ℹ️"})
            
            # For dungeon_level and building_interior, show markers and NPCs
            if data['type'] in ['dungeon_level', 'building_interior']:
                log(f"This is a tactical map ({data['type']}). Getting markers and NPCs...", 2)
                markers = self.db.get_markers(pk)
                npcs = self.db.get_npcs_for_node(pk)
                
                for m in markers: 
                    children.append({"uid": self._format_uid("marker", m['id']), "type": "marker", "name": m['title'], "icon": m['symbol']})
                for n in npcs: 
                    children.append({"uid": self._format_uid("npc", n['id']), "type": "npc", "name": n['name'], "icon": "👤"})
            
            # For other map types, show markers, NPCs, and child nodes
            else:
                markers = self.db.get_markers(pk)
                npcs = self.db.get_npcs_for_node(pk)
                
                for m in markers: 
                    children.append({"uid": self._format_uid("marker", m['id']), "type": "marker", "name": m['title'], "icon": m['symbol']})
                for n in npcs: 
                    children.append({"uid": self._format_uid("npc", n['id']), "type": "npc", "name": n['name'], "icon": "👤"})
                
                # If this is a dungeon, add all its levels as children too
                if data['type'] == 'dungeon':
                    log("This is a DUNGEON. Fetching all levels...", 2)
                    with self.db.get_connection() as conn:
                        levels = conn.execute(
                            "SELECT id, name, type FROM nodes WHERE parent_node_id=? ORDER BY id",
                            (pk,)
                        ).fetchall()
                    for level in levels:
                        children.append({
                            "uid": self._format_uid(level['type'], level['id']),
                            "type": level['type'],
                            "name": level['name'],
                            "icon": "🗺️"
                        })
            
            parent_uid = self._format_uid(self.db.get_node(data['parent_node_id'])['type'], data['parent_node_id']) if data['parent_node_id'] else self._format_uid("campaign", data['campaign_id'])
            return {
                "uid": uid,
                "parent_uid": parent_uid,
                "type": data['type'],
                "name": data['name'],
                "data": flat_data,
                "ui_schema": self._get_map_schema(),
                "children": children
            }

        elif type_prefix == "marker":
            log("Handling as a MARKER...", 1)
            
            with self.db.get_connection() as conn:
                row = conn.execute("SELECT * FROM markers WHERE id=?", (pk,)).fetchone()
            if not row: return None
            marker_data = dict(row)
            log(f"Found marker in DB: '{marker_data['title']}'", 2)
            
            try:
                marker_data['metadata'] = json.loads(marker_data.get('metadata', '{}'))
            except:
                marker_data['metadata'] = {}
            
            parent_node = self.db.get_node(marker_data['node_id'])
            destination_node = None

            # RULE 1: If on a world_map, check for destination by coordinates
            if parent_node['type'] == 'world_map':
                log("Marker is on a world_map. Searching for destination by coordinates...", 2)
                destination_node = self.db.get_node_by_coords(
                    parent_node['campaign_id'],
                    parent_id=parent_node['id'],
                    x=int(marker_data['world_x']),
                    y=int(marker_data['world_y'])
                )
                if destination_node:
                    log(f"FOUND destination map by coords: '{destination_node['name']}'", 3)
            
            # RULE 2: If on any other map, check for destination by 'portal_to'
            else:
                log("Marker is on a local/tactical map. Searching for destination by 'portal_to' metadata...", 2)
                portal_id = marker_data['metadata'].get('portal_to')
                if portal_id:
                    destination_node = self.db.get_node(portal_id)
                    if destination_node:
                        log(f"FOUND destination map by portal_to: '{destination_node['name']}'", 3)

            # If destination found
            if destination_node:
                # RULE: If world_map → local_map, JUMP directly
                if parent_node['type'] == 'world_map' and destination_node['type'] == 'local_map':
                    log("!!! World map marker → local map. Jumping directly. !!!", 2)
                    destination_uid = self._format_uid(destination_node['type'], destination_node['id'])
                    return self.get_node(destination_uid)
                
                # Otherwise: Show marker info + all structure nodes created by this marker
                else:
                    log("!!! This marker links to a structure. Getting full structure tree. !!!", 2)
                    
                    children = []
                    # First: marker info
                    children.append({
                        "uid": f"marker-info:{pk}",
                        "type": "marker-info",
                        "name": "(Entry Point Details)",
                        "icon": "ℹ️"
                    })
                    
                    # Get ALL nodes in this structure using get_structure_tree
                    log(f"Calling get_structure_tree with portal_id: {destination_node['id']}...", 3)
                    structure_nodes = self.db.get_structure_tree(destination_node['id'])
                    
                    log(f"Found {len(structure_nodes)} structure nodes.", 3)
                    for node in structure_nodes:
                        children.append({
                            "uid": self._format_uid(node['type'], node['id']),
                            "type": node['type'],
                            "name": node['name'],
                            "icon": "🗺️"
                        })
                    
                    parent_uid = self._format_uid(parent_node['type'], parent_node['id'])
                    return {
                        "uid": uid,
                        "parent_uid": parent_uid,
                        "type": "marker",
                        "name": marker_data['title'],
                        "data": marker_data,
                        "ui_schema": self._get_marker_schema(),
                        "children": children
                    }
            
            # If NO destination, it's just a Point of Interest
            else:
                log("This marker is a simple Point of Interest, not a portal.", 2)
                children = [{
                    "uid": f"marker-info:{pk}",
                    "type": "marker-info",
                    "name": "(Marker Details)",
                    "icon": "ℹ️"
                }]
                parent_uid = self._format_uid(parent_node['type'], parent_node['id'])
                return {
                    "uid": uid,
                    "parent_uid": parent_uid,
                    "type": "marker",
                    "name": marker_data['title'],
                    "data": marker_data,
                    "ui_schema": self._get_marker_schema(),
                    "children": children
                }

        elif type_prefix == "npc":
            log("Handling as an NPC (leaf node)...", 1)
            with self.db.get_connection() as conn:
                row = conn.execute("SELECT * FROM npcs WHERE id=?", (pk,)).fetchone()
            if not row: return None
            data = dict(row)
            parent_node = self.db.get_node(data['node_id'])
            parent_uid = self._format_uid(parent_node['type'], parent_node['id'])
            return {"uid": uid, "parent_uid": parent_uid, "type": "npc", "name": data['name'], "data": data, "ui_schema": self._get_npc_schema(), "children": []}
        return None

    def update_node(self, uid: str, form_data: dict):
        if "-info" in uid:
            uid = uid.replace("-info", "")
        type_prefix, pk = self._parse_uid(uid)
        
        if type_prefix == "campaign":
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE campaigns SET name=?, theme_id=? WHERE id=?",
                    (form_data.get('name'), form_data.get('theme_id'), pk)
                )
                conn.commit()
        elif type_prefix in ["world_map", "local_map", "dungeon", "dungeon_level", "building_interior"]:
            name = form_data.pop('name', None)
            current_node = self.db.get_node(pk)
            meta = current_node.get('metadata', {})
            meta.update(form_data)
            self.db.update_node_data(pk, metadata=meta)
            if name:
                with self.db.get_connection() as conn:
                    conn.execute("UPDATE nodes SET name=? WHERE id=?", (name, pk))
                    conn.commit()
        elif type_prefix == "marker":
            self.db.update_marker(pk, title=form_data.get('title'), description=form_data.get('description'))
        elif type_prefix == "npc":
            self.db.update_npc(pk, form_data)
