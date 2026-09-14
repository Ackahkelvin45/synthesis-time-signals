```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Low level character / token helpers
# ---------------------------------------------------------------------------

# Bare (unquoted) key characters accepted by the parser: A-Za-z0-9_- only.
_BARE_KEY_CHARS = st.sampled_from(
    list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    + list("abcdefghijklmnopqrstuvwxyz")
    + list("0123456789")
    + ["-", "_"]
)

# Characters that are safe inside quoted strings without escaping.
_SAFE_STRING_CHARS = st.sampled_from(
    list("abcXYZ0123456789 _-.,:;!?@#$%^&*()+=|~`<>/")
    + ["\t", "\r"]
    + ["\u00e9", "\u00fc", "\u4e2d", "\u6587", "\U0001f600", "\u00a0"]
)

# Raw control bytes (excluding NUL, which the harness skips).
_RAW_CONTROL_BYTES = st.sampled_from(
    [chr(c) for c in range(1, 9)] + [chr(c) for c in range(14, 32)] + [chr(0x7F)]
)

# A single escape sequence body (without the leading backslash).
_ESCAPE_BODY = st.one_of(
    st.sampled_from(['"', "\\", "/", "b", "f", "n", "r", "t"]),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "u%04X" % n),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "U%08X" % n),
)

# A complete escape (leading backslash included).
_ESCAPE = _ESCAPE_BODY.map(lambda b: "\\" + b)


def _basic_string_char():
    return st.one_of(
        _SAFE_STRING_CHARS,
        _RAW_CONTROL_BYTES,
        _ESCAPE,
        # JSON-ish unicode escapes via json.dumps for extra variety
        st.integers(min_value=0, max_value=0x10FFFF).map(
            lambda n: json.dumps(chr(n))[1:-1]
        ),
    )


# ---------------------------------------------------------------------------
# Strings: all four quoting forms
# ---------------------------------------------------------------------------

_basic_string = st.lists(
    _basic_string_char(), min_size=0, max_size=12
).map(lambda cs: '"' + "".join(cs) + '"')

_literal_string = st.lists(
    st.one_of(_SAFE_STRING_CHARS, _RAW_CONTROL_BYTES, st.just("\\")),
    min_size=0,
    max_size=12,
).map(lambda cs: "'" + "".join(cs) + "'")


def _ml_basic_char():
    return st.one_of(
        _SAFE_STRING_CHARS,
        _RAW_CONTROL_BYTES,
        _ESCAPE,
        st.just("\n"),
        st.just("\\\n"),
        st.just("\\\r\n"),
    )


_ml_basic_string = st.lists(
    _ml_basic_char(), min_size=0, max_size=10
).map(lambda cs: '"""' + "".join(cs) + '"""')

_ml_literal_string = st.lists(
    st.one_of(_SAFE_STRING_CHARS, _RAW_CONTROL_BYTES, st.just("\n")),
    min_size=0,
    max_size=10,
).map(lambda cs: "'''" + "".join(cs) + "'''")

# Upweighted: multi-line literal strings, including newlines, quotes, and
# backslashes (which are literal, not escapes, inside '''...''').
_ml_literal_string_upweighted = st.one_of(
    _ml_literal_string,
    st.lists(
        st.one_of(
            _SAFE_STRING_CHARS,
            _RAW_CONTROL_BYTES,
            st.just("\n"),
            st.just("\r\n"),
            st.just("\\"),
            st.just('"'),
            st.just("'"),
        ),
        min_size=0,
        max_size=16,
    ).map(lambda cs: "'''" + "".join(cs) + "'''"),
    st.lists(
        st.one_of(
            _SAFE_STRING_CHARS,
            _RAW_CONTROL_BYTES,
            st.just("\n"),
            st.just("\\"),
        ),
        min_size=1,
        max_size=8,
    ).map(lambda cs: "'''\n" + "".join(cs) + "\n'''"),
)

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string_upweighted,
)


# ---------------------------------------------------------------------------
# Integers: all bases, underscores, extremes
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 64), max_value=2 ** 64).map(str),
    st.integers(min_value=-(2 ** 200), max_value=2 ** 200).map(str),
    st.sampled_from(
        [
            "0", "-0", "+0", "007", "-007", "+007",
            "1_000", "1_0_0_0", "9_223_372_036_854_775_807",
            "-9_223_372_036_854_775_808",
            "99999999999999999999999999999999999999999999999999",
            "-99999999999999999999999999999999999999999999999999",
        ]
    ),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0x%X" % n),
    st.sampled_from(["0x0", "0xDEAD_BEEF", "0xdeadbeef", "0xFFFFFFFFFFFFFFFF"]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 30).map(lambda n: "0o%o" % n),
    st.sampled_from(["0o0", "0o777", "0o1_2_3", "0o1777777777777777777777"]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0b" + bin(n)[2:]),
    st.sampled_from(["0b0", "0b1", "0b1010_1010", "0b" + "1" * 64]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)


# ---------------------------------------------------------------------------
# Floats: normal, extremes, inf/nan, lenient forms
# ---------------------------------------------------------------------------

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(
        [
            "1.0", "-1.0", "+1.0", "3.14159", "1e10", "1E10", "-1e-10",
            "1e+10", "1.5e10", "1_000.000_1", "1.", ".5", "-.5", "1.e10",
            "1e309", "-1e309", "1e-309", "0.0", "-0.0",
            "1.7976931348623157e308",
            "2.2250738585072014e-308",
            "4.9e-324",
        ]
    ),
    st.integers(min_value=-1000, max_value=1000).map(lambda n: "%d.0" % n),
)

_inf_nan = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

_floating_point = st.one_of(_float, _inf_nan)


# ---------------------------------------------------------------------------
# Booleans
# ---------------------------------------------------------------------------

_bool = st.sampled_from(["true", "false"])


# ---------------------------------------------------------------------------
# Date-times: all four forms, including calendar-invalid and lenient
# ---------------------------------------------------------------------------

_date_time = st.one_of(
    st.sampled_from(
        [
            "1979-05-27T07:32:00Z",
            "1979-05-27T00:32:00-07:00",
            "1979-05-27T00:32:00.999999-07:00",
            "1979-05-27 07:32:00Z",
            "1979-05-27t07:32:00z",
            "1979-05-27T07:32:00",
            "1979-05-27T07:32:00.999999",
            "1979-05-27 07:32:00",
            "1979-05-27",
            "07:32:00",
            "07:32:00.999999",
            "0000-00-00",
            "1979-02-30",
            "1979-13-45",
            "9999-99-99T99:99:99Z",
            "1979-05-27T07:32:00+23:59",
            "1979-05-27T07:32:00-23:59",
        ]
    ),
    st.tuples(
        st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
    ).map(lambda t: "%s-%s-%s" % t),
    st.tuples(
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
    ).map(lambda t: "%s:%s:%s" % t),
)


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.lists(
    _BARE_KEY_CHARS, min_size=1, max_size=8
).map(lambda cs: "".join(cs))

_quoted_key = st.one_of(
    _basic_string,
    _literal_string,
    st.just('""'),
    st.just("''"),
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(
    _simple_key, min_size=2, max_size=4
).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)


# ---------------------------------------------------------------------------
# Recursive value strategy: arrays and inline tables
# ---------------------------------------------------------------------------

_value = st.deferred(lambda: _value_strategy)


def _array_values(v):
    return st.one_of(
        # empty array
        st.just("[]"),
        # simple single value
        st.builds(lambda x: "[" + x + "]", v),
        # comma separated values with optional trailing comma
        st.lists(v, min_size=1, max_size=6).map(
            lambda xs: "[" + ", ".join(xs) + "]"
        ),
        st.lists(v, min_size=1, max_size=6).map(
            lambda xs: "[" + ", ".join(xs) + ",]"
        ),
        # multiline array with comments and newlines
        st.lists(v, min_size=1, max_size=5).map(
            lambda xs: "[\n  " + ",\n  ".join(xs) + ",\n]"
        ),
        st.lists(v, min_size=1, max_size=4).map(
            lambda xs: "[\n# c\n" + ",\n# c\n".join(xs) + "\n]"
        ),
    )


def _inline_table(v):
    return st.one_of(
        st.just("{}"),
        st.builds(
            lambda k, val: "{" + k + " = " + val + "}",
            _key,
            v,
        ),
        st.lists(
            st.tuples(_key, v), min_size=1, max_size=5
        ).map(lambda kvs: "{" + ", ".join("%s = %s" % kv for kv in kvs) + "}"),
        st.lists(
            st.tuples(_key, v), min_size=1, max_size=5
        ).map(lambda kvs: "{" + ", ".join("%s = %s" % kv for kv in kvs) + ",}"),
    )


def _make_value():
    return st.one_of(
        _string,
        _integer,
        _floating_point,
        _bool,
        _bool,
        _bool,
        _date_time,
        st.deferred(lambda: _array_values(_value)),
        st.deferred(lambda: _inline_table(_value)),
    )


_value_strategy = _make_value()
_value = st.deferred(lambda: _value_strategy)


# ---------------------------------------------------------------------------
# Key/value lines, tables, comments
# ---------------------------------------------------------------------------

_comment_text = st.lists(
    st.one_of(
        _SAFE_STRING_CHARS,
        _RAW_CONTROL_BYTES,
        st.sampled_from(["#", "=", "[", "]", "{", "}", ",", '"', "'"]),
    ),
    min_size=0,
    max_size=20,
).map(lambda cs: "#" + "".join(cs))

_comment = st.one_of(st.just("#"), _comment_text)

_key_value = st.builds(
    lambda k, v: k + " = " + v,
    _key,
    _value,
)

_standard_table = st.builds(
    lambda k: "[" + k + "]",
    _key,
)

_array_table = st.builds(
    lambda k: "[[" + k + "]]",
    _key,
)

# Upweighted: inline tables with one or more key/value pairs.
_inline_table_keyvals_non_empty = st.one_of(
    st.builds(
        lambda k, v: "{" + k + " = " + v + "}",
        _key,
        _value,
    ),
    st.lists(
        st.tuples(_key, _value), min_size=2, max_size=6
    ).map(lambda kvs: "{" + ", ".join("%s = %s" % kv for kv in kvs) + "}"),
    st.lists(
        st.tuples(_key, _value), min_size=2, max_size=6
    ).map(lambda kvs: "{" + ", ".join("%s = %s" % kv for kv in kvs) + ",}"),
    st.lists(
        st.tuples(_key, _value), min_size=2, max_size=4
    ).map(lambda kvs: "{\n  " + ",\n  ".join("%s = %s" % kv for kv in kvs) + ",\n}"),
)

_expression = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

_document = st.one_of(
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("# only a comment\n"),
    st.lists(_expression, min_size=1, max_size=10).map(
        lambda es: "\n".join(es)
    ),
    st.lists(_expression, min_size=1, max_size=10).map(
        lambda es: "\n".join(es) + "\n"
    ),
    st.lists(_expression, min_size=1, max_size=10).map(
        lambda es: "\r\n".join(es) + "\r\n"
    ),
    st.lists(_expression, min_size=1, max_size=10).map(
        lambda es: "\n".join(es)
    ),
    st.lists(_expression, min_size=1, max_size=10).map(
        lambda es: "\n".join(es)
    ),
)


# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    # missing closing delimiter
    st.builds(lambda k, v: k + " = [" + v, _key, _value),
    st.builds(lambda k, v: k + " = {" + v, _key, _value),
    st.builds(lambda k: "[" + k, _key),
    st.builds(lambda k: "[[" + k, _key),
    # doubled delimiter
    st.builds(lambda k, v: k + " = [[ " + v + "]]]", _key, _value),
    st.builds(lambda k, v: k + " = {{" + v + "}}", _key, _value),
    st.builds(lambda k: "[[" + k + "]]]", _key),
    # unterminated strings
    st.builds(lambda k: k + ' = "unterminated', _key),
    st.builds(lambda k: k + " = 'unterminated", _key),
    st.builds(lambda k: k + ' = """unterminated', _key),
    st.builds(lambda k: k + " = '''unterminated", _key),
    # stray tokens
    st.builds(lambda k: "=" + k, _key),
    st.builds(lambda k: k + " = = 1", _key),
    st.builds(lambda k: k + " = ", _key),
    st.builds(lambda k: "[]" + k, _key),
    st.builds(lambda k: k + " = 1 2 3", _key),
    # value on the next line
    st.builds(lambda k, v: k + " =\n" + v, _key, _value),
    # newline inside inline table
    st.builds(
        lambda k, v: "{a = 1,\n" + k + " = " + v + "}",
        _key,
        _value,
    ),
    # invalid escape
    st.builds(lambda k: k + ' = "\\q"', _key),
    # bare key with non-ASCII
    st.builds(lambda k: k + " = 1", st.just("\u00e9")),
    # duplicate key
    st.builds(
        lambda k, v1, v2: k + " = " + v1 + "\n" + k + " = " + v2,
        _key,
        _value,
        _value,
    ),
    # duplicate table
    st.builds(lambda k: "[" + k + "]\n[" + k + "]", _key),
    # table and array of tables with same name
    st.builds(lambda k: "[" + k + "]\n[[" + k + "]]", _key),
    # redefining table through dotted key
    st.builds(
        lambda k: "[" + k + "]\n" + k + ".sub = 1",
        _key,
    ),
)


# ---------------------------------------------------------------------------
# Deep nesting strategy (1500-2048 levels)
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_inline_table(depth):
    return "{a = " * depth + "1" + "}" * depth


_deep = st.one_of(
    st.integers(min_value=1500, max_value=2048).map(_deep_array),
    st.integers(min_value=1500, max_value=2048).map(_deep_inline_table),
    st.integers(min_value=1500, max_value=2048).map(
        lambda d: "x = " + _deep_array(d)
    ),
    st.integers(min_value=1500, max_value=2048).map(
        lambda d: "x = " + _deep_inline_table(d)
    ),
    st.integers(min_value=1, max_value=100).map(_deep_array),
    st.integers(min_value=1, max_value=100).map(_deep_inline_table),
)


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _malformed,
    _deep,
    # upweighted: inline tables with non-empty keyvals
    _inline_table_keyvals_non_empty,
    st.builds(lambda it: "a = " + it, _inline_table_keyvals_non_empty),
    # upweighted: multi-line literal strings
    st.builds(lambda s: "a = " + s, _ml_literal_string_upweighted),
    st.builds(lambda s: "a = " + s + "\n", _ml_literal_string_upweighted),
    # empty containers
    st.sampled_from(
        [
            "a = []",
            "a = {}",
            "[t]",
            "[[a]]",
            "a = [[]]",
            "a = [{}]",
            "a = {b = {}}",
            'a = ""',
            "a = ''",
            '"" = 1',
            "'' = 1",
            "a = 1 # comment",
            "a = 1 # comment\n",
            "a = 1\r\n",
            "\n",
            "\r\n",
            "# comment only",
            "# comment only\n",
            "a = 1",
            "a = 1\n",
            "a = true",
            "a = false",
            "a = true\nb = false",
        ]
    ),
)
```