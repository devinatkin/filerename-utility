import os
import json
import argparse
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading

# Import the function from the external file.
from suggest_file_names import suggest_new_filename


def unique_suggestion(filepath, existing_names, method="slugify", attempts=3):
    """Generate a filename suggestion that is unique among ``existing_names``.

    If a conflict is detected, try ``attempts`` times to regenerate.  After the
    limit is reached, append ``-N`` to the final suggestion until it becomes
    unique.
    """
    ext = os.path.splitext(filepath)[1]
    dir_name = os.path.dirname(filepath)

    last_name = "file"
    for _ in range(attempts):
        result = suggest_new_filename(filepath, method=method)
        name = result.get("suggested_filename") or "file"
        candidate = os.path.join(dir_name, name + ext)
        exists_elsewhere = os.path.exists(candidate) and os.path.abspath(candidate) != os.path.abspath(filepath)
        if name not in existing_names and not exists_elsewhere:
            return name
        last_name = name

    base = last_name
    counter = 1
    new_name = base
    while True:
        candidate = os.path.join(dir_name, new_name + ext)
        exists_elsewhere = os.path.exists(candidate) and os.path.abspath(candidate) != os.path.abspath(filepath)
        if new_name not in existing_names and not exists_elsewhere:
            break
        new_name = f"{base}-{counter}"
        counter += 1
    return new_name

class FileRenamerUI:
    def __init__(self, master, method="slugify"):
        self.master = master
        self.method = method
        master.title("AI File Renamer")
        master.geometry("700x500")

        self.files = []  # list of file paths
        self.file_data = {}  # key: filepath, value: suggested filename

        # Create UI elements
        self.top_frame = tk.Frame(master)
        self.top_frame.pack(pady=10)

        self.select_btn = tk.Button(self.top_frame, text="Select Files", command=self.select_files)
        self.select_btn.pack(side=tk.LEFT, padx=5)

        self.rename_btn = tk.Button(self.top_frame, text="Rename Selected Files", command=self.rename_files, state=tk.DISABLED)
        self.rename_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(master, orient="horizontal", length=600, mode="determinate")
        self.progress.pack(pady=10)

        self.table_frame = tk.Frame(master)
        self.table_frame.pack(fill=tk.BOTH, expand=True)

        # Create treeview for file list
        columns = ("orig_name", "suggested_name", "rename", "regenerate")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings")
        self.tree.heading("orig_name", text="Current Filename")
        self.tree.heading("suggested_name", text="Suggested Filename")
        self.tree.heading("rename", text="Rename")
        self.tree.heading("regenerate", text="Regenerate")
        self.tree.column("orig_name", width=250)
        self.tree.column("suggested_name", width=250)
        self.tree.column("rename", width=80)
        self.tree.column("regenerate", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Dict to hold IntVar for checkbuttons
        self.rename_vars = {}

    def select_files(self):
        filepaths = filedialog.askopenfilenames(title="Select Files to Rename")
        if not filepaths:
            return
        self.files = list(filepaths)
        self.tree.delete(*self.tree.get_children())
        self.rename_vars = {}
        self.file_data = {}
        self.rename_btn.config(state=tk.DISABLED)
        # Start the suggestion process in a separate thread
        threading.Thread(target=self.process_files, daemon=True).start()

    def process_files(self):
        total_files = len(self.files)
        self.master.after(0, lambda: self.progress.config(maximum=total_files))
        for idx, filepath in enumerate(self.files, start=1):
            # Get a unique suggested filename for each file
            existing = set(self.file_data.values())
            suggested_name = unique_suggestion(filepath, existing, method=self.method)
            self.file_data[filepath] = suggested_name

            def update_ui(idx=idx, filepath=filepath, suggested_name=suggested_name):
                # Insert row in treeview
                var = tk.IntVar(value=1)
                self.rename_vars[filepath] = var
                self.tree.insert("", "end", iid=filepath,
                                 values=(os.path.basename(filepath), suggested_name, "", ""),
                                 tags=("cb",))
                # After insertion, overlay widgets on cells
                self.create_checkbox(filepath)
                self.create_regen_button(filepath)
                # Update progress bar
                self.progress["value"] = idx
                self.master.update_idletasks()
            self.master.after(0, update_ui)
        def finalize():
            self.rename_btn.config(state=tk.NORMAL)
            messagebox.showinfo("Completed", "Filename suggestions generated.")
        self.master.after(0, finalize)

    def create_checkbox(self, filepath):
        # Get tree item bbox for the "rename" column
        bbox = self.tree.bbox(filepath, column="rename")
        if not bbox:
            # If widget is not visible, schedule after a delay.
            self.master.after(100, self.create_checkbox, filepath)
            return
        x, y, width, height = bbox
        var = self.rename_vars[filepath]
        cb = tk.Checkbutton(self.tree, variable=var)
        cb.place(x=x + width // 2, y=y + height // 2, anchor="center")

    def create_regen_button(self, filepath):
        """Place a regenerate button in the appropriate table cell."""
        bbox = self.tree.bbox(filepath, column="regenerate")
        if not bbox:
            self.master.after(100, self.create_regen_button, filepath)
            return
        x, y, width, height = bbox
        btn = tk.Button(
            self.tree,
            text="Regenerate",
            command=lambda p=filepath: self.regenerate_filename(p),
        )
        btn.place(x=x + width // 2, y=y + height // 2, anchor="center")

    def regenerate_filename(self, filepath):
        """Regenerate a unique filename suggestion for ``filepath``."""
        existing = set(self.file_data.values()) - {self.file_data.get(filepath)}
        new_name = unique_suggestion(filepath, existing, method=self.method)
        self.file_data[filepath] = new_name
        self.tree.set(filepath, "suggested_name", new_name)
    
    def rename_files(self):
        errors = []
        for filepath in self.files:
            if self.rename_vars.get(filepath, tk.IntVar()).get():
                dir_name = os.path.dirname(filepath)
                ext = os.path.splitext(filepath)[1]  # Preserve original extension
                new_base = self.file_data.get(filepath, "")
                if not new_base:
                    continue
                # Construct new path
                new_path = os.path.join(dir_name, new_base + ext)
                if os.path.abspath(new_path) == os.path.abspath(filepath):
                    continue
                try:
                    os.rename(filepath, new_path)
                except Exception as e:
                    errors.append(f"Failed to rename {filepath}: {e}")
        if errors:
            messagebox.showerror("Error", "\n".join(errors))
        else:
            messagebox.showinfo("Success", "Files renamed successfully.")
        # Clear files list and reset UI
        self.files = []
        self.tree.delete(*self.tree.get_children())
        self.progress["value"] = 0
        self.rename_btn.config(state=tk.DISABLED)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI File Renamer")
    parser.add_argument("files", nargs="*", help="Files to process in CLI mode")
    parser.add_argument("-m", "--method", choices=["slugify", "gemma"], default="slugify",
                        help="Suggestion method")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of GUI")
    parser.add_argument("--rename", action="store_true", help="Rename files using suggestions (CLI mode)")
    args = parser.parse_args()

    if args.cli:
        used_names = set()
        for path in args.files:
            new_name = unique_suggestion(path, used_names, method=args.method)
            used_names.add(new_name)
            print(json.dumps({"file": path, "suggested": new_name}, indent=2))
            if args.rename:
                ext = os.path.splitext(path)[1]
                new_path = os.path.join(os.path.dirname(path), new_name + ext)
                try:
                    os.rename(path, new_path)
                except Exception as exc:
                    print(f"Failed to rename {path}: {exc}")
    else:
        root = tk.Tk()
        app = FileRenamerUI(root, method=args.method)
        root.mainloop()
