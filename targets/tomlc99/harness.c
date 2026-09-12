/*
 * harness.c — fuzzing driver for tomlc99's parse entry point (target T4, TOML).
 *
 * Exit-code contract (the whole interface the Python runner relies on):
 *
 *   exit 0   VALID   : input accepted as TOML       (toml_parse != NULL)
 *   exit 2   REJECT  : well-formed rejection (NOT a bug); tomlc99's own error
 *                      string (errbuf) is surfaced as the reason.
 *   exit 10  SKIP    : embedded NUL: toml_parse takes a NUL-terminated string,
 *                      so the input would be silently truncated. A HARNESS
 *                      limitation, not a parser rejection (same as parson).
 *   exit 11  SKIP    : input exceeded MAX_INPUT_BYTES.
 *   exit 3   ENVFAIL : allocation failure in the harness itself.
 *   crash            : sanitizer abort or fatal signal.
 *
 * toml_parse MUTATES its input buffer, so the driver's buffer is copied first
 * (the driver frees its own copy after the call).
 *
 * The stdin/exit-code mode, the batch mode and the libFuzzer entry point come
 * from harness/driver.h; this file only defines harness_parse(). Build modes
 * (harness/build.sh, TARGET=tomlc99): default, control, o2, and the
 * ground-truth bug build `bug-issue50` (vendor/tomlc99-bugs/issue50, the
 * pre-fix source of issue #50). The recursion stack-overflow bugs
 * (#94/#95/#97) are UNFIXED at the pinned HEAD, so `default` is their build.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "toml.h"
#include "driver.h"

static int harness_parse(const char *buf, size_t len, char *msg, size_t msgcap) {
    if (memchr(buf, 0, len) != NULL) return 10; /* embedded NUL -> SKIP (harness limit) */

#ifdef POSITIVE_CONTROL
    /* Synthetic bugs, compiled in ONLY under -DPOSITIVE_CONTROL. Not tomlc99 bugs. */
    if (strstr(buf, "__CRASH__") != NULL) {
        char *small = (char *)malloc(4);
        memset(small, 'A', 64);
        volatile char sink = small[0];
        (void)sink;
        free(small);
    }
    if (strstr(buf, "__HANG__") != NULL) {
        for (;;) { }
    }
#endif

    char *copy = (char *)malloc(len + 1);
    if (!copy) return 3;
    memcpy(copy, buf, len);
    copy[len] = '\0';

    char errbuf[200];
    errbuf[0] = '\0';
    toml_table_t *tab = toml_parse(copy, errbuf, sizeof errbuf);
    free(copy);
    if (tab == NULL) {
        snprintf(msg, msgcap, "%s", errbuf);
        return 2; /* clean, well-formed rejection */
    }
    toml_free(tab);
    return 0; /* accepted */
}
