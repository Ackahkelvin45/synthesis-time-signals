# json-parser ground-truth bug sources (paper RQ4)

Pre-fix copies of udp/json-parser's `json.c`/`json.h`, used only for the bug
campaigns (eval/campaign.py) via `harness/build.sh MODE=bug-<name>`. The pinned
target and the coverage/sanitizer builds use vendor/json-parser (unchanged).

| Bug | Class | Pre-fix commit (vendored here) | Fix commit | Reproducer through the harness |
|---|---|---|---|---|
| issue68 | 1-byte heap over-read on a truncated `\uXXXX` escape at end of input | `b1b09b5` | `b42439a` ("Fix buffer overrun in truncated unicode escape sequences") | `"\uDCB` (a `\u` escape truncated after 3 hex digits; verified: crashes pre-fix, clean REJECT on fixed HEAD) |
| issue78 | 1-byte heap over-read on a truncated literal (`true`/`false`/`null`) at end of input | `08f9746` | `cddc633` (merge of PR #72) | `tru` (verified: crashes the pre-fix build, clean REJECT on the fixed HEAD) |

Both over-reads are one byte PAST the end of the input, so the harness passes
`json_parse_ex` a buffer allocated to EXACTLY the input length (no trailing
NUL), which puts ASan's redzone immediately after the last byte; with the
driver's NUL-terminated buffer the extra readable byte masked them.

The pinned HEAD still carries finding #1's NULL-offset UB idiom (json.c:437),
which predates these commits and would abort on the relevant paths first, so
the bug builds compile with `-fno-sanitize=pointer-overflow` (only that
check; every other sanitizer stays live), exactly as the `hunt` build does.

STATUS (2026-09-12): both positive controls pass. The issue's documented
reproducer did not crash, but a search over truncated `\u` escapes found that
`"\uDCB` (3 hex digits then EOF) triggers the same one-byte over-read; it is
clean on the fixed HEAD. So json-parser contributes TWO ground-truth bugs
(issue68, issue78), tomlc99 two (issue50, recursion); cJSON and libexpat
(Stage 2) bring the rest.
