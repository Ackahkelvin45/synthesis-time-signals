/*
 * harness.c — fuzzing driver for cJSON's length-taking parse entry point (target T5, JSON).
 *
 * Exit-code contract (the whole interface the Python runner relies on):
 *
 *   exit 0   VALID   : input accepted as JSON       (cJSON_ParseWithLength != NULL)
 *   exit 2   REJECT  : well-formed rejection (NOT a bug); the byte offset cJSON
 *                      reports through cJSON_GetErrorPtr is surfaced as the reason.
 *   exit 11  SKIP    : input exceeded MAX_INPUT_BYTES.
 *   exit 3   ENVFAIL : allocation failure in the harness itself.
 *   crash            : sanitizer abort or fatal signal.
 *
 * Like the json-parser harness, the input is handed to the LENGTH-taking API in a
 * buffer of EXACTLY `len` bytes (no terminating NUL): embedded NUL bytes are parsed
 * faithfully rather than truncating the input, and an over-read past the end of
 * the input is a real out-of-bounds access under ASan rather than a read of the
 * driver's terminator. CVE-2023-53154 (the ground-truth bug build) is exactly such
 * an over-read and is only reachable this way.
 *
 * cJSON does not require the whole buffer to be consumed (require_null_terminated
 * = 0), so trailing content after a complete value is ACCEPTED; nesting deeper
 * than CJSON_NESTING_LIMIT (1000) is REJECTED. Both are recorded in the
 * adaptation notes.
 *
 * Build modes (harness/build.sh, TARGET=cjson): default, control, o2, and the
 * ground-truth bug build `bug-cve-2023-53154` (vendor/cjson-bugs/cve-2023-53154).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cJSON.h"
#include "driver.h"

static int harness_parse(const char *buf, size_t len, char *msg, size_t msgcap) {
#ifdef POSITIVE_CONTROL
    /* Synthetic bugs, compiled in ONLY under -DPOSITIVE_CONTROL. Not cJSON bugs. */
    if (memmem(buf, len, "__CRASH__", 9) != NULL) {
        char *small = (char *)malloc(4);
        memset(small, 'A', 64);
        volatile char sink = small[0];
        (void)sink;
        free(small);
    }
    if (memmem(buf, len, "__HANG__", 8) != NULL) {
        for (;;) { }
    }
#endif
    char *exact = (char *)malloc(len ? len : 1);
    if (!exact) return 3;
    memcpy(exact, buf, len);
    const char *end = NULL;
    cJSON *v = cJSON_ParseWithLengthOpts(exact, len, &end, 0);
    if (v == NULL) {
        size_t off = (end && end >= exact) ? (size_t)(end - exact) : 0;
        snprintf(msg, msgcap, "parse error at byte %zu of %zu", off, len);
        free(exact);
        return 2; /* clean, well-formed rejection */
    }
    cJSON_Delete(v);
    free(exact);
    return 0; /* accepted */
}
