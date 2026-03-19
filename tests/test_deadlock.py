"""
tests/test_deadlock.py — Nikhil (Deadlock Engineer)

Minimum required tests (per Task 3 spec):
  1. Banker's returns False for known unsafe request
  2. Safe request returns True
  3. deadlock_recover terminates PRACTICE before RESEARCH before EXAM
  4. 5 concurrent reader threads + 1 writer cause no data corruption
  + bonus: release_resources frees allocation back to pool
"""

import time
import threading
import pytest

from shared import PCB, Role, JobType, State
from deadlock import (
    ResourceManager,
    AcadosSemaphore,
    create_db,
    db_read,
    db_write,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_pcb(pid: int, job_type=JobType.PRACTICE, role=Role.STUDENT) -> PCB:
    return PCB(
        pid=pid,
        user_id=pid * 10,
        role=role,
        job_type=job_type,
        deadline=time.time() + 3600,
        cpu_budget_ns=1_000_000,
    )


# ─── Test 1: Safe request is granted ─────────────────────────────────────────

def test_safe_request_returns_true():
    rm  = ResourceManager()
    pcb = make_pcb(1)
    rm.register(pcb, {'CPU': 2, 'MEM_BLOCK': 4})

    result = rm.request_resources(pcb, {'CPU': 1, 'MEM_BLOCK': 2})

    assert result is True
    assert rm.allocation[1]['CPU'] == 1
    assert rm.allocation[1]['MEM_BLOCK'] == 2
    assert rm.available['CPU'] == 3          # 4 - 1
    assert rm.available['MEM_BLOCK'] == 6    # 8 - 2


# ─── Test 2: Unsafe request is denied ────────────────────────────────────────

def test_unsafe_request_returns_false():
    """
    Classic deadlock scenario:
      available = {CPU:1, MEM_BLOCK:1}
      P1: max=3/3, alloc=1/1  → need=2/2
      P2: max=3/3, alloc=1/1  → need=2/2
      P3: max=3/3, alloc=1/1  → need=2/2
    P1 requests {CPU:1, MEM_BLOCK:1} → hypo available=0/0 → nobody can finish → UNSAFE.
    """
    rm = ResourceManager()
    rm.available = {'CPU': 1, 'MEM_BLOCK': 1}

    p1, p2, p3 = make_pcb(1), make_pcb(2), make_pcb(3)
    for p in (p1, p2, p3):
        rm.max_need[p.pid]   = {'CPU': 3, 'MEM_BLOCK': 3}
        rm.allocation[p.pid] = {'CPU': 1, 'MEM_BLOCK': 1}

    result = rm.request_resources(p1, {'CPU': 1, 'MEM_BLOCK': 1})

    assert result is False


# ─── Test 3: Recovery order — PRACTICE first, EXAM last ──────────────────────

def test_recovery_terminates_practice_before_exam():
    """
    Setup (deadlocked):
      available = {CPU:0, MEM_BLOCK:0}
      EXAM      (pid=1): alloc=2/2, max=3/3, need=1/1
      RESEARCH  (pid=2): alloc=1/1, max=3/3, need=2/2
      PRACTICE  (pid=3): alloc=1/1, max=3/3, need=2/2

    Terminating PRACTICE frees {1,1} → available={1,1}.
    EXAM need=1 ≤ work=1 → EXAM finishes, work={3,3}.
    RESEARCH need=2 ≤ work=3 → safe.
    → Recovery stops after terminating only PRACTICE.
    """
    rm = ResourceManager()
    rm.available = {'CPU': 0, 'MEM_BLOCK': 0}

    exam     = make_pcb(1, JobType.EXAM,     Role.STUDENT)
    research = make_pcb(2, JobType.RESEARCH,  Role.RESEARCHER)
    practice = make_pcb(3, JobType.PRACTICE,  Role.STUDENT)

    rm.max_need[1]   = {'CPU': 3, 'MEM_BLOCK': 3}
    rm.allocation[1] = {'CPU': 2, 'MEM_BLOCK': 2}

    rm.max_need[2]   = {'CPU': 3, 'MEM_BLOCK': 3}
    rm.allocation[2] = {'CPU': 1, 'MEM_BLOCK': 1}

    rm.max_need[3]   = {'CPU': 3, 'MEM_BLOCK': 3}
    rm.allocation[3] = {'CPU': 1, 'MEM_BLOCK': 1}

    terminated = rm.deadlock_recover([exam, research, practice])

    assert len(terminated) >= 1
    assert terminated[0] == 3          # PRACTICE killed first
    assert 1 not in terminated         # EXAM never touched


def test_recovery_order_practice_before_research():
    """If both PRACTICE and RESEARCH must go, PRACTICE is still terminated first."""
    rm = ResourceManager()
    rm.available = {'CPU': 0, 'MEM_BLOCK': 0}

    exam     = make_pcb(1, JobType.EXAM,     Role.STUDENT)
    research = make_pcb(2, JobType.RESEARCH,  Role.RESEARCHER)
    practice = make_pcb(3, JobType.PRACTICE,  Role.STUDENT)

    # Give all processes needs that can't be satisfied — full deadlock
    for pid, alloc in [(1, 2), (2, 1), (3, 1)]:
        rm.max_need[pid]   = {'CPU': 10, 'MEM_BLOCK': 10}
        rm.allocation[pid] = {'CPU': alloc, 'MEM_BLOCK': alloc}

    terminated = rm.deadlock_recover([exam, research, practice])

    practice_idx = terminated.index(3) if 3 in terminated else None
    research_idx = terminated.index(2) if 2 in terminated else None

    if practice_idx is not None and research_idx is not None:
        assert practice_idx < research_idx   # PRACTICE before RESEARCH


# ─── Test 4: Readers-Writers — no corruption under concurrency ───────────────

def test_readers_writers_no_corruption():
    """5 reader threads + 1 writer thread must not corrupt the DB."""
    create_db()
    db_write(777, {
        'user_id': 1, 'role': 'STUDENT', 'job_type': 'PRACTICE',
        'cpu_used': 0, 'start_time': 0.0, 'end_time': 0.0, 'missed_deadline': 0,
    })

    results: list = []
    errors:  list = []

    def reader():
        try:
            row = db_read(777)
            results.append(row)
        except Exception as e:
            errors.append(str(e))

    def writer():
        try:
            db_write(777, {
                'user_id': 1, 'role': 'STUDENT', 'job_type': 'PRACTICE',
                'cpu_used': 99, 'start_time': 1.0, 'end_time': 2.0, 'missed_deadline': 0,
            })
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=reader) for _ in range(5)]
    threads.append(threading.Thread(target=writer))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Concurrency errors: {errors}"
    assert len(results) == 5          # all 5 readers completed


# ─── Test 5: release_resources returns allocation to pool ────────────────────

def test_release_returns_resources_to_pool():
    rm  = ResourceManager()
    pcb = make_pcb(1)
    rm.register(pcb, {'CPU': 2, 'MEM_BLOCK': 4})
    rm.request_resources(pcb, {'CPU': 1, 'MEM_BLOCK': 3})

    cpu_before = rm.available['CPU']
    mem_before = rm.available['MEM_BLOCK']

    rm.release_resources(pcb)

    assert rm.available['CPU']      == cpu_before + 1
    assert rm.available['MEM_BLOCK'] == mem_before + 3
    assert 1 not in rm.allocation    # pid removed from dict
    assert pcb.resources_held == {}
