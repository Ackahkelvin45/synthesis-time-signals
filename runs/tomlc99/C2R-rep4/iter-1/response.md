```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _join(parts):
    return "".join(parts)


# ---------------------------------------------------------------------------
# Scalar lexical pieces
# ---------------------------------------------------------------------------

# Keys: unquoted (ASCII only), quoted (basic/literal), dotted.
_unquoted_key = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"),
    min_size=1,
    max_size=12,
)

# Basic-string body: escapes, non-ASCII text, raw control bytes (except NUL).
_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04X" % n),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08X" % n),
    # malformed escape (near-valid-but-malformed)
    st.sampled_from(["\\q", "\\x", "\\u12", "\\U0000", "\\"]),
)

_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(lambda c: c not in '"\\'),
    st.characters(min_codepoint=0x01, max_codepoint=0x1F),  # raw control bytes, no NUL
    st.sampled_from(["\x7f", "\x80", "\u00e9", "\u4e2d", "\U0001F600"]),
)

_basic_body = st.one_of(
    st.lists(_basic_char, max_size=8).map(_join),
    st.lists(st.one_of(_basic_char, _escape), max_size=8).map(_join),
)

_basic_string = _basic_body.map(lambda s: '"' + s + '"')

_literal_body = st.one_of(
    st.lists(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(lambda c: c != "'"),
            st.characters(min_codepoint=0x01, max_codepoint=0x1F),
        ),
        max_size=8,
    ).map(_join),
)

_literal_string = _literal_body.map(lambda s: "'" + s + "'")

# Multiline strings.
_ml_basic = st.one_of(
    st.lists(st.one_of(_basic_char, _escape, st.sampled_from(["\n", "\r\n"])), max_size=8).map(
        lambda parts: '"""' + _join(parts) + '"""'
    ),
)

_ml_literal = st.one_of(
    st.lists(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(lambda c: c != "'"),
            st.characters(min_codepoint=0x01, max_codepoint=0x1F),
            st.sampled_from(["\n", "\r\n"]),
        ),
        max_size=8,
    ).map(lambda parts: "'''" + _join(parts) + "'''"),
)

# Unterminated variants (near-valid-but-malformed).
_unterminated_string = st.one_of(
    _basic_body.map(lambda s: '"' + s),
    _literal_body.map(lambda s: "'" + s),
    st.lists(st.one_of(_basic_char, _escape), max_size=6).map(lambda p: '"""' + _join(p)),
    st.lists(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(lambda c: c != "'"),
        max_size=6,
    ).map(lambda p: "'''" + _join(p)),
)

# Integers.
_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
    st.integers(min_value=0, max_value=99).map(lambda n: "0" + str(n)),  # leading zeros
    st.integers(min_value=0, max_value=10 ** 20).map(
        lambda n: "1_" + "_".join(str(n))
    ),
    st.sampled_from(["0", "-0", "+0", "007", "0_0", "1_000_000"]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0x%X" % n),
    st.sampled_from(["0x0", "0xDEAD_BEEF", "0xdeadbeef", "0x_1"]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 40).map(lambda n: "0o%o" % n),
    st.sampled_from(["0o0", "0o7", "0o1_2_3"]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 40).map(lambda n: "0b" + bin(n)[2:]),
    st.sampled_from(["0b0", "0b1_0_1", "0b1111"]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# Floats.
_plain_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False, width=64).map(repr),
    st.sampled_from(
        [
            "1.0",
            "1.",
            ".5",
            "0.0",
            "-0.0",
            "3.14159",
            "1e10",
            "1E-10",
            "1_000.000_1",
            "1e309",
            "1e-309",
            "1.7976931348623157e308",
            "5e-324",
            "0e0",
            "1.5e+300",
        ]
    ),
    st.integers(min_value=1, max_value=10 ** 6).map(lambda n: "%d.%d" % (n, n)),
)

_float = st.one_of(
    _plain_float,
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
)

# Booleans.
_boolean = st.sampled_from(["true", "false"])

# Dates / times.
_date = st.one_of(
    st.sampled_from(
        [
            "1979-05-27",
            "0000-00-00",
            "1979-02-30",  # calendar-invalid, accepted
            "9999-12-31",
            "2024-01-01",
        ]
    ),
    st.tuples(
        st.integers(min_value=0, max_value=9999),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ).map(lambda t: "%04d-%02d-%02d" % t),
)

_time = st.one_of(
    st.sampled_from(["07:32:00", "00:00:00", "23:59:59", "07:32:00.999999"]),
    st.tuples(
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ).map(lambda t: "%02d:%02d:%02d" % t),
)

_offset = st.sampled_from(["Z", "z", "+00:00", "-07:00", "+23:59"])

_datetime = st.one_of(
    st.tuples(_date, _time).map(lambda t: t[0] + "T" + t[1]),
    st.tuples(_date, _time).map(lambda t: t[0] + "t" + t[1]),
    st.tuples(_date, _time).map(lambda t: t[0] + " " + t[1]),
    st.tuples(_date, _time, _offset).map(lambda t: t[0] + "T" + t[1] + t[2]),
    st.tuples(_date, _time, _offset).map(lambda t: t[0] + " " + t[1] + t[2]),
    _date,
    _time,
)


# ---------------------------------------------------------------------------
# Recursive value grammar (arrays / inline tables)
# ---------------------------------------------------------------------------

# Depth band: concentrate interesting depth in 1500-2048.
_deep_depth = st.integers(min_value=1500, max_value=2048)
_shallow_depth = st.integers(min_value=0, max_value=4)

# Scalar strings (all four quoting forms).
_string = st.one_of(_basic_string, _ml_basic, _literal_string, _ml_literal)

# A scalar value (non-recursive).
_scalar_value = st.one_of(
    _string,
    _integer,
    _float,
    _boolean,
    _datetime,
    _unterminated_string,
)

# Key variants.
_quoted_key = st.one_of(
    _basic_string,
    _literal_string,
    st.just('""'),  # empty quoted key
    st.just("''"),
)
_simple_key = st.one_of(_unquoted_key, _quoted_key)
_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(".".join)
_key = st.one_of(_simple_key, _dotted_key)

# Near-valid-but-malformed raw tokens.
_malformed = st.sampled_from(
    [
        "=",
        "]",
        "}",
        "[",
        "{",
        "[[",
        "]]",
        "a =",
        "a = = 1",
        "a 1",
        "a = 1 2",
        "a = 1,",
        "a = {b = 1,}",
        "a = [1, 2,]",
        "a = {b = 1",
        "a = [1, 2",
        '"unterminated',
        "'unterminated",
        "a = '\\q'",
        "a = 1\nb",
    ]
)

# Recursive value strategy.
_value = st.recursive(
    _scalar_value,
    lambda children: st.one_of(
        # Array
        st.lists(
            st.one_of(children, _malformed),
            max_size=6,
        ).map(lambda items: "[" + ", ".join(items) + "]"),
        # Array with trailing comma
        st.lists(children, min_size=1, max_size=6).map(
            lambda items: "[" + ", ".join(items) + ",]"
        ),
        # Empty array
        st.just("[]"),
        # Array with newlines / comments
        st.lists(children, max_size=4).map(
            lambda items: "[\n" + ",\n".join(items) + "\n]"
        ),
        # Inline table
        st.lists(
            st.tuples(_key, children).map(lambda kv: kv[0] + " = " + kv[1]),
            max_size=4,
        ).map(lambda kvs: "{" + ", ".join(kvs) + "}"),
        # Inline table with trailing comma
        st.lists(
            st.tuples(_key, children).map(lambda kv: kv[0] + " = " + kv[1]),
            min_size=1,
            max_size=4,
        ).map(lambda kvs: "{" + ", ".join(kvs) + ",}"),
        # Empty inline table
        st.just("{}"),
    ),
    max_leaves=20,
)

# Deep nested arrays / inline tables in the 1500-2048 band.
_deep_nested_array = _deep_depth.map(lambda d: "[" * d + "]" * d)
_deep_nested_inline = _deep_depth.map(
    lambda d: "{a = " * d + "1" + "}" * d
)


# ---------------------------------------------------------------------------
# Document-level productions
# ---------------------------------------------------------------------------

_comment = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(min_codepoint=0x01, max_codepoint=0x10FFFF),
        max_size=20,
    ).map(lambda s: "#" + s),
)

_key_value = st.tuples(_key, _value).map(lambda kv: kv[0] + " = " + kv[1])

_standard_table = _key.map(lambda k: "[" + k + "]")
_array_table = _key.map(lambda k: "[[" + k + "]]")

_expression = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
    _malformed,
)

_document = st.lists(_expression, max_size=8).map(lambda lines: "\n".join(lines))

# Empty / comment-only documents.
_empty_doc = st.sampled_from(["", "\n", "# comment only", "#\n#\n"])

# Duplicate keys / tables (expected rejection).
_dup_keys = st.tuples(_key, _value).map(
    lambda kv: kv[0] + " = " + kv[1] + "\n" + kv[0] + " = " + kv[1]
)
_dup_tables = _key.map(lambda k: "[" + k + "]\n[" + k + "]")

# Table + array-of-tables with same name.
_table_and_array = _key.map(lambda k: "[" + k + "]\n[[" + k + "]]")

# Dotted key redefining a table.
_dotted_redef = _key.map(lambda k: "[" + k + "]\n" + k + ".x = 1")


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _empty_doc,
    _deep_nested_array,
    _deep_nested_inline,
    _dup_keys,
    _dup_tables,
    _table_and_array,
    _dotted_redef,
    # Single value documents
    _key_value,
    _comment,
    _malformed,
)
```