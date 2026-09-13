from hypothesis import strategies as st
import json

# ---------- primitives ----------

_digits = st.integers(min_value=0, max_value=9)

def _digit_str(n=1):
    return st.text(alphabet="0123456789", min_size=n, max_size=n)

# ---------- keys ----------

_unquoted_key_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
)

unquoted_key = st.text(alphabet=_unquoted_key_char, min_size=1, max_size=12)

# quoted keys: basic and literal
basic_key_inner = st.text(
    alphabet=st.characters(blacklist_characters='"\n\\', blacklist_categories=("Cs",)),
    max_size=8,
)
basic_quoted_key = basic_key_inner.map(lambda s: '"' + s + '"')

literal_key_inner = st.text(
    alphabet=st.characters(blacklist_characters="'\n", blacklist_categories=("Cs",)),
    max_size=8,
)
literal_quoted_key = literal_key_inner.map(lambda s: "'" + s + "'")

simple_key = st.one_of(unquoted_key, basic_quoted_key, literal_quoted_key)

dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

key = st.one_of(simple_key, dotted_key)

# ---------- strings (all four quoting forms) ----------

_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_unicode_escape = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "\\u%04X" % n
)

_ex_unicode_escape = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda n: "\\U%08X" % n
)

_basic_char = st.one_of(
    st.characters(
        blacklist_characters='"\\\n',
        blacklist_categories=("Cs",),
    ),
    _escape,
    _unicode_escape,
    _ex_unicode_escape,
)

basic_string = st.lists(_basic_char, max_size=10).map(lambda cs: '"' + "".join(cs) + '"')

_literal_char = st.characters(blacklist_characters="'\n", blacklist_categories=("Cs",))
literal_string = st.lists(_literal_char, max_size=10).map(
    lambda cs: "'" + "".join(cs) + "'"
)

_ml_basic_char = st.one_of(
    st.characters(blacklist_characters='"\\', blacklist_categories=("Cs",)),
    _escape,
    _unicode_escape,
    _ex_unicode_escape,
    st.just("\n"),
    st.just("\r\n"),
)

ml_basic_string = st.lists(_ml_basic_char, max_size=12).map(
    lambda cs: '"""' + "".join(cs) + '"""'
)

_ml_literal_char = st.characters(blacklist_characters="'", blacklist_categories=("Cs",))
ml_literal_string = st.lists(_ml_literal_char, max_size=12).map(
    lambda cs: "'''" + "".join(cs) + "'''"
)

string_value = st.one_of(
    basic_string, literal_string, ml_basic_string, ml_literal_string
)

# ---------- integers ----------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
    st.integers(min_value=0, max_value=10 ** 6).map(lambda n: "%07d" % n),
    st.integers(min_value=0, max_value=10 ** 9).map(
        lambda n: format(n, ",").replace(",", "_")
    ),
    st.just("0"),
    st.just("+0"),
    st.just("-0"),
)

_hex_digits = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=10)
_hex_int = _hex_digits.map(lambda s: "0x" + s)

_oct_digits = st.text(alphabet="01234567", min_size=1, max_size=10)
_oct_int = _oct_digits.map(lambda s: "0o" + s)

_bin_digits = st.text(alphabet="01", min_size=1, max_size=12)
_bin_int = _bin_digits.map(lambda s: "0b" + s)

integer_value = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# ---------- floats ----------

_float_forms = st.one_of(
    st.tuples(
        st.integers(min_value=-10 ** 6, max_value=10 ** 6),
        st.integers(min_value=0, max_value=10 ** 6),
    ).map(lambda t: "%d.%d" % t),
    st.integers(min_value=-10 ** 6, max_value=10 ** 6).map(lambda n: "%d." % n),
    st.integers(min_value=0, max_value=10 ** 6).map(lambda n: ".%d" % n),
    st.tuples(
        st.integers(min_value=-10 ** 3, max_value=10 ** 3),
        st.integers(min_value=-400, max_value=400),
    ).map(lambda t: "%de%d" % t),
    st.tuples(
        st.integers(min_value=-10 ** 3, max_value=10 ** 3),
        st.integers(min_value=0, max_value=10 ** 3),
        st.integers(min_value=-400, max_value=400),
    ).map(lambda t: "%d.%de%d" % t),
    st.just("inf"),
    st.just("-inf"),
    st.just("+inf"),
    st.just("nan"),
    st.just("-nan"),
    st.just("+nan"),
    st.just("1e309"),
    st.just("1e-309"),
    st.just("1_000.000_1"),
)

float_value = _float_forms

# ---------- booleans ----------

bool_value = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_date = st.tuples(
    st.integers(min_value=0, max_value=9999),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: "%04d-%02d-%02d" % t)

_time = st.tuples(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: "%02d:%02d:%02d" % t)

_time_frac = st.tuples(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=999999),
).map(lambda t: "%02d:%02d:%02d.%d" % t)

_offset = st.one_of(
    st.just("Z"),
    st.tuples(
        st.sampled_from(["+", "-"]),
        st.integers(min_value=0, max_value=23),
        st.integers(min_value=0, max_value=59),
    ).map(lambda t: "%s%02d:%02d" % t),
)

_delim = st.sampled_from(["T", "t", " "])

offset_date_time = st.tuples(_date, _delim, _time, _offset).map(
    lambda t: "%s%s%s%s" % t
)

local_date_time = st.tuples(_date, _delim, _time).map(lambda t: "%s%s%s" % t)

local_date = _date

local_time = st.one_of(_time, _time_frac)

date_time_value = st.one_of(
    offset_date_time, local_date_time, local_date, local_time
)

# ---------- recursive values: arrays and inline tables ----------

def _join(parts):
    return "".join(parts)

# forward-declared via st.recursive
_scalar_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value,
)

_comment_text = st.text(
    alphabet=st.characters(blacklist_characters="\n", blacklist_categories=("Cs",)),
    max_size=20,
)

def _comment():
    return _comment_text.map(lambda s: "#" + s)

_value = st.recursive(
    _scalar_value,
    lambda children: st.one_of(
        _array_of(children),
        _inline_table_of(children),
    ),
    max_leaves=20,
)

def _array_of(children):
    return st.lists(children, max_size=4).map(
        lambda vs: "[" + ", ".join(vs) + "]"
    )

def _inline_table_of(children):
    return st.lists(
        st.tuples(simple_key, children), max_size=3
    ).map(
        lambda kvs: "{" + ", ".join("%s = %s" % kv for kv in kvs) + "}"
    )

value = _value

# ---------- key/value lines ----------

key_value = st.tuples(key, value).map(lambda t: "%s = %s" % t)

# ---------- tables ----------

standard_table = key.map(lambda k: "[%s]" % k)

array_table = key.map(lambda k: "[[%s]]" % k)

# ---------- document assembly ----------

_line = st.one_of(
    key_value,
    standard_table,
    array_table,
    _comment(),
)

def _doc(lines):
    return "\n".join(lines)

document = st.one_of(
    st.just(""),
    _comment(),
    st.lists(_line, min_size=1, max_size=8).map(_doc),
)

# ---------- malformed / near-valid inputs ----------

_malformed = st.sampled_from([
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    "a = [1, 2",
    "a = {b = 1",
    "a = {b = 1,}",
    "[t",
    "[[t]",
    "a = ",
    "= 1",
    "a = 1 2",
    "a = 1\nb = 1\nb = 2",
    "[t]\n[t]",
    "a = {b = 1,\nc = 2}",
    "a = 1\nb =",
    "a = \\q",
    "a = \"\\q\"",
    "a = 007",
    "a = 1.",
    "a = .5",
    "a = 1979-02-30",
    'a = "x\x01y"',
    "# comment with \x01 control",
    "a = 1e309",
    "missing =",
    "a.b = 1\na.b = 2",
    "a = 1\r\nb = 2",
    "\ta = 1",
    "a = [1,]",
    "a = {b = 1, c = 2,}",
    "a = true\nb = false",
    "a = 1979-05-27 07:32:00Z",
    "a = 1979-05-27T07:32:00",
    "a = 07:32:00",
    "a = 1979-05-27",
    "a = +inf",
    "a = -nan",
    '"" = 1',
    "a = 0x1F",
    "a = 0o17",
    "a = 0b1010",
    "a = 1_000",
])

# ---------- deep nesting ----------

def _deep_array(depth):
    return "[" * depth + "]" * depth

def _deep_inline(depth):
    return "{" * depth + "}" * depth

deep_nesting = st.one_of(
    st.integers(min_value=1, max_value=2048).map(_deep_array),
    st.integers(min_value=1, max_value=2048).map(_deep_inline),
)

# ---------- top-level strategy ----------

strategy = st.one_of(
    document,
    _malformed,
    deep_nesting,
    st.tuples(key, value).map(lambda t: "%s = %s" % t),
)