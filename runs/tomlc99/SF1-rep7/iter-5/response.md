```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------- helpers

def _join(parts):
    return "".join(parts)


def _join_tuple(t):
    return "".join(t)


# ---------------------------------------------------------------- scalars

_ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_digits = "0123456789"
_bare_chars = _ascii_letters + _digits + "-_"

unquoted_key = st.text(alphabet=_bare_chars, min_size=1, max_size=12)

# strings: escapes and non-ascii and control bytes (no NUL raw)
_esc_simple = st.sampled_from(["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"])


def _u_escape():
    return st.integers(min_value=0, max_value=0xFFFF).map(
        lambda n: "\\u%04X" % n
    )


def _U_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08X" % n
    )


_esc = st.one_of(_esc_simple, _u_escape(), _U_escape())

# basic string body char: printable non-quote non-backslash, plus escapes,
# plus raw control chars (allowed by parser), plus non-ascii
_basic_body_char = st.one_of(
    st.characters(
        blacklist_characters='"\\\n',
        blacklist_categories=("Cs",),
    ),
    _esc,
)

basic_string = st.builds(
    lambda body: '"' + body + '"',
    st.lists(_basic_body_char, max_size=10).map(_join),
)

_literal_body_char = st.characters(
    blacklist_characters="'\n",
    blacklist_categories=("Cs",),
)

literal_string = st.builds(
    lambda body: "'" + body + "'",
    st.lists(_literal_body_char, max_size=10).map(_join),
)

# multiline basic: allow newlines, escapes, quotes not triple
_ml_basic_char = st.one_of(
    st.characters(
        blacklist_characters='"\\',
        blacklist_categories=("Cs",),
    ),
    _esc,
    st.just('"'),
    st.just('""'),
    st.just("\\\n"),
    st.just("\\\r\n"),
)

ml_basic_string = st.builds(
    lambda body: '"""' + body + '"""',
    st.lists(_ml_basic_char, max_size=10).map(_join),
)

_ml_literal_char = st.one_of(
    st.characters(blacklist_characters="'", blacklist_categories=("Cs",)),
    st.just("'"),
    st.just("''"),
)

ml_literal_string = st.builds(
    lambda body: "'''" + body + "'''",
    st.lists(_ml_literal_char, max_size=10).map(_join),
)

any_string = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# integers
_sign = st.sampled_from(["", "+", "-"])

dec_digits = st.text(alphabet=_digits, min_size=1, max_size=20)

dec_int = st.builds(
    lambda s, d: s + d,
    _sign,
    st.one_of(
        dec_digits,
        # underscores
        st.builds(
            lambda head, tail: head + tail,
            st.text(alphabet="123456789", min_size=1, max_size=1),
            st.lists(
                st.builds(
                    lambda d: "_" + d,
                    st.text(alphabet=_digits, min_size=1, max_size=1),
                ),
                min_size=1,
                max_size=6,
            ).map(_join),
        ),
        # leading zeros (accepted deviation)
        st.text(alphabet=_digits, min_size=2, max_size=10),
        # extreme magnitude
        st.just("9" * 40),
        st.just("0"),
    ),
)

_hex_digits = "0123456789abcdefABCDEF"
hex_int = st.builds(
    lambda body: "0x" + body,
    st.text(alphabet=_hex_digits, min_size=1, max_size=20),
)

oct_int = st.builds(
    lambda body: "0o" + body,
    st.text(alphabet="01234567", min_size=1, max_size=20),
)

bin_int = st.builds(
    lambda body: "0b" + body,
    st.text(alphabet="01", min_size=1, max_size=20),
)

any_int = st.one_of(dec_int, hex_int, oct_int, bin_int)

# floats
_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    _sign,
    st.text(alphabet=_digits, min_size=1, max_size=4),
)

_frac = st.builds(
    lambda d: "." + d,
    st.text(alphabet=_digits, min_size=1, max_size=12),
)

float_num = st.builds(
    lambda s, intpart, frac, exp: s + intpart + (frac or "") + (exp or ""),
    _sign,
    st.one_of(
        st.text(alphabet=_digits, min_size=1, max_size=12),
        st.just(""),  # for .5 form
    ),
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
).filter(lambda s: s not in ("", "+", "-") and ("." in s or "e" in s or "E" in s))

inf_nan = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

any_float = st.one_of(float_num, inf_nan)

# booleans
boolean = st.sampled_from(["true", "false"])

# dates
_year = st.text(alphabet=_digits, min_size=4, max_size=4)
_month = st.text(alphabet=_digits, min_size=2, max_size=2)
_day = st.text(alphabet=_digits, min_size=2, max_size=2)
_hour = st.text(alphabet=_digits, min_size=2, max_size=2)
_minute = st.text(alphabet=_digits, min_size=2, max_size=2)
_second = st.text(alphabet=_digits, min_size=2, max_size=2)

full_date = st.builds(
    lambda y, m, d: y + "-" + m + "-" + d, _year, _month, _day
)

_secfrac = st.builds(lambda d: "." + d, st.text(alphabet=_digits, min_size=1, max_size=6))

partial_time = st.builds(
    lambda h, mi, s, f: h + ":" + mi + ":" + s + (f or ""),
    _hour,
    _minute,
    _second,
    st.one_of(st.none(), _secfrac),
)

_offset = st.one_of(
    st.just("Z"),
    st.builds(
        lambda s, h, m: s + h + ":" + m,
        st.sampled_from(["+", "-"]),
        _hour,
        _minute,
    ),
)

full_time = st.builds(lambda pt, off: pt + off, partial_time, _offset)

_delim = st.sampled_from(["T", "t", " "])

offset_datetime = st.builds(
    lambda d, dl, t: d + dl + t, full_date, _delim, full_time
)
local_datetime = st.builds(
    lambda d, dl, t: d + dl + t, full_date, _delim, partial_time
)
local_date = full_date
local_time = partial_time

any_datetime = st.one_of(offset_datetime, local_datetime, local_date, local_time)

# ---------------------------------------------------------------- recursive values

_scalar_value = st.one_of(
    any_string,
    any_int,
    any_float,
    boolean,
    any_datetime,
)


def _key():
    return st.one_of(
        unquoted_key,
        basic_string,
        literal_string,
    )


def _dotted_key():
    return st.builds(
        lambda parts: ".".join(parts),
        st.lists(_key(), min_size=2, max_size=3),
    )

any_key = st.one_of(_key(), _dotted_key())


def _inline_table_kv(value):
    return st.builds(
        lambda k, v: k + " = " + v,
        any_key,
        value,
    )


def _inline_table(value):
    return st.builds(
        lambda kvs, trailing: "{" + ", ".join(kvs) + ("," if trailing and kvs else "") + "}",
        st.lists(_inline_table_kv(value), min_size=0, max_size=4),
        st.booleans(),
    )


def _array(value):
    return st.builds(
        lambda items, trailing: "[" + ", ".join(items) + ("," if trailing and items else "") + "]",
        st.lists(value, min_size=0, max_size=5),
        st.booleans(),
    )


def _value_strategy(depth):
    if depth <= 0:
        return _scalar_value
    inner = _value_strategy(depth - 1)
    return st.one_of(
        _scalar_value,
        _array(inner),
        _inline_table(inner),
    )


value = _value_strategy(6)


# ---------------------------------------------------------------- documents

def _key_value_line():
    return st.builds(
        lambda k, v: k + " = " + v,
        any_key,
        value,
    )


def _standard_table():
    return st.builds(
        lambda k: "[" + k + "]",
        any_key,
    )


def _array_table():
    return st.builds(
        lambda k: "[[" + k + "]]",
        any_key,
    )


def _comment():
    return st.builds(
        lambda body: "#" + body,
        st.text(
            alphabet=st.characters(blacklist_characters="\n", blacklist_categories=("Cs",)),
            max_size=20,
        ),
    )


def _line():
    return st.one_of(
        _key_value_line(),
        _standard_table(),
        _array_table(),
        _comment(),
        st.just(""),
    )


def _document():
    return st.builds(
        lambda lines, trailing_nl: "\n".join(lines) + ("\n" if trailing_nl and lines else ""),
        st.lists(_line(), min_size=0, max_size=12),
        st.booleans(),
    )


# ---------------------------------------------------------------- malformed near-valid


def _unterminated():
    return st.builds(
        lambda s: s,
        st.one_of(
            st.builds(lambda b: '"' + b, st.text(alphabet="abc", max_size=5)),
            st.builds(lambda b: "'" + b, st.text(alphabet="abc", max_size=5)),
            st.just('"""abc'),
            st.just("'''abc"),
        ),
    )


def _missing_delimiter():
    return st.sampled_from(
        [
            "[t",
            "[[t]",
            "[[t]]]",
            "a = [1, 2",
            "a = {b = 1",
            "a = {b = 1,",
            "a = ",
            "= 1",
            "a = 1 2",
            "a = \"x",
            "a = 'y",
            "[t]]",
            "a = [1,,2]",
            "a = {b = 1 c = 2}",
        ]
    )


def _stray_token():
    return st.builds(
        lambda pre, tok, post: pre + tok + post,
        st.sampled_from(["", "a = ", "[", "a = [", "a = {"]),
        st.sampled_from(["@", "$", "`", "\\", "?", "!", "%", "&", "*", "(", ")", "^"]),
        st.sampled_from(["", " = 1", "]", "}", "\n"]),
    )


malformed = st.one_of(_unterminated(), _missing_delimiter(), _stray_token())


# ---------------------------------------------------------------- deep nesting

def _deep_array(depth):
    return st.just("[" * depth + "]" * depth)


def _deep_inline(depth):
    return st.just("{a = " * depth + "1" + "}" * depth)


def _deep_doc():
    return st.builds(
        lambda d, kind: "a = " + (kind(d) if callable(kind) else kind),
        st.integers(min_value=1, max_value=2048),
        st.sampled_from([_deep_array, _deep_inline]),
    ).map(lambda s: s if isinstance(s, str) else s)


def _deep_array_value():
    return st.builds(
        lambda d: "a = " + "[" * d + "]" * d,
        st.integers(min_value=1, max_value=2048),
    )


def _deep_inline_value():
    return st.builds(
        lambda d: "a = " + "{x = " * d + "1" + "}" * d,
        st.integers(min_value=1, max_value=2048),
    )


deep = st.one_of(_deep_array_value(), _deep_inline_value())


# ---------------------------------------------------------------- final strategy

strategy = st.one_of(
    _document(),
    malformed,
    deep,
)
```