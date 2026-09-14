Requirements for the `strategy`:
- Generate strings in the JSON grammar below. Use st.recursive (or @st.composite)
  for the recursive obj/arr productions — do NOT flatten to a big random string.
- Deliberately cover edge cases: empty {} and [], deep nesting, duplicate keys,
  extreme numeric magnitudes/exponents (including overflow like 1e309), \uXXXX
  and surrogate escapes, embedded NUL/control bytes, and near-valid-but-malformed
  inputs (double commas, missing colons, unterminated strings, leading +/.5/01).
- Respect the parser realities in the adaptation notes: there is NO nesting
  cap (vary depth freely), and bias toward OBJECTS WITH MEMBERS (the stressed
  first-pass path). Emitting a raw NUL byte is allowed and encouraged — the
  harness tests it faithfully.
- NOTE: the parser ACCEPTS duplicate keys, a single trailing comma, non-finite
  numbers, and a lone `-`. These are still valuable edge inputs; expect them to
  be accepted rather than treating acceptance as a defect.
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
# Grammar: source and adaptations for the parser

## Source

`JSON.g4` is taken verbatim from the ANTLR **grammars-v4** repository:
<https://github.com/antlr/grammars-v4/blob/master/json/JSON.g4>
(derived from the reference grammar in *The Definitive ANTLR 4 Reference*, which
follows <https://json.org>). It is the canonical RFC 8259-style JSON grammar:
`value` is one of `STRING | NUMBER | obj | arr | true | false | null`, with
`obj` and `arr` recursive through `value`.

This grammar is the **seed** handed to the LLM in the agentic loop. The notes
below record where **the parser**'s *actual* accepted language differs from
this formal grammar — the gap the LLM must be told about so the generator
targets reality, not the spec. Each item was confirmed empirically against the
pinned build (`8ac4477`) through the `default`/`hunt` harnesses.

Target entry point: `the parse function(&settings, buf, len, error)` with
zero-initialized settings (so `json_enable_comments` is **off**).

## Where the parser is a SUPERSET of the grammar (accepts more — leniencies)

> **Framing (important for grading).** These are **behavioral deltas between
> the parser and RFC 8259**: the parser is *more lenient* than the formal
> grammar. They are **not crashes and not defects to file** — none trips a
> sanitizer; each is an implementation choice. The assignment asks specifically
> for where "the library's real accepted format is a subset/superset/informal
> variant" of the grammar; these are that. Telling this apart from a real
> memory-safety bug is the point.

- **A single trailing comma before `]`/`}` is accepted (CONFIRMED).**
  `[1,2,]` and `{"a":1,}` parse as VALID, though RFC 8259 forbids trailing
  commas. Only *one* trailing comma is tolerated: `[1,,2]`, `[,]`, and `[,1]`
  are all cleanly rejected. A notable leniency and a good generator target.
- **Duplicate object keys are accepted (CONFIRMED).** `{"a":1,"a":2}` parses
  VALID. RFC 8259 says names SHOULD be unique but permits either behavior;
  the parser keeps both. (This is the *opposite* of the reference parser used
  in the original placeholder target, which rejected duplicates — a good
  reminder that "the accepted language" is per-implementation.)
- **Non-finite numbers are accepted (CONFIRMED).** `1e309` and similar overflow
  magnitudes parse VALID (to a `double` `inf`), where a strict RFC reader has no
  representation for them.
- **A lone `-` is accepted as a number (CONFIRMED).** `-` parses VALID even
  though RFC 8259 requires at least one digit.

## Where the parser is a SUBSET / RFC-conformant (accepts less than a lenient reader)

- **Trailing content after a complete value is REJECTED (CONFIRMED).** `1abc`,
  `[]xyz`, `1 garbage`, and `true false` are all rejected — the parser requires
  the whole input to be consumed. (This is RFC-conformant and *stricter* than
  some lenient JSON readers.)
- **Strict number forms.** Leading `+` (`+1`), a leading dot (`.5`), a trailing
  dot (`1.`), leading zeros (`01`), and hex (`0x1F`) are all rejected.
- **No comments / single quotes / bare keys.** With default settings `//x`,
  `/* */1`, `'x'`, and `{a:1}` are rejected. (the parser *can* accept `//` and
  `/* */` comments via the `json_enable_comments` flag, but our harness leaves
  it off, so comments are out of scope for this run.)

## Parser-specific concerns that shape the generator

- **Embedded NUL bytes ARE tested.** Unlike a NUL-terminated `const char *` API,
  the parser `the parse function` takes an explicit **length**, so a `0x00` byte
  is parsed faithfully rather than truncating the input. The generator is
  therefore *free to emit NUL and other control bytes* — NUL handling is a
  classic crash source and is now in scope.
- **No recursion-based depth limit.** the parser uses a two-pass, iterative
  state machine (not recursive descent), so deeply-nested input does **not**
  stack-overflow: `[` × 100000 parses fine. Depth is therefore *not* a crash
  vector here, but deep **object** nesting does stress the first-pass memory
  measurement, which is where the confirmed UB finding lives (see
  `crashes/FINDINGS.md`).
- **Duplicate keys, edge numbers, unicode/surrogate escapes, NUL/control bytes,
  near-valid-but-malformed** — these are the edge classes the assignment calls
  out; they are legal in this grammar and are where the generator should spend
  its budget.

## Adaptation summary for the LLM seed prompt

> Generate strings in the JSON grammar above, targeting the parser
> `the parse function` entry point (comments disabled). There is no nesting-depth
> cap, so vary depth freely, and bias toward **objects with members** (the
> stressed path). NUL and other control bytes are testable — include them.
> Deliberately cover the edge classes: empty `{}`/`[]`, deep nesting, duplicate
> object keys, a single trailing comma, extreme numeric magnitudes and exponents
> (including overflow), `\uXXXX` and `\uD800`-style surrogate escapes, embedded
> NUL/control bytes, and near-valid-but-malformed variants (double commas,
> missing colons, unterminated strings, leading `+`/`.5`/`01` number forms).


=== your previous attempt was REJECTED before it ran ===
import: TypeError: 'OneOfStrategy' object is not callable
Do not repeat this failure. Use only real Hypothesis APIs and keep the module internally consistent.

Return the full module as one ```python code block.