import pytest
import sqlite3
import os
import time
from shared import PCB, Role, JobType, State
from io_manager import cscan, sstf, create_db, log_job, AbuseMonitor

def test_cscan():
    requests = [95, 180, 34, 119, 11, 123, 62, 64, 66]
    head = 50
    # Requests sorted: 11, 34, 62, 64, 66, 95, 119, 123, 180
    # Head=50. C-SCAN right: 62, 64, 66, 95, 119, 123, 180. Left: 11, 34
    expected = [62, 64, 66, 95, 119, 123, 180, 11, 34]
    assert cscan(requests, head) == expected

def test_sstf():
    requests = [95, 180, 34, 119, 11, 123, 62, 64, 66]
    head = 50
    # closest to 50 is 62.
    expected = [62, 64, 66, 95, 119, 123, 180, 34, 11] 
    assert sstf(requests, head) == expected

def test_log_job():
    # clean db if exists
    if os.path.exists('acados.db'):
        os.remove('acados.db')
        
    create_db()
    
    pcb = PCB(
        pid=999,
        user_id=1,
        role=Role.STUDENT,
        job_type=JobType.EXAM,
        deadline=time.time() + 1000,
        cpu_budget_ns=500,
        cpu_used=600
    )
    
    log_job(pcb)
    
    conn = sqlite3.connect('acados.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_log WHERE pid=999")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == 999
    assert row[2] == "STUDENT"
    assert row[4] == 600

def test_abuse_monitor():
    pcb = PCB(
        pid=1001,
        user_id=2,
        role=Role.STUDENT,
        job_type=JobType.PRACTICE,
        deadline=time.time() + 1000,
        cpu_budget_ns=100,
        cpu_used=250,  # 250 > 2 * 100 -> abusive
        state=State.RUNNING
    )
    
    monitor = AbuseMonitor([pcb], tick_interval=0.1)
    monitor.start()
    
    time.sleep(0.3)
    monitor.stop()
    monitor.join()
    
    assert pcb.abuse_flag is True
    assert pcb.state == State.THROTTLED
    assert pcb.cpu_budget_ns == 50
