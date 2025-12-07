import os
from .ai.gemini import GeminiProvider

class AIManager:
    def __init__(self):
        # Configuration logic happens here, not in the UI
        # Future: Could check config file for "provider": "openai" vs "gemini"
        self.provider = GeminiProvider()

    def is_available(self):
        return self.provider.is_available()

    def generate_json(self, prompt, schema_hint):
        return self.provider.generate_json(prompt, schema_hint)

    def generate_text(self, prompt, context=""):
        return self.provider.generate_text(prompt, context)
