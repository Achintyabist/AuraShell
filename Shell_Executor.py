# shell_executor.py
# Execution engine: parsing, builtin handling, PATHEXT-aware executable lookup, pipeline/redirection, history
import os
import sys
import shlex
import subprocess
import io
from typing import List, Tuple, Optional, Dict

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
        self.load_history()
        self.current_cwd = os.getcwd()
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
        posix_mode = (os.name != 'nt')
        try:
            return shlex.split(command_line, posix=posix_mode)
        except Exception:
            return command_line.split()

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
        redir = {'stdout': None, 'stdout_append': False, 'stderr': None, 'stderr_append': False}
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
            argv.append(t)
            i += 1
        return argv, redir

    # -------------------------
    # Executable discovery
    # -------------------------
    def is_executable_file(self, path: str) -> bool:
        if sys.platform == "win32":
            return os.path.isfile(path)
        else:
            return os.path.isfile(path) and os.access(path, os.X_OK)

    def _pathexts(self) -> List[str]:
        raw = os.environ.get('PATHEXT', '.COM;.EXE;.BAT;.CMD')
        parts = [p.strip().lower() for p in raw.split(os.pathsep) if p.strip()]
        normalized = []
        for p in parts:
            if not p.startswith('.'):
                p = '.' + p
            normalized.append(p)
        return normalized

    def find_executable(self, cmd: str) -> Optional[str]:
        cmd = cmd.strip('"').strip("'")
        if not cmd:
            return None
        if os.path.dirname(cmd):
            if self.is_executable_file(cmd):
                return os.path.abspath(cmd)
            if sys.platform == "win32":
                for ext in self._pathexts():
                    cand = cmd + ext
                    if os.path.exists(cand):
                        return os.path.abspath(cand)
            return None
        path_env = os.environ.get('PATH', '')
        if sys.platform == "win32":
            exts = self._pathexts()
        else:
            exts = ['']
        for directory in path_env.split(os.pathsep):
            if not directory:
                continue
            candidate = os.path.join(directory, cmd)
            if self.is_executable_file(candidate):
                return os.path.abspath(candidate)
            if sys.platform == "win32":
                for ext in exts:
                    cand = candidate + ext
                    if os.path.exists(cand):
                        return os.path.abspath(cand)
        return None

    def get_path_commands(self) -> List[str]:
        commands = set()
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        if sys.platform == "win32":
            exts = self._pathexts()
        else:
            exts = ['']
        for d in path_dirs:
            try:
                for fname in os.listdir(d):
                    lower = fname.lower()
                    if sys.platform == "win32":
                        root, ext = os.path.splitext(lower)
                        if ext in exts and root:
                            commands.add(root)
                    else:
                        full = os.path.join(d, fname)
                        if '.' not in fname and os.access(full, os.X_OK):
                            commands.add(fname)
            except Exception:
                continue
        return sorted(commands)

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
                target_dir = args[0]
            os.chdir(target_dir)
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
    def _run_external(self, argv: List[str], input_data: Optional[str], cwd: Optional[str]) -> Tuple[str, str, int]:
        try:
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

    def run_command(self, command_line: str) -> Dict:
        if not command_line:
            return {"stdout": "", "stderr": "", "returncode": 0, "clear": False}

        tokens = self.tokenize(command_line)
        self.command_history.append(command_line)
        if len(self.command_history) > self.history_limit:
            overflow = len(self.command_history) - self.history_limit
            self.command_history = self.command_history[overflow:]
            self._history_loaded_count = max(0, self._history_loaded_count - overflow)

        segments = self.split_pipeline(tokens)
        prev_output = None
        last_return = 0
        final_stdout = ""
        final_stderr = ""
        clear_flag = False

        for idx, seg in enumerate(segments):
            argv, redir = self.parse_redirections(seg)
            is_last = (idx == len(segments) - 1)
            if not argv:
                continue
            cmd = argv[0]
            args = argv[1:]

            if cmd in self.builtins:
                handler_name = self.builtins[cmd]
                handler = getattr(self, handler_name, None)
                if handler is None:
                    out, err, rc = ("", f"{cmd}: builtin not implemented\n", 1)
                else:
                    out, err, rc = handler(args)
                prev_output = out
                last_return = rc
                if out == "__CLEAR_SCREEN__":
                    clear_flag = True
                    prev_output = ""
                continue

            exe = None
            if os.path.dirname(cmd):
                if self.is_executable_file(cmd):
                    exe = os.path.abspath(cmd)
            else:
                exe = self.find_executable(cmd)
            if exe:
                cmd_argv = [exe] + args
            else:
                cmd_argv = [cmd] + args

            stdout, stderr, rc = self._run_external(cmd_argv, prev_output, self.current_cwd)
            prev_output = stdout
            final_stderr += stderr
            last_return = rc

        final_stdout = prev_output or ""
        if segments:
            last_argv, last_redir = self.parse_redirections(segments[-1])
            if last_redir.get('stdout'):
                mode = 'a' if last_redir.get('stdout_append') else 'w'
                path = os.path.join(self.current_cwd, last_redir['stdout'])
                try:
                    with open(path, mode, encoding='utf-8') as f:
                        f.write(final_stdout)
                    final_stdout = ""
                except Exception as e:
                    final_stderr += f"redirect error: {e}\n"
            if last_redir.get('stderr'):
                mode = 'a' if last_redir.get('stderr_append') else 'w'
                path = os.path.join(self.current_cwd, last_redir['stderr'])
                try:
                    with open(path, mode, encoding='utf-8') as f:
                        f.write(final_stderr)
                    final_stderr = ""
                except Exception as e:
                    final_stderr += f"redirect error: {e}\n"

        return {"stdout": final_stdout or "", "stderr": final_stderr or "", "returncode": last_return or 0, "clear": clear_flag}

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
                self.command_history = lines
                self._history_loaded_count = len(self.command_history)
        except IOError:
            pass

    def save_history(self):
        try:
            if self.append_history_on_exit:
                to_write = self.command_history[self._history_loaded_count:]
                if to_write:
                    with open(self.HISTORY_FILE, 'a', encoding='utf-8') as f:
                        for cmd in to_write:
                            f.write(cmd + "\n")
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
        except IOError:
            pass