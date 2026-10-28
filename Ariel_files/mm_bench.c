/*
  mm_bench.c - Simple matrix multiplication benchmark

  Kernels: ijk, kij

  Usage:
    gcc -O2 -static -o mm_bench mm_bench.c -lm
    ./mm_bench <n> <kernel>

  Examples:
    ./mm_bench 64 ijk
    ./mm_bench 128 kij
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>

/* Simple time measurement */
static inline double get_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* Allocate and initialize matrix with random values */
static double* alloc_matrix(int n) {
    double *m = (double*)malloc(n * n * sizeof(double));
    if (!m) {
        fprintf(stderr, "Memory allocation failed\n");
        exit(1);
    }
    for (int i = 0; i < n * n; i++) {
        m[i] = (double)rand() / RAND_MAX;
    }
    return m;
}

/* Zero initialize matrix */
static double* alloc_matrix_zero(int n) {
    double *m = (double*)calloc(n * n, sizeof(double));
    if (!m) {
        fprintf(stderr, "Memory allocation failed\n");
        exit(1);
    }
    return m;
}

/*
 * IJK kernel (row-major, standard triple loop)
 *
 * Access pattern:
 *   A[i][k] - sequential in k (good)
 *   B[k][j] - stride n in k (cache unfriendly)
 *   C[i][j] - reloaded each k iteration
 */
void mm_ijk(double *C, const double *A, const double *B, int n) {
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            double sum = 0.0;
            for (int k = 0; k < n; k++) {
                sum += A[i * n + k] * B[k * n + j];
            }
            C[i * n + j] = sum;
        }
    }
}

/*
 * KIJ kernel (better cache locality for row-major)
 *
 * Access pattern:
 *   A[i][k] - stride n in i, but k is fixed per inner loop
 *   B[k][j] - sequential in j (good)
 *   C[i][j] - sequential in j (good)
 */
void mm_kij(double *C, const double *A, const double *B, int n) {
    /* Zero C first */
    for (int i = 0; i < n * n; i++) {
        C[i] = 0.0;
    }

    for (int k = 0; k < n; k++) {
        for (int i = 0; i < n; i++) {
            double a_ik = A[i * n + k];
            for (int j = 0; j < n; j++) {
                C[i * n + j] += a_ik * B[k * n + j];
            }
        }
    }
}

/* Verify result against reference */
static double verify(const double *C, const double *C_ref, int n) {
    double max_diff = 0.0;
    for (int i = 0; i < n * n; i++) {
        double diff = fabs(C[i] - C_ref[i]);
        if (diff > max_diff) max_diff = diff;
    }
    return max_diff;
}

static void print_usage(const char *prog) {
    printf("Usage: %s <n> <kernel>\n", prog);
    printf("  n      : matrix size (n x n)\n");
    printf("  kernel : ijk or kij\n");
    printf("\nExamples:\n");
    printf("  %s 64 ijk\n", prog);
    printf("  %s 128 kij\n", prog);
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        print_usage(argv[0]);
        return 1;
    }

    int n = atoi(argv[1]);
    const char *kernel = argv[2];

    if (n <= 0 || n > 4096) {
        fprintf(stderr, "Error: n must be between 1 and 4096\n");
        return 1;
    }

    if (strcmp(kernel, "ijk") != 0 && strcmp(kernel, "kij") != 0) {
        fprintf(stderr, "Error: kernel must be 'ijk' or 'kij'\n");
        return 1;
    }

    printf("Matrix Multiplication Benchmark\n");
    printf("================================\n");
    printf("Matrix size: %d x %d\n", n, n);
    printf("Kernel:      %s\n", kernel);
    printf("\n");

    /* Seed random number generator */
    srand(42);

    /* Allocate matrices */
    double *A = alloc_matrix(n);
    double *B = alloc_matrix(n);
    double *C = alloc_matrix_zero(n);
    double *C_ref = alloc_matrix_zero(n);

    /* Compute reference result with ijk */
    mm_ijk(C_ref, A, B, n);

    /* Run selected kernel */
    double t_start, t_end, elapsed;

    printf("Running %s kernel...\n", kernel);

    t_start = get_time();

    if (strcmp(kernel, "ijk") == 0) {
        mm_ijk(C, A, B, n);
    } else {
        mm_kij(C, A, B, n);
    }

    t_end = get_time();
    elapsed = t_end - t_start;

    /* Calculate GFLOP/s (2*n^3 FLOPs for matrix multiply) */
    double flops = 2.0 * (double)n * (double)n * (double)n;
    double gflops = flops / elapsed / 1e9;

    /* Verify correctness */
    double max_diff = verify(C, C_ref, n);

    printf("\n");
    printf("=== RESULTS ===\n");
    printf("Time:        %.6f seconds\n", elapsed);
    printf("GFLOP/s:     %.3f\n", gflops);
    printf("Max error:   %.2e\n", max_diff);
    printf("\n");

    /* Cleanup */
    free(A);
    free(B);
    free(C);
    free(C_ref);

    return 0;
}
