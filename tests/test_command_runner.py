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

__intname__ = 'command_runner_tests'
__author__ = 'Orsiris de Jong'
__copyright__ = 'Copyright (C) 2015-2022 Orsiris de Jong'
__licence__ = 'BSD 3 Clause'
__build__ = '2022052202'


import re
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


streams = ['stdout', 'stderr']
methods = ['monitor', 'poller']

if os.name == 'nt':
    ENCODING = 'cp437'
    PING_CMD = 'ping 127.0.0.1 -n 4'
    PING_CMD_REDIR = PING_CMD + ' 1>&2'
else:
    ENCODING = 'utf-8'
    PING_CMD = ['ping', '127.0.0.1', '-c', '4']
    PING_CMD_REDIR = 'ping 127.0.0.1 -c 4 1>&2'
    # TODO shlex.split(command, posix=True) test for Linux

ELAPSED_TIME = timestamp(datetime.now())
PROCESS_ID = None
STREAM_OUTPUT = ""
PROC = None


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


def test_standard_ping_with_encoding():
    """
    Test command_runner with a standard ping and encoding parameter
    """
    for method in methods:
        exit_code, output = command_runner(PING_CMD, encoding=ENCODING, method=method)
        print(output)
        assert exit_code == 0, 'Exit code should be 0 for ping command with method {}'.format(method)


def test_standard_ping_without_encoding():
    """
    Without encoding, iter(stream.readline, '') will hang since the expected sentinel char would be b'':
    This could only happen on python <3.6 since command_runner decides to use an encoding anyway
    """
    for method in methods:
        exit_code, output = command_runner(PING_CMD, encoding=None, method=method)
        print(output)
        assert exit_code == 0, 'Exit code should be 0 for ping command with method {}'.format(method)


def test_timeout():
    """
    Test command_runner with a timeout
    """
    for method in methods:
        begin_time = datetime.now()
        exit_code, output = command_runner(PING_CMD, timeout=1, method=method)
        print(output)
        end_time = datetime.now()
        assert (end_time - begin_time).total_seconds() < 2, 'It took more than 2 seconds for a timeout=1 command to finish with method {}'.format(method)
        assert exit_code == -254, 'Exit code should be -254 on timeout with method {}'.format(method)
        assert 'Timeout' in output, 'Output should have timeout with method {}'.format(method)


def test_timeout_with_subtree_killing():
    """
    Launch a subtree of long commands and see if timeout actually kills them in time
    """
    if os.name != 'nt':
        cmd = 'echo "test" && sleep 5 && echo "done"'
    else:
        cmd = 'echo test && {} && echo done'.format(PING_CMD)

    for method in methods:
        begin_time = datetime.now()
        exit_code, output = command_runner(cmd, shell=True, timeout=1, method=method)
        print(output)
        end_time = datetime.now()
        elapsed_time = (end_time - begin_time).total_seconds()
        assert elapsed_time < 4, 'It took more than 2 seconds for a timeout=1 command to finish with method {}'.format(method)
        assert exit_code == -254, 'Exit code should be -254 on timeout with method {}'.format(method)
        assert 'Timeout' in output, 'Output should have timeout with method {}'.format(method)


def test_no_timeout():
    """
    Test with setting timeout=None
    """
    for method in methods:
        exit_code, output = command_runner(PING_CMD, timeout=None, method=method)
        print(output)
        assert exit_code == 0, 'Without timeout, command should have run with method {}'.format(method)


def test_live_output():
    """
    Test command_runner with live output to stdout
    """
    for method in methods:
        exit_code, _ = command_runner(PING_CMD, stdout=PIPE, encoding=ENCODING, method=method)
        assert exit_code == 0, 'Exit code should be 0 for ping command with method {}'.format(method)


def test_not_found():
    """
    Test command_runner with an unexisting command
    """
    for method in methods:
        print('The following command should fail with method {}'.format(method))
        exit_code, _ = command_runner('unknown_command_nowhere_to_be_found_1234')
        assert exit_code == -253, 'Unknown command should trigger a -253 exit code with method {}'.format(method)


def test_file_output():
    """
    Test commandr_runner with file output instead of stdout
    """
    for method in methods:
        stdout_filename = 'temp.test'
        stderr_filename = 'temp.test.err'
        print('The following command should timeout')
        exit_code, output = command_runner(PING_CMD, timeout=1, stdout=stdout_filename, stderr=stderr_filename, method=method)
        assert os.path.isfile(stdout_filename), 'Log file does not exist with method {}'.format(method)
        with open(stdout_filename, 'r') as file_handle:
            output = file_handle.read()
        assert os.path.isfile(stderr_filename), 'stderr log file does not exist with method {}'.format(method)
        assert exit_code == -254, 'Exit code should be -254 for timeouts with method {}'.format(method)
        assert 'Timeout' in output, 'Output should have timeout with method {}'.format(method)

        # arbitrary time to make sure file handle was closed
        sleep(3)
        os.remove(stdout_filename)
        os.remove(stderr_filename)


def test_valid_exit_codes():
    """
    Test command_runner with a failed ping but that should not trigger an error
    """
    for method in methods:
        exit_code, _ = command_runner('ping nonexistent_host', shell=True, valid_exit_codes=[0, 1, 2], method=method)
        assert exit_code in [0, 1, 2], 'Exit code not in valid list with method {}'.format(method)


def test_unix_only_split_command():
    """
    This test is specifically written when command_runner receives a str command instead of a list on unix
    """
    if os.name == 'posix':
        for method in methods:
            exit_code, _ = command_runner(' '.join(PING_CMD), method=method)
            assert exit_code == 0, 'Non splitted command should not trigger an error with method {}'.format(method)


def test_create_no_window():
    """
    Only used on windows, when we don't want to create a cmd visible windows
    """
    for method in methods:
        exit_code, _ = command_runner(PING_CMD, windows_no_window=True, method=method)
        assert exit_code == 0, 'Should have worked too with method {}'.format(method)


def test_read_file():
    """
    Read a couple of times the same file to be sure we don't get garbage from _read_pipe()
    This is a random failure detection test
    """
    test_filename = 'README.md'
    with open(test_filename, 'r') as file:
        file_content = file.read()

    for method in methods:
        for round in range(0, 2500):
            print('Comparaison round {} with method {}'.format(round, method))
            if os.name == 'nt':
                exit_code, output = command_runner('type {}'.format(test_filename), shell=True, method=method)
                output = output.replace('\r\n', '\n')
            else:
                exit_code, output = command_runner('cat {}'.format(test_filename), shell=True, method=method)

            assert exit_code == 0, 'Did not succeed to read {}, method={}, exit_code: {}, output: {}'.format(test_filename, method, exit_code,
                                                                                                 output)
            assert file_content == output, 'Round {} File content and output are not identical, method={}'.format(round, method)


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
        print('method={}'.format(method))
        exit_code, output = command_runner(PING_CMD, stop_on=stop_on, method=method)

        # On github actions only with Python 2.7.18, we sometimes get -251 failed because of OS: [Error 5] Access is denied
        # when os.kill(pid) is called in kill_childs_mod
        # On my windows platform using the same Python version, it works...
        # well nothing I can debug on github actions
        if running_on_github_actions() and os.name == 'nt' and sys.version_info[0] < 3:
            assert exit_code in [-253, -251], 'Not as expected, we should get a permission error on github actions windows platform'
        else:
            assert exit_code == -251, 'Monitor mode should have been stopped by stop_on with exit_code -251. method={}, exit_code: {}, output: {}'.format(method, exit_code,
                                                                                                 output)
            assert re.match(expected_output_regex, output, re.MULTILINE) is not None, 'stop_on output is bogus. method={}, exit_code: {}, output: {}'.format(method, exit_code,
                                                                                                 output)


def test_process_callback():
    def callback(process_id):
        global PROCESS_ID
        PROCESS_ID = process_id

    for method in methods:
        exit_code, output = command_runner(PING_CMD, method=method, process_callback=callback)
        assert exit_code == 0, 'Wrong exit code. method={}, exit_code: {}, output: {}'.format(method, exit_code,
                                                                                                 output)
        assert isinstance(PROCESS_ID, subprocess.Popen), 'callback did not work properly. PROCESS_ID="{}"'.format(PROCESS_ID)


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
                print('Method={}, stream={}, output=callback'.format(method, stream))
                exit_code, output = command_runner(PING_CMD_REDIR, shell=True, method=method, **stream_args)
            except ValueError:
                if method == 'poller':
                    assert False, 'ValueError should not be produced in poller mode.'
            if method == 'poller':
                assert exit_code == 0, 'Wrong exit code. method={}, exit_code: {}, output: {}'.format(method, exit_code,
                                                                                                     output)

                # Since we redirect STDOUT to STDERR
                assert STREAM_OUTPUT == output, 'Callback stream should contain same result as output'
            else:
                assert exit_code == -250, 'stream_callback exit_code is bogus. method={}, exit_code: {}, output: {}'.format(method, exit_code,
                                                                                                     output)


def test_queue_output():
    """
    Thread command runner and get it's output queue
    """

    if sys.version_info[0] < 3:
        print("Queue test uses concurrent futures. Won't run on python 2.7, sorry.")
        return

    for stream in streams:
        output_queue = queue.Queue()
        for method in methods:
            stream_output = ""
            stream_args = {stream: output_queue}
            output_queue.queue.clear()
            print('Method={}, stream={}, output=queue'.format(method, stream))
            thread_result = command_runner_threaded(PING_CMD_REDIR, shell=True, method=method, **stream_args)

            read_queue = True
            while read_queue:
                if thread_result.done():
                    read_queue = False
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

            if method == 'poller':
                assert exit_code == 0, 'Wrong exit code. method={}, exit_code: {}, output: {}'.format(method, exit_code,
                                                                                                      output)
                # Since we redirect STDOUT to STDERR
                assert stream_output == output, 'Callback stream should contain same result as output'
            else:
                assert exit_code == -250, 'stream_callback exit_code is bogus. method={}, exit_code: {}, output: {}'.format(
                    method, exit_code,
                    output)


def test_deferred_command():
    """
    Using deferred_command in order to run a command after a given timespan
    """
    test_filename = 'deferred_test_file'
    if os.path.isfile(test_filename):
        os.remove(test_filename)
    deferred_command('echo test > {}'.format(test_filename), defer_time=5)
    assert os.path.isfile(test_filename) is False, 'File should not exist yet'
    sleep(6)
    assert os.path.isfile(test_filename) is True, 'File should exist now'
    os.remove(test_filename)


def test_powershell_output():
    # Don't bother to test powershell on other platforms than windows
    if os.name != 'nt':
        return True
    """
    Parts from windows_tools.powershell are used here
    """

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
    print('powershell: ', exit_code, output)
    assert exit_code == 0, 'Powershell execution failed.'


if __name__ == "__main__":
    print("Example code for %s, %s" % (__intname__, __build__))
    test_queue_output()
    test_standard_ping_with_encoding()
    test_standard_ping_without_encoding()
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
    test_queue_output()
    test_deferred_command()
    test_powershell_output()