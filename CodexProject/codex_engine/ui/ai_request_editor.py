import pygame
from codex_engine.ui.widgets import Button, Dropdown, TextArea, Checkbox
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT

class AIRequestEditor:
    def __init__(self, screen, config, ai, context_chain, prompt_label="Theme Description"):
        self.screen = screen
        self.config = config
        self.ai = ai
        self.context_chain = context_chain
        
        self.result = None # Returns (prompt, service_id, model_id, persist_bool)
        
        self.font = pygame.font.Font(None, 24)
        self.font_title = pygame.font.Font(None, 36)
        
        # Layout
        self.w, self.h = 700, 600
        self.rect = pygame.Rect(0, 0, self.w, self.h)
        self.rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        
        # --- INIT DATA ---
        registry = self.ai.get_service_registry()
        
        # 1. Determine Current Active Service (Local Override or Inherited)
        # We want to pre-select whatever is currently active
        current_svc_id = self.config.get("active_service_id", self.context_chain)
        
        # If no explicit setting, resolve what the AI Manager would default to
        if not current_svc_id and registry:
            current_svc_id = registry[0]['id']
            
        svc_opts = [{'id': s['id'], 'name': s['name']} for s in registry]
        
        # 2. Determine Current Model
        current_model = self.config.get(f"service_{current_svc_id}_model", self.context_chain)
        model_opts = [{'id': current_model, 'name': str(current_model)}] if current_model else []

        # --- WIDGETS ---
        y = self.rect.y + 60
        
        # Prompt Area
        self.lbl_prompt = self.font.render(f"{prompt_label}:", True, (200, 200, 200))
        self.text_area = TextArea(self.rect.x + 30, y + 10, self.w - 60, 200, self.font)
        
        y += 240
        
        # Config Section Header
        self.lbl_conf = self.font_title.render("AI Configuration", True, (150, 150, 180))
        self.conf_y_start = y
        
        y += 40
        
        # Service Dropdown
        self.lbl_svc = self.font.render("Service:", True, (200, 200, 200))
        self.dd_svc = Dropdown(self.rect.x + 100, y-5, 200, 30, self.font, svc_opts, initial_id=current_svc_id)
        
        # Model Dropdown
        self.lbl_model = self.font.render("Model:", True, (200, 200, 200))
        self.dd_model = Dropdown(self.rect.x + 400, y-5, 200, 30, self.font, model_opts, initial_id=current_model)
        
        y += 50
        
        # Fetch Button
        self.btn_fetch = Button(self.rect.x + 400, y, 120, 30, "Fetch Models", self.font, (60, 60, 80), (80, 80, 100), (255, 255, 255), self._fetch_models)
        
        y += 60
        
        # Persist Checkbox
        scope_name = "Global" if not context_chain else "this Map"
        self.chk_persist = Checkbox(self.rect.x + 30, y, 20, f"Save settings as default for {scope_name}", self.font)
        
        # Action Buttons
        self.btn_go = Button(self.rect.right - 130, self.rect.bottom - 60, 100, 40, "Generate", self.font, (50, 150, 50), (80, 180, 80), (255, 255, 255), self._generate)
        self.btn_cancel = Button(self.rect.right - 250, self.rect.bottom - 60, 100, 40, "Cancel", self.font, (150, 50, 50), (180, 80, 80), (255, 255, 255), self._cancel)

        self.running = True
        self.run()

    def _fetch_models(self):
        sid = self.dd_svc.get_selected_id()
        if not sid: return
        
        # Fetch using current context chain to find keys
        models = self.ai.get_available_models_for_service(sid, self.context_chain)
        self.dd_model.options = [{'id': m, 'name': m} for m in models]
        if self.dd_model.options: 
            self.dd_model.selected_idx = 0

    def _generate(self):
        prompt = self.text_area.text
        svc = self.dd_svc.get_selected_id()
        model = self.dd_model.get_selected_id()
        persist = self.chk_persist.checked
        
        if prompt and svc and model:
            self.result = (prompt, svc, model, persist)
            self.running = False

    def _cancel(self):
        self.running = False

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT: self.running = False
                
                self.text_area.handle_event(e)
                
                # Check for Service change
                prev_svc = self.dd_svc.get_selected_id()
                if self.dd_svc.handle_event(e):
                    curr_svc = self.dd_svc.get_selected_id()
                    if curr_svc != prev_svc:
                        # Reset model DD on service change
                        # Try to get default model from config for this new service
                        def_model = self.config.get(f"service_{curr_svc}_model", self.context_chain)
                        if def_model:
                            self.dd_model.options = [{'id': def_model, 'name': str(def_model)}]
                            self.dd_model.selected_idx = 0
                        else:
                            self.dd_model.options = []
                            self.dd_model.selected_idx = -1

                self.dd_model.handle_event(e)
                self.chk_persist.handle_event(e)
                
                self.btn_fetch.handle_event(e)
                self.btn_go.handle_event(e)
                self.btn_cancel.handle_event(e)

            # Draw
            self.screen.fill((0,0,0))
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0,0,0,180))
            self.screen.blit(overlay, (0,0))
            
            # Panel
            pygame.draw.rect(self.screen, (40, 40, 50), self.rect, border_radius=10)
            pygame.draw.rect(self.screen, (100, 100, 120), self.rect, 2, border_radius=10)
            
            self.screen.blit(self.lbl_prompt, (self.rect.x + 30, self.rect.y + 35))
            self.text_area.draw(self.screen)
            
            self.screen.blit(self.lbl_conf, (self.rect.x + 30, self.conf_y_start))
            
            self.screen.blit(self.lbl_svc, (self.rect.x + 30, self.dd_svc.rect.y + 8))
            self.dd_svc.draw(self.screen)
            
            self.screen.blit(self.lbl_model, (self.rect.x + 330, self.dd_model.rect.y + 8))
            self.dd_model.draw(self.screen)
            
            self.btn_fetch.draw(self.screen)
            self.chk_persist.draw(self.screen)
            
            self.btn_go.draw(self.screen)
            self.btn_cancel.draw(self.screen)
            
            # Handle dropdown overlaps
            if self.dd_svc.is_open: self.dd_svc.draw(self.screen)
            if self.dd_model.is_open: self.dd_model.draw(self.screen)

            pygame.display.flip()
            clock.tick(30)
