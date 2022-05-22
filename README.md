# command_runner
## A python tool for rapid platform agnostic command execution and UAC/sudo elevation

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Percentage of issues still open](http://isitmaintained.com/badge/open/netinvent/command_runner.svg)](http://isitmaintained.com/project/netinvent/command_runner "Percentage of issues still open")
[![Maintainability](https://api.codeclimate.com/v1/badges/defbe10a354d3705f287/maintainability)](https://codeclimate.com/github/netinvent/command_runner/maintainability)
[![codecov](https://codecov.io/gh/netinvent/command_runner/branch/master/graph/badge.svg?token=rXqlphOzMh)](https://codecov.io/gh/netinvent/command_runner)
[![linux-tests](https://github.com/netinvent/command_runner/actions/workflows/linux.yaml/badge.svg)](https://github.com/netinvent/command_runner/actions/workflows/linux.yaml)
[![windows-tests](https://github.com/netinvent/command_runner/actions/workflows/windows.yaml/badge.svg)](https://github.com/netinvent/command_runner/actions/workflows/windows.yaml)
[![GitHub Release](https://img.shields.io/github/release/netinvent/command_runner.svg?label=Latest)](https://github.com/netinvent/command_runner/releases/latest)


command_runner's purpose is to run external commands from python, just like subprocess on which it relies, 
while solving various problems a developer may face among:
   - Handling of all possible subprocess.popen / subprocess.check_output scenarios / python versions in one handy function without encoding / timeout hassle
   - Allow stdout/stderr stream output to be redirected to callback functions / output queues / files so you get live output into your application
   - Callback to optional stop check so we can stop execution from outside command_runner
   - Callback with optional process information so we get to control the process from outside command_runner
   - System agnostic functionality, the developer shouldn't carry the burden of Windows & Linux differences
   - Optional Windows UAC elevation module compatible with CPython, PyInstaller & Nuitka
   - Optional Linux sudo elevation compatible with CPython, PyInstaller & Nuitka

It is compatible with Python 2.7+ (backports some newer Python 3.5 functionality) and is tested on both Linux and Windows.
...and yes, keeping Python 2.7 compatibility is quite challenging.

## command_runner

command_runner is a replacement package for subprocess.popen and subprocess.check_output
The main promise command_runner can do is to make sure to never have a blocking command, and always get results.

It works as wrapper for subprocess.popen and subprocess.check_output that solves:
   - Platform differences
      - Handle timeouts even for windows GUI applications that don't return anything to stdout
   - Python language version differences
      - Handle timeouts even on earlier Python implementations
      - Handle encoding even on earlier Python implementations
   - Keep the promise to always return an exit code (so we don't have to deal with exit codes and exception logic at the same time)
   - Keep the promise to always return the command output regardless of the execution state (even with timeouts and keyboard interrupts)
   - Can show command output on the fly without waiting the end of execution (with `live_output=True` argument)
   - Can give command output on the fly to application by using queues or callback functions
   - Catch all possible exceptions and log them properly with encoding fixes

command_runner also promises to properly kill commands when timeouts are reached, including spawned subprocesses of such commands.
This specific behavior is achieved via psutil module, which is an optional dependency.



   
### command_runner in a nutshell

Install with `pip install command_runner`

The following example will work regardless of the host OS and the Python version.

```python
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', timeout=30, encoding='utf-8')
```


## Guide

### Setup

`pip install command_runner` or download the latest git release


### Advanced command_runner usage


#### Special exit codes

In order to keep the promise to always provide an exit_code, some arbitrary exit codes have been added for the case where none is given.
Those exit codes are:

- -250 : command_runner called with incompatible arguments
- -251 : stop_on function returned True
- -252 : KeyboardInterrupt
- -253 : FileNotFoundError, OSError, IOError
- -254 : Timeout
- -255 : Any other uncatched exceptions

This allows you to use the standard exit code logic, without having to deal with various exceptions.

#### Default encoding

command_runner has an `encoding` argument which defaults to `utf-8` for Unixes and `cp437` for Windows platforms.
Using `cp437` ensures that most `cmd.exe` output is encoded properly, including accents and special characters, on most locale systems.
Still you can specify your own encoding for other usages, like Powershell where `unicode_escape` is preferred.

```python
from command_runner import command_runner

command = r'C:\Windows\sysnative\WindowsPowerShell\v1.0\powershell.exe --help'
exit_code, output = command_runner(command, encoding='unicode_escape')
```

Earlier subprocess.popen implementations didn't have an encoding setting so command_runner will deal with encoding for those.

#### On the fly (interactive) output

command_runner can output a command output on the fly to stdout, eg show output during execution.
This is helpful when the command is long, and we need to know the output while execution is ongoing.
It is also helpful in order to catch partial command output when timeout is reached or a CTRL+C signal is received.
Example:

```python
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', shell=True, live_output=True)
```

Note: using live output relies on stdout pipe polling, which has lightly higher cpu usage.

#### Timeouts

**command_runner has a `timeout` argument which defaults to 3600 seconds.**
This default setting ensures commands will not block the main script execution.
Feel free to lower / higher that setting with `timeout` argument.
Note that a command_runner kills the whole process tree that the command may have generated, even under Windows.

```python
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', timeout=30)
```

### Remarks on processes

Using `shell=True` will spawn a shell which will spawn the desired child process.
Be aware that under MS Windows, no direct process tree is available.
We fixed this by walking processes during runtime. The drawback is that orphaned processes cannot be identified this way.


#### Disabling logs

Whenever you want another loglevel for command_runner, you might do with the following statement in your code

```python
import logging
import command_runner

logging.getLogger('command_runner').setLevel(logging.ERROR)
```

#### Capture method

`command_runner` allows two different process output capture methods:

`method='monitor'` which is default:
 - A thread is spawned in order to check timeout and kill process if needed
 - A main loop waits for the process to finish, then uses proc.communicate() to get it's output
 - Pros: less CPU usage
 - Cons: cannot read partial output on KeyboardInterrupt (still works for partial timeout output)

`method='poller'`:
 - A thread is spawned and reads stdout pipe into a output queue
 - A poller loop reads from the output queue, checks timeout and kills process if needed
 - Pros: 
      - Reads on the fly, allowing interactive commands (is also used with `live_output=True`)
      - Allows stdout/stderr output to be written live to callback functions, queues or files 
 - Cons: Lightly higher CPU usage


Example:
```python
from command_runner import command_runner
exit_code, output = command_runner('ping 127.0.0.1', method='poller')
exit_code, output = command_runner('ping 127.0.0.1', method='monitor')
```

#### Stream redirection

command_runner can redirect stdout and/or stderr streams to different outputs:
 - subprocess pipes
 - files
 - queues
 - callback functions
 - Null
 
Both queues and callback function redirects require `poller` method and will fail if method is not set.
Unless an output redrection is given for `stderr`, it will be redirected to `stdout` stream.

Possible output redirection options are:

- subprocess pipes / Null:
By default, stdout writes into a subprocess.PIPE which is read by command_runner and returned as `output` variable.
If `stdout=False` and/or `stderr=False` argument(s) are given, command output will not be saved.

- files

Giving `stdout` and/or `stderr` arguments a string, `command_runner` will consider the string to be a file path where stream output will be written live.
Example (of course this also works with unix paths):

```python
from command_runner import command_runner
exit_code, output = command_runner('dir', stdout='C:/tmp/command_result', stderr='C:/tmp/command_error', shell=True)
```

- queues:
Queue will be filled up by command_runner.
In order to keep your program "live", we'll thread a queue reading function where we can handle it's output while command_runner executes the command.
Example:

```python
import queue
import threading
from command_runner import command_runner


def read_queue(output_queue):
    """
    Read the queue
    """
    stream_output = ""
    while True:
        try:
            line = output_queue.get(timeout=0.1)
        except queue.Empty:
            pass
        else:
            # The queue reading can be stopped once 'None' is received.
            if line is None:
                break
            else:
                stream_output += line
                # ADD YOUR CODE HERE
    return stream_output

# Create a new queue that command_runner will fill up
output_queue = queue.Queue()

# Create a thread of read_queue() in order to read the queue while command_runner executes the command
read_thread = threading.Thread(
    target=read_queue, args=(output_queue, )
)
read_thread.daemon = True  # thread dies with the program
read_thread.start()

# Launch command_runner
exit_code, output = command_runner('ping 127.0.0.1', stdout=output_queue, method='poller')
```

- callback functions

The callback function will get one argument, being a str of current stream readings.
It will be executed on every line that comes from streams.
Example:
```python
from command_runner import command_runner

def callback_function(string):
    # ADD YOUR CODE HERE
    print('CALLBACK GOT:', string)
    
# Launch command_runner
exit_code, output = command_runner('ping 127.0.0.1', stdout=callback_function, method='poller')
```

### Stop_on

In some situations, you want a command to be aborted on some external triggers.
That's where `stop_on` argument comes in handy.
Just pass a function to `stop_on`, as soon as function result becomes True, execution will halt with exit code -251.

Example:
```python
from command_runner import command_runner

def some_function():
    return True if my_conditions_are_met
exit_code, output = command_runner('ping 127.0.0.1', stop_on=some_function)
```

#### Checking intervals

By default, command_runner checks timeouts and outputs every 0.05 seconds.
You can increase/decrease this setting via `check_interval` setting which accepts floats.
Example: `command_runner(cmd, check_interval=0.2)`
Note that lowering `check_interval` will increase CPU usage.

#### Getting current process information

`command_runner` can provide a subprocess.Popen instance of currently run process as external data.
In order to do so, just declare a function and give it as `process_callback` argument.

Example:
```python
from command_runner import command_runner

def show_process_info(process):
    print('My process has pid: {}'.format(process.pid))

exit_code, output = command_runner('ping 127.0.0.1', process_callback=show_process_info)
```

#### Other arguments

`command_runner` takes **any** argument that `subprocess.Popen()` would take.

It also uses the following standard arguments:
 - command: The command, doesn't need to be a list, a simple string works
 - valid_exit_codes: List of exit codes which won't trigger error logs
 - timeout: seconds before a process tree is killed forcefully, defaults to 3600
 - shell: Shall we use the cmd.exe or /usr/bin/env shell for command execution, defaults to False
 - encoding: Which text encoding the command produces, defaults to cp437 under Windows and utf-8 under Linux
 - stdout: Optional path to filename where to dump stdout, or queue where to write stdout, or callback function which is called when stdout has output
 - stderr: Optional path to filename where to dump stderr, or queue where to write stderr, or callback function which is called when stderr has output
 - windows_no_window: Shall a command create a console window (MS Windows only), defaults to False
 - live_output: Print output to stdout while executing command, defaults to False
 - method: Accepts 'poller' or 'monitor' stdout capture and timeout monitoring methods
 - check interval: Defaults to 0.05 seconds, which is the time between stream readings and timeout checks
 - stop_on: Optional function that when returns True stops command_runner execution
 - process_callback: Optional function that will take command_runner spawned process as argument, in order to deal with process info outside of command_runner
 - close_fds: Like Popen, defaults to True on Linux and False on Windows
 - universal_newlines: Like Popen, defaults to False
 - creation_flags: Like Popen, defaults to 0
 - bufsize: Like Popen, defaults to 16384. Line buffering (bufsize=1) is deprecated since Python 3.7

## UAC Elevation / sudo elevation

command_runner package allowing privilege elevation.
Becoming an admin is fairly easy with command_runner.elevate
You only have to import the elevate module, and then launch your main function with the elevate function.

### elevation In a nutshell

```python
from command_runner.elevate import elevate

def main():
    """My main function that should be elevated"""
    print("Who's the administrator, now ?")

if __name__ == '__main__':
    elevate(main)
```

elevate function handles arguments (positional and keyword arguments).
`elevate(main, arg, arg2, kw=somearg)` will call `main(arg, arg2, kw=somearg)`

### Advanced elevate usage

#### is_admin() function

The elevate module has a nifty is_admin() function that returns a boolean according to your current root/administrator privileges.
Usage:

```python
from command_runner.elevate import is_admin

print('Am I an admin ? %s' % is_admin())
```

#### sudo elevation

Initially designed for Windows UAC, command_runner.elevate can also elevate privileges on Linux, using the sudo command.
This is mainly designed for PyInstaller / Nuitka executables, as it's really not safe to allow automatic privilege elevation of a Python interpreter.

Example for a binary in `/usr/local/bin/my_compiled_python_binary`

You'll have to allow this file to be run with sudo without a password prompt.
This can be achieved in `/etc/sudoers` file.

Example for Redhat / Rocky Linux, where adding the following line will allow the elevation process to succeed without password:
```
someuser ALL= NOPASSWD:/usr/local/bin/my_compiled_python_binary
```
