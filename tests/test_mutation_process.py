import os
import sys
from pathlib import Path
from select import select

import pytest
from tools.mutation_process import Command, run_child


@pytest.mark.skipif(sys.platform == "win32", reason="Unix process groups")
def test_timeout_terminates_descendant(tmp_path: Path) -> None:
    # Given: a parent waiting on a descendant in the same process group.
    pid_file = tmp_path / "pid"
    script = (
        "import subprocess,sys; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import signal;signal.pause()']); "
        "Path(sys.argv[1]).write_text(str(p.pid));p.wait()"
    )
    # When: the bounded command exhausts its wall budget.
    result = run_child(
        Command((sys.executable, "-c", script, str(pid_file)), tmp_path),
        tmp_path / "log",
        1,
    )
    # Then: timeout is explicit and the descendant is dead (possibly unreaped).
    assert result.timed_out
    pid = int(pid_file.read_text())
    proc = Path(f"/proc/{pid}/stat")
    if sys.platform == "linux" and proc.exists():
        descriptor = os.pidfd_open(pid)
        try:
            ready, _, _ = select([descriptor], [], [], 2)
            assert ready
        finally:
            os.close(descriptor)
    if proc.exists():
        assert proc.read_text().split()[2] == "Z"
    else:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix process groups")
def test_child_failure_is_preserved(tmp_path: Path) -> None:
    # Given: a failing real child.
    command = Command((sys.executable, "-c", "raise SystemExit(7)"), tmp_path)
    # When: it completes before the budget.
    result = run_child(command, tmp_path / "log", 10)
    # Then: its exit status is not converted to success or timeout.
    assert result.returncode == 7
    assert not result.timed_out


@pytest.mark.skipif(sys.platform != "linux", reason="Linux exit-descriptor control")
def test_sigterm_cleans_active_child(tmp_path: Path) -> None:
    # Given: a real runner whose child sends SIGTERM back to its parent.
    child = """import os,signal,sys
from pathlib import Path
Path(sys.argv[1]).write_text(str(os.getpid()))
os.kill(os.getppid(), signal.SIGTERM)
signal.pause()
"""
    wrapper = """import sys
from pathlib import Path
from tools.mutation_process import Command,run_child
try:
    run_child(Command((sys.executable,'-c',sys.argv[1],sys.argv[2]),Path.cwd()),Path('inner.log'),30)
except InterruptedError:
    Path('interrupted').write_text('caught')
"""
    # When: the nested runner is interrupted while enforcing a child budget.
    result = run_child(
        Command(
            (sys.executable, "-c", wrapper, child, str(tmp_path / "pid")),
            tmp_path,
            {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])},
        ),
        tmp_path / "outer.log",
        30,
    )
    # Then: interruption is caught after cleanup and the child has exited.
    assert result.returncode == 0
    assert (tmp_path / "interrupted").read_text() == "caught"
    pid = int((tmp_path / "pid").read_text())
    if Path(f"/proc/{pid}").exists():
        descriptor = os.pidfd_open(pid)
        try:
            ready, _, _ = select([descriptor], [], [], 2)
            assert ready
        finally:
            os.close(descriptor)
