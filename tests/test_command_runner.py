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

__intname__ = "command_runner_tests"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2015-2025 Orsiris de Jong"
__licence__ = "BSD 3 Clause"
__build__ = "2025041801"


import sys
import os
import platform
import re
import threading
import logging
import collections

try:
    from command_runner import *
except ImportError:  # would be ModuleNotFoundError in Python 3+
    # In case we run tests without actually having installed command_runner
    sys.path.insert(0, os.path.abspath(os.path.join(__file__, os.pardir, os.pardir)))
    from command_runner import *

# Python 2.7 compat where datetime.now() does not have .timestamp() method
if sys.version_info[0] < 3 or sys.version_info[1] < 4:
    # python version < 3.3
    import time

    def timestamp(date):
        return time.mktime(date.timetuple())

else:

    def timestamp(date):
        return date.timestamp()


# We need a logging unit here
logger = logging.getLogger()
logger.setLevel(logging.WARNING)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

streams = ["stdout", "stderr"]
methods = ["monitor", "poller"]

TEST_FILENAME = "README.md"
if os.name == "nt":
    ENCODING = "cp437"
    PING_CMD = "ping 127.0.0.1 -n 4"
    PING_CMD_10S = "ping 127.0.0.1 -n 10"
    PING_CMD_REDIR = PING_CMD + " 1>&2"
    # Make sure we run the failure command first so end result is okay
    PING_CMD_AND_FAILURE = "ping 0.0.0.0 -n 2 1>&2 & ping 127.0.0.1 -n 2"
    PING_FAILURE = "ping 0.0.0.0 -n 2 1>&2"

    PRINT_FILE_CMD = "type {}".format(TEST_FILENAME)
else:
    ENCODING = "utf-8"
    PING_CMD = ["ping", "-c", "4", "127.0.0.1"]
    PING_CMD_10S = ["ping", "-c", "10", "127.0.0.1"]
    PING_CMD_REDIR = "ping -c 4 127.0.0.1 1>&2"
    PING_CMD_AND_FAILURE = "ping -c 2 0.0.0.0 1>&2; ping -c 2 127.0.0.1"
    PRINT_FILE_CMD = "cat {}".format(TEST_FILENAME)
    PING_FAILURE = "ping -c 2 0.0.0.0 1>&2"


ELAPSED_TIME = timestamp(datetime.now())
PROCESS_ID = None
STREAM_OUTPUT = ""
PROC = None
ON_EXIT_CALLED = False


def reset_elapsed_time():
    global ELAPSED_TIME
    ELAPSED_TIME = timestamp(datetime.now())


def get_elapsed_time():
    return timestamp(datetime.now()) - ELAPSED_TIME


def running_on_github_actions():
    """
    This is set in github actions workflow with
          env:
        RUNNING_ON_GITHUB_ACTIONS: true
    """
    return os.environ.get("RUNNING_ON_GITHUB_ACTIONS") == "true"  # bash 'true'


def is_pypy():
    """
    Checks interpreter
    """
    return True if platform.python_implementation().lower() == "pypy" else False


def is_macos():
    """
    Checks if under Mac OS
    """
    return platform.system().lower() == "darwin"


def test_standard_ping_with_encoding():
    """
    Test command_runner with a standard ping and encoding parameter
    """
    for method in methods:
        print("method={}".format(method))
        exit_code, output = command_runner(PING_CMD, encoding=ENCODING, method=method)
        print(output)
        assert (
            exit_code == 0
        ), "Exit code should be 0 for ping command with method {}".format(method)


def test_standard_ping_with_default_encoding():
    """
    Without encoding, iter(stream.readline, '') will hang since the expected sentinel char would be b'':
    This could only happen on python <3.6 since command_runner decides to use an encoding anyway
    """
    for method in methods:
        exit_code, output = command_runner(PING_CMD, encoding=None, method=method)
        print(output)
        assert (
            exit_code == 0
        ), "Exit code should be 0 for ping command with method {}".format(method)


def test_standard_ping_with_encoding_disabled():
    """
    Without encoding disabled, we should have binary output
    """
    for method in methods:
        exit_code, output = command_runner(PING_CMD, encoding=False, method=method)
        print(output)
        assert (
            exit_code == 0
        ), "Exit code should be 0 for ping command with method {}".format(method)
        assert isinstance(output, bytes), "Output should be binary."


def test_timeout():
    """
    Test command_runner with a timeout
    """
    for method in methods:
        begin_time = datetime.now()
        exit_code, output = command_runner(PING_CMD, timeout=1, method=method)
        print(output)
        end_time = datetime.now()
        assert (
            end_time - begin_time
        ).total_seconds() < 2, "It took more than 2 seconds for a timeout=1 command to finish with method {}".format(
            method
        )
        assert (
            exit_code == -254
        ), "Exit code should be -254 on timeout with method {}".format(method)
        assert "Timeout" in output, "Output should have timeout with method {}".format(
            method
        )


def test_timeout_with_subtree_killing():
    """
    Launch a subtree of long commands and see if timeout actually kills them in time
    """
    if os.name != "nt":
        cmd = 'echo "test" && sleep 5 && echo "done"'
    else:
        cmd = "echo test && {} && echo done".format(PING_CMD)

    for method in methods:
        begin_time = datetime.now()
        exit_code, output = command_runner(cmd, shell=True, timeout=1, method=method)
        print(output)
        end_time = datetime.now()
        elapsed_time = (end_time - begin_time).total_seconds()
        assert (
            elapsed_time < 4
        ), "It took more than 2 seconds for a timeout=1 command to finish with method {}".format(
            method
        )
        assert (
            exit_code == -254
        ), "Exit code should be -254 on timeout with method {}".format(method)
        assert "Timeout" in output, "Output should have timeout with method {}".format(
            method
        )


def test_no_timeout():
    """
    Test with setting timeout=None
    """
    for method in methods:
        exit_code, output = command_runner(PING_CMD, timeout=None, method=method)
        print(output)
        assert (
            exit_code == 0
        ), "Without timeout, command should have run with method {}".format(method)


def test_live_output():
    """
    Test command_runner with live output to stdout
    """
    for method in methods:
        exit_code, _ = command_runner(
            PING_CMD, stdout=PIPE, encoding=ENCODING, method=method
        )
        assert (
            exit_code == 0
        ), "Exit code should be 0 for ping command with method {}".format(method)


def test_not_found():
    """
    Test command_runner with an unexisting command
    """
    for method in methods:
        print("The following command should fail with method {}".format(method))
        exit_code, output = command_runner("unknown_command_nowhere_to_be_found_1234")
        assert (
            exit_code == -253
        ), "Unknown command should trigger a -253 exit code with method {}".format(
            method
        )
        assert "failed" in output, "Error code -253 should be Command x failed, reason"


def test_file_output():
    """
    Test command_runner with file output instead of stdout
    """
    for method in methods:
        stdout_filename = "temp.test"
        stderr_filename = "temp.test.err"
        print("The following command should timeout")
        exit_code, output = command_runner(
            PING_CMD,
            timeout=1,
            stdout=stdout_filename,
            stderr=stderr_filename,
            method=method,
        )
        assert os.path.isfile(
            stdout_filename
        ), "Log file does not exist with method {}".format(method)

        # We don't have encoding argument in Python 2, yet we need it for PyPy
        if sys.version_info[0] < 3:
            with open(stdout_filename, "r") as file_handle:
                output = file_handle.read()
        else:
            with open(stdout_filename, "r", encoding=ENCODING) as file_handle:
                output = file_handle.read()

        assert os.path.isfile(
            stderr_filename
        ), "stderr log file does not exist with method {}".format(method)
        assert (
            exit_code == -254
        ), "Exit code should be -254 for timeouts with method {}".format(method)
        assert "Timeout" in output, "Output should have timeout with method {}".format(
            method
        )

        # arbitrary time to make sure file handle was closed
        sleep(3)
        os.remove(stdout_filename)
        os.remove(stderr_filename)


def test_valid_exit_codes():
    """
    Test command_runner with a failed ping but that should not trigger an error

    # WIP We could improve tests here by capturing logs
    """
    valid_exit_codes = [0, 1, 2]
    if is_macos():
        valid_exit_codes.append(68)  # ping non-existent exits with such on Mac
    for method in methods:

        exit_code, _ = command_runner(
            "ping nonexistent_host",
            shell=True,
            valid_exit_codes=valid_exit_codes,
            method=method,
        )
        assert (
            exit_code in valid_exit_codes
        ), "Exit code not in valid list with method {}".format(method)

        exit_code, _ = command_runner(
            "ping nonexistent_host", shell=True, valid_exit_codes=True, method=method
        )
        assert exit_code != 0, "Exit code should not be equal to 0"

        exit_code, _ = command_runner(
            "ping nonexistent_host", shell=True, valid_exit_codes=False, method=method
        )
        assert exit_code != 0, "Exit code should not be equal to 0"

        exit_code, _ = command_runner(
            "ping nonexistent_host", shell=True, valid_exit_codes=None, method=method
        )
        assert exit_code != 0, "Exit code should not be equal to 0"


def test_unix_only_split_command():
    """
    This test is specifically written when command_runner receives a str command instead of a list on unix
    """
    if os.name == "posix":
        for method in methods:
            exit_code, _ = command_runner(" ".join(PING_CMD), method=method)
            assert (
                exit_code == 0
            ), "Non split command should not trigger an error with method {}".format(
                method
            )


def test_create_no_window():
    """
    Only used on windows, when we don't want to create a cmd visible windows
    """
    for method in methods:
        exit_code, _ = command_runner(PING_CMD, windows_no_window=True, method=method)
        assert exit_code == 0, "Should have worked too with method {}".format(method)


def test_read_file():
    """
    Read a couple of times the same file to be sure we don't get garbage from _read_pipe()
    This is a random failure detection test
    """

    # We don't have encoding argument in Python 2, yet we need it for PyPy
    if sys.version_info[0] < 3:
        with open(TEST_FILENAME, "r") as file:
            file_content = file.read()
    else:
        with open(TEST_FILENAME, "r", encoding=ENCODING) as file:
            file_content = file.read()
    for method in methods:
        # pypy is quite slow with poller method on github actions.
        # Lets lower rounds
        max_rounds = 100 if is_pypy() else 1000
        print("\nSetting up test_read_file for {} rounds".format(max_rounds))
        for round in range(0, max_rounds):
            print("Comparison round {} with method {}".format(round, method))
            exit_code, output = command_runner(
                PRINT_FILE_CMD, shell=True, method=method
            )
            if os.name == "nt":
                output = output.replace("\r\n", "\n")

            assert (
                exit_code == 0
            ), "Did not succeed to read {}, method={}, exit_code: {}, output: {}".format(
                TEST_FILENAME, method, exit_code, output
            )
            assert (
                file_content == output
            ), "Round {} File content and output are not identical, method={}".format(
                round, method
            )


def test_stop_on_argument():
    expected_output_regex = "Command .* was stopped because stop_on function returned True. Original output was:"

    def stop_on():
        """
        Simple function that returns True two seconds after reset_elapsed_time() has been called
        """
        if get_elapsed_time() > 2:
            return True

    for method in methods:
        reset_elapsed_time()
        print("method={}".format(method))
        exit_code, output = command_runner(PING_CMD, stop_on=stop_on, method=method)

        # On github actions only with Python 2.7.18, we sometimes get -251 failed because of OS: [Error 5] Access is denied
        # when os.kill(pid) is called in kill_childs_mod
        # On my windows platform using the same Python version, it works...
        # well nothing I can debug on github actions
        if running_on_github_actions() and os.name == "nt" and sys.version_info[0] < 3:
            assert exit_code in [
                -253,
                -251,
            ], "Not as expected, we should get a permission error on github actions windows platform"
        else:
            assert (
                exit_code == -251
            ), "Monitor mode should have been stopped by stop_on with exit_code -251. method={}, exit_code: {}, output: {}".format(
                method, exit_code, output
            )
            assert (
                re.match(expected_output_regex, output, re.MULTILINE) is not None
            ), "stop_on output is bogus. method={}, exit_code: {}, output: {}".format(
                method, exit_code, output
            )


def test_process_callback():
    def callback(process_id):
        global PROCESS_ID
        PROCESS_ID = process_id

    for method in methods:
        exit_code, output = command_runner(
            PING_CMD, method=method, process_callback=callback
        )
        assert (
            exit_code == 0
        ), "Wrong exit code. method={}, exit_code: {}, output: {}".format(
            method, exit_code, output
        )
        assert isinstance(
            PROCESS_ID, subprocess.Popen
        ), 'callback did not work properly. PROCESS_ID="{}"'.format(PROCESS_ID)


def test_stream_callback():
    global STREAM_OUTPUT

    def stream_callback(string):
        global STREAM_OUTPUT
        STREAM_OUTPUT += string
        print("CALLBACK: ", string)

    for stream in streams:
        stream_args = {stream: stream_callback}
        for method in methods:
            STREAM_OUTPUT = ""
            try:
                print("Method={}, stream={}, output=callback".format(method, stream))
                exit_code, output = command_runner(
                    PING_CMD_REDIR, shell=True, method=method, **stream_args
                )
            except ValueError:
                if method == "poller":
                    assert False, "ValueError should not be produced in poller mode."
            if method == "poller":
                assert (
                    exit_code == 0
                ), "Wrong exit code. method={}, exit_code: {}, output: {}".format(
                    method, exit_code, output
                )

                # Since we redirect STDOUT to STDERR
                assert (
                    STREAM_OUTPUT == output
                ), "Callback stream should contain same result as output"
            else:
                assert (
                    exit_code == -250
                ), "stream_callback exit_code is bogus. method={}, exit_code: {}, output: {}".format(
                    method, exit_code, output
                )


def test_queue_output():
    """
    Thread command runner and get it's output queue
    """

    if sys.version_info[0] < 3:
        print("Queue test uses concurrent futures. Won't run on python 2.7, sorry.")
        return

    # pypy is quite slow with poller method on github actions.
    # Lets lower rounds
    max_rounds = 100 if is_pypy() else 1000
    print("\nSetting up test_read_file for {} rounds".format(max_rounds))
    for i in range(0, max_rounds):
        for stream in streams:
            for method in methods:
                if method == "monitor" and i > 1:
                    # Dont bother to repeat the test for monitor mode more than once
                    continue
                output_queue = queue.Queue()
                stream_output = ""
                stream_args = {stream: output_queue}
                print(
                    "Round={}, Method={}, stream={}, output=queue".format(
                        i, method, stream
                    )
                )
                thread_result = command_runner_threaded(
                    PRINT_FILE_CMD, shell=True, method=method, **stream_args
                )

                read_queue = True
                while read_queue:
                    try:
                        line = output_queue.get(timeout=0.1)
                    except queue.Empty:
                        pass
                    else:
                        if line is None:
                            break
                        else:
                            stream_output += line

                exit_code, output = thread_result.result()

                if method == "poller":
                    assert (
                        exit_code == 0
                    ), "Wrong exit code. method={}, exit_code: {}, output: {}".format(
                        method, exit_code, output
                    )
                    # Since we redirect STDOUT to STDERR
                    if stream == "stdout":
                        assert (
                            stream_output == output
                        ), "stdout queue output should contain same result as output"
                    if stream == "stderr":
                        assert (
                            len(stream_output) == 0
                        ), "stderr queue output should be empty"
                else:
                    assert (
                        exit_code == -250
                    ), "stream_queue exit_code is bogus. method={}, exit_code: {}, output: {}".format(
                        method, exit_code, output
                    )


def test_queue_non_threaded_command_runner():
    """
    Test case for Python 2.7 without proper threading return values
    """

    def read_queue(output_queue, stream_output):
        """
        Read the queue as thread
        Our problem here is that the thread can live forever if we don't check a global value, which is...well ugly
        """
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
                    stream_output["value"] += line
                    # ADD YOUR LIVE CODE HERE
        return stream_output

    for i in range(0, 20):
        for cmd in [PING_CMD, PRINT_FILE_CMD]:
            if cmd == PRINT_FILE_CMD:
                shell_args = {"shell": True}
            else:
                shell_args = {"shell": False}
            # Create a new queue that command_runner will fill up
            output_queue = queue.Queue()
            stream_output = {"value": ""}
            # Create a thread of read_queue() in order to read the queue while command_runner executes the command
            read_thread = threading.Thread(
                target=read_queue, args=(output_queue, stream_output)
            )
            read_thread.daemon = True  # thread dies with the program
            read_thread.start()

            # Launch command_runner
            print("Round={}, cmd={}".format(i, cmd))
            exit_code, output = command_runner(
                cmd, stdout=output_queue, method="poller", **shell_args
            )
            assert (
                exit_code == 0
            ), "PING_CMD Exit code is not okay. exit_code={}, output={}".format(
                exit_code, output
            )

            # Wait until we are sure that we emptied the queue
            while not output_queue.empty():
                sleep(0.1)

            assert stream_output["value"] == output, "Output should be identical"


def test_double_queue_threaded_stop():
    """
    Use both stdout and stderr queues and make them stop
    """

    if sys.version_info[0] < 3:
        print("Queue test uses concurrent futures. Won't run on python 2.7, sorry.")
        return

    stdout_queue = queue.Queue()
    stderr_queue = queue.Queue()
    thread_result = command_runner_threaded(
        PING_CMD_AND_FAILURE,
        method="poller",
        shell=True,
        stdout=stdout_queue,
        stderr=stderr_queue,
    )

    print("Begin to read queues")
    read_stdout = read_stderr = True
    while read_stdout or read_stderr:
        try:
            stdout_line = stdout_queue.get(timeout=0.1)
        except queue.Empty:
            pass
        else:
            if stdout_line is None:
                read_stdout = False
                print("stdout is finished")
            else:
                print("STDOUT:", stdout_line)

        try:
            stderr_line = stderr_queue.get(timeout=0.1)
        except queue.Empty:
            pass
        else:
            if stderr_line is None:
                read_stderr = False
                print("stderr is finished")
            else:
                print("STDERR:", stderr_line)

    while True:
        done = thread_result.done()
        print("Thread is done:", done)
        if done:
            break
        sleep(1)

    exit_code, _ = thread_result.result()
    assert exit_code == 0, "We did not succeed in running the thread"


def test_deferred_command():
    """
    Using deferred_command in order to run a command after a given timespan
    """
    test_filename = "deferred_test_file"
    if os.path.isfile(test_filename):
        os.remove(test_filename)
    deferred_command("echo test > {}".format(test_filename), defer_time=5)
    assert os.path.isfile(test_filename) is False, "File should not exist yet"
    sleep(6)
    assert os.path.isfile(test_filename) is True, "File should exist now"
    os.remove(test_filename)


def test_powershell_output():
    # Don't bother to test powershell on other platforms than windows
    if os.name != "nt":
        return
    """
    Parts from windows_tools.powershell are used here
    """

    powershell_interpreter = None
    # Try to guess powershell path if no valid path given
    interpreter_executable = "powershell.exe"
    for syspath in ["sysnative", "system32"]:
        try:
            # Let's try native powershell (64 bit) first or else
            # Import-Module may fail when running 32 bit powershell on 64 bit arch
            best_guess = os.path.join(
                os.environ.get("SYSTEMROOT", "C:"),
                syspath,
                "WindowsPowerShell",
                "v1.0",
                interpreter_executable,
            )
            if os.path.isfile(best_guess):
                powershell_interpreter = best_guess
                break
        except KeyError:
            pass
    if powershell_interpreter is None:
        try:
            ps_paths = os.path.dirname(os.environ["PSModulePath"]).split(";")
            for ps_path in ps_paths:
                if ps_path.endswith("Modules"):
                    ps_path = ps_path.strip("Modules")
                possible_ps_path = os.path.join(ps_path, interpreter_executable)
                if os.path.isfile(possible_ps_path):
                    powershell_interpreter = possible_ps_path
                    break
        except KeyError:
            pass

    if powershell_interpreter is None:
        raise OSError("Could not find any valid powershell interpreter")

    # Do not add -NoProfile so we don't end up in a path we're not supposed to
    command = powershell_interpreter + " -NonInteractive -NoLogo %s" % PING_CMD
    exit_code, output = command_runner(command, encoding="unicode_escape")
    print("powershell: ", exit_code, output)
    assert exit_code == 0, "Powershell execution failed."


def test_null_redir():
    for method in methods:
        print("method={}".format(method))
        exit_code, output = command_runner(PING_CMD, stdout=False)
        print(exit_code)
        print("OUTPUT:", output)
        assert output is None, "We should not have any output here"

        exit_code, output = command_runner(
            PING_CMD_AND_FAILURE, shell=True, stderr=False
        )
        print(exit_code)
        print("OUTPUT:", output)
        assert "0.0.0.0" not in output, "We should not get error output from here"

    for method in methods:
        print("method={}".format(method))
        exit_code, stdout, stderr = command_runner(
            PING_CMD, split_streams=True, stdout=False, stderr=False
        )
        print(exit_code)
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        assert stdout is None, "We should not have any output from stdout"
        assert stderr is None, "We should not have any output from stderr"

        exit_code, stdout, stderr = command_runner(
            PING_CMD_AND_FAILURE,
            shell=True,
            split_streams=True,
            stdout=False,
            stderr=False,
        )
        print(exit_code)
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        assert stdout is None, "We should not have any output from stdout"
        assert stderr is None, "We should not have any output from stderr"


def test_split_streams():
    """
    Test replacing output with stdout and stderr output
    """
    for cmd in [PING_CMD, PING_CMD_AND_FAILURE]:
        for method in methods:
            print("cmd={}, method={}".format(cmd, method))

            try:
                exit_code, _ = command_runner(
                    cmd, method=method, shell=True, split_streams=True
                )
            except ValueError:
                # Should generate a valueError
                pass
            except Exception as exc:
                assert (
                    False
                ), "We should have too many values to unpack here: {}".format(exc)

            exit_code, stdout, stderr = command_runner(
                cmd, method=method, shell=True, split_streams=True
            )
            print("exit_code:", exit_code)
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            if cmd == PING_CMD:
                assert (
                    exit_code == 0
                ), "Exit code should be 0 for ping command with method {}".format(
                    method
                )
                assert "127.0.0.1" in stdout
                assert stderr is None
            if cmd == PING_CMD_AND_FAILURE:
                assert (
                    exit_code == 0
                ), "Exit code should be 0 for ping command with method {}".format(
                    method
                )
                assert "127.0.0.1" in stdout
                assert "0.0.0.0" in stderr


def test_on_exit():
    def on_exit():
        global ON_EXIT_CALLED
        ON_EXIT_CALLED = True

    exit_code, _ = command_runner(PING_CMD, on_exit=on_exit)
    assert exit_code == 0, "Exit code is not null"
    assert ON_EXIT_CALLED is True, "On exit was never called"


def test_no_close_queues():
    """
    Test no_close_queues
    """

    if sys.version_info[0] < 3:
        print("Queue test uses concurrent futures. Won't run on python 2.7, sorry.")
        return

    stdout_queue = queue.Queue()
    stderr_queue = queue.Queue()
    thread_result = command_runner_threaded(
        PING_CMD_AND_FAILURE,
        method="poller",
        shell=True,
        stdout=stdout_queue,
        stderr=stderr_queue,
        no_close_queues=True,
    )

    print("Begin to read queues")
    read_stdout = read_stderr = True
    wait_period = 50  # let's have 100 rounds of 2x timeout 0.1s = 10 seconds, which should be enough for exec to terminate
    while read_stdout or read_stderr:
        try:
            stdout_line = stdout_queue.get(timeout=0.1)
        except queue.Empty:
            pass
        else:
            if stdout_line is None:
                assert False, "STDOUT queue has been closed with no_close_queues"
            else:
                print("STDOUT:", stdout_line)

        try:
            stderr_line = stderr_queue.get(timeout=0.1)
        except queue.Empty:
            pass
        else:
            if stderr_line is None:
                assert False, "STDOUT queue has been closed with no_close_queues"
            else:
                print("STDERR:", stderr_line)
        wait_period -= 1
        if wait_period < 1:
            break

    while True:
        done = thread_result.done()
        print("Thread is done:", done)
        if done:
            break
        sleep(1)

    exit_code, _ = thread_result.result()
    assert exit_code == 0, "We did not succeed in running the thread"


def test_low_priority():
    def check_low_priority(process):
        niceness = psutil.Process(process.pid).nice()
        io_niceness = psutil.Process(process.pid).ionice()
        if os.name == "nt":
            assert niceness == 16384, "Process low prio niceness not properly set: {}".format(
                niceness
            )
            assert io_niceness == 1, "Process low prio io niceness not set properly: {}".format(
                io_niceness
            )
        else:
            assert niceness == 15, "Process low prio niceness not properly set: {}".format(
                niceness
            )
            assert io_niceness == 3, "Process low prio io niceness not set properly: {}".format(
                io_niceness
            )
        print("Nice !")

    def command_runner_thread():
        return command_runner_threaded(
            PING_CMD,
            priority="low",
            io_priority="low",
            process_callback=check_low_priority,
        )

    thread = threading.Thread(target=command_runner_thread, args=())
    thread.daemon = True  # thread dies with the program
    thread.start()


def test_high_priority():
    def check_high_priority(process):
        niceness = psutil.Process(process.pid).nice()
        io_niceness = psutil.Process(process.pid).ionice()
        if os.name == "nt":
            assert niceness == 128, "Process high prio niceness not properly set: {}".format(
                niceness
            )
            # So se actually don't test this here, since high prio cannot be set on Windows unless
            # we have NtSetInformationProcess privilege
            # assert io_niceness == 3, "Process high prio io niceness not set properly: {}".format(
            #    io_niceness
            # )
        else:
            assert niceness == -15, "Process high prio niceness not properly set: {}".format(
                niceness
            )
            assert io_niceness == 1, "Process high prio io niceness not set properly: {}".format(
                io_niceness
            )
        print("Nice !")

    def command_runner_thread():
        return command_runner_threaded(
            PING_CMD,
            priority="high",
            # io_priority="high",
            process_callback=check_high_priority,
        )

    thread = threading.Thread(target=command_runner_thread, args=())
    thread.daemon = True  # thread dies with the program
    thread.start()


def test_heartbeat():
    # Log capture class, blatantly copied from https://stackoverflow.com/a/37967421/2635443
    class TailLogHandler(logging.Handler):

        def __init__(self, log_queue):
            logging.Handler.__init__(self)
            self.log_queue = log_queue

        def emit(self, record):
            self.log_queue.append(self.format(record))


    class TailLogger(object):

        def __init__(self, maxlen):
            self._log_queue = collections.deque(maxlen=maxlen)
            self._log_handler = TailLogHandler(self._log_queue)

        def contents(self):
            return "\n".join(self._log_queue)

        @property
        def log_handler(self):
            return self._log_handler

    tail = TailLogger(10)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    log_handler = tail.log_handler
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)  # Add the handler to the logger
    logger.setLevel(logging.INFO)

    exit_code, output = command_runner(
        PING_CMD_10S, heartbeat=2, shell=False
    )
    log_contents = tail.contents()
    print("LOGS:\n", log_contents)
    print("END LOGS")
    print("COMMAND_OUTPUT:\n", output)
    assert exit_code == 0, "Exit code should be 0 for ping command with heartbeat"
    # We should have a modulo 2 heeatbeat
    assert (
        "Still running command after 4 seconds" in log_contents
    ), "Output should have heartbeat"


if __name__ == "__main__":
    print("Example code for %s, %s" % (__intname__, __build__))

    test_standard_ping_with_encoding()
    test_standard_ping_with_default_encoding()
    test_standard_ping_with_encoding_disabled()
    test_timeout()
    test_timeout_with_subtree_killing()
    test_no_timeout()
    test_live_output()
    test_not_found()
    test_file_output()
    test_valid_exit_codes()
    test_unix_only_split_command()
    test_create_no_window()
    test_read_file()
    test_stop_on_argument()
    test_process_callback()
    test_stream_callback()
    test_queue_output()
    test_queue_non_threaded_command_runner()
    test_double_queue_threaded_stop()
    test_deferred_command()
    test_powershell_output()
    test_null_redir()
    test_split_streams()
    test_on_exit()
    test_no_close_queues()
    test_low_priority()
    test_high_priority()
    test_heartbeat()

