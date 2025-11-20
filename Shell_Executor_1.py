# shell_executor.py
# Execution engine: parsing, builtin handling, PATHEXT-aware executable lookup, pipeline/redirection, history
import os
import sys
import shlex
import subprocess
import glob
import threading
from typing import List, Tuple, Optional, Dict, Any

DEFAULT_HISTORY_LIMIT = 500

class ShellExecutor:
    def __init__(self,
                 history_file: str = os.path.expanduser("~/.aurashell_history"),
                 history_limit: int = DEFAULT_HISTORY_LIMIT,
                 append_history_on_exit: bool = False):
        self.HISTORY_FILE = os.path.expanduser(history_file)
        self.history_limit = int(history_limit)
        self.append_history_on_exit = bool(append_history_on_exit)
        self.command_history: List[str] = []
        self._history_loaded_count = 0
        
        # Lock for thread-safe operations
        self.lock = threading.RLock()
        
        # Cache for commands
        self._command_cache: Optional[List[str]] = None
        self.current_cwd = os.getcwd()
        
        # Load persisted history
        self.load_history()
        # builtins mapping: name -> handler method name (resolved at runtime)
        self.builtins = {
            "exit": "builtin_exit",
            "echo": "builtin_echo",
            "pwd": "builtin_pwd",
            "cd": "builtin_cd",
            "type": "builtin_type",
            "history": "builtin_history",
            "cls": "builtin_cls",
            "help": "builtin_help",
            "which": "builtin_which",
        }

    # -------------------------
    # Tokenization / parsing
    # -------------------------
    def tokenize(self, command_line: str) -> List[str]:
        # Expand environment variables first
        expanded_line = os.path.expandvars(command_line)
        
        # Use shlex for quoted splitting (posix mode differs on Windows)
        posix_mode = (os.name != 'nt')
        try:
            tokens = shlex.split(expanded_line, posix=posix_mode)
        except Exception:
            tokens = expanded_line.split()
        
        # On Windows, shlex in non-posix mode sometimes retains outer quotes; strip them
        import glob
        final_tokens: List[str] = []
        for t in tokens:
            if os.name == 'nt':
                if len(t) >= 2 and ((t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'"))):
                    t = t[1:-1]
            
            # Globbing expansion
            if any(ch in t for ch in ['*', '?', '[']):
                matches = glob.glob(os.path.expanduser(t))
                if matches:
                    final_tokens.extend(matches)
                else:
                    final_tokens.append(t)
            else:
                final_tokens.append(t)
        
        return final_tokens

    def split_pipeline(self, tokens: List[str]) -> List[List[str]]:
        segments = []
        cur = []
        for t in tokens:
            if t == '|':
                segments.append(cur)
                cur = []
            else:
                cur.append(t)
        segments.append(cur)
        return segments

    def parse_redirections(self, tokens: List[str]) -> Tuple[List[str], Dict]:
        argv = []
        redir = {'stdout': None, 'stdout_append': False,
                 'stderr': None, 'stderr_append': False,
                 'stdin': None}
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t == '>' and i+1 < len(tokens):
                redir['stdout'] = tokens[i+1]; redir['stdout_append'] = False; i += 2; continue
            if t == '>>' and i+1 < len(tokens):
                redir['stdout'] = tokens[i+1]; redir['stdout_append'] = True; i += 2; continue
            if t == '2>' and i+1 < len(tokens):
                redir['stderr'] = tokens[i+1]; redir['stderr_append'] = False; i += 2; continue
            if t == '2>>' and i+1 < len(tokens):
                redir['stderr'] = tokens[i+1]; redir['stderr_append'] = True; i += 2; continue
            if t == '<' and i+1 < len(tokens):
                redir['stdin'] = tokens[i+1]; i += 2; continue
            argv.append(t)
            i += 1
        return argv, redir

    # -------------------------
    # Executable discovery
    # -------------------------
    def is_executable_file(self, path: str) -> bool:
        if sys.platform.startswith("win"):
            return os.path.isfile(path)
        else:
            return os.path.isfile(path) and os.access(path, os.X_OK)

    def _pathexts(self) -> List[str]:
        # PATHEXT uses ';' separators on Windows. Avoid using os.pathsep here.
        raw = os.environ.get('PATHEXT', '.COM;.EXE;.BAT;.CMD')
        parts = [p.strip().lower() for p in raw.split(';') if p.strip()]
        normalized: List[str] = []
        for p in parts:
            if not p.startswith('.'):
                p = '.' + p
            normalized.append(p)
        return normalized

    def find_executable(self, cmd: str) -> Optional[str]:
        # Expand user and environment vars for path-like inputs
        cmd = os.path.expanduser(os.path.expandvars(cmd.strip('"').strip("'")))
        if not cmd:
            return None
        if os.path.dirname(cmd):
            if self.is_executable_file(cmd):
                return os.path.abspath(cmd)
            if sys.platform.startswith("win"):
                for ext in self._pathexts():
                    cand = cmd + ext
                    if os.path.exists(cand):
                        return os.path.abspath(cand)
            return None
        path_env = os.environ.get('PATH', '')
        if sys.platform.startswith("win"):
            exts = self._pathexts()
        else:
            exts = ['']
        for directory in path_env.split(os.pathsep):
            if not directory:
                continue
            candidate = os.path.join(directory, cmd)
            if self.is_executable_file(candidate):
                return os.path.abspath(candidate)
            if sys.platform.startswith("win"):
                for ext in exts:
                    cand = candidate + ext
                    if os.path.exists(cand):
                        return os.path.abspath(cand)
        return None

    def _load_path_commands(self):
        # Populate _command_cache with command names found in PATH (display-friendly).
        with self.lock:
            if self._command_cache is not None:
                return
            commands = set()
            path_dirs = os.environ.get('PATH', '').split(os.pathsep)
            for d in path_dirs:
                try:
                    if not os.path.isdir(d):
                        continue
                    for fname in os.listdir(d):
                        try:
                            # On Windows, prefer the filename without extension (preserve case)
                            if sys.platform.startswith("win"):
                                root, ext = os.path.splitext(fname)
                                if root:
                                    commands.add(root)
                            else:
                                full = os.path.join(d, fname)
                                if os.path.isfile(full) and os.access(full, os.X_OK):
                                    commands.add(fname)
                        except Exception:
                            continue
                except Exception:
                    continue
            # store sorted list for deterministic suggestions
            self._command_cache = sorted(commands)

    def get_path_commands(self) -> List[str]:
        self._load_path_commands()
        return list(self._command_cache) if self._command_cache is not None else []

    def get_suggestions(self, query: str, max_results: int = 20) -> List[str]:
        """
        Return suggestions for a token. Handles:
         - path/file completions if token looks like a path
         - prefix-based command completions (builtins + PATH)
         - fuzzy matches (autocorrect) if few prefix matches
        Case-insensitive matching for commands.
        """
        import glob
        query = (query or "").strip()
        if not query:
            return []

        # Path-like suggestions (path separator, starting with ~ or .)
        if any(ch in query for ch in (os.sep, '/', '~')) or query.startswith('.'):
            try:
                expanded = os.path.expanduser(os.path.expandvars(query))
                matches = glob.glob(expanded + '*')
                nice: List[str] = []
                for m in matches:
                    try:
                        if os.path.isdir(m):
                            nice.append(m + os.sep)
                        else:
                            nice.append(m)
                    except Exception:
                        nice.append(m)
                return nice[:max_results]
            except Exception:
                pass

        # Ensure commands loaded
        self._load_path_commands()
        all_cmds = list(self.builtins.keys()) + (self._command_cache or [])

        ql = query.lower()
        # Prefix matches (case-insensitive)
        prefix_matches = [c for c in all_cmds if c.lower().startswith(ql)]

        fuzzy_matches: List[str] = []
        if len(prefix_matches) < 8:
            try:
                import difflib
                possibilities = all_cmds
                lower_list = [p.lower() for p in possibilities]
                fuzzy_lower = difflib.get_close_matches(ql, lower_list, n=8, cutoff=0.56)
                for fl in fuzzy_lower:
                    for orig in possibilities:
                        if orig.lower() == fl and orig not in prefix_matches and orig not in fuzzy_matches:
                            fuzzy_matches.append(orig)
                            break
            except Exception:
                pass

        results = prefix_matches + fuzzy_matches
        seen = set()
        out: List[str] = []
        for r in results:
            if r not in seen:
                seen.add(r)
                out.append(r)
            if len(out) >= max_results:
                break
        return out

    # -------------------------
    # Builtin handlers
    # -------------------------
    def builtin_echo(self, args: List[str]) -> Tuple[str, str, int]:
        return (" ".join(args) + ("\n" if args else "\n"), "", 0)

    def builtin_pwd(self, args: List[str]) -> Tuple[str, str, int]:
        return (self.current_cwd + "\n", "", 0)

    def builtin_type(self, args: List[str]) -> Tuple[str, str, int]:
        if not args:
            return ("", "type: missing operand\n", 1)
        target = args[0]
        if target in self.builtins:
            return (f"{target} is a shell builtin\n", "", 0)
        found = self.find_executable(target)
        if found:
            return (f"{target} is {found}\n", "", 0)
        return ("", f"{target}: not found\n", 1)

    def builtin_history(self, args: List[str]) -> Tuple[str, str, int]:
        out = ""
        with self.lock:
            for i, c in enumerate(self.command_history):
                out += f"  {i+1}  {c}\n"
        return (out, "", 0)

    def builtin_cd(self, args: List[str]) -> Tuple[str, str, int]:
        try:
            if not args:
                target_dir = os.path.expanduser("~")
            elif args[0] == "~":
                target_dir = os.path.expanduser("~")
            else:
                target_dir = os.path.expanduser(os.path.expandvars(args[0]))
            os.chdir(target_dir)
            with self.lock:
                self.current_cwd = os.getcwd()
            return ("", "", 0)
        except FileNotFoundError:
            return ("", f"cd: '{target_dir}': No such file or directory\n", 1)
        except Exception as e:
            return ("", f"cd error: {e}\n", 1)

    def builtin_exit(self, args: List[str]) -> Tuple[str, str, int]:
        return ("Exiting...\n", "", 0)

    def builtin_cls(self, args: List[str]) -> Tuple[str, str, int]:
        return ("__CLEAR_SCREEN__", "", 0)

    def builtin_help(self, args: List[str]) -> Tuple[str, str, int]:
        out = "Built-in commands:\n"
        for name in sorted(self.builtins.keys()):
            out += f"  - {name}\n"
        out += "External commands are located via PATH. Use quotes for arguments with spaces.\n"
        return (out, "", 0)

    def builtin_which(self, args: List[str]) -> Tuple[str, str, int]:
        if not args:
            return ("which: missing operand\n", "", 1)
        found = self.find_executable(args[0])
        if found:
            return (found + "\n", "", 0)
        return ("", f"{args[0]}: not found\n", 1)

    # -------------------------
    # Execution
    # -------------------------
    def _run_external(self, argv: List[str], input_data: Optional[str], cwd: Optional[str],
                      background: bool = False) -> Tuple[str, str, int]:
        try:
            if background:
                # Start process detached (basic support)
                stdin_arg = subprocess.DEVNULL
                proc = subprocess.Popen(argv,
                                        stdin=stdin_arg,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True,
                                        cwd=cwd,
                                        shell=False)
                return (f"[PID {proc.pid}] Started\n", "", 0)
            else:
                result = subprocess.run(argv,
                                        input=input_data,
                                        capture_output=True,
                                        text=True,
                                        cwd=cwd,
                                        shell=False)
                return (result.stdout or "", result.stderr or "", result.returncode)
        except FileNotFoundError:
            return ("", f"{argv[0]}: not found\n", 127)
        except Exception as e:
            return ("", f"Execution error: {e}\n", 1)

    def _write_to_file(self, filename: str, content: str, append: bool):
        mode = 'a' if append else 'w'
        path = os.path.join(self.current_cwd, filename)
        try:
            with open(path, mode, encoding='utf-8') as f:
                f.write(content)
        except Exception:
            pass

    def run_command(self, command_line: str) -> Dict:
        """
        Execute a command line string.

        Returns a dict with keys:
         - stdout: str
         - stderr: str
         - returncode: int
         - clear: bool
         - exit: bool
         - corrections: optional list[str] (if command not found)
         - original: original command_line (when corrections are suggested)
        """
        if not command_line:
            return {"stdout": "", "stderr": "", "returncode": 0, "clear": False, "exit": False}

        tokens = self.tokenize(command_line)

        # Background operator '&' (only if last token)
        background = False
        if tokens and tokens[-1] == '&':
            background = True
            tokens = tokens[:-1]
            if not tokens:
                return {"stdout": "", "stderr": "", "returncode": 0, "clear": False, "exit": False}

        # Append to history (thread-safe)
        with self.lock:
            self.command_history.append(command_line)
            if len(self.command_history) > self.history_limit:
                overflow = len(self.command_history) - self.history_limit
                self.command_history = self.command_history[overflow:]
                self._history_loaded_count = max(0, self._history_loaded_count - overflow)

        segments = self.split_pipeline(tokens)
        prev_output: Optional[str] = None
        last_return = 0
        final_stdout = ""
        final_stderr = ""
        clear_flag = False
        exit_flag = False

        for idx, seg in enumerate(segments):
            argv, redir = self.parse_redirections(seg)
            is_last = (idx == len(segments) - 1)
            if not argv:
                continue
            cmd = argv[0]
            args = argv[1:]

            # If stdin redirection present for this segment, load the file content to use as input
            seg_stdin_data: Optional[str] = None
            if redir.get('stdin'):
                try:
                    path = os.path.join(self.current_cwd, os.path.expanduser(redir['stdin']))
                    with open(path, 'r', encoding='utf-8') as f:
                        seg_stdin_data = f.read()
                except Exception as e:
                    final_stderr += f"stdin redir error: {e}\n"
                    seg_stdin_data = None

            # Builtins
            if cmd in self.builtins:
                handler_name = self.builtins[cmd]
                handler = getattr(self, handler_name, None)
                if handler is None:
                    out, err, rc = ("", f"{cmd}: builtin not implemented\n", 1)
                else:
                    out, err, rc = handler(args)

                # Handle redirection for builtins
                if redir.get('stdout'):
                    self._write_to_file(redir['stdout'], out, redir['stdout_append'])
                    out = ""
                if redir.get('stderr'):
                    self._write_to_file(redir['stderr'], err, redir['stderr_append'])
                    err = ""

                prev_output = out
                final_stderr += err
                last_return = rc
                if out == "__CLEAR_SCREEN__":
                    clear_flag = True
                    prev_output = ""
                if cmd == "exit":
                    exit_flag = True
                continue

            # External commands: discover executable
            exe = None
            if os.path.dirname(cmd):
                cand = os.path.expanduser(os.path.expandvars(cmd))
                if self.is_executable_file(cand):
                    exe = os.path.abspath(cand)
            else:
                exe = self.find_executable(cmd)

            # If executable not found, propose corrections (autocorrect) before attempting a run.
            if not exe:
                suggestions = self.get_suggestions(cmd, max_results=8)
                if suggestions:
                    return {"stdout": "", "stderr": f"{cmd}: not found\n", "returncode": 127,
                            "clear": False, "exit": False, "corrections": suggestions[:3], "original": command_line}
                # No suggestions, fall through and attempt to run (will likely return not-found)

            if exe:
                cmd_argv = [exe] + args
            else:
                cmd_argv = [cmd] + args

            # Determine input_data for this external process:
            # Priority: previous pipeline output -> stdin redirection -> None
            input_data = prev_output if prev_output is not None else seg_stdin_data

            # If last segment and background requested
            is_background_cmd = (is_last and background)

            stdout, stderr, rc = self._run_external(cmd_argv, input_data, self.current_cwd, background=is_background_cmd)

            # redirection to files
            if redir.get('stdout'):
                self._write_to_file(redir['stdout'], stdout, redir['stdout_append'])
                stdout = ""
            if redir.get('stderr'):
                self._write_to_file(redir['stderr'], stderr, redir['stderr_append'])
                stderr = ""

            prev_output = stdout
            final_stderr += stderr
            last_return = rc

        final_stdout = prev_output or ""

        return {"stdout": final_stdout or "", "stderr": final_stderr or "", "returncode": last_return or 0,
                "clear": clear_flag, "exit": exit_flag, "original": command_line}

    # -------------------------
    # History persistence
    # -------------------------
    def load_history(self):
        try:
            if os.path.exists(self.HISTORY_FILE):
                with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                    lines = [line.rstrip('\n') for line in f if line.strip()]
                if len(lines) > self.history_limit:
                    lines = lines[-self.history_limit:]
                with self.lock:
                    self.command_history = lines
                    self._history_loaded_count = len(self.command_history)
        except Exception:
            # ignore read errors
            pass

    def save_history(self):
        try:
            with self.lock:
                if self.append_history_on_exit:
                    to_write = self.command_history[self._history_loaded_count:]
                    if to_write:
                        with open(self.HISTORY_FILE, 'a', encoding='utf-8') as f:
                            for cmd in to_write:
                                f.write(cmd + "\n")
                    # Trim file if it grew too large
                    try:
                        with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                            all_lines = [line.rstrip('\n') for line in f if line.strip()]
                        if len(all_lines) > self.history_limit:
                            with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
                                for cmd in all_lines[-self.history_limit:]:
                                    f.write(cmd + "\n")
                    except Exception:
                        pass
                else:
                    with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
                        for cmd in self.command_history[-self.history_limit:]:
                            f.write(cmd + "\n")
        except Exception:
            pass