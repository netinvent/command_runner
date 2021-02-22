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
__copyright__ = 'Copyright (C) 2015-2021 Orsiris de Jong'
__licence__ = 'BSD 3 Clause'
__build__ = '2021022201'

from command_runner import *

if os.name == 'nt':
    ENCODING = 'cp437'
    PING_CMD = 'ping 127.0.0.1 -n 4'
else:
    ENCODING = 'utf-8'
    PING_CMD = ['ping', '127.0.0.1', '-c', '4']
    # TODO shlex.split(command, posix=True) test for Linux


def test_standard_ping_with_encoding():
    """
    Test command_runner with a standard ping and encoding parameter
    """
    exit_code, output = command_runner(PING_CMD, encoding=ENCODING)
    print(output)
    assert exit_code == 0, 'Exit code should be 0 for ping command'


def test_timeout():
    """
    Test command_runner with a timeout
    """
    exit_code, output = command_runner(PING_CMD, timeout=1)
    print(output)
    assert exit_code == -254, 'Exit code should be -254 on timeout'
    assert 'Timeout' in output, 'Output should have timeout'


def test_no_timeout():
    """
    Test with setting timeout=None
    """
    exit_code, output = command_runner(PING_CMD, timeout=None)
    print(output)
    assert exit_code == 0, 'Without timeout, command should have run'


def test_live_output():
    """
    Test command_runner with live output to stdout
    """
    exit_code, _ = command_runner(PING_CMD, stdout=PIPE, encoding=ENCODING)
    assert exit_code == 0, 'Exit code should be 0 for ping command'


def test_not_found():
    """
    Test command_runner with an unexisting command
    """
    print('The following command should fail')
    exit_code, _ = command_runner('unknown_command_nowhere_to_be_found_1234')
    assert exit_code == -253, 'Unknown command should trigger a -253 exit code'


def test_file_output():
    """
    Test commandr_runner with file output instead of stdout
    """
    stdout_filename = 'temp.test'
    stderr_filename = 'temp.test.err'
    print('The following command should timeout')
    exit_code, output = command_runner(PING_CMD, timeout=1, stdout=stdout_filename, stderr=stderr_filename)
    assert os.path.isfile(stdout_filename), 'Log file does not exist'
    with open(stdout_filename, 'r') as file_handle:
        output = file_handle.read()
    assert os.path.isfile(stderr_filename), 'stderr log file does not exist'
    assert exit_code == -254, 'Exit code should be -254 for timeouts'
    assert 'Timeout' in output, 'Output should have timeout'
    os.remove(stdout_filename)
    os.remove(stderr_filename)


def test_valid_exit_codes():
    """
    Test command_runner with a failed ping but that should not trigger an error
    """
    exit_code, _ = command_runner('ping nonexistent_host', shell=True, valid_exit_codes=[0, 1, 2])
    assert exit_code in [0, 1, 2], 'Exit code not in valid list'


def test_unix_only_split_command():
    """
    This test is specifically written when command_runner receives a str command instead of a list on unix
    """
    if os.name == 'posix':
        exit_code, _ = command_runner(' '.join(PING_CMD))
        assert exit_code == 0, 'Non splitted command should not trigger an error'


def test_create_no_window():
    """
    Only used on windows, when we don't want to create a cmd visible windows
    """
    if os.name == 'nt':
        exit_code, _ = command_runner(PING_CMD, windows_no_window=True)
        assert exit_code == 0, 'Should have worked too'


def test_deferred_command():
    """
    Using deferred_command in order to run a command after a given timespan
    """
    test_filename = 'deferred_test_file'
    assert os.path.isfile(test_filename) is False, 'Test file should not exist prior to test'
    deferred_command('echo test > {}'.format(test_filename), defer_time=5)
    assert os.path.isfile(test_filename) is False, 'File should not exist yet'
    sleep(6)
    assert os.path.isfile(test_filename) is True, 'File should exist now'
    os.remove(test_filename)
