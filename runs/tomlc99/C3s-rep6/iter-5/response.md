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

# Newly added edge cases to reach uncovered parser branches:
# - dotted keys in table headers ([[a.b]] / [a.b])
# - whitespace around dots in keys
# - bare CR and CRLF line endings
# - BOM at start of document
# - leading/trailing whitespace around key-values
# - keys with quoted segments mixed with unquoted
# - array-table with dotted keys, inline table with dotted key
# - literal/basic strings split across lines with trailing backslash
# - tab-separated key-values and comments
_edge_dotted_tables = st.sampled_from([
    "[a.b.c]",
    "[[a.b.c]]",
    "[a . b]",
    "[ a.b ]",
    "['a'.b]",
    '[a."b"]',
    "[[a.b]]\n[a.b]",
    "[a.b]\n[a.c]\n[[a.b]]",
    "[a]\n[a.b]\n[a.b.c]",
    '["a.b"]',
    "[[\"a.b\"]]",
    "a.b.c.d.e = 1",
    "a . b = 1",
    "a. b = 1",
    "a .b = 1",
    'a."b c".d = 1',
    "a.'b c'.d = 1",
    "a.b.c = { d.e = 1 }",
    "a.b = [ { c.d = 1 } ]",
    "a.b = [{c.d = 1}, {e.f = 2}]",
    "a.b = [[1,2],[3,4]]",
])

_edge_line_endings = st.sampled_from([
    "a = 1\r\nb = 2\r\nc = 3",
    "a = 1\rb = 2\rc = 3",
    "a = 1\r",
    "\ra = 1",
    "a = 1\r\n",
    "\ufeffa = 1",
    "\ufeff[a]\nb = 1",
    "\ufeff",
    "  a = 1",
    "a = 1  ",
    "\ta = 1",
    "a = 1\t",
    "a\t=\t1",
    "# comment\r\na = 1",
    "# comment\ra = 1",
    "\n\n\na = 1\n\n",
    "a = 1 # trailing comment",
    "a = 1# no space",
    "a = 1  # comment with \t tab",
])

_edge_strings2 = st.sampled_from([
    'a = "line\\\ncontinuation"',
    "a = 'line\\\ncontinuation'",
    'a = """line\\\n  continuation"""',
    "a = '''line\\\n  continuation'''",
    'a = """\\\n"""',
    "a = '''\\\n'''",
    'a = """a\\"""b"""',
    'a = """a\\""""""',
    "a = '''a\\'''b'''",
    'a = "\\u00"',
    'a = "\\U0001"',
    'a = "\\x41"',
    'a = "\\e"',
    'a = "\\uD800"',
    'a = "\\uDFFF"',
    'a = "\\uD800\\uDC00"',
    'a = "\\uFFFE"',
    'a = "\\uFFFF"',
    'a = "\\u0000\\u0001"',
])

# Additional edge cases to reach uncovered parser branches:
# - unicode escape edge cases (lone high/low surrogates, out-of-range, short)
# - control characters inside strings and comments
# - invalid UTF-8-ish byte sequences encoded as surrogates
# - exotic float/int forms (leading +, underscore placement)
# - empty/whitespace-only keys via quoted strings
# - tables with empty quoted keys and dotted empty segments
# - deeply nested inline tables / arrays combined
# - duplicate keys and redefined tables
# - multiline string with quotes near delimiters
# - keys that are reserved words (true/false/inf/nan)
# - date-time with fractional seconds and offsets variants
# - integer with leading zeros in hex/oct/bin
# - comments with embedded control chars and unicode
_edge_unicode_escapes = st.sampled_from([
    'a = "\\uD800"',
    'a = "\\uDC00"',
    'a = "\\uD800\\uD800"',
    'a = "\\uDC00\\uDC00"',
    'a = "\\uD800x"',
    'a = "\\uDC00x"',
    'a = "\\U00110000"',
    'a = "\\UFFFFFFFF"',
    'a = "\\u{41}"',
    'a = "\\u"',
    'a = "\\U"',
    'a = "\\u12"',
    'a = "\\U0001F60"',
    'a = "\\uD83D\\uDE00"',
    'a = "\\uFFFF\\uFFFE"',
    'a = "\\u0001\\u0002\\u0003"',
])

_edge_control_chars = st.sampled_from([
    'a = "\x01\x02\x03"',
    'a = "\x7f"',
    'a = "\x1b[31m"',
    "# \x01 comment\na = 1",
    "# \x7f comment\na = 1",
    'a = "\\x00\\x01"',
    'a = "\x0b\x0c"',
    'a = "\x1f"',
    'a = "\x80"',
    'a = "\xc3\xa9"',
    'a = "\xe2\x82\xac"',
    'a = "\xf0\x9f\x98\x80"',
    'a = "\xed\xa0\x80"',
    'a = "\xef\xbf\xbe"',
    'a = "\xef\xbf\xbf"',
])

_edge_numeric2 = st.sampled_from([
    "a = +1",
    "a = +0",
    "a = +0x1",
    "a = +0o1",
    "a = +0b1",
    "a = 0x_1",
    "a = 0x1_",
    "a = 0o_1",
    "a = 0b_1",
    "a = 1_000.000_1",
    "a = 1e_10",
    "a = 1_e10",
    "a = 1.0e_10",
    "a = -0",
    "a = +0.0",
    "a = -0.0",
    "a = 0e0",
    "a = 0.0e0",
    "a = 00.00",
    "a = 0000",
    "a = -0000",
])

_edge_reserved = st.sampled_from([
    "true = 1",
    "false = 1",
    "inf = 1",
    "nan = 1",
    "a = true",
    "a = false",
    "a = truefalse",
    "a = true1",
    "a = 1true",
    "a = tru",
    "a = fals",
    "a = inff",
    "a = nann",
    "a = TRUE",
    "a = FALSE",
    "a = Inf",
    "a = NaN",
])

_edge_duplicates = st.sampled_from([
    "a = 1\na = 2",
    "a = 1\na = 1",
    "[t]\na = 1\n[t]\na = 2",
    "[t]\n[t]\n[t]",
    "[[t]]\n[[t]]",
    "a = {b = 1, b = 2}",
    "a = [1, 1, 1]",
    "[a.b]\n[a.b]",
    "[a]\n[a]",
    "[[a]]\n[a]",
    "[a]\n[[a]]",
])

_edge_deep_mixed = st.integers(min_value=1, max_value=64).map(
    lambda n: "a = " + "[" * n + "{" + "b = " * 0 + "1" + "}" + "]" * n
)

_edge_deep_inline = st.integers(min_value=1, max_value=100).map(
    lambda n: "a = " + "{b = " * n + "1" + "}" * n
)

_edge_deep_arrays_in_tables = st.integers(min_value=1, max_value=64).map(
    lambda n: "[t]\na = " + "[" * n + "]" * n
)

_edge_multiline_quotes = st.sampled_from([
    'a = """"""',
    "a = ''''''",
    'a = """""""',
    "a = '''''''",
    'a = """\\""""',
    "a = '''\\''''",
    'a = """a""b"""',
    "a = '''a''b'''",
    'a = """a""""b"""',
    "a = '''a''''b'''",
    'a = """\n"""',
    "a = '''\n'''",
    'a = """\r\n"""',
    "a = '''\r\n'''",
])

_edge_datetime2 = st.sampled_from([
    "a = 1979-05-27T07:32:00.999999999Z",
    "a = 1979-05-27T07:32:00+00:00",
    "a = 1979-05-27T07:32:00-00:00",
    "a = 1979-05-27T07:32:00.5Z",
    "a = 1979-05-27T7:32:00Z",
    "a = 1979-5-27T07:32:00Z",
    "a = 1979-05-27T07:32Z",
    "a = 1979-05-27T07Z",
    "a = 1979-05-27T07:32:00.123456789012Z",
    "a = 24:00:00",
    "a = 25:00:00",
    "a = 07:60:00",
    "a = 07:32:60",
    "a = 1979-13-01",
    "a = 1979-00-01",
    "a = 1979-01-00",
    "a = 1979-01-32",
])

_edge_keys2 = st.sampled_from([
    '"" = 1',
    "'' = 1",
    '""."" = 1',
    "''.'' = 1",
    'a."" = 1',
    "a.'' = 1",
    '"".a = 1',
    "''.a = 1",
    '"a"."b"."c" = 1',
    "a.b.c.d.e.f.g = 1",
    "a . b . c = 1",
    "a\t.\tb = 1",
    "[a.b.c.d.e]",
    "[[a.b.c.d.e]]",
    "[a.b][c]",
    "[a . b . c]",
])

# Newly added edge cases targeting uncovered parser branches:
# - whitespace/comment handling around table headers and array separators
# - nested arrays/tables with comments interleaved
# - inline tables with newlines and comments
# - arrays with trailing commas and comments before close
# - table headers with trailing comments
# - key-values with comments between key and '='
# - multiline strings used as values with trailing content
# - arrays of tables with inline tables and dotted keys
# - empty table headers / whitespace-only headers
# - top-level bare values (not key=value)
# - multiple BOM/whitespace combinations
# - keys containing dots inside quotes vs unquoted splitting
# - consecutive newlines and mixed line endings in arrays
_edge_whitespace_comments = st.sampled_from([
    "a = [ 1, 2, # c\n 3 ]",
    "a = [\n1,\n2,\n]",
    "a = [\n# c\n1,\n# c\n2\n]",
    "a = { b = 1, # c\n c = 2 }",
    "a = {\n b = 1,\n c = 2,\n}",
    "[a] # trailing\nb = 1",
    "[[a]] # trailing",
    "[ a ]\nb = 1",
    "[a\t]\nb = 1",
    "a # c\n= 1",
    "a = # c\n1",
    "a = 1 # c\nb = 2",
    "a = [1,\n2,\n3,]",
    "a = [1, 2, 3,]",
    "a = {b = 1,}",
    "a = {b = 1 , }",
    "a = [ ]",
    "a = { }",
    "a = [ # c\n]",
    "a = { # c\n}",
    "[# c\na]\nb = 1",
    "[a# c\n]\nb = 1",
    "[[# c\na]]",
    "a = [\r\n1,\r\n2\r\n]",
    "a = {\r\nb = 1\r\n}",
    "a = [1,\n\n2]",
    "a = [1 , 2]",
    "a = [ 1]",
    "a = [1 ]",
    "a = [1,2 , 3]",
    "a = [\t1,\t2]",
    "a = {b = 1 ,c = 2}",
    "a = { b = 1 }",
    "a = {b = 1 }",
    "a = { b = 1}",
])

_edge_bare_values = st.sampled_from([
    "1",
    '"x"',
    "[]",
    "{}",
    "true",
    "1979-05-27",
    "1, 2",
    "a",
    "a b",
    "= 1",
    "a =",
    "a = =",
    "[",
    "]",
    "{",
    "}",
    "[[",
    "]]",
    "a = [1, [2, [3, [4]]]]",
    "a = {b = {c = {d = 1}}}",
    "[a]\n[b]\nc = 1",
    "[[a]]\n[[a]]\n[[a]]",
    "[a.b]\n[a.b.c]\n[a.b.c.d]",
    "a = [1,2,3,4,5,6,7,8,9,10]",
    "a = {b=1,c=2,d=3,e=4,f=5}",
    'a = "x" # c',
    "a = 1 # c\n# c\nb = 2",
    "\n\n\n",
    "\r\r\r",
    "\t\t\t",
    "\ufeff\ufeffa = 1",
    "\ufeff\n[a]\nb = 1",
])

_edge_docs = st.one_of(
    _malformed,
    _empty_containers,
    _edge_numeric,
    _edge_strings,
    _edge_dates,
    _edge_keys,
    _edge_dotted_tables,
    _edge_line_endings,
    _edge_strings2,
    _edge_unicode_escapes,
    _edge_control_chars,
    _edge_numeric2,
    _edge_reserved,
    _edge_duplicates,
    _edge_deep_mixed,
    _edge_deep_inline,
    _edge_deep_arrays_in_tables,
    _edge_multiline_quotes,
    _edge_datetime2,
    _edge_keys2,
    _edge_whitespace_comments,
    _edge_bare_values,
    _deep_array(),
    _deep_inline_table(),
)

_document_full = st.one_of(
    _document,
    _edge_docs,
)

strategy = _document_full.map(_no_nul)
```