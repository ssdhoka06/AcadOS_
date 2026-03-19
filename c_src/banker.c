#include <stdlib.h>
#include <string.h>

/*
 * Banker's Safety Algorithm
 *
 * available : flat array [n_resources]
 * allocation: flat array [n_processes * n_resources], row-major
 * need      : flat array [n_processes * n_resources], row-major
 *
 * Returns 1 if the system is in a safe state, 0 otherwise.
 */
int is_safe_state(int *available, int *allocation, int *need,
                  int n_processes, int n_resources)
{
    int *work   = (int *)malloc(n_resources * sizeof(int));
    int *finish = (int *)calloc(n_processes, sizeof(int));

    if (!work || !finish) {
        free(work);
        free(finish);
        return 0;
    }

    memcpy(work, available, n_resources * sizeof(int));

    int changed = 1;
    while (changed) {
        changed = 0;
        for (int i = 0; i < n_processes; i++) {
            if (finish[i]) continue;

            int can_run = 1;
            for (int j = 0; j < n_resources; j++) {
                if (need[i * n_resources + j] > work[j]) {
                    can_run = 0;
                    break;
                }
            }

            if (can_run) {
                for (int j = 0; j < n_resources; j++)
                    work[j] += allocation[i * n_resources + j];
                finish[i] = 1;
                changed   = 1;
            }
        }
    }

    int safe = 1;
    for (int i = 0; i < n_processes; i++)
        if (!finish[i]) { safe = 0; break; }

    free(work);
    free(finish);
    return safe;
}
