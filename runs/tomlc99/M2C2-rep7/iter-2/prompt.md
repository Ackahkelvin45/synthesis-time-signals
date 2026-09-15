Requirements for the `strategy`:
- Generate strings in the TOML grammar below. Use st.recursive (or @st.composite)
  for the grammar's recursive productions — do NOT flatten to a big random string.
- Deliberately cover edge cases of THIS format: empty containers, deep nesting,
  duplicate keys, extreme numeric magnitudes/exponents, escape sequences and
  non-ASCII text, embedded control bytes, and near-valid-but-malformed inputs
  (one missing or doubled delimiter, an unterminated string, a stray token).
- Respect the parser realities in the adaptation notes: arrays and inline
  tables recurse per nesting level and depth up to ~2048 is fine, so concentrate
  interesting depth in that band; NEVER emit a raw NUL byte (the parse API is
  NUL-terminated, so the harness skips such input; `\u0000` inside a string is
  fine). Emit COMPLETE documents (key/value lines, tables, arrays of tables),
  and cover every value kind: strings of all four quoting forms with escapes,
  integers in all bases with underscores and extremes, floats incl. inf/nan,
  booleans, all four date-time forms, arrays and inline tables.
- NOTE: the parser ACCEPTS leading zeros (007), floats like `1.` and `.5`,
  raw control characters in strings and comments, a trailing comma in an
  inline table, and calendar-invalid dates; it REJECTS duplicate keys and
  tables, newlines inside inline tables, and non-ASCII bare keys. Expect those
  outcomes; they are deviations, not defects.
- The output must be `str` (the candidate TOML text; NUL/control chars are ok).
- API pitfall: `st.tuples(a, b)` DRAWS TUPLES, not strings. Always `.map` a tuple
  to a joined string before combining; never pass tuples into `",".join(...)`.

=== TOML grammar (ANTLR) ===
/*
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
  KIND, either express or implied.  See the License for the
  specific language governing permissions and limitations
  under the License.
*/

// $antlr-format alignTrailingComments true, columnLimit 150, maxEmptyLinesToKeep 1, reflowComments false, useTab false
// $antlr-format allowShortRulesOnASingleLine true, allowShortBlocksOnASingleLine true, minEmptyLines 0, alignSemicolons ownLine
// $antlr-format alignColons trailing, singleLineOverrulesHangingColon true, alignLexerCommands true, alignLabels true, alignTrailers true

lexer grammar TomlLexer;

WS               : [ \t]+ -> skip;
NL               : ('\r'? '\n')+;
COMMENT          : '#' (~[\n])*;
L_BRACKET        : '[';
DOUBLE_L_BRACKET : '[[';
R_BRACKET        : ']';
DOUBLE_R_BRACKET : ']]';
EQUALS           : '=' -> pushMode(SIMPLE_VALUE_MODE);
DOT              : '.';
COMMA            : ',';

fragment DIGIT : [0-9];
fragment ALPHA : [A-Za-z];

// strings
fragment ESC     : '\\' (["\\/bfnrt] | UNICODE | EX_UNICODE);
fragment UNICODE : 'u' HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT;
fragment EX_UNICODE:
    'U' HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT
;
BASIC_STRING   : '"' (ESC | ~["\\\n])*? '"';
LITERAL_STRING : '\'' (~['\n])*? '\'';

// keys
UNQUOTED_KEY: (ALPHA | DIGIT | '-' | '_')+;

mode SIMPLE_VALUE_MODE;

VALUE_WS: WS -> skip;

L_BRACE     : '{'       -> mode(INLINE_TABLE_MODE);
ARRAY_START : L_BRACKET -> type(L_BRACKET), mode(ARRAY_MODE);

// booleans
BOOLEAN: ('true' | 'false') -> popMode;

// strings
fragment ML_ESC      : '\\' '\r'? '\n' | ESC;
VALUE_BASIC_STRING   : BASIC_STRING                    -> type(BASIC_STRING), popMode;
ML_BASIC_STRING      : '"""' (ML_ESC | ~["\\])*? '"""' -> popMode;
VALUE_LITERAL_STRING : LITERAL_STRING                  -> type(LITERAL_STRING), popMode;
ML_LITERAL_STRING    : '\'\'\'' (.)*? '\'\'\''         -> popMode;

// floating point numbers
fragment EXP                 : ('e' | 'E') [+-]? ZERO_PREFIXABLE_INT;
fragment ZERO_PREFIXABLE_INT : DIGIT (DIGIT | '_' DIGIT)*;
fragment FRAC                : '.' ZERO_PREFIXABLE_INT;
FLOAT                        : DEC_INT ( EXP | FRAC EXP?) -> popMode;
INF                          : [+-]? 'inf'                -> popMode;
NAN                          : [+-]? 'nan'                -> popMode;

// integers
fragment HEX_DIGIT : [A-Fa-f] | DIGIT;
fragment DIGIT_1_9 : [1-9];
fragment DIGIT_0_7 : [0-7];
fragment DIGIT_0_1 : [0-1];
DEC_INT            : [+-]? (DIGIT | (DIGIT_1_9 (DIGIT | '_' DIGIT)+)) -> popMode;
HEX_INT            : '0x' HEX_DIGIT (HEX_DIGIT | '_' HEX_DIGIT)*      -> popMode;
OCT_INT            : '0o' DIGIT_0_7 (DIGIT_0_7 | '_' DIGIT_0_7)*      -> popMode;
BIN_INT            : '0b' DIGIT_0_1 (DIGIT_0_1 | '_' DIGIT_0_1)*      -> popMode;

// dates
fragment YEAR         : DIGIT DIGIT DIGIT DIGIT;
fragment MONTH        : DIGIT DIGIT;
fragment DAY          : DIGIT DIGIT;
fragment DELIM        : 'T' | 't' | ' ';
fragment HOUR         : DIGIT DIGIT;
fragment MINUTE       : DIGIT DIGIT;
fragment SECOND       : DIGIT DIGIT;
fragment SECFRAC      : '.' DIGIT+;
fragment NUMOFFSET    : ('+' | '-') HOUR ':' MINUTE;
fragment OFFSET       : 'Z' | NUMOFFSET;
fragment PARTIAL_TIME : HOUR ':' MINUTE ':' SECOND SECFRAC?;
fragment FULL_DATE    : YEAR '-' MONTH '-' DAY;
fragment FULL_TIME    : PARTIAL_TIME OFFSET;
OFFSET_DATE_TIME      : FULL_DATE DELIM FULL_TIME    -> popMode;
LOCAL_DATE_TIME       : FULL_DATE DELIM PARTIAL_TIME -> popMode;
LOCAL_DATE            : FULL_DATE                    -> popMode;
LOCAL_TIME            : PARTIAL_TIME                 -> popMode;

mode INLINE_TABLE_MODE;

INLINE_TABLE_WS      : WS    -> skip;
INLINE_TABLE_KEY_DOT : DOT   -> type(DOT);
INLINE_TABLE_COMMA   : COMMA -> type(COMMA);
R_BRACE              : '}'   -> popMode;

INLINE_TABLE_KEY_BASIC_STRING   : BASIC_STRING   -> type(BASIC_STRING);
INLINE_TABLE_KEY_LITERAL_STRING : LITERAL_STRING -> type(LITERAL_STRING);
INLINE_TABLE_KEY_UNQUOTED       : UNQUOTED_KEY   -> type(UNQUOTED_KEY);

INLINE_TABLE_EQUALS: EQUALS -> type(EQUALS), pushMode(SIMPLE_VALUE_MODE);

mode ARRAY_MODE;

ARRAY_WS      : WS      -> skip;
ARRAY_NL      : NL      -> type(NL);
ARRAY_COMMENT : COMMENT -> type(COMMENT);
ARRAY_COMMA   : COMMA   -> type(COMMA);

ARRAY_INLINE_TABLE_START : L_BRACE   -> type(L_BRACE), pushMode(INLINE_TABLE_MODE);
NESTED_ARRAY_START       : L_BRACKET -> type(L_BRACKET), pushMode(ARRAY_MODE);
ARRAY_END                : R_BRACKET -> type(R_BRACKET), popMode;

ARRAY_BOOLEAN: BOOLEAN -> type(BOOLEAN);

ARRAY_BASIC_STRING      : BASIC_STRING      -> type(BASIC_STRING);
ARRAY_ML_BASIC_STRING   : ML_BASIC_STRING   -> type(ML_BASIC_STRING);
ARRAY_LITERAL_STRING    : LITERAL_STRING    -> type(LITERAL_STRING);
ARRAY_ML_LITERAL_STRING : ML_LITERAL_STRING -> type(ML_LITERAL_STRING);

ARRAY_FLOAT : FLOAT -> type(FLOAT);
ARRAY_INF   : INF   -> type(INF);
ARRAY_NAN   : NAN   -> type(NAN);

ARRAY_DEC_INT : DEC_INT -> type(DEC_INT);
ARRAY_HEX_INT : HEX_INT -> type(HEX_INT);
ARRAY_OCT_INT : OCT_INT -> type(OCT_INT);
ARRAY_BIN_INT : BIN_INT -> type(BIN_INT);

ARRAY_OFFSET_DATE_TIME : OFFSET_DATE_TIME -> type(OFFSET_DATE_TIME);
ARRAY_LOCAL_DATE_TIME  : LOCAL_DATE_TIME  -> type(LOCAL_DATE_TIME);
ARRAY_LOCAL_DATE       : LOCAL_DATE       -> type(LOCAL_DATE);
ARRAY_LOCAL_TIME       : LOCAL_TIME       -> type(LOCAL_TIME);

/*
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
  KIND, either express or implied.  See the License for the
  specific language governing permissions and limitations
  under the License.
*/

// $antlr-format alignTrailingComments true, columnLimit 150, minEmptyLines 1, maxEmptyLinesToKeep 1, reflowComments false, useTab false
// $antlr-format allowShortRulesOnASingleLine false, allowShortBlocksOnASingleLine true, alignSemicolons hanging, alignColons hanging

parser grammar TomlParser;

options {
    tokenVocab = TomlLexer;
}

document
    : expression (NL expression)* EOF
    ;

expression
    : key_value comment
    | table comment
    | comment
    ;

comment
    : COMMENT?
    ;

key_value
    : key EQUALS value
    ;

key
    : simple_key
    | dotted_key
    ;

simple_key
    : quoted_key
    | unquoted_key
    ;

unquoted_key
    : UNQUOTED_KEY
    ;

quoted_key
    : BASIC_STRING
    | LITERAL_STRING
    ;

dotted_key
    : simple_key (DOT simple_key)+
    ;

value
    : string
    | integer
    | floating_point
    | bool_
    | date_time
    | array_
    | inline_table
    ;

string
    : BASIC_STRING
    | ML_BASIC_STRING
    | LITERAL_STRING
    | ML_LITERAL_STRING
    ;

integer
    : DEC_INT
    | HEX_INT
    | OCT_INT
    | BIN_INT
    ;

floating_point
    : FLOAT
    | INF
    | NAN
    ;

bool_
    : BOOLEAN
    ;

date_time
    : OFFSET_DATE_TIME
    | LOCAL_DATE_TIME
    | LOCAL_DATE
    | LOCAL_TIME
    ;

array_
    : L_BRACKET array_values? comment_or_nl R_BRACKET
    ;

array_values
    : (comment_or_nl value nl_or_comment COMMA array_values comment_or_nl)
    | comment_or_nl value nl_or_comment COMMA?
    ;

comment_or_nl
    : (COMMENT? NL)*
    ;

nl_or_comment
    : (NL COMMENT?)*
    ;

table
    : standard_table
    | array_table
    ;

standard_table
    : L_BRACKET key R_BRACKET
    ;

inline_table
    : L_BRACE inline_table_keyvals R_BRACE
    ;

inline_table_keyvals
    : inline_table_keyvals_non_empty?
    ;

inline_table_keyvals_non_empty
    : key EQUALS value (COMMA inline_table_keyvals_non_empty)?
    ;

array_table
    : DOUBLE_L_BRACKET key DOUBLE_R_BRACKET
    ;

=== parser adaptation notes ===
# the parser: where the accepted language deviates from the TOML grammar

Target: the parser at the pinned commit (vendor/the parser/PROVENANCE.md), parsed
through `the parse function` on a NUL-terminated buffer (embedded NUL = harness SKIP).
Reference: the ANTLR grammars-v4 TOML grammar handed to the generator, and
Python's `tomllib` (TOML 1.0.0) as the strict oracle. Every line below was
confirmed by running the input through the built harness (2026-09-12); the
probe script and raw outcomes are recorded in DECISIONS.md D22.

## Accepted although the grammar / TOML 1.0 forbids it (MORE LENIENT)

| Input | the parser | strict |
|---|---|---|
| Integer with leading zeros: `a = 007` | accepted | rejected |
| Float with no digit after the dot: `a = 1.` | accepted | rejected |
| Float with no leading digit: `a = .5` | accepted | rejected |
| Raw control character inside a basic string: `a = "x\x01y"` | accepted | rejected |
| Control character inside a comment | accepted | rejected |
| Trailing comma in an inline table: `a = {b = 1,}` | accepted | rejected |
| Calendar-invalid date: `a = 1979-02-30` | accepted (no calendar check) | rejected |
| Deeply nested arrays (2048 levels) | accepted | oracle recursion limit |

These are deviations, not defects: none trips a sanitizer.

## Rejected as the grammar requires (matches strict behaviour)

Duplicate keys and duplicate tables (`key exists`), a table and an array of
tables with the same name, redefining a table through a dotted key, a
newline inside an inline table, an invalid escape (`\q`), a value on the
line after `=`, an unterminated string, a bare key outside `A-Za-z0-9_-`
(Unicode bare keys are rejected: `missing =`).

## Accepted as the grammar allows (no deviation, but worth generating)

`inf`/`nan`/`-inf`; hex/oct/bin integers; `1_000`; integers beyond 64 bits
and `1e309` (accepted, value clamps); `\uXXXX` escapes; literal, multiline
basic and multiline literal strings; raw tabs in strings; local date, local
time, offset date-time, and the space separator `1979-05-27 07:32:00Z`;
mixed-type arrays; trailing comma in an array; multiline arrays with
comments; empty arrays, empty inline tables, empty tables `[t]`, `[[a]]`;
dotted keys, quoted keys, the empty quoted key `"" = 1`; CRLF; tab
indentation; a super-table defined after its sub-table; a 10 000-character
key; documents with no trailing newline; comment-only and empty documents.

## Realities that shape generation

- Nesting: the parser recurses once per nesting level of arrays and inline
  tables. Depth 2048 parses; around 20 000 levels the recursion overflows the
  stack (sanitizer `stack-overflow`), which is the unfixed upstream issue
  (a known issue/a known issue/a known issue, a known issue). The steer band is 1500-2048.
- Embedded NUL bytes cannot be tested (NUL-terminated API): the harness skips
  them; the six-character escape ` ` inside a string is fine.
- On rejection the parser returns an error string (`line N: <reason>`); the
  harness surfaces it. In the paper's anonymized prompt mode these strings
  are withheld from the model.


=== your previous attempt was REJECTED before it ran ===
import: TypeError: deferred() missing 1 required positional argument: 'definition'
Do not repeat this failure. Use only real Hypothesis APIs and keep the module internally consistent.

Return the full module as one ```python code block.