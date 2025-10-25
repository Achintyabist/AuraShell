AuraShell (GUI)

A custom shell application with a graphical user interface (GUI) built using Python and the Tkinter library. It provides essential shell functionalities along with smart features like command suggestion and correction.

Features

GUI Interface: Runs in its own dedicated window, not just in a standard terminal.

Built-in Commands: Supports common shell commands internally:

exit: Closes the shell and saves command history.

echo [text]: Prints text to the output area.

type [command]: Shows if a command is a built-in or an external program.

cd [directory]: Changes the current working directory (supports ~, .., absolute/relative paths).

pwd: Prints the current working directory.

history: Displays the numbered command history.

cls: Clears the output area (useful on Windows).

help: Shows a list of available built-in commands.

External Command Execution: Can run any command or program available in your system's PATH (e.g., dir, python, git, notepad on Windows).

Command Correction ("Did you mean...?"): If you mistype a command, it suggests the top 3 closest matches and allows you to execute one by typing its number.

Auto-Suggestion Pop-up: As you type a command, a pop-up list appears just above the input bar, showing possible command completions.

Use <Tab> to navigate down the suggestion list.

Use <Enter> to select the highlighted suggestion and insert it into the input bar.

Persistent Command History:

Loads previous commands from ~/.aurashell_history on startup.

Saves all commands from the current session to the file on exit.

History Navigation: Use the <Up> and <Down> arrow keys to scroll through your command history in the input bar.

Setup and Installation

Prerequisites: Make sure you have Python 3.x installed on your system.

You can check by opening a terminal or command prompt and typing python --version.

If you need to install Python, download it from python.org. Important: During installation, ensure you check the box "Add Python to PATH".

Get the Code: Place the py_shell_gui.py file in a dedicated project folder (e.g., MyAuraShell).

Install Dependencies: Open your terminal or command prompt, navigate to your project folder using cd, and install the required library:

pip install rapidfuzz


Running AuraShell

Open your terminal or command prompt.

Navigate (cd) to the directory where you saved py_shell_gui.py.

Run the shell using the Python interpreter:

python py_shell_gui.py
