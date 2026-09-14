```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"
_hex_digits = st.sampled_from(list(_hex))

def _make_unicode_escape():
    # \uXXXX including surrogate halves
    return st.tuples(st.just("\\u"), _hex_digits, _hex_digits, _hex_digits, _hex_digits).map(
        lambda t: "".join(t)
    )

def _make_simple_escape():
    return st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _make_escaped_seq():
    return st.one_of(_make_simple_escape(), _make_unicode_escape())

# safe unescaped chars: exclude quote, backslash, control chars, and raw NUL
_safe_char = st.characters(
    blacklist_categories=("Cc", "Cs"),
    blacklist_characters='"\\\x00',
)

def _make_string_body():
    pieces = st.one_of(_safe_char, _make_escaped_seq())
    return st.lists(pieces, min_size=0, max_size=12).map("".join)

def _make_string():
    return _make_string_body().map(lambda b: '"' + b + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), st.lists(st.sampled_from("0123456789"), max_size=6).map("".join)).map(lambda t: t[0] + t[1]),
        st.integers(min_value=0, max_value=10**18).map(str),
    )

def _frac_part():
    return st.tuples(st.just("."), st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join)).map(lambda t: t[0] + t[1])

def _exp_part():
    return st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=4).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2])

def _make_number():
    base = _int_part()
    with_frac = st.one_of(st.just(""), _frac_part()).map(lambda s: s)
    with_exp = st.one_of(st.just(""), _exp_part()).map(lambda s: s)
    sign = st.sampled_from(["", "-"])
    composed = st.tuples(sign, base, with_frac, with_exp).map(lambda t: t[0] + t[1] + t[2] + t[3])
    # extreme magnitudes and overflow-ish exponents
    extreme = st.one_of(
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-309"),
        st.just("1e9999"),
        st.just("1e-9999"),
        st.just("1E+308"),
        st.just("1E-308"),
        st.just("0e0"),
        st.just("-0"),
        st.just("0.0"),
        st.just("1e01"),
        st.just("1E01"),
        st.just("123456789012345678901234567890"),
        st.just("0.0000000000000000000000001"),
    )
    return st.one_of(composed, extreme)

# ---------- recursive structure ----------

def _make_scalar():
    return st.one_of(
        _make_string(),
        _make_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )

def _join_parts(parts):
    return "".join(parts)

def _make_pair(value_strategy):
    key = _make_string()
    colon = st.sampled_from([":", " : ", ":", ": "])
    return st.tuples(key, colon, value_strategy).map(lambda t: t[0] + t[1] + t[2])

def _make_obj(value_strategy):
    empty = st.just("{}")
    pairs = st.lists(_make_pair(value_strategy), min_size=1, max_size=5)
    sep = st.sampled_from([",", ", ", ",\n", " , "])
    ws = st.sampled_from(["", " ", "\n", "\t"])
    def build(pair_list):
        # note: duplicates are intentional in some cases (parser rejects them)
        return "{" + ws.example() + (sep.example().join(pair_list)) + ws.example() + "}"
    # simpler: build with fixed separators via map on tuple
    def build2(t):
        pair_list, s, w1, w2 = t
        return "{" + w1 + s.join(pair_list) + w2 + "}"
    return st.one_of(
        empty,
        st.tuples(pairs, sep, ws, ws).map(build2),
    )

def _make_arr(value_strategy):
    empty = st.just("[]")
    vals = st.lists(value_strategy, min_size=1, max_size=6)
    sep = st.sampled_from([",", ", ", ",\n", " , "])
    ws = st.sampled_from(["", " ", "\n", "\t"])
    def build(t):
        val_list, s, w1, w2 = t
        return "[" + w1 + s.join(val_list) + w2 + "]"
    return st.one_of(
        empty,
        st.tuples(vals, sep, ws, ws).map(build),
    )

# ---------- malformed / near-valid ----------

def _make_malformed():
    return st.one_of(
        st.just("{"),
        st.just("}"),
        st.just("["),
        st.just("]"),
        st.just("[1,]"),
        st.just("[,1]"),
        st.just("[1,,2]"),
        st.just("{\"a\":}"),
        st.just("{\"a\" 1}"),
        st.just("{\"a\":1,}"),
        st.just("{,}"),
        st.just("{\"a\":1 \"b\":2}"),
        st.just("\"unterminated"),
        st.just("\"unterminated\\"),
        st.just("\"bad\\u12\""),
        st.just("\"bad\\uZZZZ\""),
        st.just("01"),
        st.just("00"),
        st.just("+1"),
        st.just(".5"),
        st.just("1."),
        st.just("-.5"),
        st.just("-"),
        st.just("1e"),
        st.just("1e+"),
        st.just("tru"),
        st.just("fals"),
        st.just("nul"),
        st.just("1abc"),
        st.just("[]xyz"),
        st.just("{\"a\":1}x"),
        st.just("truefalse"),
        st.just("\"a\"\"b\""),
        st.just("\u0000".replace("\u0000", "\\u0000")),  # the escape, not raw NUL
        st.just("{\"a\":1,\"a\":2}"),
        st.just("{\"k\":0,\"k\":1}"),
        st.just("[1 2]"),
        st.just("{\"a\":01}"),
        st.just("\"\\uD800\""),
        st.just("\"\\uDC00\""),
        st.just("\"\\uD800\\uDC00\""),
        st.just("  "),
        st.just(""),
    )

# ---------- deep nesting near cap ----------

def _make_deep():
    # concentrate depth near 2048
    depths = st.one_of(
        st.integers(min_value=0, max_value=8),
        st.integers(min_value=2000, max_value=2050),
        st.integers(min_value=1024, max_value=1030),
        st.just(2047),
        st.just(2048),
        st.just(2049),
    )
    def build(d):
        if d < 0:
            d = 0
        return "[" * d + "0" + "]" * d
    return depths.map(build)

def _make_deep_obj():
    depths = st.one_of(
        st.integers(min_value=0, max_value=6),
        st.integers(min_value=2000, max_value=2050),
        st.just(2047),
        st.just(2048),
        st.just(2049),
    )
    def build(d):
        if d < 0:
            d = 0
        return "{\"a\":" * d + "0" + "}" * d
    return depths.map(build)

# ---------- top-level strategy ----------

_value = st.recursive(
    _make_scalar(),
    lambda children: st.one_of(
        _make_obj(children),
        _make_arr(children),
    ),
    max_leaves=30,
)

# trailing content after a complete value (accepted by parser)
_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("garbage"),
    st.just("abc"),
    st.just("xyz"),
    st.just("//comment"),
    st.just("1"),
)

def _with_trailing(v):
    return st.tuples(st.just(v), _trailing).map(lambda t: t[0] + t[1])

_structured = st.one_of(
    _value,
    _value.flatmap(_with_trailing),
)

# ---------- whitespace / control-char edge cases (new branch coverage) ----------

def _make_whitespace_edges():
    ws = st.sampled_from([" ", "\t", "\n", "\r", "\f", "\b", "\x0b", "\x0c", "\x1f", "\x7f"])
    return st.one_of(
        # leading/trailing/interior whitespace around valid values
        st.tuples(ws, _value, ws).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(ws, ws, _value, ws, ws).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
        # whitespace inside arrays and objects
        st.lists(ws, min_size=1, max_size=4).map(lambda l: "[" + "".join(l) + "1" + "".join(l) + "]"),
        st.lists(ws, min_size=1, max_size=4).map(lambda l: "{" + "".join(l) + "\"a\"" + "".join(l) + ":" + "".join(l) + "1" + "".join(l) + "}"),
        # raw control characters embedded (parser may reject or handle)
        st.just("\x00"),
        st.just("\x01"),
        st.just("\x1f"),
        st.just("\x7f"),
        st.just("\"\x00\""),
        st.just("\"\x01\""),
        st.just("\"\x1f\""),
        st.just("\"\x7f\""),
        st.just("[\x00]"),
        st.just("{\x00}"),
        st.just("\x00" + "1"),
        st.just("1" + "\x00"),
        # BOM and other unicode whitespace
        st.just("\ufeff1"),
        st.just("\ufeff{}"),
        st.just("\u00a01"),
        st.just("\u20281"),
        st.just("\u20291"),
        st.just("\u30001"),
        # vertical tab / form feed as whitespace between tokens
        st.just("[\x0b1]"),
        st.just("[\x0c1]"),
        st.just("{\x0b\"a\":1}"),
        st.just("{\x0c\"a\":1}"),
        # whitespace-only inputs of various lengths
        st.lists(ws, min_size=0, max_size=8).map("".join),
    )

strategy = st.one_of(
    _structured,
    _make_malformed(),
    _make_deep(),
    _make_deep_obj(),
    _make_whitespace_edges(),
)
```