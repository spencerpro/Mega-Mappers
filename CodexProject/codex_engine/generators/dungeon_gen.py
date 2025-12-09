import pygame
import random
import math
import heapq

# --- SETTINGS ---
TURN_PENALTY = 5
ADJACENCY_PENALTY = 20
ROOM_PADDING = 3

class Room:
    def __init__(self, x, y, width, height, id):
        self.id = id
        self.rect = pygame.Rect(x, y, width, height)
        self.center = self.rect.center
    def intersects(self, other_room):
        return self.rect.colliderect(other_room.rect.inflate(ROOM_PADDING * 2, ROOM_PADDING * 2))

class AStarNode:
    def __init__(self, parent=None, position=None, direction=(0,0)):
        self.parent, self.position, self.direction = parent, position, direction
        self.g, self.h, self.f = 0, 0, 0
    def __eq__(self, other): return self.position == other.position
    def __lt__(self, other): return self.f < other.f
    def __hash__(self): return hash(self.position)

class DungeonGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        # Configurable settings
        self.world_w = 60
        self.world_h = 60
        self.min_room_size = 6
        self.max_room_size = 12
        self.max_rooms = 40

    def generate_dungeon_complex(self, parent_node, marker, campaign_id, levels=3):
        previous_level_node_id = parent_node['id']
        first_level_id = None
        
        for i in range(1, levels + 1):
            level_name = f"{marker['title']} - Level {i}"
            
            node_id = self.db.create_node(
                campaign_id, "dungeon_level", parent_node['id'],
                int(marker['world_x']), int(marker['world_y']), level_name
            )
            
            if i == 1:
                first_level_id = node_id

            grid, rooms = self._generate_layout()
            
            self.db.update_node_data(node_id, geometry={
                "grid": grid, 
                "width": self.world_w, 
                "height": self.world_h,
                "rooms": [list(r.rect) for r in rooms]
            })

            if rooms:
                # --- FIX: ADD ROOM NUMBER MARKERS ---
                for room in rooms:
                    self.db.add_marker(
                        node_id, 
                        room.rect.x + 0.5, # Place in top-left corner of room
                        room.rect.y + 0.5,
                        'room_number',
                        f"{room.id + 1}", # The text to be displayed
                        "An unexplored chamber."
                    )

                # Stairs Up (in the first room)
                up_room = rooms[0]
                self.db.add_marker(node_id, up_room.center[0], up_room.center[1], "stairs_up", "Stairs Up", "", metadata={"portal_to": previous_level_node_id})

                # Stairs Down (in the last room, if not the last level)
                if i < levels:
                    down_room = rooms[-1]
                    self.db.add_marker(node_id, down_room.center[0], down_room.center[1], "stairs_down", "Stairs Down", "", metadata={})

            previous_level_node_id = node_id

        return first_level_id

    def generate_single_room(self, parent_node, marker, campaign_id):
        w, h = 20, 20
        grid = [[1 for _ in range(w)] for _ in range(h)]
        nid = self.db.create_node(campaign_id, "dungeon_level", parent_node['id'], int(marker['world_x']), int(marker['world_y']), "Single Room")
        self.db.update_node_data(nid, geometry={"grid": grid, "width": w, "height": h})
        return nid

    def _generate_layout(self):
        grid = [[0 for _ in range(self.world_w)] for _ in range(self.world_h)]
        rooms = []
        
        for _ in range(5000):
            if len(rooms) >= self.max_rooms: break
            w = random.randint(self.min_room_size, self.max_room_size)
            h = random.randint(self.min_room_size, self.max_room_size)
            x = random.randint(2, self.world_w - w - 2)
            y = random.randint(2, self.world_h - h - 2)
            new_room = Room(x, y, w, h, len(rooms))
            if not any(new_room.intersects(other) for other in rooms):
                rooms.append(new_room)
        
        rooms.sort(key=lambda r: (r.rect.y, r.rect.x))
        for i, r in enumerate(rooms): r.id = i
        
        for r in rooms:
            for ry in range(r.rect.height):
                for rx in range(r.rect.width):
                    grid[r.rect.y + ry][r.rect.x + rx] = 1

        if len(rooms) > 1:
            self._route_corridors(grid, rooms)

        return grid, rooms

    def _route_corridors(self, grid, rooms):
        room_map = {r.id: r for r in rooms}
        edges = []
        for i, r1 in enumerate(rooms):
            for j in range(i + 1, len(rooms)):
                r2 = rooms[j]
                dist = math.hypot(r1.center[0] - r2.center[0], r1.center[1] - r2.center[1])
                edges.append((dist, r1.id, r2.id))
        
        edges.sort()
        connections, mst_pairs = [], set()
        parent = {r.id: r.id for r in rooms}
        
        def find(id):
            if parent[id] == id: return id
            parent[id] = find(parent[id]); return parent[id]
            
        def union(id1, id2):
            r1, r2 = find(id1), find(id2)
            if r1 != r2: parent[r1] = r2; return True
            return False
            
        for _, r1_id, r2_id in edges:
            if union(r1_id, r2_id):
                connections.append((room_map[r1_id], room_map[r2_id]))
                mst_pairs.add(tuple(sorted((r1_id, r2_id))))
                
        extra_edges = [e for e in edges if tuple(sorted((e[1], e[2]))) not in mst_pairs]
        random.shuffle(extra_edges)
        connections.extend([(room_map[e[1]], room_map[e[2]]) for e in extra_edges[:len(rooms)//4]])

        for r1, r2 in connections:
            start_pos, end_pos = r1.center, r2.center
            path = self._find_path_a_star(grid, start_pos, end_pos)
            if path:
                for p in path:
                    if grid[p[1]][p[0]] == 0: grid[p[1]][p[0]] = 2
            else:
                self._force_corridor_l_shape(grid, start_pos, end_pos)

    def _force_corridor_l_shape(self, grid, start, end):
        x, y = start
        target_x, target_y = end
        step_x = 1 if target_x > x else -1
        step_y = 1 if target_y > y else -1
        while x != target_x:
            if 0 <= x < self.world_w and 0 <= y < self.world_h and grid[y][x] == 0: grid[y][x] = 2
            x += step_x
        while y != target_y:
            if 0 <= x < self.world_w and 0 <= y < self.world_h and grid[y][x] == 0: grid[y][x] = 2
            y += step_y

    def _find_path_a_star(self, grid, start, end):
        start_node = AStarNode(None, start)
        open_list, closed_set = [start_node], set()
        
        while open_list:
            current = heapq.heappop(open_list)
            if current.position in closed_set: continue
            closed_set.add(current.position)
            
            if current.position == end:
                path = []
                while current: path.append(current.position); current = current.parent
                return path[::-1]
            
            (x, y) = current.position
            for dx, dy in [(0,-1), (0,1), (-1,0), (1,0)]:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.world_w and 0 <= ny < self.world_h): continue
                
                cost = 1
                if grid[ny][nx] == 1: cost += 100
                if current.parent and (dx, dy) != current.direction: cost += TURN_PENALTY
                
                adj = 0
                for ax, ay in [(0,-1),(0,1),(-1,0),(1,0)]:
                    cx, cy = nx+ax, ny+ay
                    if 0 <= cx < self.world_w and 0 <= cy < self.world_h and grid[cy][cx] == 1:
                        adj = ADJACENCY_PENALTY; break
                
                new_node = AStarNode(current, (nx, ny), (dx, dy))
                new_node.g = current.g + cost + adj
                new_node.h = abs(nx - end[0]) + abs(ny - end[1])
                new_node.f = new_node.g + new_node.h
                heapq.heappush(open_list, new_node)
        
        return None
