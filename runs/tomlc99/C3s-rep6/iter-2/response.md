```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_SAFE_ASCII = st.characters(
    blacklist_categories=("Cs",), blacklist_characters="\x00"
)

def _no_nul(s):
    return s.replace("\x00", "")

# ---------- keys ----------

_unquoted_key = st.text(
    alphabet=st.sampled_from(
        list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    ),
    min_size=1,
    max_size=12,
)

_basic_string_inner = st.text(
    alphabet=_SAFE_ASCII,
    max_size=12,
).filter(lambda s: "\x00" not in s and '"' not in s and "\\" not in s and "\n" not in s)

_literal_string_inner = st.text(
    alphabet=_SAFE_ASCII,
    max_size=12,
).filter(lambda s: "\x00" not in s and "'" not in s and "\n" not in s)

_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0041", "\\u00e9", "\\U0001F600", "\\u0000"]
)

_escaped_basic = st.recursive(
    st.one_of(
        _basic_string_inner,
        st.text(alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF, blacklist_categories=("Cs",)), max_size=6),
        _escape,
    ),
    lambda children: st.lists(children, max_size=4).map("".join),
    max_leaves=8,
)

_basic_string = _escaped_basic.map(lambda s: '"' + s + '"')
_literal_string = _literal_string_inner.map(lambda s: "'" + s + "'")

def _ml_basic_inner():
    return st.one_of(
        st.text(alphabet=_SAFE_ASCII, max_size=16).filter(
            lambda s: "\x00" not in s and '"""' not in s
        ),
        _escape,
    )

_ml_basic_string = st.lists(_ml_basic_inner(), max_size=4).map(
    lambda parts: '"""' + "".join(parts) + '"""'
)

_ml_literal_string = st.text(alphabet=_SAFE_ASCII, max_size=16).filter(
    lambda s: "\x00" not in s and "'''" not in s
).map(lambda s: "'''" + s + "'''")

_string_value = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# ---------- numbers ----------

_dec_int = st.one_of(
    st.integers(min_value=-(2**70), max_value=2**70).map(str),
    st.integers(min_value=0, max_value=9).map(str),
    st.sampled_from(["0", "007", "-0", "+0", "1_000", "1_2_3", "9" * 30, "-" + "9" * 30]),
)

_hex_int = st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x"))
_oct_int = st.integers(min_value=0, max_value=2**32).map(lambda n: "0o" + format(n, "o"))
_bin_int = st.integers(min_value=0, max_value=2**32).map(lambda n: "0b" + format(n, "b"))

_integer_value = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float_value = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False, width=64).map(repr),
    st.sampled_from([
        "1.0", "-1.0", "+1.0", "1e10", "1E-10", "1.5e+3", "1e309", "-1e309",
        "1.", ".5", "0.0", "-0.0", "1_0.0_1", "3.14159", "1e-9999", "inf",
        "-inf", "+inf", "nan", "-nan", "+nan", "1.0e0",
    ]),
)

_boolean_value = st.sampled_from(["true", "false"])

_date_time_value = st.sampled_from([
    "1979-05-27", "1979-05-27T07:32:00", "1979-05-27T07:32:00Z",
    "1979-05-27T07:32:00.999999", "1979-05-27 07:32:00Z",
    "1979-05-27T00:32:00-07:00", "1979-05-27T00:32:00.999999-07:00",
    "07:32:00", "07:32:00.999999", "1979-02-30", "0000-00-00",
    "9999-99-99T99:99:99Z", "1979-05-27t07:32:00z",
])

# ---------- recursive values ----------

def _value_strategy(draw, depth):
    return draw(_scalar_value)


_scalar_value = st.one_of(
    _string_value,
    _integer_value,
    _float_value,
    _boolean_value,
    _date_time_value,
)

def _make_value(depth):
    if depth <= 0:
        return _scalar_value
    return st.one_of(
        _scalar_value,
        _array(depth - 1),
        _inline_table(depth - 1),
    )

def _array(depth):
    inner = _make_value(depth)
    return st.lists(
        inner,
        max_size=5,
    ).map(lambda xs: "[" + ", ".join(xs) + "]")

def _inline_table(depth):
    inner = _make_value(depth)
    return st.lists(
        st.tuples(_key(), inner).map(lambda kv: kv[0] + " = " + kv[1]),
        max_size=4,
    ).map(lambda kvs: "{" + ", ".join(kvs) + "}")

def _key():
    return st.one_of(
        _unquoted_key,
        _basic_string,
        _literal_string,
        st.lists(
            st.one_of(_unquoted_key, _basic_string, _literal_string),
            min_size=2,
            max_size=3,
        ).map(lambda parts: ".".join(parts)),
    )

# depth band 1500-2048 for deep nesting tests
def _deep_array():
    return st.integers(min_value=1500, max_value=2048).map(
        lambda n: "[" * n + "]" * n
    )

def _deep_inline_table():
    return st.integers(min_value=1, max_value=200).map(
        lambda n: "{a = " * n + "1" + "}" * n
    )

# ---------- documents ----------

_value = st.recursive(
    _scalar_value,
    lambda children: st.one_of(
        st.lists(children, max_size=5).map(lambda xs: "[" + ", ".join(xs) + "]"),
        st.lists(
            st.tuples(_key(), children).map(lambda kv: kv[0] + " = " + kv[1]),
            max_size=4,
        ).map(lambda kvs: "{" + ", ".join(kvs) + "}"),
    ),
    max_leaves=6,
)

_key_value = st.tuples(_key(), _value).map(lambda kv: kv[0] + " = " + kv[1])

_table = st.tuples(_key()).map(lambda k: "[" + k[0] + "]")
_array_table = st.tuples(_key()).map(lambda k: "[[" + k[0] + "]]")

_comment_line = st.text(
    alphabet=_SAFE_ASCII, max_size=20
).filter(lambda s: "\x00" not in s and "\n" not in s).map(lambda s: "# " + s)

_line = st.one_of(_key_value, _table, _array_table, _comment_line, st.just(""))

_document = st.lists(_line, max_size=12).map(lambda ls: "\n".join(ls))

# ---------- malformed / edge cases ----------

_malformed = st.sampled_from([
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    "a = [1, 2",
    "a = {b = 1",
    "a = {b = 1,}",
    "a = [1, 2,]",
    "a = 1 2",
    "a =",
    "= 1",
    "a = = 1",
    "[a",
    "[[a]",
    "a = 1\na = 2",
    "[t]\n[t]",
    "a = 007",
    "a = 1.",
    "a = .5",
    'a = "x\x01y"',
    "# comment\x01\n",
    "a = 1979-02-30",
    "a.b = 1\na = 2",
    "a = {b = 1\nc = 2}",
    "a = \"\\q\"",
    "a = 1\nb",
    "a = \"\"\"x\"\"",
    "missing =",
    "a = 1e",
    "a = 0x",
    "a = 0b2",
    "a = 0o8",
    "a = +",
    "a = -",
    "a = 1__0",
    "a = 1_",
    "a = _1",
    "",
    "\n",
    "\r\n",
    "\t",
    " ",
])

_empty_containers = st.sampled_from([
    "a = []",
    "a = {}",
    "[t]",
    "[[a]]",
    '"" = 1',
    "a = [[]]",
    "a = {b = {}}",
    "a = [{}]",
])

_edge_numeric = st.sampled_from([
    "a = " + "9" * 100,
    "a = -" + "9" * 100,
    "a = 1e309",
    "a = -1e309",
    "a = 1e-309",
    "a = 0x" + "f" * 64,
    "a = 0b" + "1" * 64,
    "a = 1_000_000_000_000_000_000_000",
    "a = inf\na = nan\na = -inf",
])

_edge_strings = st.sampled_from([
    'a = "\\u0000"',
    'a = "\\U0001F600"',
    'a = "tab\there"',
    'a = "é"',
    'a = "日本語"',
    "a = 'literal \\n'",
    'a = """\nmulti\nline"""',
    "a = '''\nmulti\nliteral'''",
    'a = ""',
    "a = ''",
])

_edge_dates = st.sampled_from([
    "a = 1979-05-27T07:32:00Z",
    "a = 1979-05-27 07:32:00Z",
    "a = 07:32:00",
    "a = 1979-02-30",
    "a = 0000-00-00T00:00:00Z",
])

_edge_keys = st.sampled_from([
    '"" = 1',
    "a.b.c = 1",
    '"a b" = 1',
    "'a b' = 1",
    "a-b_c = 1",
    "123 = 1",
    "- = 1",
    "_ = 1",
])

_edge_docs = st.one_of(
    _malformed,
    _empty_containers,
    _edge_numeric,
    _edge_strings,
    _edge_dates,
    _edge_keys,
    _deep_array(),
    _deep_inline_table(),
)

_document_full = st.one_of(
    _document,
    _edge_docs,
)

strategy = _document_full.map(_no_nul)
```