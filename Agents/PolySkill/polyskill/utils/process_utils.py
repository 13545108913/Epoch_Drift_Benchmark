import os
import multiprocessing
import signal


def run_with_timeout(function, timeout_seconds, *args, **kwargs):
    # Create the multiprocessing process, passing the function and arguments
    process = multiprocessing.Process(target=function, args=args, kwargs=kwargs)
    process.start()

    # Wait for the process to finish within the timeout
    process.join(timeout=timeout_seconds)

    if process.is_alive():
        print(f"Process (PID: {process.pid}) exceeded timeout, sending SIGKILL...")
        os.kill(process.pid, signal.SIGKILL)  # Send SIGKILL to the process
        process.join()  # Ensure cleanup after killing
        raise TimeoutError(
            f"Function execution exceeded timeout of {timeout_seconds} seconds."
        )
