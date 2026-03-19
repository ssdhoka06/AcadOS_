import pytest
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory import MemoryManager
from shared import PCB, Role, JobType, State


class TestMemoryManager:
    """Test suite for MemoryManager class"""

    def test_tlb_hit_no_second_page_fault(self):
        """
        Test that TLB hit on second access to same page results in no second page fault.
        """
        mm = MemoryManager()

        # Create a test PCB
        pcb = PCB(
            pid=1,
            user_id=100,
            role=Role.STUDENT,
            job_type=JobType.PRACTICE,
            deadline=1000.0,
            cpu_budget_ns=1000000
        )

        # First access - should cause page fault
        initial_faults = mm.fault_counters.get('PRACTICE', 0)
        frame1 = mm.access_page(pcb, virtual_page=0, tick=1)
        faults_after_first = mm.fault_counters.get('PRACTICE', 0)

        # Verify page fault occurred
        assert faults_after_first == initial_faults + 1

        # Second access to same page - should be TLB hit, no page fault
        frame2 = mm.access_page(pcb, virtual_page=0, tick=2)
        faults_after_second = mm.fault_counters.get('PRACTICE', 0)

        # Verify no additional page fault
        assert faults_after_second == faults_after_first
        assert frame1 == frame2

        # Verify page is in TLB
        assert (pcb.pid, 0) in mm.tlb
        assert mm.tlb[(pcb.pid, 0)] == frame1

    def test_page_fault_fires_when_page_not_in_table(self):
        """
        Test that page fault fires when page is not in page_table.
        """
        mm = MemoryManager()

        # Create a test PCB
        pcb = PCB(
            pid=2,
            user_id=101,
            role=Role.STUDENT,
            job_type=JobType.RESEARCH,
            deadline=2000.0,
            cpu_budget_ns=2000000
        )

        # Access a page that doesn't exist - should cause page fault
        initial_faults = mm.fault_counters.get('RESEARCH', 0)
        frame = mm.access_page(pcb, virtual_page=5, tick=1)
        faults_after = mm.fault_counters.get('RESEARCH', 0)

        # Verify page fault occurred
        assert faults_after == initial_faults + 1

        # Verify page is now in page table
        assert pcb.pid in mm.page_table
        assert 5 in mm.page_table[pcb.pid]
        assert mm.page_table[pcb.pid][5] == frame

    def test_exam_never_evicted_when_practice_exists(self):
        """
        Test that EXAM pages are NEVER evicted when PRACTICE pages exist.
        Fill all 32 frames with PRACTICE PCBs, then allocate EXAM,
        confirm only PRACTICE frames were evicted.
        """
        mm = MemoryManager()

        # Create PRACTICE PCBs and fill all 32 frames
        practice_pcbs = []
        for i in range(8):  # 8 processes with 4 pages each = 32 frames
            pcb = PCB(
                pid=100 + i,
                user_id=200 + i,
                role=Role.STUDENT,
                job_type=JobType.PRACTICE,
                deadline=3000.0,
                cpu_budget_ns=1000000
            )
            practice_pcbs.append(pcb)
            mm.allocate_pages(pcb, 4)

        # Verify all frames are used
        assert len(mm.free_frames) == 0

        # Access all practice pages to set LRU times
        tick = 1
        for pcb in practice_pcbs:
            for vpage in range(4):
                mm.access_page(pcb, vpage, tick)
                tick += 1

        # Now create an EXAM PCB and allocate pages
        exam_pcb = PCB(
            pid=500,
            user_id=600,
            role=Role.FACULTY,
            job_type=JobType.EXAM,
            deadline=4000.0,
            cpu_budget_ns=5000000
        )

        # Allocate 4 pages for EXAM - should evict PRACTICE pages only
        mm.allocate_pages(exam_pcb, 4)

        # Verify EXAM pages are allocated
        assert exam_pcb.pid in mm.page_table
        assert len(mm.page_table[exam_pcb.pid]) == 4

        # Verify EXAM pages are tracked with correct job type
        for vpage in range(4):
            key = (exam_pcb.pid, vpage)
            assert key in mm.page_owners
            assert mm.page_owners[key] == JobType.EXAM

        # Now try to allocate more PRACTICE pages
        # This should evict existing PRACTICE pages, NOT EXAM pages
        new_practice_pcb = PCB(
            pid=999,
            user_id=888,
            role=Role.STUDENT,
            job_type=JobType.PRACTICE,
            deadline=5000.0,
            cpu_budget_ns=1000000
        )

        mm.allocate_pages(new_practice_pcb, 8)

        # Verify EXAM pages are still in page table (not evicted)
        assert exam_pcb.pid in mm.page_table
        assert len(mm.page_table[exam_pcb.pid]) == 4

        # Verify all EXAM pages are still allocated
        for vpage in range(4):
            assert vpage in mm.page_table[exam_pcb.pid]

    def test_free_pages_returns_frames(self):
        """
        Test that free_pages() returns all frames back to free_frames list.
        """
        mm = MemoryManager()

        # Create a test PCB
        pcb = PCB(
            pid=10,
            user_id=110,
            role=Role.RESEARCHER,
            job_type=JobType.RESEARCH,
            deadline=6000.0,
            cpu_budget_ns=3000000
        )

        # Allocate 8 pages
        initial_free = len(mm.free_frames)
        mm.allocate_pages(pcb, 8)
        after_alloc_free = len(mm.free_frames)

        # Verify frames were allocated
        assert after_alloc_free == initial_free - 8

        # Access some pages to populate TLB and LRU tracker
        for vpage in range(4):
            mm.access_page(pcb, vpage, tick=vpage + 1)

        # Verify entries exist
        assert pcb.pid in mm.page_table
        assert len(mm.page_table[pcb.pid]) == 8
        assert any(k[0] == pcb.pid for k in mm.tlb.keys())
        assert any(k[0] == pcb.pid for k in mm.lru_tracker.keys())

        # Free pages
        mm.free_pages(pcb)

        # Verify all frames returned
        assert len(mm.free_frames) == initial_free

        # Verify all entries removed
        assert pcb.pid not in mm.page_table
        assert not any(k[0] == pcb.pid for k in mm.tlb.keys())
        assert not any(k[0] == pcb.pid for k in mm.lru_tracker.keys())
        assert not any(k[0] == pcb.pid for k in mm.swap_space.keys())
        assert not any(k[0] == pcb.pid for k in mm.page_owners.keys())

    def test_fault_counters_increment(self):
        """
        Test that fault_counters increments correctly on page fault.
        """
        mm = MemoryManager()

        # Create test PCBs for different job types
        pcb_practice = PCB(
            pid=20,
            user_id=120,
            role=Role.STUDENT,
            job_type=JobType.PRACTICE,
            deadline=7000.0,
            cpu_budget_ns=1000000
        )

        pcb_exam = PCB(
            pid=21,
            user_id=121,
            role=Role.FACULTY,
            job_type=JobType.EXAM,
            deadline=8000.0,
            cpu_budget_ns=5000000
        )

        # Initial fault counts should be 0
        assert mm.fault_counters.get('PRACTICE', 0) == 0
        assert mm.fault_counters.get('EXAM', 0) == 0

        # Access pages for PRACTICE (will cause page faults)
        mm.access_page(pcb_practice, 0, tick=1)
        assert mm.fault_counters['PRACTICE'] == 1

        mm.access_page(pcb_practice, 1, tick=2)
        assert mm.fault_counters['PRACTICE'] == 2

        # Access same page again (TLB hit, no fault)
        mm.access_page(pcb_practice, 0, tick=3)
        assert mm.fault_counters['PRACTICE'] == 2  # Should not increment

        # Access pages for EXAM (will cause page faults)
        mm.access_page(pcb_exam, 0, tick=4)
        assert mm.fault_counters['EXAM'] == 1

        mm.access_page(pcb_exam, 1, tick=5)
        assert mm.fault_counters['EXAM'] == 2

        # Verify PRACTICE counter unchanged
        assert mm.fault_counters['PRACTICE'] == 2

    def test_tlb_eviction_when_full(self):
        """
        Test that TLB evicts LRU entry when it reaches max size (8).
        """
        mm = MemoryManager()

        # Create a test PCB
        pcb = PCB(
            pid=30,
            user_id=130,
            role=Role.STUDENT,
            job_type=JobType.PRACTICE,
            deadline=9000.0,
            cpu_budget_ns=2000000
        )

        # Access 9 different pages to fill TLB beyond capacity
        for vpage in range(9):
            mm.access_page(pcb, vpage, tick=vpage + 1)

        # TLB should only have 8 entries (max size)
        assert len(mm.tlb) == 8

        # The oldest entry (page 0) should have been evicted
        assert (pcb.pid, 0) not in mm.tlb

        # The newest 8 entries should be present
        for vpage in range(1, 9):
            assert (pcb.pid, vpage) in mm.tlb

    def test_swap_space_and_page_reload(self):
        """
        Test that evicted pages go to swap_space and can be reloaded.
        """
        mm = MemoryManager()

        # Fill all 32 frames with PRACTICE pages
        practice_pcb = PCB(
            pid=40,
            user_id=140,
            role=Role.STUDENT,
            job_type=JobType.PRACTICE,
            deadline=10000.0,
            cpu_budget_ns=3000000
        )

        mm.allocate_pages(practice_pcb, 32)

        # Access all pages to set LRU times
        for vpage in range(32):
            mm.access_page(practice_pcb, vpage, tick=vpage + 1)

        # Clear TLB to force page table lookups later
        mm.tlb.clear()

        # Allocate pages for a new PCB, forcing eviction
        new_pcb = PCB(
            pid=41,
            user_id=141,
            role=Role.STUDENT,
            job_type=JobType.PRACTICE,
            deadline=11000.0,
            cpu_budget_ns=3000000
        )

        mm.allocate_pages(new_pcb, 4)

        # Some pages should have been evicted to swap_space
        assert len(mm.swap_space) > 0

        # Verify evicted pages are from practice_pcb
        evicted_keys = list(mm.swap_space.keys())
        assert all(k[0] == practice_pcb.pid for k in evicted_keys)

        # Try to access an evicted page - should reload from swap
        evicted_page = evicted_keys[0][1]
        initial_faults = mm.fault_counters.get('PRACTICE', 0)

        frame = mm.access_page(practice_pcb, evicted_page, tick=100)

        # Should cause a page fault and reload from swap
        assert mm.fault_counters['PRACTICE'] > initial_faults

        # Page should be back in page table
        assert evicted_page in mm.page_table[practice_pcb.pid]

        # Page should be removed from swap_space
        assert (practice_pcb.pid, evicted_page) not in mm.swap_space


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
