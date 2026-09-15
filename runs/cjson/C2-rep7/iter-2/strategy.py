from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _unicode_escape():
    return st.builds(lambda h: "\\u" + h, st.text(_hex, min_size=4, max_size=4))

def _surrogate_escape():
    # lone surrogate escapes (rejected by parser) and valid pairs
    hi = st.integers(min_value=0xD800, max_value=0xDBFF)
    lo = st.integers(min_value=0xDC00, max_value=0xDFFF)
    lone = st.builds(lambda n: "\\u%04x" % n, st.one_of(hi, lo))
    pair = st.builds(lambda a, b: "\\u%04x\\u%04x" % (a, b), hi, lo)
    return st.one_of(lone, pair)

_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _string_char():
    return st.one_of(
        # safe code points
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                      blacklist_categories=("Cs",)).filter(lambda c: c not in '"\\'),
        # raw control bytes incl NUL, tab, newline
        st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
        _simple_esc,
        _unicode_escape(),
        _surrogate_escape(),
    )

def _string_body():
    return st.lists(_string_char(), max_size=12).map("".join)

def _string():
    return st.builds(lambda b: '"' + b + '"', _string_body())

# ---------- numbers ----------

_int = st.one_of(
    st.just("0"),
    st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True),
    # leading zeros (accepted by parser)
    st.from_regex(r"0[0-9]{1,4}", fullmatch=True),
)

_frac = st.one_of(
    st.builds(lambda d: "." + d, st.from_regex(r"[0-9]{1,6}", fullmatch=True)),
    st.just("."),  # trailing dot, accepted
)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.from_regex(r"[0-9]{1,4}", fullmatch=True),
)

def _number():
    sign = st.sampled_from(["", "-"])
    mantissa = st.one_of(
        _int,
        st.tuples(_int, _frac).map(lambda t: t[0] + t[1]),
    )
    return st.tuples(sign, mantissa, st.one_of(st.just(""), _exp)).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _extreme_number():
    return st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e999999", "-1e999999",
        "0e0", "0e999", "1E+308", "1e-9999",
        "9" * 40, "-" + "9" * 40,
        "0." + "0" * 20 + "1",
        "1" + "0" * 300,
        "1.7976931348623157e309",
    ])

# ---------- malformed / edge fragments ----------

_malformed = st.sampled_from([
    "", " ", "  \t\n",
    "-", "+1", ".5", "01", "1.", "0x10", "0X1F",
    "NaN", "Infinity", "-Infinity", "nan", "inf",
    "tru", "fals", "nul", "TRUE", "True", "NULL",
    "'single'", '"unterminated', '"esc\\q"', '"\\u12"', '"\\uZZZZ"',
    "[1,]", '{"a":1,}', "[,1]", "{,}", '{"a" 1}', '{"a":}', "{:1}",
    "[1 2]", "[1,2", '{"a":1', "[", "{", "]", "}",
    ",", ":", "\\", '"\\', "\x00", "\x01\x02",
    "\ufeff", "\ufeff1", "\ufeff[1]",
])

# ---------- recursive JSON values ----------

def _json_value(depth):
    if depth <= 0:
        return st.one_of(_string(), _number(), _extreme_number(),
                         st.sampled_from(["true", "false", "null"]),
                         _malformed)
    inner = st.deferred(lambda: _json_value(depth - 1))
    return st.one_of(
        _string(),
        _number(),
        _extreme_number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed,
        # arrays
        st.lists(inner, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]"),
        st.just("[]"),
        # objects
        st.lists(st.tuples(_string(), inner), max_size=4).map(
            lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"
        ),
        st.just("{}"),
        # duplicate keys explicitly
        st.builds(
            lambda v: '{"dup":' + v + ',"dup":' + v + "}",
            st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])),
        ),
    )

_value = st.deferred(lambda: _json_value(3))

# ---------- deep nesting near the 1000 limit ----------

def _deep_array():
    return st.integers(min_value=700, max_value=950).map(
        lambda n: "[" * n + "]" * n
    )

def _deep_object():
    return st.integers(min_value=700, max_value=950).map(
        lambda n: '{"a":' * n + "null" + "}" * n
    )

def _deep_mixed():
    return st.integers(min_value=700, max_value=950).map(
        lambda n: ("[{" * (n // 2)) + "0" + ("}]" * (n // 2))
    )

# ---------- top-level strategy ----------

strategy = st.one_of(
    _value,
    _deep_array(),
    _deep_object(),
    _deep_mixed(),
    _malformed,
    st.sampled_from([
        "{}", "[]", "null", "true", "false", "0", "-0",
        '"\\u0000"', '"\\ud800"', '"\\udc00"', '"\\ud83d\\ude00"',
        '"a\x00b"', '"a\tb"', "\ufeff{}", "1abc", "1 2",
        "1e309", "-1e309", "01", "1.", "0x10",
    ]),
).map(lambda s: s if isinstance(s, str) else json.dumps(s))