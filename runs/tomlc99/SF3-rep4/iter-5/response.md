```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- keys ----------

_unquoted_key = st.from_regex(r"[A-Za-z0-9_-]{1,12}", fullmatch=True)

_basic_key_str = st.builds(
    lambda inner: '"' + inner + '"',
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs", "Cc"),
            blacklist_characters='"\\',
        ),
        max_size=10,
    ),
)

_literal_key_str = st.builds(
    lambda inner: "'" + inner + "'",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\n\r",
        ),
        max_size=10,
    ),
)

_simple_key = st.one_of(_unquoted_key, _basic_key_str, _literal_key_str)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------- scalar values ----------

def _esc_char():
    return st.one_of(
        st.sampled_from(['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]),
        st.from_regex(r"\\u[0-9A-Fa-f]{4}", fullmatch=True),
        st.from_regex(r"\\U[0-9A-Fa-f]{8}", fullmatch=True),
    )

_basic_string_inner = st.recursive(
    st.one_of(
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters='"\\\n\r',
            ),
            max_size=8,
        ),
        _esc_char(),
        st.sampled_from(["\x01", "\x02", "\x7f", "\t"]),
    ),
    lambda children: st.lists(children, max_size=4).map(_join),
)

_basic_string = _basic_string_inner.map(lambda s: '"' + s + '"')

_literal_string = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="'\n\r",
    ),
    max_size=12,
).map(lambda s: "'" + s + "'")

_ml_basic_inner = st.recursive(
    st.one_of(
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters='"\\',
            ),
            max_size=8,
        ),
        _esc_char(),
        st.sampled_from(["\n", "\r\n", "\t", "\x01"]),
    ),
    lambda children: st.lists(children, max_size=4).map(_join),
)

# avoid accidental closing of """ by ensuring no """ inside; simple approach:
_ml_basic_string = _ml_basic_inner.map(lambda s: '"""' + s.replace('"""', '"" ') + '"""')

_ml_literal_inner = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="'",
    ),
    max_size=12,
)
_ml_literal_string = _ml_literal_inner.map(
    lambda s: "'''" + s.replace("'''", "'' ") + "'''"
)

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# integers
_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.from_regex(r"[+-]?[0-9]{1,25}", fullmatch=True),
    st.sampled_from(["0", "-0", "+0", "007", "000123", "1_000", "1_2_3_4"]),
)

_hex_int = st.from_regex(r"0x[0-9A-Fa-f]{1,20}", fullmatch=True)
_oct_int = st.from_regex(r"0o[0-7]{1,20}", fullmatch=True)
_bin_int = st.from_regex(r"0b[01]{1,20}", fullmatch=True)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# floats
_float = st.one_of(
    st.from_regex(r"[+-]?[0-9]{1,20}\.[0-9]{0,20}([eE][+-]?[0-9]{1,5})?", fullmatch=True),
    st.from_regex(r"[+-]?\.[0-9]{1,20}([eE][+-]?[0-9]{1,5})?", fullmatch=True),
    st.from_regex(r"[+-]?[0-9]{1,20}[eE][+-]?[0-9]{1,5}", fullmatch=True),
    st.sampled_from(
        [
            "1.",
            ".5",
            "1e309",
            "-1e309",
            "1e-400",
            "3.141592653589793",
            "1_0.5",
            "+1.5",
            "-0.0",
        ]
    ),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_floating_point = st.one_of(_float, _inf_nan)

_boolean = st.sampled_from(["true", "false"])

# date-times
_date = st.from_regex(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", fullmatch=True)
_time = st.from_regex(r"[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?", fullmatch=True)
_offset = st.from_regex(r"(Z|[+-][0-9]{2}:[0-9]{2})", fullmatch=True)

_offset_date_time = st.builds(
    lambda d, sep, t, o: d + sep + t + o,
    _date,
    st.sampled_from(["T", "t", " "]),
    _time,
    _offset,
)
_local_date_time = st.builds(
    lambda d, sep, t: d + sep + t,
    _date,
    st.sampled_from(["T", "t", " "]),
    _time,
)
_local_date = _date
_local_time = _time

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    st.sampled_from(["1979-02-30", "1979-13-40", "0000-00-00T00:00:00Z"]),
)

# ---------- recursive values: arrays and inline tables ----------

_scalar = st.one_of(
    _string,
    _integer,
    _floating_point,
    _boolean,
    _date_time,
)

def _array_from(value):
    def build(elems):
        if not elems:
            return st.sampled_from(["[]", "[ ]", "[\n]", "[\n\n]"])
        body = ",".join(elems)
        return st.sampled_from(
            [
                "[" + body + "]",
                "[" + body + ",]",
                "[\n" + ",\n".join(elems) + "\n]",
                "[\n" + ",\n".join(elems) + ",\n]",
                "[ # comment\n" + ",\n".join(elems) + "\n]",
            ]
        )
    return value.flatmap(build)

def _inline_table_from(value):
    def build(pairs):
        if not pairs:
            return st.sampled_from(["{}", "{ }", "{,}"])
        body = ", ".join(pairs)
        return st.sampled_from(["{" + body + "}", "{" + body + ",}", "{ " + body + " }"])
    return value.flatmap(build)

_value = st.recursive(
    _scalar,
    lambda children: st.one_of(
        _array_from(children),
        _inline_table_from(
            st.lists(
                st.builds(
                    lambda k, v: k + " = " + v,
                    _key,
                    children,
                ),
                max_size=4,
            )
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ", ".join(vs) + "]"
        ),
    ),
    max_leaves=20,
)

# ---------- documents ----------

def _key_value_line():
    return st.builds(lambda k, v: k + " = " + v, _key, _value)

_comment = st.builds(
    lambda body: "#" + body,
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\n\r",
        ),
        max_size=20,
    ),
)

_standard_table = st.builds(lambda k: "[" + k + "]", _key)
_array_table = st.builds(lambda k: "[[" + k + "]]", _key)

def _expr():
    return st.one_of(
        _key_value_line(),
        _standard_table,
        _array_table,
        _comment,
        st.just(""),
    )

_document = st.lists(_expr(), max_size=8).map(lambda lines: "\n".join(lines))

# ---------- malformed variants ----------

_malformed = st.one_of(
    # unterminated basic string
    st.builds(lambda s: s + ' = "abc', _simple_key),
    # unterminated literal string
    st.builds(lambda s: s + " = 'abc", _simple_key),
    # missing closing bracket on table
    st.builds(lambda s: "[" + s, _simple_key),
    # doubled equals
    st.builds(lambda s: s + " == 1", _simple_key),
    # missing value
    st.builds(lambda s: s + " =", _simple_key),
    # stray token
    st.builds(lambda s: s + " = @", _simple_key),
    # invalid escape
    st.builds(lambda s: s + ' = "\\q"', _simple_key),
    # newline inside inline table
    st.builds(lambda s: s + " = {a = 1,\nb = 2}", _simple_key),
    # bare unicode key
    st.builds(lambda s: s + "é = 1", _simple_key),
    # array missing closing bracket
    st.builds(lambda s: s + " = [1, 2", _simple_key),
    # doubled closing bracket
    st.builds(lambda s: s + " = 1]", _simple_key),
)

# ---------- deep nesting ----------

def _deep_array(depth):
    return "[" * depth + "]" * depth

_deep = st.integers(min_value=1, max_value=2048).map(_deep_array)

# ---------- unicode escapes / utf8 conversion targeting ----------

def _utf8_payload():
    # Exercise toml_utf8_to_ucs: valid and invalid \u / \U escapes, surrogate and
    # out-of-range codepoints, and multi-byte raw UTF-8 characters inside strings.
    return st.one_of(
        st.builds(
            lambda k, body: k + ' = "' + body + '"',
            _simple_key,
            st.one_of(
                st.from_regex(r"\\u[0-9A-Fa-f]{4}", fullmatch=True),
                st.from_regex(r"\\U[0-9A-Fa-f]{8}", fullmatch=True),
                st.sampled_from(
                    [
                        "\\u0000",
                        "\\uD800",
                        "\\uDFFF",
                        "\\uFFFF",
                        "\\uFFFE",
                        "\\U0010FFFF",
                        "\\U00110000",
                        "\\UFFFFFFFF",
                        "\\uD83D\\uDE00",
                        "é",
                        "日本語",
                        "𝄞",
                        "\u00e9\u0301",
                        "a\\u00e9b",
                        "\\u00",
                        "\\U0000",
                        "\\U000",
                        "\\uZZZZ",
                        "\\u12",
                        "\\U1234567",
                        "\\uD800x",
                    ]
                ),
            ),
        ),
        st.builds(
            lambda k, body: k + " = '" + body + "'",
            _simple_key,
            st.sampled_from(["é", "日本語", "𝄞", "a\u0301", "\u00e9"]),
        ),
        # raw multi-byte utf8 in keys
        st.builds(
            lambda body: '"' + body + '" = 1',
            st.sampled_from(["é", "日本語", "𝄞", "a\u0301", "\U0001F600"]),
        ),
    )

# ---------- realtime offset / datetime edge cases (toml_rtots, toml_rtod_ex) ----------

def _datetime_edge():
    return st.one_of(
        st.builds(
            lambda d, sep, t, o: d + sep + t + o,
            st.from_regex(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", fullmatch=True),
            st.sampled_from(["T", "t", " "]),
            st.from_regex(r"[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?", fullmatch=True),
            st.sampled_from(
                [
                    "Z", "z",
                    "+00:00", "-00:00",
                    "+23:59", "-23:59",
                    "+24:00", "-24:00",
                    "+99:99", "-99:99",
                    "+01:60", "-01:60",
                    "+1:00", "-1:0",
                    "+0000", "-0000",
                    "+01", "-01",
                ]
            ),
        ),
        st.sampled_from(
            [
                "1979-05-27T00:32:00.999999999Z",
                "1979-05-27T00:32:00.999999999999Z",
                "1979-05-27T00:32:00.Z",
                "1979-05-27T00:32:00Z",
                "1979-05-27T00:32:00+24:00",
                "1979-05-27T00:32:00-00:00",
                "1979-05-27T00:32:00+00:60",
                "1979-05-27T24:00:00Z",
                "1979-05-27T23:59:60Z",
                "1979-05-27T23:59:60.5Z",
                "1979-05-27T00:32:00.123456789012Z",
                "1979-02-29T00:00:00Z",
                "1979-04-31T00:00:00Z",
                "1979-00-00T00:00:00Z",
                "0000-00-00T00:00:00Z",
                "9999-12-31T23:59:59.999999999+23:59",
                "1979-05-27",
                "00:32:00",
                "00:32:00.999999999999",
                "24:00:00",
                "23:59:60",
            ]
        ),
    )

_datetime_value = st.builds(
    lambda k, v: k + " = " + v,
    _simple_key,
    _datetime_edge(),
)

# ---------- integer / float parse edge cases (toml_rtod_ex) ----------

_float_edge = st.builds(
    lambda k, v: k + " = " + v,
    _simple_key,
    st.sampled_from(
        [
            "1e309",
            "-1e309",
            "1e-400",
            "-1e-400",
            "0.0e0",
            "1.0e+308",
            "1.0e-308",
            "1_0.5",
            "1.0_1",
            "1_0e1_0",
            "0.000000000000000000000000000001",
            "1.7976931348623157e308",
            "2.2250738585072014e-308",
            "4.9406564584124654e-324",
            "1e999999999",
            "1e-999999999",
            "0.1e999999999",
            "1.e1",
            "1.e",
            ".e1",
            "+.5",
            "-.5",
            "1.0e",
            "1.0e+",
            "1.0e-",
            "1.0E+10",
            "inf",
            "+inf",
            "-inf",
            "nan",
            "+nan",
            "-nan",
            "Infinity",
            "NaN",
        ]
    ),
)

# ---------- literal string normalization (norm_lit_str) ----------

_lit_str_value = st.builds(
    lambda k, v: k + " = " + v,
    _simple_key,
    st.one_of(
        st.builds(
            lambda inner: "'''" + inner + "'''",
            st.text(
                alphabet=st.characters(blacklist_categories=("Cs",)),
                max_size=20,
            ),
        ),
        st.builds(
            lambda inner: "'''\n" + inner + "'''",
            st.text(
                alphabet=st.characters(blacklist_categories=("Cs",)),
                max_size=20,
            ),
        ),
        st.builds(
            lambda inner: "'''\r\n" + inner + "'''",
            st.text(
                alphabet=st.characters(blacklist_categories=("Cs",)),
                max_size=20,
            ),
        ),
        st.builds(
            lambda inner: "'" + inner + "'",
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="'\n\r",
                ),
                max_size=20,
            ),
        ),
        # literal strings with backslashes must NOT process escapes
        st.builds(
            lambda inner: "'" + inner + "'",
            st.sampled_from(["\\n", "\\t", "\\\\", "\\u0041", "\\q", "a\\nb"]),
        ),
    ),
)

# ---------- file-level / document-level edge cases (toml_parse_file) ----------

_file_edge = st.one_of(
    st.just(""),
    st.just("\n"),
    st.just("\r\n"),
    st.just("\r"),
    st.just("\xef\xbb\xbfa = 1"),
    st.just("\xef\xbb\xbf"),
    st.just("\xef\xbb\xbf[a]\nb = 1"),
    st.just("\x00"),
    st.just("a = 1\x00"),
    st.just("a = 1\n\x00"),
    st.just("# comment without newline"),
    st.just("a = 1 # trailing comment"),
    st.just("a = 1\n\n\n\nb = 2"),
    st.just("a = 1\r\n\r\nb = 2"),
    st.just("[a]\n[b]\n[a]"),
    st.just("[[a]]\n[a]"),
    st.just("a = 1\na = 2"),
    st.just("[a]\nb = 1\n[a]\nc = 2"),
    st.just("a.b.c = 1"),
    st.just("[a.b.c]\nd = 1"),
    st.just("a = { b = { c = { d = 1 } } }"),
    st.just("a = [[[[1]]]]"),
    st.just("a = [" + ",".join(["1"] * 100) + "]"),
    st.just("a = 1\n" * 100),
    st.just("[t]\n" * 50),
    st.just("a = \t 1"),
    st.just("a\t=\t1"),
    st.just("a=1"),
)

# ---------- deep nesting ----------

def _deep_array(depth):
    return "[" * depth + "]" * depth

_deep = st.integers(min_value=1, max_value=2048).map(_deep_array)

# ---------- final strategy ----------

strategy = st.one_of(
    _document,
    _malformed,
    _deep,
    _utf8_payload(),
    _datetime_value,
    _float_edge,
    _lit_str_value,
    _file_edge,
    st.just(""),
    st.just("\n"),
    st.just("# just a comment"),
    st.just("[t]\n"),
    st.just("[[a]]\n[[a]]\n"),
    st.just('"" = 1'),
    st.just("a = 1\r\nb = 2"),
    st.just("a = 1"),
)
```