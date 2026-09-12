/*
 * driver.h — shared harness driver (paper branch, plan step 4).
 *
 * A target harness #includes this header and defines ONE function:
 *
 *   static int harness_parse(const char *buf, size_t len, char *msg, size_t msgcap);
 *
 * returning the outcome code of the exit-code contract (0 VALID, 2 REJECT,
 * 10 SKIP embedded-NUL, 11 SKIP oversized, 3 ENVFAIL). `msg` may receive a
 * short reason string (the parser's own error text) or be left empty.
 *
 * The driver then provides three entry points on top of it:
 *
 *   1. main (stdin mode, unchanged contract)   ./harness < input
 *      One input on stdin, the outcome as the exit code, a reject reason on
 *      stderr as "reject: <msg>". Sanitizer aborts and fatal signals are
 *      crashes by the runner's rule. This is what the loop and triage use.
 *
 *   2. main --batch [--timeout S] [--checkpoints n1,n2,...] [--profile-prefix P]
 *      Many inputs over stdin in one process: each input is a 4-byte
 *      little-endian length followed by the bytes; the driver answers one
 *      line on stdout per input:  R <index> <code> [<msg>]\n
 *      (msg is sanitized to printable ASCII, whitespace collapsed). A crash
 *      kills the process; the Python side (fuzz/runner.py run_many) reads the
 *      sanitizer report from stderr, classifies the input whose "R" line never
 *      arrived, restarts the process and resumes at the next index. A hang is
 *      cut by an in-process alarm: exit code 124 after `--timeout` seconds
 *      (default 5). Index numbering continues across restarts because the
 *      Python side passes --start-index.
 *      Under -DCOVERAGE_BUILD the driver flushes the LLVM profile counters at
 *      each checkpoint (cumulative, counters are never reset) to
 *      "<prefix>.<n>.profraw", and at exit or on a fatal signal to
 *      "<prefix>.final.profraw", so coverage-vs-inputs curves come from ONE
 *      pass over the inputs.
 *
 *   3. LLVMFuzzerTestOneInput   for libFuzzer / AFL++ (compile with
 *      -fsanitize=fuzzer and -DNO_HARNESS_MAIN) — the community reference row.
 *
 *   --mode prints the compiled HARNESS_MODE (unchanged).
 */
#ifndef HARNESS_DRIVER_H
#define HARNESS_DRIVER_H

#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef HARNESS_MODE
#define HARNESS_MODE "default"
#endif

/* Reject anything larger than this as SKIP (exit 11). */
#ifndef MAX_INPUT_BYTES
#define MAX_INPUT_BYTES (64u * 1024u * 1024u)
#endif

#define HARNESS_MSG_CAP 200
#define HARNESS_TIMEOUT_EXIT 124

static int harness_parse(const char *buf, size_t len, char *msg, size_t msgcap);

/* ---- coverage checkpoints (only in the coverage build) ------------------- */
#ifdef COVERAGE_BUILD
int __llvm_profile_write_file(void);
void __llvm_profile_set_filename(const char *);
static char g_profile_prefix[4096];
static void profile_flush(const char *suffix) {
    if (!g_profile_prefix[0]) return;
    char name[4200];
    snprintf(name, sizeof name, "%s.%s.profraw", g_profile_prefix, suffix);
    __llvm_profile_set_filename(name);
    __llvm_profile_write_file();
}
static void on_fatal_signal(int sig) {
    profile_flush("final");
    signal(sig, SIG_DFL);
    raise(sig);
}
#else
static void profile_flush(const char *suffix) { (void)suffix; }
#endif

/* ---- per-input timeout -------------------------------------------------- */
static void on_alarm(int sig) {
    (void)sig;
    profile_flush("final");
    _exit(HARNESS_TIMEOUT_EXIT);
}

/* ---- stdin mode ---------------------------------------------------------- */
static int read_all_stdin(char **out, size_t *outlen) {
    size_t cap = 1u << 16, len = 0;
    char *buf = (char *)malloc(cap);
    if (!buf) return 3;
    int ch;
    while ((ch = getchar()) != EOF) {
        if (len + 1 >= cap) {
            if (cap >= MAX_INPUT_BYTES) { free(buf); return 11; }
            cap *= 2;
            char *nbuf = (char *)realloc(buf, cap);
            if (!nbuf) { free(buf); return 3; }
            buf = nbuf;
        }
        buf[len++] = (char)ch;
    }
    buf[len] = '\0';
    *out = buf; *outlen = len;
    return 0;
}

static int run_stdin_mode(void) {
    char *buf = NULL; size_t len = 0;
    int rc = read_all_stdin(&buf, &len);
    if (rc != 0) return rc;
    char msg[HARNESS_MSG_CAP]; msg[0] = '\0';
    rc = harness_parse(buf, len, msg, sizeof msg);
    free(buf);
    if (rc == 2 && msg[0]) fprintf(stderr, "reject: %s\n", msg);
    return rc;
}

/* ---- batch mode ---------------------------------------------------------- */
static void print_sanitized(const char *s) {
    int last_space = 1;
    for (; *s; ++s) {
        unsigned char c = (unsigned char)*s;
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
            if (!last_space) { putchar(' '); last_space = 1; }
        } else if (c >= 0x20 && c < 0x7f) {
            putchar((int)c); last_space = 0;
        } else {
            putchar('?'); last_space = 0;
        }
    }
}

static int read_exact(void *dst, size_t n) {
    size_t got = 0;
    while (got < n) {
        size_t r = fread((char *)dst + got, 1, n - got, stdin);
        if (r == 0) return 0;
        got += r;
    }
    return 1;
}

static int run_batch_mode(unsigned timeout_s, const char *checkpoints, size_t start_index) {
    /* parse checkpoint list once */
    size_t cps[64]; int ncp = 0;
    if (checkpoints && *checkpoints) {
        const char *p = checkpoints;
        while (*p && ncp < 64) {
            cps[ncp++] = (size_t)strtoull(p, (char **)&p, 10);
            if (*p == ',') ++p; else break;
        }
    }
    signal(SIGALRM, on_alarm);
#ifdef COVERAGE_BUILD
    signal(SIGSEGV, on_fatal_signal);
    signal(SIGBUS, on_fatal_signal);
    signal(SIGABRT, on_fatal_signal);
    signal(SIGFPE, on_fatal_signal);
    signal(SIGILL, on_fatal_signal);
#endif
    setvbuf(stdout, NULL, _IOLBF, 0);

    size_t index = start_index;   /* global index of the input being processed */
    size_t seen = start_index;    /* inputs processed so far incl. earlier segments */
    uint32_t len32;
    while (read_exact(&len32, 4)) {
        size_t len = len32;
        char *buf = (char *)malloc(len + 1);
        if (!buf) { printf("R %zu 3\n", index); return 3; }
        if (!read_exact(buf, len)) { free(buf); break; }
        buf[len] = '\0';
        int rc;
        char msg[HARNESS_MSG_CAP]; msg[0] = '\0';
        if (len > MAX_INPUT_BYTES) {
            rc = 11;
        } else {
            alarm(timeout_s);
            rc = harness_parse(buf, len, msg, sizeof msg);
            alarm(0);
        }
        free(buf);
        printf("R %zu %d", index, rc);
        if (msg[0]) { putchar(' '); print_sanitized(msg); }
        putchar('\n');
        fflush(stdout);
        ++index; ++seen;
        for (int i = 0; i < ncp; ++i) {
            if (cps[i] == seen) {
                char suf[32]; snprintf(suf, sizeof suf, "%zu", seen);
                profile_flush(suf);
            }
        }
    }
    profile_flush("final");
    return 0;
}

/* ---- libFuzzer / AFL++ entry -------------------------------------------- */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    char *buf = (char *)malloc(size + 1);
    if (!buf) return 0;
    memcpy(buf, data, size);
    buf[size] = '\0';
    char msg[HARNESS_MSG_CAP]; msg[0] = '\0';
    (void)harness_parse(buf, size, msg, sizeof msg);
    free(buf);
    return 0;
}

#ifndef NO_HARNESS_MAIN
int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--mode") == 0) {
        puts(HARNESS_MODE);
        return 0;
    }
    int batch = 0; unsigned timeout_s = 5; const char *cps = NULL; size_t start = 0;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--batch") == 0) batch = 1;
        else if (strcmp(argv[i], "--timeout") == 0 && i + 1 < argc) timeout_s = (unsigned)atoi(argv[++i]);
        else if (strcmp(argv[i], "--checkpoints") == 0 && i + 1 < argc) cps = argv[++i];
        else if (strcmp(argv[i], "--start-index") == 0 && i + 1 < argc) start = (size_t)strtoull(argv[++i], NULL, 10);
#ifdef COVERAGE_BUILD
        else if (strcmp(argv[i], "--profile-prefix") == 0 && i + 1 < argc) {
            strncpy(g_profile_prefix, argv[++i], sizeof g_profile_prefix - 1);
        }
#else
        else if (strcmp(argv[i], "--profile-prefix") == 0 && i + 1 < argc) ++i;
#endif
        else { fprintf(stderr, "unknown argument: %s\n", argv[i]); return 64; }
    }
    if (batch) return run_batch_mode(timeout_s, cps, start);
    return run_stdin_mode();
}
#endif

#endif /* HARNESS_DRIVER_H */
