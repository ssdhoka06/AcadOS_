# main.py — run with: python main.py
import os, time
import os; os.makedirs('outputs', exist_ok=True)
from shared import PCB, Role, JobType, State, transition_state
from scheduler import submit_job, scheduler_tick, plot_gantt
from memory import allocate_pages, access_page, free_pages, plot_page_faults
from deadlock import request_resources, release_resources, deadlock_recover, create_db
from io_manager import log_job, AbuseMonitor, plot_disk_seeks, cscan, sstf
create_db()   # initialise sqlite3
# Create jobs
jobs = [
  PCB(pid=1, user_id=101, role=Role.STUDENT,    job_type=JobType.EXAM,     deadline=time.time()+300, cpu_budget_ns=1000),
  PCB(pid=2, user_id=102, role=Role.STUDENT,    job_type=JobType.PRACTICE, deadline=time.time()+3600, cpu_budget_ns=1000),
  PCB(pid=3, user_id=201, role=Role.RESEARCHER, job_type=JobType.RESEARCH,  deadline=time.time()+1800, cpu_budget_ns=1000),
  PCB(pid=4, user_id=103, role=Role.STUDENT,    job_type=JobType.PRACTICE, deadline=time.time()+7200, cpu_budget_ns=1000),
  PCB(pid=5, user_id=301, role=Role.FACULTY,    job_type=JobType.EVALUATION,deadline=time.time()+600, cpu_budget_ns=1000),
]
# Allocate + request + submit
for job in jobs:
    allocate_pages(job, num_pages=4)
    request_resources(job, {'CPU': 1, 'MEM_BLOCK': 2})
    submit_job(job)
# Start abuse monitor as background thread
monitor = AbuseMonitor(process_table=jobs, tick_interval=5)
monitor.start()
# Run 50 ticks
timeline = []
for tick in range(50):
    running, preempted = scheduler_tick(tick)
    if running:
        access_page(running, virtual_page=tick % 4)
        running.cpu_used += 1
    timeline.append((running.pid if running else -1, tick))
# Cleanup + log + graphs
monitor.stop()
for job in jobs:
    release_resources(job)
    free_pages(job)
    log_job(job)
plot_gantt(timeline)
plot_disk_seeks(cscan([95,180,34,119,11,123,62,64,66], 50),
               sstf([95,180,34,119,11,123,62,64,66], 50))
