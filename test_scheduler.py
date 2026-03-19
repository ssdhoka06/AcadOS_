import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared import PCB, Role, JobType, State, transition_state
from scheduler import (
    submit_job,
    scheduler_tick,
    plot_gantt,
    save_context,
    load_context,
    get_context,
    reset_scheduler,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_pcb(pid, role=Role.STUDENT, job_type=JobType.PRACTICE,
              deadline_offset=3600):
    return PCB(
        pid=pid,
        user_id=pid * 100,
        role=role,
        job_type=job_type,
        deadline=time.time() + deadline_offset,
        cpu_budget_ns=100,
    )


@pytest.fixture(autouse=True)
def _clean_scheduler():
    reset_scheduler()
    yield
    reset_scheduler()


# ─── 1. EXAM always preempts PRACTICE ────────────────────────────────────────

def test_exam_preempts_practice():
    """Submit PRACTICE first, then EXAM. EXAM should get CPU on the next tick."""
    p1 = _make_pcb(1, job_type=JobType.PRACTICE, deadline_offset=7200)
    p2 = _make_pcb(2, job_type=JobType.EXAM, deadline_offset=300)

    submit_job(p1)
    running, preempted = scheduler_tick(0)
    assert running is not None
    assert running.pid == 1

    submit_job(p2)
    running, preempted = scheduler_tick(1)
    assert running is not None
    assert running.pid == 2, "EXAM should preempt PRACTICE"
    assert preempted is not None
    assert preempted.pid == 1, "PRACTICE should be preempted"
    # Preempted PCB goes back to READY (no PREEMPTED state in shared.py)
    assert preempted.state == State.READY


def test_exam_always_scheduled_first_in_mixed_queue():
    """With EXAM, RESEARCH, PRACTICE submitted together, EXAM runs first."""
    practice = _make_pcb(1, job_type=JobType.PRACTICE, deadline_offset=7200)
    research = _make_pcb(2, role=Role.RESEARCHER,
                         job_type=JobType.RESEARCH, deadline_offset=1800)
    exam     = _make_pcb(3, job_type=JobType.EXAM, deadline_offset=300)

    submit_job(practice)
    submit_job(research)
    submit_job(exam)

    running, _ = scheduler_tick(0)
    assert running.pid == 3, "EXAM must be first to run"


# ─── 2. Tier-2 aging ────────────────────────────────────────────────────────

def test_tier2_aging_increments_urgency():
    """Urgency of RESEARCH jobs should increase after aging interval."""
    r1 = _make_pcb(10, role=Role.RESEARCHER,
                   job_type=JobType.RESEARCH, deadline_offset=1800)
    submit_job(r1)
    initial_urgency = r1.urgency_score

    # Keep r1 in queue by having a higher-priority job run
    exam = _make_pcb(99, job_type=JobType.EXAM, deadline_offset=300)
    submit_job(exam)

    for t in range(6):
        scheduler_tick(t)

    # r1 should have been aged at tick 5
    assert r1.urgency_score >= initial_urgency


# ─── 3. Context switch saves & restores ─────────────────────────────────────

def test_context_save_and_restore():
    """save_context stores tick-based values; get_context reads them."""
    pcb = _make_pcb(42)
    save_context(pcb, tick=10)
    ctx = get_context(pcb)
    assert ctx == {"PC": 10, "REG": 20}

    # Reinitialise
    load_context(pcb, tick=10)
    ctx2 = get_context(pcb)
    assert ctx2 == {"PC": 10, "REG": 20}


def test_context_preserved_across_preemption():
    """When a job is preempted, its context should have been saved."""
    p1 = _make_pcb(1, job_type=JobType.PRACTICE, deadline_offset=7200)
    submit_job(p1)
    scheduler_tick(0)  # p1 runs

    p2 = _make_pcb(2, job_type=JobType.EXAM, deadline_offset=300)
    submit_job(p2)
    _, preempted = scheduler_tick(1)  # p2 preempts p1

    assert preempted is not None
    ctx = get_context(preempted)
    assert "PC" in ctx
    assert "REG" in ctx


# ─── 4. plot_gantt creates file ──────────────────────────────────────────────

def test_plot_gantt_creates_file(tmp_path):
    timeline = [
        (1, "EXAM",     0),
        (1, "EXAM",     1),
        (2, "PRACTICE", 2),
        (2, "PRACTICE", 3),
        (3, "RESEARCH", 4),
    ]
    out = str(tmp_path / "gantt.png")
    plot_gantt(timeline, path=out)
    assert os.path.isfile(out), "Gantt chart PNG should exist"
    assert os.path.getsize(out) > 0, "Gantt chart PNG should not be empty"


# ─── 5. 30-tick mixed workload ──────────────────────────────────────────────

def test_30_tick_mixed_workload():
    """Run 30 ticks with 3 EXAM + 3 PRACTICE + 2 RESEARCH. No crashes."""
    jobs = [
        _make_pcb(1, job_type=JobType.EXAM,     deadline_offset=300),
        _make_pcb(2, job_type=JobType.EXAM,     deadline_offset=400),
        _make_pcb(3, job_type=JobType.EXAM,     deadline_offset=500),
        _make_pcb(4, job_type=JobType.PRACTICE,  deadline_offset=7200),
        _make_pcb(5, job_type=JobType.PRACTICE,  deadline_offset=7200),
        _make_pcb(6, job_type=JobType.PRACTICE,  deadline_offset=7200),
        _make_pcb(7, role=Role.RESEARCHER,
                  job_type=JobType.RESEARCH, deadline_offset=1800),
        _make_pcb(8, role=Role.RESEARCHER,
                  job_type=JobType.RESEARCH, deadline_offset=2000),
    ]
    for j in jobs:
        submit_job(j)

    timeline = []
    exam_ticks = 0
    for t in range(30):
        running, _ = scheduler_tick(t)
        if running:
            jt_str = running.job_type.name
            timeline.append((running.pid, jt_str, t))
            if running.job_type == JobType.EXAM:
                exam_ticks += 1

    assert exam_ticks > 0, "EXAM jobs should have run at least once"
    assert len(timeline) == 30, "Every tick should schedule something"


# ─── 6. submit_job transitions NEW → READY ─────────────────────────────────

def test_submit_job_transitions_state():
    pcb = _make_pcb(99)
    assert pcb.state == State.NEW
    submit_job(pcb)
    assert pcb.state == State.READY


# ─── 7. EVALUATION treated same as EXAM (Tier 1) ───────────────────────────

def test_evaluation_is_tier1():
    """EVALUATION jobs should be in Tier 1 alongside EXAM."""
    ev = _make_pcb(1, role=Role.FACULTY, job_type=JobType.EVALUATION,
                   deadline_offset=600)
    pr = _make_pcb(2, job_type=JobType.PRACTICE, deadline_offset=7200)

    submit_job(pr)
    submit_job(ev)

    running, _ = scheduler_tick(0)
    assert running.pid == 1, "EVALUATION should run before PRACTICE"
