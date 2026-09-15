```python
from hypothesis import strategies as st
import json

# Allowed ASCII chars for unquoted keys
_ASCII_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
_HEX_CHARS = "0123456789abcdefABCDEF"
_OCT_CHARS = "01234567"
_BIN_CHARS = "01"
_DIGITS = "0123456789"

# Utilities
def _wrap_quotes(s):
    return '"' + s.replace('"', '\\"').replace('\n', '\\n') + '"'

# Basic pieces

# Unquoted key (ASCII only, per parser reality)
unquoted_key = st.text(alphabet=_ASCII_KEY_CHARS, min_size=1, max_size=20)

# Quoted key: can be basic or literal quoted
# Basic quoted for keys must not contain raw newline; literal can't contain raw newline either per grammar for single-line literal.
_basic_key_inner = st.lists(
    st.one_of(
        # raw safe chars (no double-quote, no backslash, no CR/LF, no NUL)
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/.: ", min_size=1, max_size=8),
        # control chars except NUL, CR, LF (to hit edge cases)
        st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c not in ("\x00", "\n", "\r")),
        # explicit escape sequences (as two chars) to exercise escapes in keys when quoted
        st.sampled_from(["\\n", "\\t", "\\u00E9", "\\\""])
    ),
    min_size=1, max_size=4
).map("".join)

quoted_key_basic = _basic_key_inner.map(lambda s: '"' + s.replace('"', '\\"') + '"')
quoted_key_literal = _basic_key_inner.map(lambda s: "'" + s.replace("'", "") + "'")  # drop single quotes inside to keep literal simple

quoted_key = st.one_of(quoted_key_basic, quoted_key_literal)

# Simple key: quoted or unquoted
simple_key = st.one_of(quoted_key, unquoted_key)

# Dotted key: join simple keys with dots
dotted_key = st.lists(simple_key, min_size=2, max_size=5).map(lambda parts: ".".join(parts))

# Key strategy for key-value pair: sometimes simple_key, sometimes dotted
key_strategy = st.one_of(simple_key, dotted_key)

# String value generators
# We'll construct string representations (with quotes) possibly malformed (unterminated, doubled delimiter, invalid escapes)

# Helper to make random unicode escape e.g. \uXXXX
def _unicode_escape():
    import random
    return "\\u" + "".join("{:04x}".format(random.randint(0, 0xFFFF))[i:i+4] for i in (0,))[0:4]

# Basic string content: may include raw control characters (except NUL), escapes, unicode, other text, but cannot include raw " or backslash unescaped or newline CR/LF
basic_inner = st.lists(
    st.one_of(
        # normal printable chunk
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_,.:;()[]{} <>/?!@#$%^&*+=|~", min_size=0, max_size=6),
        # control chars except NUL, CR, LF
        st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c not in ("\x00", "\n", "\r")),
        # explicit escape sequences (two-char sequences)
        st.sampled_from(["\\n", "\\t", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\u0000", "\\u263A", "\\U0001F600", "\\q"])  # include invalid \q occasionally
    ),
    min_size=0, max_size=8
).map("".join)

basic_string = st.one_of(
    # proper basic string
    basic_inner.map(lambda s: '"' + s.replace('"', '\\"') + '"'),
    # unterminated basic string (missing closing quote)
    basic_inner.map(lambda s: '"' + s.replace('"', '\\"')),
    # doubled delimiter (e.g. extra leading quote)
    basic_inner.map(lambda s: '""' + s + '"')
)

# Multiline basic string: use triple double quotes, allow newlines and various escapes, sometimes unterminated
ml_basic_inner = st.lists(
    st.one_of(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_,.:;()[]{} <>/?!@#$%^&*+=|~\t", min_size=0, max_size=40),
        st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c != '\x00'),  # allow CR/LF too in multiline
        st.sampled_from(["\\n", "\\t", "\\\"", "\\\\", "\\u263A", "\\U0001F600"])
    ),
    min_size=0, max_size=6
).map("\n".join)  # introduce newlines

ml_basic_string = st.one_of(
    ml_basic_inner.map(lambda s: '"""' + s + '"""'),
    ml_basic_inner.map(lambda s: '"""' + s),  # unterminated
)

# Literal strings (single quoted): no escapes processed; allow control bytes except NUL
literal_inner = st.lists(
    st.one_of(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_,.:;()[]{} <>/?!@#$%^&*+=|~\t", min_size=0, max_size=8),
        st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c not in ("\x00",)),
    ),
    min_size=0, max_size=8
).map("".join)

literal_string = st.one_of(
    literal_inner.map(lambda s: "'" + s.replace("'", "") + "'"),
    literal_inner.map(lambda s: "'" + s.replace("'", "")),  # unterminated
)

ml_literal_inner = st.lists(
    st.one_of(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_,.:;()[]{} <>/?!@#$%^&*+=|~\t", min_size=0, max_size=40),
        st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c != '\x00'),
    ),
    min_size=0, max_size=6
).map("\n".join)

ml_literal_string = st.one_of(
    ml_literal_inner.map(lambda s: "'''" + s + "'''"),
    ml_literal_inner.map(lambda s: "'''" + s)  # unterminated
)

string_value = st.one_of(basic_string, ml_basic_string, literal_string, ml_literal_string)

# Integer strategies
def _insert_underscores(s):
    # randomly insert underscores between digits
    import random
    if len(s) <= 1:
        return s
    parts = []
    for ch in s:
        parts.append(ch)
        if random.random() < 0.15:
            parts.append('_')
    return "".join(parts).strip('_')

decimal_int = st.one_of(
    st.integers(min_value=-10**40, max_value=10**40).map(lambda n: str(n)),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "{:03d}".format(n)),  # leading zeros allowed
    st.integers(min_value=0, max_value=10**18).map(lambda n: _insert_underscores(str(n)))
)

hex_int = st.integers(min_value=0, max_value=2**128).map(lambda n: "0x" + format(n, "x"))
hex_int_underscored = hex_int.map(lambda s: s.replace('a','a_').replace('b','b_') if len(s)>4 else s)

oct_int = st.integers(min_value=0, max_value=2**128).map(lambda n: "0o" + format(n, "o"))
bin_int = st.integers(min_value=0, max_value=2**128).map(lambda n: "0b" + format(n, "b"))

integer_value = st.one_of(decimal_int, hex_int_underscored, oct_int, bin_int)

# Float strategies
float_decimal = st.one_of(
    # simple floats
    st.builds(lambda a,b: f"{a}.{b}", st.integers(min_value=0, max_value=10**6).map(str), st.integers(min_value=0, max_value=10**6).map(str)),
    # 1. and .5 forms
    st.one_of(
        st.integers(min_value=0, max_value=10**6).map(lambda s: str(s) + "."),
        st.integers(min_value=0, max_value=10**6).map(lambda s: "." + str(s))
    ),
    # scientific
    st.floats(allow_infinity=False, allow_nan=False).map(lambda f: ("{:.6e}".format(f)) if abs(f) > 0 else "0e0"),
    # huge exponent
    st.integers(min_value=1, max_value=400).map(lambda e: "1e" + str(e)),
)

float_special = st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan"])

float_value = st.one_of(float_decimal, float_special)

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time: produce strings matching forms, including invalid calendar dates
def _year():
    return st.integers(min_value=1, max_value=9999).map(lambda y: "{:04d}".format(y))

_month = st.integers(min_value=1, max_value=12).map(lambda m: "{:02d}".format(m))
_day = st.integers(min_value=1, max_value=31).map(lambda d: "{:02d}".format(d))
_hour = st.integers(min_value=0, max_value=23).map(lambda h: "{:02d}".format(h))
_minute = st.integers(min_value=0, max_value=59).map(lambda m: "{:02d}".format(m))
_second = st.integers(min_value=0, max_value=59).map(lambda s: "{:02d}".format(s))
_frac = st.integers(min_value=0, max_value=999999999).map(lambda x: "." + str(x))
offset = st.one_of(st.just("Z"), st.builds(lambda s,t: s + ":" + t, st.one_of(st.just("+00"), st.just("-00"), st.integers(min_value=-12, max_value=14).map(lambda h: "{:+03d}".format(h))).map(lambda s: s if s.startswith('+') or s.startswith('-') else '+'+s), _minute))

date_time_value = st.one_of(
    st.builds(lambda y,m,d: f"{y}-{m}-{d}", _year(), _month, _day),  # local date
    st.builds(lambda y,m,d,hh,mm,ss: f"{y}-{m}-{d}T{hh}:{mm}:{ss}", _year(), _month, _day, _hour, _minute, _second),  # local datetime without secfrac/offset
    st.builds(lambda y,m,d,hh,mm,ss,off: f"{y}-{m}-{d} {hh}:{mm}:{ss}{off}", _year(), _month, _day, _hour, _minute, _second, offset),  # offset datetime with space delimiter
    st.builds(lambda hh,mm,ss: f"{hh}:{mm}:{ss}", _hour, _minute, _second)  # local time
)

# Base value strategy (non-recursive)
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value
)

# Now recursive composition for arrays and inline tables
def _array_strategy(inner):
    # inner is a strategy producing value strings (possibly arrays/inline tables as strings too)
    # produce lists of inner, with optional comments/newlines, trailing commas allowed
    def mk_array(lst):
        # lst is list of value strings; sometimes insert newlines and comments
        import random
        if not lst:
            return "[]"
        parts = []
        for v in lst:
            # sometimes wrap with comments/newlines
            if random.random() < 0.2:
                parts.append("\n# comment between\n")
            parts.append(v)
        # join with commas; sometimes double delimiter (e.g., missing comma) or missing comma to create near-malformed
        if random.random() < 0.05 and len(parts) >= 2:
            # missing comma between elements: concatenate last two without comma
            joined = ", ".join(parts)
            joined = joined.replace(", ", " ", 1)
        else:
            joined = ", ".join(parts)
        # sometimes include trailing comma
        if random.random() < 0.15:
            joined = joined + ","
        return "[" + joined + "]"
    return st.lists(inner, min_size=0, max_size=6).map(mk_array)

def _inline_table_strategy(inner):
    # inline tables must not contain newlines per grammar; but we'll sometimes generate newline inside for near-invalid inputs
    def mk_inline(pairs):
        import random
        if not pairs:
            return "{}"
        kvs = []
        for k,v in pairs:
            kvs.append(f"{k} = {v}")
        # sometimes include newline inside inline table (invalid)
        if random.random() < 0.08:
            body = ", ".join(kvs[:len(kvs)//2]) + "\n" + ", ".join(kvs[len(kvs)//2:])
        else:
            body = ", ".join(kvs)
        # allow trailing comma as parser accepts it
        if random.random() < 0.12:
            body = body + ","
        return "{" + body + "}"
    # pairs: (key, inner)
    pair_strategy = st.tuples(st.one_of(quoted_key, unquoted_key), inner)
    return st.lists(pair_strategy, min_size=0, max_size=6).map(mk_inline)

# Build recursive value strategy
value_strategy = st.recursive(
    base_value,
    lambda children: st.one_of(_array_strategy(children), _inline_table_strategy(children)),
    max_leaves=2000
)

# Key-value line generator
def _kv_line(k, v):
    import random
    # random spacing around '=' and sometimes missing equals/doubled equals to create near-malformed
    if random.random() < 0.03:
        return f"{k} {v}"  # missing equals (malformed)
    if random.random() < 0.03:
        return f"{k} == {v}"  # doubled delimiter (malformed)
    # usual proper line
    space_left = " " if random.random() < 0.9 else ""
    space_right = " " if random.random() < 0.9 else ""
    comment = ""
    if random.random() < 0.25:
        comment = "  # " + ("duplicate key" if random.random() < 0.1 else "comment")
    return f"{k}{space_left}={space_right}{v}{comment}"

key_value_line = st.tuples(key_strategy, value_strategy).map(lambda kv: _kv_line(kv[0], kv[1]))

# Table lines: standard [key] or array table [[key]]
def _table_line(kname, double=False):
    import random
    if double:
        # sometimes produce malformed doubled bracket
        if random.random() < 0.03:
            return "[[" + kname + "]"  # missing closing bracket
        return "[[" + kname + "]]"
    else:
        if random.random() < 0.02:
            return "[" + kname + "]]"  # stray token
        return "[" + kname + "]"

standard_table = simple_key.map(lambda k: _table_line(k, double=False))
array_table = simple_key.map(lambda k: _table_line(k, double=True))
table_line = st.one_of(standard_table, array_table)

# Comment-only line
comment_line = st.one_of(
    st.just("# just a comment"),
    st.just("")  # empty line
)

# Expression: key_value, table, or comment
expression = st.one_of(
    key_value_line,
    table_line,
    comment_line
)

# Document: sequence of expressions. Include empty doc, comment-only, no trailing newline sometimes.
def _join_doc(lines):
    import random
    # remove possible empty trailing lines based on random choice
    doc = "\n".join(lines)
    # sometimes insert CRLF
    if random.random() < 0.05:
        doc = doc.replace("\n", "\r\n")
    # sometimes add an extra stray token at end
    if random.random() < 0.02:
        doc = doc + "\n" + "STRAY_TOKEN"
    # sometimes produce duplicate keys by appending again
    if random.random() < 0.05 and len(lines) >= 1:
        doc = doc + "\n" + lines[0]
    # occasionally produce very deep nesting by appending a deep array/inline table expression
    if random.random() < 0.02:
        depth = 0
        # pick depth in interesting band 1500-2048 sometimes
        if random.random() < 0.5:
            depth = 1500 + int(random.random() * 500)
        else:
            depth = int(random.random() * 10)
        # build nested arrays like [[[[...]]]]
        inner = "0"
        for _ in range(depth):
            inner = "[" + inner + "]"
        doc = doc + "\n" + "deep = " + inner
    return doc

document = st.lists(expression, min_size=0, max_size=40).map(_join_doc)

# Final strategy: ensure no raw NUL character in the final string (module must never emit raw NUL)
strategy = document.filter(lambda s: '\x00' not in s)
```