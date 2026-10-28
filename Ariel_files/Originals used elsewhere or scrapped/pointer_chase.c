
/*
 * pointer_chase.c - Memory latency microbenchmark
 *
 * Creates a shuffled linked list in an array, then chases pointers.
 * Working set size is configurable to test different cache levels.
 *
 * Usage:
 *   gcc -O2 -static -o pointer_chase pointer_chase.c
 *   ./pointer_chase <num_nodes> <num_iters>
 *
 * Examples:
 *   ./pointer_chase 1024 1000000    # ~4KB  working set (fits L1)
 *   ./pointer_chase 8192 1000000    # ~32KB working set (spills L1)
 *   ./pointer_chase 65536 500000    # ~256KB working set (spills L2)
 */

#include <stdio.h>
#include <stdlib.h>

/*
 * Fisher-Yates shuffle to create a random cycle through all nodes.
 * This ensures every access is a dependent load (can't be prefetched)
 * and visits every element exactly once per traversal.
 */
void create_random_cycle(int *nodes, int n)
{
    /* Initialize as sequential cycle */
    for (int i = 0; i < n; i++)
    {
        nodes[i] = (i + 1) % n;
    }

    /* Shuffle via random swaps of "next" pointers */
    /* Simple LCG random - deterministic for reproducibility */
    unsigned int seed = 42;
    for (int i = n - 1; i > 0; i--)
    {
        seed = seed * 1103515245 + 12345;
        int j = (seed >> 16) % (i + 1);

        /* Swap where i and j point to */
        int tmp = nodes[i];
        nodes[i] = nodes[j];
        nodes[j] = tmp;
    }
}

volatile int sink; /* Prevent compiler optimization */

int main(int argc, char *argv[])
{
    if (argc != 3)
    {
        printf("Usage: %s <num_nodes> <num_iters>\n", argv[0]);
        printf("  num_nodes: number of array elements (working set = num_nodes * 4 bytes)\n");
        printf("  num_iters: number of pointer chases to perform\n");
        return 1;
    }

    int num_nodes = atoi(argv[1]);
    int num_iters = atoi(argv[2]);

    if (num_nodes <= 1 || num_nodes > (1 << 24))
    {
        fprintf(stderr, "Error: num_nodes must be between 2 and %d\n", 1 << 24);
        return 1;
    }

    printf("Pointer Chase Benchmark\n");
    printf("========================\n");
    printf("Nodes:        %d\n", num_nodes);
    printf("Working set:  %d KB\n", (num_nodes * (int)sizeof(int)) / 1024);
    printf("Iterations:   %d\n", num_iters);
    printf("\n");

    /* Allocate and initialize */
    int *nodes = (int *)malloc(num_nodes * sizeof(int));
    if (!nodes)
    {
        fprintf(stderr, "Memory allocation failed\n");
        return 1;
    }

    create_random_cycle(nodes, num_nodes);

    /* Chase pointers */
    printf("Running pointer chase...\n");

    int idx = 0;
    for (int i = 0; i < num_iters; i++)
    {
        idx = nodes[idx];
    }
    sink = idx;

    printf("Done. Final index: %d\n", idx);

    free(nodes);
    return 0;
}
