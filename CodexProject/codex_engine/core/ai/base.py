from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    def configure(self, api_key: str, base_url: str = None): pass
    @abstractmethod
    def list_models(self) -> list[str]: pass
    @abstractmethod
    def generate_text(self, model: str, prompt: str, context: str) -> str: pass
    @abstractmethod
    def generate_json(self, model: str, prompt: str, schema: str) -> dict: pass
