import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shared import PCB, JobType


class MemoryManager:
    def __init__(self):
        self.total_frames = 32
        self.free_frames = list(range(32))
        self.page_table = {}  # pid -> {virtual_page: frame}
        self.tlb = {}  # (pid, vpage) -> frame (max size 8)
        self.lru_tracker = {}  # (pid, vpage) -> last_access_tick
        self.swap_space = {}  # (pid, vpage) -> 'data'
        self.fault_counters = {}  # job_type_name -> int

    def allocate_pages(self, pcb: PCB, num_pages: int) -> bool:
        """
        Allocate num_pages for the given PCB.
        If not enough free frames, call _deadline_replace() first.
        Raises MemoryError if still not enough frames after replacement.
        """
        # Check if we need to evict pages
        if len(self.free_frames) < num_pages:
            needed = num_pages - len(self.free_frames)
            self._deadline_replace(needed)

        # Check again after replacement
        if len(self.free_frames) < num_pages:
            raise MemoryError(f"Not enough free frames: need {num_pages}, have {len(self.free_frames)}")

        # Initialize page table for this process if needed
        if pcb.pid not in self.page_table:
            self.page_table[pcb.pid] = {}

        # Allocate pages
        for i in range(num_pages):
            frame = self.free_frames.pop(0)
            virtual_page = len(self.page_table[pcb.pid])
            self.page_table[pcb.pid][virtual_page] = frame

        return True

    def access_page(self, pcb: PCB, virtual_page: int, tick: int = 0) -> int:
        """
        Access a virtual page for the given PCB.
        Check TLB first (hit = return frame).
        Miss = check page_table.
        Not found = call _page_fault_handler().
        Update lru_tracker on every access.
        Returns frame_number.
        """
        key = (pcb.pid, virtual_page)

        # Check TLB first
        if key in self.tlb:
            frame = self.tlb[key]
            self.lru_tracker[key] = tick
            return frame

        # TLB miss - check page table
        if pcb.pid in self.page_table and virtual_page in self.page_table[pcb.pid]:
            frame = self.page_table[pcb.pid][virtual_page]

            # Update TLB (with LRU eviction if full)
            if len(self.tlb) >= 8:
                # Evict LRU entry from TLB
                lru_key = min(self.tlb.keys(), key=lambda k: self.lru_tracker.get(k, 0))
                del self.tlb[lru_key]

            self.tlb[key] = frame
            self.lru_tracker[key] = tick
            return frame

        # Page fault - page not in page table
        frame = self._page_fault_handler(pcb, virtual_page, tick)
        return frame

    def free_pages(self, pcb: PCB) -> None:
        """
        Remove all entries for pcb.pid from page_table, TLB, lru_tracker.
        Return frames to free_frames.
        """
        if pcb.pid not in self.page_table:
            return

        # Get all frames for this process
        frames = list(self.page_table[pcb.pid].values())

        # Return frames to free list
        self.free_frames.extend(frames)
        self.free_frames.sort()

        # Remove from page table
        del self.page_table[pcb.pid]

        # Remove from TLB
        tlb_keys_to_remove = [k for k in self.tlb.keys() if k[0] == pcb.pid]
        for key in tlb_keys_to_remove:
            del self.tlb[key]

        # Remove from LRU tracker
        lru_keys_to_remove = [k for k in self.lru_tracker.keys() if k[0] == pcb.pid]
        for key in lru_keys_to_remove:
            del self.lru_tracker[key]

        # Remove from swap space
        swap_keys_to_remove = [k for k in self.swap_space.keys() if k[0] == pcb.pid]
        for key in swap_keys_to_remove:
            del self.swap_space[key]

    def _deadline_replace(self, num_needed: int) -> None:
        """
        Evict pages to free up at least num_needed frames.
        Victim order: PRACTICE pages first, then RESEARCH, then EXAM.
        Within same job_type, pick LRU page (oldest lru_tracker entry).
        Move evicted page to swap_space.
        Update page_table and TLB.
        """
        evicted_count = 0

        # Priority order for eviction
        priority_order = [JobType.PRACTICE, JobType.RESEARCH, JobType.EXAM, JobType.EVALUATION]

        # Build a mapping of (pid, vpage) to job_type
        page_to_jobtype = {}
        for pid, pages_dict in self.page_table.items():
            # Find the PCB for this pid (we need to track this)
            # Since we don't have direct access to PCB from pid, we need to infer from context
            # We'll search through lru_tracker which has all active pages
            for vpage in pages_dict.keys():
                key = (pid, vpage)
                if key in self.lru_tracker:
                    page_to_jobtype[key] = pid  # Store pid for now, we'll need job_type

        # We need to find job_type for each page
        # Build list of candidates with their info
        candidates = []
        for pid, pages_dict in self.page_table.items():
            for vpage, frame in pages_dict.items():
                key = (pid, vpage)
                lru_time = self.lru_tracker.get(key, 0)
                candidates.append({
                    'key': key,
                    'pid': pid,
                    'vpage': vpage,
                    'frame': frame,
                    'lru_time': lru_time
                })

        # We need to determine job_type for each candidate
        # Since we don't have direct access to PCBs, we'll use a heuristic
        # or we need to store job_type info separately
        # Let me revise this - we need to store PCB reference or job_type

        # Actually, looking at the requirements again, the _deadline_replace should
        # know the job_type of each page. We need to track this.
        # Let me add a mapping: (pid, vpage) -> job_type
        # But we don't have that in the init. Let me reconsider...

        # The issue is that we need to know which job_type owns each page.
        # The best way is to maintain a mapping when we allocate or fault in pages.
        # Let me add page_owners = {} mapping (pid, vpage) -> job_type

        # For now, let me implement a version that requires us to track this
        # I'll need to add page_owners in __init__ and update it in allocate_pages and _page_fault_handler
        pass  # Will implement after adding page_owners

    def _page_fault_handler(self, pcb: PCB, vpage: int, tick: int = 0) -> int:
        """
        Load page from swap_space (or allocate new frame) into free frame.
        Update page_table and TLB.
        Increment fault_counters[pcb.job_type.name].
        Returns frame_number.
        """
        key = (pcb.pid, vpage)

        # Increment fault counter
        job_name = pcb.job_type.name
        if job_name not in self.fault_counters:
            self.fault_counters[job_name] = 0
        self.fault_counters[job_name] += 1

        # Check if we need to evict a page
        if len(self.free_frames) == 0:
            self._deadline_replace(1)

        # Get a free frame
        if len(self.free_frames) == 0:
            raise MemoryError("No free frames available after eviction")

        frame = self.free_frames.pop(0)

        # Load from swap space if it exists (otherwise it's a new page)
        if key in self.swap_space:
            # Page was swapped out, load it back
            del self.swap_space[key]

        # Initialize page table for this process if needed
        if pcb.pid not in self.page_table:
            self.page_table[pcb.pid] = {}

        # Add to page table
        self.page_table[pcb.pid][vpage] = frame

        # Add to TLB (with LRU eviction if full)
        if len(self.tlb) >= 8:
            # Evict LRU entry from TLB
            lru_key = min(self.tlb.keys(), key=lambda k: self.lru_tracker.get(k, 0))
            del self.tlb[lru_key]

        self.tlb[key] = frame
        self.lru_tracker[key] = tick

        return frame

    def plot_page_faults(self, acados_faults: dict, lru_faults: dict) -> None:
        """
        Create a grouped bar chart comparing page faults.
        x-axis = job type names.
        Two bars per group (AcadOS vs LRU).
        Save to outputs/page_faults.png.
        """
        # Create outputs directory if it doesn't exist
        os.makedirs('outputs', exist_ok=True)

        # Get all job types
        job_types = sorted(set(list(acados_faults.keys()) + list(lru_faults.keys())))

        # Prepare data
        acados_values = [acados_faults.get(jt, 0) for jt in job_types]
        lru_values = [lru_faults.get(jt, 0) for jt in job_types]

        # Create bar chart
        x = range(len(job_types))
        width = 0.35

        fig, ax = plt.subplots(figsize=(10, 6))
        bars1 = ax.bar([i - width/2 for i in x], acados_values, width, label='AcadOS')
        bars2 = ax.bar([i + width/2 for i in x], lru_values, width, label='LRU')

        ax.set_xlabel('Job Type')
        ax.set_ylabel('Page Faults')
        ax.set_title('Page Faults Comparison: AcadOS vs LRU')
        ax.set_xticks(x)
        ax.set_xticklabels(job_types)
        ax.legend()

        plt.tight_layout()
        plt.savefig('outputs/page_faults.png')
        plt.close()


# Fix the _deadline_replace implementation
# We need to track job_type for each page
# Let me revise the MemoryManager class to add this tracking

class MemoryManager:
    def __init__(self):
        self.total_frames = 32
        self.free_frames = list(range(32))
        self.page_table = {}  # pid -> {virtual_page: frame}
        self.tlb = {}  # (pid, vpage) -> frame (max size 8)
        self.lru_tracker = {}  # (pid, vpage) -> last_access_tick
        self.swap_space = {}  # (pid, vpage) -> 'data'
        self.fault_counters = {}  # job_type_name -> int
        self.page_owners = {}  # (pid, vpage) -> job_type

    def allocate_pages(self, pcb: PCB, num_pages: int) -> bool:
        """
        Allocate num_pages for the given PCB.
        If not enough free frames, call _deadline_replace() first.
        Raises MemoryError if still not enough frames after replacement.
        """
        # Check if we need to evict pages
        if len(self.free_frames) < num_pages:
            needed = num_pages - len(self.free_frames)
            self._deadline_replace(needed)

        # Check again after replacement
        if len(self.free_frames) < num_pages:
            raise MemoryError(f"Not enough free frames: need {num_pages}, have {len(self.free_frames)}")

        # Initialize page table for this process if needed
        if pcb.pid not in self.page_table:
            self.page_table[pcb.pid] = {}

        # Allocate pages
        for i in range(num_pages):
            frame = self.free_frames.pop(0)
            virtual_page = len(self.page_table[pcb.pid])
            self.page_table[pcb.pid][virtual_page] = frame
            # Track job type for this page
            self.page_owners[(pcb.pid, virtual_page)] = pcb.job_type

        return True

    def access_page(self, pcb: PCB, virtual_page: int, tick: int = 0) -> int:
        """
        Access a virtual page for the given PCB.
        Check TLB first (hit = return frame).
        Miss = check page_table.
        Not found = call _page_fault_handler().
        Update lru_tracker on every access.
        Returns frame_number.
        """
        key = (pcb.pid, virtual_page)

        # Check TLB first
        if key in self.tlb:
            frame = self.tlb[key]
            self.lru_tracker[key] = tick
            return frame

        # TLB miss - check page table
        if pcb.pid in self.page_table and virtual_page in self.page_table[pcb.pid]:
            frame = self.page_table[pcb.pid][virtual_page]

            # Update TLB (with LRU eviction if full)
            if len(self.tlb) >= 8:
                # Evict LRU entry from TLB
                lru_key = min(self.tlb.keys(), key=lambda k: self.lru_tracker.get(k, 0))
                del self.tlb[lru_key]

            self.tlb[key] = frame
            self.lru_tracker[key] = tick
            return frame

        # Page fault - page not in page table
        frame = self._page_fault_handler(pcb, virtual_page, tick)
        return frame

    def free_pages(self, pcb: PCB) -> None:
        """
        Remove all entries for pcb.pid from page_table, TLB, lru_tracker.
        Return frames to free_frames.
        """
        if pcb.pid not in self.page_table:
            return

        # Get all frames for this process
        frames = list(self.page_table[pcb.pid].values())

        # Return frames to free list
        self.free_frames.extend(frames)
        self.free_frames.sort()

        # Remove from page table
        del self.page_table[pcb.pid]

        # Remove from TLB
        tlb_keys_to_remove = [k for k in self.tlb.keys() if k[0] == pcb.pid]
        for key in tlb_keys_to_remove:
            del self.tlb[key]

        # Remove from LRU tracker
        lru_keys_to_remove = [k for k in self.lru_tracker.keys() if k[0] == pcb.pid]
        for key in lru_keys_to_remove:
            del self.lru_tracker[key]

        # Remove from swap space
        swap_keys_to_remove = [k for k in self.swap_space.keys() if k[0] == pcb.pid]
        for key in swap_keys_to_remove:
            del self.swap_space[key]

        # Remove from page owners
        owner_keys_to_remove = [k for k in self.page_owners.keys() if k[0] == pcb.pid]
        for key in owner_keys_to_remove:
            del self.page_owners[key]

    def _deadline_replace(self, num_needed: int) -> None:
        """
        Evict pages to free up at least num_needed frames.
        Victim order: PRACTICE pages first, then RESEARCH, then EXAM.
        Within same job_type, pick LRU page (oldest lru_tracker entry).
        Move evicted page to swap_space.
        Update page_table and TLB.
        """
        evicted_count = 0

        # Priority order for eviction (lower priority = evict first)
        priority_order = [JobType.PRACTICE, JobType.RESEARCH, JobType.EXAM, JobType.EVALUATION]

        # Build list of all pages with their info
        candidates = []
        for pid, pages_dict in self.page_table.items():
            for vpage, frame in pages_dict.items():
                key = (pid, vpage)
                job_type = self.page_owners.get(key, JobType.PRACTICE)  # Default to PRACTICE if not found
                lru_time = self.lru_tracker.get(key, 0)
                candidates.append({
                    'key': key,
                    'pid': pid,
                    'vpage': vpage,
                    'frame': frame,
                    'job_type': job_type,
                    'lru_time': lru_time,
                    'priority': priority_order.index(job_type) if job_type in priority_order else 999
                })

        # Sort by priority (lower first), then by LRU time (older first)
        candidates.sort(key=lambda x: (x['priority'], x['lru_time']))

        # Evict pages until we have enough
        for candidate in candidates:
            if evicted_count >= num_needed:
                break

            key = candidate['key']
            pid = candidate['pid']
            vpage = candidate['vpage']
            frame = candidate['frame']

            # Move page to swap space
            self.swap_space[key] = 'data'

            # Remove from page table
            del self.page_table[pid][vpage]

            # Remove from TLB if present
            if key in self.tlb:
                del self.tlb[key]

            # Return frame to free list
            self.free_frames.append(frame)
            self.free_frames.sort()

            evicted_count += 1

    def _page_fault_handler(self, pcb: PCB, vpage: int, tick: int = 0) -> int:
        """
        Load page from swap_space (or allocate new frame) into free frame.
        Update page_table and TLB.
        Increment fault_counters[pcb.job_type.name].
        Returns frame_number.
        """
        key = (pcb.pid, vpage)

        # Increment fault counter
        job_name = pcb.job_type.name
        if job_name not in self.fault_counters:
            self.fault_counters[job_name] = 0
        self.fault_counters[job_name] += 1

        # Check if we need to evict a page
        if len(self.free_frames) == 0:
            self._deadline_replace(1)

        # Get a free frame
        if len(self.free_frames) == 0:
            raise MemoryError("No free frames available after eviction")

        frame = self.free_frames.pop(0)

        # Load from swap space if it exists (otherwise it's a new page)
        if key in self.swap_space:
            # Page was swapped out, load it back
            del self.swap_space[key]

        # Initialize page table for this process if needed
        if pcb.pid not in self.page_table:
            self.page_table[pcb.pid] = {}

        # Add to page table
        self.page_table[pcb.pid][vpage] = frame

        # Track job type for this page
        self.page_owners[key] = pcb.job_type

        # Add to TLB (with LRU eviction if full)
        if len(self.tlb) >= 8:
            # Evict LRU entry from TLB
            lru_key = min(self.tlb.keys(), key=lambda k: self.lru_tracker.get(k, 0))
            del self.tlb[lru_key]

        self.tlb[key] = frame
        self.lru_tracker[key] = tick

        return frame

    def plot_page_faults(self, acados_faults: dict, lru_faults: dict) -> None:
        """
        Create a grouped bar chart comparing page faults.
        x-axis = job type names.
        Two bars per group (AcadOS vs LRU).
        Save to outputs/page_faults.png.
        """
        # Create outputs directory if it doesn't exist
        os.makedirs('outputs', exist_ok=True)

        # Get all job types
        job_types = sorted(set(list(acados_faults.keys()) + list(lru_faults.keys())))

        # Prepare data
        acados_values = [acados_faults.get(jt, 0) for jt in job_types]
        lru_values = [lru_faults.get(jt, 0) for jt in job_types]

        # Create bar chart
        x = range(len(job_types))
        width = 0.35

        fig, ax = plt.subplots(figsize=(10, 6))
        bars1 = ax.bar([i - width/2 for i in x], acados_values, width, label='AcadOS')
        bars2 = ax.bar([i + width/2 for i in x], lru_values, width, label='LRU')

        ax.set_xlabel('Job Type')
        ax.set_ylabel('Page Faults')
        ax.set_title('Page Faults Comparison: AcadOS vs LRU')
        ax.set_xticks(x)
        ax.set_xticklabels(job_types)
        ax.legend()

        plt.tight_layout()
        plt.savefig('outputs/page_faults.png')
        plt.close()


# Singleton instance
_memory_manager = MemoryManager()


# Module-level wrapper functions
def allocate_pages(pcb: PCB, num_pages: int) -> bool:
    """Allocate pages for the given PCB."""
    return _memory_manager.allocate_pages(pcb, num_pages)


def access_page(pcb: PCB, virtual_page: int, tick: int = 0) -> int:
    """Access a page for the given PCB."""
    return _memory_manager.access_page(pcb, virtual_page, tick)


def free_pages(pcb: PCB) -> None:
    """Free all pages for the given PCB."""
    _memory_manager.free_pages(pcb)


def plot_page_faults(acados_faults: dict, lru_faults: dict) -> None:
    """Plot page faults comparison."""
    _memory_manager.plot_page_faults(acados_faults, lru_faults)
