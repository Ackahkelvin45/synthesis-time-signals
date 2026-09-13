```python
from hypothesis import strategies as st
import json

# ---------------- helpers ----------------

_SAFE_CTRL = "\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"

_plain_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\"'\\\n\r{}[]=#,",
)

_plain_text = st.text(_plain_chars, max_size=8)

_key_chars = st.sampled_from("abcXYZ_0123456789-")
_unquoted_key = st.text(_key_chars, min_size=1, max_size=10)

_basic_esc = st.sampled_from(["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/", "\\u0041", "\\U0001F600"])

_basic_string = st.one_of(
    st.builds(lambda a, b: '"' + a + b + '"', _plain_text, _plain_text),
    st.text(st.one_of(_plain_chars, _basic_esc), max_size=10).map(lambda s: '"' + s + '"'),
    st.just('""'),
    st.just('"\\u0000"'),
    st.just('"x' + _SAFE_CTRL[0] + 'y"'),
    st.just('"tab\there"'),
)

_literal_string = st.one_of(
    st.just("''"),
    st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="'\x00"), max_size=10).map(lambda s: "'" + s + "'"),
    st.just("'raw \\n not escape'"),
)

_ml_basic_string = st.one_of(
    st.just('""""""'),
    st.text(st.one_of(_plain_chars, st.sampled_from(["\n", "\\n", "\\t", "\\\"", "\\\\"])), max_size=12).map(lambda s: '"""' + s + '"""'),
)

_ml_literal_string = st.one_of(
    st.just("''''''"),
    st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"), max_size=12).map(lambda s: "'''" + s + "'''"),
)

_string_value = st.one_of(_basic_string, _literal_string, _ml_basic_string, _ml_literal_string)

# ---------------- numbers ----------------

_dec_int = st.one_of(
    st.integers(min_value=-10**20, max_value=10**20).map(str),
    st.sampled_from(["0", "007", "+0", "-0", "1_000", "9223372036854775807", "-9223372036854775808", "99999999999999999999999999"]),
)

_hex_int = st.one_of(
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF", "0xabcdef"]),
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x")),
)

_oct_int = st.one_of(
    st.sampled_from(["0o0", "0o777", "0o7_7_7", "0o01234567"]),
    st.integers(min_value=0, max_value=2**32).map(lambda n: "0o" + format(n, "o")),
)

_bin_int = st.one_of(
    st.sampled_from(["0b0", "0b1", "0b1010_1010", "0b11111111"]),
    st.integers(min_value=0, max_value=2**32).map(lambda n: "0b" + format(n, "b")),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.sampled_from(["1.0", "-0.0", "+1.5", "1e10", "1E-10", "6.626e-34", "1e309", "-1e309", "1.", ".5", "1_000.000_1"]),
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.integers(min_value=-10**6, max_value=10**6).map(lambda n: "%d.%d" % (n, abs(n) % 1000)),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_floating_point = st.one_of(_float, _inf_nan)

_boolean = st.sampled_from(["true", "false"])

# ---------------- dates ----------------

_date = st.sampled_from(["1979-05-27", "0000-00-00", "1979-02-30", "9999-12-31", "2024-13-45"])
_time = st.sampled_from(["07:32:00", "00:00:00", "23:59:60", "07:32:00.999999", "12:00:00.1"])
_offset = st.sampled_from(["Z", "z", "+07:00", "-07:00", "+00:00", "-23:59"])
_date_time = st.one_of(
    _date,
    _time,
    st.tuples(_date, st.sampled_from(["T", "t", " "]), _time).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_date, st.sampled_from(["T", "t", " "]), _time, _offset).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

# ---------------- keys ----------------

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------------- recursive values ----------------

def _join_inline(items):
    return "{" + ", ".join(items) + "}"

def _join_array(items):
    return "[" + ", ".join(items) + "]"


def _make_value_strategy():
    scalar = st.one_of(
        _string_value,
        _integer,
        _floating_point,
        _boolean,
        _date_time,
    )

    def array_from(value_st):
        return st.lists(value_st, max_size=4).map(_join_array)

    def inline_from(value_st):
        def build(pairs):
            return "{" + ", ".join(pairs) + "}"
        pair = st.tuples(_unquoted_key, value_st).map(lambda t: t[0] + " = " + t[1])
        return st.lists(pair, max_size=4).map(build)

    return st.recursive(
        scalar,
        lambda children: st.one_of(array_from(children), inline_from(children)),
        max_leaves=12,
    )


_value = _make_value_strategy()

# deep nesting: arrays nested up to ~1800 levels, in the interesting band
_deep_array = st.integers(min_value=1, max_value=1800).map(lambda n: "[" * n + "]" * n)
_deep_inline = st.integers(min_value=1, max_value=1800).map(lambda n: "{a = " * n + "1" + "}" * n)

_value_with_depth = st.one_of(_value, _deep_array, _deep_inline)

# ---------------- documents ----------------

_comment = st.one_of(
    st.just("#"),
    st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00\n\r"), max_size=20).map(lambda s: "# " + s),
)

_key_value = st.tuples(_key, _value_with_depth).map(lambda t: t[0] + " = " + t[1])

_std_table = _key.map(lambda k: "[" + k + "]")
_array_table = _key.map(lambda k: "[[" + k + "]]")

_line = st.one_of(_key_value, _std_table, _array_table, _comment, st.just(""))

_document = st.lists(_line, max_size=8).map(lambda lines: "\n".join(lines))

# ---------------- malformed / near-valid ----------------

_malformed = st.sampled_from([
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    "a = [1, 2",
    "a = [1, 2]]",
    "a = {b = 1",
    "a = {b = 1}}",
    "a = {b = 1,}",
    "[t",
    "[[t]",
    "[[t]]]",
    "a = ",
    "= 1",
    "a = 1 b = 2",
    "a = 1\nextra",
    "a = 1\n\n\nb = 2",
    "a = 1\n# comment",
    "a = 1\r\nb = 2\r\n",
    "a = 1\nb = 2",
    "a = 1\na = 2",
    "[t]\n[t]",
    "[[t]]\n[t]",
    "a = 1\n[t]\na = 2",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[[t]]\n[[t]]",
    "a = 1\n",
    "a = 1",
    "",
    "# only comment",
    "\n\n\n",
    "a = 1\n[t]\nb = 2",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
    "a = 1\n[t]\n[t]\n",
   