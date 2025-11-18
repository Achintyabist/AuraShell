# aurashell_gui.py
# GUI front-end that imports ShellExecutor from shell_executor.py
import tkinter as tk
from tkinter import scrolledtext
import threading
import os
from Shell_Executor import ShellExecutor

class AuraShellGUI(tk.Tk):
    def __init__(self, executor: ShellExecutor):
        super().__init__()
        self.executor = executor
        self.title("AuraShell (Refactored GUI)")
        self.geometry("820x600")
        self.current_cwd = os.getcwd()

        self.output_area = scrolledtext.ScrolledText(self, bg="#2B2B2B", fg="#E0E0E0",
                                                     font=("Consolas", 12), insertbackground="white",
                                                     state='disabled')
        self.output_area.pack(fill='both', expand=True, padx=5, pady=5)

        self.input_frame = tk.Frame(self, bg="#2B2B2B")
        self.input_frame.pack(fill='x', padx=5, pady=(0,5))

        self.prompt_label = tk.Label(self.input_frame, text=f"{self.current_cwd}$ ",
                                     fg="#64FFDA", bg="#2B2B2B", font=("Consolas", 12, "bold"))
        self.prompt_label.pack(side=tk.LEFT, padx=(5,0))

        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(self.input_frame, bg="#2B2B2B", fg="#A9B7C6",
                                    font=("Consolas",12), insertbackground="white",
                                    textvariable=self.input_var, relief=tk.FLAT)
        self.input_field.pack(fill='x', expand=True, side=tk.LEFT)
        self.input_field.focus_set()

        self.suggestion_listbox = tk.Listbox(self, font=("Consolas",11), bg="#3C3F41",
                                             fg="white", selectbackground="#4B6EAF",
                                             exportselection=False, activestyle="none")
        self.suggestion_list_active = False
        self.current_suggestions = []
        self.last_selected_index = -1

        # key bindings
        self.input_field.bind('<Return>', self.on_enter)
        self.input_field.bind('<KeyRelease>', self.on_key_release)
        self.input_field.bind('<Tab>', self.on_tab)
        self.input_field.bind('<Up>', self.on_up)
        self.input_field.bind('<Down>', self.on_down)
        self.protocol("WM_DELETE_WINDOW", lambda: self.on_close())

        # history navigation state
        self.history_index = len(self.executor.command_history)

        self.print_to_output("Welcome to AuraShell (Refactored). Type 'help' for commands.\n")
        self.update_prompt()

    # ---------- GUI helpers ----------
    def print_to_output(self, text: str):
        self.output_area.config(state='normal')
        self.output_area.insert(tk.END, text)
        self.output_area.config(state='disabled')
        self.output_area.see(tk.END)

    def thread_print(self, text: str):
        if threading.current_thread() is threading.main_thread():
            self.print_to_output(text)
        else:
            self.after(0, lambda: self.print_to_output(text))

    def update_prompt(self):
        self.current_cwd = os.getcwd()
        self.prompt_label.config(text=f"{self.current_cwd}$ ")

    def on_close(self):
        try:
            self.executor.save_history()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    # ---------- input handling ----------
    def on_enter(self, event=None):
        line = self.input_var.get().strip()
        self.input_var.set('')
        self.print_to_output(self.prompt_label.cget('text') + line + "\n")
        if not line:
            self.update_prompt()
            return
        t = threading.Thread(target=self._worker_run, args=(line,), daemon=True)
        t.start()

    def _worker_run(self, line: str):
        result = self.executor.run_command(line)
        def _apply_result():
            if result.get("clear"):
                self.output_area.config(state='normal')
                self.output_area.delete('1.0', tk.END)
                self.output_area.config(state='disabled')
            out = result.get("stdout", "")
            err = result.get("stderr", "")
            if out:
                self.print_to_output(out)
            if err:
                self.print_to_output(err)
            self.update_prompt()
            self.history_index = len(self.executor.command_history)
        self.after(0, _apply_result)

    # ---------- suggestions ----------
    def on_key_release(self, event):
        if event.keysym in ('Return', 'Escape', 'Left', 'Right', 'Up', 'Down', 'Tab'):
            if event.keysym in ('Escape', 'Left', 'Right'):
                self.hide_suggestion_list()
            return
        text = self.input_var.get().strip()
        if ' ' in text or not text:
            self.hide_suggestion_list()
            return
        all_cmds = list(self.executor.builtins.keys()) + self.executor.get_path_commands()
        matches = [c for c in all_cmds if c.startswith(text)]
        if matches:
            self.show_suggestion_list(matches)
        else:
            self.hide_suggestion_list()

    def show_suggestion_list(self, matches):
        self.current_suggestions = matches[:]
        self.suggestion_listbox.delete(0, tk.END)
        for m in matches:
            self.suggestion_listbox.insert(tk.END, m)
        self.suggestion_listbox.selection_clear(0, tk.END)
        self.update_idletasks()
        x = self.input_field.winfo_rootx() - self.winfo_rootx()
        y = self.input_field.winfo_rooty() - self.winfo_rooty() + self.input_field.winfo_height() + 2
        width = self.input_field.winfo_width()
        height = min(10, len(matches)) * 20
        self.suggestion_listbox.place(x=x, y=y, width=width, height=height)
        self.suggestion_list_active = True
        self.last_selected_index = -1

    def hide_suggestion_list(self):
        self.suggestion_listbox.place_forget()
        self.suggestion_list_active = False
        self.current_suggestions = []
        self.last_selected_index = -1

    def navigate_suggestions(self, direction: int):
        if not self.suggestion_list_active:
            return
        cur = self.suggestion_listbox.curselection()
        idx = cur[0] if cur else -1
        size = self.suggestion_listbox.size()
        if size == 0:
            return
        if idx == -1:
            new = 0 if direction > 0 else size - 1
        else:
            new = (idx + direction) % size
        self.suggestion_listbox.selection_clear(0, tk.END)
        self.suggestion_listbox.selection_set(new)
        self.suggestion_listbox.activate(new)
        self.suggestion_listbox.see(new)
        self.last_selected_index = new

    def on_tab(self, event):
        if self.suggestion_list_active:
            if not self.suggestion_listbox.curselection():
                self.navigate_suggestions(1)
            else:
                self.navigate_suggestions(1)
            sel = self.suggestion_listbox.curselection()
            if sel:
                s = self.suggestion_listbox.get(sel[0])
                self.input_var.set(s + " ")
                self.input_field.icursor(tk.END)
                self.input_field.selection_range(0, tk.END)
                self.hide_suggestion_list()
        return "break"

    def on_up(self, event):
        if self.suggestion_list_active:
            self.navigate_suggestions(-1)
            return "break"
        if self.history_index > 0:
            self.history_index -= 1
            self.input_var.set(self.executor.command_history[self.history_index])
        return "break"

    def on_down(self, event):
        if self.suggestion_list_active:
            self.navigate_suggestions(1)
            return "break"
        if self.history_index < len(self.executor.command_history)-1:
            self.history_index += 1
            self.input_var.set(self.executor.command_history[self.history_index])
        else:
            self.history_index = len(self.executor.command_history)
            self.input_var.set("")
        return "break"

def main():
    executor = ShellExecutor()
    app = AuraShellGUI(executor)
    app.mainloop()

if __name__ == "__main__":
    main()