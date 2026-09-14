# cJSON: where the accepted language deviates from the JSON grammar

Target: cJSON at the pinned release (see the provenance note), parsed
through the length-taking entry point on a buffer of exactly the input's
length (no terminating NUL). Reference: the ANTLR grammars-v4 JSON grammar
handed to the generator, and Python's `json` module as the strict oracle.
Every line below was confirmed by running the input through the built
harness (2026-09-14, probe table in DECISIONS.md D29).

## Accepted although the grammar / RFC 8259 forbids it (MORE LENIENT)

| Input | cJSON | strict |
|---|---|---|
| Integer with leading zeros: `01` | accepted | rejected |
| Float with a trailing dot: `1.` | accepted | rejected |
| Hex number: `0x10` | accepted | rejected |
| Trailing content after a complete value: `1abc` | accepted (parsing stops after the first value) | rejected |
| Two top-level values: `1 2` | accepted (second value ignored) | rejected |
| Raw control character inside a string (tab, newline) | accepted | rejected |
| Raw NUL byte inside a string, or after a value | accepted | rejected |
| UTF-8 byte-order mark before the value | accepted | rejected |

These are deviations, not defects: none trips a sanitizer. Because trailing
content is ignored, an input is rejected only if its FIRST value is
malformed; do not rely on junk after a valid value to produce a rejection.

## Rejected although the strict oracle accepts it (STRICTER)

| Input | cJSON | strict |
|---|---|---|
| `NaN` and `Infinity` literals | rejected | accepted (Python extension) |
| Lone surrogate escape: `"\ud800"` | rejected | accepted |
| Nesting deeper than 1000 levels (arrays or objects) | rejected at the 1001st level | accepted |

The nesting limit is a compile-time constant (1000 levels).
Depth 1000 is accepted; 1001 is a clean rejection. Concentrate interesting
depth near, not beyond, that limit.

## Matches strict behaviour

Duplicate object keys (accepted, last wins on lookup), non-finite magnitudes
such as `1e309` (accepted, stored as inf), trailing commas in arrays and
objects (rejected), lone `-`, leading `+`, bare `.5` (rejected), invalid
escapes, single-quoted strings, unquoted keys, empty input (rejected).

## Harness facts

- The length-taking API is used with `require_null_terminated = 0`; an
  embedded NUL byte is parsed faithfully (the harness never truncates).
- A rejection reports the byte offset cJSON stopped at, nothing else.
- No serializer is exercised (parse-only), so the parse-reachable region is
  the parse_* family plus the value allocator and the UTF-16 escape decoder.
