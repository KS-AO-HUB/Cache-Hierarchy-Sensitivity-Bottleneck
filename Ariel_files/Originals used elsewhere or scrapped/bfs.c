/*
 * bfs.c - BFS on a random sparse graph (CSR format)
 *
 * Generates a deterministic pseudo-random graph and runs BFS.
 * Irregular memory access pattern stresses cache hierarchy.
 *
 * Usage:
 *   gcc -O2 -static -o bfs bfs.c
 *   ./bfs <num_vertices> <avg_degree>
 *
 * Examples:
 *   ./bfs 4096 6
 *   ./bfs 8192 10
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* CSR graph storage */
int *row_ptr;
int *col_idx;
int *distance;
int *queue;

/*
 * Build a deterministic pseudo-random graph in CSR format.
 * Uses a simple LCG so results are reproducible.
 */
void build_graph(int num_verts, int avg_deg, int *num_edges_out)
{
    int max_edges = num_verts * avg_deg;

    row_ptr = (int *)malloc((num_verts + 1) * sizeof(int));
    col_idx = (int *)malloc(max_edges * sizeof(int));
    distance = (int *)malloc(num_verts * sizeof(int));
    queue = (int *)malloc(num_verts * sizeof(int));

    if (!row_ptr || !col_idx || !distance || !queue)
    {
        fprintf(stderr, "Memory allocation failed\n");
        exit(1);
    }

    unsigned int seed = 12345;
    int edge_count = 0;

    for (int v = 0; v < num_verts; v++)
    {
        row_ptr[v] = edge_count;
        for (int d = 0; d < avg_deg; d++)
        {
            seed = seed * 1103515245 + 12345;
            int neighbor = (seed >> 16) % num_verts;
            if (edge_count < max_edges)
            {
                col_idx[edge_count++] = neighbor;
            }
        }
    }
    row_ptr[num_verts] = edge_count;
    *num_edges_out = edge_count;
}

int bfs(int source, int num_verts)
{
    memset(distance, -1, num_verts * sizeof(int));
    int head = 0, tail = 0;

    distance[source] = 0;
    queue[tail++] = source;

    while (head < tail)
    {
        int v = queue[head++];
        for (int e = row_ptr[v]; e < row_ptr[v + 1]; e++)
        {
            int u = col_idx[e];
            if (distance[u] == -1)
            {
                distance[u] = distance[v] + 1;
                queue[tail++] = u;
            }
        }
    }
    return tail; /* number of reachable vertices */
}

int main(int argc, char *argv[])
{
    if (argc != 3)
    {
        printf("Usage: %s <num_vertices> <avg_degree>\n", argv[0]);
        return 1;
    }

    int num_verts = atoi(argv[1]);
    int avg_deg = atoi(argv[2]);

    if (num_verts <= 0 || num_verts > (1 << 20))
    {
        fprintf(stderr, "Error: num_vertices must be between 1 and %d\n", 1 << 20);
        return 1;
    }
    if (avg_deg <= 0 || avg_deg > 100)
    {
        fprintf(stderr, "Error: avg_degree must be between 1 and 100\n");
        return 1;
    }

    printf("BFS Benchmark\n");
    printf("==============\n");
    printf("Vertices:    %d\n", num_verts);
    printf("Avg degree:  %d\n", avg_deg);

    int num_edges = 0;
    build_graph(num_verts, avg_deg, &num_edges);
    printf("Edges:       %d\n", num_edges);
    printf("\n");

    /* Run BFS from multiple sources for more work */
    printf("Running BFS...\n");
    int total_reached = 0;
    int num_sources = 5;

    for (int s = 0; s < num_sources; s++)
    {
        int source = (s * 997) % num_verts; /* spread out sources */
        int reached = bfs(source, num_verts);
        total_reached += reached;
    }

    printf("Total vertices reached across %d BFS runs: %d\n", num_sources, total_reached);

    free(row_ptr);
    free(col_idx);
    free(distance);
    free(queue);

    return 0;
}
