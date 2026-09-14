```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character classes
# ---------------------------------------------------------------------------

# ASCII letters/digits used in bare keys.
BARE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

# Characters that can appear raw inside strings (no NUL, no newline in basic).
RAW_STRING_CHARS = (
    "".join(chr(c) for c in range(0x20, 0x7F) if chr(c) not in '"\\')
    + "".join(chr(c) for c in range(0x80, 0x2000))
    + "\t"
)

# Control characters (raw, allowed by parser inside strings/comments).
CONTROL_CHARS = "".join(chr(c) for c in range(0x01, 0x20) if c != 0x0A)

# Non-ASCII letters for quoted keys/strings.
NON_ASCII = "".join(chr(c) for c in range(0xA0, 0x300))

# ---------------------------------------------------------------------------
# Escapes
# ---------------------------------------------------------------------------

SIMPLE_ESCAPES = ["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]

def _hex_digits(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

unicode_escape = _hex_digits(4).map(lambda h: "\\u" + h)
ex_unicode_escape = _hex_digits(8).map(lambda h: "\\U" + h)

escape = st.one_of(
    st.sampled_from(SIMPLE_ESCAPES),
    unicode_escape,
    ex_unicode_escape,
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

bare_key = st.text(alphabet=BARE_CHARS, min_size=1, max_size=12)

# occasionally a very long key (the parser accepts ~10000 char keys)
long_bare_key = st.text(alphabet=BARE_CHARS, min_size=500, max_size=2000)

basic_key_body = st.one_of(
    st.text(alphabet=RAW_STRING_CHARS + NON_ASCII, min_size=0, max_size=8),
    st.lists(escape, min_size=1, max_size=3).map("".join),
)
basic_key = basic_key_body.map(lambda s: '"' + s + '"')

literal_key_body = st.text(
    alphabet="".join(chr(c) for c in range(0x20, 0x7F) if chr(c) != "'")
    + NON_ASCII,
    min_size=0,
    max_size=8,
)
literal_key = literal_key_body.map(lambda s: "'" + s + "'")

quoted_key = st.one_of(basic_key, literal_key)

simple_key = st.one_of(
    bare_key,
    long_bare_key,
    quoted_key,
    st.just('""'),  # empty quoted key
)

dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(".".join)

key = st.one_of(simple_key, dotted_key)

# ---------------------------------------------------------------------------
# Integers
# ---------------------------------------------------------------------------

dec_int = st.one_of(
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    st.sampled_from(["0", "007", "00", "-0", "+0", "1_000", "9_223_372_036_854_775_807",
                     "18446744073709551615", "99999999999999999999999999999999"]),
)

hex_int = st.one_of(
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8).map(lambda s: "0x" + s),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF"]),
)

oct_int = st.one_of(
    st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda s: "0o" + s),
    st.sampled_from(["0o0", "0o777", "0o1_2_3"]),
)

bin_int = st.one_of(
    st.text(alphabet="01", min_size=1, max_size=8).map(lambda s: "0b" + s),
    st.sampled_from(["0b0", "0b1010", "0b1_0_1"]),
)

integer = st.one_of(dec_int, hex_int, oct_int, bin_int)

# ---------------------------------------------------------------------------
# Floats
# ---------------------------------------------------------------------------

float_lit = st.one_of(
    st.sampled_from([
        "1.0", "-1.0", "+1.0", "3.14159", "1e10", "1E10", "1e+10", "1e-10",
        "1.5e10", "1.5E-10", "1.", ".5", "0.0", "-0.0", "1_000.000_1",
        "1e309", "1e-309", "6.02e23", "1.0e+308",
    ]),
    st.integers(min_value=-10**6, max_value=10**6).map(lambda n: f"{n}.{abs(n) % 1000}"),
    st.integers(min_value=-10**6, max_value=10**6).map(lambda n: f"{n}e{abs(n) % 100}"),
)

inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

floating_point = st.one_of(float_lit, inf_nan)

# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

local_date = st.sampled_from([
    "1979-05-27", "0000-00-00", "1979-02-30", "9999-12-31", "2024-01-01",
])

local_time = st.sampled_from([
    "07:32:00", "00:00:00", "23:59:59", "07:32:00.999999", "12:00:00.5",
])

offset_date_time = st.sampled_from([
    "1979-05-27T07:32:00Z", "1979-05-27T07:32:00+07:00",
    "1979-05-27 07:32:00Z", "1979-05-27t07:32:00-05:00",
    "1979-05-27T00:32:00.999999-07:00",
])

local_date_time = st.sampled_from([
    "1979-05-27T07:32:00", "1979-05-27 07:32:00", "1979-05-27t07:32:00.999999",
])

date_time = st.one_of(offset_date_time, local_date_time, local_date, local_time)

# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

def _basic_body():
    return st.one_of(
        st.text(alphabet=RAW_STRING_CHARS + NON_ASCII, min_size=0, max_size=20),
        st.lists(escape, min_size=1, max_size=4).map("".join),
        st.text(alphabet=CONTROL_CHARS, min_size=1, max_size=3),
    )

basic_string = _basic_body().map(lambda s: '"' + s + '"')

ml_basic_string = st.one_of(
    st.text(alphabet=RAW_STRING_CHARS + NON_ASCII + "\n", min_size=0, max_size=30),
    st.lists(escape, min_size=1, max_size=3).map("".join),
).map(lambda s: '"""' + s + '"""')

literal_string = st.text(
    alphabet="".join(chr(c) for c in range(0x20, 0x7F) if chr(c) != "'") + NON_ASCII,
    min_size=0,
    max_size=20,
).map(lambda s: "'" + s + "'")

ml_literal_string = st.text(
    alphabet="".join(chr(c) for c in range(0x20, 0x7F) if chr(c) != "'") + NON_ASCII + "\n",
    min_size=0,
    max_size=30,
).map(lambda s: "'''" + s + "'''")

string_value = st.one_of(basic_string, ml_basic_string, literal_string, ml_literal_string)

# ---------------------------------------------------------------------------
# Booleans
# ---------------------------------------------------------------------------

boolean = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _value_leaf():
    return st.one_of(
        string_value,
        integer,
        floating_point,
        boolean,
        date_time,
    )

# inline table key/value pair
def _inline_pair(value_strategy):
    return st.tuples(key, value_strategy).map(lambda kv: kv[0] + " = " + kv[1])

def _inline_table(value_strategy):
    pairs = st.lists(_inline_pair(value_strategy), min_size=0, max_size=4)
    return pairs.map(lambda ps: "{" + ", ".join(ps) + "}")

def _array(value_strategy):
    elems = st.lists(value_strategy, min_size=0, max_size=6)
    return elems.map(lambda es: "[" + ", ".join(es) + "]")

def _value(value_strategy):
    return st.one_of(
        _value_leaf(),
        _array(value_strategy),
        _inline_table(value_strategy),
    )

value = st.recursive(_value_leaf(), _value, max_leaves=40)

# ---------------------------------------------------------------------------
# Key-value lines
# ---------------------------------------------------------------------------

def _key_value():
    return st.tuples(key, value).map(lambda kv: kv[0] + " = " + kv[1])

key_value = _key_value()

# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

comment = st.one_of(
    st.text(
        alphabet="".join(chr(c) for c in range(0x01, 0x7F)),
        min_size=0,
        max_size=20,
    ).map(lambda s: "#" + s),
    st.just("#"),
)

# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

standard_table_header = key.map(lambda k: "[" + k + "]")
array_table_header = key.map(lambda k: "[[" + k + "]]")

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _line():
    return st.one_of(
        key_value,
        comment,
        standard_table_header,
        array_table_header,
    )

def _document():
    lines = st.lists(_line(), min_size=0, max_size=12)
    sep = st.sampled_from(["\n", "\r\n"])
    return st.tuples(lines, sep).map(lambda ls: ls[1].join(ls[0]))

document = _document()

# ---------------------------------------------------------------------------
# Near-valid-but-malformed inputs
# ---------------------------------------------------------------------------

def _malformed():
    return st.one_of(
        # missing closing delimiter
        st.just('a = [1, 2'),
        st.just('a = {b = 1'),
        st.just('a = "unterminated'),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        st.just("[table"),
        st.just("[[array"),
        # doubled delimiter
        st.just('a = [[1, 2]]'),
        st.just('a = {{b = 1}}'),
        st.just('a = "x""'),
        # stray token
        st.just('a = @'),
        st.just('a = '),
        st.just('= 1'),
        st.just('a = 1 = 2'),
        st.just('a = 1 2'),
        st.just('a = 1\n  2'),
        st.just('a = 1\n\n\n'),
        # invalid escape
        st.just('a = "\\q"'),
        # newline inside inline table
        st.just('a = {b = 1,\nc = 2}'),
        # value on line after =
        st.just('a =\n1'),
        # duplicate keys / tables
        st.just('a = 1\na = 2'),
        st.just('[t]\n[t]'),
        st.just('[[a]]\n[[a]]'),
        st.just('[a]\n[a.b]\n[a]'),
        # non-ascii bare key
        st.just('café = 1'),
        st.just('naïve = 1'),
        # bare key with invalid char
        st.just('a$b = 1'),
        st.just('a b = 1'),
        # empty key line
        st.just(' = 1'),
        st.just('= 1'),
        # comment with stray closing
        st.just(']'),
        st.just('}'),
        st.just('a = ]'),
    )

malformed = _malformed()

# ---------------------------------------------------------------------------
# Deep nesting (depth 1500-2048)
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth

def _deep_inline_table(depth):
    return "{" + "a = " * 0 + "{" * 0  # placeholder; use nested arrays

deep_nesting = st.integers(min_value=1500, max_value=2048).flatmap(
    lambda d: st.just("a = " + _deep_array(d))
)

# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

edge_cases = st.one_of(
    st.just(""),
    st.just("\n"),
    st.just("\r\n"),
    st.just("\t\n"),
    st.just("# only comment"),
    st.just("# comment\n"),
    st.just("a = 1"),
    st.just("a = 1\n"),
    st.just("a=1"),  # no spaces
    st.just("  a  =  1  "),
    st.just("a = []"),
    st.just("a = {}"),
    st.just("[t]"),
    st.just("[t]\n"),
    st.just("[[a]]"),
    st.just("[[a]]\n"),
    st.just('"" = 1'),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just('a = "x\x01y"'),
    st.just("a = {b = 1,}"),
    st.just("a = 1979-02-30"),
    st.just("a = 1e309"),
    st.just("a = 18446744073709551615"),
    st.just("a = -9223372036854775808"),
    st.just('a = "\\u0000"'),
    st.just('a = "\\U0001F600"'),
    st.just("a = 1_000_000"),
    st.just("a = 0xDEADBEEF"),
    st.just("a = 0o777"),
    st.just("a = 0b1010"),
    st.just("a = inf"),
    st.just("a = -inf"),
    st.just("a = nan"),
    st.just("a = true"),
    st.just("a = false"),
    st.just("a = true\nb = false"),
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    document,
    malformed,
    edge_cases,
    deep_nesting,
)
```