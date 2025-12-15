# --- START OF FILE CodexProject/codex_server/schemas.py ---
from pydantic import BaseModel
from typing import Optional, Dict, List, Any, Union

# The instructions for the Frontend
class FieldDefinition(BaseModel):
    key: str                # The JSON key (e.g., "overview")
    label: str              # The display label (e.g., "Area Overview")
    type: str               # "text", "textarea", "number", "select", "list", "json"
    readonly: bool = False
    options: Optional[List[str]] = None # For select dropdowns

class TreeNodeResponse(BaseModel):
    uid: str
    parent_uid: Optional[str]
    type: str           # "campaign", "map", "marker", "npc"
    name: str
    
    # The actual values (e.g., { "title": "Inn", "desc": "Smells like ale" })
    data: Dict[str, Any]
    
    # The instructions on how to edit 'data'
    ui_schema: List[FieldDefinition]
    
    # Navigation
    children: List['TreeNodeSummary'] = []

class TreeNodeSummary(BaseModel):
    uid: str
    type: str
    name: str
    icon: str = "📄"

class NodeUpdate(BaseModel):
    data: Dict[str, Any]
