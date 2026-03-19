import os
import time
import sqlite3
import threading
import matplotlib.pyplot as plt
from rich.table import Table
from rich.console import Console

from shared import PCB, Role, JobType, State, transition_state

class Diskscheduler:
    pass

def cscan(requests, head):
    requests = sorted(requests)
    left = [r for r in requests if r < head]
    right = [r for r in requests if r >= head]
    return right + left

def sstf(requests, head):
    requests = requests.copy()
    sequence = []
    current_head = head
    while requests:
        closest = min(requests, key=lambda x: abs(x - current_head))
        sequence.append(closest)
        requests.remove(closest)
        current_head = closest
    return sequence

def plot_disk_seeks(cscan_order, sstf_order):
    os.makedirs('outputs', exist_ok=True)
    plt.figure(figsize=(10, 6))
    
    x_cscan = range(1, len(cscan_order) + 1)
    x_sstf = range(1, len(sstf_order) + 1)
    
    plt.plot(x_cscan, cscan_order, marker='o', color='blue', label='C-SCAN')
    plt.plot(x_sstf, sstf_order, marker='x', color='orange', label='SSTF')
    
    plt.title('Disk Seek Comparison')
    plt.xlabel('Service Sequence')
    plt.ylabel('Cylinder Number')
    plt.legend()
    plt.grid(True)
    
    plt.savefig('outputs/disk_seeks.png')
    plt.close()

def create_db():
    conn = sqlite3.connect('acados.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_log (
            pid INTEGER,
            user_id INTEGER,
            role TEXT,
            job_type TEXT,
            cpu_used INTEGER,
            start_time REAL,
            end_time REAL,
            missed_deadline BOOLEAN
        )
    ''')
    conn.commit()
    conn.close()

def log_job(pcb):
    conn = sqlite3.connect('acados.db')
    cursor = conn.cursor()
    end_time = time.time()
    # Assume 0.0 for start_time since it's not in PCB
    start_time = 0.0
    missed_deadline = bool(end_time > pcb.deadline)
    cursor.execute('''
        INSERT INTO job_log (pid, user_id, role, job_type, cpu_used, start_time, end_time, missed_deadline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        pcb.pid, pcb.user_id, pcb.role.name, pcb.job_type.name,
        pcb.cpu_used, start_time, end_time, missed_deadline
    ))
    conn.commit()
    conn.close()

class QuotaError(Exception):
    pass

class FileSystem:
    QUOTAS = {
        Role.STUDENT: 10,
        Role.RESEARCHER: 100,
        Role.FACULTY: 500
    }
    
    def __init__(self):
        self.registrations = {}
        
    def create_job_dir(self, pcb):
        self.registrations[pcb.pid] = pcb.user_id
        
    def check_quota(self, pcb, usage_gb):
        limit = self.QUOTAS.get(pcb.role, 0)
        if usage_gb > limit:
            raise QuotaError("Quota exceeded")

class AbuseMonitor(threading.Thread):
    def __init__(self, process_table, tick_interval=5):
        super().__init__()
        self.process_table = process_table
        self.tick_interval = tick_interval
        self._stop_event = threading.Event()
        self.console = Console()
        self.lock = threading.Lock()
        self.daemon = True # ensure it exits when main program exits
        
    def stop(self):
        self._stop_event.set()
        
    def run(self):
        tick_count = 0
        while not self._stop_event.is_set():
            time.sleep(self.tick_interval)
            tick_count += self.tick_interval
            
            with self.lock:
                for pcb in self.process_table:
                    # Sanat wraps process_table access in a threading.Lock().
                    if pcb.cpu_used > 2 * pcb.cpu_budget_ns and not pcb.abuse_flag:
                        pcb.abuse_flag = True
                        pcb.cpu_budget_ns //= 2
                        try:
                            transition_state(pcb, State.THROTTLED)
                        except ValueError:
                            pass # if invalid state transition (like EXIT -> THROTTLED)
                            
            if tick_count % 10 == 0:
                self.print_table()
                
    def print_table(self):
        table = Table(title="Live Process Table")
        table.add_column("PID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Role", style="magenta")
        table.add_column("JobType", style="green")
        table.add_column("State", style="yellow")
        table.add_column("CPU Used", justify="right", style="blue")
        table.add_column("Abuse Flag", style="red")
        
        with self.lock:
            for pcb in self.process_table:
                row_style = "red" if pcb.state == State.THROTTLED else ""
                table.add_row(
                    str(pcb.pid),
                    pcb.role.name,
                    pcb.job_type.name,
                    pcb.state.name,
                    str(pcb.cpu_used),
                    str(pcb.abuse_flag),
                    style=row_style
                )
        self.console.print(table)
