import json
from hypothesis import strategies as st

# ---------- helpers ----------

_WS_CHARS = " \t\n\r"

def _ws():
    return st.text(alphabet=_WS_CHARS, min_size=0, max_size=3)

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _escape():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    unicode_esc = st.builds(lambda h: "\\u" + h, _hex4())
    # lone surrogates and other weird \u values
    weird = st.builds(lambda h: "\\u" + h, _hex4())
    return st.one_of(simple, unicode_esc, weird)

def _safe_codepoint():
    # printable-ish plus control bytes and NUL allowed (parser takes explicit length)
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                      blacklist_categories=("Cs",), blacklist_characters='"\\'),
        st.characters(min_codepoint=0x00, max_codepoint=0x1F),
        st.just("\x00"),
        st.just("\x7f"),
    )

def _string_body_char():
    return st.one_of(_escape(), _safe_codepoint())

def _string_content():
    return st.lists(_string_body_char(), min_size=0, max_size=8).map("".join)

def _string():
    return _string_content().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_DIGITS = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        _DIGITS.filter(lambda d: d[0] != "0"),
        # near-valid: leading zeros
        st.text(alphabet="0123456789", min_size=2, max_size=6).filter(lambda d: d[0] == "0"),
    )

def _frac_part():
    return st.one_of(
        st.just(""),
        _DIGITS.map(lambda d: "." + d),
        st.just("."),  # near-valid trailing dot
    )

def _exp_part():
    sign = st.sampled_from(["", "+", "-"])
    digits = st.text(alphabet="0123456789", min_size=1, max_size=4)
    return st.builds(lambda s, d: "e" + s + d, sign, digits)

def _number():
    sign = st.sampled_from(["", "-", "+"])  # leading + is near-valid
    intp = st.one_of(_int_part(), st.just(""))  # empty for near-valid forms
    frac = _frac_part()
    exp = st.one_of(st.just(""), _exp_part())
    base = st.tuples(sign, intp, frac, exp).map(lambda t: "".join(t))
    # extreme magnitudes
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e-999", "1E+308", "1e308", "9" * 40,
        "-" + "9" * 40, "0.0000000000000000001e400", "1e1000000",
    ])
    lone_minus = st.just("-")
    leading_dot = st.builds(lambda d: "." + d, _DIGITS)
    return st.one_of(base, extreme, lone_minus, leading_dot)

# ---------- recursive values ----------

_VALUE_STRATEGY = None
_OBJ_STRATEGY = None
_ARR_STRATEGY = None

def _value_st():
    return _VALUE_STRATEGY

def _value_st_impl():
    return st.one_of(
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _string(),
        _number(),
        _OBJ_STRATEGY,
        _ARR_STRATEGY,
    )

def _obj_st():
    return _OBJ_STRATEGY

def _obj_st_impl():
    return st.recursive(
        st.one_of(
            st.just("{}"),
            st.builds(lambda k, v: "{" + k + ":" + v + "}",
                      _string(), _value_st()),
            st.builds(lambda k1, v1, k2, v2: "{" + k1 + ":" + v1 + "," + k2 + ":" + v2 + "}",
                      _string(), _value_st(), _string(), _value_st()),
        ),
        lambda children: st.one_of(
            st.builds(lambda cs: "{" + ",".join(cs) + "}", st.lists(children, min_size=1, max_size=4)),
            st.builds(lambda cs: "{" + ",".join(cs) + ",}", st.lists(children, min_size=1, max_size=4)),
            st.builds(lambda k, c: "{" + k + ":" + c + "}", _string(), children),
        ),
        max_leaves=20,
    )

def _arr_st():
    return _ARR_STRATEGY

def _arr_st_impl():
    return st.recursive(
        st.one_of(
            st.just("[]"),
            st.builds(lambda v: "[" + v + "]", _value_st()),
            st.builds(lambda v1, v2: "[" + v1 + "," + v2 + "]", _value_st(), _value_st()),
        ),
        lambda children: st.one_of(
            st.builds(lambda cs: "[" + ",".join(cs) + "]", st.lists(children, min_size=1, max_size=4)),
            st.builds(lambda cs: "[" + ",".join(cs) + ",]", st.lists(children, min_size=1, max_size=4)),
        ),
        max_leaves=20,
    )

# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        # double commas
        st.sampled_from([
            "[1,,2]", "[,]", "[,1]", "[1,,]", "{,}", '{"a":1,,}',
            '{"a":1,,,"b":2}', "[,,,]", "[1,2,,3]",
        ]),
        # missing colons
        st.sampled_from([
            '{"a" 1}', '{"a"}', '{"a":}', '{:1}', '{"a":1,"b"}',
        ]),
        # unterminated strings
        st.sampled_from([
            '"abc', '{"a:1}', '["abc]', '"\\', '"\\u12', '"\\uZZZZ"',
        ]),
        # bad number forms
        st.sampled_from([
            "+1", ".5", "1.", "01", "0x1F", "1abc", "00", "- 1", "1e", "1e+",
            "1.2.3", "--1", "+-1", "0.e1",
        ]),
        # trailing garbage
        st.sampled_from([
            "1 garbage", "[]xyz", "true false", "{} {}", "null null",
            "1 2", '"a" "b"',
        ]),
        # bare keys / single quotes / comments
        st.sampled_from([
            "{a:1}", "'x'", "//x", "/* */1", "{'a':1}",
        ]),
        # unterminated containers
        st.sampled_from([
            "{", "[", "{[", "[{", '{"a":', "[1,", '{"a":1',
        ]),
        # stray closers
        st.sampled_from([
            "}", "]", "]", "]", "}}", "][",
        ]),
    )

# ---------- deep nesting ----------

def _deep_nesting():
    depth = st.integers(min_value=50, max_value=3000)
    kind = st.sampled_from(["[", "{"])
    def build(d, k):
        if k == "[":
            return "[" * d + "]" * d
        else:
            # deep object nesting: {"a":{"a":...null...}}
            inner = "null"
            return '{"a":' * d + inner + "}" * d
    return st.builds(build, depth, kind)

# ---------- top-level ----------

def _top_level():
    ws_l = _ws()
    ws_r = _ws()
    body = st.one_of(
        _value_st(),
        _malformed(),
        _deep_nesting(),
        st.just(""),
        st.just(" "),
        st.just("\x00"),
        st.just("\x00\x00\x00"),
    )
    return st.tuples(ws_l, body, ws_r).map(lambda t: t[0] + t[1] + t[2])

# Build the mutually recursive strategies eagerly, once, to avoid
# unbounded recursion during generation.
_OBJ_STRATEGY = _obj_st_impl()
_ARR_STRATEGY = _arr_st_impl()
_VALUE_STRATEGY = _value_st_impl()

strategy = _top_level()