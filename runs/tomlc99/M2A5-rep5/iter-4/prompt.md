Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# Primitive helpers
ASCII_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
NON_ASCII_CHARS = "".join(chr(i) for i in range(0x80, 0x100))  # some non-ascii bytes mapped to str
# top-level strategy will be named `strategy`
# Build primitive TOML value texts (strings) first.

# Basic content for strings: allow almost any codepoint except NUL (0) and CR (we'll avoid raw CR to reduce surprises).
_char_excluding_nul = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters=["\x00", "\r"])

# textual content without newlines (for BASIC and LITERAL strings that cannot contain raw newlines)
_content_no_newline = st.text(alphabet=_char_excluding_nul, min_size=0, max_size=24).filter(lambda s: "\n" not in s)

def _escape_backslashes_and_quotes(s: str) -> str:
    # escape backslash and double-quote for basic string rendering when we want raw control chars preserved
    return s.replace("\\", "\\\\").replace('"', '\\"')

# Basic (non-multiline) basic string (double-quoted)
basic_string = st.one_of(
    # JSON-escaped variant (ensures proper escapes like \uXXXX, \n, etc.)
    _content_no_newline.map(lambda s: json.dumps(s)),
    # Raw variant that keeps control characters raw but escapes quotes and backslashes
    _content_no_newline.map(lambda s: '"' + _escape_backslashes_and_quotes(s) + '"'),
    # Include some explicit escape sequences embedded (e.g. \u0000 allowed as an escape)
    _content_no_newline.map(lambda s: '"' + _escape_backslashes_and_quotes(s).replace("A", "\\u0041") + '"')
)

# Literal basic string (single-quoted), cannot contain single quote or newline raw
_literal_content = st.text(alphabet=_char_excluding_nul, min_size=0, max_size=24).filter(lambda s: ("'" not in s) and ("\n" not in s))
literal_string = _literal_content.map(lambda s: "'" + s + "'")

# Multiline basic string ("""...""") allows newlines. We build content possibly containing triple quote sequences to exercise near-malformed cases.
_ml_content = st.text(alphabet=_char_excluding_nul, min_size=0, max_size=200)
ml_basic_string = _ml_content.map(lambda s: '"""' + s + '"""')

# Multiline literal string ('''...''') - allows anything including quotes and newlines; can produce near-malformed by embedding endings
ml_literal_string = st.text(min_size=0, max_size=200).map(lambda s: "'''" + s + "'''")

# Integer forms
def _int_with_underscores(n: int) -> str:
    s = str(abs(n))
    if len(s) <= 3:
        r = s
    else:
        # insert underscores every few digits from right
        parts = []
        while s:
            parts.append(s[-3:])
            s = s[:-3]
        r = "_".join(reversed(parts))
    if n < 0:
        r = "-" + r
    return r

dec_int = st.integers(min_value=-10**50, max_value=10**50).map(lambda n: _int_with_underscores(n) if not (n >= 0 and len(str(n)) > 1 and str(n).startswith("0")) else str(n))
# leading-zero decimal like 007 sometimes
leading_zero_dec = st.integers(min_value=0, max_value=999).map(lambda n: str(n).rjust(3, "0"))

hex_int = st.integers(min_value=0, max_value=2**160).map(lambda n: "0x" + format(n, "x"))
oct_int = st.integers(min_value=0, max_value=2**160).map(lambda n: "0o" + format(n, "o"))
bin_int = st.integers(min_value=0, max_value=2**160).map(lambda n: "0b" + format(n, "b"))

# Floats: include .5, 1., scientific, inf, nan
float_regular = st.one_of(
    st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: str(f)),
    st.floats(allow_infinity=False, allow_nan=False, width=64).map(lambda f: str(f)),
    # explicit patterns
    st.tuples(st.integers(min_value=0, max_value=9999), st.integers(min_value=0, max_value=9999)).map(lambda t: f"{t[0]}.{t[1]}"),
    st.integers(min_value=0, max_value=9999).map(lambda i: f"{i}."),  # trailing dot allowed by parser
    st.integers(min_value=0, max_value=9999).map(lambda i: f".{i}")   # leading dot allowed
)

float_extreme = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-9999"),
    st.just("123_456.789_012"),
)

float_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

float_str = st.one_of(float_regular, float_extreme, float_inf_nan)

# Booleans
bool_str = st.sampled_from(["true", "false"])

# Date/time strings: OFFSET_DATE_TIME, LOCAL_DATE_TIME, LOCAL_DATE, LOCAL_TIME
def _zero_pad(n, width=2):
    s = str(n)
    return s.zfill(width)

date_full = st.tuples(st.integers(0,9999), st.integers(1,12), st.integers(1,31)).map(lambda t: f"{t[0]:04d}-{_zero_pad(t[1])}-{_zero_pad(t[2])}")
time_partial = st.tuples(st.integers(0,23), st.integers(0,59), st.integers(0,59), st.integers(0,999999)).map(lambda t: f"{_zero_pad(t[0])}:{_zero_pad(t[1])}:{_zero_pad(t[2])}" + (f".{t[3]}" if t[3] else ""))
offset = st.one_of(st.just("Z"), st.tuples(st.sampled_from(["+","-"]), st.integers(0,23), st.integers(0,59)).map(lambda t: f"{t[0]}{_zero_pad(t[1])}:{_zero_pad(t[2])}"))
offset_date_time = st.tuples(date_full, st.sampled_from(["T","t"," "]), time_partial, offset).map(lambda t: f"{t[0]}{t[1]}{t[2]}{t[3]}")
local_date_time = st.tuples(date_full, st.sampled_from(["T","t"," "]), time_partial).map(lambda t: f"{t[0]}{t[1]}{t[2]}")
local_date = date_full
local_time = time_partial

date_time_str = st.one_of(offset_date_time, local_date_time, local_date, local_time)

# Primitive value strategy: any of the above value texts
primitive_value = st.one_of(
    basic_string,
    literal_string,
    ml_basic_string,
    ml_literal_string,
    dec_int,
    leading_zero_dec,
    hex_int,
    oct_int,
    bin_int,
    float_str,
    bool_str,
    date_time_str
)

# Keys: unquoted (ASCII only), quoted (basic or literal), dotted keys
unquoted_key = st.text(alphabet=ASCII_KEY_CHARS, min_size=1, max_size=40)
quoted_key_basic = basic_string
quoted_key_literal = literal_string
simple_key = st.one_of(unquoted_key, quoted_key_basic, quoted_key_literal)

dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: ".".join(parts))

# Use st.recursive to build arrays and inline tables recursively from primitive_value
def _array_builder(child):
    # produce arrays that can have comments/newlines style by including whitespace and trailing commas occasionally
    return st.lists(child, min_size=0, max_size=6).map(
        lambda items: "[" + (", ".join(items) + ("," if (len(items)>0 and len(items)%2==0) else "")) + "]"
    )

def _inline_table_builder(child):
    # inline table with 0..4 entries, keys unquoted or quoted
    keys = st.lists(st.one_of(unquoted_key, quoted_key_basic, quoted_key_literal), min_size=0, max_size=4)
    return st.tuples(keys, st.lists(child, min_size=0, max_size=4)).map(
        lambda t: "{" + (", ".join(f"{k} = {v}" for k, v in zip(t[0], t[1])) + ("," if len(t[0])>0 and len(t[0])%2==1 else "")) + "}"
    )

# Allow deep nesting by using a large max_leaves
recursive_values = st.recursive(
    primitive_value,
    lambda children: st.one_of(_array_builder(children), _inline_table_builder(children)),
    max_leaves=2000
)

# Expressions at top-level: key_value, table, array_table, comment-only
# Build key_value lines using recursive_values as value
# We will occasionally introduce near-malformed variants (missing =, double =, unterminated string in value, stray token)
_corruption_flag = st.integers(min_value=0, max_value=3).map(lambda i: i == 0)  # ~25% chance of corruption per expression

def _make_key_value():
    def build_kv(kv):
        key, value_text, corrupt = kv
        # possible corruptions if corrupt == True:
        if corrupt:
            # choose a corruption at random via simple heuristics (using deterministic transforms to avoid extra imports)
            # We'll create few corruption types by patterning on key and value lengths.
            # 1) missing equals
            if len(value_text) % 5 == 0:
                line = f"{key} {value_text}"
            # 2) doubled equals
            elif len(value_text) % 5 == 1:
                line = f"{key} == {value_text}"
            # 3) unterminated basic string: remove trailing quote if value_text starts with "
            elif value_text.startswith('"') and len(value_text) > 1:
                if value_text.endswith('"'):
                    line = f"{key} = {value_text[:-1]}"
                else:
                    line = f"{key} = {value_text}"
            # 4) stray token appended
            else:
                line = f"{key} = {value_text} EXTRA"
            return line
        else:
            return f"{key} = {value_text}"
    return st.tuples(dotted_key, recursive_values, _corruption_flag).map(build_kv)

# Table header: [key] or [[key]]
def _make_table():
    def build_table(t):
        kind, key, corrupt = t
        if corrupt:
            # malformed table header variants
            if kind == "std":
                # missing closing bracket
                return "[" + key
            else:
                # extra closing bracket
                return "[[" + key + "]]]"
        else:
            return ("[" + key + "]") if kind == "std" else ("[[" + key + "]]")
    return st.tuples(st.sampled_from(["std", "array"]), dotted_key, _corruption_flag).map(build_table)

# Comments lines
comment_line = st.one_of(
    st.just(""),
    st.text(alphabet=st.characters(blacklist_characters=["\n", "\r"]), min_size=0, max_size=80).map(lambda s: "#" + s)
)

# Build a document: a sequence of expressions. To exercise duplicates we may intentionally duplicate keys occasionally.
def _document_builder():
    # number of top-level expressions
    return st.integers(min_value=0, max_value=12).flatmap(
        lambda n: st.lists(st.one_of(_make_key_value(), _make_table(), comment_line), min_size=n, max_size=n)
    ).map(lambda lines: "\n".join(lines))

# Finally, the top-level strategy: ensure it's a strategy producing str
strategy = _document_builder()
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.