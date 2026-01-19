"""
Test Executor

Utilities for executing and validating skill tests in sandboxed environments.
"""

import os
import subprocess
import tempfile
import shutil
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TestResult(Enum):
    """Test execution results."""
    PASSED = "passed"
    FAILED = "failed" 
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class TestCase:
    """A test case for skill validation."""
    id: str
    name: str
    test_script: str
    expected_result: Any = None
    timeout: int = 60
    environment: Dict[str, str] = None
    cleanup_commands: List[str] = None
    
    def __post_init__(self):
        if self.environment is None:
            self.environment = {}
        if self.cleanup_commands is None:
            self.cleanup_commands = []


@dataclass
class TestExecution:
    """Result of test execution."""
    test_case: TestCase
    result: TestResult
    output: str = ""
    error: str = ""
    duration: float = 0.0
    exit_code: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_case.id,
            "test_name": self.test_case.name,
            "result": self.result.value,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "exit_code": self.exit_code,
            "metadata": self.metadata
        }


class TestExecutor:
    """
    Executes skill validation tests in controlled environments.
    
    Features:
    - Sandboxed execution
    - Timeout handling
    - Resource monitoring
    - Cleanup management
    - Parallel test execution
    """
    
    def __init__(
        self,
        working_dir: str = "/tmp/skill_tests",
        max_parallel: int = 3,
        default_timeout: int = 120,
        enable_cleanup: bool = True
    ):
        """Initialize test executor."""
        self.working_dir = Path(working_dir)
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self.enable_cleanup = enable_cleanup
        
        # Create working directory
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        # Track running tests
        self.running_tests: Dict[str, subprocess.Popen] = {}
        self.semaphore = threading.Semaphore(max_parallel)
    
    def create_test_case(
        self,
        test_id: str,
        name: str,
        skill_code: str,
        test_actions: List[str],
        timeout: int = None
    ) -> TestCase:
        """Create a test case for skill validation."""
        timeout = timeout or self.default_timeout
        
        # Build test script
        test_script = self._build_test_script(skill_code, test_actions)
        
        return TestCase(
            id=test_id,
            name=name,
            test_script=test_script,
            timeout=timeout,
            cleanup_commands=[f"rm -rf {self.working_dir / test_id}"]
        )
    
    def _build_test_script(self, skill_code: str, test_actions: List[str]) -> str:
        """Build executable test script."""
        script_parts = [
            "#!/usr/bin/env python3",
            "import sys",
            "import traceback",
            "",
            "# Skill code",
            skill_code,
            "",
            "# Test execution",
            "def run_test():",
            "    try:",
            "        # Mock page object for testing",
            "        class MockPage:",
            "            def __init__(self):",
            "                self.actions = []",
            "            ",
            "            def click(self, selector):",
            "                self.actions.append(('click', selector))",
            "            ",
            "            def fill(self, selector, value):",
            "                self.actions.append(('fill', selector, value))",
            "            ",
            "            def goto(self, url):",
            "                self.actions.append(('goto', url))",
            "            ",
            "            def wait_for_selector(self, selector):",
            "                self.actions.append(('wait', selector))",
            "",
            "        page = MockPage()",
            ""
        ]
        
        # Add test actions
        for action in test_actions:
            script_parts.append(f"        {action}")
        
        script_parts.extend([
            "",
            "        print('Test completed successfully')",
            "        return True",
            "    except Exception as e:",
            "        print(f'Test failed: {e}')",
            "        traceback.print_exc()",
            "        return False",
            "",
            "if __name__ == '__main__':",
            "    success = run_test()",
            "    sys.exit(0 if success else 1)"
        ])
        
        return "\n".join(script_parts)
    
    def execute_test(self, test_case: TestCase) -> TestExecution:
        """Execute a single test case."""
        start_time = time.time()
        
        try:
            with self._test_environment(test_case) as test_dir:
                # Write test script
                script_path = test_dir / "test_script.py"
                script_path.write_text(test_case.test_script)
                script_path.chmod(0o755)
                
                # Execute test
                result = self._run_test_process(test_case, script_path)
                
        except Exception as e:
            logger.error(f"Error executing test {test_case.id}: {e}")
            result = TestExecution(
                test_case=test_case,
                result=TestResult.ERROR,
                error=str(e),
                duration=time.time() - start_time
            )
        
        return result
    
    @contextmanager
    def _test_environment(self, test_case: TestCase):
        """Create isolated test environment."""
        test_dir = self.working_dir / test_case.id
        
        try:
            # Create test directory
            test_dir.mkdir(parents=True, exist_ok=True)
            
            # Set up environment
            os.chdir(test_dir)
            
            yield test_dir
            
        finally:
            # Cleanup
            if self.enable_cleanup:
                try:
                    shutil.rmtree(test_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup test dir {test_dir}: {e}")
    
    def _run_test_process(self, test_case: TestCase, script_path: Path) -> TestExecution:
        """Run test process with timeout and monitoring."""
        start_time = time.time()
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(test_case.environment)
            
            # Start process
            process = subprocess.Popen(
                ["python3", str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            self.running_tests[test_case.id] = process
            
            try:
                # Wait for completion with timeout
                stdout, stderr = process.communicate(timeout=test_case.timeout)
                
                # Determine result
                if process.returncode == 0:
                    result = TestResult.PASSED
                else:
                    result = TestResult.FAILED
                
                return TestExecution(
                    test_case=test_case,
                    result=result,
                    output=stdout,
                    error=stderr,
                    duration=time.time() - start_time,
                    exit_code=process.returncode
                )
                
            except subprocess.TimeoutExpired:
                # Kill process and return timeout result
                process.kill()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", "Process killed due to timeout"
                
                return TestExecution(
                    test_case=test_case,
                    result=TestResult.TIMEOUT,
                    output=stdout,
                    error=stderr,
                    duration=time.time() - start_time,
                    exit_code=-1
                )
            
            finally:
                if test_case.id in self.running_tests:
                    del self.running_tests[test_case.id]
        
        except Exception as e:
            return TestExecution(
                test_case=test_case,
                result=TestResult.ERROR,
                error=str(e),
                duration=time.time() - start_time,
                exit_code=-1
            )
    
    def execute_tests_parallel(self, test_cases: List[TestCase]) -> List[TestExecution]:
        """Execute multiple test cases in parallel."""
        results = []
        threads = []
        
        def run_test(test_case):
            with self.semaphore:
                result = self.execute_test(test_case)
                results.append(result)
        
        # Start all test threads
        for test_case in test_cases:
            thread = threading.Thread(target=run_test, args=(test_case,))
            thread.start()
            threads.append(thread)
        
        # Wait for all tests to complete
        for thread in threads:
            thread.join()
        
        return results
    
    def validate_skill_with_trajectories(
        self,
        skill_code: str,
        skill_name: str,
        trajectory_tests: List[Dict[str, Any]]
    ) -> Tuple[bool, List[TestExecution]]:
        """Validate a skill against trajectory-based tests."""
        test_cases = []
        
        for i, traj_test in enumerate(trajectory_tests):
            test_case = TestCase(
                id=f"{skill_name}_traj_{i}",
                name=f"Trajectory test {i+1} for {skill_name}",
                test_script=self._build_trajectory_test(skill_code, skill_name, traj_test),
                timeout=traj_test.get('timeout', self.default_timeout)
            )
            test_cases.append(test_case)
        
        # Execute tests
        results = self.execute_tests_parallel(test_cases)
        
        # Check if all passed
        all_passed = all(result.result == TestResult.PASSED for result in results)
        
        return all_passed, results
    
    def _build_trajectory_test(
        self,
        skill_code: str,
        skill_name: str, 
        trajectory_test: Dict[str, Any]
    ) -> str:
        """Build test script for trajectory validation."""
        script_parts = [
            "#!/usr/bin/env python3",
            "import sys",
            "",
            "# Skill code",
            skill_code,
            "",
            "# Trajectory test",
            "def test_trajectory():",
            "    try:",
            "        # Mock page with action recording",
            "        class MockPage:",
            "            def __init__(self):",
            "                self.actions = []",
            "            ",
            "            def click(self, selector):",
            "                self.actions.append(f'click({repr(selector)})')",
            "                return self",
            "            ",
            "            def fill(self, selector, value):",
            "                self.actions.append(f'fill({repr(selector)}, {repr(value)})')",
            "                return self",
            "            ",
            "            def goto(self, url):",
            "                self.actions.append(f'goto({repr(url)})')",
            "                return self",
            "",
            "        page = MockPage()",
            ""
        ]
        
        # Add skill function call
        args = trajectory_test.get('args', [])
        kwargs = trajectory_test.get('kwargs', {})
        
        if args or kwargs:
            arg_str = ', '.join([repr(arg) for arg in args])
            if kwargs:
                kwarg_str = ', '.join([f'{k}={repr(v)}' for k, v in kwargs.items()])
                if arg_str:
                    call_str = f"page, {arg_str}, {kwarg_str}"
                else:
                    call_str = f"page, {kwarg_str}"
            else:
                call_str = f"page, {arg_str}" if arg_str else "page"
        else:
            call_str = "page"
        
        script_parts.extend([
            f"        {skill_name}({call_str})",
            "",
            "        # Validate expected actions",
            f"        expected_actions = {trajectory_test.get('expected_actions', [])}",
            "        if expected_actions:",
            "            if set(page.actions) != set(expected_actions):",
            "                print(f'Action mismatch. Expected: {expected_actions}, Got: {page.actions}')",
            "                return False",
            "",
            "        print('Trajectory test passed')",
            "        return True",
            "    except Exception as e:",
            "        print(f'Trajectory test failed: {e}')",
            "        return False",
            "",
            "if __name__ == '__main__':",
            "    success = test_trajectory()",
            "    sys.exit(0 if success else 1)"
        ])
        
        return "\n".join(script_parts)
    
    def kill_running_tests(self):
        """Kill all currently running tests."""
        for test_id, process in list(self.running_tests.items()):
            try:
                process.kill()
                logger.info(f"Killed test process: {test_id}")
            except Exception as e:
                logger.error(f"Failed to kill test {test_id}: {e}")
        
        self.running_tests.clear()
    
    def get_test_summary(self, results: List[TestExecution]) -> Dict[str, Any]:
        """Generate summary statistics for test results."""
        total = len(results)
        passed = sum(1 for r in results if r.result == TestResult.PASSED)
        failed = sum(1 for r in results if r.result == TestResult.FAILED)
        timeout = sum(1 for r in results if r.result == TestResult.TIMEOUT)
        error = sum(1 for r in results if r.result == TestResult.ERROR)
        
        avg_duration = sum(r.duration for r in results) / total if total > 0 else 0
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "timeout": timeout,
            "error": error,
            "success_rate": passed / total if total > 0 else 0,
            "average_duration": avg_duration,
            "total_duration": sum(r.duration for r in results)
        }