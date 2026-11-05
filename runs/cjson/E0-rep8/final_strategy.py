from hypothesis import strategies as st
import json

# ---------- building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = _hex4().map(lambda h: "\\u" + h)

# lone surrogates: parser rejects, but interesting to fuzz
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDFFF"]
)

# valid surrogate pairs (high surrogate followed by low surrogate)
_surrogate_pair = st.tuples(
    st.sampled_from(["\\ud800", "\\ud801", "\\udbff", "\\uD800"]),
    st.sampled_from(["\\udc00", "\\udc01", "\\udfff", "\\uDC00"]),
).map(lambda t: t[0] + t[1])

# raw control / NUL bytes inside strings (parser accepts)
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

# safe code points (no quote, backslash, control)
_safechar = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_string_piece = st.one_of(
    _safechar,
    _simple_esc,
    _unicode_esc,
    _surrogate_esc,
    _surrogate_pair,
    _raw_control,
)

def _make_string():
    return st.lists(_string_piece, max_size=12).map(lambda parts: '"' + "".join(parts) + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
    _digits,  # leading zeros (accepted by parser)
    st.just(""),  # for malformed like ".5" or "-"
)

_frac_part = st.one_of(
    st.just(""),
    _digits.map(lambda d: "." + d),
    st.just("."),  # trailing dot (accepted)
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_sign = st.one_of(st.just(""), st.just("-"), st.just("+"))

def _make_number():
    return st.tuples(_sign, _int_part, _frac_part, _exp_part).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

# extreme magnitudes
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-400", "-1e-400",
    "1e999999999", "0." + "0" * 20 + "1",
    "9" * 40, "-" + "9" * 40,
    "123456789012345678901234567890",
    "1e308", "1.7976931348623157e308",
    "0x10", "0xDEADBEEF", "0x", "0xg",
])

_number = st.one_of(_make_number(), _extreme_number)

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null", "NaN", "Infinity", "-Infinity"])

# ---------- recursive values ----------

_key = _make_string()

def _make_pair():
    return st.tuples(_key, st.just(":"), st.deferred(lambda: _value)).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _make_obj():
    return st.tuples(
        st.just("{"),
        st.lists(_make_pair(), max_size=4).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + t[2])

def _make_arr():
    return st.tuples(
        st.just("["),
        st.lists(st.deferred(lambda: _value), max_size=4).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + t[2])

_value = st.deferred(lambda: _value_strategy)

_value_strategy = st.recursive(
    st.one_of(_make_string(), _number, _literal),
    lambda children: st.one_of(_make_obj(), _make_arr()),
    max_leaves=20,
)

# ---------- deep nesting near the 1000 limit ----------

# Generate depths that straddle the parser's depth cap (around 1000), with
# emphasis on the boundary region where acceptance/rejection flips.
_depth = st.one_of(
    st.just(0),
    st.just(1),
    st.just(2),
    st.integers(min_value=0, max_value=50),
    st.integers(min_value=900, max_value=1100),
    st.sampled_from([998, 999, 1000, 1001, 1002, 1003]),
)

def _deep_array():
    return _depth.map(lambda d: "[" * d + "]" * d)

def _deep_object():
    return _depth.map(lambda d: '{"a":' * d + "0" + "}" * d)

# Mixed deep nesting: arrays and objects interleaved at boundary depths.
def _deep_mixed():
    return st.tuples(
        _depth,
        st.lists(st.sampled_from(["[", '{"a":']), min_size=0, max_size=0),
    ).map(lambda t: t[0])  # placeholder, replaced below

def _deep_mixed_real():
    return st.tuples(
        st.integers(min_value=900, max_value=1050),
        st.lists(st.sampled_from(["[", '{"a":']), min_size=1, max_size=1050),
    ).map(lambda t: "".join(t[1]) + "0" + "".join(
        "]" if p == "[" else "}" for p in reversed(t[1])
    ))

# ---------- malformed near-valid ----------

_malformed = st.sampled_from([
    "",
    "{",
    "[",
    "}",
    "]",
    ",",
    ":",
    "{},",
    "[,]",
    "[1,]",
    '{"a":1,}',
    '{"a" 1}',
    '{"a":}',
    '{:1}',
    '{"a":1 "b":2}',
    '"unterminated',
    '"\\',
    '"\\u12"',
    '"\\u"',
    '"\\x41"',
    "'single'",
    "{a:1}",
    "{'a':1}",
    "-",
    "+",
    "+1",
    ".5",
    "-.5",
    "1.",
    "01",
    "00",
    "-01",
    "1e",
    "1e+",
    "1e-",
    "1.2.3",
    "1 2",
    "1abc",
    "truefalse",
    "nulll",
    "tru",
    "fals",
    "NaN",
    "Infinity",
    "-Infinity",
    "\\u0000",
    "\x00",
    "\xef\xbb\xbf1",
    "\ufeff1",
    "1\x00",
    '{"a":1}\x00',
    "[1,2,3]extra",
    '{"a":1}{"b":2}',
    "1,2",
])

# ---------- whitespace-heavy production (under-used) ----------

_ws = st.sampled_from([" ", "\t", "\n", "\r", "\r\n", "\x0b", "\x0c", ""])

def _ws_pad():
    return st.lists(_ws, min_size=0, max_size=4).map(lambda parts: "".join(parts))

def _ws_value():
    # A value with whitespace sprinkled around structural tokens.
    return st.tuples(
        _ws_pad(),
        st.deferred(lambda: _value),
        _ws_pad(),
    ).map(lambda t: t[0] + t[1] + t[2])

def _ws_array():
    return st.tuples(
        _ws_pad(),
        st.lists(_ws_value(), max_size=4).map(lambda vs: ("," + _ws_pad()).join(vs)),
        _ws_pad(),
    ).map(lambda t: "[" + t[0] + t[1] + t[2] + "]")

def _ws_object():
    def _pair():
        return st.tuples(
            _ws_pad(),
            _key,
            _ws_pad(),
            st.just(":"),
            _ws_pad(),
            st.deferred(lambda: _value),
            _ws_pad(),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5] + t[6])
    return st.tuples(
        _ws_pad(),
        st.lists(_pair(), max_size=4).map(lambda ps: ("," + _ws_pad()).join(ps)),
        _ws_pad(),
    ).map(lambda t: "{" + t[0] + t[1] + t[2] + "}")

_ws_document = st.one_of(_ws_array(), _ws_object())

# ---------- combine ----------

def _join(t):
    return "".join(t)

_top = st.one_of(
    _value_strategy,
    _deep_array(),
    _deep_object(),
    _deep_mixed_real(),
    _malformed,
    _ws_document,
    st.tuples(_value_strategy, st.sampled_from(["", "\x00", " ", "x", "1"])).map(_join),
    st.tuples(st.sampled_from(["", "\ufeff", "\xef\xbb\xbf", " ", "\n"]), _value_strategy).map(_join),
)

strategy = _top