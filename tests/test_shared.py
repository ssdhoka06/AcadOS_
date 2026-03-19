import time
import pytest
import os
from shared import PCB, Role, JobType, State, transition_state, load_pcb_from_c

def test_pcb_creation():
    pcb = PCB(
        pid=10,
        user_id=999,
        role=Role.RESEARCHER,
        job_type=JobType.RESEARCH,
        deadline=time.time() + 3600,
        cpu_budget_ns=1000000
    )
    assert pcb.pid == 10
    assert pcb.role == Role.RESEARCHER
    assert pcb.job_type == JobType.RESEARCH
    assert pcb.state == State.NEW

def test_compute_urgency():
    now = time.time()
    # EXAM
    pcb_exam = PCB(pid=1, user_id=1, role=Role.STUDENT, job_type=JobType.EXAM, deadline=now+100, cpu_budget_ns=100)
    # PRACTICE
    pcb_prac = PCB(pid=2, user_id=2, role=Role.STUDENT, job_type=JobType.PRACTICE, deadline=now+100, cpu_budget_ns=100)
    
    exam_urgency = pcb_exam.compute_urgency()
    prac_urgency = pcb_prac.compute_urgency()
    
    assert exam_urgency > prac_urgency

def test_legal_state_transitions():
    pcb = PCB(pid=1, user_id=1, role=Role.STUDENT, job_type=JobType.EXAM, deadline=time.time()+100, cpu_budget_ns=100)
    assert pcb.state == State.NEW
    
    # NEW -> READY
    transition_state(pcb, State.READY)
    assert pcb.state == State.READY
    
    # READY -> RUNNING
    transition_state(pcb, State.RUNNING)
    assert pcb.state == State.RUNNING

    # RUNNING -> BLOCKED
    transition_state(pcb, State.BLOCKED)
    assert pcb.state == State.BLOCKED

def test_illegal_state_transitions():
    pcb = PCB(pid=1, user_id=1, role=Role.STUDENT, job_type=JobType.EXAM, deadline=time.time()+100, cpu_budget_ns=100)
    
    with pytest.raises(ValueError):
        # NEW -> RUNNING is illegal
        transition_state(pcb, State.RUNNING)
        
    transition_state(pcb, State.READY)
    transition_state(pcb, State.RUNNING)
    
    with pytest.raises(ValueError):
        # RUNNING -> NEW is illegal
        transition_state(pcb, State.NEW)

def test_load_pcb_from_c():
    so_path = os.path.join(os.path.dirname(__file__), '..', 'c_src', 'pcb.so')
    if os.path.exists(so_path):
        pcb = load_pcb_from_c(so_path)
        assert pcb.pid == 1
        assert pcb.user_id == 101
        assert pcb.role == Role.STUDENT
        assert pcb.job_type == JobType.PRACTICE
        assert pcb.state == State.NEW
