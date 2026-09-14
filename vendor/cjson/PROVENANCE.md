# cJSON (target T5, JSON; Stage 2)

- Upstream: https://github.com/DaveGamble/cJSON (MIT; LICENSE vendored).
- Pinned release for the loop target and the coverage builds: tag `v1.7.18`,
  commit `acc76239bee01d8e9c858ae2cab296704e52d916`, the first release containing the
  CVE-2023-53154 fix. Files: cJSON.c, cJSON.h (byte-identical copies).
  (The plan named v1.7.17; that release is the VULNERABLE one, found by the
  positive control crashing the default build, so the pin was moved to
  v1.7.18 and v1.7.17 became the bug build.)
- Ground-truth bug build (paper RQ4), under `vendor/cjson-bugs/`:
  - `cve-2023-53154/`: cJSON.c + cJSON.h at tag `v1.7.17`
    (`87d8f0961a01bf09bef98ff89bae9fdec42181ee`, 2023-12), the last release
    before the fix `3ef4e4e730e5efd381be612df41e1ff3f5bb3c32`
    ("Fix heap buffer overflow", fixes #800, 2024-04-30): `parse_object`
    advanced past a trailing comma without checking that a byte exists, so a
    buffer ending in `,` inside an object is read one byte past its end.
    Reachable only through the length-taking API on a buffer that is not
    NUL-terminated, which is how the harness calls it. Class: heap
    buffer over-read. Reproducer: `{"a":1,` (exactly those seven bytes).
- Grammar: the same ANTLR grammars-v4 `json/JSON.g4` as json-parser and parson.
- Vendored 2026-09-14 for the paper's Stage 2; never modified.
