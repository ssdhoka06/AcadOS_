import os
from collections import deque
from heapq import heappush, heappop
from typing import Optional, Tuple, List, Dict, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from shared import PCB, Role, JobType, State, transition_state


# ─── Internal state ─────────────────────────────────────────────────────────

_tier1: list = []          # min-heap keyed on deadline  (EXAM / EVALUATION)
_tier2: list = []          # min-heap keyed on -urgency  (RESEARCH)
_tier3: deque = deque()    # FIFO round-robin            (PRACTICE)

_tier2_counter: int = 0    # monotonic tiebreaker for heap stability
_current: Optional[PCB] = None

# Context storage — PCB dataclass has no .context field
_contexts: Dict[int, Dict[str, Any]] = {}

AGING_INTERVAL = 5         # ticks between aging bumps
AGING_AMOUNT   = 0.1       # urgency added per bump


# ─── Public API ──────────────────────────────────────────────────────────────

def submit_job(pcb: PCB) -> None:
    """Compute urgency, transition NEW→READY, place in correct tier queue."""
    pcb.compute_urgency()
    if pcb.state == State.NEW:
        transition_state(pcb, State.READY)

    if pcb.job_type in (JobType.EXAM, JobType.EVALUATION):
        heappush(_tier1, (pcb.deadline, pcb.pid, pcb))
    elif pcb.job_type == JobType.RESEARCH:
        global _tier2_counter
        heappush(_tier2, (-pcb.urgency_score, _tier2_counter, pcb))
        _tier2_counter += 1
    else:
        _tier3.append(pcb)


def scheduler_tick(tick_number: int) -> Tuple[Optional[PCB], Optional[PCB]]:
    """
    Execute one scheduler tick.

    Returns (running_pcb, preempted_pcb | None)
    """
    global _current

    # 1. Aging for Tier 2 every AGING_INTERVAL ticks
    if tick_number > 0 and tick_number % AGING_INTERVAL == 0:
        _apply_tier2_aging()

    # 2. Re-compute urgency for all queued jobs
    _recompute_urgencies()

    # 3. Pick the highest-priority candidate
    candidate = _peek_best()

    preempted: Optional[PCB] = None

    # 4. If something is already running, check preemption
    if _current is not None:
        if candidate is not None and _should_preempt(_current, candidate):
            # Preempt: save context, RUNNING → READY, requeue
            save_context(_current, tick_number)
            transition_state(_current, State.READY)
            _requeue(_current)
            preempted = _current
            _current = None
        else:
            # Current keeps CPU
            return (_current, None)

    # 5. Dispatch next job
    next_pcb = _pop_best()
    if next_pcb is not None:
        load_context(next_pcb, tick_number)
        if next_pcb.state == State.READY:
            transition_state(next_pcb, State.RUNNING)
        _current = next_pcb

    return (_current, preempted)


def plot_gantt(timeline_list: list, path: str = "outputs/gantt.png") -> None:
    """
    Draw a colour-coded Gantt chart.
    Accepts list of (pid, job_type_str, tick) or (pid, tick).
    """
    os.makedirs(os.path.dirname(path) or "outputs", exist_ok=True)

    colour_map = {
        "EXAM":       "#e74c3c",
        "EVALUATION": "#e67e22",
        "RESEARCH":   "#f39c12",
        "PRACTICE":   "#2ecc71",
    }
    default_colour = "#95a5a6"

    normalised = []
    for entry in timeline_list:
        if len(entry) == 2:
            pid, tick = entry
            normalised.append((pid, "UNKNOWN", tick))
        else:
            normalised.append(tuple(entry))

    if not normalised:
        return

    pids_seen = sorted(set(e[0] for e in normalised if e[0] != -1))
    pid_y = {pid: idx for idx, pid in enumerate(pids_seen)}

    fig, ax = plt.subplots(figsize=(14, max(3, len(pids_seen) * 0.6)))
    fig.patch.set_facecolor("#1e1e2e")
    ax.set_facecolor("#1e1e2e")

    for pid, job_type_str, tick in normalised:
        if pid == -1:
            continue
        colour = colour_map.get(job_type_str, default_colour)
        y = pid_y[pid]
        ax.barh(y, 1, left=tick, height=0.6, color=colour,
                edgecolor="#11111b", linewidth=0.5)

    ax.set_yticks(list(range(len(pids_seen))))
    ax.set_yticklabels([f"PID {p}" for p in pids_seen],
                       color="#cdd6f4", fontsize=10)
    ax.set_xlabel("Tick", color="#cdd6f4", fontsize=11)
    ax.set_title("AcadOS — CPU Gantt Chart", color="#cdd6f4",
                 fontsize=13, fontweight="bold")
    ax.tick_params(colors="#6c7086")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#6c7086")
    ax.spines["bottom"].set_color("#6c7086")

    patches = [mpatches.Patch(color=c, label=l) for l, c in colour_map.items()]
    ax.legend(handles=patches, loc="upper right",
              facecolor="#313244", edgecolor="#6c7086",
              labelcolor="#cdd6f4", fontsize=9)

    plt.tight_layout()
    plt.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()


# ─── Context switch helpers (external storage) ──────────────────────────────

def save_context(pcb: PCB, tick: int) -> None:
    """Persist simulated CPU registers keyed by PID."""
    _contexts[pcb.pid] = {"PC": tick, "REG": tick * 2}


def load_context(pcb: PCB, tick: int) -> None:
    """Restore saved context (or initialise)."""
    if pcb.pid not in _contexts:
        _contexts[pcb.pid] = {"PC": tick, "REG": tick * 2}


def get_context(pcb: PCB) -> Dict[str, Any]:
    """Read the saved context for a PCB (for tests / inspection)."""
    return _contexts.get(pcb.pid, {})


# ─── Reset ───────────────────────────────────────────────────────────────────

def reset_scheduler() -> None:
    """Clear all internal queues and state."""
    global _tier1, _tier2, _tier3, _tier2_counter, _current, _contexts
    _tier1 = []
    _tier2 = []
    _tier3 = deque()
    _tier2_counter = 0
    _current = None
    _contexts = {}


# ─── Private helpers ─────────────────────────────────────────────────────────

def _apply_tier2_aging() -> None:
    global _tier2, _tier2_counter
    rebuilt = []
    while _tier2:
        _, _, pcb = heappop(_tier2)
        pcb.urgency_score += AGING_AMOUNT
        heappush(rebuilt, (-pcb.urgency_score, _tier2_counter, pcb))
        _tier2_counter += 1
    _tier2 = rebuilt


def _recompute_urgencies() -> None:
    global _tier1, _tier2, _tier2_counter

    for _, _, pcb in _tier1:
        pcb.compute_urgency()

    rebuilt = []
    while _tier2:
        _, _, pcb = heappop(_tier2)
        pcb.compute_urgency()
        heappush(rebuilt, (-pcb.urgency_score, _tier2_counter, pcb))
        _tier2_counter += 1
    _tier2 = rebuilt

    for pcb in _tier3:
        pcb.compute_urgency()


def _peek_best() -> Optional[PCB]:
    if _tier1:
        return _tier1[0][2]
    if _tier2:
        return _tier2[0][2]
    if _tier3:
        return _tier3[0]
    return None


def _pop_best() -> Optional[PCB]:
    if _tier1:
        _, _, pcb = heappop(_tier1)
        return pcb
    if _tier2:
        _, _, pcb = heappop(_tier2)
        return pcb
    if _tier3:
        return _tier3.popleft()
    return None


def _should_preempt(current: PCB, candidate: PCB) -> bool:
    c_tier = _tier_of(current)
    n_tier = _tier_of(candidate)
    if n_tier < c_tier:
        return True
    if n_tier == c_tier == 1:
        return candidate.deadline < current.deadline
    if n_tier == c_tier == 2:
        return candidate.urgency_score > current.urgency_score
    return False


def _tier_of(pcb: PCB) -> int:
    if pcb.job_type in (JobType.EXAM, JobType.EVALUATION):
        return 1
    if pcb.job_type == JobType.RESEARCH:
        return 2
    return 3


def _requeue(pcb: PCB) -> None:
    global _tier2_counter
    if pcb.job_type in (JobType.EXAM, JobType.EVALUATION):
        heappush(_tier1, (pcb.deadline, pcb.pid, pcb))
    elif pcb.job_type == JobType.RESEARCH:
        heappush(_tier2, (-pcb.urgency_score, _tier2_counter, pcb))
        _tier2_counter += 1
    else:
        _tier3.appendleft(pcb)
