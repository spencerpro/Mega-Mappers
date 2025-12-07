import json

class VillageContentManager:
    def __init__(self, node, db, ai):
        if not node or node['type'] != 'local_map':
            raise ValueError("VillageContentManager requires a 'local_map' node.")
        self.node = node
        self.db = db
        self.ai = ai

    def generate_details(self):
        """The main method that drives the AI content generation for the village."""
        if not self.ai.is_available():
            print("AI Service Unavailable.")
            return

        context = self._gather_context()
        prompt = self._build_prompt(context)

        # DEFINE SCHEMA HINT
        schema = """
        {
            "overview": "...",
            "locations": { "Building Name 1": "description..." },
            "npcs": [ {"name":"...", "role":"...", "personality":"...", "hook":"...", "location":"Building Name 1"} ],
            "rumors": [ "rumor 1", "rumor 2" ]
        }
        """

        print("Sending request to AI...")
        response_data = self.ai.generate_json(prompt, schema_hint=schema)

        if not response_data:
            print("AI generation failed.")
            return
            
        print("AI response received. Updating database...")
        self._persist_response(response_data)

    def _gather_context(self):
        """Collects all known data about the village to inform the AI."""
        context = {
            "name": self.node['name'],
            "overview": self.node['metadata'].get('overview', 'Not yet described.'),
            "locations": [],
            "npcs": []
        }
        
        markers = self.db.get_markers(self.node['id'])
        for m in markers:
            context['locations'].append({
                "name": m['title'],
                "description": m['description'] if m['description'] else "Not yet described."
            })

        context['npcs'] = self.db.get_npcs_for_node(self.node['id'])
        return context

    def _build_prompt(self, context):
        """Constructs a detailed, context-aware prompt for the AI."""
        locations_str = "\n".join([f"- {loc['name']} (Existing Desc: '{loc['description']}')" for loc in context['locations']])
        npcs_str = "\n".join([f"- {npc['name']} ({npc['role']})" for npc in context['npcs']]) if context['npcs'] else "None"

        return (
            f"You are a TTRPG content generator. Enhance the details for the village of '{context['name']}'.\n"
            f"Here is the data I already have. Fill in any blanks, add more detail, and ensure consistency. Do not remove or contradict existing data.\n"
            f"Current Overview: {context['overview']}\n\n"
            f"Locations to describe:\n{locations_str}\n\n"
            f"Known NPCs (enhance these and add 2-3 new ones):\n{npcs_str}\n\n"
            "Return a single JSON object with this exact structure:\n"
            "- 'overview': An improved, atmospheric paragraph about the village.\n"
            "- 'locations': A dictionary where each key is a location name, and the value is an improved, one-sentence description.\n"
            "- 'npcs': A list of all NPC objects (both enhanced existing and new). Each object must have keys: 'name', 'role', 'personality', 'hook', and 'location' (must be a location name from the list).\n"
            "- 'rumors': A list of 4-6 new, interesting plot hooks or rumors."
        )

    def _persist_response(self, data):
        """Updates the database with the data returned from the AI."""
        locations = data.get('locations', {})
        markers = self.db.get_markers(self.node['id'])
        for m in markers:
            if m['title'] in locations:
                self.db.update_marker(m['id'], description=locations[m['title']])

        npcs_from_ai = data.get('npcs', [])
        existing_npcs_map = {npc['name']: npc for npc in self.db.get_npcs_for_node(self.node['id'])}
        
        for npc_data in npcs_from_ai:
            npc_name = npc_data.get('name')
            if not npc_name: continue
            
            if npc_name in existing_npcs_map:
                npc_id = existing_npcs_map[npc_name]['id']
                self.db.update_npc(npc_id, npc_data)
            else:
                self.db.add_npc(self.node['id'], npc_data)
        
        node_meta = self.node.get('metadata', {})
        node_meta['overview'] = data.get('overview')
        node_meta['rumors'] = data.get('rumors', [])
        self.db.update_node_data(self.node['id'], metadata=node_meta)
