import tkinter as tk
from tkinter import scrolledtext
import subprocess
import os
import sys
from rapidfuzz import distance as rapidfuzz_distance

HISTORY_FILE = os.path.expanduser("~/.aurashell_history")

class PyShell(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AuraShell (GUI)")
        self.geometry("800x600")
        self.current_cwd = os.getcwd()
        self.command_history = []
        self.history_index = 0
        self.load_history()
        self.builtins = {
            "exit": self.handle_exit,
            "echo": self.handle_echo,
            "type": self.handle_type,
            "cd": self.handle_cd,
            "pwd": self.handle_pwd,
            "history": self.handle_history,
            "cls": self.handle_clear,
            "help": self.handle_help,
        }
        self.all_system_commands = self.get_path_commands()
        self.correction_active = False
        self.pending_correction = None
        self.current_suggestions = []
        self.suggestion_list_active = False
        self.last_selected_index = -1
        self.output_area = scrolledtext.ScrolledText(
            self,
            bg="#2B2B2B", fg="#E0E0E0",
            font=("Consolas", 12),
            insertbackground="white",
            state='disabled'
        )
        self.output_area.pack(fill='both', expand=True, padx=5, pady=5)
        self.input_frame = tk.Frame(self, bg="#2B2B2B")
        self.input_frame.pack(fill='x', padx=5, pady=(0, 5))
        self.prompt_label = tk.Label(
            self.input_frame, text="aurashell$ ", fg="#64FFDA",
            bg="#2B2B2B", font=("Consolas", 12, "bold")
        )
        self.prompt_label.pack(side=tk.LEFT, padx=(5, 0))
        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(
            self.input_frame, bg="#2B2B2B", fg="#A9B7C6",
            font=("Consolas", 12), insertbackground="white",
            textvariable=self.input_var, relief=tk.FLAT, width=1
        )
        self.input_field.pack(fill='x', expand=True, side=tk.LEFT)
        self.input_field.focus_set()
        self.suggestion_listbox = tk.Listbox(
            self, font=("Consolas", 11), bg="#3C3F41", fg="white",
            selectbackground="#4B6EAF", selectforeground="#000000",
            relief=tk.FLAT, exportselection=False, activestyle="none"
        )
        self.suggestion_listbox.bind('<Button-1>', self.select_suggestion_click)
        self.suggestion_listbox.bind('<Return>', self.handle_return_key)
        self.suggestion_listbox.bind('<FocusIn>', self.on_listbox_focus_in)
        self.input_field.bind('<Return>', self.handle_return_key)
        self.input_field.bind('<Tab>', self.select_suggestion_key)
        self.input_field.bind('<Up>', self.handle_up_key)
        self.input_field.bind('<Down>', self.handle_down_key)
        self.input_field.bind('<KeyRelease>', self.on_key_release)
        self.input_field.bind('<FocusOut>', self.hide_suggestion_list_on_focus_out)
        self.input_field.bind('<Control-Up>', self.handle_ctrl_up)
        self.input_field.bind('<Control-Down>', self.handle_ctrl_down)
        self.bind('<Configure>', self.on_window_move)
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        self._list_normal_bg = "#3C3F41"
        self._list_normal_fg = "white"
        self._list_sel_bg = "#4B6EAF"
        self._list_sel_fg = "#000000"

        self.print_to_output("Welcome to AuraShell. History loaded. Type 'help' for commands.\n")
        self.update_prompt()

    def print_to_output(self, text):
        self.output_area.config(state='normal')
        self.output_area.insert(tk.END, text)
        self.output_area.config(state='disabled')
        self.output_area.see(tk.END)

    def update_prompt(self):
        self.current_cwd = os.getcwd()
        self.prompt_label.config(text=f"{self.current_cwd}$ ")

    def process_command(self, event=None):
        command_line = self.input_var.get().strip()
        self.input_var.set('')
        self.print_to_output(self.prompt_label.cget('text') + command_line + "\n")
        if not command_line:
            self.update_prompt()
            return
        if command_line:
            self.command_history.append(command_line)
        self.history_index = len(self.command_history)
        if self.correction_active:
            self.handle_correction_response(command_line)
            return
        parts = command_line.split()
        command = parts[0]
        args = parts[1:]
        if command in self.builtins:
            self.builtins[command](args)
        else:
            self.execute_external(command, args)
        self.update_prompt()

    def on_exit(self):
        self.print_to_output("Saving history... Exiting AuraShell...\n")
        self.save_history()
        self.destroy()

    def handle_exit(self, args):
        self.on_exit()

    def handle_echo(self, args):
        self.print_to_output(" ".join(args) + "\n")

    def handle_pwd(self, args):
        self.print_to_output(self.current_cwd + "\n")

    def handle_clear(self, args):
        self.output_area.config(state='normal')
        self.output_area.delete('1.0', tk.END)
        self.output_area.config(state='disabled')

    def handle_help(self, args):
        help_text = "AuraShell Built-in Commands:\n"
        for cmd in self.builtins:
            help_text += f"  - {cmd}\n"
        help_text += "All other system commands (ls, dir, etc.) are also available.\n"
        self.print_to_output(help_text)

    def handle_cd(self, args):
        try:
            if not args:
                target_dir = os.path.expanduser("~")
            elif args[0] == "~":
                target_dir = os.path.expanduser("~")
            else:
                target_dir = args[0]
            os.chdir(target_dir)
            self.current_cwd = os.getcwd()
        except FileNotFoundError:
            self.print_to_output(f"cd: '{target_dir}': No such file or directory\n")
        except Exception as e:
            self.print_to_output(f"cd error: {e}\n")

    def handle_type(self, args):
        if not args:
            self.print_to_output("type: missing operand\n")
            return
        cmd_to_find = args[0]
        if cmd_to_find in self.builtins:
            self.print_to_output(f"{cmd_to_find} is a shell builtin\n")
            return
        found_path = self.find_in_path(cmd_to_find)
        if found_path:
            self.print_to_output(f"{cmd_to_find} is {found_path}\n")
            return
        self.print_to_output(f"{cmd_to_find}: not found\n")

    def execute_external(self, command, args):
        try:
            result = subprocess.run(
                [command] + args,
                capture_output=True, text=True,
                cwd=self.current_cwd, shell=True
            )
            if result.returncode != 0:
                stderr_lower = (result.stderr or "").lower()
                if "not recognized" in stderr_lower or "not found" in stderr_lower or "no such file" in stderr_lower:
                    self.suggest_correction(command, args)
                else:
                    if result.stdout:
                        self.print_to_output(result.stdout)
                    if result.stderr:
                        self.print_to_output(result.stderr)
            else:
                if result.stdout:
                    self.print_to_output(result.stdout)
                if result.stderr:
                    self.print_to_output(result.stderr)
        except FileNotFoundError:
            self.suggest_correction(command, args)
        except Exception as e:
            self.print_to_output(f"Error: {e}\n")

    def suggest_correction(self, typo_command, args):
        all_cmds = list(self.builtins.keys()) + self.all_system_commands
        min_distance_threshold = 3
        try:
            distances = []
            for cmd in all_cmds:
                distance = rapidfuzz_distance.Levenshtein.distance(typo_command, cmd)
                if distance < min_distance_threshold:
                    distances.append((distance, cmd))
            distances.sort()
            top_matches = [cmd for dist, cmd in distances[:3]]
            if top_matches:
                suggestion_text = f"Command not found: '{typo_command}'. Did you mean:\n"
                for i, match in enumerate(top_matches):
                    suggestion_text += f"  {i+1}) {match}\n"
                suggestion_text += f"Enter a number (1-{len(top_matches)}) or 'n' to cancel: "
                self.print_to_output(suggestion_text)
                self.correction_active = True
                self.pending_correction = (top_matches, args)
            else:
                self.print_to_output(f"{typo_command}: command not found\n")
        except Exception as e:
            self.print_to_output(f"Error during correction: {e}\n")
            self.print_to_output(f"{typo_command}: command not found\n")

    def handle_correction_response(self, response):
        suggested_commands, args = self.pending_correction
        try:
            choice_num = int(response)
            if 1 <= choice_num <= len(suggested_commands):
                command_to_run = suggested_commands[choice_num - 1]
                self.input_var.set(command_to_run + " ")
                self.input_field.focus_set()
                self.after(1, lambda: (self.input_field.icursor(tk.END), self.input_field.selection_range(0, tk.END)))
            else:
                self.print_to_output("--- Invalid choice. Aborted. ---\n")
        except ValueError:
            self.print_to_output("--- Aborted ---\n")
        self.correction_active = False
        self.pending_correction = None

    def on_window_move(self, event):
        if self.suggestion_list_active and self.current_suggestions:
            try:
                self.show_suggestion_list(self.current_suggestions)
            except Exception:
                self.hide_suggestion_list()

    def hide_suggestion_list_on_focus_out(self, event):
        self.after(100, self._check_focus)

    def _check_focus(self):
        if self.focus_get() not in (self.input_field, self.suggestion_listbox):
            self.hide_suggestion_list()

    def handle_up_key(self, event):
        widget = event.widget
        if self.suggestion_list_active and widget is self.input_field:
            self.navigate_suggestions(-1)
            return "break"
        if widget is self.input_field:
            return self.history_scroll(event)
        return None

    def handle_down_key(self, event):
        widget = event.widget
        if self.suggestion_list_active and widget is self.input_field:
            self.navigate_suggestions(1)
            return "break"
        if widget is self.input_field:
            return self.history_scroll(event)
        return None

    def handle_ctrl_up(self, event):
        return self.history_scroll(event)

    def handle_ctrl_down(self, event):
        return self.history_scroll(event)

    def navigate_suggestions(self, direction):
        if not self.suggestion_list_active:
            return
        current_selection = self.suggestion_listbox.curselection()
        current_index = current_selection[0] if current_selection else -1
        list_size = self.suggestion_listbox.size()
        if list_size == 0:
            return
        if current_index == -1:
            if direction > 0:
                new_index = 0
            else:
                new_index = max(0, list_size - 1)
        else:
            new_index = current_index + direction
            if new_index >= list_size:
                new_index = 0
            elif new_index < 0:
                new_index = list_size - 1
        self.suggestion_listbox.selection_clear(0, tk.END)
        self.suggestion_listbox.selection_set(new_index)
        self.suggestion_listbox.activate(new_index)
        self.suggestion_listbox.see(new_index)
        self.last_selected_index = new_index
        self._apply_visual_selection(new_index)

    def _apply_visual_selection(self, sel_index):
        size = self.suggestion_listbox.size()
        for i in range(size):
            if i == sel_index:
                try:
                    self.suggestion_listbox.itemconfig(i, bg=self._list_sel_bg, fg=self._list_sel_fg)
                except Exception:
                    pass
            else:
                try:
                    self.suggestion_listbox.itemconfig(i, bg=self._list_normal_bg, fg=self._list_normal_fg)
                except Exception:
                    pass

    def _clear_visual_selection(self):
        size = self.suggestion_listbox.size()
        for i in range(size):
            try:
                self.suggestion_listbox.itemconfig(i, bg=self._list_normal_bg, fg=self._list_normal_fg)
            except Exception:
                pass

    def on_listbox_focus_in(self, event):
        self.after(1, lambda: self.input_field.focus_set())

    def handle_return_key(self, event):
        if self.suggestion_list_active and self.suggestion_listbox.curselection():
            self.fill_suggestion_from_list()
            return "break"
        else:
            self.process_command(event)
            return "break"

    def select_suggestion_key(self, event):
        if self.suggestion_list_active:
            self.navigate_suggestions(1)
            return "break"
        return "break"

    def select_suggestion_click(self, event):
        if self.suggestion_list_active and self.suggestion_listbox.curselection():
            self.fill_suggestion_from_list()
        self.input_field.focus_set()

    def fill_suggestion_from_list(self):
        selection_indices = self.suggestion_listbox.curselection()
        if not selection_indices:
            return
        selected_command = self.suggestion_listbox.get(selection_indices[0])
        self.input_var.set(selected_command + " ")
        self.input_field.focus_set()
        self.after(1, lambda: (self.input_field.icursor(tk.END), self.input_field.selection_range(0, tk.END)))
        self.hide_suggestion_list()

    def on_key_release(self, event):
        if event.keysym in ('Return', 'Escape', 'FocusOut', 'Left', 'Right', 'Up', 'Down', 'Tab'):
            if event.keysym in ('Escape', 'Left', 'Right'):
                self.hide_suggestion_list()
            return
        current_text = self.input_var.get().strip()
        if ' ' in current_text or not current_text:
            self.hide_suggestion_list()
            return
        prev = self.current_suggestions[:]
        all_cmds = list(self.builtins.keys()) + self.all_system_commands
        matches = [cmd for cmd in all_cmds if cmd.startswith(current_text)]
        if matches:
            # if matches changed, reset last_selected_index
            if matches != prev:
                self.last_selected_index = -1
            self.show_suggestion_list(matches)
        else:
            self.hide_suggestion_list()

    def show_suggestion_list(self, matches):
        prev = self.current_suggestions[:]
        self.current_suggestions = matches[:]
        self.suggestion_listbox.delete(0, tk.END)
        for match in matches:
            self.suggestion_listbox.insert(tk.END, match)
        # preserve previous selection if matches unchanged
        if prev == matches and 0 <= self.last_selected_index < len(matches):
            self.suggestion_listbox.selection_clear(0, tk.END)
            self.suggestion_listbox.selection_set(self.last_selected_index)
            self.suggestion_listbox.activate(self.last_selected_index)
            self._apply_visual_selection(self.last_selected_index)
        else:
            self.suggestion_listbox.selection_clear(0, tk.END)
            self._clear_visual_selection()
        try:
            self.suggestion_listbox.yview_moveto(0.0)
        except Exception:
            pass
        self.update_idletasks()
        field_root_x = self.input_field.winfo_rootx()
        field_root_y = self.input_field.winfo_rooty()
        root_root_x = self.winfo_rootx()
        root_root_y = self.winfo_rooty()
        x = field_root_x - root_root_x
        y = field_root_y - root_root_y
        width = self.input_field.winfo_width()
        item_height = 20
        list_height = min(len(matches), 10) * item_height
        above_y = y - list_height - 2
        below_y = y + self.input_field.winfo_height() + 2
        try:
            is_fullscreen = bool(self.attributes('-fullscreen'))
        except Exception:
            is_fullscreen = False
        try:
            is_maximized = (self.state() == 'zoomed')
        except Exception:
            is_maximized = False
        place_above = is_fullscreen or is_maximized or (above_y >= 0)
        if place_above:
            final_y = max(0, above_y)
        else:
            final_y = min(below_y, self.winfo_height() - list_height - 2)
        final_x = max(0, min(x, self.winfo_width() - width - 2))
        final_width = min(width, max(80, self.winfo_width() - final_x - 2))
        final_height = min(list_height, max(30, self.winfo_height() - final_y - 10))
        self.suggestion_listbox.place(x=final_x, y=final_y, width=final_width, height=final_height)
        self.suggestion_list_active = True

    def hide_suggestion_list(self):
        self.suggestion_listbox.place_forget()
        self.suggestion_list_active = False
        self.current_suggestions = []
        self.last_selected_index = -1
        self._clear_visual_selection()

    def history_scroll(self, event):
        if self.suggestion_list_active:
            self.hide_suggestion_list()
        if event.keysym == 'Up':
            if self.history_index > 0:
                self.history_index -= 1
        elif event.keysym == 'Down':
            if self.history_index < len(self.command_history):
                self.history_index += 1
        if self.history_index < len(self.command_history):
            self.input_var.set(self.command_history[self.history_index])
        else:
            self.history_index = len(self.command_history)
            self.input_var.set("")
        self.input_field.icursor(tk.END)
        return "break"

    def get_path_commands(self):
        commands = set()
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        extensions = os.environ.get('PATHEXT', '').split(os.pathsep) if sys.platform == "win32" else ['']
        for directory in path_dirs:
            try:
                for filename in os.listdir(directory):
                    for ext in extensions:
                        if filename.lower().endswith(ext.lower()) and ext != '':
                            cmd_name = os.path.splitext(filename)[0]
                            commands.add(cmd_name.lower())
                    if sys.platform != "win32" and '.' not in filename and os.access(os.path.join(directory, filename), os.X_OK):
                        commands.add(filename.lower())
            except (IOError, NotADirectoryError):
                continue
        return list(commands)

    def find_in_path(self, cmd):
        if sys.platform == "win32":
            find_cmd = "where"
        else:
            find_cmd = "which"
        try:
            result = subprocess.run(
                [find_cmd, cmd], capture_output=True,
                text=True, check=True, shell=True
            )
            return result.stdout.splitlines()[0]
        except subprocess.CalledProcessError:
            return None

    def load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r') as f:
                    self.command_history = [line.strip() for line in f if line.strip()]
                self.history_index = len(self.command_history)
        except IOError as e:
            print(f"Error loading history: {e}")

    def save_history(self):
        try:
            with open(HISTORY_FILE, 'w') as f:
                for command in self.command_history:
                    f.write(command + "\n")
        except IOError as e:
            print(f"Error saving history: {e}")

    def handle_history(self, args):
        history_str = ""
        for i, command in enumerate(self.command_history):
            history_str += f"  {i+1}  {command}\n"
        self.print_to_output(history_str)

if __name__ == "__main__":
    app = PyShell()
    app.mainloop()