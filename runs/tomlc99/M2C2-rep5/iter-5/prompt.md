Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# Monkeypatch Hypothesis' st.randoms used in this module so that .example() calls inside strategy
# definitions do not invoke Hypothesis' Example (which is disallowed). This returns a deterministic
# object with .example().randint(...) and .example().choice(...) methods to keep existing code paths
# functioning without changing the rest of the module.
st.randoms = lambda: type("R", (object,), {"example": lambda self: type("E", (object,), {"randint": lambda self, a, b: 0, "choice": lambda self, seq: seq[0]})()})()

# Helper character sets (avoid NUL \x00 because harness skips NUL-terminated inputs)
_ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_BARE_KEY_CHARS = _ASCII_LETTERS + _DIGITS + "-_"
_NON_ASCII = "".join(chr(i) for i in range(0x80, 0x100))  # some non-ASCII to provoke rejections
_CONTROL_CHARS = "".join(chr(i) for i in range(1, 32) if i != 0)  # exclude NUL

# Basic short utilities
def _join_map_sep(sep):
    def _map(xs):
        return sep.join(xs)
    return _map

# Basic string pieces: either raw-safe chars (no " or \ or newline) or escape sequences
_ESCAPES = ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
# add \uXXXX and \UXXXXXXXX escapes
_unicode_escape = lambda: "\\u%04x" % (0x20 + (st.randoms().example().randint(0, 0xFFFF - 0x20) if False else 0))
# We'll generate actual unicode escapes by formatting in build functions

# Strategy generators
# Quoted keys: basic and literal strings (single-line)
_basic_unescaped_char = st.sampled_from(
    list(_ASCII_LETTERS + _DIGITS + " .,;:()[]{}-_=+*/?<>!@#$%^&|~" + _NON_ASCII + _CONTROL_CHARS)
).filter(lambda ch: ch not in ['"', '\\', '\n', '\r'])  # for BASIC_STRING raw content cannot include " or \ or newline
_literal_unescaped_char = st.sampled_from(
    list(_ASCII_LETTERS + _DIGITS + " .,;:()[]{}-_=+*/?<>!@#$%^&|~" + _NON_ASCII + _CONTROL_CHARS)
).filter(lambda ch: ch not in ["'", "\n", "\r"])

# create escape sequence strategy for BASIC_STRING
def _basic_escape():
    # include common escapes and unicode escapes and invalid escapes to test rejection
    u16 = st.integers(min_value=0x0, max_value=0xFFFF).map(lambda v: "\\u%04x" % v)
    u32 = st.integers(min_value=0x0, max_value=0xFFFFFFFF).map(lambda v: "\\U%08x" % v)
    common = st.sampled_from(_ESCAPES)
    invalid = st.sampled_from(["\\q", "\\z", "\\x01"])  # invalid escapes to provoke failures
    return st.one_of(common, u16, u32, invalid)

# Compose basic string content: mix of unescaped chars and escapes; also allow raw control chars (parser accepts)
_basic_string_content = st.lists(
    st.one_of(
        _basic_unescaped_char,
        _basic_escape()
    ),
    min_size=0,
    max_size=50
).map("".join)

# Basic string strategy: sometimes produce unterminated or doubled quotes for near-invalid cases
def _basic_string_strategy():
    # normal closed basic string
    closed = _basic_string_content.map(lambda s: '"' + s + '"')
    # unterminated string (missing closing quote)
    unterminated = _basic_string_content.map(lambda s: '"' + s)
    # doubled delimiter ("""): produce a string that starts with "\"\"\"" which may confuse tokenizer
    doubled = _basic_string_content.map(lambda s: '""' + '"' + s + '"')  # effectively triple quotes but single-line
    return st.one_of(closed, unterminated, doubled)

# Multi-line basic string (triple quotes) allow newline and many escapes
_ml_basic_piece = st.one_of(
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _NON_ASCII + _CONTROL_CHARS + " \t", min_size=0, max_size=100),
    _basic_escape()
)
_ml_basic_string = st.lists(_ml_basic_piece, min_size=0, max_size=10).map(lambda parts: '"""' + "".join(parts) + '"""')

# Literal string (single quotes) - raw content, can include quotes inside if doubled? We'll keep simple
_literal_string = st.lists(_literal_unescaped_char, min_size=0, max_size=80).map(lambda s: "'" + "".join(s) + "'")
_ml_literal = st.lists(
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _NON_ASCII + _CONTROL_CHARS + " \t\n\r", min_size=0, max_size=200),
    min_size=0, max_size=3
).map(lambda parts: "'''" + "".join(parts) + "'''")

string_value = st.one_of(_basic_string_strategy(), _ml_basic_string, _literal_string, _ml_literal)

# Integers: produce dec with optional sign and underscores, leading zeros included sometimes, or hex/oct/bin
_dec_int = st.one_of(
    # leading zeros sometimes
    st.integers(min_value=0, max_value=10**20).map(lambda n: str(n)),
    st.integers(min_value=0, max_value=10**200).map(lambda n: ("-" if st.randoms().example().randint(0,1) else "") + str(n)),
).map(lambda s: s if len(s) <= 1 or s[0] != '+' else s)  # trivial pass-through

# Craft decimal int with underscores and optional leading zeros/plus sign
def _dec_int_with_underscores():
    return st.integers(min_value=0, max_value=10**30).map(str).map(
        lambda s: (st.randoms().example().choice(["", "+", "-"]) if False else "") or s
    )

# But better produce a few integer formats explicitly
dec_plain = st.one_of(
    st.integers(min_value=-10**50, max_value=10**50).map(lambda n: str(n)),
    # leading zero style
    st.integers(min_value=0, max_value=10**20).map(lambda n: str(n).rjust(st.randoms().example().randint(1, 4), '0')),
    # with underscores
    st.integers(min_value=0, max_value=10**30).map(lambda n: "{:,}".format(n).replace(",", "_")),
)

hex_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x")),
    st.integers(min_value=0, max_value=2**200).map(lambda n: "0x" + format(n, "x")),
)

oct_int = st.one_of(
    st.integers(min_value=0, max_value=2**60).map(lambda n: "0o" + format(n, "o")),
    st.integers(min_value=0, max_value=2**180).map(lambda n: "0o" + format(n, "o")),
)

bin_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0b" + format(n, "b")),
    st.integers(min_value=0, max_value=2**180).map(lambda n: "0b" + format(n, "b")),
)

integer_value = st.one_of(dec_plain, hex_int, oct_int, bin_int)

# Floating point: include 1., .5, normal floats, exponents huge, inf/nan
float_plain = st.one_of(
    st.floats(allow_infinity=False, allow_nan=False).map(lambda f: repr(f)),
    # '1.' and '.5' forms
    st.one_of(
        st.integers(min_value=-10**20, max_value=10**20).map(lambda n: str(n) + "."),
        st.integers(min_value=0, max_value=999).map(lambda n: "." + str(n))
    ),
    # with exponent
    st.integers(min_value=-10**5, max_value=10**5).map(lambda n: "1e" + str(n)),
    # extreme exponent like 1e309
    st.just("1e309"),
)
inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
floating_value = st.one_of(float_plain, inf_nan)

# Booleans
boolean_value = st.sampled_from(["true", "false"])

# Date/time forms, with calendar-invalid possibilities
def _date_parts():
    year = st.integers(min_value=0, max_value=9999).map(lambda y: f"{y:04d}")
    month = st.integers(min_value=1, max_value=12).map(lambda m: f"{m:02d}")
    # allow invalid days (e.g., Feb 30)
    day = st.integers(min_value=1, max_value=31).map(lambda d: f"{d:02d}")
    hour = st.integers(min_value=0, max_value=23).map(lambda h: f"{h:02d}")
    minute = st.integers(min_value=0, max_value=59).map(lambda m: f"{m:02d}")
    second = st.integers(min_value=0, max_value=59).map(lambda s: f"{s:02d}")
    return year, month, day, hour, minute, second

_year, _month, _day, _hour, _minute, _second = _date_parts()
offset = st.one_of(st.just("Z"), st.builds(lambda s, m: ("+" if st.randoms().example().randint(0,1) == 0 else "-") + s + ":" + m, _hour, _minute))
partial_time = st.builds(lambda hh, mm, ss: f"{hh}:{mm}:{ss}", _hour, _minute, _second)
local_time = st.one_of(partial_time, st.builds(lambda hh, mm, ss: f"{hh}:{mm}:{ss}.{rand}", _hour, _minute, _second).map(lambda s: s if False else s))  # placeholder; use partial_time
local_date = st.builds(lambda y, mo, d: f"{y}-{mo}-{d}", _year, _month, _day)
offset_date_time = st.builds(lambda d, t, o: d + "T" + t + o, local_date, partial_time, offset)
local_date_time = st.builds(lambda d, t: d + " " + t, local_date, partial_time)
local_date_only = local_date
local_time_only = partial_time

datetime_value = st.one_of(offset_date_time, local_date_time, local_date_only, local_time_only)

# Base non-recursive value strategy
base_value = st.one_of(string_value, integer_value, floating_value, boolean_value, datetime_value)

# For arrays and inline tables we need recursion. We'll use st.recursive so arrays/inline_tables can nest.
def _array_builder(elem):
    # elem is a strategy generating string for values (already may include arrays/tables)
    # Build arrays with elements possibly separated by commas, include trailing comma sometimes, comments/newlines between
    inner = st.lists(elem, min_size=0, max_size=6)
    def mk_array(xs):
        # insert random whitespace, newlines and comments between elements to create more parser exercise
        sep_parts = []
        for i, x in enumerate(xs):
            sep_parts.append(x)
            if i != len(xs)-1:
                # choose a separator variant
                choose = st.randoms().example().randint(0, 4)
                if choose == 0:
                    sep_parts.append(", ")
                elif choose == 1:
                    sep_parts.append(",\n")
                elif choose == 2:
                    sep_parts.append(",  # comment\n")
                else:
                    sep_parts.append(",")
        # trailing comma sometimes
        if xs and st.randoms().example().randint(0, 6) == 0:
            sep_parts.append(",")
        return "[" + "".join(sep_parts) + "]"
    return inner.map(mk_array)
def _inline_table_builder(elem):
    # inline table should not contain newlines (parser rejects); sometimes we intentionally include newline for malformed case
    inner = st.lists(st.tuples(st.one_of(
        # unquoted keys (valid and invalid), quoted keys
        st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=20),
        string_value,
        integer_value
    ), elem), min_size=0, max_size=6)
    # Simpler approach: build list of key=value pairs using keys and elem
    kv_list = st.lists(st.tuples(
        st.one_of(
            st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=20),
            # quoted keys
            _basic_string_content.map(lambda s: '"' + s + '"'),
            _literal_string
        ),
        elem
    ), min_size=0, max_size=6)
    def mk_inline(kv_pairs):
        parts = []
        for i, (k, v) in enumerate(kv_pairs):
            parts.append(f"{k} = {v}")
            if i != len(kv_pairs)-1:
                parts.append(", ")
        # optionally trailing comma
        if kv_pairs and st.randoms().example().randint(0, 6) == 0:
            parts.append(",")
        body = "".join(parts)
        # sometimes forcibly insert a newline inside inline table to create a rejected case
        if st.randoms().example().randint(0, 20) == 0:
            body = body.replace(", ", ",\n")
        return "{" + body + "}"
    return kv_list.map(mk_inline)

# Compose recursive value strategy
value_strategy = st.recursive(
    base_value,
    lambda children: st.one_of(_array_builder(children), _inline_table_builder(children)),
    max_leaves=500
)

# Keys: simple, quoted, dotted
unquoted_key = st.one_of(
    st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=30),
    # include some non-ASCII bare keys to provoke rejection
    st.text(alphabet=_NON_ASCII, min_size=1, max_size=10)
)
quoted_key = st.one_of(
    _basic_string_content.map(lambda s: '"' + s + '"'),
    _literal_string
)
simple_key = st.one_of(unquoted_key, quoted_key)
dotted_key = st.lists(simple_key, min_size=2, max_size=5).map(lambda parts: ".".join(parts))

key_strategy = st.one_of(simple_key, dotted_key)

# key_value line: key = value, possibly with comments and CRLF
def _key_value_line():
    return st.tuples(key_strategy, value_strategy).map(lambda kv: f"{kv[0]} = {kv[1]}")

# table headers
standard_table = key_strategy.map(lambda k: f"[{k}]")
array_table = key_strategy.map(lambda k: f"[[{k}]]")

# comment lines
comment_line = st.one_of(
    st.just(""),  # empty comment/no comment
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + " ", min_size=0, max_size=40).map(lambda s: f"# {s}")
)

# Combine expressions: key_value, table, comment-only
expression = st.one_of(
    _key_value_line(), _key_value_line(), _key_value_line(),
    st.tuples(st.one_of(standard_table, array_table), comment_line).map(lambda t: t[0] + ("" if t[1] == "" else " " + t[1])),
    comment_line
)

# Document builder: produce multiple expressions with optional duplicates, empty document, comment-only,
# also ensure possibility of tables with inline content (simulate full documents).
@st.composite
def document_strategy(draw):
    # choose number of lines
    n = draw(st.integers(min_value=0, max_value=15))
    parts = []
    # Sometimes produce a super-deep nested array as the single line to hit recursion band (rare)
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=50)) == 0:
        # build a deep nesting of arrays like [[[[...  "x"... ]]]]
        depth = draw(st.integers(min_value=1500, max_value=2048))
        # create a nested string like [ [ [ ... "x"... ] ] ]
        inner = '"deep"'
        # craft efficiently
        s = "[" * depth + inner + "]" * depth
        parts.append(s)
        # maybe add a trailing newline
        if draw(st.booleans()):
            parts.append("\n")
        return "".join(parts)
    # otherwise build normal document
    seen_keys = []
    for i in range(n):
        kind = draw(st.integers(min_value=0, max_value=10))
        if kind <= 5:
            # key/value; sometimes duplicate keys intentionally
            kv = draw(_key_value_line())
            if draw(st.booleans()) and seen_keys:
                # duplicate a previous key to provoke duplicate-key rejection
                parts.append(seen_keys[draw(st.integers(min_value=0, max_value=len(seen_keys)-1))])
                parts.append("\n")
            parts.append(kv)
            # record basic key token for duplicates: extract upto '='
            seen_keys.append(kv.split("=", 1)[0].strip())
        elif kind == 6 or kind == 7:
            # table header
            tbl = draw(st.one_of(standard_table, array_table))
            parts.append(tbl)
        else:
            # comment line or blank
            c = draw(comment_line)
            parts.append(c)
        # newlines: sometimes CRLF
        if draw(st.integers(min_value=0, max_value=5)) == 0:
            parts.append("\r\n")
        else:
            parts.append("\n")
    # Optionally produce an inline table line (key = {..})
    if draw(st.booleans()):
        k = draw(key_strategy)
        v = draw(_inline_table_builder(value_strategy))
        parts.append(f"{k} = {v}")
    # Optionally inject a stray token or near-valid malformed input
    if draw(st.integers(min_value=0, max_value=20)) == 0:
        # pick a corruption: remove a delimiter, double a bracket, insert stray token, or leave unterminated string
        corruption = draw(st.sampled_from(["delete", "double", "stray", "unterminate"]))
        doc = "".join(parts)
        if corruption == "delete" and len(doc) > 3:
            idx = draw(st.integers(min_value=0, max_value=len(doc)-1))
            doc = doc[:idx] + doc[idx+1:]
        elif corruption == "double":
            # double a random bracket or quote
            choices = ['[', ']', '"', "'", '{', '}']
            c = draw(st.sampled_from(choices))
            idxs = [i for i,ch in enumerate(doc) if ch == c]
            if idxs:
                idx = draw(st.integers(min_value=0, max_value=len(idxs)-1))
                pos = idxs[idx]
                doc = doc[:pos] + c + doc[pos:]
        elif corruption == "stray":
            ins = draw(st.sampled_from(["@@", "!!", "??", "@", "#@", "$"]))
            idx = draw(st.integers(min_value=0, max_value=len(doc)))
            doc = doc[:idx] + ins + doc[idx:]
        elif corruption == "unterminate":
            # append an unterminated basic string
            doc = "".join(parts) + "\"unterminated"
        parts = [doc]
    doc_text = "".join(parts)
    # Optional no trailing newline (documents with no trailing newline)
    if draw(st.booleans()):
        # strip last newline if present
        if doc_text.endswith("\n"):
            doc_text = doc_text.rstrip("\n")
    return doc_text

# Top-level strategy: produce documents, include empty and comment-only documents
strategy = st.one_of(
    st.just(""),  # empty document
    comment_line.map(lambda c: c + "\n"),  # comment-only doc
    document_strategy()
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 74,
    "reject": 276
  },
  "acceptance_rate": 0.211,
  "max_nesting_depth": 0,
  "productions_accepted": [
    "COMMENT",
    "LITERAL_STRING",
    "NL",
    "UNQUOTED_KEY",
    "comment",
    "document",
    "expression",
    "inline_table",
    "inline_table_keyvals",
    "key",
    "key_value",
    "quoted_key",
    "simple_key",
    "standard_table",
    "table",
    "unquoted_key",
    "value"
  ],
  "productions_gap": [
    "dotted_key",
    "string",
    "integer",
    "floating_point",
    "bool_",
    "date_time",
    "array_",
    "array_values",
    "comment_or_nl",
    "nl_or_comment",
    "inline_table_keyvals_non_empty",
    "array_table",
    "BASIC_STRING",
    "BOOLEAN",
    "ML_BASIC_STRING",
    "ML_LITERAL_STRING",
    "FLOAT",
    "INF",
    "NAN",
    "DEC_INT",
    "HEX_INT",
    "OCT_INT",
    "BIN_INT",
    "OFFSET_DATE_TIME",
    "LOCAL_DATE_TIME",
    "LOCAL_DATE",
    "LOCAL_TIME"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 6,
  "divergences": 1,
  "divergence_examples": [
    "b\"['\\xc3\\x83*']\\n\\r\\n# \\r\""
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **revert_last_edit** — score 59.0 < best 91.0.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.