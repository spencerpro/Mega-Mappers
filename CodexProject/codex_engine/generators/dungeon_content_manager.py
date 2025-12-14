import pygame

class DungeonContentManager:
    def __init__(self, node, db, ai):
        self.node = node
        self.db = db
        self.ai = ai

    def start_generation(self, theme="", context_for_ai=None, callback=None, service_override=None, model_override=None):
        """
        Formats a prompt and submits a job to the central AI Manager.
        The provided callback will be executed upon completion.
        """
        
        if not context_for_ai or not callback:
            print("Error: start_generation requires context_for_ai and a callback.")
            return False
        
        prompt = self._build_prompt(context_for_ai, theme)
        schema = '{"1": "A short, atmospheric description...", "2": "..."}'
        

        
        def callback_wrapper(result):
            callback(result)

        self.ai.submit_json_request(
            prompt=prompt,
            schema_hint=schema,
            context_chain=[('node', self.node['id'])],
            callback=callback_wrapper, # Pass the wrapper
            service_override=service_override,
            model_override=model_override
        )
        return True

    def _build_prompt(self, context, theme=""):
        """Builds the AI prompt from a generic context dictionary."""
        room_list_str = "\n".join([f"- {room['title']}" for room in context.get('rooms', [])])
        
        prompt = (f"You are a TTRPG content generator. Your style is concise and evocative.\n")
        if theme:
            prompt += f"MANDATORY THEME: Every description you write MUST be strictly focused on the theme: '{theme}'. Use vocabulary and imagery associated with this theme.\n"
        prompt += (f"Generate a unique, one-sentence description for each of the following rooms in the dungeon level '{context.get('name', 'this area')}'.\n\n"
                   f"Rooms to describe:\n{room_list_str}\n\n"
                   "Return a single JSON object where each key is the room title (e.g., '1', '2') and the value is the description string.")
        return prompt
