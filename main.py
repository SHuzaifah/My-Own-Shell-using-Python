import sys, os, subprocess, readline, shlex

BUILTINS = {
    "exit",
    "echo",
    "type",
    "pwd",
    "cd",
    "history",
}

command_history = []
last_written_index = 0  # Track how many commands have been written to file


def display_matches_hook(substitution, matches, longest_match_length):
    """Custom display for showing completion matches without trailing spaces"""
    print()
    for match in matches:
        print(match.rstrip(), end="  ")  # Remove space for display
    print()
    print("$ " + readline.get_line_buffer(), end="", flush=True)


def complete(text, state):
    if state == 0:
        commands = list(BUILTINS)

        path = os.environ.get("PATH", "")
        for dir in path.split(":"):
            try:
                for item in os.listdir(dir):
                    full_path = os.path.join(dir, item)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        commands.append(item)
            except:
                pass

        # Generate list of matches
        complete.matches = [c for c in commands if c.startswith(text)]

    if state < len(complete.matches):
        # Always add space - display hook handles showing without space
        return complete.matches[state] + " "
    return None


complete.matches = []


def find_in_path(command):
    # Simulate searching for a command in the system PATH
    # in a real shell, this would check the filesystem

    path = os.environ.get("PATH", "")
    for dir in path.split(":"):
        full_path = os.path.join(dir, command)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None


def main():
    # TODO: Uncomment the code below to pass the first stage
    global last_written_index

    # Read history from HISTFILE on startup if it exists
    histfile = os.environ.get("HISTFILE")
    if histfile:
        histfile = os.path.expanduser(histfile)
        try:
            with open(histfile, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        command_history.append(line)
            last_written_index = len(command_history)
        except FileNotFoundError:
            pass  # File doesn't exist yet, that's ok
        except Exception:
            pass  # Ignore other errors silently

    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n;")
    readline.set_completion_display_matches_hook(display_matches_hook)

    while True:
        # Read - get user input
        try:
            command = input("$ ")
        except EOFError:
            # Append history on exit (Ctrl+D)
            histfile = os.environ.get("HISTFILE")
            if histfile:
                histfile = os.path.expanduser(histfile)
                try:
                    with open(histfile, "a") as f:
                        # Only append commands added during this session
                        for hist_cmd in command_history[last_written_index:]:
                            f.write(hist_cmd + "\n")
                except Exception:
                    pass  # Ignore errors silently
            break  # Handle Ctrl+D to exit

        # Check for output redirection FIRST
        output_file = None
        redirect_type = "stdout"  # Default redirect type
        append_mode = False  # Default to overwrite mode

        if command.strip():
            command_history.append(command)

        if ">" in command:
            if "2>>" in command:
                cmd_part, file_part = command.split("2>>", 1)
                redirect_type = "stderr"  # Redirect/Append standard error
                append_mode = True
            elif "1>>" in command:
                cmd_part, file_part = command.split("1>>", 1)
                redirect_type = "stdout"  # Append/Redirect standard ouput
                append_mode = True
            elif ">>" in command:
                cmd_part, file_part = command.split(">>", 1)
                redirect_type = "stdout"
                append_mode = True
            elif "2>" in command:
                cmd_part, file_part = command.split("2>", 1)
                redirect_type = "stderr"
                append_mode = False
            elif "1>" in command:
                cmd_part, file_part = command.split("1>", 1)
                redirect_type = "stdout"
                append_mode = False
            else:
                cmd_part, file_part = command.split(">", 1)
                redirect_type = "stdout"
                append_mode = False

            # Parse the file part to get just the filename (handles quotes)
            file_parts = shlex.split(file_part.strip())
            output_file = file_parts[0] if file_parts else None
            command = cmd_part.strip()  # Update command to be just before redirect

        # Check for pipeline (pipe character)
        if "|" in command:
            # Split command string on pipe character
            pipeline_commands = command.split("|")

            # Validate pipeline has at least 2 commands
            if len(pipeline_commands) < 2:
                print("Error: pipeline needs at least 2 commands")
                continue

            # Parse all commands in the pipeline
            parsed_cmds = []
            for cmd_str in pipeline_commands:
                parts = shlex.split(cmd_str.strip())
                if parts:
                    parsed_cmds.append(parts)

            try:
                # Build pipeline with support for builtins at any position
                processes = []  # List of subprocess.Popen objects
                prev_stdout = None  # Output from previous command

                for i, cmd_parts in enumerate(parsed_cmds):
                    cmd = cmd_parts[0]
                    is_first = i == 0
                    is_last = i == len(parsed_cmds) - 1

                    # Handle builtin commands
                    if cmd in BUILTINS:
                        # Execute builtin and capture output
                        if cmd == "echo":
                            builtin_output = " ".join(cmd_parts[1:])
                        elif cmd == "pwd":
                            builtin_output = os.getcwd()
                        elif cmd == "type":
                            if len(cmd_parts) > 1:
                                cmd_to_check = cmd_parts[1]
                                if cmd_to_check in BUILTINS:
                                    builtin_output = (
                                        f"{cmd_to_check} is a shell builtin"
                                    )
                                else:
                                    path = find_in_path(cmd_to_check)
                                    if path:
                                        builtin_output = f"{cmd_to_check} is {path}"
                                    else:
                                        builtin_output = f"{cmd_to_check}: not found"
                            else:
                                builtin_output = ""
                        elif cmd == "cd":
                            if len(cmd_parts) > 1:
                                path = cmd_parts[1]
                                if path == "~":
                                    path = os.path.expanduser("~")
                                try:
                                    os.chdir(path)
                                    builtin_output = ""
                                except FileNotFoundError:
                                    builtin_output = (
                                        f"cd: {path}: No such file or directory"
                                    )
                                except Exception as e:
                                    builtin_output = f"cd: {e}"
                            else:
                                builtin_output = ""
                        elif cmd == "history":
                            # Check for -w flag (write to file)
                            if len(cmd_parts) > 1 and cmd_parts[1] == "-w":
                                history_file = os.path.expanduser(
                                    cmd_parts[2]
                                    if len(cmd_parts) > 2
                                    else "~/.shell_history"
                                )
                                try:
                                    with open(history_file, "w") as f:
                                        for hist_cmd in command_history:
                                            f.write(hist_cmd + "\n")
                                    last_written_index = len(command_history)
                                    builtin_output = ""  # Silent success
                                except Exception as e:
                                    builtin_output = f"history: {e}"
                            # Check for -a flag (append to file)
                            elif len(cmd_parts) > 1 and cmd_parts[1] == "-a":
                                history_file = os.path.expanduser(
                                    cmd_parts[2]
                                    if len(cmd_parts) > 2
                                    else "~/.shell_history"
                                )
                                try:
                                    with open(history_file, "a") as f:
                                        # Only append commands added since last write
                                        for hist_cmd in command_history[
                                            last_written_index:
                                        ]:
                                            f.write(hist_cmd + "\n")
                                    last_written_index = len(command_history)
                                    builtin_output = ""  # Silent success
                                except Exception as e:
                                    builtin_output = f"history: {e}"
                            # Check for -r flag (read from file)
                            elif len(cmd_parts) > 1 and cmd_parts[1] == "-r":
                                history_file = os.path.expanduser(
                                    cmd_parts[2]
                                    if len(cmd_parts) > 2
                                    else "~/.shell_history"
                                )
                                try:
                                    with open(history_file, "r") as f:
                                        for line in f:
                                            line = line.strip()
                                            if line and line not in command_history:
                                                command_history.append(line)
                                    builtin_output = ""  # No output for -r
                                except FileNotFoundError:
                                    builtin_output = f"history: {history_file}: No such file or directory"
                                except Exception as e:
                                    builtin_output = f"history: {e}"
                            # Check if theres a limit argument
                            elif len(cmd_parts) > 1:
                                try:
                                    limit = int(cmd_parts[1])
                                    history_to_show = command_history[-limit:]
                                    start_index = (
                                        len(command_history) - len(history_to_show) + 1
                                    )
                                except ValueError:
                                    history_to_show = command_history
                                    start_index = 1

                                history_output = []
                                for i, hist_cmd in enumerate(
                                    history_to_show, start=start_index
                                ):
                                    history_output.append(f"{i:>4}  {hist_cmd}")
                                builtin_output = "\n".join(history_output)
                            else:
                                history_to_show = command_history
                                start_index = 1

                                history_output = []
                                for i, hist_cmd in enumerate(
                                    history_to_show, start=start_index
                                ):
                                    history_output.append(f"{i:>4}  {hist_cmd}")
                                builtin_output = "\n".join(history_output)
                        else:
                            builtin_output = ""

                        # If this is the last command, output directly
                        if is_last:
                            if output_file:
                                file_mode = "a" if append_mode else "w"
                                with open(output_file, file_mode) as f:
                                    f.write(builtin_output + "\n")
                            else:
                                print(builtin_output)
                            prev_stdout = None
                        else:
                            # Not last - need to pipe to next command
                            # Store output as bytes to pass to next command
                            prev_stdout = builtin_output.encode()

                    # Handle external commands
                    else:
                        # Determine stdin source
                        if is_first:
                            stdin_source = None  # Read from terminal
                        elif isinstance(prev_stdout, bytes):
                            # Previous was a builtin - create stdin from its output
                            stdin_source = subprocess.PIPE
                        else:
                            # Previous was external - use its stdout
                            stdin_source = prev_stdout

                        # Determine stdout destination
                        if is_last and output_file:
                            # Last command with redirect
                            file_mode = "a" if append_mode else "w"
                            f = open(output_file, file_mode)
                            stdout_dest = f
                        elif is_last:
                            # Last command to terminal
                            stdout_dest = None
                        else:
                            # Not last - pipe to next command
                            stdout_dest = subprocess.PIPE

                        # Create process
                        proc = subprocess.Popen(
                            cmd_parts, stdin=stdin_source, stdout=stdout_dest
                        )
                        processes.append(proc)

                        # If previous was builtin, write its output to this process
                        if isinstance(prev_stdout, bytes):
                            proc.stdin.write(prev_stdout + b"\n")
                            proc.stdin.close()
                        # If previous was external, close its stdout in parent
                        elif prev_stdout is not None:
                            prev_stdout.close()

                        # If not last, save stdout for next command
                        if not is_last:
                            prev_stdout = proc.stdout
                        else:
                            prev_stdout = None

                # Wait for all processes to complete
                for proc in processes:
                    proc.wait()

                # Close output file if opened
                if output_file and "f" in locals():
                    f.close()

            except Exception as e:
                print(f"Error in pipeline: {e}")

            continue  # Skip normal command execution - go to next prompt

        # Parse command into parts, handling quotes
        parts = shlex.split(command) if command.strip() else []
        if not parts:
            continue

        cmd = parts[0]
        args = parts[1:]

        # Evaluate - process the command
        if cmd == "exit":
            # Append history on exit
            histfile = os.environ.get("HISTFILE")
            if histfile:
                histfile = os.path.expanduser(histfile)
                try:
                    with open(histfile, "a") as f:
                        # Only append commands added during this session
                        for hist_cmd in command_history[last_written_index:]:
                            f.write(hist_cmd + "\n")
                except Exception:
                    pass  # Ignore errors silently
            break
        elif cmd == "echo":
            result = " ".join(args)
            if output_file:
                file_mode = "a" if append_mode else "w"
                # Create the file for redirect
                try:
                    with open(output_file, file_mode) as f:
                        if redirect_type == "stdout":
                            # Redirect stdout to file
                            f.write(result + "\n")
                        else:
                            # Redirecting stderr (2>) but echo produces stdout
                            # File gets created empty, output goes to terminal
                            print(result)
                except Exception as e:
                    print(f"Error writing to file: {e}")
            else:
                print(result)
        elif cmd == "type":
            if args:
                cmd_to_check = args[0]
                if cmd_to_check in BUILTINS:
                    print(f"{cmd_to_check} is a shell builtin")
                else:
                    path = find_in_path(cmd_to_check)
                    if path:
                        print(f"{cmd_to_check} is {path}")
                    else:
                        print(f"{cmd_to_check}: not found")
        elif cmd == "pwd":
            print(os.getcwd())
        elif cmd == "cd":
            if args:
                path = args[0]

                # Expand ~ to home directory
                if path == "~":
                    path = os.path.expanduser("~")

                try:
                    os.chdir(path)
                except FileNotFoundError:
                    print(f"cd: {path}: No such file or directory")
                except Exception as e:
                    print(f"cd: {e}")

        elif cmd == "history":
            if args and args[0] == "-w":
                # Write history to file
                history_file = os.path.expanduser(
                    args[1] if len(args) > 1 else "~/.shell_history"
                )
                try:
                    with open(history_file, "w") as f:
                        for hist_cmd in command_history:
                            f.write(hist_cmd + "\n")
                    last_written_index = len(command_history)
                    pass  # Silent success
                except Exception as e:
                    print(f"history: {e}")
            elif args and args[0] == "-a":
                # Append history to file
                history_file = os.path.expanduser(
                    args[1] if len(args) > 1 else "~/.shell_history"
                )
                try:
                    with open(history_file, "a") as f:
                        # Only append commands added since last write
                        for hist_cmd in command_history[last_written_index:]:
                            f.write(hist_cmd + "\n")
                    last_written_index = len(command_history)
                    pass  # Silent success
                except Exception as e:
                    print(f"history: {e}")
            elif args and args[0] == "-r":
                # Read history from file
                history_file = os.path.expanduser(
                    args[1] if len(args) > 1 else "~/.shell_history"
                )
                try:
                    with open(history_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and line not in command_history:  # Avoid duplicates
                                command_history.append(line)
                except FileNotFoundError:
                    print(f"history: {history_file}: No such file or directory")
                except Exception as e:
                    print(f"history: {e}")
            elif args:
                # Check if argument is a number (limit)
                try:
                    limit = int(args[0])
                    history_to_show = command_history[-limit:]
                    start_index = len(command_history) - len(history_to_show) + 1
                except ValueError:
                    # Not a number - show all history
                    history_to_show = command_history
                    start_index = 1
            else:
                history_to_show = command_history
                start_index = 1

            # Only display if not -r, -w, or -a flag
            if not (args and (args[0] == "-r" or args[0] == "-w" or args[0] == "-a")):
                for i, hist_cmd in enumerate(history_to_show, start=start_index):
                    print(f"{i:>4}  {hist_cmd}")

        else:
            # Execute - run external commands
            if find_in_path(cmd):
                try:
                    if output_file:
                        file_mode = "a" if append_mode else "w"
                        # Open file to ensure it's created even if no output
                        with open(output_file, file_mode) as f:
                            if redirect_type == "stderr":
                                subprocess.run(parts, stderr=f)
                            else:
                                subprocess.run(parts, stdout=f)
                    else:
                        subprocess.run(parts)
                except Exception as e:
                    print(f"Error: {e}")
            else:
                print(f"{cmd}: command not found")

    # Continue looping back to "Read"


if __name__ == "__main__":
    main()