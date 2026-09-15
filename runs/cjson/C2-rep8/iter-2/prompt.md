Requirements for the `strategy`:
- Generate strings in the JSON grammar below. Use st.recursive (or @st.composite)
  for the recursive obj/arr productions — do NOT flatten to a big random string.
- Deliberately cover edge cases: empty {} and [], deep nesting, duplicate keys,
  extreme numeric magnitudes/exponents (including overflow like 1e309), \uXXXX
  and surrogate escapes, embedded NUL/control bytes, and near-valid-but-malformed
  inputs (double commas, missing colons, unterminated strings, leading +/.5/01).
- Respect the parser realities in the adaptation notes: nesting deeper than
  ~1000 levels is cleanly REJECTED, so concentrate interesting depth NEAR that
  limit rather than far beyond it. Emitting a raw NUL byte is allowed and
  encouraged: the parse API takes an explicit length, so the harness tests it
  faithfully. Trailing content after a complete value is ACCEPTED (the parser
  stops at the end of the first value), so do not rely on it to produce
  rejections.
- NOTE: the parser ACCEPTS duplicate keys, trailing content, leading zeros
  (`01`), a trailing dot (`1.`), hex numbers, non-finite magnitudes (1e309),
  raw control and NUL bytes inside strings, and a leading byte-order mark; it
  REJECTS trailing commas, a lone `-`, `+1`, `.5`, the `NaN` and `Infinity`
  words, lone surrogate escapes, and nesting beyond 1000 levels. Expect those
  outcomes; they are deviations, not defects.
- The output must be `str` (the candidate JSON text; NUL/control chars are ok).
- API pitfall: `st.tuples(a, b)` DRAWS TUPLES, not strings. Always `.map` a tuple
  to a joined string before combining; never pass tuples into `",".join(...)`.

=== JSON grammar (ANTLR) ===
/** Taken from "The Definitive ANTLR 4 Reference" by Terence Parr */

// Derived from https://json.org

// $antlr-format alignTrailingComments true, columnLimit 150, minEmptyLines 1, maxEmptyLinesToKeep 1, reflowComments false, useTab false
// $antlr-format allowShortRulesOnASingleLine false, allowShortBlocksOnASingleLine true, alignSemicolons hanging, alignColons hanging

grammar JSON;

json
    : value EOF
    ;

obj
    : '{' pair (',' pair)* '}'
    | '{' '}'
    ;

pair
    : STRING ':' value
    ;

arr
    : '[' value (',' value)* ']'
    | '[' ']'
    ;

value
    : STRING
    | NUMBER
    | obj
    | arr
    | 'true'
    | 'false'
    | 'null'
    ;

STRING
    : '"' (ESC | SAFECODEPOINT)* '"'
    ;

fragment ESC
    : '\\' (["\\/bfnrt] | UNICODE)
    ;

fragment UNICODE
    : 'u' HEX HEX HEX HEX
    ;

fragment HEX
    : [0-9a-fA-F]
    ;

fragment SAFECODEPOINT
    : ~ ["\\\u0000-\u001F]
    ;

NUMBER
    : '-'? INT ('.' [0-9]+)? EXP?
    ;

fragment INT
    // integer part forbids leading 0s (e.g. `01`)
    : '0'
    | [1-9] [0-9]*
    ;

// no leading zeros

fragment EXP
    // exponent number permits leading 0s (e.g. `1e01`)
    : [Ee] [+-]? [0-9]+
    ;

WS
    : [ \t\n\r]+ -> skip
    ;


=== parser adaptation notes ===
# the parser: where the accepted language deviates from the JSON grammar

Target: the parser at the pinned release (see the provenance note), parsed
through the length-taking entry point on a buffer of exactly the input's
length (no terminating NUL). Reference: the ANTLR grammars-v4 JSON grammar
handed to the generator, and Python's `json` module as the strict oracle.
Every line below was confirmed by running the input through the built
harness (2026-09-14, probe table in DECISIONS.md D29).

## Accepted although the grammar / RFC 8259 forbids it (MORE LENIENT)

| Input | the parser | strict |
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

| Input | the parser | strict |
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
- A rejection reports the byte offset the parser stopped at, nothing else.
- No serializer is exercised (parse-only), so the parse-reachable region is
  the parse_* family plus the value allocator and the UTF-16 escape decoder.


=== your previous attempt was REJECTED before it ran ===
strategy does not parse: (unicode error) 'unicodeescape' codec can't decode bytes in position 2-3: truncated \uXXXX escape (<unknown>, line 24)
Do not repeat this failure. Use only real Hypothesis APIs and keep the module internally consistent.

Return the full module as one ```python code block.