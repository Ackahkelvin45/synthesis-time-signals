from hypothesis import strategies as st
import json

# ---------- helpers ----------

_ws = st.sampled_from([" ", "\t", "  ", "\t\t", ""])

# characters safe (non-quote, non-backslash, non-newline, non-NUL) for basic strings
_basic_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\n\r\x00',
)

_esc = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0000", "\\uFFFF", "\\u00e9", "\\U0001F600", "\\U00000041"]
)

def _basic_string_body():
    return st.one_of(_basic_safe, _esc)

basic_string = st.lists(_basic_string_body(), max_size=12).map(
    lambda cs: '"' + "".join(cs) + '"'
)

literal_string = st.lists(
    st.characters(blacklist_characters="'\n\r\x00"), max_size=12
).map(lambda cs: "'" + "".join(cs) + "'")

ml_basic_string = st.lists(
    st.one_of(_basic_safe, _esc, st.just("\n"), st.just("\r\n")),
    max_size=10,
).map(lambda cs: '"""' + "".join(cs) + '"""')

ml_literal_string = st.lists(
    st.one_of(
        st.characters(blacklist_characters="'\x00"),
        st.just("\n"),
        st.just("\r\n"),
    ),
    max_size=10,
).map(lambda cs: "'''" + "".join(cs) + "'''")

# ---------- integers ----------

_dec_int = st.one_of(
    st.integers(min_value=0, max_value=9).map(str),
    st.integers(min_value=-(10**25), max_value=10**25).map(str),
    st.just("007"),
    st.just("0"),
    st.just("+0"),
    st.just("-0"),
    st.just("1_000"),
    st.just("9" * 40),
    st.just("1" + "_0" * 30),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2**70).map(lambda n: "0x" + format(n, "x")),
    st.just("0xDEADBEEF"),
    st.just("0x0"),
    st.just("0xdead_beef"),
    st.just("0x" + "f" * 40),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2**70).map(lambda n: "0o" + format(n, "o")),
    st.just("0o0"),
    st.just("0o777"),
    st.just("0o7_7_7"),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2**70).map(lambda n: "0b" + format(n, "b")),
    st.just("0b0"),
    st.just("0b1010"),
    st.just("0b1_0_1"),
)

integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# ---------- floats ----------

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.just("1."),
    st.just(".5"),
    st.just("+1.0"),
    st.just("-0.0"),
    st.just("1e309"),
    st.just("1e-309"),
    st.just("6.626e-34"),
    st.just("1_000.0"),
    st.just("1.0_1"),
    st.just("0e0"),
    st.just("1E+10"),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

floating_point = st.one_of(_float, _inf_nan)

# ---------- booleans ----------

boolean = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_date = st.one_of(
    st.sampled_from([
        "1979-05-27", "0000-00-00", "1979-02-30", "9999-12-31",
        "2024-01-01", "1979-13-45",
    ])
)

_time = st.one_of(
    st.sampled_from([
        "07:32:00", "00:00:00", "23:59:59.999999", "07:32:00.1",
        "99:99:99", "12:00:00.000000001",
    ])
)

_offset = st.sampled_from(["Z", "z", "+00:00", "-07:00", "+23:59", "-00:00"])

_sep = st.sampled_from(["T", "t", " "])

def _mk_dt(parts):
    return "".join(parts)

datetime_ = st.one_of(
    st.tuples(_date, _sep, _time, _offset).map(_mk_dt),
    st.tuples(_date, _sep, _time).map(_mk_dt),
    _date,
    _time,
)

# ---------- keys ----------

_unquoted_key = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
            min_size=1, max_size=8),
    st.just("a"),
    st.just("key"),
    st.just("x" * 100),
    st.just("k" * 10000),
    st.just("-"),
    st.just("_"),
    st.just("123"),
)

_quoted_key = st.one_of(basic_string, literal_string, st.just('""'))

simple_key = st.one_of(_unquoted_key, _quoted_key)

def _dotted_key(parts):
    return ".".join(parts)

dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(_dotted_key)

key = st.one_of(simple_key, dotted_key)

# ---------- comments ----------

_comment_text = st.lists(
    st.characters(blacklist_characters="\n\r\x00"), max_size=20
).map(lambda cs: "#" + "".join(cs))

comment_opt = st.one_of(st.just(""), _comment_text)

# ---------- recursive values: arrays and inline tables ----------

def _join_array(parts):
    inner = ",".join(parts)
    return "[" + inner + "]"

def _join_inline(parts):
    inner = ", ".join(parts)
    return "{" + inner + "}"

# We build recursive strategies.  Depth is controlled by st.recursive's
# `max_leaves` and the branching factor; we bias toward moderate depth but
# allow deep nesting up to ~2048 via an explicit deep-array strategy.

_simple_value_no_container = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    integer,
    floating_point,
    boolean,
    datetime_,
)

def _kv_pair(k, v):
    return k + " = " + v

# recursive containers
def _value_strategy(draw):
    # We use st.recursive with a base of simple values and a container step.
    return draw(_recursive_value)

_recursive_value = None  # placeholder

def _make_recursive_value():
    base = _simple_value_no_container
    def extend(children):
        arr = st.lists(children, max_size=4).map(_join_array)
        inner = st.lists(
            st.tuples(key, children).map(lambda t: t[0] + " = " + t[1]),
            max_size=4,
        ).map(_join_inline)
        return st.one_of(arr, inner)
    return st.recursive(base, extend, max_leaves=30)

_recursive_value = _make_recursive_value()

value = _recursive_value

# empty containers explicitly
_empty_containers = st.sampled_from(["[]", "{}", "[ ]", "{ }", "[\n]", "[\n\n]"])

value = st.one_of(value, _empty_containers)

# deep nesting: build arrays nested up to ~2048 deep
_deep_array = st.integers(min_value=1, max_value=2048).map(
    lambda n: "[" * n + "]" * n
)

value = st.one_of(value, _deep_array)

# ---------- key-value lines ----------

key_value = st.tuples(key, value).map(lambda t: t[0] + " = " + t[1])

# ---------- tables ----------

_standard_table = key.map(lambda k: "[" + k + "]")
_array_table = key.map(lambda k: "[[" + k + "]]")

table = st.one_of(_standard_table, _array_table)

# ---------- expressions ----------

expression = st.one_of(
    st.tuples(key_value, comment_opt).map(lambda t: t[0] + (" " + t[1] if t[1] else "")),
    st.tuples(table, comment_opt).map(lambda t: t[0] + (" " + t[1] if t[1] else "")),
    comment_opt,
)

# ---------- malformed / near-valid inputs ----------

_malformed = st.sampled_from([
    # missing delimiter
    "a = [1, 2",
    "a = {b = 1",
    "a = {b = 1,}",
    "a = [1, 2,]",
    "[t",
    "[[t]",
    # doubled delimiter
    "a = [[1, 2]]",
    "a = {{b = 1}}",
    "[t]]",
    "[[t]]]",
    # unterminated string
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    # stray token
    "a = ",
    "= 1",
    "a 1",
    "a = 1 2",
    "a = ,",
    "a = [1 2]",
    "a = {b = 1 c = 2}",
    # duplicate keys (rejected by parser)
    "a = 1\na = 2",
    "[t]\n[t]",
    # newline in inline table (rejected)
    "a = {b = 1,\nc = 2}",
    # invalid escape
    'a = "\\q"',
    # value on next line
    "a =\n1",
    # bare key with unicode
    "café = 1",
    # leading zeros, floats without digits (accepted)
    "a = 007",
    "a = 1.",
    "a = .5",
    # raw control char in string
    'a = "x\x01y"',
    # control char in comment
    "# comment with \x01 control",
    # trailing comma in inline table (accepted)
    "a = {b = 1,}",
    # calendar-invalid date (accepted)
    "a = 1979-02-30",
])

# ---------- document ----------

def _join_exprs(exprs):
    return "\n".join(exprs)

document = st.one_of(
    st.lists(expression, min_size=0, max_size=8).map(_join_exprs),
    _malformed,
)

# final strategy: strings
strategy = document