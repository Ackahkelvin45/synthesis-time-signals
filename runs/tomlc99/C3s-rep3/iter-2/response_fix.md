```python
from hypothesis import strategies as st
import json

# ---------- small building blocks ----------

_ws = st.sampled_from(["", " ", "\t", "  "])
_comment_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r\x00"),
    max_size=20,
)
_comment = st.one_of(
    st.just(""),
    _comment_text.map(lambda s: "#" + s),
)

_nl = st.sampled_from(["\n", "\r\n"])

# ---------- keys ----------

_unquoted_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)
_unquoted_key = st.text(_unquoted_char, min_size=1, max_size=12)

_basic_str_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\n\r\x00'),
    st.sampled_from(["\\n", "\\t", "\\r", "\\b", "\\f", "\\\\", '\\"', "\\/"]),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\u%04X" % (n & 0xFFFF)),
    st.sampled_from(["\x01", "\x02", "\x1f", "\x7f"]),
)
_basic_string = st.lists(_basic_str_char, max_size=8).map(
    lambda parts: '"' + "".join(parts) + '"'
)
_literal_string = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="'\n\r\x00"),
    max_size=8,
).map(lambda s: "'" + s + "'")

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------- scalars ----------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
    st.sampled_from(["0", "-0", "+0", "007", "1_000", "123456789012345678901234567890"]),
)
_hex_int = st.sampled_from(["0x0", "0xDEAD_beef", "0xFF", "0x1_2_3"])
_oct_int = st.sampled_from(["0o0", "0o777", "0o1_7"])
_bin_int = st.sampled_from(["0b0", "0b1010", "0b1_0_1"])
_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(
        [
            "1.",
            ".5",
            "1e309",
            "-1e309",
            "1E-10",
            "3.14",
            "1_0.0_1",
            "0.0",
            "-0.0",
        ]
    ),
)
_inf_nan = st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"])
_floating_point = st.one_of(_float, _inf_nan)

_bool = st.sampled_from(["true", "false"])

_date = st.sampled_from(
    [
        "1979-05-27",
        "1979-02-30",
        "0000-00-00",
        "9999-12-31",
    ]
)
_local_time = st.sampled_from(["07:32:00", "00:00:00.000001", "23:59:59.999999"])
_local_dt = st.sampled_from(
    [
        "1979-05-27T07:32:00",
        "1979-05-27t07:32:00.999",
        "1979-05-27 07:32:00",
    ]
)
_offset_dt = st.sampled_from(
    [
        "1979-05-27T07:32:00Z",
        "1979-05-27T00:32:00-07:00",
        "1979-05-27 07:32:00+00:00",
    ]
)
_date_time = st.one_of(_date, _local_time, _local_dt, _offset_dt)

_ml_basic = st.lists(
    st.one_of(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        st.sampled_from(["\\\n", "\\n", "\\u0041"]),
    ),
    max_size=6,
).map(lambda parts: '"""' + "".join(parts) + '"""')

_ml_literal = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    max_size=10,
).map(lambda s: "'''" + s + "'''")

_string = st.one_of(_basic_string, _literal_string, _ml_basic, _ml_literal)

# ---------- recursive structures ----------

# leaf values (non-container)
_leaf_value = st.one_of(
    _string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
)

# forward-declared recursive value strategy
_value = st.deferred(lambda: _value_strategy)

def _make_inline_table(inner):
    def build(pairs):
        if not pairs:
            return "{}"
        body = ", ".join("%s = %s" % (k, v) for (k, v) in pairs)
        return "{" + body + "}"
    return st.lists(
        st.tuples(_key, inner),
        max_size=3,
    ).map(build)

def _make_array(inner):
    def build(items):
        if not items:
            return "[]"
        return "[" + ", ".join(items) + "]"
    return st.lists(inner, max_size=4).map(build)

# Build value strategy using recursive with depth control.
# We combine: leaves, arrays of values, inline tables of values.
_value_strategy = st.one_of(
    _leaf_value,
    st.recursive(
        _leaf_value,
        lambda children: st.one_of(
            _make_array(children),
            _make_inline_table(children),
        ),
        max_leaves=20,
    ),
)

# ---------- key/value lines ----------

_kv_line = st.builds(
    lambda k, v, c: "%s = %s%s" % (k, v, c),
    _key,
    _value,
    _comment,
)

# table headers
_standard_table = _key.map(lambda k: "[%s]" % k)
_array_table = _key.map(lambda k: "[[%s]]" % k)
_table = st.one_of(_standard_table, _array_table)

# ---------- documents ----------

def _join_lines(lines):
    return "\n".join(lines)

_line = st.one_of(
    _kv_line,
    _table,
    _comment,
)

_document = st.lists(_line, max_size=8).map(_join_lines)

# ---------- malformed / edge-case variants ----------

def _mangle_one(s):
    """Produce a near-valid-but-malformed variant of a document."""
    if not s:
        return s
    # choose a mutation index safely
    n = len(s)
    i = n // 2
    ch = s[i]
    if ch in "[]{}":
        # drop a delimiter
        return s[:i] + s[i + 1:]
    if ch == '"':
        # unterminated string: drop closing quote if present
        if s.count('"') % 2 == 1:
            return s  # already unbalanced
        # remove last quote
        j = s.rfind('"')
        return s[:j] + s[j + 1:]
    if ch in "=":
        # doubled equals
        return s[:i] + "==" + s[i + 1:]
    # stray token
    return s[:i] + "@" + s[i:]

_malformed = _document.map(_mangle_one)

# empty / comment-only docs, no trailing newline
_empty_doc = st.just("")
_comment_only = st.lists(_comment, min_size=1, max_size=3).map("\n".join)

# deep nesting band 1500-2048
_deep_depth = st.integers(min_value=1500, max_value=2048)

def _deep_array(depth):
    return "a = " + ("[" * depth) + ("]" * depth)

_deep_doc = _deep_depth.map(_deep_array)

def _deep_inline(depth):
    # nested inline tables: {a = {a = ... }}
    return "a = " + ("{a = " * depth) + "1" + ("}" * depth)

_deep_inline_doc = _deep_depth.map(_deep_inline)

# duplicate keys (rejected but interesting)
_dup_keys = st.builds(
    lambda k, v: "%s = %s\n%s = %s" % (k, v, k, v),
    _unquoted_key,
    _leaf_value,
)

# non-ASCII bare key (rejected)
_nonascii_key = st.just("kéy = 1")

# newline inside inline table (rejected)
_nl_inline = st.just("a = {b = 1,\nc = 2}")

# invalid escape (rejected)
_bad_escape = st.just('a = "x\\qy"')

# unterminated string (rejected)
_unterminated = st.just('a = "unterminated')

# value on next line (rejected)
_val_next_line = st.just("a =\n1")

# trailing comma in inline table (accepted, deviation)
_trailing_comma_inline = st.just("a = {b = 1,}")

# leading zeros (accepted, deviation)
_leading_zero = st.just("a = 007")

# float no digits (accepted, deviation)
_float_odd = st.just("a = 1.")

# calendar-invalid date (accepted, deviation)
_bad_date = st.just("a = 1979-02-30")

# raw control char in string (accepted, deviation)
_ctrl_in_string = st.just('a = "x\x01y"')

# control char in comment (accepted, deviation)
_ctrl_in_comment = st.just("# comment\x02")

# empty quoted key
_empty_key = st.just('"" = 1')

# long key
_long_key = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r\x00="),
    min_size=1000,
    max_size=1000,
).map(lambda s: s.replace(" ", "")[:1000]).filter(lambda s: len(s) == 1000).map(
    lambda s: s + " = 1"
)

# CRLF and tab indentation
_crlf_doc = st.just("a = 1\r\nb = 2\r\n")
_tab_indent = st.just("\ta = 1\n")

# super-table after sub-table
_super_after_sub = st.just("[a.b]\nx = 1\n\n[a]\ny = 2\n")

# mixed-type array
_mixed_array = st.just('a = [1, "two", 3.0, true, 1979-05-27]')

# multiline array with comments
_ml_array = st.just("a = [\n  1, # one\n  2, # two\n]")

# empty containers
_empty_containers = st.just("a = []\nb = {}\n[t]\n[[u]]\n")

# all value kinds
_all_kinds = st.just(
    'a = "basic"\n'
    "b = 'literal'\n"
    'c = """ml basic"""\n'
    "d = '''ml literal'''\n"
    "e = 42\n"
    "f = 0xDEAD\n"
    "g = 0o777\n"
    "h = 0b1010\n"
    "i = 3.14\n"
    "j = inf\n"
    "k = nan\n"
    "l = true\n"
    "m = false\n"
    "n = 1979-05-27\n"
    "o = 07:32:00\n"
    "p = 1979-05-27T07:32:00\n"
    "q = 1979-05-27T07:32:00Z\n"
    "r = [1, 2]\n"
    "s = {x = 1}\n"
)

# ---------- combine everything ----------

strategy = st.one_of(
    _document,
    _malformed,
    _empty_doc,
    _comment_only,
    _deep_doc,
    _deep_inline_doc,
    _dup_keys,
    _nonascii_key,
    _nl_inline,
    _bad_escape,
    _unterminated,
    _val_next_line,
    _trailing_comma_inline,
    _leading_zero,
    _float_odd,
    _bad_date,
    _ctrl_in_string,
    _ctrl_in_comment,
    _empty_key,
    _long_key,
    _crlf_doc,
    _tab_indent,
    _super_after_sub,
    _mixed_array,
    _ml_array,
    _empty_containers,
    _all_kinds,
)
```