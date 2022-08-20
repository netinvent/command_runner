#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of command_runner module

"""
command_runner is a quick tool to launch commands from Python, get exit code
and output, and handle most errors that may happen

Versioning semantics:
    Major version: backward compatibility breaking changes
    Minor version: New functionality
    Patch version: Backwards compatible bug fixes

"""
# python 2.7 compat fixes so all strings are considered unicode
from __future__ import unicode_literals


__intname__ = "command_runner"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2015-2022 Orsiris de Jong"
__licence__ = "BSD 3 Clause"
__version__ = "1.4.0"
__build__ = "2022053001"
__compat__ = "python2.7+"

import io
import os
import shlex
import subprocess
import sys
from datetime import datetime
from logging import getLogger
from time import sleep

try:
    import psutil
except ImportError:
    # Don't bother with an error since we need command_runner to work without dependencies
    pass
try:
    import signal
except ImportError:
    pass

# Python 2.7 compat fixes (queue was Queue)
try:
    import queue
except ImportError:
    import Queue as queue
import threading

# Python 2.7 compat fixes (missing typing)
try:
    from typing import Union, Optional, List, Tuple, NoReturn, Any, Callable
except ImportError:
    pass

# Python 2.7 compat fixes (no concurrent futures)
try:
    from concurrent.futures import Future
    from functools import wraps
except ImportError:
    # Python 2.7 just won't have concurrent.futures, so we just declare threaded and wraps in order to
    # avoid NameError
    def threaded(fn):
        return fn

    def wraps(fn):
        return fn


# Python 2.7 compat fixes (no FileNotFoundError class)
try:
    # pylint: disable=E0601 (used-before-assignment)
    FileNotFoundError
except NameError:
    # pylint: disable=W0622 (redefined-builtin)
    FileNotFoundError = IOError

# python <= 3.3 compat fixes (missing TimeoutExpired class)
try:
    TimeoutExpired = subprocess.TimeoutExpired
except AttributeError:

    class TimeoutExpired(BaseException):
        """
        Basic redeclaration when subprocess.TimeoutExpired does not exist, python <= 3.3
        """

        def __init__(self, cmd, timeout, output=None, stderr=None):
            self.cmd = cmd
            self.timeout = timeout
            self.output = output
            self.stderr = stderr

        def __str__(self):
            return "Command '%s' timed out after %s seconds" % (self.cmd, self.timeout)

        @property
        def stdout(self):
            return self.output

        @stdout.setter
        def stdout(self, value):
            # There's no obvious reason to set this, but allow it anyway so
            # .stdout is a transparent alias for .output
            self.output = value


class InterruptGetOutput(BaseException):
    """
    Make sure we get the current output when process is stopped mid-execution
    """

    def __init__(self, output):
        self._output = output

    @property
    def output(self):
        return self._output


class KbdInterruptGetOutput(InterruptGetOutput):
    """
    Make sure we get the current output when KeyboardInterrupt is made
    """

    def __init__(self, output):
        self._output = output

    @property
    def output(self):
        return self._output


class StopOnInterrupt(InterruptGetOutput):
    """
    Make sure we get the current output when optional stop_on function execution returns True
    """

    def __init__(self, output):
        self._output = output

    @property
    def output(self):
        return self._output


### BEGIN DIRECT IMPORT FROM ofunctions.threading
def call_with_future(fn, future, args, kwargs):
    """
    Threading a function with return info using Future
    from https://stackoverflow.com/a/19846691/2635443

    """
    try:
        result = fn(*args, **kwargs)
        future.set_result(result)
    except Exception as exc:
        future.set_exception(exc)


# pylint: disable=E0102 (function-redefined)
def threaded(fn):
    """
    @threaded wrapper in order to thread any function

    @wraps decorator sole purpose is for function.__name__ to be the real function
    instead of 'wrapper'

    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        future = Future()
        threading.Thread(
            target=call_with_future, args=(fn, future, args, kwargs)
        ).start()
        return future

    return wrapper


### END DIRECT IMPORT FROM ofunctions.threading


logger = getLogger(__intname__)
PIPE = subprocess.PIPE


def to_encoding(
    process_output,  # type: Union[str, bytes]
    encoding,  # type: Optional[str]
    errors,  # type: str
):
    # type: (...) -> str
    """
    Convert bytes output to string and handles conversion errors
    Varation of ofunctions.string_handling.safe_string_convert
    """

    if not encoding:
        return process_output

    # Compatibility for earlier Python versions where Popen has no 'encoding' nor 'errors' arguments
    if isinstance(process_output, bytes):
        try:
            process_output = process_output.decode(encoding, errors=errors)
        except TypeError:
            try:
                # handle TypeError: don't know how to handle UnicodeDecodeError in error callback
                process_output = process_output.decode(encoding, errors="ignore")
            except (ValueError, TypeError):
                # What happens when str cannot be concatenated
                logger.debug("Output cannot be captured {}".format(process_output))
    return process_output


def kill_childs_mod(
    pid=None,  # type: int
    itself=False,  # type: bool
    soft_kill=False,  # type: bool
):
    # type: (...) -> bool
    """
    Inline version of ofunctions.kill_childs that has no hard dependency on psutil

    Kills all childs of pid (current pid can be obtained with os.getpid())
    If no pid given current pid is taken
    Good idea when using multiprocessing, is to call with atexit.register(ofunctions.kill_childs, os.getpid(),)

    Beware: MS Windows does not maintain a process tree, so child dependencies are computed on the fly
    Knowing this, orphaned processes (where parent process died) cannot be found and killed this way

    Prefer using process.send_signal() in favor of process.kill() to avoid race conditions when PID was reused too fast

    :param pid: Which pid tree we'll kill
    :param itself: Should parent be killed too ?
    """
    sig = None

    ### BEGIN COMMAND_RUNNER MOD
    if "psutil" not in sys.modules:
        logger.error(
            "No psutil module present. Can only kill direct pids, not child subtree."
        )
    if "signal" not in sys.modules:
        logger.error(
            "No signal module present. Using direct psutil kill API which might have race conditions when PID is reused too fast."
        )
    else:
        """
        Warning: There are only a couple of signals supported on Windows platform

        Extract from signal.valid_signals():

        Windows / Python 3.9-64
        {<Signals.SIGINT: 2>, <Signals.SIGILL: 4>, <Signals.SIGFPE: 8>, <Signals.SIGSEGV: 11>, <Signals.SIGTERM: 15>, <Signals.SIGBREAK: 21>, <Signals.SIGABRT: 22>}

        Linux / Python 3.8-64
        {<Signals.SIGHUP: 1>, <Signals.SIGINT: 2>, <Signals.SIGQUIT: 3>, <Signals.SIGILL: 4>, <Signals.SIGTRAP: 5>, <Signals.SIGABRT: 6>, <Signals.SIGBUS: 7>, <Signals.SIGFPE: 8>, <Signals.SIGKILL: 9>, <Signals.SIGUSR1: 10>, <Signals.SIGSEGV: 11>, <Signals.SIGUSR2: 12>, <Signals.SIGPIPE: 13>, <Signals.SIGALRM: 14>, <Signals.SIGTERM: 15>, 16, <Signals.SIGCHLD: 17>, <Signals.SIGCONT: 18>, <Signals.SIGSTOP: 19>, <Signals.SIGTSTP: 20>, <Signals.SIGTTIN: 21>, <Signals.SIGTTOU: 22>, <Signals.SIGURG: 23>, <Signals.SIGXCPU: 24>, <Signals.SIGXFSZ: 25>, <Signals.SIGVTALRM: 26>, <Signals.SIGPROF: 27>, <Signals.SIGWINCH: 28>, <Signals.SIGIO: 29>, <Signals.SIGPWR: 30>, <Signals.SIGSYS: 31>, <Signals.SIGRTMIN: 34>, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, <Signals.SIGRTMAX: 64>}

        A ValueError will be raised in any other case. Note that not all systems define the same set of signal names;
        an AttributeError will be raised if a signal name is not defined as SIG* module level constant.
        """
        try:
            if not soft_kill and hasattr(signal, "SIGKILL"):
                # Don't bother to make pylint go crazy on Windows
                # pylint: disable=E1101
                sig = signal.SIGKILL
            else:
                sig = signal.SIGTERM
        except NameError:
            sig = None
    ### END COMMAND_RUNNER MOD

    def _process_killer(
        process,  # type: Union[subprocess.Popen, psutil.Process]
        sig,  # type: signal.valid_signals
        soft_kill,  # type: bool
    ):
        # (...) -> None
        """
        Simple abstract process killer that works with signals in order to avoid reused PID race conditions
        and can prefers using terminate than kill
        """
        if sig:
            try:
                process.send_signal(sig)
            # psutil.NoSuchProcess might not be available, let's be broad
            # pylint: disable=W0703
            except Exception:
                pass
        else:
            if soft_kill:
                process.terminate()
            else:
                process.kill()

    try:
        current_process = psutil.Process(pid)
    # psutil.NoSuchProcess might not be available, let's be broad
    # pylint: disable=W0703
    except Exception:
        if itself:
            ### BEGIN COMMAND_RUNNER MOD
            try:
                os.kill(
                    pid, 15
                )  # 15 being signal.SIGTERM or SIGKILL depending on the platform
            except OSError as exc:
                if os.name == "nt":
                    # We'll do an ugly hack since os.kill() has some pretty big caveats on Windows
                    # especially for Python 2.7 where we can get Access Denied
                    os.system("taskkill /F /pid {}".format(pid))
                else:
                    logger.error(
                        "Could not properly kill process with pid {}: {}".format(
                            pid,
                            to_encoding(exc.__str__(), "utf-8", "backslashreplace"),
                        )
                    )
                raise
            ### END COMMAND_RUNNER MOD
        return False
    else:
        for child in current_process.children(recursive=True):
            _process_killer(child, sig, soft_kill)

        if itself:
            _process_killer(current_process, sig, soft_kill)
        return True


def command_runner(
    command,  # type: Union[str, List[str]]
    valid_exit_codes=None,  # type: Optional[List[int]]
    timeout=3600,  # type: Optional[int]
    shell=False,  # type: bool
    encoding=None,  # type: Optional[Union[str, bool]]
    stdout=None,  # type: Optional[Union[int, str, Callable, queue.Queue]]
    stderr=None,  # type: Optional[Union[int, str, Callable, queue.Queue]]
    windows_no_window=False,  # type: bool
    live_output=False,  # type: bool
    method="monitor",  # type: str
    check_interval=0.05,  # type: float
    stop_on=None,  # type: Callable
    process_callback=None,  # type: Callable
    split_streams=False,  # type: bool
    **kwargs  # type: Any
):
    # type: (...) -> Union[Tuple[int, Optional[Union[bytes, str]]], Tuple[int, Optional[Union[bytes, str]], Optional[Union[bytes, str]]]]
    """
    Unix & Windows compatible subprocess wrapper that handles output encoding and timeouts
    Newer Python check_output already handles encoding and timeouts, but this one is retro-compatible
    It is still recommended to set cp437 for windows and utf-8 for unix

    Also allows a list of various valid exit codes (ie no error when exit code = arbitrary int)

    command should be a list of strings, eg ['ping', '-c 2', '127.0.0.1']
    command can also be a single string, ex 'ping -c 2 127.0.0.1' if shell=True or if os is Windows

    Accepts all of subprocess.popen arguments

    Whenever we can, we need to avoid shell=True in order to preserve better security
    Avoiding shell=True involves passing absolute paths to executables since we don't have shell PATH environment

    When no stdout option is given, we'll get output into the returned (exit_code, output) tuple
    When stdout = filename or stderr = filename, we'll write output to the given file

    live_output will poll the process for output and show it on screen (output may be non reliable, don't use it if
    your program depends on the commands' stdout output)

    windows_no_window will disable visible window (MS Windows platform only)

    stop_on is an optional function that will stop execution if function returns True

    Returns a tuple (exit_code, output)
    """

    # Choose default encoding when none set
    # cp437 encoding assures we catch most special characters from cmd.exe
    # Unless encoding=False in which case nothing gets encoded except Exceptions and logger strings for Python 2
    error_encoding = "cp437" if os.name == "nt" else "utf-8"
    if encoding is not False:
        encoding = error_encoding

    # Fix when unix command was given as single string
    # This is more secure than setting shell=True
    if os.name == "posix":
        if not shell and isinstance(command, str):
            command = shlex.split(command)
        elif shell and isinstance(command, list):
            command = " ".join(command)

    # Set default values for kwargs
    errors = kwargs.pop(
        "errors", "backslashreplace"
    )  # Don't let encoding issues make you mad
    universal_newlines = kwargs.pop("universal_newlines", False)
    creationflags = kwargs.pop("creationflags", 0)
    # subprocess.CREATE_NO_WINDOW was added in Python 3.7 for Windows OS only
    if (
        windows_no_window
        and sys.version_info[0] >= 3
        and sys.version_info[1] >= 7
        and os.name == "nt"
    ):
        # Disable the following pylint error since the code also runs on nt platform, but
        # triggers an error on Unix
        # pylint: disable=E1101
        creationflags = creationflags | subprocess.CREATE_NO_WINDOW
    close_fds = kwargs.pop("close_fds", "posix" in sys.builtin_module_names)

    # Default buffer size. line buffer (1) is deprecated in Python 3.7+
    bufsize = kwargs.pop("bufsize", 16384)

    # Decide whether we write to output variable only (stdout=None), to output variable and stdout (stdout=PIPE)
    # or to output variable and to file (stdout='path/to/file')
    if stdout is None:
        _stdout = PIPE
        stdout_destination = "pipe"
    elif callable(stdout):
        _stdout = PIPE
        stdout_destination = "callback"
    elif isinstance(stdout, queue.Queue):
        _stdout = PIPE
        stdout_destination = "queue"
    elif isinstance(stdout, str):
        # We will send anything to file
        _stdout = open(stdout, "wb")
        stdout_destination = "file"
    elif stdout is False:
        # Python 2.7 does not have subprocess.DEVNULL, hence we need to use a file descriptor
        try:
            _stdout = subprocess.DEVNULL
        except AttributeError:
            _stdout = PIPE
        stdout_destination = None
    else:
        # We will send anything to given stdout pipe
        _stdout = stdout
        stdout_destination = "pipe"

    # The only situation where we don't add stderr to stdout is if a specific target file was given
    if callable(stderr):
        _stderr = PIPE
        stderr_destination = "callback"
    elif isinstance(stderr, queue.Queue):
        _stderr = PIPE
        stderr_destination = "queue"
    elif isinstance(stderr, str):
        _stderr = open(stderr, "wb")
        stderr_destination = "file"
    elif stderr is False:
        try:
            _stderr = subprocess.DEVNULL
        except AttributeError:
            _stderr = PIPE
        stderr_destination = None
    elif stderr is not None:
        _stderr = stderr
        stderr_destination = "pipe"
    # Automagically add a pipe so we are sure not to redirect to stdout
    elif split_streams:
        _stderr = PIPE
        stderr_destination = "pipe"
    else:
        _stderr = subprocess.STDOUT
        stderr_destination = "stdout"

    def _read_pipe(
        stream,  # type: io.StringIO
        output_queue,  # type: queue.Queue
    ):
        # type: (...) -> None
        """
        will read from subprocess.PIPE
        Must be threaded since readline() might be blocking on Windows GUI apps

        Partly based on https://stackoverflow.com/a/4896288/2635443
        """

        # WARNING: Depending on the stream type (binary or text), the sentinel character
        # needs to be of the same type, or the iterator won't have an end

        # We also need to check that stream has readline, in case we're writing to files instead of PIPE

        # Another magnificient python 2.7 fix
        # So we need to convert sentinel_char which would be unicode because of unicode_litterals
        # to str which is the output format from stream.readline()

        if hasattr(stream, "readline"):
            sentinel_char = str("") if hasattr(stream, "encoding") else b""
            for line in iter(stream.readline, sentinel_char):
                output_queue.put(line)
            output_queue.put(None)
            stream.close()

    def _get_error_output(output_stdout, output_stderr):
        """
        Try to concatenate output for exceptions if possible
        """
        try:
            return output_stdout + output_stderr
        except TypeError:
            if output_stdout:
                return output_stdout
            if output_stderr:
                return output_stderr
            return None

    def _poll_process(
        process,  # type: Union[subprocess.Popen[str], subprocess.Popen]
        timeout,  # type: int
        encoding,  # type: str
        errors,  # type: str
    ):
        # type: (...) -> Union[Tuple[int, Optional[str]], Tuple[int, Optional[str], Optional[str]]]
        """
        Process stdout/stderr output polling is only used in live output mode
        since it takes more resources than using communicate()

        Reads from process output pipe until:
        - Timeout is reached, in which case we'll terminate the process
        - Process ends by itself

        Returns an encoded string of the pipe output
        """

        def __check_timeout(
            begin_time,  # type: datetime.timestamp
            timeout,  # type: int
        ):
            # type: (...) -> None
            """
            Simple subfunction to check whether timeout is reached
            Since we check this alot, we put it into a function
            """

            if timeout and (datetime.now() - begin_time).total_seconds() > timeout:
                kill_childs_mod(process.pid, itself=True, soft_kill=False)
                raise TimeoutExpired(
                    process, timeout, _get_error_output(output_stdout, output_stderr)
                )
            if stop_on and stop_on():
                kill_childs_mod(process.pid, itself=True, soft_kill=False)
                raise StopOnInterrupt(_get_error_output(output_stdout, output_stderr))

        begin_time = datetime.now()
        if encoding is False:
            output_stdout = output_stderr = b""
        else:
            output_stdout = output_stderr = ""

        try:
            if stdout_destination is not None:
                stdout_read_queue = True
                stdout_queue = queue.Queue()
                stdout_read_thread = threading.Thread(
                    target=_read_pipe, args=(process.stdout, stdout_queue)
                )
                stdout_read_thread.daemon = True  # thread dies with the program
                stdout_read_thread.start()
            else:
                stdout_read_queue = False

            # Don't bother to read stderr if we redirect to stdout
            if stderr_destination not in ["stdout", None]:
                stderr_read_queue = True
                stderr_queue = queue.Queue()
                stderr_read_thread = threading.Thread(
                    target=_read_pipe, args=(process.stderr, stderr_queue)
                )
                stderr_read_thread.daemon = True  # thread dies with the program
                stderr_read_thread.start()
            else:
                stderr_read_queue = False

            while stdout_read_queue or stderr_read_queue:
                if stdout_read_queue:
                    try:
                        line = stdout_queue.get(timeout=check_interval)
                    except queue.Empty:
                        pass
                    else:
                        if line is None:
                            stdout_read_queue = False
                        else:
                            line = to_encoding(line, encoding, errors)
                            if stdout_destination == "callback":
                                stdout(line)
                            if stdout_destination == "queue":
                                stdout.put(line)
                            if live_output:
                                sys.stdout.write(line)
                            output_stdout += line

                if stderr_read_queue:
                    try:
                        line = stderr_queue.get(timeout=check_interval)
                    except queue.Empty:
                        pass
                    else:
                        if line is None:
                            stderr_read_queue = False
                        else:
                            line = to_encoding(line, encoding, errors)
                            if stderr_destination == "callback":
                                stderr(line)
                            if stderr_destination == "queue":
                                stderr.put(line)
                            if live_output:
                                sys.stderr.write(line)
                            if split_streams:
                                output_stderr += line
                            else:
                                output_stdout += line

                __check_timeout(begin_time, timeout)

            # Make sure we wait for the process to terminate, even after
            # output_queue has finished sending data, so we catch the exit code
            while process.poll() is None:
                __check_timeout(begin_time, timeout)
            # Additional timeout check to make sure we don't return an exit code from processes
            # that were killed because of timeout
            __check_timeout(begin_time, timeout)
            exit_code = process.poll()
            if split_streams:
                return exit_code, output_stdout, output_stderr
            else:
                return exit_code, output_stdout

        except KeyboardInterrupt:
            raise KbdInterruptGetOutput(_get_error_output(output_stdout, output_stderr))

    def _timeout_check_thread(
        process,  # type: Union[subprocess.Popen[str], subprocess.Popen]
        timeout,  # type: int
        must_stop,  # type dict
    ):
        # type: (...) -> None

        """
        Since elder python versions don't have timeout, we need to manually check the timeout for a process
        when working in process monitor mode
        """

        begin_time = datetime.now()
        while True:
            if timeout and (datetime.now() - begin_time).total_seconds() > timeout:
                kill_childs_mod(process.pid, itself=True, soft_kill=False)
                must_stop["value"] = "T"  # T stands for TIMEOUT REACHED
                break
            if stop_on and stop_on():
                kill_childs_mod(process.pid, itself=True, soft_kill=False)
                must_stop["value"] = "S"  # S stands for STOP_ON RETURNED TRUE
                break
            if process.poll() is not None:
                break
            # We definitly need some sleep time here or else we will overload CPU
            sleep(check_interval)

    def _monitor_process(
        process,  # type: Union[subprocess.Popen[str], subprocess.Popen]
        timeout,  # type: int
        encoding,  # type: str
        errors,  # type: str
    ):
        # type: (...) -> Union[Tuple[int, Optional[str]], Tuple[int, Optional[str], Optional[str]]]
        """
        Create a thread in order to enforce timeout or a stop_on condition
        Get stdout output and return it
        """

        # Shared mutable objects have proven to have race conditions with PyPy 3.7 (mutable object
        # is changed in thread, but outer monitor function has still old mutable object state)
        # Strangely, this happened only sometimes on github actions/ubuntu 20.04.3 & pypy 3.7
        # Just make sure the thread is done before using mutable object
        must_stop = {"value": False}

        thread = threading.Thread(
            target=_timeout_check_thread,
            args=(process, timeout, must_stop),
        )
        thread.daemon = True  # was setDaemon(True) which has been deprecated
        thread.start()

        if encoding is False:
            output_stdout = output_stderr = b""
            output_stdout_end = output_stderr_end = b""
        else:
            output_stdout = output_stderr = ""
            output_stdout_end = output_stderr_end = ""

        try:
            # Don't use process.wait() since it may deadlock on old Python versions
            # Also it won't allow communicate() to get incomplete output on timeouts
            while process.poll() is None:
                if must_stop["value"]:
                    break
                # We still need to use process.communicate() in this loop so we don't get stuck
                # with poll() is not None even after process is finished, when using shell=True
                # Behavior validated on python 3.7
                try:
                    output_stdout, output_stderr = process.communicate()
                # ValueError is raised on closed IO file
                except (TimeoutExpired, ValueError):
                    pass
            exit_code = process.poll()

            try:
                output_stdout_end, output_stderr_end = process.communicate()
            except (TimeoutExpired, ValueError):
                pass

            # Fix python 2.7 first process.communicate() call will have output whereas other python versions
            # will give output in second process.communicate() call
            if output_stdout_end and len(output_stdout_end) > 0:
                output_stdout = output_stdout_end
            if output_stderr_end and len(output_stderr_end) > 0:
                output_stderr = output_stderr_end

            if split_streams:
                if stdout_destination is not None:
                    output_stdout = to_encoding(output_stdout, encoding, errors)
                if stderr_destination is not None:
                    output_stderr = to_encoding(output_stderr, encoding, errors)
            else:
                if stdout_destination is not None:
                    output_stdout = to_encoding(output_stdout, encoding, errors)

            # On PyPy 3.7 only, we can have a race condition where we try to read the queue before
            # the thread could write to it, failing to register a timeout.
            # This workaround prevents reading the mutable object while the thread is still alive
            while thread.is_alive():
                sleep(check_interval)

            if must_stop["value"] == "T":
                raise TimeoutExpired(
                    process, timeout, _get_error_output(output_stdout, output_stderr)
                )
            elif must_stop["value"] == "S":
                raise StopOnInterrupt(_get_error_output(output_stdout, output_stderr))
            if split_streams:
                return exit_code, output_stdout, output_stderr
            else:
                return exit_code, output_stdout
        except KeyboardInterrupt:
            raise KbdInterruptGetOutput(_get_error_output(output_stdout, output_stderr))

    # After all the stuff above, here's finally the function main entry point
    output_stdout = output_stderr = None

    try:
        # Don't allow monitor method when stdout or stderr is callback/queue redirection (makes no sense)
        if method == "monitor" and (
            stdout_destination
            in [
                "callback",
                "queue",
            ]
            or stderr_destination in ["callback", "queue"]
        ):
            raise ValueError(
                'Cannot use callback or queue destination in monitor mode. Please use method="poller" argument.'
            )

        # Finally, we won't use encoding & errors arguments for Popen
        # since it would defeat the idea of binary pipe reading in live mode

        # Python >= 3.3 has SubProcessError(TimeoutExpired) class
        # Python >= 3.6 has encoding & error arguments
        # universal_newlines=True makes netstat command fail under windows
        # timeout does not work under Python 2.7 with subprocess32 < 3.5
        # decoder may be cp437 or unicode_escape for dos commands or utf-8 for powershell
        # Disabling pylint error for the same reason as above
        # pylint: disable=E1123
        if sys.version_info >= (3, 6):
            process = subprocess.Popen(
                command,
                stdout=_stdout,
                stderr=_stderr,
                shell=shell,
                universal_newlines=universal_newlines,
                encoding=encoding if encoding is not False else None,
                errors=errors if encoding is not False else None,
                creationflags=creationflags,
                bufsize=bufsize,  # 1 = line buffered
                close_fds=close_fds,
                **kwargs
            )
        else:
            process = subprocess.Popen(
                command,
                stdout=_stdout,
                stderr=_stderr,
                shell=shell,
                universal_newlines=universal_newlines,
                creationflags=creationflags,
                bufsize=bufsize,
                close_fds=close_fds,
                **kwargs
            )

        try:
            # let's return process information if callback was given
            if callable(process_callback):
                process_callback(process)
            if method == "poller" or live_output and _stdout is not False:
                if split_streams:
                    exit_code, output_stdout, output_stderr = _poll_process(
                        process, timeout, encoding, errors
                    )
                else:
                    exit_code, output_stdout = _poll_process(
                        process, timeout, encoding, errors
                    )
            elif method == "monitor":
                if split_streams:
                    exit_code, output_stdout, output_stderr = _monitor_process(
                        process, timeout, encoding, errors
                    )
                else:
                    exit_code, output_stdout = _monitor_process(
                        process, timeout, encoding, errors
                    )
            else:
                raise ValueError("Unknown method {} provided.".format(method))
        except KbdInterruptGetOutput as exc:
            exit_code = -252
            output_stdout = "KeyboardInterrupted. Partial output\n{}".format(exc.output)
            try:
                kill_childs_mod(process.pid, itself=True, soft_kill=False)
            except AttributeError:
                pass
            if stdout_destination == "file" and output_stdout:
                _stdout.write(output_stdout.encode(encoding, errors=errors))
            if stderr_destination == "file" and output_stderr:
                _stderr.write(output_stderr.encode(encoding, errors=errors))
            elif stdout_destination == "file" and output_stderr:
                _stdout.write(output_stderr.encode(encoding, errors=errors))

        logger.debug(
            'Command "{}" returned with exit code "{}". Command output was:'.format(
                command, exit_code
            )
        )
    except subprocess.CalledProcessError as exc:
        exit_code = exc.returncode
        try:
            output_stdout = exc.output
        except AttributeError:
            output_stdout = "command_runner: Could not obtain output from command."
        if exit_code in valid_exit_codes if valid_exit_codes is not None else [0]:
            logger.debug(
                'Command "{}" returned with exit code "{}". Command output was:'.format(
                    command, exit_code
                )
            )
        logger.error(
            'Command "{}" failed with exit code "{}". Command output was:'.format(
                command, exc.returncode
            )
        )
        logger.error(output_stdout)
    except FileNotFoundError as exc:
        message = 'Command "{}" failed, file not found: {}'.format(
            command, to_encoding(exc.__str__(), error_encoding, errors)
        )
        logger.error(message)
        if stdout_destination == "file":
            _stdout.write(message.encode(error_encoding, errors=errors))
        exit_code, output_stdout = (-253, message)
    # On python 2.7, OSError is also raised when file is not found (no FileNotFoundError)
    # pylint: disable=W0705 (duplicate-except)
    except (OSError, IOError) as exc:
        message = 'Command "{}" failed because of OS: {}'.format(
            command, to_encoding(exc.__str__(), error_encoding, errors)
        )
        logger.error(message)
        if stdout_destination == "file":
            _stdout.write(message.encode(error_encoding, errors=errors))
        exit_code, output_stdout = (-253, message)
    except TimeoutExpired as exc:
        message = 'Timeout {} seconds expired for command "{}" execution. Original output was: {}'.format(
            timeout, command, exc.output
        )
        logger.error(message)
        if stdout_destination == "file":
            _stdout.write(message.encode(error_encoding, errors=errors))
        exit_code, output_stdout = (-254, message)
    except StopOnInterrupt as exc:
        message = "Command {} was stopped because stop_on function returned True. Original output was: {}".format(
            command, to_encoding(exc.output, error_encoding, errors)
        )
        logger.info(message)
        if stdout_destination == "file":
            _stdout.write(message.encode(error_encoding, errors=errors))
        exit_code, output_stdout = (-251, message)
    except ValueError as exc:
        message = to_encoding(exc.__str__(), error_encoding, errors)
        logger.error(message, exc_info=True)
        if stdout_destination == "file":
            _stdout.write(message)
        exit_code, output_stdout = (-250, message)
    # We need to be able to catch a broad exception
    # pylint: disable=W0703
    except Exception as exc:
        logger.error(
            'Command "{}" failed for unknown reasons: {}'.format(
                command, to_encoding(exc.__str__(), error_encoding, errors)
            ),
            exc_info=True,
        )
        exit_code, output_stdout = (
            -255,
            to_encoding(exc.__str__(), error_encoding, errors),
        )
    finally:
        if stdout_destination == "file":
            _stdout.close()
        if stderr_destination == "file":
            _stderr.close()

    logger.debug(
        "STDOUT: " + to_encoding(output_stdout, error_encoding, errors)
        if output_stdout
        else "None"
    )
    if stderr_destination not in ["stdout", None]:
        logger.debug(
            "STDERR: " + to_encoding(output_stderr, error_encoding, errors)
            if output_stderr
            else "None"
        )

    # Make sure we send a simple queue end before leaving to make any queue read process will stop regardless
    # of command_runner state (useful when launching with queue and method poller which isn't supposed to write queues)
    if stdout_destination == "queue":
        stdout.put(None)
    if stderr_destination == "queue":
        stderr.put(None)

    # With polling, we return None if nothing has been send to the queues
    # With monitor, process.communicate() will result in '' even if nothing has been sent
    # Let's fix this here
    # Python 2.7 will return False to u'' == '' (UnicodeWarning: Unicode equal comparison failed)
    # so we have to make the following statement
    if stdout_destination is None or (
        output_stdout is not None and len(output_stdout) == 0
    ):
        output_stdout = None
    if stderr_destination is None or (
        output_stderr is not None and len(output_stderr) == 0
    ):
        output_stderr = None

    if split_streams:
        return exit_code, output_stdout, output_stderr
    else:
        return exit_code, _get_error_output(output_stdout, output_stderr)


if sys.version_info[0] >= 3:

    @threaded
    def command_runner_threaded(*args, **kwargs):
        """
        Threaded version of command_runner_threaded which returns concurrent.Future result
        Not available for Python 2.7
        """
        return command_runner(*args, **kwargs)


def deferred_command(command, defer_time=300):
    # type: (str, int) -> None
    """
    This is basically an ugly hack to launch commands which are detached from parent process
    Especially useful to launch an auto update/deletion of a running executable after a given amount of
    seconds after it finished
    """
    # Use ping as a standard timer in shell since it's present on virtually *any* system
    if os.name == "nt":
        deferrer = "ping 127.0.0.1 -n {} > NUL & ".format(defer_time)
    else:
        deferrer = "ping 127.0.0.1 -c {} > /dev/null && ".format(defer_time)

    # We'll create a independent shell process that will not be attached to any stdio interface
    # Our command shall be a single string since shell=True
    subprocess.Popen(
        deferrer + command,
        shell=True,
        stdin=None,
        stdout=None,
        stderr=None,
        close_fds=True,
    )
