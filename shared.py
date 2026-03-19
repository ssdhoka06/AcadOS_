import time
import ctypes
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any

class Role(Enum):
    STUDENT = 1
    RESEARCHER = 2
    FACULTY = 3

class JobType(Enum):
    PRACTICE = 1
    RESEARCH = 2
    EXAM = 3
    EVALUATION = 4

class State(Enum):
    NEW = 1
    READY = 2
    RUNNING = 3
    BLOCKED = 4
    EXIT = 5
    THROTTLED = 6
    SUSPENDED_READY = 7
    SUSPENDED_BLOCKED = 8

@dataclass
class PCB:
    pid: int
    user_id: int
    role: Role
    job_type: JobType
    deadline: float
    cpu_budget_ns: int
    urgency_score: float = 0.0
    abuse_flag: bool = False
    state: State = State.NEW
    cpu_used: int = 0
    pages: List[int] = field(default_factory=list)
    resources_held: Dict[str, int] = field(default_factory=dict)
    disk_requests: List[int] = field(default_factory=list)

    def compute_urgency(self) -> float:
        """
        formula: urgency = (role_weight * jobtype_weight) / max(0.01, deadline - time.time())
        Role weights: S=1, R=2, F=3
        JobType weights: PRACTICE=1, RESEARCH=2, EXAM=4, EVALUATION=5
        """
        role_weights = {Role.STUDENT: 1, Role.RESEARCHER: 2, Role.FACULTY: 3}
        jobtype_weights = {JobType.PRACTICE: 1, JobType.RESEARCH: 2, JobType.EXAM: 4, JobType.EVALUATION: 5}
        
        rw = role_weights.get(self.role, 1)
        jw = jobtype_weights.get(self.job_type, 1)
        
        time_diff = self.deadline - time.time()
        denom = max(0.01, time_diff)
        
        self.urgency_score = (rw * jw) / denom
        return self.urgency_score

def transition_state(pcb: PCB, new_state: State) -> PCB:
    """
    validates legal transitions (e.g. RUNNING->BLOCKED is valid, RUNNING->NEW is not).
    Raise ValueError on illegal transition.
    """
    valid_transitions = {
        State.NEW: [State.READY],
        State.READY: [State.RUNNING],
        State.RUNNING: [State.READY, State.BLOCKED, State.EXIT, State.THROTTLED],
        State.BLOCKED: [State.READY, State.SUSPENDED_BLOCKED],
        State.THROTTLED: [State.READY, State.EXIT, State.BLOCKED],
        State.SUSPENDED_READY: [State.READY],
        State.SUSPENDED_BLOCKED: [State.SUSPENDED_READY, State.READY],
        State.EXIT: []
    }
    
    if new_state not in valid_transitions.get(pcb.state, []):
        raise ValueError(f"Illegal transition from {pcb.state.name} to {new_state.name}")
    
    pcb.state = new_state
    return pcb

class PCB_C(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("user_id", ctypes.c_int),
        ("role", ctypes.c_int),
        ("job_type", ctypes.c_int),
        ("deadline", ctypes.c_double),
        ("cpu_budget_ns", ctypes.c_longlong),
        ("urgency_score", ctypes.c_double),
        ("abuse_flag", ctypes.c_int),
        ("state", ctypes.c_int),
        ("cpu_used", ctypes.c_longlong)
    ]

def load_pcb_from_c(so_path: str) -> PCB:
    """
    loads the .so and maps C struct fields to Python PCB object.
    """
    if not os.path.exists(so_path):
        raise FileNotFoundError(f"Shared library {so_path} not found.")
        
    lib = ctypes.CDLL(os.path.abspath(so_path))
    lib.get_dummy_pcb.restype = ctypes.POINTER(PCB_C)
    
    ptr = lib.get_dummy_pcb()
    c_struct = ptr.contents
    
    return PCB(
        pid=c_struct.pid,
        user_id=c_struct.user_id,
        role=Role(c_struct.role),
        job_type=JobType(c_struct.job_type),
        deadline=c_struct.deadline,
        cpu_budget_ns=c_struct.cpu_budget_ns,
        urgency_score=c_struct.urgency_score,
        abuse_flag=bool(c_struct.abuse_flag),
        state=State(c_struct.state),
        cpu_used=c_struct.cpu_used
    )
