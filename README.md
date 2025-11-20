# AuraShell - Modern Terminal with AI-Powered Features

<div align="center">

![AuraShell](https://img.shields.io/badge/AuraShell-Terminal-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.7+-green?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A modern, feature-rich terminal emulator with intelligent command completion, auto-correction, and a futuristic UI**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Screenshots](#-screenshots)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Technical Details](#-technical-details)
- [Requirements](#-requirements)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🚀 Overview

AuraShell is a modern terminal emulator built with Python and Tkinter that provides an enhanced command-line experience. It features intelligent auto-completion, command suggestions, auto-correction, and a beautiful futuristic UI design.

### Why AuraShell?

- **Smart Auto-Complete**: Tab completion with intelligent suggestions
- **Auto-Correction**: Suggests corrections for misspelled commands
- **Modern UI**: Futuristic design with glow effects and smooth animations
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **History Management**: Persistent command history with easy navigation
- **Built-in Commands**: Essential shell commands built right in

---

## ✨ Features

### 🎯 Core Features

#### 1. **Intelligent Auto-Complete**
- Real-time command suggestions as you type
- Tab completion for commands and file paths
- Multi-word command support
- Case-insensitive matching
- Fuzzy matching for better suggestions

#### 2. **Auto-Correction**
- Detects misspelled commands
- Suggests up to 3 corrections
- One-click correction selection
- Non-intrusive popup interface

#### 3. **Command Suggestions**
- Dynamic suggestion box that appears as you type
- Click to select and populate commands
- Keyboard navigation (Up/Down arrows)
- Smart positioning (above/below input field)

#### 4. **Modern UI Design**
- Futuristic dark theme with cyan accents
- Glowing borders and hover effects
- Smooth visual transitions
- Responsive layout
- Professional typography

#### 5. **Built-in Commands**
- `help` - Show available commands
- `cd` - Change directory
- `pwd` - Print working directory
- `echo` - Print text
- `history` - View command history
- `type` - Check command type
- `which` - Find command location
- `cls` - Clear screen
- `exit` - Exit shell

#### 6. **Advanced Features**
- Command history with persistent storage
- Pipeline support (`|`)
- Input/output redirection (`>`, `>>`, `<`, `2>`)
- Background process support (`&`)
- Environment variable expansion
- Path globbing (`*`, `?`, `[ ]`)
- Thread-safe execution

---

## 📦 Installation

### Prerequisites

- Python 3.7 or higher
- Tkinter (usually included with Python)

### Quick Install

1. **Clone or download the repository**
   ```bash
   git clone <repository-url>
   cd AuraShell
   ```

2. **Run the application**
   ```bash
   python AuraShell_Gui_1.py
   ```

That's it! No additional dependencies required.

### Verify Installation

```bash
python --version  # Should be 3.7+
python -c "import tkinter; print('Tkinter available')"
```

---

## 🎮 Usage

### Starting AuraShell

```bash
python AuraShell_Gui_1.py
```

### Basic Commands

```bash
# List files
dir          # Windows
ls           # Linux/Mac (if available)

# Change directory
cd Documents
cd ..        # Go up one level
cd ~         # Go to home directory

# View current directory
pwd

# Clear screen
cls          # or Ctrl+L

# View history
history

# Get help
help
```

### Auto-Complete

1. **Type a partial command** (e.g., `hel`)
2. **Press Tab** to see suggestions
3. **Use Up/Down arrows** to navigate
4. **Press Tab again** or **click** to select
5. **Press Enter** to execute

### Auto-Correction

1. **Type a misspelled command** (e.g., `helpp`)
2. **Press Enter**
3. **Select a correction** from the popup
4. The corrected command will populate the input field
5. **Press Enter** to execute

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` | Auto-complete / Select suggestion |
| `↑` / `↓` | Navigate history / Navigate suggestions |
| `Enter` | Execute command |
| `Escape` | Hide suggestions |
| `Ctrl+L` | Clear screen |

### Command History

- Use **Up Arrow** to go back in history
- Use **Down Arrow** to go forward in history
- History is automatically saved to `~/.aurashell_history`

---

## 📁 Project Structure

```
AuraShell/
│
├── AuraShell_Gui_1.py      # Main GUI application (recommended)
├── AuraShell_Gui.py         # Alternative GUI version
├── Shell_Executor_1.py      # Command execution engine (recommended)
├── Shell_Executor.py        # Alternative executor version
└── README.md                # This file
```

### File Descriptions

- **AuraShell_Gui_1.py**: Main GUI frontend with all modern features
- **Shell_Executor_1.py**: Core execution engine with auto-correction and suggestions
- **AuraShell_Gui.py**: Alternative GUI implementation
- **Shell_Executor.py**: Alternative executor implementation

---

## 🔧 Technical Details

### Architecture

AuraShell follows a clean separation of concerns:

- **GUI Layer** (`AuraShell_Gui_1.py`): Handles user interface, input/output display, and user interactions
- **Execution Layer** (`Shell_Executor_1.py`): Manages command parsing, execution, history, and suggestions

### Key Components

#### ShellExecutor Class
- Command tokenization and parsing
- Builtin command handling
- External command execution
- Path resolution (PATHEXT-aware on Windows)
- Command history management
- Suggestion generation with fuzzy matching

#### AuraShellGUI Class
- Tkinter-based GUI
- Real-time suggestion display
- Auto-correction popup
- Command history navigation
- Thread-safe output handling

### Features Implementation

#### Auto-Complete
- Uses `get_suggestions()` method
- Searches builtin commands and PATH executables
- Supports prefix and fuzzy matching
- Handles file path completions

#### Auto-Correction
- Uses `difflib` for fuzzy string matching
- Calculates similarity scores
- Suggests top 3 matches
- Non-blocking popup interface

#### Suggestion Box
- Dynamic positioning (above/below input)
- Bounds checking
- Glow effect styling
- Click-to-select functionality

---

## 📋 Requirements

### System Requirements

- **Operating System**: Windows, Linux, or macOS
- **Python**: 3.7 or higher
- **RAM**: Minimal (runs efficiently)
- **Disk Space**: < 1 MB

### Python Dependencies

AuraShell uses only Python standard library modules:

- `tkinter` - GUI framework
- `threading` - Thread-safe operations
- `subprocess` - Command execution
- `os` - System operations
- `shlex` - Command parsing
- `glob` - Path expansion
- `difflib` - Fuzzy matching

**No external packages required!**

---

## 🎨 Customization

### Color Scheme

Edit the `colors` dictionary in `AuraShell_Gui_1.py`:

```python
self.colors = {
    'bg_main': '#1E1E2E',        # Main background
    'accent': '#00D9FF',          # Accent color (cyan)
    'prompt': '#00FFD1',          # Prompt color
    # ... more colors
}
```

### History File Location

Change the history file path in `Shell_Executor_1.py`:

```python
history_file: str = os.path.expanduser("~/.aurashell_history")
```

### Window Size

Modify the window geometry in `AuraShell_Gui_1.py`:

```python
self.geometry("900x700")  # width x height
```

---

## 🐛 Troubleshooting

### Issue: Suggestions not appearing

**Solution**: Make sure you're typing in the input field and the command exists in PATH or builtins.

### Issue: Commands not executing

**Solution**: 
- Check if the command exists in your system PATH
- Verify the command is executable
- Check error messages in the output area

### Issue: History not saving

**Solution**: 
- Check file permissions for `~/.aurashell_history`
- Ensure you have write access to your home directory

### Issue: Window not displaying properly

**Solution**:
- Update your Python/Tkinter installation
- Check display resolution settings
- Try running with different window sizes

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

### Areas for Contribution

- Additional builtin commands
- Theme customization options
- Performance optimizations
- Cross-platform improvements
- Documentation improvements
- Bug fixes

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- Built with Python and Tkinter
- Inspired by modern terminal emulators
- Designed for productivity and aesthetics

---

## 📞 Support

For issues, questions, or suggestions:

- Open an issue on GitHub
- Check existing issues for solutions
- Review the code comments for implementation details

---

## 🗺️ Roadmap

Future enhancements planned:

- [ ] Plugin system for custom commands
- [ ] Multiple theme support
- [ ] Command aliases
- [ ] Tab completion for arguments
- [ ] Syntax highlighting in output
- [ ] Split panes support
- [ ] Session management
- [ ] Export/import settings

---

<div align="center">

**Made with ❤️ for developers who love beautiful terminals**

⭐ Star this repo if you find it useful!

</div>

