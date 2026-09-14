from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

def _unicode_escape():
    return st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet=_hex, min_size=4, max_size=4),
    )

def _surrogate_escape():
    return st.sampled_from(
        ["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\uD800", "\\uDC00", "\\u0000", "\\uffff"]
    )

def _simple_escape():
    return st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _safe_char():
    # SAFECODEPOINT: anything except " \ and control 0x00-0x1F
    return st.characters(
        blacklist_characters=' "\\',
        blacklist_categories=("Cs",),
        min_codepoint=0x20,
    )

def _raw_control():
    # raw control bytes / NUL — allowed in output, parser sees them faithfully
    return st.sampled_from(["\x00", "\x01", "\x1f", "\x0b", "\x0c", "\x7f"])

def _string_body_piece():
    return st.one_of(
        _safe_char(),
        _simple_escape(),
        _unicode_escape(),
        _surrogate_escape(),
        _raw_control(),
    )

def _string():
    return st.builds(
        lambda parts: '"' + "".join(parts) + '"',
        st.lists(_string_body_piece(), max_size=12),
    )

def _unterminated_string():
    return st.builds(
        lambda parts: '"' + "".join(parts),
        st.lists(_string_body_piece(), min_size=1, max_size=8),
    )

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.builds(
            lambda d, rest: d + rest,
            st.integers(min_value=1, max_value=9).map(str),
            st.text(alphabet="0123456789", max_size=6),
        ),
        st.text(alphabet="0123456789", min_size=1, max_size=8),  # leading zeros (malformed)
    )

def _number():
    intpart = _int_part()
    frac = st.one_of(
        st.just(""),
        st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=8)),
        st.just("."),  # trailing dot (malformed)
        st.builds(lambda d: "." + d, st.text(alphabet="0123456789", max_size=8)),
    )
    exp = st.one_of(
        st.just(""),
        st.builds(
            lambda e, s, d: e + s + d,
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.text(alphabet="0123456789", min_size=1, max_size=4),
        ),
    )
    sign = st.sampled_from(["", "-"])
    return st.builds(
        lambda s, i, f, e: s + i + f + e,
        sign, intpart, frac, exp,
    )

def _extreme_number():
    return st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e999", "-1e999",
        "1e308", "1.7976931348623157e308", "5e-324",
        "0", "-0", "0.0", "-0.0",
        "1e01", "1E+01", "1e-01",
        "999999999999999999999999999999",
        "0.000000000000000000000000001",
        "-",  # lone minus (accepted by parser)
        "1.", ".5", "+1", "01", "0x1F",  # malformed forms
    ])

# ---------- recursive value/obj/arr ----------

def _value(depth):
    return st.one_of(
        _string(),
        _number(),
        _extreme_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _obj(depth),
        _arr(depth),
    )

def _pair(depth):
    key = st.one_of(_string(), _extreme_number())
    return st.builds(
        lambda k, v: k + ":" + v,
        key,
        _value(depth),
    )

def _obj(depth):
    # bias toward objects with members
    members = st.lists(_pair(depth), min_size=0, max_size=5)
    trailing = st.booleans()
    def build(pairs, tr):
        if not pairs:
            return "{}"
        body = ",".join(pairs)
        if tr:
            body += ","
        return "{" + body + "}"
    return st.builds(build, members, trailing)

def _arr(depth):
    elems = st.lists(_value(depth), min_size=0, max_size=5)
    trailing = st.booleans()
    def build(items, tr):
        if not items:
            return "[]"
        body = ",".join(items)
        if tr:
            body += ","
        return "[" + body + "]"
    return st.builds(build, elems, trailing)

# ---------- malformed near-valid ----------

def _malformed():
    return st.sampled_from([
        "[,]", "[,1]", "[1,,2]", "[1 2]", "[1 2,3]",
        "{,}", "{a:1}", '{"a" 1}', '{"a":}', '{"a":1,,"b":2}',
        '{"a":1 "b":2}', '{"a"::1}', '"unterminated', '{', '[', '}',
        ']', '{"a":1', '[1,2', 'true false', '1abc', '[]xyz',
        '1 garbage', 'null null', '{"a":}', '"\\u12"', '"\\uZZZZ"',
        '"\\x"', '"\\"', "'x'", "//x", "/* */1", "\x00", "\x00{}",
        '{"a":\x001}', '[\x00]', '{"\x00":1}',
    ])

# ---------- deep nesting ----------

def _deep_object(depth):
    # nested objects like {"a":{"a":{...}}}
    return st.builds(
        lambda d: '{"a":' * d + "1" + "}" * d,
        st.integers(min_value=0, max_value=30),
    )

def _deep_array(depth):
    return st.builds(
        lambda d: "[" * d + "1" + "]" * d,
        st.integers(min_value=0, max_value=60),
    )

# ---------- top-level strategy ----------

def _json_value():
    # use recursive to allow arbitrary depth
    return st.recursive(
        st.one_of(
            _string(),
            _number(),
            _extreme_number(),
            st.just("true"),
            st.just("false"),
            st.just("null"),
        ),
        lambda children: st.one_of(
            st.builds(
                lambda items, tr: "[" + ",".join(items) + ("," if tr and items else "") + "]",
                st.lists(children, max_size=4),
                st.booleans(),
            ),
            st.builds(
                lambda pairs, tr: "{" + ",".join(pairs) + ("," if tr and pairs else "") + "}",
                st.lists(
                    st.builds(
                        lambda k, v: k + ":" + v,
                        st.one_of(_string(), _extreme_number()),
                        children,
                    ),
                    max_size=4,
                ),
                st.booleans(),
            ),
        ),
        max_leaves=20,
    )

strategy = st.one_of(
    _json_value(),
    _malformed(),
    _deep_object(0),
    _deep_array(0),
    _extreme_number(),
    _unterminated_string(),
)