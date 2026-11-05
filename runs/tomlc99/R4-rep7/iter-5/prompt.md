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
# UTF-8 decoding edge cases (targets toml_utf8_to_ucs)
# ---------------------------------------------------------------------------

# Raw invalid / truncated UTF-8 byte sequences encoded as latin-1-decoded
# strings so they can be embedded inside string literals. These exercise the
# decoder's length checks and continuation-byte checks.
def _utf8_byte(b):
    return chr(b & 0xFF)


def _utf8_seq(lead, conts, truncate=0):
    bs = [lead] + list(conts)
    if truncate:
        bs = bs[:-truncate]
    return "".join(_utf8_byte(b) for b in bs)


def _utf8_edge_cases():
    cases = []
    # Valid sequences of every length (2..4) plus ASCII.
    cases.append("\x41")                      # ASCII
    cases.append(_utf8_seq(0xC3, [0xA9]))     # é 2-byte
    cases.append(_utf8_seq(0xE2, [0x82, 0xAC]))     # € 3-byte
    cases.append(_utf8_seq(0xF0, [0x9F, 0x98, 0x80]))  # 🙂 4-byte
    # Truncated multibyte sequences for each lead-byte class.
    for lead, n in [(0xC3, 1), (0xE2, 2), (0xF0, 3), (0xF8, 4), (0xFC, 5)]:
        conts = [0x80] * n
        for t in range(1, n + 1):
            cases.append(_utf8_seq(lead, conts, truncate=t))
    # Bad continuation bytes for each lead-byte class.
    for lead, n in [(0xC3, 1), (0xE2, 2), (0xF0, 3), (0xF8, 4), (0xFC, 5)]:
        for pos in range(n):
            for bad in (0x41, 0x00, 0x80, 0xBF, 0xC0):
                conts = [0x80] * n
                conts[pos] = bad
                cases.append(_utf8_seq(lead, conts))
    # Overlong encodings.
    cases.append(_utf8_seq(0xC0, [0x80]))            # overlong NUL
    cases.append(_utf8_seq(0xC1, [0xBF]))            # overlong
    cases.append(_utf8_seq(0xE0, [0x80, 0x80]))      # overlong
    cases.append(_utf8_seq(0xF0, [0x80, 0x80, 0x80]))  # overlong
    # Surrogate encodings (invalid).
    cases.append(_utf8_seq(0xED, [0xA0, 0x80]))      # U+D800
    cases.append(_utf8_seq(0xED, [0xBF, 0xBF]))      # U+DFFF
    # Max codepoint U+10FFFF.
    cases.append(_utf8_seq(0xF4, [0x8F, 0xBF, 0xBF]))
    # Lone continuation bytes.
    cases.append(_utf8_byte(0x80))
    cases.append(_utf8_byte(0x80) + _utf8_byte(0x80))
    cases.append(_utf8_byte(0xBF))
    # 5- and 6-byte lead bytes.
    cases.append(_utf8_seq(0xF8, [0x88, 0x80, 0x80, 0x80]))
    cases.append(_utf8_seq(0xFC, [0x84, 0x80, 0x80, 0x80, 0x80]))
    # Bare lead bytes.
    for lead in (0xC3, 0xE2, 0xF0, 0xF8, 0xFC, 0xFE, 0xFF):
        cases.append(_utf8_byte(lead))
    return cases


_UTF8_EDGE = st.sampled_from(_utf8_edge_cases())


# ---------------------------------------------------------------------------
# Escapes and basic strings
# ---------------------------------------------------------------------------

_simple_esc = st.sampled_from(["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"])

_unicode_esc = _hex_digits(4).map(lambda h: "\\u" + h)
_ex_unicode_esc = _hex_digits(8).map(lambda h: "\\U" + h)

# Invalid escapes (targets parser error paths)
_bad_esc = st.sampled_from(
    ["\\x", "\\q", "\\a", "\\v", "\\0", "\\'", "\\U0001", "\\u12", "\\uZZZZ"]
)

_escape = st.one_of(_simple_esc, _unicode_esc, _ex_unicode_esc, _bad_esc)


def _basic_sl_body():
    piece = st.one_of(
        _BASIC_SL.map(lambda c: c),
        _escape,
        _NONASCII,
        _UTF8_EDGE,
    )
    return st.lists(piece, max_size=12).map("".join)


_basic_string = _basic_sl_body().map(lambda s: '"' + s + '"')


def _literal_sl_body():
    piece = st.one_of(_LIT_SL.map(lambda c: c), _NONASCII, _UTF8_EDGE)
    return st.lists(piece, max_size=12).map("".join)


_literal_string = _literal_sl_body().map(lambda s: "'" + s + "'")


def _ml_basic_body():
    piece = st.one_of(
        _ML_BASIC.map(lambda c: c),
        _escape,
        _NONASCII,
        _UTF8_EDGE,
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
        _UTF8_EDGE,
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
    # Near-miss timestamp forms to exercise toml_timestamp_at
    st.sampled_from(
        [
            "1979-05-27T07:32:00",       # local date-time
            "1979-05-27T00:32:00.999999-07:00",
            "1979-05-27 07:32:00Z",
            "1979-05-27",                # local date
            "07:32:00",                  # local time
            "07:32:00.999",              # local time with frac
            "1979-05-27T07:32:00.123456789Z",
            "1979-05-27T07:32:00+00:00",
            "1979-05-27T07:32:00-00:00",
            "1979-05-27t07:32:00z",
            "1979-05-27T7:32:00Z",       # single-digit hour (invalid)
            "1979-05-27T07:32Z",         # missing seconds (invalid)
            "1979-05-27T07:32:00.",      # trailing dot (invalid)
            "1979-05-27T07:32:00+07",    # bad offset (invalid)
        ]
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
    return st.one_of(
        _string,
        _integer,
        _float,
        _boolean,
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

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 70.11,
  "region_coverage_pct": 71.59,
  "least_covered_functions": [
    "toml_utf8_to_ucs (0% of branches)",
    "toml_parse_file (0% of branches)",
    "norm_lit_str (0% of branches)",
    "toml_rtos (0% of branches)",
    "toml_timestamp_at (0% of branches)"
  ],
  "least_covered_function_source": "int toml_utf8_to_ucs(const char *orig, int len, int64_t *ret) {\n  const unsigned char *buf = (const unsigned char *)orig;\n  unsigned i = *buf++;\n  int64_t v;\n\n  /* 0x00000000 - 0x0000007F:\n     0xxxxxxx\n  */\n  if (0 == (i >> 7)) {\n    if (len < 1)\n      return -1;\n    v = i;\n    return *ret = v, 1;\n  }\n  /* 0x00000080 - 0x000007FF:\n     110xxxxx 10xxxxxx\n  */\n  if (0x6 == (i >> 5)) {\n    if (len < 2)\n      return -1;\n    v = i & 0x1f;\n    for (int j = 0; j < 1; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x00000800 - 0x0000FFFF:\n     1110xxxx 10xxxxxx 10xxxxxx\n  */\n  if (0xE == (i >> 4)) {\n    if (len < 3)\n      return -1;\n    v = i & 0x0F;\n    for (int j = 0; j < 2; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x00010000 - 0x001FFFFF:\n     11110xxx 10xxxxxx 10xxxxxx 10xxxxxx\n  */\n  if (0x1E == (i >> 3)) {\n    if (len < 4)\n      return -1;\n    v = i & 0x07;\n    for (int j = 0; j < 3; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x00200000 - 0x03FFFFFF:\n     111110xx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx\n  */\n  if (0x3E == (i >> 2)) {\n    if (len < 5)\n      return -1;\n    v = i & 0x03;\n    for (int j = 0; j < 4; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x04000000 - 0x7FFFFFFF:\n     1111110x 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx\n/* ... truncated ... */"
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.