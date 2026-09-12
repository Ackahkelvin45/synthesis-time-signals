/*
 * harness.c — fuzzing driver for json-parser's parse entry point.
 *
 * Exit-code contract (the whole interface the Python runner relies on):
 *
 *   exit 0   VALID   : input accepted as JSON        (json_parse_ex != NULL)
 *   exit 2   REJECT  : well-formed rejection of malformed JSON (NOT a bug);
 *                      the parser's own error string is written to stderr so
 *                      the loop finally has a "why was this rejected" signal.
 *   exit 11  SKIP    : input exceeded MAX_INPUT_BYTES; skipped as "not
 *                      faithfully testable here", logged distinctly.
 *   exit 3   ENVFAIL : allocation failure in the harness itself.
 *   crash            : sanitizer abort or fatal signal. The runner treats ANY
 *                      outcome not in {0,2,11,3} — plus timeouts — as a crash.
 *
 * Why no embedded-NUL SKIP (unlike the parson harness): json-parser's
 * `json_parse_ex(settings, json, LENGTH, error)` takes an explicit length, so a
 * buffer containing NUL bytes is parsed faithfully rather than truncated at the
 * first NUL. NUL handling is a classic crash source, so we now TEST it instead
 * of skipping it.
 *
 * json-parser is parse-only (no serializer), so there is no roundtrip mode.
 *
 * The stdin/exit-code mode, the batch mode (many inputs, one process, coverage
 * checkpoints) and the libFuzzer entry point all come from harness/driver.h;
 * this file only defines harness_parse(). Build modes (see build.sh) are
 * compiled in and reportable via `--mode`, so the runner can VERIFY (not
 * assume) which binary it is talking to and refuse to treat a positive-control
 * crash as a real finding.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "json.h"
#include "driver.h"

static int harness_parse(const char *buf, size_t len, char *msg, size_t msgcap) {
#ifdef POSITIVE_CONTROL
    /* Synthetic bugs, compiled in ONLY under -DPOSITIVE_CONTROL. The default
     * build physically cannot execute this. Triggered by marker inputs so the
     * full pipeline (build -> run -> detect -> capture) can be proven to catch
     * a crash and a hang on this exact target binary. Not json-parser bugs. */
    if (memmem(buf, len, "__CRASH__", 9) != NULL) {
        char *small = (char *)malloc(4);
        memset(small, 'A', 64); /* 64 bytes into a 4-byte buffer */
        volatile char sink = small[0];
        (void)sink;
        free(small);
    }
    if (memmem(buf, len, "__HANG__", 8) != NULL) {
        for (;;) { }
    }
#endif

    json_settings settings;
    memset(&settings, 0, sizeof settings);  /* defaults: malloc/free, no comments */
    char error[json_error_max];
    error[0] = '\0';

    /* Hand the LENGTH-taking API a buffer of exactly `len` bytes. The driver's
     * buffer carries a trailing NUL, and that one extra readable byte would
     * mask the library's historical one-byte over-reads at the end of the
     * input (issues #68 and #78, the paper's ground-truth bugs). An exact
     * heap allocation puts ASan's redzone right after the last input byte. */
    char *exact = (char *)malloc(len ? len : 1);
    if (!exact) return 3;
    memcpy(exact, buf, len);
    json_value *v = json_parse_ex(&settings, exact, len, error);
    free(exact);
    if (v == NULL) {
        /* well-formed rejection: surface the parser's reason (parson gives none) */
        snprintf(msg, msgcap, "%s", error);
        return 2;
    }
    json_value_free(v);
    return 0; /* accepted */
}
