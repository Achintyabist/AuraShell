    # aurashell_gui.py
# GUI front-end that imports ShellExecutor from shell_executor.py
import tkinter as tk
from tkinter import scrolledtext
import threading
import os
from typing import List
from Shell_Executor_1 import ShellExecutor

class AuraShellGUI(tk.Tk):
    def __init__(self, executor: ShellExecutor):
        super().__init__()
        self.executor = executor
        
        # Modern color palette
        self.colors = {
            'bg_main': '#1E1E2E',           # Deep dark blue-gray
            'bg_secondary': '#2D2D44',       # Slightly lighter
            'bg_input': '#252538',          # Input field background
            'bg_output': '#1A1A2E',         # Output area background
            'bg_suggestion': '#2A2A3E',     # Suggestion box background
            'fg_primary': '#E4E4E7',        # Primary text
            'fg_secondary': '#A1A1AA',      # Secondary text
            'accent': '#00D9FF',            # Cyan accent
            'accent_hover': '#00B8D9',     # Accent hover
            'prompt': '#00FFD1',            # Prompt color (cyan-green)
            'success': '#00FF88',           # Success green
            'error': '#FF6B6B',             # Error red
            'border': '#3A3A4E',            # Border color
            'selection': '#4A9EFF',         # Selection blue
        }
        
        # Configure window
        self.title("AuraShell - Modern Terminal")
        self.geometry("900x700")
        self.configure(bg=self.colors['bg_main'])
        self.current_cwd = os.getcwd()
        
        # Create main container with padding
        main_container = tk.Frame(self, bg=self.colors['bg_main'])
        main_container.pack(fill='both', expand=True, padx=8, pady=8)
        
        # Output area with modern styling
        output_frame = tk.Frame(main_container, bg=self.colors['bg_output'], 
                               relief=tk.FLAT, bd=0)
        output_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.output_area = scrolledtext.ScrolledText(
            output_frame, 
            bg=self.colors['bg_output'],
            fg=self.colors['fg_primary'],
            font=("Consolas", 11),
            insertbackground=self.colors['accent'],
            state='disabled',
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=15,
            wrap=tk.WORD,
            selectbackground=self.colors['selection'],
            selectforeground='#FFFFFF'
        )
        self.output_area.pack(fill='both', expand=True)
        
        # Input frame with modern styling
        input_container = tk.Frame(main_container, bg=self.colors['bg_main'])
        input_container.pack(fill='x')
        
        # Input field container with futuristic glow border effect
        self.input_glow_frame = tk.Frame(input_container, bg=self.colors['accent'], bd=0)
        self.input_glow_frame.pack(fill='x', padx=0, pady=0)
        
        self.input_frame = tk.Frame(self.input_glow_frame, bg=self.colors['bg_input'],
                                    relief=tk.FLAT, bd=0, highlightbackground=self.colors['border'],
                                    highlightthickness=1)
        self.input_frame.pack(fill='x', ipady=10, ipadx=15, padx=1, pady=1)
        
        # Prompt label with icon-like styling
        self.prompt_label = tk.Label(
            self.input_frame,
            text=f"❯ ",
            fg=self.colors['prompt'],
            bg=self.colors['bg_input'],
            font=("Consolas", 13, "bold"),
            anchor='w'
        )
        self.prompt_label.pack(side=tk.LEFT, padx=(0, 8))
        
        # Path label (separate from prompt)
        self.path_label = tk.Label(
            self.input_frame,
            text=f"{self.current_cwd}",
            fg=self.colors['fg_secondary'],
            bg=self.colors['bg_input'],
            font=("Consolas", 10),
            anchor='w'
        )
        self.path_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(
            self.input_frame,
            bg=self.colors['bg_input'],
            fg=self.colors['fg_primary'],
            font=("Consolas", 12),
            insertbackground=self.colors['accent'],
            textvariable=self.input_var,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0
        )
        self.input_field.pack(fill='x', expand=True, side=tk.LEFT)
        self.input_field.focus_set()
        
        # Bind focus events for input field styling
        self.input_field.bind('<FocusIn>', lambda e: self._on_input_focus_in())
        self.input_field.bind('<FocusOut>', lambda e: self._on_input_focus_out())
        
        # Create a container frame for suggestion box with futuristic glow effect
        self.suggestion_container = tk.Frame(self, bg=self.colors['accent'], bd=0)
        
        # Inner frame for the actual listbox (creates glow border effect)
        self.suggestion_inner = tk.Frame(self.suggestion_container, 
                                        bg=self.colors['bg_suggestion'],
                                        bd=0,
                                        highlightthickness=2,
                                        highlightbackground=self.colors['accent'],
                                        highlightcolor=self.colors['accent'])
        
        # Suggestion listbox with modern styling
        self.suggestion_listbox = tk.Listbox(
            self.suggestion_inner,
            font=("Consolas", 10),
            bg=self.colors['bg_suggestion'],
            fg=self.colors['fg_primary'],
            selectbackground=self.colors['selection'],
            selectforeground='#FFFFFF',
            exportselection=False,
            activestyle="none",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0
        )
        
        # Configure listbox item spacing
        self.suggestion_listbox.configure(
            selectmode=tk.SINGLE,
            height=0  # Will be set dynamically
        )
        
        # Pack the listbox inside inner frame
        self.suggestion_listbox.pack(fill='both', expand=True, padx=2, pady=2)
        self.suggestion_list_active = False
        self.current_suggestions = []
        self.last_selected_index = -1
        self._populating_suggestion = False  # Flag to prevent execution during population

        # key bindings for input field
        self.input_field.bind('<Return>', self.on_enter)
        self.input_field.bind('<KeyRelease>', self.on_key_release)
        self.input_field.bind('<Tab>', self.on_tab)
        self.input_field.bind('<Up>', self.on_up)
        self.input_field.bind('<Down>', self.on_down)
        self.input_field.bind('<Escape>', self.on_escape)
        # clear screen with Ctrl+L
        self.input_field.bind('<Control-l>', self.on_clear)
        
        # bindings for suggestion listbox - single click directly populates (no popup)
        self.suggestion_listbox.bind('<ButtonRelease-1>', self.on_suggestion_click)
        self.suggestion_listbox.bind('<Double-Button-1>', self.on_suggestion_double_click)
        self.suggestion_listbox.bind('<Return>', self.on_suggestion_enter)
        self.suggestion_listbox.bind('<FocusOut>', lambda e: None)  # Prevent focus issues
        
        # Bind click outside to hide suggestions
        self.bind('<Button-1>', self.on_window_click)
        self.output_area.bind('<Button-1>', self.on_window_click)
        
        # Update suggestion position on window resize
        self.bind('<Configure>', self.on_window_configure)
        
        self.protocol("WM_DELETE_WINDOW", lambda: self.on_close())

        # history navigation state
        self.history_index = len(self.executor.command_history)

        # Setup text tags for colored output
        self._setup_text_tags()
        
        # Print welcome message with styling
        welcome_msg = f"""
╔══════════════════════════════════════════════════════════════╗
║                    AuraShell Terminal                        ║
║              Modern Shell with Auto-Complete                 ║
╚══════════════════════════════════════════════════════════════╝

"""
        self.print_to_output(welcome_msg, "accent")
        
        help_msg = "Type 'help' to see available commands.\n"
        self.print_to_output(help_msg, "secondary")
        
        tips_msg = "💡 Tips: Use Tab for auto-completion, ↑↓ for history, Ctrl+L to clear.\n\n"
        self.print_to_output(tips_msg, "secondary")
        
        self.update_prompt()
    
    def _on_input_focus_in(self):
        """Change input frame border color when focused - futuristic glow effect"""
        self.input_frame.config(highlightbackground=self.colors['accent'])
        self.input_glow_frame.config(bg=self.colors['accent'])
    
    def _on_input_focus_out(self):
        """Reset input frame border color when not focused"""
        self.input_frame.config(highlightbackground=self.colors['border'])
        self.input_glow_frame.config(bg=self.colors['border'])

    # ---------- GUI helpers ----------
    def print_to_output(self, text: str, color=None):
        """
        Print text to output area with optional color styling
        """
        self.output_area.config(state='normal')
        if color:
            self.output_area.insert(tk.END, text, color)
        else:
            self.output_area.insert(tk.END, text)
        self.output_area.config(state='disabled')
        self.output_area.see(tk.END)
    
    def _setup_text_tags(self):
        """Setup text color tags for syntax highlighting"""
        # Configure text tags for different output types
        self.output_area.tag_config("error", foreground=self.colors['error'])
        self.output_area.tag_config("success", foreground=self.colors['success'])
        self.output_area.tag_config("prompt", foreground=self.colors['prompt'])
        self.output_area.tag_config("accent", foreground=self.colors['accent'])
        self.output_area.tag_config("secondary", foreground=self.colors['fg_secondary'])

    def thread_print(self, text: str):
        if threading.current_thread() is threading.main_thread():
            self.print_to_output(text)
        else:
            self.after(0, lambda: self.print_to_output(text))

    def update_prompt(self):
        self.current_cwd = os.getcwd()
        # Keep prompt icon, update path separately
        self.path_label.config(text=f"{self.current_cwd}")

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
        """
        Handle Enter key in input field - this is the ONLY place where commands are executed.
        Suggestions and corrections only populate the input field - they never execute automatically.
        """
        # Prevent execution if we're currently populating a suggestion
        if self._populating_suggestion:
            return
        
        # Hide suggestions when Enter is pressed (they should already be hidden, but be safe)
        if self.suggestion_list_active:
            self.hide_suggestion_list()
        
        line = self.input_var.get().strip()
        # Echo the prompt + command into the output with styling
        prompt_text = self.prompt_label.cget('text')
        path_text = self.path_label.cget('text')
        self.print_to_output(f"{prompt_text}{path_text} ", "prompt")
        self.print_to_output(f"{line}\n")
        self.input_var.set('')
        if not line:
            self.update_prompt()
            return
        # ONLY place where commands are executed - user must explicitly press Enter here
        t = threading.Thread(target=self._worker_run, args=(line,), daemon=True)
        t.start()

    def _worker_run(self, line: str):
        result = self.executor.run_command(line)

        def _apply_result():
            # If the executor suggested corrections because the command wasn't found,
            # show a modal choices dialog to the user.
            corrections = result.get("corrections")
            if corrections:
                # show popup with choices; pass the original line so we can replace the command token
                self.show_corrections_popup(corrections, line)
                return

            if result.get("clear"):
                self.output_area.config(state='normal')
                self.output_area.delete('1.0', tk.END)
                self.output_area.config(state='disabled')
            out = result.get("stdout", "")
            err = result.get("stderr", "")
            if out:
                self.print_to_output(out)
            if err:
                # Use error color tag for error messages
                self.print_to_output(err, "error")
            self.update_prompt()
            self.history_index = len(self.executor.command_history)
            # Handle exit request
            if result.get("exit"):
                try:
                    self.executor.save_history()
                except Exception:
                    pass
                try:
                    self.destroy()
                except Exception:
                    pass

        self.after(0, _apply_result)

    # ---------- suggestions ----------
    def on_key_release(self, event):
        if event.keysym in ('Return', 'Escape', 'Left', 'Right', 'Up', 'Down', 'Tab'):
            if event.keysym in ('Escape', 'Left', 'Right'):
                self.hide_suggestion_list()
            return

        text = self.input_var.get() or ""
        stripped = text.strip()
        if not stripped:
            self.hide_suggestion_list()
            return

        # Suggest for the last token under the cursor (works with multi-word commands)
        tokens = text.rstrip().split()
        current_token = tokens[-1] if tokens else stripped

        matches = self.executor.get_suggestions(current_token)
        if matches:
            self.show_suggestion_list(matches)
            # Update position in case window was resized or scrolled
            self.after_idle(self._update_suggestion_position)
        else:
            self.hide_suggestion_list()
    
    def _update_suggestion_position(self):
        """Update suggestion listbox position (called after layout changes)"""
        if not self.suggestion_list_active:
            return
        # Use the same positioning logic
        self._position_suggestion_listbox(self.current_suggestions)

    def show_suggestion_list(self, matches):
        self.current_suggestions = matches[:]
        self.suggestion_listbox.delete(0, tk.END)
        for m in matches:
            self.suggestion_listbox.insert(tk.END, m)
        self.suggestion_listbox.selection_clear(0, tk.END)
        self.update_idletasks()
        
        # Calculate position with bounds checking
        self._position_suggestion_listbox(matches)
        
        self.suggestion_list_active = True
        self.last_selected_index = -1
    
    def _position_suggestion_listbox(self, matches):
        """Position the suggestion listbox within window bounds with accurate calculations"""
        try:
            # Get window dimensions
            window_width = self.winfo_width()
            window_height = self.winfo_height()
            
            # Get input field absolute position relative to window
            input_field_x = self.input_field.winfo_rootx() - self.winfo_rootx()
            input_field_y = self.input_field.winfo_rooty() - self.winfo_rooty()
            input_field_width = self.input_field.winfo_width()
            input_field_height = self.input_field.winfo_height()
            
            # Calculate suggestion box dimensions
            max_items = min(8, len(matches))  # Reduced for better fit
            item_height = 24  # Slightly larger for better visibility
            box_height = max_items * item_height + 4  # Add padding
            box_width = input_field_width + 4  # Match input width with padding
            
            # Calculate x position (align with input field)
            x = input_field_x - 2  # Offset for glow border
            
            # Check available space below and above
            space_below = window_height - (input_field_y + input_field_height) - 10
            space_above = input_field_y - 10
            
            # Decide position: prefer below, but use above if not enough space
            if space_below >= box_height:
                # Show below input field
                y = input_field_y + input_field_height + 3
            elif space_above >= box_height:
                # Show above input field
                y = input_field_y - box_height - 3
            else:
                # Not enough space in either direction, use the one with more space
                if space_below > space_above:
                    y = input_field_y + input_field_height + 3
                    box_height = max(22, space_below - 5)
                else:
                    y = max(10, input_field_y - box_height - 3)
                    box_height = max(22, space_above - 5)
            
            # Ensure x stays within window bounds
            if x < 8:
                x = 8
            if x + box_width > window_width - 8:
                box_width = window_width - x - 8
                if box_width < 150:
                    x = 8
                    box_width = window_width - 16
            
            # Ensure y stays within window bounds
            if y < 8:
                y = 8
            if y + box_height > window_height - 8:
                box_height = window_height - y - 8
                if box_height < 24:
                    box_height = 24
            
            # Place the container (with glow effect)
            self.suggestion_container.place(x=x, y=y, width=box_width, height=box_height)
            self.suggestion_inner.pack(fill='both', expand=True, padx=1, pady=1)
            
            # Ensure it's on top
            self.suggestion_container.lift()
            
        except Exception as e:
            # Fallback positioning
            try:
                input_field_x = self.input_field.winfo_rootx() - self.winfo_rootx()
                input_field_y = self.input_field.winfo_rooty() - self.winfo_rooty()
                input_field_width = self.input_field.winfo_width()
                input_field_height = self.input_field.winfo_height()
                
                x = max(8, input_field_x - 2)
                y = input_field_y + input_field_height + 3
                width = input_field_width + 4
                height = min(8, len(matches)) * 24 + 4
                
                if y + height > self.winfo_height() - 8:
                    y = max(8, input_field_y - height - 3)
                
                self.suggestion_container.place(x=x, y=y, width=width, height=height)
                self.suggestion_inner.pack(fill='both', expand=True, padx=1, pady=1)
                self.suggestion_container.lift()
            except Exception:
                pass

    def hide_suggestion_list(self):
        self.suggestion_container.place_forget()
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

    def _populate_suggestion(self, suggestion: str):
        """
        Helper method to populate input field with suggestion.
        IMPORTANT: This method ONLY populates the input field - it does NOT execute commands.
        User must manually press Enter in the input field to execute.
        NO POPUPS ARE SHOWN - just direct population.
        """
        # Set flag to prevent any accidental execution
        self._populating_suggestion = True
        
        # Hide suggestions first to prevent any interference
        self.hide_suggestion_list()
        
        # Get current input
        full = self.input_var.get() or ""
        if full.strip() == "":
            new_full = suggestion + " "
        else:
            parts = full.rstrip().split(' ')
            parts[-1] = suggestion
            new_full = " ".join(parts) + " "
        
        # ONLY populate the input field - NO execution, NO popups happen here
        self.input_var.set(new_full)
        self.input_field.icursor(tk.END)
        
        # Return focus to input field so user can review and press Enter manually if desired
        # Use after_idle to ensure this happens after any pending events
        def _restore_focus():
            self._populating_suggestion = False  # Clear flag after a short delay
            self.input_field.focus_set()
        
        self.after_idle(_restore_focus)
        
        # Explicitly ensure no command execution is triggered
        # This method should NEVER call _worker_run or show any popups

    def on_tab(self, event):
        """
        Handle Tab key - shows suggestions or selects/populates suggestion.
        IMPORTANT: This only populates the input field, does NOT execute commands.
        """
        if not self.suggestion_list_active:
            # Try to trigger suggestions
            text = self.input_var.get() or ""
            stripped = text.strip()
            if not stripped:
                return "break"
            parts = text.rstrip().split()
            token = parts[-1] if parts else stripped
            matches = self.executor.get_suggestions(token)
            if matches:
                self.show_suggestion_list(matches)
            return "break"

        # If suggestions are active, select and populate (but don't execute)
        sel = self.suggestion_listbox.curselection()
        if not sel:
            self.navigate_suggestions(1)
            sel = self.suggestion_listbox.curselection()
        if sel:
            s = self.suggestion_listbox.get(sel[0])
            # Only populate - user must press Enter to execute
            self._populate_suggestion(s)
        return "break"
    
    def on_suggestion_click(self, event):
        """
        Handle single click on suggestion - directly populate input field immediately.
        NO POPUP, NO EXECUTION - just writes the command to the terminal input field.
        """
        # Stop event propagation immediately to prevent any other handlers
        try:
            event.widget.focus_set()
        except:
            pass
        
        # Get the clicked item - ButtonRelease fires after selection is made
        try:
            sel = self.suggestion_listbox.curselection()
            if sel:
                s = self.suggestion_listbox.get(sel[0])
                # Directly populate input field - NO popup, NO execution, just populate
                self._populate_suggestion(s)
            else:
                # If no selection, try to get item from click position
                try:
                    index = self.suggestion_listbox.nearest(event.y)
                    if 0 <= index < self.suggestion_listbox.size():
                        s = self.suggestion_listbox.get(index)
                        self._populate_suggestion(s)
                except Exception:
                    pass
        except Exception:
            pass
        
        # CRITICAL: Return "break" to stop ALL event propagation
        # This prevents any other handlers (like window click) from interfering
        return "break"
    
    def on_suggestion_double_click(self, event):
        """
        Handle double-click on suggestion - populate input field only.
        IMPORTANT: Does NOT execute - user must press Enter in input field to run command.
        """
        sel = self.suggestion_listbox.curselection()
        if sel:
            s = self.suggestion_listbox.get(sel[0])
            # Only populate, never execute
            self._populate_suggestion(s)
        return "break"
    
    def on_suggestion_enter(self, event):
        """
        Handle Enter key in suggestion listbox - populate input field only.
        IMPORTANT: Does NOT execute - user must press Enter in input field to run command.
        """
        sel = self.suggestion_listbox.curselection()
        if sel:
            s = self.suggestion_listbox.get(sel[0])
            # Only populate, never execute
            self._populate_suggestion(s)
        elif self.suggestion_listbox.size() > 0:
            # If nothing selected, select first item and populate
            self.suggestion_listbox.selection_set(0)
            self.suggestion_listbox.activate(0)
            s = self.suggestion_listbox.get(0)
            # Only populate, never execute
            self._populate_suggestion(s)
        return "break"

    def on_up(self, event):
        if self.suggestion_list_active:
            self.navigate_suggestions(-1)
            return "break"
        if self.executor.command_history:
            if self.history_index > 0:
                self.history_index -= 1
                self.input_var.set(self.executor.command_history[self.history_index])
        return "break"

    def on_down(self, event):
        if self.suggestion_list_active:
            self.navigate_suggestions(1)
            return "break"
        if self.executor.command_history:
            if self.history_index < len(self.executor.command_history) - 1:
                self.history_index += 1
                self.input_var.set(self.executor.command_history[self.history_index])
            else:
                self.history_index = len(self.executor.command_history)
                self.input_var.set("")
        return "break"

    def on_escape(self, event=None):
        """Handle Escape key - hide suggestions and return focus to input"""
        if self.suggestion_list_active:
            self.hide_suggestion_list()
            self.input_field.focus_set()
        return "break"
    
    def on_window_click(self, event):
        """Handle clicks outside suggestion listbox - hide suggestions"""
        if self.suggestion_list_active:
            # Check if click is on the suggestion container - if so, ignore
            try:
                widget = event.widget
                if widget == self.suggestion_listbox or widget == self.suggestion_container or widget == self.suggestion_inner:
                    # Click is on suggestion area, let it handle it
                    return
            except Exception:
                pass
            
            # Check if click is outside the suggestion container
            try:
                x, y = event.x_root, event.y_root
                container_x = self.suggestion_container.winfo_rootx()
                container_y = self.suggestion_container.winfo_rooty()
                container_w = self.suggestion_container.winfo_width()
                container_h = self.suggestion_container.winfo_height()
                
                if not (container_x <= x <= container_x + container_w and 
                       container_y <= y <= container_y + container_h):
                    self.hide_suggestion_list()
            except Exception:
                # If calculation fails, just hide it
                self.hide_suggestion_list()
    
    def on_window_configure(self, event):
        """Handle window resize/configure events - update suggestion position"""
        if self.suggestion_list_active and event.widget == self:
            # Update suggestion position after window resize
            self.after_idle(self._update_suggestion_position)
    
    def on_clear(self, event=None):
        # Map Ctrl+L to clear screen (and do not insert into history)
        self.output_area.config(state='normal')
        self.output_area.delete('1.0', tk.END)
        self.output_area.config(state='disabled')
        return "break"

    # ---------- corrections popup ----------
    def show_corrections_popup(self, corrections: List[str], original_line: str):
        # Must run in main thread (this function is called via after)
        win = tk.Toplevel(self)
        win.title("Command Correction")
        win.configure(bg=self.colors['bg_main'])
        win.transient(self)
        win.grab_set()
        
        # Remove default window decorations for futuristic look
        try:
            win.overrideredirect(False)
        except:
            pass
        
        # Create outer glow frame
        glow_frame = tk.Frame(win, bg=self.colors['accent'], bd=0)
        glow_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        # Main content frame
        main_frame = tk.Frame(glow_frame, bg=self.colors['bg_main'], bd=0)
        main_frame.pack(fill='both', expand=True, padx=1, pady=1)
        
        # Header frame with futuristic styling
        header_frame = tk.Frame(main_frame, bg=self.colors['bg_secondary'], pady=18, padx=25)
        header_frame.pack(fill='x')
        
        # Glowing icon
        icon_frame = tk.Frame(header_frame, bg=self.colors['error'], width=40, height=40)
        icon_frame.pack(side=tk.LEFT, padx=(0, 15))
        icon_label = tk.Label(icon_frame, text="⚠", font=("Arial", 18), 
                             bg=self.colors['error'], fg='#FFFFFF')
        icon_label.pack(expand=True)
        
        title_label = tk.Label(header_frame, 
                              text="Command Not Found", 
                              font=("Consolas", 14, "bold"),
                              bg=self.colors['bg_secondary'], 
                              fg=self.colors['fg_primary'])
        title_label.pack(side=tk.LEFT)
        
        # Message label
        msg_frame = tk.Frame(main_frame, bg=self.colors['bg_main'], pady=12, padx=25)
        msg_frame.pack(fill='x')
        lbl = tk.Label(msg_frame, 
                      text="Did you mean one of these?", 
                      font=("Consolas", 10),
                      bg=self.colors['bg_main'], 
                      fg=self.colors['fg_secondary'],
                      anchor='w')
        lbl.pack(fill='x')

        # Button frame with modern styling
        button_frame = tk.Frame(main_frame, bg=self.colors['bg_main'], padx=25, pady=12)
        button_frame.pack(fill='x')

        # limit to 3 suggestions visually
        shown = corrections[:3]

        def choose_and_populate(choice: str):
            # replace the first token (command) in original_line with the chosen suggestion
            parts = original_line.strip().split()
            if parts:
                parts[0] = choice
            new_line = " ".join(parts)
            # Close the popup
            try:
                win.grab_release()
                win.destroy()
            except Exception:
                pass
            # Populate input field with corrected command (user can then press Enter to run)
            self.input_var.set(new_line)
            self.input_field.icursor(tk.END)
            self.input_field.focus_set()

        for s in shown:
            # Create button with glow effect
            btn_glow = tk.Frame(button_frame, bg=self.colors['accent'], bd=0)
            btn_glow.pack(fill='x', pady=5)
            
            btn = tk.Button(btn_glow, 
                           text=f"  {s}  ",
                           font=("Consolas", 11, "bold"),
                           bg=self.colors['bg_secondary'],
                           fg=self.colors['fg_primary'],
                           activebackground=self.colors['selection'],
                           activeforeground='#FFFFFF',
                           relief=tk.FLAT,
                           bd=0,
                           padx=18,
                           pady=12,
                           cursor='hand2',
                           command=lambda s=s: choose_and_populate(s))
            btn.pack(fill='x', padx=2, pady=2)
            
            # Add futuristic hover effects
            def on_enter(e, b=btn, bg=btn_glow):
                b.config(bg=self.colors['selection'], fg='#FFFFFF')
                bg.config(bg=self.colors['accent_hover'])
            def on_leave(e, b=btn, bg=btn_glow):
                b.config(bg=self.colors['bg_secondary'], fg=self.colors['fg_primary'])
                bg.config(bg=self.colors['accent'])
            
            btn.bind('<Enter>', on_enter)
            btn.bind('<Leave>', on_leave)
            btn_glow.bind('<Enter>', on_enter)
            btn_glow.bind('<Leave>', on_leave)

        # Populate original command
        def populate_original():
            try:
                win.grab_release()
                win.destroy()
            except Exception:
                pass
            # Populate input field with original command (user can then press Enter to run)
            self.input_var.set(original_line)
            self.input_field.icursor(tk.END)
            self.input_field.focus_set()

        # Cancel
        def cancel():
            try:
                win.grab_release()
                win.destroy()
            except Exception:
                pass

        # Options frame
        opt_frame = tk.Frame(main_frame, bg=self.colors['bg_main'], padx=25, pady=(8, 18))
        opt_frame.pack(fill='x')
        
        btn_populate_original = tk.Button(opt_frame, 
                                         text="Use Original",
                                         font=("Consolas", 9),
                                         bg=self.colors['bg_secondary'],
                                         fg=self.colors['fg_secondary'],
                                         activebackground=self.colors['bg_secondary'],
                                         activeforeground=self.colors['fg_primary'],
                                         relief=tk.FLAT,
                                         bd=0,
                                         padx=12,
                                         pady=6,
                                         cursor='hand2',
                                         command=populate_original)
        btn_populate_original.pack(side=tk.LEFT, padx=(0, 8))
        
        btn_cancel = tk.Button(opt_frame, 
                              text="Cancel",
                              font=("Consolas", 9),
                              bg=self.colors['bg_secondary'],
                              fg=self.colors['fg_secondary'],
                              activebackground=self.colors['error'],
                              activeforeground='#FFFFFF',
                              relief=tk.FLAT,
                              bd=0,
                              padx=12,
                              pady=6,
                              cursor='hand2',
                              command=cancel)
        btn_cancel.pack(side=tk.LEFT)

        # Center the popup with better positioning
        win.update_idletasks()
        try:
            # Get main window dimensions and position
            pw = self.winfo_width()
            ph = self.winfo_height()
            px = self.winfo_rootx()
            py = self.winfo_rooty()
            
            # Get popup dimensions
            ww = win.winfo_width()
            wh = win.winfo_height()
            
            # Calculate center position
            center_x = px + (pw - ww) // 2
            center_y = py + (ph - wh) // 2
            
            # Ensure popup stays within screen bounds
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            
            center_x = max(10, min(center_x, screen_width - ww - 10))
            center_y = max(10, min(center_y, screen_height - wh - 10))
            
            win.geometry(f"+{center_x}+{center_y}")
        except Exception:
            pass

def main():
    executor = ShellExecutor()
    app = AuraShellGUI(executor)
    app.mainloop()

if __name__ == "__main__":
    main()