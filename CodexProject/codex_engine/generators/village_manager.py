import pygame
from codex_engine.ui.ai_request_editor import AIRequestEditor

class VillageContentManager:
    def __init__(self, node, db, ai, screen): # <-- Accepts screen
        if not node or node['type'] != 'local_map':
            raise ValueError("VillageContentManager requires a 'local_map' node.")
        self.node = node
        self.db = db
        self.ai = ai
        self.screen = screen # <-- Stores screen
        self.is_generating = False

    def generate_details(self):
        """
        Handles the entire process: shows the complex UI, submits the async job,
        and defines the callback internally.
        """
        chain = [('node', self.node['id']), ('campaign', self.node.get('campaign_id'))]
        
        # Use the screen object to show the editor
        editor = AIRequestEditor(self.screen, self.ai.config, self.ai, chain, "Village Theme / Concept")
        
        if editor.result:
            prompt, svc, model, persist = editor.result

            if persist:
                scope, scope_id = chain[0]
                self.ai.config.set("active_service_id", svc, scope, scope_id)
                self.ai.config.set(f"service_{svc}_model", model, scope, scope_id)

            def on_generation_complete(result):
                print("[Callback] Received Village content.")
                if result:
                    self.persist_response(result)
                    # This event will be picked up by the main loop to trigger a final reload.
                    pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"action": "reload_node_callback"}))
                else:
                    print("[Callback] Village AI generation failed.")
            
            self._start_generation_internal(
                theme=prompt,
                callback=on_generation_complete,
                service_override=svc,
                model_override=model
            )

    def _start_generation_internal(self, theme="", callback=None, service_override=None, model_override=None):
        if not callback: return False

        context = self._gather_context()
        prompt = self._build_prompt(context, theme)
        
        schema = """
        {
            "overview": "...",
            "locations": { "Building Name 1": "description..." },
            "npcs": [ {"name":"...", "role":"...", "personality":"...", "hook":"...", "location":"Building Name 1"} ],
            "rumors": [ "rumor 1", "rumor 2" ]
        }
        """

        self.is_generating = True
        
        def callback_wrapper(result):
            self.is_generating = False
            callback(result)

        self.ai.submit_json_request(
            prompt=prompt, schema_hint=schema,
            context_chain=[('node', self.node['id'])],
            callback=callback_wrapper,
            service_override=service_override, model_override=model_override
        )
        return True

    def _gather_context(self):
        context = { "name": self.node['name'], "locations": [] }
        markers = self.db.get_markers(self.node['id'])
        for m in markers:
            if not m.get('metadata', {}).get('is_view_marker'):
                context['locations'].append({ "name": m['title'] })
        return context

    def _build_prompt(self, context, theme):
        locations_str = "\n".join([f"- {loc['name']}" for loc in context['locations']])
        theme_directive = f"The primary theme is: '{theme}'. All content MUST strongly reflect this theme." if theme else ""
        return (
            f"You are a TTRPG content generator for the location '{context['name']}'.\n{theme_directive}\n\n"
            f"Locations to describe:\n{locations_str}\n\n"
            "Return a single JSON object with 'overview' (paragraph), 'locations' (dictionary of name: description), 'npcs' (list of 4-5 NPC objects), and 'rumors' (list of 4-6 plot hooks)."
        )
        
    def persist_response(self, data):
        if not data: return
        locations = data.get('locations', {})
        markers = self.db.get_markers(self.node['id'])
        for m in markers:
            if m['title'] in locations:
                self.db.update_marker(m['id'], description=locations[m['title']])
        with self.db.get_connection() as conn:
             conn.execute("DELETE FROM npcs WHERE node_id = ?", (self.node['id'],))
        npcs_from_ai = data.get('npcs', [])
        for npc_data in npcs_from_ai:
            if npc_data.get('name'):
                self.db.add_npc(self.node['id'], npc_data)
        node_meta = self.node.get('metadata', {})
        node_meta['overview'] = data.get('overview')
        node_meta['rumors'] = data.get('rumors', [])
        self.db.update_node_data(self.node['id'], metadata=node_meta)
