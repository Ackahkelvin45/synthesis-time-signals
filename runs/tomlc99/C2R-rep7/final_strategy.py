import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Low-level lexical fragments
# ---------------------------------------------------------------------------

# NUL is never emitted raw.  We use \u0000 escapes inside strings instead.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

# Characters allowed raw inside a basic string (no quote, no backslash, no NL).
_basic_raw = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\n\r\x00'),
    st.sampled_from([" ", "\t", "\x01", "\x02", "\x07", "\x1b", "\x7f"]),
)

_basic_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]
)

_unicode_escapes = st.one_of(
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04X" % n),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08X" % n),
)

_escape = st.one_of(_basic_escapes, _unicode_escapes)


def _basic_string_body():
    return st.lists(st.one_of(_basic_raw, _escape), max_size=12).map("".join)


_basic_string = _basic_string_body().map(lambda b: '"' + b + '"')

# Literal strings: raw only, no quote, no newline.
_lit_raw = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters="'\n\r\x00"),
    st.sampled_from([" ", "\t", "\x01", "\x7f"]),
)
_literal_string = (
    st.lists(_lit_raw, max_size=12).map("".join).map(lambda b: "'" + b + "'")
)

# Multiline basic: allow newlines, escapes, control chars.
_ml_basic_raw = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters="\\\x00"),
    st.sampled_from(["\r\n", "\x01", "\t"]),
)
_ml_basic = (
    st.lists(st.one_of(_ml_basic_raw, _escape), max_size=14)
    .map("".join)
    .map(lambda b: '"""' + b + '"""')
)

# Multiline literal: anything except the terminator; keep it simple.
_ml_lit_raw = st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00")
_ml_literal = (
    st.lists(_ml_lit_raw, max_size=14)
    .map("".join)
    .map(lambda b: "'''" + b + "'''")
)

_string = st.one_of(_basic_string, _literal_string, _ml_basic, _ml_literal)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-10**20, max_value=10**20).map(str),
    st.sampled_from(
        ["0", "007", "-007", "+0", "1_000", "1_2_3", "9223372036854775808",
         "-9223372036854775809", "18446744073709551616"]
    ),
    st.integers(min_value=0, max_value=10**6).map(
        lambda n: "+" + str(n)
    ),
)

_hex_int = st.integers(min_value=0, max_value=0xFFFFFFFF).map(
    lambda n: "0x%X" % n
)
_oct_int = st.integers(min_value=0, max_value=0o77777777).map(
    lambda n: "0o%o" % n
)
_bin_int = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "0b" + format(n, "b")
)
_int_underscore = st.sampled_from(
    ["0x1_2", "0o1_2", "0b1_0", "1_0_0"]
)

_integer = st.one_of(
    _dec_int, _hex_int, _oct_int, _bin_int, _int_underscore
)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(
        ["1.", ".5", "1e309", "-1e309", "1e-400", "6.626e-34", "1_0.0_1",
         "0.0", "-0.0", "+1.5", "3.14", "1e10", "1E+10", "0e0"]
    ),
    st.floats(allow_nan=True, allow_infinity=True).map(repr),
)

_special_float = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

_floating_point = st.one_of(_float, _special_float)

# ---------------------------------------------------------------------------
# Dates / times
# ---------------------------------------------------------------------------

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.sampled_from(["01", "02", "12", "13", "00", "99"])
_day = st.sampled_from(["01", "28", "30", "31", "00", "99"])
_hms = st.tuples(
    st.integers(0, 99).map(lambda n: "%02d" % n),
    st.integers(0, 99).map(lambda n: "%02d" % n),
    st.integers(0, 99).map(lambda n: "%02d" % n),
).map(lambda t: t[0] + ":" + t[1] + ":" + t[2])
_secfrac = st.integers(0, 999999).map(lambda n: ".%d" % n)
_date = st.tuples(_year, _month, _day).map(lambda t: t[0] + "-" + t[1] + "-" + t[2])
_partial_time = st.tuples(_hms, st.one_of(st.none(), _secfrac)).map(
    lambda t: t[0] if t[1] is None else t[0] + t[1]
)
_delim = st.sampled_from(["T", "t", " "])
_offset = st.one_of(
    st.just("Z"),
    st.tuples(
        st.sampled_from(["+", "-"]),
        st.integers(0, 99).map(lambda n: "%02d" % n),
        st.integers(0, 99).map(lambda n: "%02d" % n),
    ).map(lambda t: t[0] + t[1] + ":" + t[2]),
)

_offset_date_time = st.tuples(_date, _delim, _partial_time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)
_local_date_time = st.tuples(_date, _delim, _partial_time).map(
    lambda t: t[0] + t[1] + t[2]
)
_local_date = _date
_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time, _local_date_time, _local_date, _local_time
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=10,
)

_quoted_key = st.one_of(
    _basic_string,
    _literal_string,
    st.just('""'),
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(".".join)

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Values (recursive)
# ---------------------------------------------------------------------------

_bool = st.sampled_from(["true", "false"])

_scalar = st.one_of(
    _string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
)

# Inline table: key = value pairs, optional trailing comma (parser accepts).
def _inline_table(key_strategy, value_strategy):
    pair = st.tuples(key_strategy, st.just(" = "), value_strategy).map(
        lambda t: t[0] + t[1] + t[2]
    )
    body = st.lists(pair, max_size=3).map(", ".join)
    trailing = st.booleans()
    return st.tuples(body, trailing).map(
        lambda t: "{" + t[0] + ("," if t[1] and t[0] else "") + "}"
    )


def _array(value_strategy):
    inner = st.lists(value_strategy, max_size=4).map(", ".join)
    trailing = st.booleans()
    return st.tuples(inner, trailing).map(
        lambda t: "[" + t[0] + ("," if t[1] and t[0] else "") + "]"
    )


def _value_impl():
    return st.recursive(
        _scalar,
        lambda children: st.one_of(
            _array(children),
            _inline_table(_key, children),
        ),
        max_leaves=12,
    )


_value = _value_impl()

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

_key_value = st.tuples(_key, st.just(" = "), _value).map(
    lambda t: t[0] + t[1] + t[2]
)

_comment = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",), blacklist_characters="\n\r\x00"
        ),
        max_size=20,
    ).map(lambda s: "#" + s),
)

_standard_table = _key.map(lambda k: "[" + k + "]")
_array_table = _key.map(lambda k: "[[" + k + "]]")

_line = st.one_of(_key_value, _standard_table, _array_table, _comment)
_nl = st.sampled_from(["\n", "\r\n"])

_document = st.lists(_line, max_size=6).map("\n".join)

# ---------------------------------------------------------------------------
# Edge cases / near-valid-but-malformed inputs
# ---------------------------------------------------------------------------

_deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "a = " + "[" * n + "]" * n
)

_deep_inline = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "a = " + "{ b = " * n + "1" + " }" * n
)

_duplicate_keys = st.just("a = 1\na = 2\n")
_duplicate_tables = st.just("[t]\n[t]\n")
_table_array_conflict = st.just("[t]\n[[t]]\n")
_nl_in_inline = st.just("a = {b = 1\n}\n")
_unterminated_string = st.just('a = "unterminated\n')
_bad_escape = st.just('a = "\\q"\n')
_missing_delim = st.just("a = [1, 2\n")
_double_delim = st.just("a = [[1, 2]]\n")
_stray_token = st.just("a = @\n")
_unicode_bare_key = st.just("caf\u00e9 = 1\n")
_value_next_line = st.just("a =\n1\n")

_edge = st.one_of(
    _deep_array,
    _deep_inline,
    _duplicate_keys,
    _duplicate_tables,
    _table_array_conflict,
    _nl_in_inline,
    _unterminated_string,
    _bad_escape,
    _missing_delim,
    _double_delim,
    _stray_token,
    _unicode_bare_key,
    _value_next_line,
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _edge,
    st.just(""),
    st.just("\n"),
    st.just("# just a comment"),
    st.just("# comment no trailing newline"),
    st.just("a = 1"),
)