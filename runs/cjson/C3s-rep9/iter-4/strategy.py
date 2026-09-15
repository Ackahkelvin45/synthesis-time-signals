from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Safe code points for strings (no quote, no backslash, no raw control)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes: lone surrogates (rejected) and valid pairs (accepted).
_high_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(
    lambda n: "\\u%04x" % n
)
_low_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)
_surrogate_pair = st.tuples(_high_surrogate, _low_surrogate).map(lambda t: t[0] + t[1])

# Raw control / NUL bytes inside strings (accepted by parser, rejected by strict).
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f"])

_string_piece = st.one_of(
    _safe_char,
    _escapes,
    _unicode_escape,
    _surrogate_pair,
    _high_surrogate,   # lone surrogate -> rejection edge case
    _low_surrogate,    # lone surrogate -> rejection edge case
    _raw_control,      # raw control / NUL inside string
)

# A well-formed JSON string
_string = st.lists(_string_piece, max_size=8).map(lambda parts: '"' + "".join(parts) + '"')

# Malformed strings: unterminated, invalid escapes, single quotes.
_malformed_string = st.one_of(
    _string.map(lambda s: s[:-1]),                          # unterminated
    st.just('"'),
    st.just("'abc'"),                                       # single-quoted
    st.just('"\\x"'),                                       # invalid escape
    st.just('"\\u12"'),                                     # short unicode escape
    st.just('"\\uZZZZ"'),                                   # bad hex
)

# ---------- numbers ----------

# Valid numbers per grammar
_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
)
_frac = st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n))
_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10**3).map(str),
).map(lambda t: t[0] + t[1] + t[2])

_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + fr + ex,
    sign=st.sampled_from(["", "-"]),
    ip=_int_part,
    fr=st.one_of(st.just(""), _frac),
    ex=st.one_of(st.just(""), _exp),
)

# Extreme magnitudes / overflow
_extreme_number = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1e999999"),
    st.just("0.000000000000000000000000000001"),
    st.integers(min_value=-(10**300), max_value=10**300).map(str),
)

# Malformed numbers (rejected by parser)
_malformed_number = st.one_of(
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("00"),
    st.just("1."),        # accepted by parser actually (lenient); keep as edge
    st.just("0x10"),      # accepted by parser (lenient)
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just("1e"),
    st.just("--1"),
    st.just("1..2"),
)

# ---------- recursive JSON values ----------

_json_value = st.recursive(
    st.one_of(
        _string,
        _number,
        _extreme_number,
        _malformed_string,
        _malformed_number,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        # arrays
        st.lists(children, max_size=4).map(
            lambda items: "[" + ",".join(items) + "]"
        ),
        # objects with unique-ish keys
        st.lists(
            st.tuples(_string, children),
            max_size=4,
        ).map(
            lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
        ),
        # duplicate keys
        st.tuples(_string, children, children).map(
            lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
        ),
        # trailing commas (rejected)
        st.lists(children, min_size=1, max_size=3).map(
            lambda items: "[" + ",".join(items) + ",]"
        ),
        # double commas (rejected)
        st.lists(children, min_size=1, max_size=3).map(
            lambda items: "[" + ",".join(items) + ",,]"
        ),
        # missing colon (rejected)
        st.tuples(_string, children).map(
            lambda t: "{" + t[0] + t[1] + "}"
        ),
    ),
    max_leaves=12,
)

# ---------- depth-focused strategies (near the 1000 limit) ----------

def _nested_array(depth):
    return "[" * depth + "0" + "]" * depth

def _nested_object(depth):
    return '{"a":' * depth + "0" + "}" * depth

_depth_near_limit = st.integers(min_value=900, max_value=1001).flatmap(
    lambda d: st.one_of(
        st.just(_nested_array(d)),
        st.just(_nested_object(d)),
    )
)

_depth_far = st.just(_nested_array(2000))

# ---------- structural edge cases (new: hit parser branches never exercised) ----------

# Whitespace variants the parser's skip-whitespace loop may handle specially.
_ws = st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\r\t "])

# Leading/trailing whitespace around values (parser whitespace-skip branches).
_ws_wrapped = st.tuples(_ws, _json_value, _ws).map(
    lambda t: t[0] + t[1] + t[2]
)

# Empty objects/arrays with interior whitespace (empty-container branches).
_empty_ws = st.one_of(
    st.tuples(_ws, _ws).map(lambda t: "{" + t[0] + t[1] + "}"),
    st.tuples(_ws, _ws).map(lambda t: "[" + t[0] + t[1] + "]"),
)

# Objects/arrays with whitespace around separators (separator-skip branches).
_ws_separated = st.one_of(
    st.tuples(_string, _ws, _json_value).map(
        lambda t: "{" + t[0] + t[1] + ":" + t[2] + "}"
    ),
    st.tuples(_json_value, _ws, _json_value).map(
        lambda t: "[" + t[0] + t[1] + "," + t[2] + "]"
    ),
    st.tuples(_string, _ws, _json_value, _ws, _string, _ws, _json_value).map(
        lambda t: "{" + t[0] + t[1] + ":" + t[2] + "," + t[4] + t[5] + ":" + t[6] + "}"
    ),
)

# Truncated / partial inputs that terminate mid-token (EOF-in-token branches).
_truncated = st.one_of(
    st.just("{"),
    st.just("["),
    st.just('{"a"'),
    st.just('{"a":'),
    st.just('{"a":1'),
    st.just("[1"),
    st.just("[1,"),
    st.just('"abc'),
    st.just("tru"),
    st.just("fals"),
    st.just("nul"),
    st.just("-"),
    st.just("1e"),
    st.just("1e+"),
    st.just("1."),
    st.just("\\"),
    st.just("\\u"),
    st.just("\\u12"),
)

# Keywords with trailing garbage (keyword-parse branch).
_keyword_edge = st.one_of(
    st.just("truex"),
    st.just("falsey"),
    st.just("nullz"),
    st.just("truE"),
    st.just("TRUE"),
    st.just("Null"),
)

# Deeply nested alternating structures (recursion branches beyond arrays/objects).
def _nested_mixed(depth):
    s = "0"
    for i in range(depth):
        s = "[" + s + "]" if i % 2 == 0 else '{"k":' + s + "}"
    return s

_nested_mixed_edge = st.integers(min_value=1, max_value=50).map(_nested_mixed)

# ---------- top-level ----------

_top = st.one_of(
    _json_value,
    # empty containers
    st.just("{}"),
    st.just("[]"),
    # BOM prefix (accepted)
    _json_value.map(lambda s: "\ufeff" + s),
    # trailing content after a valid value (accepted, ignored)
    st.tuples(_json_value, st.just("abc")).map(lambda t: t[0] + t[1]),
    st.tuples(_json_value, st.just(" 1 2")).map(lambda t: t[0] + t[1]),
    # raw NUL after a value
    st.tuples(_json_value, st.just("\x00")).map(lambda t: t[0] + t[1]),
    # depth edge cases
    _depth_near_limit,
    _depth_far,
    # empty input / whitespace only (rejected)
    st.just(""),
    st.just("   "),
    st.just("\n\t"),
    # lone punctuation
    st.sampled_from(["{", "}", "[", "]", ",", ":", '"']),
    # new structural edge cases
    _ws_wrapped,
    _empty_ws,
    _ws_separated,
    _truncated,
    _keyword_edge,
    _nested_mixed_edge,
)

strategy = _top