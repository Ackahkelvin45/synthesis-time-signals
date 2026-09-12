# Coverage evaluation (measurement only — not used to steer the loop)

Line coverage of `vendor/json-parser/json.c` over 400 seeded examples each, on a separate non-sanitizer `-fcoverage-mapping` build. The input-set id
is a hash of (strategy source, n, seed); identical ids mean identical inputs,
so the numbers reproduce exactly across machines and script versions:

| Generator | line coverage | input set |
|---|---|---|
| naive baseline (`st.text()`, Step 3) | 42.2% | `3ee9fd92929ffa28` |
| LLM grammar-seeded (evolved, iter-5) | 83.1% | `bc9d33b1241de2ff` |

The grammar-seeded generator reaches **2.0x** the line coverage of random text. Random text still exercises the lexer and
rejection/error paths (hence the non-trivial baseline), but it rarely forms a
parseable value, so it misses the value/number/string/object *construction*
paths that only (near-)valid input reaches — exactly what the grammar-seeded
generator adds. This *measures* an assertion the design rests on; it is not a
steering signal.
