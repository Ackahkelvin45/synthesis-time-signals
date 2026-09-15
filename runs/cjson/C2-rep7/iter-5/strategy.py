from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _unicode_escape():
    return st.builds(lambda h: "\\u" + h, st.text(_hex, min_size=4, max_size=4))

def _surrogate_escape():
    hi = st.integers(min_value=0xD800, max_value=0xDBFF)
    lo = st.integers(min_value=0xDC00, max_value=0xDFFF)
    lone = st.builds(lambda n: "\\u%04x" % n, st.one_of(hi, lo))
    pair = st.builds(lambda a, b: "\\u%04x\\u%04x" % (a, b), hi, lo)
    return st.one_of(lone, pair)

_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _string_char():
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                      blacklist_categories=("Cs",)).filter(lambda c: c not in '"\\'),
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
    st.from_regex(r"0[0-9]{1,4}", fullmatch=True),
)

_frac = st.one_of(
    st.builds(lambda d: "." + d, st.from_regex(r"[0-9]{1,6}", fullmatch=True)),
    st.just("."),
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
        st.lists(inner, min_size=0, max_size=6).map(lambda xs: "[" + ",".join(xs) + "]"),
        st.just("[]"),
        st.lists(st.tuples(_string(), inner), min_size=0, max_size=6).map(
            lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"
        ),
        st.just("{}"),
        st.builds(
            lambda v: '{"dup":' + v + ',"dup":' + v + "}",
            st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])),
        ),
        st.builds(lambda a: "[" + a + "]", inner),
        st.builds(lambda v: '{"k":' + v + "}", inner),
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

# ---------- broadened structural diversity (accepted structures) ----------

def _wide_array():
    return st.lists(
        st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])),
        min_size=0, max_size=40,
    ).map(lambda xs: "[" + ",".join(xs) + "]")

def _wide_object():
    keys = st.text(
        st.characters(min_codepoint=0x61, max_codepoint=0x7a),
        min_size=1, max_size=6,
    )
    return st.lists(
        st.tuples(keys, st.one_of(_number(), _string(),
                                  st.sampled_from(["true", "false", "null"]))),
        min_size=0, max_size=40,
    ).map(lambda ps: "{" + ",".join('"' + k + '":' + v for k, v in ps) + "}")

def _heterogeneous_mix():
    # arrays/objects mixing every value kind, varied depth
    leaf = st.one_of(_number(), _string(), _extreme_number(),
                     st.sampled_from(["true", "false", "null"]))
    def build(d):
        if d <= 0:
            return leaf
        sub = st.deferred(lambda: build(d - 1))
        return st.one_of(
            leaf,
            st.lists(sub, min_size=0, max_size=5).map(
                lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(st.tuples(_string(), sub), min_size=0, max_size=5).map(
                lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
        )
    return build(4)

def _balanced_structures():
    # deeply balanced but irregular shapes
    return st.recursive(
        st.one_of(_number(), _string(),
                  st.sampled_from(["true", "false", "null"])),
        lambda children: st.one_of(
            st.lists(children, min_size=1, max_size=4).map(
                lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(st.tuples(_string(), children), min_size=1, max_size=4).map(
                lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
        ),
        max_leaves=30,
    )

def _whitespace_variants():
    ws = st.sampled_from([" ", "\t", "\n", "\r", "\r\n", "  ", "\n\t"])
    return st.builds(
        lambda a, b, c, d, e: a + "[" + b + "1" + c + "," + d + "2" + e + "]",
        ws, ws, ws, ws, ws,
    )

def _key_diversity_object():
    keys = st.one_of(
        _string(),
        st.sampled_from(['"a"', '"b"', '"key"', '""', '"\\n"', '"\\u0041"',
                         '"dup"', '"0"', '"true"', '"null"']),
    )
    return st.lists(
        st.tuples(keys, st.one_of(_number(), _string(),
                                  st.sampled_from(["true", "false", "null"]))),
        min_size=1, max_size=12,
    ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}")

# ---------- top-level strategy ----------

strategy = st.one_of(
    _value,
    _deep_array(),
    _deep_object(),
    _deep_mixed(),
    _malformed,
    _wide_array(),
    _wide_object(),
    _heterogeneous_mix(),
    _balanced_structures(),
    _whitespace_variants(),
    _key_diversity_object(),
    st.sampled_from([
        "{}", "[]", "null", "true", "false", "0", "-0",
        '"\\u0000"', '"\\ud800"', '"\\udc00"', '"\\ud83d\\ude00"',
        '"a\x00b"', '"a\tb"', "\ufeff{}", "1abc", "1 2",
        "1e309", "-1e309", "01", "1.", "0x10",
    ]),
).map(lambda s: s if isinstance(s, str) else json.dumps(s))