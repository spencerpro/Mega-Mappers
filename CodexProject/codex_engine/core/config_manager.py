import os
from .db_manager import DBManager

class ConfigManager:
    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        # No default providers. User must add them.
        self.defaults = {} 

    def get(self, key: str, context_chain: list = None):
        # 1. Check Context Hierarchy
        if context_chain:
            for scope, scope_id in context_chain:
                val = self.db.get_setting_raw(key, scope, scope_id)
                if val is not None:
                    return val

        # 2. Check Global
        val = self.db.get_setting_raw(key, 'global', None)
        if val is not None:
            return val

        # 3. Defaults
        return self.defaults.get(key)

    def set(self, key: str, value, scope: str = 'global', scope_id: int = None):
        self.db.set_setting(key, value, scope, scope_id)
