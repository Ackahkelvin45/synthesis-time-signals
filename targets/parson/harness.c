/*
 * harness.c — fuzzing driver for parson's JSON parse entry point (target T2).
 *
 * Exit-code contract (the whole interface the Python runner relies on):
 *
 *   exit 0   VALID   : input accepted as JSON     (json_parse_string != NULL)
 *   exit 2   REJECT  : well-formed rejection of malformed JSON (NOT a bug).
 *                      parson returns NULL with NO error message, so unlike the
 *                      json-parser harness there is no "why rejected" string.
 *   exit 10  SKIP    : harness could not test this input faithfully because it
 *                      contains an embedded NUL (parson has no length-taking
 *                      parse API, so the input would be silently truncated).
 *                      This is a HARNESS LIMITATION, not a parser rejection, so
 *                      it gets its own code and its own bucket in the logs.
 *   exit 11  SKIP    : input exceeded MAX_INPUT_BYTES; skipped for the same
 *                      "not faithfully testable here" reason, logged distinctly.
 *   exit 3   ENVFAIL : allocation failure in the harness itself.
 *   crash            : sanitizer abort or fatal signal. The runner treats ANY
 *                      outcome not in {0,2,10,11,3} — plus timeouts — as a crash.
 *
 * The stdin/exit-code mode, the batch mode and the libFuzzer entry point come
 * from harness/driver.h; this file only defines harness_parse(). Build modes
 * (see harness/build.sh, TARGET=parson) are compiled in and reportable via
 * `--mode`:
 *   default    parse -> free
 *   roundtrip  parse -> serialize -> free   (parson HAS a serializer, unlike
 *              json-parser; its historical overflow bugs lived there, so this
 *              mode adds real bug surface)
 *   control    injects a synthetic crash    (positive control)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "parson.h"
#include "driver.h"

static int harness_parse(const char *buf, size_t len, char *msg, size_t msgcap) {
    (void)msg; (void)msgcap;
    if (memchr(buf, 0, len) != NULL) return 10; /* embedded NUL -> SKIP (harness limit) */

#ifdef POSITIVE_CONTROL
    /* Synthetic bugs, compiled in ONLY under -DPOSITIVE_CONTROL. The default
     * build physically cannot execute this. Not parson bugs. */
    if (strstr(buf, "__CRASH__") != NULL) {
        char *small = (char *)malloc(4);
        memset(small, 'A', 64); /* 64 bytes into a 4-byte buffer */
        volatile char sink = small[0];
        (void)sink;
        free(small);
    }
    if (strstr(buf, "__HANG__") != NULL) {
        for (;;) { }
    }
#endif

    JSON_Value *v = json_parse_string(buf);
    if (v == NULL) {
        return 2; /* clean, well-formed rejection (parson gives no reason) */
    }

#ifdef ROUNDTRIP
    char *out = json_serialize_to_string(v);
    if (out) json_free_serialized_string(out);
#endif

    json_value_free(v);
    return 0; /* accepted */
}
