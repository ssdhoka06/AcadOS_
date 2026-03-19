#include <stdint.h>
#include <stdlib.h>

typedef struct {
    int pid;
    int user_id;
    int role;
    int job_type;
    double deadline;
    long long cpu_budget_ns;
    double urgency_score;
    int abuse_flag;
    int state;
    long long cpu_used;
} PCB_C;

PCB_C dummy_pcb = {
    1, 101, 1, 1, 9999999999.0, 5000000000LL, 0.0, 0, 1, 0
};

PCB_C* get_dummy_pcb() {
    return &dummy_pcb;
}
