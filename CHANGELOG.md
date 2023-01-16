# v1.5.0 - command and conquer them all, nod if you're happy

- New silent parameter disabling all logger calls except of logging.DEBUG levels
- New on_exit parameter that takes a callback function as argument
- valid_exit_codes now accept boolean True which means "all" exit codes
- Fix output capture failure should be an error log instead of debug
- Fix no longer show debug logging for stdout or stderr when empty

# v1.4.1 - command and conquer them all, don't nod

- Fix endoding always was set to os default unless explicitly disabled by setting `encoding=False`

# v1.4.0 - command and conquer them all

## Features

- command_runner now has a `command_runner_threaded()` function which allows to run in background, but stil provide live stdout/stderr stream output via queues/callbacks
- Refactor poller mode to allow multiple stdout / stderr stream redirectors
    - Passing a queue.Queue() instance to stdout/stderr arguments will fill queue with live stream output
	- Passing a function to stdout/stderr arguments will callback said function with live stream output
	- Passing a string to stdout/stderr arguments will redirect stream into filename described by string
- Added `split_stream` argument which will make command_runner return (exit_code, stdout, stderr) instead of (exit_code, output) tuple
- Added `check_interval` argument which decides how much time we sleep between two checks, defaults to 0.05 seconds.
  Lowering this improves responsiveness, but increases CPU usage. Default value should be more than reasaonable for most applications
- Added `stop_on` argument which takes a function, which is called every `check_interval` and will interrupt execution if it returns True
- Added `process_callback` argument which takes a function(process), which is called upon execution with a subprocess.Popen object as argument for optional external process control
- Possibility to disable command_runner stream encoding with `encoding=False` so we get raw output (bytes)
- Added more unit tests (stop_on, process_callback, stream callback / queues, to_null_redirections, split_streams)

## Fixes

- Fix unix command provided as list didn't work with `shell=True`
- Fixed more Python 2.7 UnicodedecodeErrors on corner case exceptions catches
- Fixed python 2.7 TimeoutException output can fail with UnicodedecodeError
- Fix Python 2.7 does not have subprocess.DEVNULL
- Ensure output is always None if process didn't return any string on stdout/stderr on Python 2.7
- Fix python 2.7 process.communicate() multiple calls endup without output (non blocking process.poll() needs communicate() when using shell=True)

## Misc

- Removed queue usage in monitor mode (needs lesser threads)
- Optimized performance
- Added new exit code -250 when queue/callbacks are used with monitor method or unknown method has been called
- Optimized tests

# v1.3.1 - command & conquer the standard out/err reloaded

## Misc

- Packaging fixes for Python 2.7 when using `pip install command_runner`

# v1.3.0 - command & conquer the standard out/err

## Features

- Adds the possibility to redirect stdout/stderr to null with `stdout=False` or `stderr=False` arguments

## Misc

- Add python 3.10 to the test matrix

# v1.2.1 - command (threads) & conquer

## Fixes

- Timeout race condition with pypy 3.7 (!) where sometimes exit code wasn't -254
- Try to use signal.SIGTERM (if exists) to kill a process instead of os API that uses PID in order to prevent possible collision when process is already dead and another process with the same PID exists

## Misc

- Unit tests are more verbose
- Black formatter is now enforced
- Timeout tests are less strict to cope with some platform delays

# v1.2.0 - command (runner) & conquer

## Features

- Added a new capture method (monitor)
- There are now two distinct methods to capture output
    - Spawning a thread to enforce timeouts, and using process.communicate() (monitor method)
    - Spawning a thread to readlines from stdout pipe to an output queue, and reading from that output queue while enforcing timeouts (polller method)
- On the fly output (live_output=True) option is now explicit (uses poller method only)
- Returns partial stdout output when timeouts are reached
- Returns partial stdout output when CTRL+C signal is received (only with poller method)

## Fixes

- CRITICAL: Fixed rare annoying but where output wasn't complete
- Use process signals in favor of direct os.kill API to avoid potential race conditions when PID is reused too fast
- Allow full process subtree killing on Windows & Linux, hence not blocking multiple commands like echo "test" && sleep 100 && echo "done"
- Windows does not maintain an explicit process subtree, so we runtime walk processes to establish the child processes to kill. Obviously, orphaned processes cannot be killed that way.-

## Misc

- Adds a default 16K stdout buffer
- Default command execution timeout is 3600s (1 hour)
- Highly improved tests
    - All tests are done for both capture methods
    - Timeout tests are more accurate
    - Added missing encoding tests
    - 2500 rounds of file reading and comparaison are added to detect rare queue read misses

# v0.7.0 (yanked - do not use; see v1.2.0 critical fixes) - The windows GUI

## Features

- Added threaded pipe reader (poller) in order to enforce timeouts on Windows GUI apps

# v0.6.4 - Keep it working more

## Fixes

- Fixed possible encoding issue with Python < 3.4 and powershell containing non unicode output
- More packaging fixes

# v0.6.3 - keep_it_working

## Fixes

- Packaging fixes for Python 2.7

# v0.6.2 - make_it_work

## Fixes

- Improve CI tests
- Fixed possible use of `windows_no_window` with Python < 3.7 should not be allowed

# v0.6.0 - Initial public release - make_it_simple