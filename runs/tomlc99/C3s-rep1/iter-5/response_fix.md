```python
from hypothesis import strategies as st
import json

# ---------- low-level character pools ----------

ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
digits = "0123456789"
bare_key_chars = ascii_letters + digits + "-_"

# control bytes that are NOT NUL (NUL would be skipped by the harness)
control_bytes = "".join(chr(c) for c in range(1, 32) if c != 0) + chr(127)

# non-ASCII characters (latin-1 range + a few higher planes)
non_ascii = "".join(
    chr(c) for c in list(range(0x80, 0x100)) + [0x2028, 0x2029, 0xFEFF, 0x1F600, 0x10FFFF]
)

# characters that are safe inside strings (no NUL, no unescaped quote/backslash/newline)
def _plain_string_chars(quote):
    pool = ascii_letters + digits + " \t!#$%&()*+,-./:;<=>?@[]^_`{|}~"
    pool += non_ascii
    pool += control_bytes
    # exclude the active quote char and backslash from the raw pool
    return "".join(ch for ch in pool if ch not in (quote, "\\"))

# ---------- escapes ----------

_escape_simple = ["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

def _unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda cp: "\\u%04X" % (cp & 0xFFFF) if cp <= 0xFFFF else "\\U%08X" % cp
    )

_escape_full = st.one_of(
    st.sampled_from(_escape_simple),
    _unicode_escape(),
)

# ---------- strings ----------

def _basic_string_body():
    return st.one_of(
        st.text(_plain_string_chars('"'), min_size=0, max_size=12),
        _escape_full,
    )

basic_string = st.lists(_basic_string_body(), max_size=8).map(
    lambda parts: '"' + "".join(parts) + '"'
)

literal_string = st.text(_plain_string_chars("'"), min_size=0, max_size=12).map(
    lambda s: "'" + s + "'"
)

# multiline basic string: content may include newlines and escaped newline
_ml_basic_chunk = st.one_of(
    st.text(
        "".join(ch for ch in (ascii_letters + digits + " \t!#$%&()*+,-./:;<=>?@[]^_`{|}~" + non_ascii + control_bytes + "\n\r")
               if ch not in ('"', "\\")),
        min_size=0,
        max_size=12,
    ),
    _escape_full,
    st.just("\\\n"),
    st.just("\\\r\n"),
)

ml_basic_string = st.lists(_ml_basic_chunk, max_size=6).map(
    lambda parts: '"""' + "".join(parts) + '"""'
)

_ml_literal_chunk = st.text(
    "".join(ch for ch in (ascii_letters + digits + " \t!#$%&()*+,-./:;<=>?@[]^_`{|}~" + non_ascii + control_bytes + "\n\r")
           if ch != "'"),
    min_size=0,
    max_size=12,
)

ml_literal_string = st.lists(_ml_literal_chunk, max_size=6).map(
    lambda parts: "'''" + "".join(parts) + "'''"
)

any_string = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# ---------- numbers ----------

_dec_digits = st.text(digits, min_size=1, max_size=20)

def _with_underscores(digit_strategy, min_len=1, max_len=20):
    # produce a digit run, optionally with underscores between digits
    return st.lists(
        st.tuples(digit_strategy, st.booleans()),
        min_size=min_len,
        max_size=max_len,
    ).map(lambda pairs: "".join(d + ("_" if u else "") for d, u in pairs))

dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.integers(min_value=-2**63, max_value=2**63).map(str),
    st.just("0"),
    st.just("-0"),
    st.just("+0"),
    st.just("007"),
    st.just("000123"),
    st.just("1_000"),
    st.just("1_2_3_4_5"),
    st.just("-1_000_000"),
    st.just("9223372036854775807"),
    st.just("-9223372036854775808"),
    st.just("999999999999999999999999999999"),
    _with_underscores(st.sampled_from(list(digits))).map(lambda s: s),
)

hex_int = st.one_of(
    st.just("0x0"),
    st.just("0xDEADBEEF"),
    st.just("0xdead_beef"),
    st.just("0xFFFFFFFFFFFFFFFF"),
    st.text("0123456789abcdefABCDEF", min_size=1, max_size=16).map(lambda s: "0x" + s),
)

oct_int = st.one_of(
    st.just("0o0"),
    st.just("0o777"),
    st.just("0o7_7_7"),
    st.text("01234567", min_size=1, max_size=16).map(lambda s: "0o" + s),
)

bin_int = st.one_of(
    st.just("0b0"),
    st.just("0b1"),
    st.just("0b1010_1010"),
    st.text("01", min_size=1, max_size=16).map(lambda s: "0b" + s),
)

integer = st.one_of(dec_int, hex_int, oct_int, bin_int)

# floats
_frac = st.text(digits, min_size=1, max_size=10).map(lambda s: "." + s)
_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(digits, min_size=1, max_size=5),
).map(lambda t: t[0] + t[1] + t[2])

float_val = st.one_of(
    st.just("1."),
    st.just(".5"),
    st.just("1.0"),
    st.just("0.0"),
    st.just("-0.0"),
    st.just("+1.5"),
    st.just("1e10"),
    st.just("1E10"),
    st.just("1e+10"),
    st.just("1e-10"),
    st.just("1.5e10"),
    st.just("1.5E-10"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1_000.000_1"),
    st.just("3.141592653589793"),
    st.just("inf"),
    st.just("+inf"),
    st.just("-inf"),
    st.just("nan"),
    st.just("+nan"),
    st.just("-nan"),
    st.tuples(_dec_digits, _frac, st.one_of(_exp, st.just(""))).map(
        lambda t: t[0] + t[1] + t[2]
    ),
)

floating_point = float_val

# ---------- booleans ----------

boolean = st.sampled_from(["true", "false"])

# ---------- dates ----------

def _d(n):
    return st.text(digits, min_size=n, max_size=n)

_year = _d(4)
_month = _d(2)
_day = _d(2)
_hour = _d(2)
_minute = _d(2)
_second = _d(2)
_secfrac = st.text(digits, min_size=1, max_size=6).map(lambda s: "." + s)
_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(st.sampled_from(["+", "-"]), _d(2), st.just(":"), _d(2)).map(
        lambda t: "".join(t)
    ),
)
_delim = st.sampled_from(["T", "t", " "])

_full_date = st.tuples(_year, st.just("-"), _month, st.just("-"), _day).map(
    lambda t: "".join(t)
)
_partial_time = st.tuples(
    _hour, st.just(":"), _minute, st.just(":"), _second,
    st.one_of(_secfrac, st.just("")),
).map(lambda t: "".join(t))
_full_time = st.tuples(_partial_time, _offset).map(lambda t: t[0] + t[1])

date_time = st.one_of(
    st.tuples(_full_date, _delim, _full_time).map(lambda t: "".join(t)),
    st.tuples(_full_date, _delim, _partial_time).map(lambda t: "".join(t)),
    _full_date,
    _partial_time,
    st.just("1979-02-30"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("1979-05-27T07:32:00"),
    st.just("07:32:00"),
    st.just("1979-05-27"),
)

# ---------- keys ----------

unquoted_key = st.one_of(
    st.text(bare_key_chars, min_size=1, max_size=10),
    st.just("a"),
    st.just("key"),
    st.just("x-y_z"),
    st.just("123"),
)

quoted_key = st.one_of(
    basic_string,
    literal_string,
    st.just('""'),
    st.just("''"),
)

simple_key = st.one_of(unquoted_key, quoted_key)

dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

key = st.one_of(simple_key, dotted_key)

# ---------- recursive values ----------

# base (non-recursive) values, defined before the recursive strategy
_base_value = st.one_of(
    any_string,
    integer,
    floating_point,
    boolean,
    date_time,
)

def _inline_table_kv(children):
    return st.tuples(key, st.just(" = "), children).map(lambda t: "".join(t))

def _inline_table(children):
    return st.one_of(
        st.just("{}"),
        st.lists(_inline_table_kv(children), min_size=1, max_size=4).map(
            lambda kvs: "{" + ", ".join(kvs) + "}"
        ),
        st.lists(_inline_table_kv(children), min_size=1, max_size=4).map(
            lambda kvs: "{" + ", ".join(kvs) + ",}"
        ),
    )

def _array(children):
    return st.one_of(
        st.just("[]"),
        st.lists(children, min_size=1, max_size=5).map(
            lambda vs: "[" + ", ".join(vs) + "]"
        ),
        st.lists(children, min_size=1, max_size=5).map(
            lambda vs: "[" + ", ".join(vs) + ",]"
        ),
        st.lists(children, min_size=1, max_size=5).map(
            lambda vs: "[\n  " + ",\n  ".join(vs) + ",\n]"
        ),
        st.lists(children, min_size=1, max_size=5).map(
            lambda vs: "[\n# c\n" + ",\n".join(vs) + "\n]"
        ),
    )

value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        children,
        _array(children),
        _inline_table(children),
    ),
    max_leaves=20,
)

# ---------- deep nesting (band 1500-2048) ----------

deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "[" * n + "0" + "]" * n
)

deep_inline_table = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "{a = " * n + "0" + "}" * n
)

# ---------- key/value lines ----------

key_value = st.tuples(key, st.just(" = "), value).map(lambda t: "".join(t))

key_value_with_comment = st.tuples(
    key_value,
    st.one_of(
        st.just(""),
        st.just(" # comment"),
        st.just(" # " + "".join(control_bytes[:5])),
    ),
).map(lambda t: t[0] + t[1])

# ---------- tables ----------

standard_table = st.tuples(
    st.just("["), key, st.just("]")
).map(lambda t: "".join(t))

array_table = st.tuples(
    st.just("[["), key, st.just("]]")
).map(lambda t: "".join(t))

empty_table = st.just("[t]")

# ---------- malformed inputs (near-valid) ----------

malformed = st.one_of(
    # missing closing delimiter
    st.tuples(key, st.just(" = ["), value).map(lambda t: "".join(t)),
    st.tuples(key, st.just(" = {"), key, st.just(" = "), value).map(lambda t: "".join(t)),
    st.tuples(st.just("["), key).map(lambda t: "".join(t)),
    st.tuples(st.just("[["), key, st.just("]")).map(lambda t: "".join(t)),
    # doubled delimiter
    st.tuples(key, st.just(" = [["), value, st.just("]")).map(lambda t: "".join(t)),
    st.tuples(key, st.just(" = {{"), key, st.just(" = "), value, st.just("}")).map(lambda t: "".join(t)),
    # unterminated string
    st.tuples(key, st.just(' = "abc')).map(lambda t: "".join(t)),
    st.tuples(key, st.just(" = 'abc")).map(lambda t: "".join(t)),
    st.tuples(key, st.just(' = """abc')).map(lambda t: "".join(t)),
    # stray token
    st.just("= 1"),
    st.just("]"),
    st.just("}"),
    st.just("[a"),
    st.just("a ="),
    st.just("a = "),
    st.just("a = \n 1"),
    st.just("a = {b = 1\nc = 2}"),
    st.just("a = \"\\q\""),
    st.just("a = 1 2"),
    st.just("a = [1 2]"),
    st.just("a b = 1"),
    st.just("[a] [b]"),
    st.just("a = 1\na = 2"),
    st.just("[a]\n[a]"),
    st.just("[a]\n[[a]]"),
    st.just("a.b = 1\n[a]\nc = 2"),
    st.just('a = "x\x00y"'),
)

# ---------- documents ----------

_line = st.one_of(
    key_value_with_comment,
    standard_table,
    array_table,
    st.just(""),
    st.just("# comment"),
    st.just("#"),
    st.just("   "),
)

def _join_lines(lines):
    return "\n".join(lines)

document = st.one_of(
    st.lists(_line, min_size=0, max_size=8).map(_join_lines),
    st.lists(_line, min_size=1, max_size=8).map(lambda ls: "\n".join(ls) + "\n"),
    st.lists(_line, min_size=1, max_size=8).map(lambda ls: "\r\n".join(ls)),
    st.lists(_line, min_size=1, max_size=8).map(lambda ls: "\t" + "\n\t".join(ls)),
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("# only a comment\n"),
    st.just("[t]\n"),
    st.just("[[a]]\n"),
    st.just("[[a]]\n[[a]]\n"),
    st.just('"" = 1'),
    st.just('"a b" = 1'),
    st.just("'a.b' = 1"),
    st.just("a.b.c = 1"),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just("a = 1979-02-30"),
    st.just("a = {b = 1,}"),
    st.just('a = "x\x01y"'),
    st.just("# comment with \x01 control"),
    deep_array,
    deep_inline_table,
    malformed,
    st.tuples(st.just("a = "), value).map(lambda t: "".join(t)),
    st.tuples(st.just("a = "), value, st.just("\n")).map(lambda t: "".join(t)),
    st.tuples(
        st.lists(key_value, min_size=1, max_size=5),
        st.just("\n"),
        st.lists(
            st.one_of(standard_table, array_table),
            min_size=1,
            max_size=3,
        ).map(lambda ts: "\n".join(ts)),
    ).map(lambda t: "\n".join(t[0]) + t[1] + t[2]),
)

strategy = st.one_of(
    document,
    st.tuples(st.just("a = "), value).map(lambda t: "".join(t)),
    st.tuples(st.just("key = "), value, st.just("\n")).map(lambda t: "".join(t)),
    st.tuples(st.just("["), key, st.just("]\n"), key_value).map(lambda t: "".join(t)),
    st.tuples(st.just("[["), key, st.just("]]\n"), key_value).map(lambda t: "".join(t)),
    st.tuples(key, st.just(" = "), value, st.just(" # comment\n")).map(lambda t: "".join(t)),
)
```