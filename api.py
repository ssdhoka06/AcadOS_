import asyncio
import json
import os
import time
import threading
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared import PCB, Role, JobType, State, transition_state
from scheduler import submit_job, scheduler_tick, plot_gantt, reset_scheduler
from memory import allocate_pages, access_page, free_pages, MemoryManager
from deadlock import (
    request_resources, release_resources, deadlock_recover,
    create_db, db_read, db_write, ResourceManager,
)

# io_manager not yet pushed by Sanat — will import when available:
# from io_manager import log_job, AbuseMonitor, plot_disk_seeks, cscan, sstf

app = FastAPI(title="AcadOS API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── In-memory simulation state ─────────────────────────────────────────────

class SimState:
    def __init__(self):
        self.jobs: Dict[int, PCB] = {}
        self.timeline: list = []
        self.tick: int = 0
        self.running: bool = False
        self.current_pid: Optional[int] = None
        self.ws_clients: List[WebSocket] = []
        self.lock = threading.Lock()
        self.memory_mgr = MemoryManager()
        self.resource_mgr = ResourceManager()

    def reset(self):
        self.jobs.clear()
        self.timeline.clear()
        self.tick = 0
        self.running = False
        self.current_pid = None
        reset_scheduler()
        self.memory_mgr = MemoryManager()
        self.resource_mgr = ResourceManager()

sim = SimState()


# ─── Pydantic models ────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    pid: int
    user_id: int
    role: int           # 1=STUDENT, 2=RESEARCHER, 3=FACULTY
    job_type: int       # 1=PRACTICE, 2=RESEARCH, 3=EXAM, 4=EVALUATION
    deadline_offset: float = 3600.0
    cpu_budget_ns: int = 100

class SimConfig(BaseModel):
    total_ticks: int = 50
    tick_delay_ms: int = 200


# ─── REST Endpoints ──────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "AcadOS API running", "tick": sim.tick}


@app.post("/jobs")
def create_job(job: JobCreate):
    pcb = PCB(
        pid=job.pid,
        user_id=job.user_id,
        role=Role(job.role),
        job_type=JobType(job.job_type),
        deadline=time.time() + job.deadline_offset,
        cpu_budget_ns=job.cpu_budget_ns,
    )
    sim.jobs[pcb.pid] = pcb

    # Allocate memory (Ragini's module)
    try:
        sim.memory_mgr.allocate_pages(pcb, num_pages=4)
    except MemoryError as e:
        pass  # proceed even if memory is full

    # Request resources (Nikhil's module)
    sim.resource_mgr.register(pcb, {'CPU': 1, 'MEM_BLOCK': 2})
    sim.resource_mgr.request_resources(pcb, {'CPU': 1, 'MEM_BLOCK': 2})

    submit_job(pcb)
    return {"message": f"Job PID={pcb.pid} submitted", "state": pcb.state.name}


@app.get("/jobs")
def list_jobs():
    return [
        {
            "pid": p.pid,
            "user_id": p.user_id,
            "role": p.role.name,
            "job_type": p.job_type.name,
            "state": p.state.name,
            "urgency_score": round(p.urgency_score, 4),
            "cpu_used": p.cpu_used,
            "abuse_flag": p.abuse_flag,
            "cpu_budget_ns": p.cpu_budget_ns,
        }
        for p in sim.jobs.values()
    ]


@app.get("/scheduler/tick")
def manual_tick():
    running, preempted = scheduler_tick(sim.tick)
    result = {
        "tick": sim.tick,
        "running_pid": running.pid if running else None,
        "running_job_type": running.job_type.name if running else None,
        "preempted_pid": preempted.pid if preempted else None,
    }
    if running:
        running.cpu_used += 1
        # Access a page via Ragini's memory module
        try:
            sim.memory_mgr.access_page(running, virtual_page=sim.tick % 4, tick=sim.tick)
        except (MemoryError, KeyError):
            pass
        sim.timeline.append((running.pid, running.job_type.name, sim.tick))
    else:
        sim.timeline.append((-1, "IDLE", sim.tick))
    sim.tick += 1
    return result


@app.post("/scheduler/reset")
def reset():
    sim.reset()
    return {"message": "Simulation reset"}


@app.get("/timeline")
def get_timeline():
    return sim.timeline


@app.post("/gantt")
def generate_gantt():
    os.makedirs("outputs", exist_ok=True)
    plot_gantt(sim.timeline, path="outputs/gantt.png")
    return {"message": "Gantt chart saved to outputs/gantt.png"}


@app.post("/simulation/run")
async def run_simulation(config: SimConfig):
    if sim.running:
        raise HTTPException(400, "Simulation already running")
    sim.running = True

    for t in range(config.total_ticks):
        if not sim.running:
            break
        running, preempted = scheduler_tick(sim.tick)
        if running:
            running.cpu_used += 1
            try:
                sim.memory_mgr.access_page(running, virtual_page=sim.tick % 4, tick=sim.tick)
            except (MemoryError, KeyError):
                pass
            sim.timeline.append((running.pid, running.job_type.name, sim.tick))
        else:
            sim.timeline.append((-1, "IDLE", sim.tick))

        tick_data = {
            "type": "tick",
            "tick": sim.tick,
            "running_pid": running.pid if running else None,
            "running_job_type": running.job_type.name if running else None,
            "preempted_pid": preempted.pid if preempted else None,
            "process_table": [
                {
                    "pid": p.pid,
                    "role": p.role.name,
                    "job_type": p.job_type.name,
                    "state": p.state.name,
                    "urgency": round(p.urgency_score, 4),
                    "cpu_used": p.cpu_used,
                    "abuse_flag": p.abuse_flag,
                }
                for p in sim.jobs.values()
            ],
        }

        dead = []
        for ws in sim.ws_clients:
            try:
                await ws.send_json(tick_data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            sim.ws_clients.remove(ws)

        sim.tick += 1
        await asyncio.sleep(config.tick_delay_ms / 1000.0)

    sim.running = False
    return {"message": f"Simulation complete. {sim.tick} ticks executed."}


@app.post("/simulation/stop")
def stop_simulation():
    sim.running = False
    return {"message": "Simulation stopped"}


# ─── Memory endpoints (Ragini's module — LIVE) ──────────────────────────────

@app.get("/memory/status")
def memory_status():
    mm = sim.memory_mgr
    return {
        "total_frames": mm.total_frames,
        "free_frames": len(mm.free_frames),
        "page_faults": dict(mm.fault_counters),
        "tlb_hits": sum(1 for _ in mm.tlb),  # approximate
        "tlb_misses": sum(mm.fault_counters.values()),
        "page_table_size": sum(len(v) for v in mm.page_table.values()),
    }


# ─── Deadlock endpoints (Nikhil's module — LIVE) ────────────────────────────

@app.get("/deadlock/status")
def deadlock_status():
    rm = sim.resource_mgr
    return {
        "available": dict(rm.available),
        "safe_state": True,  # checked at request time
        "allocation_count": len(rm.allocation),
    }


@app.post("/deadlock/recover")
def trigger_recovery():
    active = [p for p in sim.jobs.values() if p.state != State.EXIT]
    terminated = sim.resource_mgr.deadlock_recover(active)
    return {"terminated_pids": terminated}


# ─── I/O endpoints (Sanat's module — STUBBED, not yet pushed) ───────────────

@app.get("/io/disk")
def disk_status():
    requests = [95, 180, 34, 119, 11, 123, 62, 64, 66]
    head = 50
    # Stub SSTF / C-SCAN until Sanat pushes io_manager.py
    sstf_order = sorted(requests, key=lambda r: abs(r - head))
    cscan_order = sorted([r for r in requests if r >= head]) + sorted(
        [r for r in requests if r < head]
    )
    return {
        "cscan_order": cscan_order,
        "sstf_order": sstf_order,
        "head": head,
        "note": "Stub — waiting for Sanat's io_manager.py"
    }


@app.get("/db/logs")
def db_logs():
    return {
        "logs": [
            {
                "pid": p.pid,
                "user_id": p.user_id,
                "role": p.role.name,
                "job_type": p.job_type.name,
                "cpu_used": p.cpu_used,
            }
            for p in sim.jobs.values()
        ],
        "note": "Stub — real DB via Sanat's io_manager.py"
    }


# ─── WebSocket for live tick streaming ───────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    sim.ws_clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "tick":
                running, preempted = scheduler_tick(sim.tick)
                if running:
                    running.cpu_used += 1
                    sim.timeline.append(
                        (running.pid, running.job_type.name, sim.tick)
                    )
                await ws.send_json({
                    "type": "tick",
                    "tick": sim.tick,
                    "running_pid": running.pid if running else None,
                })
                sim.tick += 1
    except WebSocketDisconnect:
        sim.ws_clients.remove(ws)
