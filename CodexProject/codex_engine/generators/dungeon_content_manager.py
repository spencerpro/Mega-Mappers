class DungeonContentManager:
    def __init__(self, node, db, ai):
        if not node or node['type'] != 'dungeon_level':
            raise ValueError("DungeonContentManager requires a 'dungeon_level' node.")
        self.node = node
        self.db = db
        self.ai = ai

    def populate_descriptions(self, theme=""):
        """Drives the AI content generation for the dungeon rooms."""
        if not self.ai.is_available():
            print("AI Service Unavailable.")
            return False

        context = self._gather_context()
        if not context['rooms']:
            print("No rooms found to describe.")
            return False
            
        prompt = self._build_prompt(context, theme)

        schema = '{"1": "A short, atmospheric description...", "2": "..."}'

        print("Sending request to AI for dungeon room descriptions...")
        response_data = self.ai.generate_json(prompt, schema_hint=schema)

        if not response_data:
            print("AI generation failed.")
            return False
            
        print("AI response received. Updating database...")
        self._persist_response(response_data)
        return True

    def _gather_context(self):
        """Collects all room markers to inform the AI."""
        context = {
            "name": self.node['name'],
            "rooms": []
        }
        
        all_markers = self.db.get_markers(self.node['id'])
        for m in all_markers:
            if m.get('symbol') == 'room_number':
                context['rooms'].append({ "title": m['title'], "id": m['id'] })
        
        try:
            context['rooms'].sort(key=lambda r: int(r['title']))
        except ValueError:
            context['rooms'].sort(key=lambda r: r['title']) # Fallback for non-numeric titles
        return context

    def _build_prompt(self, context, theme=""):
        """Constructs a detailed, context-aware prompt for the AI."""
        room_list_str = "\n".join([f"- {room['title']}" for room in context['rooms']])

        prompt = (
            f"You are a TTRPG content generator. Your style is concise and evocative, like a classic dungeon module.\n"
        )
        
        # Conditionally add the theme to the prompt
        if theme:
            prompt += f"The theme for this area is: '{theme}'. Generate descriptions that fit this theme.\n"

        prompt += (
            f"Generate a unique, one-sentence description for each of the following rooms in the dungeon level '{context['name']}'.\n\n"
            f"Rooms to describe:\n{room_list_str}\n\n"
            "Return a single JSON object where each key is the room title (e.g., '1', '2') and the value is the description string."
        )
        return prompt

    def _persist_response(self, data):
        """Updates the room markers with the descriptions from the AI."""
        all_markers = self.db.get_markers(self.node['id'])
        for m in all_markers:
            if m['title'] in data:
                self.db.update_marker(m['id'], description=data[m['title']])
