# command_runner
## A python tool for rapid platform agnostic command execution and elevation

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Percentage of issues still open](http://isitmaintained.com/badge/open/netinvent/command_runner.svg)](http://isitmaintained.com/project/netinvent/command_runner "Percentage of issues still open")
[![Maintainability](https://api.codeclimate.com/v1/badges/defbe10a354d3705f287/maintainability)](https://codeclimate.com/github/netinvent/command_runner/maintainability)
[![codecov](https://codecov.io/gh/netinvent/command_runner/branch/master/graph/badge.svg?token=rXqlphOzMh)](https://codecov.io/gh/netinvent/command_runner)
[![linux-tests](https://github.com/netinvent/command_runner/actions/workflows/main.yaml/badge.svg)](https://github.com/netinvent/command_runner/actions/workflows/main.yaml)
[![windows-tests](https://github.com/netinvent/command_runner/actions/workflows/windows.yaml/badge.svg)](https://github.com/netinvent/command_runner/actions/workflows/windows.yaml)
[![GitHub Release](https://img.shields.io/github/release/netinvent/command_runner.svg?label=Latest)](https://github.com/netinvent/command_runner/releases/latest)


command_runner is solution for rapid development that tries to solve various problems a developper may face among:
   - Handling of all possible subprocess.popen / subprocess.check_output scenarios / python versions in one handy function
   - System agnostic functionalty, the developper shouldn't carry the burden of Windows & Linux differences
   - Optional Windows UAC elevation module compatible with CPython, PyInstaller & Nuitka
   - Optional Linux sudo elevation compatible with CPython, PyInstaller & Nuitka

It is compatible with Python 2.7+ (backports some newer Python 3.5 functionality) and is tested on both Linux and Windows.


## command_runner

It works as wrapper for subprocess.popen and subprocess.check_output that solves:
   - Platform differences
   - Python language version differences
      - Handle timeouts even on earlier Python implementations
      - Handle encoding even on earlier Python implementations
   - Promises to always return an exit_code regardless of the execution state (even with timeouts, keboard interruptions)
   - Catch all possible exceptions and log them
   - Allows live stdout output of current execution

   
### command_runner in a nutshell

Install with `pip install command_runner`

The following example will work regardless of the host OS and the Python version.

```
from command_runner import command_runner

exit_code, output = command_runner('ping 127.0.0.1', timeout=30, encoding='utf-8')
```



## UAC Elevation / sudo elevation

command_runner package allowing privilege elevation.
Becomming an admin is fairly easy with command_runner.elevate
You only have to import the elevate module, and then launch your main function with the elevate function.

### elevation In a nutshell

```
from command_runner.elevate import elevate

def main():
    """My main function that should be elevated"""
    print("Who's the administrator, now ?")

if __name__ == '__main__':
    elevate(main)
```

elevate function handles arguments (positional and keyword arguments).
`elevate(main, arg, arg2, kw=somearg)` will call `main(arg, arg2, kw=somearg)`


## Guide

### Setup

`pip install command_runner` or download the latest git release


### Advanced command_runner usage


#### Special exit codes

In order to keep the promise to always provide an exit_code, some arbitrary exit codes have been added for the case where none is given.
Those exit codes are:

- -252 : KeyboardInterrupt
- -253 : FileNotFoundError, OSError, IOError
- -254 : Timeout
- -255 : Any other uncatched exceptions

#### Default encoding

command_runner has an `encoding` argument which defaults to `utf-8` for Unixes and `cp437` for Windows platforms.
Using `cp437` ensures that most `cmd.exe` output is encoded properly, including accents and special characters, on most locale systems.
Still you can specify your own encoding for other usages, like Powershell where `unicode_escape` is preferred.

```
exit_code, output = command_runner(r'C:\Windows\sysnative\WindowsPowerShell\v1.0\powershell.exe --help', encoding='unicode_escape')
```

Earlier subprocess.popen implementations didn't have an encoding setting so command_runner will deal with encoding for those.

#### Timeouts

command_runner as a `timeout` argument which defaults to 1800 seconds.
This default setting ensures commands will not block the main script execution.
Feel free to lower / higher that setting with

```
exit_code, command_runner('ping 127.0.0.1', timeout=30)
```

#### Disabling logs

Whenever you want another loglevel for command_runner, you might do with the following statement in your codeclimate

```
import logging
import command_runner

logging.getLogger('command_runner').setLevel(logging.ERROR)
```

### Advanced elevate usage

#### is_admin() function

The elevate module has a nifty is_admin() function that returns a boolean according to your current root/administrator privileges.
Usage:

```
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
