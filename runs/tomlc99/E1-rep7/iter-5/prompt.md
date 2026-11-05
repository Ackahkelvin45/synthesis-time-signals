Here is the current Hypothesis strategy:

```python
import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Character / text building blocks
# ---------------------------------------------------------------------------

_SAFE_RAW = st.characters(
    blacklist_categories=(), blacklist_characters="\x00"
)

_BASIC_SL = st.characters(
    blacklist_characters='\x00"\\\n\r',
    blacklist_categories=(),
)

_LIT_SL = st.characters(
    blacklist_characters="\x00'\n\r",
    blacklist_categories=(),
)

_ML_BASIC = st.characters(
    blacklist_characters='\x00"',
    blacklist_categories=(),
)

_ML_LIT = st.characters(
    blacklist_characters="\x00'",
    blacklist_categories=(),
)

_COMMENT_CH = st.characters(
    blacklist_characters="\x00\n\r",
    blacklist_categories=(),
)

_NONASCII = st.sampled_from(
    [
        "é", "ü", "ñ", "Ω", "λ", "水", "火", "🙂", "🚀", "𝕏",
        "\u00e9", "\u03c0", "\u4e2d", "\U0001F600", "\u00a0", "\u00b7",
    ]
)

_HEX = "0123456789abcdefABCDEF"


def _hex_digits(n):
    return st.lists(st.sampled_from(_HEX), min_size=n, max_size=n).map("".join)


# ---------------------------------------------------------------------------
# Escapes and basic strings
# ---------------------------------------------------------------------------

_simple_esc = st.sampled_from(["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"])

_unicode_esc = _hex_digits(4).map(lambda h: "\\u" + h)
_ex_unicode_esc = _hex_digits(8).map(lambda h: "\\U" + h)

_escape = st.one_of(_simple_esc, _unicode_esc, _ex_unicode_esc)


def _basic_sl_body():
    piece = st.one_of(
        _BASIC_SL.map(lambda c: c),
        _escape,
        _NONASCII,
    )
    return st.lists(piece, max_size=12).map("".join)


_basic_string = _basic_sl_body().map(lambda s: '"' + s + '"')


def _literal_sl_body():
    piece = st.one_of(_LIT_SL.map(lambda c: c), _NONASCII)
    return st.lists(piece, max_size=12).map("".join)


_literal_string = _literal_sl_body().map(lambda s: "'" + s + "'")


def _ml_basic_body():
    piece = st.one_of(
        _ML_BASIC.map(lambda c: c),
        _escape,
        _NONASCII,
        st.sampled_from(["\n", "\r\n", "\\\n", "\\\r\n"]),
    )
    def build(parts):
        s = "".join(parts)
        while '"""' in s:
            s = s.replace('"""', '""')
        return s
    return st.lists(piece, max_size=10).map(build)


_ml_basic_string = _ml_basic_body().map(lambda s: '"""' + s + '"""')


def _ml_lit_body():
    piece = st.one_of(
        _ML_LIT.map(lambda c: c),
        _NONASCII,
        st.sampled_from(["\n", "\r\n"]),
    )
    def build(parts):
        s = "".join(parts)
        while "'''" in s:
            s = s.replace("'''", "''")
        return s
    return st.lists(piece, max_size=10).map(build)


_ml_literal_string = _ml_lit_body().map(lambda s: "'''" + s + "'''")


_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------------------------------------------------------------------------
# Integers
# ---------------------------------------------------------------------------

_dec_digits = st.lists(st.sampled_from("0123456789"), min_size=1, max_size=25).map("".join)


def _with_underscores(digits):
    return st.tuples(st.just(digits), st.booleans()).map(
        lambda t: t[0] if not t[1] or len(t[0]) < 2
        else "_".join(list(t[0]))
    )


_dec_int = st.one_of(
    _dec_digits,
    st.tuples(
        st.sampled_from(["", "+", "-"]),
        st.one_of(_dec_digits, _dec_digits.flatmap(_with_underscores)),
    ).map(lambda t: t[0] + t[1]),
    st.lists(st.sampled_from("0123456789"), min_size=2, max_size=6)
    .map(lambda d: "0" + "".join(d)),
    st.just("0"),
    st.just("9223372036854775808"),
    st.just("-9223372036854775809"),
    st.just("18446744073709551616"),
    st.just("99999999999999999999999999999999999999999999999999"),
)

_hex_int = st.tuples(
    st.sampled_from(["0x", "0X"]),
    st.lists(st.sampled_from(_HEX), min_size=1, max_size=20).map("".join),
).map(lambda t: t[0] + t[1])

_oct_int = st.tuples(
    st.sampled_from(["0o", "0O"]),
    st.lists(st.sampled_from("01234567"), min_size=1, max_size=20).map("".join),
).map(lambda t: t[0] + t[1])

_bin_int = st.tuples(
    st.sampled_from(["0b", "0B"]),
    st.lists(st.sampled_from("01"), min_size=1, max_size=20).map("".join),
).map(lambda t: t[0] + t[1])

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# ---------------------------------------------------------------------------
# Floats
# ---------------------------------------------------------------------------

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.sampled_from("0123456789"), min_size=1, max_size=4).map("".join),
).map(lambda t: t[0] + t[1] + t[2])

_frac_part = st.tuples(
    st.just("."),
    st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join),
).map(lambda t: t[0] + t[1])

_float = st.one_of(
    st.tuples(
        st.one_of(_dec_digits, st.just("0")),
        _frac_part,
        st.one_of(st.just(""), _exp_part),
    ).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_dec_digits, _exp_part).map(lambda t: t[0] + t[1]),
    st.tuples(_dec_digits, st.just(".")).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("."), st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join))
    .map(lambda t: t[0] + t[1]),
    st.sampled_from(
        [
            "1e309", "1e-309", "-1e309", "1.0e308", "1.7976931348623157e308",
            "4.9e-324", "1e999999", "1e-999999", "0.0", "-0.0", "1.0",
        ]
    ),
    st.sampled_from(
        ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
    ),
)

# ---------------------------------------------------------------------------
# Booleans / date-times
# ---------------------------------------------------------------------------

_boolean = st.sampled_from(["true", "false"])

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hour = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_minute = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_second = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

_secfrac = st.tuples(
    st.just("."),
    st.lists(st.sampled_from("0123456789"), min_size=1, max_size=9).map("".join),
).map(lambda t: t[0] + t[1])

_partial_time = st.tuples(
    _hour, st.just(":"), _minute, st.just(":"), _second,
    st.one_of(st.just(""), _secfrac),
).map(lambda t: "".join(t))

_full_date = st.tuples(
    _year, st.just("-"), _month, st.just("-"), _day
).map(lambda t: "".join(t))

_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _hour, st.just(":"), _minute
    ).map(lambda t: "".join(t)),
)

_full_time = st.tuples(_partial_time, _offset).map(lambda t: t[0] + t[1])

_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(_full_date, _delim, _full_time).map(lambda t: "".join(t))
_local_date_time = st.tuples(_full_date, _delim, _partial_time).map(lambda t: "".join(t))
_local_date = _full_date
_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    st.sampled_from(
        ["1979-02-30", "2000-13-01", "0000-00-00", "9999-99-99",
         "2021-02-29", "2023-04-31"]
    ),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.lists(
    st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"),
    min_size=1,
    max_size=12,
).map("".join)

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key, st.just('""'))


def _dotted_key():
    return st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))


_key = st.one_of(_simple_key, _dotted_key())

# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

_comment = st.tuples(
    st.just("#"),
    st.lists(_COMMENT_CH, max_size=20).map("".join),
).map(lambda t: t[0] + t[1])

_optional_comment = st.one_of(st.just(""), _comment)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

_MAX_DEPTH = 2048


def _scalar_value():
    # Upweight productions the run under-used: hex/oct/bin integers, floats,
    # booleans, and the date-time family. These leaves now dominate so the
    # parser exercises those grammar productions far more heavily.
    return st.one_of(
        _string,
        _integer,
        _hex_int,
        _hex_int,
        _hex_int,
        _hex_int,
        _oct_int,
        _oct_int,
        _oct_int,
        _oct_int,
        _bin_int,
        _bin_int,
        _bin_int,
        _bin_int,
        _float,
        _float,
        _float,
        _float,
        _float,
        _boolean,
        _boolean,
        _boolean,
        _boolean,
        _boolean,
        _offset_date_time,
        _offset_date_time,
        _offset_date_time,
        _offset_date_time,
        _local_date_time,
        _local_date_time,
        _local_date_time,
        _local_date_time,
        _local_date,
        _local_date,
        _local_date,
        _local_time,
        _local_time,
        _local_time,
        _date_time,
    )


def _build_value_st():
    leaf = _scalar_value()

    def extend(children):
        child = children
        array = st.tuples(
            st.just("["),
            st.lists(
                st.tuples(
                    child,
                    _optional_comment,
                    st.sampled_from([",", ", ", ",\n", "\n,", " , "]),
                ).map(lambda t: t[0] + t[1] + t[2]),
                max_size=4,
            ).map("".join),
            st.sampled_from(["", ",", ",\n", " , "]),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3])

        inline = st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(
                    _key,
                    st.just(" = "),
                    child,
                    st.sampled_from([",", ", "]),
                ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
                max_size=3,
            ).map("".join),
            st.sampled_from(["", ","]),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3])

        return st.one_of(array, inline)

    return st.recursive(leaf, extend, max_leaves=8)


_value = _build_value_st()


def _deep_array(depth):
    inner = _scalar_value()
    return st.tuples(
        st.just("[" * depth),
        inner,
        st.just("]" * depth),
    ).map(lambda t: t[0] + t[1] + t[2])


def _deep_inline(depth):
    inner = _scalar_value()
    return st.tuples(
        st.just("{k = " * depth),
        inner,
        st.just("}" * depth),
    ).map(lambda t: t[0] + t[1] + t[2])


def _deep_value():
    return st.one_of(
        st.integers(min_value=1500, max_value=_MAX_DEPTH).flatmap(
            lambda d: _deep_array(d)
        ),
        st.integers(min_value=200, max_value=900).flatmap(
            lambda d: _deep_inline(d)
        ),
    )


# ---------------------------------------------------------------------------
# Malformed / near-valid mutations
# ---------------------------------------------------------------------------

def _malformed():
    good_kv = st.tuples(_key, st.just(" = "), _value).map(lambda t: "".join(t))
    return st.one_of(
        st.tuples(_key, st.just(" = ["), _scalar_value()).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" = {a = "), _scalar_value()).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" = [["), _scalar_value(), st.just("]]]")).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" = {{a = "), _scalar_value(), st.just("}}}")).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(' = "abc')).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" = 'abc")).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(' = """abc')).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" "), _scalar_value()).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" = "), _scalar_value(), st.just(" ???")).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" =\n"), _scalar_value()).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(' = "a\\q"')).map(lambda t: "".join(t)),
        st.tuples(_key, st.just(" = {a = 1,\nb = 2}")).map(lambda t: "".join(t)),
        st.tuples(st.just("é"), st.just(" = "), _scalar_value()).map(lambda t: "".join(t)),
        good_kv,
    )


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _key_value_line():
    return st.tuples(
        _key, st.just(" = "), _value, _optional_comment
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])


def _standard_table():
    return st.tuples(
        st.just("["), _key, st.just("]"), _optional_comment
    ).map(lambda t: "".join(t))


def _array_table():
    return st.tuples(
        st.just("[["), _key, st.just("]]"), _optional_comment
    ).map(lambda t: "".join(t))


def _line():
    return st.one_of(
        _key_value_line(),
        _standard_table(),
        _array_table(),
        _comment,
        st.just(""),
    )


def _nl():
    return st.sampled_from(["\n", "\r\n"])


def _document():
    base = st.lists(_line(), max_size=8)
    deep = st.lists(_deep_value().map(lambda v: "deep = " + v), max_size=1)
    mal = st.lists(_malformed(), max_size=2)
    return st.tuples(base, deep, mal).map(
        lambda t: t[0] + t[1] + t[2]
    ).flatmap(
        lambda lines: st.tuples(
            st.just(lines),
            st.one_of(
                st.just("\n").flatmap(
                    lambda _: st.lists(_nl(), min_size=0, max_size=1)
                    .map(lambda nls: nls[0] if nls else "\n")
                ),
                st.just("\n"),
            ),
        ).map(
            lambda t: t[1].join(t[0])
        )
    )


strategy = _document()
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 113,
    "reject": 237
  },
  "acceptance_rate": 0.323,
  "max_nesting_depth": 1863,
  "productions_accepted": [
    "BASIC_STRING",
    "BIN_INT",
    "COMMENT",
    "DEC_INT",
    "FLOAT",
    "HEX_INT",
    "LITERAL_STRING",
    "LOCAL_DATE",
    "LOCAL_TIME",
    "NL",
    "UNQUOTED_KEY",
    "array_",
    "array_table",
    "array_values",
    "comment",
    "comment_or_nl",
    "date_time",
    "document",
    "dotted_key",
    "expression",
    "floating_point",
    "inline_table",
    "inline_table_keyvals",
    "inline_table_keyvals_non_empty",
    "integer",
    "key",
    "key_value",
    "nl_or_comment",
    "quoted_key",
    "simple_key",
    "standard_table",
    "string",
    "table",
    "unquoted_key",
    "value"
  ],
  "productions_gap": [
    "bool_",
    "BOOLEAN",
    "ML_BASIC_STRING",
    "ML_LITERAL_STRING",
    "INF",
    "NAN",
    "OCT_INT",
    "OFFSET_DATE_TIME",
    "LOCAL_DATE_TIME"
  ],
  "cap_distance_mass": 0.124,
  "novelty": 45,
  "divergences": 57,
  "divergence_examples": [
    "b'deep = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['",
    "b'deep = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['",
    "b'\\ndeep = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **one edit of your choice from this list** — add_or_upweight_production (add or upweight a grammar production the inputs under-use); generate_nesting_toward_cap (generate nesting close to the parser's depth limit); fix_feature_encoding (fix how one feature of the format is encoded); broaden_exploration (diversify the structures the inputs take). Use the run feedback above where it is given, and write the name of the edit you chose on the first line as EDIT: <name>.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.