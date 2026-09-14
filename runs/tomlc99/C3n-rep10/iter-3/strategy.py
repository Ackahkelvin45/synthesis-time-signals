from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _j(*parts):
    return "".join(parts)

# ---------- scalar leaves ----------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

_basic_body_char = st.one_of(
    _safe_chars.filter(lambda c: c not in '"\\\n'),
    st.sampled_from(["\\t", "\\n", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\/"]),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\u%04X" % (n & 0xFFFF)),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08X" % n),
    st.sampled_from(["\\u0000", "\\U00000000", "\\uD800", "\\uDFFF"]),
    st.just("\x01"),
    st.just("\x7f"),
    st.just("\t"),
)

_basic_string_body = st.lists(_basic_body_char, max_size=8).map("".join)

_literal_body_char = st.one_of(
    _safe_chars.filter(lambda c: c not in "'\n"),
    st.just("\t"),
    st.just("\x01"),
    st.just("\x7f"),
)

_literal_string_body = st.lists(_literal_body_char, max_size=8).map("".join)

_ml_basic_body_char = st.one_of(
    _safe_chars.filter(lambda c: c != "\\"),
    st.sampled_from(["\\\n", "\\\r\n", "\\t", "\\n", "\\\"", "\\\\", "\\u0041", "\\U0001F600"]),
    st.just("\n"),
    st.just("\r\n"),
    st.just("\x01"),
    st.just("\t"),
)
_ml_basic_body = st.lists(_ml_basic_body_char, max_size=8).map("".join)

_ml_literal_body_char = st.one_of(
    _safe_chars.filter(lambda c: c != "'"),
    st.just("\n"),
    st.just("\r\n"),
    st.just("\x01"),
    st.just("\t"),
)
_ml_literal_body = st.lists(_ml_literal_body_char, max_size=8).map("".join)

basic_string = _basic_string_body.map(lambda b: '"' + b + '"')
literal_string = _literal_string_body.map(lambda b: "'" + b + "'")
ml_basic_string = _ml_basic_body.map(lambda b: '"""' + b + '"""')
ml_literal_string = _ml_literal_body.map(lambda b: "'''" + b + "'''")

any_string = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# malformed strings
unterminated_basic = _basic_string_body.map(lambda b: '"' + b)
unterminated_literal = _literal_string_body.map(lambda b: "'" + b)

# ---------- keys ----------

_unquoted_key = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_", min_size=1, max_size=6),
    st.just(""),
    st.text(alphabet="abcXYZ019-_", min_size=1, max_size=10000),
)

_quoted_key = st.one_of(basic_string, literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

# dotted key: at least two simple keys
_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------- numbers ----------

_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.integers(min_value=-2**63, max_value=2**63).map(str),
    st.just("007"),
    st.just("0"),
    st.just("-0"),
    st.just("+0"),
    st.sampled_from(["1_000", "1_0_0", "9223372036854775807", "-9223372036854775808", "9223372036854775808", "99999999999999999999999999"]),
)

_hex_int = st.one_of(
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8).map(lambda s: "0x" + s),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xfffffffffffffffff"]),
)

_oct_int = st.one_of(
    st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda s: "0o" + s),
    st.sampled_from(["0o0", "0o777", "0o7_7_7"]),
)

_bin_int = st.one_of(
    st.text(alphabet="01", min_size=1, max_size=8).map(lambda s: "0b" + s),
    st.sampled_from(["0b0", "0b1010", "0b1_0_1"]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False, width=64).map(repr),
    st.sampled_from([
        "1.0", "1.", ".5", "-.5", "+1.", "0.0", "3.14", "1e10", "1E10", "1e+10",
        "1e-10", "1_000.000_1", "1e309", "-1e309", "1e-309", "0e0",
        "6.626e-34", "1.0e10", "1.0e+10",
    ]),
    st.integers(min_value=-1000, max_value=1000).map(lambda n: "%de%d" % (n, 5)),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_floating_point = st.one_of(_float, _inf_nan)

_bool = st.sampled_from(["true", "false"])

# ---------- dates ----------

def _dt2(n):
    return "%02d" % (n % 100)

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
    _time,
    st.integers(min_value=0, max_value=999999),
).map(lambda t: "%s.%06d" % (t[0], t[1]))

_partial_time = st.one_of(_time, _time_frac)

_offset = st.one_of(
    st.just("Z"),
    st.tuples(
        st.sampled_from(["+", "-"]),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ).map(lambda t: "%s%02d:%02d" % t),
)

_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(_date, _delim, _partial_time, _offset).map(lambda t: "%s%s%s%s" % t)
_local_date_time = st.tuples(_date, _delim, _partial_time).map(lambda t: "%s%s%s" % t)
_local_date = _date
_local_time = _partial_time

_date_time = st.one_of(_offset_date_time, _local_date_time, _local_date, _local_time)

# ---------- recursive values ----------

_leaf = st.one_of(
    any_string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
)

def _array_body(v):
    # array element with optional commas/newlines/comments
    return st.one_of(
        st.lists(v, max_size=4).map(lambda xs: ", ".join(xs)),
        st.lists(v, max_size=4).map(lambda xs: ", ".join(xs) + ","),
        st.lists(v, max_size=3).map(lambda xs: ",\n".join(xs)),
        st.lists(v, max_size=3).map(lambda xs: ",\n".join(xs) + ",\n"),
        st.just(""),
    )

def _inline_keyvals(v):
    def one_pair(key):
        return st.tuples(st.just(key), v).map(lambda t: "%s = %s" % t)
    return st.lists(_key, min_size=0, max_size=3).flatmap(
        lambda keys: st.lists(
            st.one_of(*[one_pair(k) for k in keys]) if keys else st.just("x = 1"),
            min_size=0, max_size=3,
        )
    )

def _inline_table(v):
    return _inline_keyvals(v).map(lambda pairs: "{ " + ", ".join(pairs) + " }")

def _inline_table_trailing_comma(v):
    return _inline_keyvals(v).map(lambda pairs: "{ " + ", ".join(pairs) + ", }")

def _array(v):
    return _array_body(v).map(lambda body: "[" + body + "]")

def _array_deep(depth):
    # nested arrays up to depth
    def build(n):
        if n <= 0:
            return st.one_of(any_string, _integer, _bool)
        return st.one_of(
            build(0),
            build(n - 1).map(lambda s: "[" + s + "]"),
        )
    return build(depth)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        _array(children),
        _inline_table(children),
        _inline_table_trailing_comma(children),
    ),
    max_leaves=20,
)

# deep nesting value (1500-2048)
def _deep_value_build(d):
    # Build a deeply nested array string directly without recursion in the
    # strategy graph, to avoid RecursionError during generation.
    return "[" * d + "1" + "]" * d

_deep_value = st.integers(min_value=1500, max_value=2048).map(_deep_value_build)

# ---------- documents ----------

def _key_value(v):
    return st.tuples(_key, v).map(lambda t: "%s = %s" % t)

def _key_value_comment(v):
    return st.tuples(_key_value(v), st.one_of(st.just(""), st.text(alphabet="abc #\t", max_size=10))).map(
        lambda t: t[0] + (" # " + t[1] if t[1] else "")
    )

def _standard_table():
    return _key.map(lambda k: "[%s]" % k)

def _array_table():
    return _key.map(lambda k: "[[%s]]" % k)

def _comment():
    return st.one_of(
        st.just("#"),
        st.text(alphabet="abc XYZ\t\x01\x7f", max_size=20).map(lambda s: "# " + s),
    )

def _empty_line():
    return st.just("")

def _statement(v):
    return st.one_of(
        _key_value_comment(v),
        _standard_table(),
        _array_table(),
        _comment(),
        _empty_line(),
    )

def _document(v):
    return st.lists(_statement(v), min_size=0, max_size=6).map(lambda lines: "\n".join(lines))

# malformed / near-valid documents
def _malformed(v):
    return st.one_of(
        # stray token
        st.tuples(_key, v).map(lambda t: "%s = %s extra" % t),
        # missing '='
        st.tuples(_key, v).map(lambda t: "%s %s" % t),
        # doubled delimiter
        st.tuples(_key, v).map(lambda t: "%s == %s" % t),
        # unterminated string
        st.tuples(_key, st.one_of(unterminated_basic, unterminated_literal)).map(
            lambda t: "%s = %s" % t
        ),
        # value on next line
        st.tuples(_key, v).map(lambda t: "%s =\n%s" % t),
        # newline inside inline table
        st.tuples(_key, v).map(lambda t: '%s = { a = 1,\n b = %s }' % t),
        # bad escape
        st.tuples(_key, st.just('"a\\qb"')).map(lambda t: "%s = %s" % t),
        # non-ASCII bare key
        st.tuples(st.just("kéy"), v).map(lambda t: "%s = %s" % t),
        # missing closing bracket
        st.tuples(_key, v).map(lambda t: "[%s\n%s = %s" % (t[0], t[0], t[1])),
        # missing closing brace
        st.tuples(_key, v).map(lambda t: "%s = { a = %s" % t),
        # doubled comma
        st.tuples(_key, v).map(lambda t: "%s = [%s,, %s]" % (t[0], t[1], t[1])),
        # unterminated array
        st.tuples(_key, v).map(lambda t: "%s = [%s" % t),
        # duplicate key
        st.tuples(_key, v).map(lambda t: "%s = %s\n%s = %s" % (t[0], t[1], t[0], t[1])),
        # duplicate table
        st.tuples(_key, v).map(lambda t: "[%s]\na = 1\n[%s]\nb = 2" % (t[0], t[0])),
        # empty quoted key valid
        st.just('"" = 1'),
        # empty doc
        st.just(""),
        # comment only
        st.just("# just a comment"),
    )

# ---------- utf8 decoding coverage ----------

# Exercise toml_utf8_to_ucs by embedding raw non-ASCII UTF-8 byte sequences
# (multi-byte lead/continuation bytes) inside strings, keys, and comments.
_utf8_multibyte = st.sampled_from([
    "\u00e9",      # 2-byte
    "\u00ff",
    "\u07ff",
    "\u0800",      # 3-byte
    "\u4e2d",
    "\uffff",
    "\U00010000",  # 4-byte
    "\U0001F600",
    "\U0010FFFF",
])

# Raw bytes that form (in)valid UTF-8 sequences, embedded via latin-1 chars.
_utf8_raw_bytes = st.lists(
    st.integers(min_value=0x80, max_value=0xFF),
    min_size=1, max_size=6,
).map(lambda bs: "".join(chr(b) for b in bs))

_utf8_payload = st.one_of(_utf8_multibyte, _utf8_raw_bytes)

def _utf8_string():
    return st.lists(
        st.one_of(_safe_chars, _utf8_payload),
        max_size=6,
    ).map(lambda cs: '"' + "".join(cs) + '"')

_utf8_key = _utf8_payload

_utf8_doc = st.one_of(
    st.tuples(_utf8_key, _utf8_payload).map(lambda t: '"%s" = "%s"' % t),
    st.tuples(_utf8_key, _utf8_payload).map(lambda t: "%s = '%s'" % (t[0], t[1])),
    _utf8_payload.map(lambda s: "# " + s),
    _utf8_payload.map(lambda s: "[" + s + "]"),
    _utf8_string().map(lambda s: "k = " + s),
    st.tuples(_utf8_key, _utf8_payload).map(lambda t: "'''%s''' = 1" % t[0]),
    st.tuples(_utf8_key, _utf8_payload).map(lambda t: '"""%s""" = 1' % t[0]),
)

# ---------- final assembly ----------

_document_strategy = st.one_of(
    _document(_value),
    _malformed(_value),
    st.tuples(_key, _deep_value).map(lambda t: "%s = %s" % t),
    _document(_deep_value),
    st.tuples(_key, _value).map(lambda t: "%s = %s" % t),  # single line
    st.just("\r\n".join(["a = 1", "b = 2"])),
    st.just("a = 1\r\nb = 2\r\n"),
    st.just("\ta = 1"),
    st.tuples(_key, _value).map(lambda t: "%s=%s" % t),
    st.tuples(_key, _value).map(lambda t: "%s = %s" % t),  # no trailing newline
    _utf8_doc,
)

strategy = _document_strategy