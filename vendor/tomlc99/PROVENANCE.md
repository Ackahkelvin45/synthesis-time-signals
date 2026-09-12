# tomlc99 (target T4, TOML)

- Upstream: https://github.com/cktan/tomlc99 (MIT; LICENSE vendored). The repo
  is marked obsolete upstream (successor tomlc17); it is pinned here as an
  artifact and never modified.
- Pinned commit for the loop target and the coverage builds:
  `29076dfd095bbbbd50a3c1b2760d29f4b83e74ac` (2026-01-30). Files: toml.c,
  toml.h (byte-identical copies).
- Ground-truth bug builds (paper RQ4), under `vendor/tomlc99-bugs/`:
  - `issue50/`: toml.c + toml.h at the PRE-FIX commit `c5d2e37`; fixed by
    `fd82018f7939df1c6fd4c5a064d28221ddbec0d3` ("fix #50: crash on input",
    a NULL check on `subtabstr` in `parse_keyval`). Class: NULL dereference.
    Reproducer (from the issue): `[0]\n0.0=[]\n+.\n`.
  - Recursion stack overflow via unbounded recursion in `parse_array` /
    `parse_keyval` / `parse_inline_table` (issues #94, #95, #97, #99;
    CVE-2026-16634): UNFIXED at the pinned HEAD, so the default build is the
    bug build. Reproducer: `a = ` + `[`*100000 + `1` + `]`*100000.
- Grammar: ANTLR grammars-v4 `toml/TomlLexer.g4` + `toml/TomlParser.g4` at
  grammars-v4 commit `8af0d4c26c` (2026-07-05), vendored verbatim under
  `grammar/`.
