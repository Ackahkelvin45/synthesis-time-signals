"""runner.py — run one candidate input through the compiled harness and classify.

This is the single source of truth for "crash vs. rejection vs. valid parse".
Everything else (baseline strategy, agentic loop, triage) calls run_once().

Classification rule (deliberately conservative, per the harness contract):
    exit 0                      -> VALID   (parser accepted the input)
    exit 2                      -> REJECT  (well-formed rejection; NOT a bug)
    exit 11                     -> SKIP    (oversized input the harness could not
                                            test faithfully — a HARNESS limitation,
                                            not a parser rejection. Unlike the
                                            parson harness there is NO embedded-NUL
                                            skip: json-parser's length-taking API
                                            tests NUL bytes faithfully.)
    timeout (> TIMEOUT_S)       -> CRASH   (a hang is a DoS bug per the spec)
    killed by a signal          -> CRASH   (SIGSEGV/SIGABRT/...)
    ANY other exit code         -> CRASH   (sanitizer aborts, unexpected codes)

SKIP is its own bucket so "reject" in the logs always means "the parser
rejected malformed JSON", never "the harness declined to test it". We never
hardcode "the sanitizer exit code": anything outside the known set is a crash.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

TIMEOUT_S = 5  # per-input wall-clock cap (assignment constraint)

# Sanitizer runtime options. abort_on_error makes the process die with a signal
# so we see a crash rather than a clean exit; print_stacktrace gives UBSan a
# trace for dedup; halt_on_error makes the FIRST error fatal.
SANITIZER_ENV = {
    "ASAN_OPTIONS": "abort_on_error=1:detect_stack_use_after_return=1:"
                    "allocator_may_return_null=0:detect_leaks=0",
    "UBSAN_OPTIONS": "print_stacktrace=1:halt_on_error=1:abort_on_error=1",
}


class Outcome(str, Enum):
    VALID = "valid"
    REJECT = "reject"
    SKIP = "skip"     # harness could not test this input faithfully
    CRASH = "crash"


# Exit codes the harness uses for non-crash outcomes. Anything NOT in this map
# (and not exit 0/2) is treated as a crash.
# 10 = embedded NUL (parson: no length-taking API, so a raw NUL would silently
# truncate the input — a harness limitation, not a parser rejection). json-parser
# never emits 10 because its length API tests NUL faithfully.
_SKIP_CODES = {10: "embedded-nul", 11: "oversized"}
_ENVFAIL_CODE = 3


@dataclass
class Result:
    outcome: Outcome
    exit_code: int | None      # process exit code, or None if killed/timed out
    term_signal: int | None    # terminating signal number, if any
    timed_out: bool
    stderr: bytes              # captured for crash triage (sanitizer report)
    detail: str = ""           # e.g. skip reason ("embedded-nul") for logging

    @property
    def is_crash(self) -> bool:
        return self.outcome is Outcome.CRASH

    def signature_source(self) -> str:
        """Human-readable one-line reason, handy for logs."""
        if self.timed_out:
            return f"timeout>{TIMEOUT_S}s"
        if self.term_signal is not None:
            return f"signal:{signal.Signals(self.term_signal).name}"
        if self.detail:
            return f"exit:{self.exit_code}({self.detail})"
        return f"exit:{self.exit_code}"


# The harness needs almost nothing from our environment. Passing the FULL
# environment handed the LLM API key (loaded from .env into os.environ) to every
# one of thousands of subprocess spawns; an allowlist keeps secrets out of them.
_ENV_PASSTHROUGH = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "DYLD_LIBRARY_PATH",
                    "LD_LIBRARY_PATH", "ASAN_SYMBOLIZER_PATH")


def run_once(binary: str | Path, data: bytes, timeout_s: int = TIMEOUT_S) -> Result:
    """Feed `data` to `binary` on stdin and classify the outcome."""
    env = {k: os.environ[k] for k in _ENV_PASSTHROUGH if k in os.environ}
    env.update(SANITIZER_ENV)
    try:
        proc = subprocess.run(
            [str(binary)],
            input=data,
            stdout=subprocess.DEVNULL,   # harness prints nothing on stdout by design
            stderr=subprocess.PIPE,      # sanitizer report lands here
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        # A hang is a crash by the SAME rule as any non-{0,2} outcome: it is not
        # a clean parse/reject. timed_out only records WHY, it is not a separate
        # verdict path — the bucket is still CRASH.
        return Result(Outcome.CRASH, None, None, True, e.stderr or b"", "timeout")

    rc = proc.returncode
    if rc < 0:  # killed by signal -N
        return Result(Outcome.CRASH, None, -rc, False, proc.stderr)
    if rc == 0:
        return Result(Outcome.VALID, 0, None, False, proc.stderr)
    if rc == 2:
        return Result(Outcome.REJECT, 2, None, False, proc.stderr)
    if rc in _SKIP_CODES:
        return Result(Outcome.SKIP, rc, None, False, proc.stderr, _SKIP_CODES[rc])
    if rc == _ENVFAIL_CODE:
        return Result(Outcome.SKIP, rc, None, False, proc.stderr, "harness-envfail")
    return Result(Outcome.CRASH, rc, None, False, proc.stderr)


def harness_mode(binary: str | Path) -> str:
    """Ask the binary which build mode it is (default | roundtrip | control)."""
    out = subprocess.run([str(binary), "--mode"], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, timeout=10)
    return out.stdout.decode().strip()


# 'roundtrip' (parson) is the real parser plus its real serializer — genuine
# surface, not synthetic — so it is a legitimate source of findings.
_REAL_TARGET_MODES = {"default", "hunt", "unmask", "roundtrip"}


def assert_real_target(binary: str | Path) -> None:
    """Guard: refuse to treat a SYNTHETIC build as a source of real findings.

    Enforced, not merely intended — the positive-control build reports mode
    'control' and is rejected here, so its injected crash can never be logged as
    a json-parser bug. The 'hunt' and 'unmask' builds ARE allowed: both are the
    real parser with finding #1 (the known first-pass NULL-offset idiom) removed
    so the loop can reach past it — 'hunt' by disabling the pointer-overflow check
    globally, 'unmask' by a value-preserving integer-arithmetic rewrite of just
    that site (pointer-overflow stays live everywhere else). Any crash either
    surfaces is a genuine bug — re-confirmed on the 'default' build.
    """
    mode = harness_mode(binary)
    if mode not in _REAL_TARGET_MODES:
        raise RuntimeError(
            f"refusing to fuzz for real findings with a '{mode}'-mode binary "
            f"({binary}); real runs must use the default or hunt build."
        )


if __name__ == "__main__":
    # Manual smoke helper:  python runner.py <binary> [file]  (stdin if no file)
    import sys

    binary = sys.argv[1]
    if len(sys.argv) > 2:
        payload = Path(sys.argv[2]).read_bytes()
    else:
        payload = sys.stdin.buffer.read()
    r = run_once(binary, payload)
    print(f"{r.outcome.value:6}  {r.signature_source()}")
    if r.is_crash and r.stderr:
        sys.stderr.buffer.write(r.stderr)


# --- batch mode: many inputs, one process (paper plan, step 4) ---------------
#
# The harness's `--batch` mode (harness/driver.h) reads length-prefixed inputs
# on stdin and answers one "R <index> <code> [<msg>]" line per input. The
# classification rule is the SAME as run_once: the code maps exactly like an
# exit code, a process death is a crash for the input whose line never came
# (sanitizer report read from stderr), and a hang is cut by the harness's own
# alarm (exit 124) or, as a backstop, by the runner. After a death the runner
# restarts the harness at the next index, so one crash never costs the rest of
# the batch. `profile_prefix` (coverage builds only) makes the harness flush
# cumulative profile counters at `checkpoints`; each restart is a new SEGMENT
# ("<prefix>.seg<k>"), and the caller merges segments (eval/cell.py).

import selectors
import struct
import threading

HARNESS_TIMEOUT_EXIT = 124


def _classify_code(rc: int, stderr: bytes) -> Result:
    if rc == 0:
        return Result(Outcome.VALID, 0, None, False, stderr)
    if rc == 2:
        return Result(Outcome.REJECT, 2, None, False, stderr)
    if rc in _SKIP_CODES:
        return Result(Outcome.SKIP, rc, None, False, stderr, _SKIP_CODES[rc])
    if rc == _ENVFAIL_CODE:
        return Result(Outcome.SKIP, rc, None, False, stderr, "harness-envfail")
    return Result(Outcome.CRASH, rc, None, False, stderr)


class _Harness:
    """One live harness process in --batch mode."""

    def __init__(self, binary: str | Path, start_index: int, timeout_s: int,
                 checkpoints: list[int] | None, profile_prefix: str | None):
        env = {k: os.environ[k] for k in _ENV_PASSTHROUGH if k in os.environ}
        env.update(SANITIZER_ENV)
        argv = [str(binary), "--batch", "--timeout", str(timeout_s),
                "--start-index", str(start_index)]
        if checkpoints:
            argv += ["--checkpoints", ",".join(str(c) for c in checkpoints)]
        if profile_prefix:
            argv += ["--profile-prefix", profile_prefix]
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env)
        self._err = bytearray()
        self._err_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._err_thread.start()
        self._buf = bytearray()
        self._sel = selectors.DefaultSelector()
        self._sel.register(self.proc.stdout, selectors.EVENT_READ)

    def _drain_stderr(self) -> None:
        for chunk in iter(lambda: self.proc.stderr.read1(65536), b""):
            self._err += chunk

    def send(self, data: bytes) -> None:
        self.proc.stdin.write(struct.pack("<I", len(data)) + data)
        self.proc.stdin.flush()

    def read_line(self, timeout_s: float) -> bytes | None:
        """Next stdout line, or None on EOF/timeout (caller checks .proc)."""
        deadline = time.monotonic() + timeout_s
        while b"\n" not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            if not self._sel.select(remaining):
                return None
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                return None
            self._buf += chunk
        line, _, rest = bytes(self._buf).partition(b"\n")
        self._buf = bytearray(rest)
        return line

    def kill(self) -> None:
        try:
            self.proc.kill()
        except ProcessLookupError:
            pass
        self.close()

    def close(self) -> bytes:
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        self.proc.wait()
        self._err_thread.join(timeout=5)
        self._sel.close()
        return bytes(self._err)


def run_many(binary: str | Path, inputs: list[bytes], timeout_s: int = TIMEOUT_S,
             checkpoints: list[int] | None = None,
             profile_prefix: str | None = None) -> tuple[list[Result], list[str]]:
    """Classify every input in one (restarted-on-crash) harness process.

    Returns (results, segment_prefixes). results[i] corresponds to inputs[i]
    with the same Outcome rule as run_once. segment_prefixes lists the
    "<profile_prefix>.seg<k>" used by each process segment (empty when no
    profile_prefix), so the caller can merge coverage across restarts.
    """
    results: list[Result] = []
    segments: list[str] = []
    i = 0
    n = len(inputs)
    while i < n:
        seg_prefix = f"{profile_prefix}.seg{len(segments)}" if profile_prefix else None
        if seg_prefix:
            segments.append(seg_prefix)
        h = _Harness(binary, i, timeout_s, checkpoints, seg_prefix)
        died = False
        while i < n and not died:
            data = inputs[i]
            try:
                h.send(data)
            except (BrokenPipeError, OSError):
                died = True
                break
            line = h.read_line(timeout_s + 2.0)
            if line is None:
                if h.proc.poll() is None:
                    # runner-side backstop: the harness alarm did not fire
                    h.kill()
                    results.append(Result(Outcome.CRASH, None, None, True, b"", "timeout"))
                    i += 1
                    died = True
                    break
                died = True
                break
            parts = line.decode("utf-8", "replace").split(" ", 3)
            if len(parts) < 3 or parts[0] != "R":
                died = True
                break
            idx, code = int(parts[1]), int(parts[2])
            if idx != i:
                died = True
                break
            msg = parts[3] if len(parts) > 3 else ""
            r = _classify_code(code, (b"reject: " + msg.encode()) if code == 2 and msg else b"")
            results.append(r)
            i += 1
        if died:
            err = h.close()
            rc = h.proc.returncode
            if len(results) < i:
                pass  # already classified (runner-side timeout)
            elif i < n:
                if rc is not None and rc < 0:
                    results.append(Result(Outcome.CRASH, None, -rc, False, err))
                elif rc == HARNESS_TIMEOUT_EXIT:
                    results.append(Result(Outcome.CRASH, None, None, True, err, "timeout"))
                else:
                    results.append(Result(Outcome.CRASH, rc, None, False, err))
                i += 1
            continue
        h.close()
    return results, segments
