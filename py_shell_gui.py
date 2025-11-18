#!/usr/bin/env python3
"""
Clean, ready-to-run py_shell_gui.py for AuraShell (GUI) with pipeline support.

Features:
 - Proper quoted-argument parsing using shlex.split()
 - Multi-stage pipeline support using subprocess.Popen
 - Support for builtin commands producing output into pipelines (dir, echo, pwd, history)
 - Safe argv-based execution for normal commands
 - Fallback to shell=True when shell operators (>, <, &&, ;, ||) are present
 - Preserves builtins: exit, echo, type, cd, pwd, history, cls, help, dir
 - GUI with autocompletion, history, and typo-suggestion flow retained

Usage:
    python py_shell_gui.py

Drop this file into your project folder and run it. No sandbox or /mnt/data
references are included.
"""

import tkinter as tk
from tkinter import scrolledtext
import subprocess
import os
import sys
from rapidfuzz import distance as rapidfuzz_distance
import shlex
import shutil
import threading
from typing import List, Callable, Optional
import io

HISTORY_FILE = os.path.expanduser("~/.aurashell_history")

# Simple in-memory history used by process_command wrapper below
HISTORY: List[str] = []

# We'll populate builtins inside the PyShell __init__ so they can call module-level
# helpers (which are defined below) for pipeline-capable behavior.

class PyShell(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AuraShell (GUI)")
        self.geometry("800x600")
        self.current_cwd = os.getcwd()
        self.command_history = []
        self.history_index = 0
        self.load_history()
        # builtins mapping: each value is a callable taking (args, out=None)
        # When called with just (args) it will still work because out has default None.
        self.builtins = {
            "exit": lambda args, out=None: self.handle_exit(args),
            "echo": lambda args, out=None: handle_echo(self, args, out),
            "type": lambda args, out=None: self.handle_type(args) if out is None else self._type_to_out(args, out),
            "cd": lambda args, out=None: self.handle_cd(args),
            "pwd": lambda args, out=None: handle_pwd(self, args, out),
            "history": lambda args, out=None: handle_history(self, args, out),
            "cls": lambda args, out=None: self.handle_clear(args),
            "help": lambda args, out=None: self.handle_help(args),
            "dir": lambda args, out=None: handle_dir(self, args, out),
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

        # record history
        if command_line:
            self.command_history.append(command_line)
        self.history_index = len(self.command_history)

        # correction flow
        if self.correction_active:
            self.handle_correction_response(command_line)
            return

        # If the user typed a pipeline, prefer pipeline execution.
        if '|' in command_line:
            # tokenise safely to inspect stage commands
            try:
                tokens = shlex.split(command_line, posix=True)
            except ValueError as e:
                self.print_to_output(f"Parsing error: {e}\n")
                return

            # extract the first token of each stage (commands before each |)
            stage_cmds = []
            cur = []
            for tok in tokens:
                if tok == '|':
                    if cur:
                        stage_cmds.append(cur[0])
                        cur = []
                else:
                    cur.append(tok)
            if cur:
                stage_cmds.append(cur[0])

            # If any stage is a builtin, run the pipeline with mixed builtin/external support
            if any((cmd in self.builtins) for cmd in stage_cmds):
                try:
                    stages = split_pipeline_stages(command_line)
                except ValueError as e:
                    self.print_to_output(f"Parsing error: {e}\n")
                    self.update_prompt()
                    return
                try:
                    rc, out, err = execute_mixed_pipeline(stages, self, cwd=self.current_cwd)
                    if out:
                        self.print_to_output(out)
                    if err:
                        self.print_to_output(err)
                    if rc == 127 and stage_cmds:
                        self.suggest_correction(stage_cmds[0], [])
                except Exception as e:
                    self.print_to_output(f"Error executing mixed pipeline: {e}\n")
                self.update_prompt()
                return
            else:
                # No builtins involved — use the safer native pipeline executor
                try:
                    rc, out, err = process_command_external(command_line, cwd=self.current_cwd)
                    if out:
                        self.print_to_output(out)
                    if err:
                        self.print_to_output(err)
                    if rc == 127 and stage_cmds:
                        self.suggest_correction(stage_cmds[0], [])
                except Exception as e:
                    self.print_to_output(f"Error executing pipeline: {e}\n")
                self.update_prompt()
                return

        # --- Non-pipeline path: preserve builtin dispatch and external execution ---
        # Use shlex to split for correct handling of quotes when dispatching to builtins
        if is_shell_operator_present(command_line):
            try:
                rc, out, err = process_command_external(command_line, cwd=self.current_cwd)
                if out:
                    self.print_to_output(out)
                if err:
                    self.print_to_output(err)
            except Exception as e:
                self.print_to_output(f"Error executing shell command: {e}\n")
            self.update_prompt()
            return
        try:
            parts = shlex.split(command_line, posix=True)
        except ValueError as e:
            self.print_to_output(f"Parsing error: {e}\n")
            return
        if not parts:
            self.update_prompt()
            return
        command = parts[0]
        args = parts[1:]

        if command in self.builtins:
            # builtin handlers (cd, echo, etc.)
            # builtins in this mapping accept (args, out=None)
            self.builtins[command](args)
        else:
            # Use the wrapper that calls the improved external executor
            try:
                # Requote args to reconstruct a safe command line for the external executor
                quoted_args = " ".join(shlex.quote(a) for a in args)
                command_line_for_exec = command if not quoted_args else f"{command} {quoted_args}"
                rc, out, err = process_command_external(command_line_for_exec, cwd=self.current_cwd)
                if out:
                    self.print_to_output(out)
                if err:
                    self.print_to_output(err)
                if rc == 127:
                    # preserve suggestion behavior on not-found
                    self.suggest_correction(command, args)
            except Exception as e:
                self.print_to_output(f"Error executing external command: {e}\n")

        self.update_prompt()


    def on_exit(self):
        self.print_to_output("Saving history. Exiting AuraShell.\n")
        self.save_history()
        self.destroy()
    
    def _type_to_out(self, args, out):
        # Small adapter so `type` builtin can write to a pipe when used in a pipeline
        if not args:
            out.write("type: missing operand\n")
            out.flush()
            return
        cmd_to_find = args[0]
        if cmd_to_find in self.builtins:
            out.write(f"{cmd_to_find} is a shell builtin\n")
            out.flush()
            return
        found_path = self.find_in_path(cmd_to_find)
        if found_path:
            out.write(f"{cmd_to_find} is {found_path}\n")
            out.flush()
            return
        out.write(f"{cmd_to_find}: not found\n")
        out.flush()

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
        # non-pipeline behavior: prints to GUI
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
        # kept for compatibility; older UI paths call this. We reconstruct a line and use new executor
        try:
            quoted_args = " ".join(shlex.quote(a) for a in args)
            command_line_for_exec = command if not quoted_args else f"{command} {quoted_args}"
            rc, out, err = process_command_external(command_line_for_exec, cwd=self.current_cwd)
            if out:
                self.print_to_output(out)
            if err:
                self.print_to_output(err)
            if rc == 127:
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


# --- Improved external execution functions (pipeline + shell-aware) ---

def is_shell_operator_present(s: str) -> bool:
    ops = [">", "<", "&&", "&", ";", "||"]
    return any(op in s for op in ops)


def split_pipeline_stages(command_line: str) -> List[List[str]]:
    tokens = shlex.split(command_line, posix=True)
    stages: List[List[str]] = []
    cur: List[str] = []
    for tok in tokens:
        if tok == "|":
            if not cur:
                raise ValueError("Empty stage in pipeline")
            stages.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        stages.append(cur)
    return stages


def execute_pipeline(stages: List[List[str]]):
    procs = []
    prev_proc = None
    for i, argv in enumerate(stages):
        stdin = prev_proc.stdout if prev_proc is not None else None
        stdout = subprocess.PIPE
        try:
            proc = subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as e:
            for p in procs:
                try:
                    p.kill()
                except Exception:
                    pass
            raise e
        if prev_proc is not None:
            prev_proc.stdout.close()
        procs.append(proc)
        prev_proc = proc

    stdout, stderr = procs[-1].communicate()
    for p in procs[:-1]:
        p.wait()
    return procs[-1].returncode, stdout, stderr


def process_command_external(command_line: str, cwd: str = None):
    # If shell operators present, fall back to shell=True
    if is_shell_operator_present(command_line):
        res = subprocess.run(command_line, shell=True, capture_output=True, text=True, cwd=cwd)
        return res.returncode, res.stdout, res.stderr

    # If pipelines are present, handle them natively
    if "|" in command_line:
        try:
            stages = split_pipeline_stages(command_line)
        except ValueError as e:
            return 1, "", str(e)
        try:
            return execute_pipeline(stages)
        except FileNotFoundError as e:
            return 127, "", f"Command not found in pipeline: {e}"
        except Exception as e:
            return 1, "", str(e)

    # Safe argv execution
    argv = shlex.split(command_line, posix=True)
    if not argv:
        return 0, "", ""
    try:
        res = subprocess.run(argv, capture_output=True, text=True, cwd=cwd)
        return res.returncode, res.stdout, res.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {argv[0]}"
    except Exception as e:
        return 1, "", str(e)


# --- Mixed pipeline executor that supports builtin producers like `dir` ---

def execute_mixed_pipeline(stages: List[List[str]], app: PyShell, cwd: Optional[str] = None):
    """
    Execute a pipeline where some stages may be builtins (present in app.builtins).
    Builtin stages must accept (args, out=None) and write their output to the provided file-like `out`.
    External stages are launched with subprocess.Popen.

    Returns: (returncode, stdout, stderr)
    """
    procs = []
    threads = []
    prev_read_fd = None      # integer FD when the producer was a builtin
    prev_proc = None         # subprocess.Popen when the producer was an external process

    try:
        for i, argv in enumerate(stages):
            is_builtin = argv[0] in app.builtins
            next_is_last = (i == len(stages) - 1)

            if is_builtin:
                # create a pipe: builtin writes to w_fd, we read from r_fd
                r_fd, w_fd = os.pipe()
                w_file = os.fdopen(w_fd, 'w', encoding='utf-8', errors='replace', buffering=1)

                def run_builtin_write(fn: Callable, args, out_file, target_cwd):
                    orig_cwd = os.getcwd()
                    try:
                        if target_cwd:
                            os.chdir(target_cwd)
                        fn(args, out=out_file)
                    except Exception as e:
                        try:
                            out_file.write(f"Builtin error: {e}\n")
                        except Exception:
                            pass
                    finally:
                        try:
                            out_file.close()
                        except Exception:
                            pass
                        try:
                            if target_cwd:
                                os.chdir(orig_cwd)
                        except Exception:
                            pass

                t = threading.Thread(target=run_builtin_write, args=(app.builtins[argv[0]], argv[1:], w_file, cwd))
                t.daemon = True
                t.start()
                threads.append(t)

                # builtin produced a read fd for the next stage
                # if there was a previous external process, its stdout should already have been consumed
                if prev_proc is not None:
                    # previous external's stdout should be closed by now (no longer used)
                    try:
                        prev_proc.stdout.close()
                    except Exception:
                        pass
                    prev_proc = None
                # close any old prev_read_fd (shouldn't normally be set)
                if prev_read_fd is not None:
                    try:
                        os.close(prev_read_fd)
                    except Exception:
                        pass
                prev_read_fd = r_fd

            else:
                # External command
                stdin_param = None
                # If previous stage was an external process, connect its stdout directly
                if prev_proc is not None:
                    stdin_param = prev_proc.stdout
                # Else if previous stage was builtin, use its read fd as file object
                elif prev_read_fd is not None:
                    stdin_param = os.fdopen(prev_read_fd, 'r', encoding='utf-8', errors='replace')

                try:
                    proc = subprocess.Popen(argv,
                                            stdin=stdin_param,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            text=True,
                                            cwd=cwd)
                except FileNotFoundError as e:
                    # cleanup
                    for p in procs:
                        try:
                            p.kill()
                        except Exception:
                            pass
                    for t in threads:
                        t.join(timeout=0.1)
                    raise e

                procs.append(proc)

                # If we created a file object for prev_read_fd, close it in parent (proc has its own fd)
                if prev_read_fd is not None:
                    try:
                        stdin_param.close()
                    except Exception:
                        pass
                # If prev_proc was an external Popen, close prev_proc.stdout in parent so the child sees EOF when appropriate
                if prev_proc is not None:
                    try:
                        prev_proc.stdout.close()
                    except Exception:
                        pass

                # now the current external becomes the prev_proc for the next stage
                prev_proc = proc
                prev_read_fd = None

        # After launching all stages, obtain final output
        if procs:
            last_proc = procs[-1]
            stdout, stderr = last_proc.communicate()
            for p in procs[:-1]:
                try:
                    p.wait()
                except Exception:
                    pass
            for t in threads:
                t.join(timeout=0.1)
            return last_proc.returncode, stdout, stderr
        else:
            # pipeline consisted only of builtins — read from the last builtin pipe (prev_read_fd)
            if prev_read_fd is None:
                return 0, "", ""
            try:
                with os.fdopen(prev_read_fd, 'r', encoding='utf-8', errors='replace') as rf:
                    content = rf.read()
            except Exception as e:
                content = f"Error reading builtin output: {e}\n"
            for t in threads:
                t.join(timeout=0.1)
            return 0, content, ""
    except FileNotFoundError as e:
        return 127, "", f"Command not found in pipeline: {e}"
    except Exception as e:
        return 1, "", str(e)


def handle_echo(self, args, out=None):
    """Echo that writes to out (file-like) if provided, otherwise to GUI."""
    text = " ".join(args) + "\n" if args else "\n"
    if out:
        out.write(text)
        out.flush()
    else:
        self.print_to_output(text)


def handle_pwd(self, args, out=None):
    text = os.getcwd() + "\n"
    if out:
        out.write(text); out.flush()
    else:
        self.print_to_output(text)


def handle_history(self, args, out=None):
    out_lines = "\n".join(f"{i+1}  {h}" for i, h in enumerate(self.command_history)) + "\n"
    if out:
        out.write(out_lines); out.flush()
    else:
        self.print_to_output(out_lines)


def handle_dir(self, args, out=None):
    """
    Pipeline-capable dir:
    - if out is provided: write entries into out (text)
    - otherwise print to GUI (similar to previous handle_dir)
    """
    try:
        target = self.current_cwd if not args else args[0]
        target = os.path.expanduser(target)
        if not os.path.exists(target):
            msg = f"dir: cannot access '{target}': No such file or directory\n"
            if out:
                out.write(msg); out.flush()
            else:
                self.print_to_output(msg)
            return

        header = f"\n Directory of {target}\n\n"
        if out:
            out.write(header)
        else:
            self.print_to_output(header)

        for entry in sorted(os.listdir(target), key=str.lower):
            full_path = os.path.join(target, entry)
            if os.path.isdir(full_path):
                tag = "<DIR>"
                line = f" {tag:10} {entry}\n"
            else:
                size = os.path.getsize(full_path)
                line = f" {size:10} {entry}\n"
            if out:
                out.write(line)
            else:
                self.print_to_output(line)

        if out:
            out.write("\n"); out.flush()
        else:
            self.print_to_output("\n")

    except Exception as e:
        msg = f"dir error: {e}\n"
        if out:
            out.write(msg); out.flush()
        else:
            self.print_to_output(msg)


# If run directly, act as a GUI application
if __name__ == "__main__":
    import traceback, time

    LOG_PATH = os.path.join(os.getcwd(), "aura_error_log.txt")

    def log_and_print(msg: str):
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
        except Exception:
            pass
        try:
            print(msg)
        except Exception:
            pass

    try:
        # Quick dependency sanity checks
        missing = []
        try:
            import tkinter  # noqa: F401
        except Exception:
            missing.append("tkinter")
        try:
            import rapidfuzz  # noqa: F401
        except Exception:
            missing.append("rapidfuzz (pip install rapidfuzz)")

        if missing:
            log_and_print("Missing dependencies detected: " + ", ".join(missing))
            log_and_print("Attempting to continue, but install missing packages and restart for full GUI.")
            # If tkinter missing, fall back to a simple console message
            if "tkinter" in missing:
                print("tkinter not available. Exiting GUI. See aura_error_log.txt for details.")
                raise SystemExit(1)

        # Normal GUI start
        try:
            app = PyShell()
            app.mainloop()
        except Exception as gui_exc:
            tb = traceback.format_exc()
            log_and_print("Unhandled exception in GUI startup:\n" + tb)
            # Try a minimal fallback that at least prints an error and drops to REPL-like prompt
            print("GUI failed to start. Logged traceback to aura_error_log.txt.")
            print("Starting minimal console fallback for diagnosis. Type 'exit' to quit.")
            while True:
                try:
                    line = input("aurashell-cmd> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print('\\nExiting fallback.')
                    break
                if not line:
                    continue
                if line.lower() in ("exit", "quit"):
                    break
                # Simple exec: print what's parsed (do not execute dangerous shell)
                print("You entered:", line)
            raise SystemExit(1)

    except SystemExit:
        # allow normal exit
        raise
    except Exception as e:
        # catastrophic, log the exception
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write("CRITICAL STARTUP ERROR:\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        print("Critical error during startup. See aura_error_log.txt for details.")
        raise