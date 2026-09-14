from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Low level character / token helpers
# ---------------------------------------------------------------------------

# Characters allowed in bare keys (ASCII only per parser realities).
_BARE_KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

def _bare_key():
    return st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=12)

# Non-ASCII / control text for strings; never a raw NUL.
_STRING_BODY_CHARS = st.characters(
    blacklist_characters="\x00",
    blacklist_categories=("Cs",),  # surrogates
)

# ---------------------------------------------------------------------------
# Strings: all four quoting forms
# ---------------------------------------------------------------------------

_ESCAPES = st.sampled_from(
    ['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]
)

def _unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).filter(
        lambda cp: not (0xD800 <= cp <= 0xDFFF)
    ).map(lambda cp: "\\u%04X" % cp if cp <= 0xFFFF else "\\U%08X" % cp)

# A basic string body piece: raw char, escape, or unicode escape.
_basic_piece = st.one_of(
    _STRING_BODY_CHARS.filter(lambda c: c not in '"\\\n'),
    _ESCAPES,
    _unicode_escape(),
)

def _basic_string():
    return st.lists(_basic_piece, max_size=8).map(
        lambda parts: '"' + "".join(parts) + '"'
    )

def _literal_string():
    return st.lists(
        _STRING_BODY_CHARS.filter(lambda c: c not in "'\n"), max_size=8
    ).map(lambda parts: "'" + "".join(parts) + "'")

def _ml_basic_string():
    inner = st.one_of(
        _STRING_BODY_CHARS.filter(lambda c: c != '\\'),
        _ESCAPES,
        _unicode_escape(),
        st.just("\n"),
        st.just("\r\n"),
    )
    return st.lists(inner, max_size=10).map(
        lambda parts: '"""' + "".join(parts) + '"""'
    )

def _ml_literal_string():
    inner = st.one_of(
        _STRING_BODY_CHARS.filter(lambda c: c != "'"),
        st.just("\n"),
    )
    return st.lists(inner, max_size=10).map(
        lambda parts: "'''" + "".join(parts) + "'''"
    )

def _string_value():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    )

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _dec_int():
    return st.one_of(
        st.integers(min_value=-10**30, max_value=10**30).map(str),
        st.sampled_from(["0", "007", "-007", "+0", "1_000", "10_000_000"]),
    )

def _hex_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2**64).map(lambda n: "0x%x" % n),
        st.sampled_from(["0xDEAD_BEEF", "0x0", "0xFF_FF"]),
    )

def _oct_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2**32).map(lambda n: "0o%o" % n),
        st.sampled_from(["0o755", "0o0", "0o1_7"]),
    )

def _bin_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2**32).map(lambda n: "0b" + bin(n)[2:]),
        st.sampled_from(["0b0", "0b1010", "0b1_0_1"]),
    )

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    return st.one_of(
        st.floats(allow_nan=False, allow_infinity=False).map(repr),
        st.sampled_from([
            "1.", ".5", "1e309", "-1e309", "1E+10", "6.626e-34",
            "1_000.000_1", "3.14159", "0.0", "-0.0", "inf", "+inf",
            "-inf", "nan", "+nan", "-nan",
        ]),
    )

# ---------------------------------------------------------------------------
# Booleans and date-times
# ---------------------------------------------------------------------------

def _boolean():
    return st.sampled_from(["true", "false"])

def _date_time():
    return st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00.999999+00:00",
        "1979-05-27 07:32:00Z",
        "1979-05-27T07:32:00",
        "1979-05-27",
        "07:32:00",
        "07:32:00.999",
        "1979-02-30",          # calendar-invalid, accepted by parser
        "0000-00-00",
        "9999-99-99T99:99:99Z",
    ])

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_bare_key(), _quoted_key())

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(
        lambda ks: ".".join(ks)
    )

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# Depth band: concentrate interesting depth in the 1500-2048 range.
_depth_choices = st.one_of(
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=1500, max_value=2048),
)

def _scalar_value():
    return st.one_of(
        _string_value(),
        _integer(),
        _float(),
        _boolean(),
        _date_time(),
    )

def _array_of(value_st):
    def build(vs):
        inner = st.one_of(
            st.just(""),
            st.lists(vs, min_size=1, max_size=4).map(lambda xs: ", ".join(xs)),
            st.lists(vs, min_size=1, max_size=4).map(
                lambda xs: ", ".join(xs) + ","
            ),
            st.lists(vs, min_size=1, max_size=3).map(
                lambda xs: "\n  " + ",\n  ".join(xs) + ",\n"
            ),
            st.just("# comment\n"),
        )
        return inner.map(lambda s: "[" + s + "]")
    return build

def _inline_table_of(value_st):
    def build(vs):
        def entry(v):
            return st.tuples(_key(), st.just(v)).map(lambda kv: kv[0] + " = " + kv[1])
        inner = st.one_of(
            st.just(""),
            st.lists(vs, min_size=1, max_size=3).map(
                lambda xs: ", ".join(xs)
            ),
            st.lists(vs, min_size=1, max_size=3).map(
                lambda xs: ", ".join(xs) + ","
            ),
        )
        return inner.map(lambda s: "{" + s + "}")
    return build

# Recursive value strategy.
_value = st.recursive(
    _scalar_value(),
    lambda children: st.one_of(
        _array_of(children),
        _inline_table_of(children),
    ),
    max_leaves=8,
)

# ---------------------------------------------------------------------------
# Key/value pairs, tables, documents
# ---------------------------------------------------------------------------

def _key_value():
    return st.tuples(_key(), _value()).map(lambda kv: kv[0] + " = " + kv[1])

def _comment():
    return st.lists(
        _STRING_BODY_CHARS.filter(lambda c: c != "\n"), max_size=20
    ).map(lambda cs: "#" + "".join(cs))

def _standard_table():
    return _key().map(lambda k: "[" + k + "]")

def _array_table():
    return _key().map(lambda k: "[[" + k + "]]")

def _line():
    return st.one_of(
        _key_value(),
        _standard_table(),
        _array_table(),
        _comment(),
    )

def _malformed_snippets():
    return st.sampled_from([
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = [1, 2",
        "a = {b = 1",
        "a = 1 2",
        "a = = 1",
        "[table",
        "[[table]",
        "a = ",
        "= 1",
        "a = \\q",
        "a = [1,,2]",
        "a = {b = 1,, c = 2}",
        "a = 1\nb = 2\nb = 3",
        "a = 1\na = 2",
        "[t]\n[t]",
        "a = {b = 1,\n c = 2}",
        "a = 1\n[",
    ])

def _document():
    def build(lines):
        body = "\n".join(lines)
        return body

    lines = st.one_of(
        st.lists(_line(), min_size=0, max_size=8),
        st.lists(_line(), min_size=1, max_size=4).map(
            lambda ls: ls + [_malformed_snippets()]
        ),
    )
    return lines.map(build)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document(),
    _malformed_snippets(),
)