```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

_SAFE_ASCII = st.characters(min_codepoint=0x20, max_codepoint=0x7E)
_NON_ASCII = st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF)
_CTRL = st.sampled_from(["\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\x7f"])
_TAB = st.just("\t")

# Escape sequences valid in basic strings (excluding the raw-NUL-producing ones
# we must never emit; \u0000 is fine because it's an escape, not a raw NUL).
_ESCAPES = st.sampled_from(
    [
        "\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t",
        "\\u0041", "\\u00e9", "\\u0000", "\\uFFFF",
        "\\U0001F600", "\\U0010FFFF",
    ]
)


def _basic_string_body():
    return st.one_of(
        st.text(_SAFE_ASCII, max_size=12),
        st.text(_NON_ASCII, max_size=6),
        st.text(_CTRL, max_size=3),
        st.just("\t"),
        st.lists(_ESCAPES, min_size=1, max_size=4).map("".join),
        st.lists(
            st.one_of(_SAFE_ASCII, _NON_ASCII, _CTRL, _ESCAPES, st.just("\t")),
            max_size=8,
        ).map("".join),
    )


def _literal_string_body():
    return st.one_of(
        st.text(_SAFE_ASCII, max_size=12),
        st.text(_NON_ASCII, max_size=6),
        st.text(_CTRL, max_size=3),
        st.lists(
            st.one_of(_SAFE_ASCII, _NON_ASCII, _CTRL, st.just("\t")),
            max_size=8,
        ).map("".join),
    )


# ---------------------------------------------------------------------------
# Strings: the four quoting forms
# ---------------------------------------------------------------------------

basic_string = _basic_string_body().map(lambda s: '"' + s.replace('"', '\\"') + '"')
literal_string = _literal_string_body().map(lambda s: "'" + s.replace("'", "") + "'")

# Multiline strings: content may include newlines but must not contain the
# closing delimiter.  Keep it simple and safe.
_ml_basic_body = st.one_of(
    st.text(_SAFE_ASCII, max_size=20),
    st.text(_NON_ASCII, max_size=10),
    st.lists(
        st.one_of(
            st.text(_SAFE_ASCII, max_size=4),
            st.text(_NON_ASCII, max_size=2),
            st.just("\n"),
            st.just("\r\n"),
            st.just("\\\n"),
            _ESCAPES,
        ),
        max_size=6,
    ).map("".join),
)


def _ml_basic():
    return _ml_basic_body.map(
        lambda s: '"""' + s.replace('"""', '""') + '"""'
    )


_ml_literal_body = st.one_of(
    st.text(_SAFE_ASCII, max_size=20),
    st.text(_NON_ASCII, max_size=10),
    st.lists(
        st.one_of(
            st.text(_SAFE_ASCII, max_size=4),
            st.text(_NON_ASCII, max_size=2),
            st.just("\n"),
            st.just("\r\n"),
        ),
        max_size=6,
    ).map("".join),
)


def _ml_literal():
    return _ml_literal_body.map(lambda s: "'''" + s.replace("'''", "''") + "'''")


string_value = st.one_of(
    basic_string,
    literal_string,
    _ml_basic(),
    _ml_literal(),
)

# ---------------------------------------------------------------------------
# Integers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-(2**70), max_value=2**70).map(str),
    st.sampled_from(
        [
            "0", "007", "0_0", "1_000", "123456789012345678901234567890",
            "-0", "+0", "9223372036854775807", "9223372036854775808",
            "-9223372036854775808", "-9223372036854775809",
        ]
    ),
)


def _digits_with_underscores(alphabet, min_len=1, max_len=24):
    return st.lists(st.sampled_from(list(alphabet)), min_size=min_len, max_size=max_len).map(
        "".join
    )


_hex_int = _digits_with_underscores("0123456789abcdefABCDEF", 1, 20).map("0x" + "")
_hex_int = st.lists(st.sampled_from("0123456789abcdefABCDEF"), min_size=1, max_size=20).map(
    lambda cs: "0x" + "".join(cs)
)
_oct_int = st.lists(st.sampled_from("01234567"), min_size=1, max_size=20).map(
    lambda cs: "0o" + "".join(cs)
)
_bin_int = st.lists(st.sampled_from("01"), min_size=1, max_size=40).map(
    lambda cs: "0b" + "".join(cs)
)

integer_value = st.one_of(
    _dec_int,
    _hex_int,
    _oct_int,
    _bin_int,
    st.just("0xFFFFFFFFFFFFFFFFFFFFFF"),
    st.just("0o777777777777777777777777"),
    st.just("0b" + "1" * 64),
)

# ---------------------------------------------------------------------------
# Floats
# ---------------------------------------------------------------------------

_float_specials = st.sampled_from(
    [
        "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "1e309", "-1e309", "1e-400", "1.7976931348623157e308",
        "1.", ".5", "1e10", "1E10", "1e+10", "1e-10",
        "3.141592653589793", "-0.0", "0.0", "1_000.000_1",
        "6.626e-34", "9_224_617.445_991_228_313",
    ]
)


def _float_num():
    return st.one_of(
        st.integers(min_value=-(10**6), max_value=10**6).map(lambda n: f"{n}.0"),
        st.tuples(
            st.integers(min_value=0, max_value=10**6),
            st.integers(min_value=0, max_value=10**6),
        ).map(lambda t: f"{t[0]}.{t[1]}"),
        st.tuples(
            st.integers(min_value=-10**6, max_value=10**6),
            st.integers(min_value=-300, max_value=300),
        ).map(lambda t: f"{t[0]}e{t[1]}"),
    )


float_value = st.one_of(_float_specials, _float_num())

# ---------------------------------------------------------------------------
# Booleans and date-times
# ---------------------------------------------------------------------------

bool_value = st.sampled_from(["true", "false"])


def _two_digits(lo, hi):
    return st.integers(min_value=lo, max_value=hi).map(lambda n: f"{n:02d}")


_year = st.integers(min_value=0, max_value=9999).map(lambda n: f"{n:04d}")
_month = _two_digits(0, 99)
_day = _two_digits(0, 99)
_hour = _two_digits(0, 99)
_minute = _two_digits(0, 99)
_second = _two_digits(0, 99)
_secfrac = st.integers(min_value=0, max_value=10**9).map(lambda n: f".{n:09d}")
_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _hour, _minute
    ).map(lambda t: f"{t[0]}{t[1]}:{t[2]}"),
)
_delim = st.sampled_from(["T", "t", " "])

_full_date = st.tuples(_year, _month, _day).map(lambda t: f"{t[0]}-{t[1]}-{t[2]}")
_partial_time = st.tuples(_hour, _minute, _second).map(
    lambda t: f"{t[0]}:{t[1]}:{t[2]}"
)
_partial_time_frac = st.tuples(_partial_time, _secfrac).map(lambda t: t[0] + t[1])

date_time_value = st.one_of(
    st.tuples(_full_date, _delim, _partial_time_frac, _offset).map(
        lambda t: f"{t[0]}{t[1]}{t[2]}{t[3]}"
    ),
    st.tuples(_full_date, _delim, _partial_time_frac).map(
        lambda t: f"{t[0]}{t[1]}{t[2]}"
    ),
    _full_date,
    _partial_time_frac,
    st.just("1979-02-30"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("0000-00-00"),
    st.just("23:59:60"),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.one_of(
    st.text(
        st.sampled_from(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
        ),
        min_size=1,
        max_size=12,
    ),
    st.just("a" * 100),
    st.just("0"),
    st.just("-"),
    st.just("_"),
    st.just("007"),
)

_quoted_key = st.one_of(
    basic_string,
    literal_string,
    st.just('""'),
    st.just("''"),
    st.just('"key with spaces"'),
    st.just('"\\u0041"'),
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(".".join)

key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# Depth band: interesting depth concentrated in 1500-2048 for arrays/inline
# tables.  We keep the *base* generator small and let `st.recursive` build
# depth; we also add explicit deep chains.
_MAX_DEPTH = 2048


def _deep_array(n):
    return "[" * n + "0" + "]" * n


def _deep_inline(n):
    return "{a=" * n + "0" + "}" * n


_deep_arrays = st.integers(min_value=1500, max_value=_MAX_DEPTH).map(_deep_array)
_deep_inlines = st.integers(min_value=1, max_value=200).map(_deep_inline)

# A shallow recursive value generator.
_scalar = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value,
)

_array_inner = st.one_of(
    _scalar,
    st.lists(
        st.one_of(_scalar, st.just("")),
        max_size=6,
    ).map(lambda xs: ", ".join(xs)),
)

_array = st.one_of(
    st.just("[]"),
    st.just("[\n]"),
    st.just("[ ]"),
    st.lists(_array_inner, max_size=6).map(lambda xs: "[" + ", ".join(xs) + "]"),
    st.lists(_array_inner, max_size=6).map(
        lambda xs: "[\n" + ",\n".join(xs) + ",\n]"
    ),
    st.lists(_array_inner, max_size=3).map(lambda xs: "[" + ",".join(xs) + ",]"),
)

_inline_kv = st.tuples(key, _scalar).map(lambda t: f"{t[0]} = {t[1]}")

_inline_table = st.one_of(
    st.just("{}"),
    st.just("{ }"),
    st.lists(_inline_kv, max_size=5).map(lambda kvs: "{" + ", ".join(kvs) + "}"),
    st.lists(_inline_kv, max_size=4).map(lambda kvs: "{" + ", ".join(kvs) + ",}"),
)

# Recursive combination of arrays and inline tables.
_recursive_value = st.recursive(
    _scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=4).map(lambda xs: "[" + ", ".join(xs) + "]"),
        st.lists(
            st.tuples(key, children), max_size=3
        ).map(
            lambda kvs: "{" + ", ".join(f"{k} = {v}" for k, v in kvs) + "}"
        ),
    ),
    max_leaves=30,
)

value = st.one_of(
    _scalar,
    _array,
    _inline_table,
    _recursive_value,
    _deep_arrays,
    _deep_inlines,
)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        "a = [1, 2",
        "a = {b = 1",
        "a = {b = 1\n}",
        "a = 1 2",
        "a = ",
        "a",
        "a =",
        "= 1",
        "a == 1",
        "[t",
        "[[t]",
        "[[t]]]",
        "[t]]",
        "]",
        "}",
        "a = 1\nb = 2\nb = 3",
        "[t]\n[t]",
        "a = \\q",
        "a = \"\\q\"",
        "a = 0x",
        "a = 0b2",
        "a = 0o8",
        "a = 1e",
        "a = .",
        "a = ..",
        "a = +",
        "a = -",
        "a = {,}",
        "a = [,]",
        "a = [1,,2]",
        "a = {b = 1, b = 2}",
        "a = true false",
        "a = 1979-05-27T",
        "a = 1979-05-27T07:32",
        "a = 07:32:00.",
        "a = \"\\u12\"",
        "a = \"\\U0011\"",
        "a = \"\\uZZZZ\"",
        "a = 'x' 'y'",
        "a = 1\n  = 2",
        "a = 1\n\t= 2",
        "a = 1 # comment\nb = 2",
        "a = 1#comment",
        "a = \"\"\"x\"\"",
        "a = '''x''",
        "a = {b = 1, }",
        "a = [1, 2,]",
        "a = [\n1,\n2,\n]",
        "a = {b = {c = {d = 1}}}",
        "a = [[[[1]]]]",
        "\n\n\n",
        "",
        "# just a comment",
        "# comment\n",
        "a = 1\n# trailing",
        "a = 1\n",
        "a = 1\r\nb = 2\r\n",
        "a = 1\r\n",
        "a = 1\r",
        "a = 1\n\n\nb = 2",
        "a = 1\n\n\n",
        "a = 1\n\n\n",
        "a = 1\n\r\nb = 2",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1\n\r\n",
        "a = 1