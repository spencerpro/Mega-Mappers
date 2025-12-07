import tkinter as tk
from tkinter import ttk, scrolledtext
import json

class NativeMarkerEditor:
    def __init__(self, marker_data, map_context, on_save, on_ai_gen=None):
        self.marker_data = marker_data
        self.on_save = on_save
        self.on_ai_gen = on_ai_gen
        
        # Determine initial values
        self.title_val = marker_data.get('title', '')
        self.desc_val = marker_data.get('description', '')
        self.symbol_val = marker_data.get('symbol', 'star')
        
        # Handle Metadata JSON
        meta_raw = marker_data.get('metadata', {})
        if isinstance(meta_raw, str):
            self.meta_val = meta_raw 
        else:
            self.meta_val = json.dumps(meta_raw, indent=4)

        # Setup Main Window
        self.root = tk.Tk()
        self.root.title(f"Edit Marker: {self.title_val}")
        self.root.geometry("600x700")
        
        # Styles
        style = ttk.Style()
        style.theme_use('clam')

        self._build_ui(map_context)
        
        # Center window
        self.root.eval('tk::PlaceWindow . center')
        self.root.mainloop()

    def _build_ui(self, context):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Title
        ttk.Label(main_frame, text="Title:").pack(anchor=tk.W)
        self.entry_title = ttk.Entry(main_frame)
        self.entry_title.insert(0, self.title_val)
        self.entry_title.pack(fill=tk.X, pady=(0, 10))

        # 2. Type/Symbol
        ttk.Label(main_frame, text="Type:").pack(anchor=tk.W)
        self.combo_type = ttk.Combobox(main_frame, state="readonly")
        
        if context == "world_map":
            self.combo_type['values'] = ["village", "dungeon", "landmark"]
        else:
            self.combo_type['values'] = ["building", "dungeon", "portal", "note"]
            
        # Map symbol back to readable type if possible, or default
        current_type = "note"
        for t in self.combo_type['values']:
            if t in self.symbol_val: current_type = t
        
        self.combo_type.set(current_type)
        self.combo_type.pack(fill=tk.X, pady=(0, 10))

        # 3. Description
        ttk.Label(main_frame, text="Description (Public Tooltip):").pack(anchor=tk.W)
        self.text_desc = scrolledtext.ScrolledText(main_frame, height=5)
        self.text_desc.insert(tk.END, self.desc_val)
        self.text_desc.pack(fill=tk.X, pady=(0, 10))

        # 4. Metadata (JSON)
        ttk.Label(main_frame, text="Metadata (JSON Configuration):").pack(anchor=tk.W)
        self.text_meta = scrolledtext.ScrolledText(main_frame, height=10, font=("Consolas", 10))
        self.text_meta.insert(tk.END, self.meta_val)
        self.text_meta.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 5. Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.root.destroy).pack(side=tk.LEFT, padx=5)
        
        if self.on_ai_gen:
            ttk.Button(btn_frame, text="✨ AI Generate Details", command=self.run_ai).pack(side=tk.RIGHT, padx=5)

    def run_ai(self):
        # Disable button to prevent spam
        title = self.entry_title.get()
        mtype = self.combo_type.get()
        existing_desc = self.text_desc.get("1.0", tk.END).strip()
        
        if self.on_ai_gen:
            # We pass the metadata context too so AI knows what fields to fill
            result = self.on_ai_gen(mtype, title, existing_desc)
            if result:
                # Update Description
                if 'description' in result:
                    self.text_desc.delete("1.0", tk.END)
                    self.text_desc.insert(tk.END, result['description'])
                
                # Update Metadata (Merge)
                if 'metadata' in result:
                    try:
                        current_meta = json.loads(self.text_meta.get("1.0", tk.END))
                    except:
                        current_meta = {}
                    
                    current_meta.update(result['metadata'])
                    self.text_meta.delete("1.0", tk.END)
                    self.text_meta.insert(tk.END, json.dumps(current_meta, indent=4))

    def save(self):
        # Validate JSON
        try:
            meta_obj = json.loads(self.text_meta.get("1.0", tk.END))
        except json.JSONDecodeError as e:
            tk.messagebox.showerror("JSON Error", f"Invalid Metadata JSON:\n{e}")
            return

        # Map Type back to Symbol icon
        # Simple mapping for now
        chosen_type = self.combo_type.get()
        symbol_map = {
            "village": "house", "building": "house",
            "dungeon": "skull", "landmark": "star",
            "portal": "star", "note": "star"
        }
        
        # Call callback
        self.on_save(
            self.marker_data.get('id'),
            symbol_map.get(chosen_type, "star"), # symbol
            self.entry_title.get(),              # title
            self.text_desc.get("1.0", tk.END).strip(), # note
            meta_obj                             # metadata dict
        )
        self.root.destroy()
