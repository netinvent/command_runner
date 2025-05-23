# command_runner
# Platform agnostic command execution, timed background jobs with live stdout/stderr output capture, and UAC/sudo elevation

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
   - Allow stdout/stderr stream output to be redirected to callback functions / output queues / files so you get to handle output in your application while commands are running
   - Callback to optional stop check so we can stop execution from outside command_runner
   - Callback with optional process information so we get to control the process from outside command_runner
   - Callback once we're finished to easen thread usage
   - Optional process priority and io_priority settings
   - System agnostic functionality, the developer shouldn't carry the burden of Windows & Linux differences
   - Optional Windows UAC elevation module compatible with CPython, PyInstaller & Nuitka
   - Optional Linux sudo elevation compatible with CPython, PyInstaller & Nuitka
   - Optional heartbeat for command execution

It is compatible with Python 2.7+, tested up to Python 3.13 (backports some newer functionality to Python 3.5) and is tested on Linux, Windows and MacOS.
It is also compatible with PyPy Python implementation.
...and yes, keeping Python 2.7 compatibility has proven to be quite challenging.

## command_runner

command_runner is a replacement package for subprocess.popen and subprocess.check_output
The main promise command_runner can do is to make sure to never have a blocking command, and always get results.

It works as wrapper for subprocess.popen and subprocess.communicate that solves:
   - Platform differences
      - Handle timeouts even for windows GUI applications that don't return anything to stdout
   - Python language version differences
      - Handle timeouts even on earlier Python implementations
      - Handle encoding even on earlier Python implementations
   - Keep the promise to always return an exit code (so we don't have to deal with exit codes and exception logic at the same time)
   - Keep the promise to always return the command output regardless of the execution state (even with timeouts, callback interrupts and keyboard interrupts)
   - Can show command output on the fly without waiting the end of execution (with `live_output=True` argument)
   - Can give command output on the fly to application by using queues or callback functions
   - Catch all possible exceptions and log them properly with encoding fixes
   - Be compatible, and always return the same result regardless of platform

command_runner also promises to properly kill commands when timeouts are reached, including spawned subprocesses of such commands.
This specific behavior is achieved via psutil module, which is an optional dependency.

   
### command_runner in a nutshell

### In a nutshell

Install with `pip install command_runner`

The following example will work regardless of the host OS and the Python version.

```python
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', timeout=10)
```


## Advanced command_runner usage


### Special exit codes

In order to keep the promise to always provide an exit_code, special exit codes have been added for the case where none is given.
Those exit codes are:

- -250 : command_runner called with incompatible arguments
- -251 : stop_on function returned True
- -252 : KeyboardInterrupt
- -253 : FileNotFoundError, OSError, IOError
- -254 : Timeout
- -255 : Any other uncatched exceptions

This allows you to use the standard exit code logic, without having to deal with various exceptions.

### Default encoding

command_runner has an `encoding` argument which defaults to `utf-8` for Unixes and `cp437` for Windows platforms.
Using `cp437` ensures that most `cmd.exe` output is encoded properly, including accents and special characters, on most locale systems.
Still you can specify your own encoding for other usages, like Powershell where `unicode_escape` is preferred.

```python
from command_runner import command_runner

command = r'C:\Windows\sysnative\WindowsPowerShell\v1.0\powershell.exe --help'
exit_code, output = command_runner(command, encoding='unicode_escape')
```

Earlier subprocess.popen implementations didn't have an encoding setting so command_runner will deal with encoding for those.   
You can also disable command_runner's internal encoding in order to get raw process output (bytes) by passing False boolean.

Example:
```python
from command_runner import command_runner

exit_code, raw_output = command_runner('ping 127.0.0.1', encoding=False)
```

### On the fly (interactive screen) output

**Note: for live output capture and threading, see stream redirection. If you want to run your application while command_runner gives back command output, the best way to achieve this is using queues / callbacks.**

command_runner can output a command output on the fly to stdout, eg show output on screen during execution.
This is helpful when the command is long, and we need to know the output while execution is ongoing.
It is also helpful in order to catch partial command output when timeout is reached or a CTRL+C signal is received.
Example:

```python
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', shell=True, live_output=True)
```

Note: using live output relies on stdout pipe polling, which has lightly higher cpu usage.

### Timeouts

**command_runner has a `timeout` argument which defaults to 3600 seconds.**  
This default setting ensures commands will not block the main script execution.
Feel free to lower / higher that setting with `timeout` argument.
Note that a command_runner will try to kill the whole process tree that the command may have generated.

```python
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', timeout=30)
```

#### Remarks on processes termination

When we instruct command_runner to stop a process (because of one of the requirements met, example timeouts), using `shell=True` will spawn a shell which will spawn the desired child process. Under MS Windows, there is no direct process tree, so we cannot easily kill the whole process tree.
We fixed this by walking processes during runtime. The drawback is that orphaned processes cannot be identified this way.

### Disabling logs / silencing

`command_runner` has it's own logging system, which will log all sorts of error logs.
If you need to disable it's logging, just run with argument silent.
Be aware that logging.DEBUG log levels won't be silenced, by design.

Example:
```python
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', silent=True)
```

If you also need to disable logging.DEBUG level, you can run the following code which will required logging.CRITICAL only messages which `command_runner` never does:

```python
import logging
import command_runner

logging.getLogger('command_runner').setLevel(logging.CRITICAL)
```

### Capture method

`command_runner` allows two different process output capture methods:

`method='monitor'` which is default:
 - A thread is spawned in order to check stop conditions and kill process if needed
 - A main loop waits for the process to finish, then uses proc.communicate() to get it's output
 - Pros:
     - less CPU usage
     - less threads
 - Cons:
     - cannot read partial output on KeyboardInterrupt or stop_on (still works for partial timeout output)
     - cannot use queues or callback functions redirectors
     - is 0.1 seconds slower than poller method
     

`method='poller'`:
 - A thread is spawned and reads stdout/stderr pipes into output queues
 - A poller loop reads from the output queues, checks stop conditions and kills process if needed
 - Pros: 
      - Reads on the fly, allowing interactive commands (is also used with `live_output=True`)
      - Allows stdout/stderr output to be written live to callback functions, queues or files (useful when threaded)
      - is 0.1 seconds faster than monitor method, is preferred method for fast batch runnings
 - Cons:
      - lightly higher CPU usage

Example:
```python
from command_runner import command_runner


exit_code, output = command_runner('ping 127.0.0.1', method='poller')
exit_code, output = command_runner('ping 127.0.0.1', method='monitor')
```

#### stdout / stderr stream redirection using poller capture method

command_runner can redirect the command's stdout and/or stderr streams to different outputs:
 - subprocess pipes
 - /dev/null or NUL
 - files
 - queues
 - callback functions

Unless an output redirector is given for `stderr` argument, stderr will be redirected to `stdout` stream.
Note that both queues and callback function redirectors require `poller` method and will fail if method is not set.

Output redirector descriptions:  

- subprocess pipes

  - By default, stdout writes into a subprocess.PIPE which is read by command_runner and returned as `output` variable.
  - You may also pass any other subprocess.PIPE int values to `stdout` or `stderr` arguments.

- /dev/null or NUL

  - If `stdout=False` and/or `stderr=False` argument(s) are given, command output will not be saved.
  - stdout/stderr streams will be redirected to `/dev/null` or `NUL` depending on platform.
  - Output will always be `None`. See `split_streams` for more details using multiple outputs.

- files

  - Giving `stdout` and/or `stderr` arguments a string, `command_runner` will consider the string to be a file path where stream output will be written live.
  - Examples:
```python
from command_runner import command_runner
exit_code, output = command_runner('dir', stdout=r"C:/tmp/command_result", stderr=r"C:/tmp/command_error", shell=True)
```
```python
from command_runner import command_runner
exit_code, output = command_runner('dir', stdout='/tmp/stdout.log', stderr='/tmp/stderr.log', shell=True)
```
  - Opening a file with the wrong encoding (especially opening a CP437 encoded file on Windows with UTF-8 coded might endup with UnicodedecodeError.)

- queues

  - Queue(s) will be filled up by command_runner.
  - In order to keep your program "live", we'll use the threaded version of command_runner which is basically the same except it returns a future result instead of a tuple.
  - Note: With all the best will, there's no good way to achieve this under Python 2.7 without using more queues, so the threaded version is only compatible with Python 3.3+.
  - For Python 2.7, you must create your thread and queue reader yourself (see footnote for a Python 2.7 compatible example).
  - Threaded command_runner plus queue example:

```python
import queue
from command_runner import command_runner_threaded

output_queue = queue.Queue()
stream_output = ""
thread_result = command_runner_threaded('ping 127.0.0.1', shell=True, method='poller', stdout=output_queue)

read_queue = True
while read_queue:
    try:
        line = output_queue.get(timeout=0.1)
    except queue.Empty:
        pass
    else:
        if line is None:
            read_queue = False
        else:
            stream_output += line
            # ADD YOUR LIVE CODE HERE

# Now we may get exit_code and output since result has become available at this point
exit_code, output = thread_result.result()
```
  - You might also want to read both stdout and stderr queues. In that case, you can create a read loop just like in the following example.
  - Here we're reading both queues in one loop, so we need to observe a couple of conditions before stopping the loop, in order to catch all queue output:
```python
import queue
from time import sleep
from command_runner import command_runner_threaded

stdout_queue = queue.Queue()
stderr_queue = queue.Queue()
thread_result = command_runner_threaded('ping 127.0.0.1', method='poller', shell=True, stdout=stdout_queue, stderr=stderr_queue)

read_stdout = read_stderr = True
while read_stdout or read_stderr:

    try:
        stdout_line = stdout_queue.get(timeout=0.1)
    except queue.Empty:
        pass
    else:
        if stdout_line is None:
            read_stdout = False
        else:
            print('STDOUT:', stdout_line)

    try:
        stderr_line = stderr_queue.get(timeout=0.1)
    except queue.Empty:
        pass
    else:
        if stderr_line is None:
            read_stderr = False
        else:
            print('STDERR:', stderr_line)
    
    # ADD YOUR LIVE CODE HERE

exit_code, output = thread_result.result()
assert exit_code == 0, 'We did not succeed in running the thread'

```

- callback functions

  - The callback function will get one argument, being a str of current stream readings.
  - It will be executed on every line that comes from streams. Example:
```python
from command_runner import command_runner

def callback_function(string):
    # ADD YOUR CODE HERE
    print('CALLBACK GOT:', string)
    
# Launch command_runner
exit_code, output = command_runner('ping 127.0.0.1', stdout=callback_function, method='poller')
```

### stdin stream redirection

`command_runner` allows to redirect some stream directly into the subprocess it spawns.

Example code
```python
import sys
from command_runner import command_runner


exit_code, output = command_runner("gzip -d", stdin=sys.stdin.buffer)
print("Uncompressed data", output)
```
The above program, when run with `echo "Hello, World!" | gzip | python myscript.py` will show the uncompressed  string `Hello, World!`

You can use whatever file descriptor you want, basic ones being sys.stdin for text input and sys.stdin.buffer for binary input.

### Checking intervals

By default, command_runner checks timeouts and outputs every 0.05 seconds.
You can increase/decrease this setting via `check_interval` setting which accepts floats.
Example: `command_runner(cmd, check_interval=0.2)`
Note that lowering `check_interval` will increase CPU usage.

### stop_on

In some situations, you want a command to be aborted on some external triggers.
That's where `stop_on` argument comes in handy,
Just pass a function to `stop_on`, which will be executed every on every `check_interval`. As soon as function result becomes True, execution will halt with exit code -251.

As a side note, when using `stop_on=my_func`, if `my_func` is cpu/io intensive, you should set `check_interval` to something reasonable, which generally counts in seconds.

Example:
```python
from command_runner import command_runner

def some_function():
    return True if we_must_stop_execution
exit_code, output = command_runner('ping 127.0.0.1', stop_on=some_function, check_interval=2)
```

### Getting current process information

`command_runner` can provide an instance of subprocess.Popen of currently run command as external data, in order to retrieve process data like pids.  
In order to do so, just declare a function and give it as `process_callback` argument.

Example:
```python
from command_runner import command_runner

def show_process_info(process):
    print('My process has pid: {}'.format(process.pid))

exit_code, output = command_runner('ping 127.0.0.1', process_callback=show_process_info)
```

### Split stdout and stderr

By default, `command_runner` returns a tuple like `(exit_code, output)` in which output contains both stdout and stderr stream outputs.
You can alter that behavior by using argument `split_stream=True`.
In that case, `command_runner` will return a tuple like `(exit_code, stdout, stderr)`.

Example:
```python
from command_runner import command_runner

exit_code, stdout, stderr = command_runner('ping 127.0.0.1', split_streams=True)
print('exit code:', exit_code)
print('stdout', stdout)
print('stderr', stderr)
```

### On-exit Callback

`command_runner` allows to execute a callback function once it has finished it's execution.  
This might help building threaded programs where a callback is needed to disable GUI elements for example, or make the program aware that execution has finished without the need for polling checks.

Example:
```python
from command_runner import command_runner

def do_something():
    print("We're done running")

exit_code, output = command_runner('ping 127.0.0.1', on_exit=do_something)
```

### Process and IO priority
`command_runner` can set it's subprocess priority to 'low', 'normal' or 'high', which translate to 15, 0, -15 niceness on Linux and BELOW_NORMAL_PRIORITY_CLASS and HIGH_PRIORITY_CLASS in Windows.
On Linux, you may also directly use priority with niceness int values.

You may also set subprocess io priority to 'low', 'normal' or 'high'.

Example:
```python
from command_runner import command_runner

exit_code, output = command_runner('some_intensive_process', priority='low', io_priority='high')
```

### Heartbeat
When running long commands, one might want to know that the program is still running.    
The following example will log a message every hour stating that we're still running our command

```python
from command_runner import command_runner

exit_code, output = command_runner('/some/long/command', timeout=None, heartbeat=3600)
```

### Other arguments

`command_runner` takes **any** argument that `subprocess.Popen()` would take.

It also uses the following standard arguments:
 - command (str/list): The command, doesn't need to be a list, a simple string works
 - valid_exit_codes (list): List of exit codes which won't trigger error logs
 - timeout (int): seconds before a process tree is killed forcefully, defaults to 3600
 - shell (bool): Shall we use the cmd.exe or /usr/bin/env shell for command execution, defaults to False
 - encoding (str/bool): Which text encoding the command produces, defaults to cp437 under Windows and utf-8 under Linux
 - stdin (sys.stdin/int): Optional stdin file descriptor, sent to the process command_runner spawns
 - stdout (str/queue.Queue/function/False/None): Optional path to filename where to dump stdout, or queue where to write stdout, or callback function which is called when stdout has output
 - stderr (str/queue.Queue/function/False/None): Optional path to filename where to dump stderr, or queue where to write stderr, or callback function which is called when stderr has output
 - no_close_queues (bool): Normally, command_runner sends None to stdout / stderr queues when process is finished. This behavior can be disabled allowing to reuse those queues for other functions wrapping command_runner
 - windows_no_window (bool): Shall a command create a console window (MS Windows only), defaults to False
 - live_output (bool): Print output to stdout while executing command, defaults to False
 - method (str): Accepts 'poller' or 'monitor' stdout capture and timeout monitoring methods
 - check interval (float): Defaults to 0.05 seconds, which is the time between stream readings and timeout checks
 - stop_on (function): Optional function that when returns True stops command_runner execution
 - on_exit (function): Optional function that gets executed when command_runner has finished (callback function)
 - process_callback (function): Optional function that will take command_runner spawned process as argument, in order to deal with process info outside of command_runner
 - split_streams (bool): Split stdout and stderr into two separate results
 - silent (bool): Allows to disable command_runner's internal logs, except for logging.DEBUG levels which for obvious reasons should never be silenced
 - priority (str): Allows to set CPU bound process priority (takes 'low', 'normal' or 'high' parameter)
 - io_priority (str): Allows to set IO priority for process (takes 'low', 'normal' or 'high' parameter)
 - heartbeat (int): Optional seconds on which command runner should log a heartbeat message
 - close_fds (bool): Like Popen, defaults to True on Linux and False on Windows
 - universal_newlines (bool): Like Popen, defaults to False
 - creation_flags (int): Like Popen, defaults to 0
 - bufsize (int): Like Popen, defaults to 16384. Line buffering (bufsize=1) is deprecated since Python 3.7

**Note that ALL other subprocess.Popen arguments are supported, since they are directly passed to subprocess.**


### command_runner Python 2.7 compatible queue reader

The following example is a Python 2.7 compatible threaded implementation that reads stdout / stderr queue in a thread.
This only exists for compatibility reasons.

```python
import queue
import threading
from command_runner import command_runner

def read_queue(output_queue):
    """
    Read the queue as thread
    Our problem here is that the thread can live forever if we don't check a global value, which is...well ugly
    """
    stream_output = ""
    read_queue = True
    while read_queue:
        try:
            line = output_queue.get(timeout=1)
        except queue.Empty:
            pass
        else:
            # The queue reading can be stopped once 'None' is received.
            if line is None:
                read_queue = False
            else:
                stream_output += line
                # ADD YOUR LIVE CODE HERE


# Create a new queue that command_runner will fill up
output_queue = queue.Queue()

# Create a thread of read_queue() in order to read the queue while command_runner executes the command
read_thread = threading.Thread(
    target=read_queue, args=(output_queue)
)
read_thread.daemon = True  # thread dies with the program
read_thread.start()

# Launch command_runner, which will be blocking. Your live code goes directly into the threaded function
exit_code, output = command_runner('ping 127.0.0.1', stdout=output_queue, method='poller')
```

# UAC Elevation / sudo elevation

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
