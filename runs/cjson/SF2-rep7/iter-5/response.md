```python
import json
from hypothesis import strategies as st

# ---------- scalar / leaf strategies ----------

_num_int = st.one_of(
    st.integers(min_value=-(10**30), max_value=10**30),
    st.integers(min_value=-(2**63), max_value=2**63),
    st.sampled_from([0, -0, 1, -1, 10, 100, 1000]),
)

_num_str = st.one_of(
    _num_int.map(str),
    st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e308", "-1e308",
        "1E+400", "1e-400", "0e0", "0e999", "1e01",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "5e-324",
    ]),
    st.sampled_from(["01", "-01", "007", "00", "1.", "0.", "-1.", "0x10", "0xFF", "-0x1a"]),
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
)

_hex = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_unicode_escape = st.one_of(
    _hex.map(lambda h: "\\u" + h),
    st.sampled_from([
        "\\ud800", "\\udfff", "\\ud83d\\ude00", "\\u0000",
        "\\uD834\\uDD1E", "\\uFFFF", "\\u00e9", "\\u2603",
    ]),
)

_simple_escape = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

_string_body_piece = st.one_of(
    _safe_char,
    _simple_escape,
    _unicode_escape,
    _raw_control,
    st.sampled_from(["\x00", "\x1f", "\x7f", "\ufeff"]),
)

_string_body = st.lists(_string_body_piece, max_size=12).map("".join)

_quoted_string = _string_body.map(lambda s: '"' + s + '"')

_malformed_string = st.one_of(
    _string_body.map(lambda s: '"' + s),
    _string_body.map(lambda s: '"' + s + "'"),
    st.sampled_from(['"\\x"', '"\\u12"', '"\\uZZZZ"', '"', "'abc'"]),
)

_leaf = st.one_of(
    _quoted_string,
    _malformed_string,
    _num_str,
    st.sampled_from(["true", "false", "null", "NaN", "Infinity", "-Infinity"]),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

def _pair(value):
    key = st.one_of(_quoted_string, _string_body.map(lambda s: '"' + s + '"'))
    colon = st.sampled_from([":", ":", " :", ": ", " : "])
    return st.tuples(key, colon, value).map(lambda t: t[0] + t[1] + t[2])

def _bad_pair(value):
    return st.one_of(
        st.tuples(_quoted_string, value).map(lambda t: t[0] + t[1]),
        st.tuples(_quoted_string, value).map(lambda t: t[0] + "::" + t[1]),
        value.map(lambda v: ": " + v),
    )

def _obj(value):
    inner = st.one_of(
        st.lists(_pair(value), min_size=0, max_size=4).map(
            lambda ps: ",".join(ps)
        ),
        st.tuples(_pair(value), _pair(value)).map(lambda t: t[0] + "," + t[1]),
    )
    bracketed = st.tuples(
        st.just("{"), _ws, inner, _ws, st.just("}")
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])
    malformed = st.one_of(
        st.tuples(st.just("{"), inner).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("{"), inner, st.just(",}")).map(lambda t: t[0] + t[1] + t[2]),
        st.just("{}"),
        st.just("{,}"),
        st.just("{:}"),
    )
    return st.one_of(bracketed, malformed)

def _arr(value):
    inner = st.lists(value, min_size=0, max_size=4).map(
        lambda vs: ",".join(vs)
    )
    bracketed = st.tuples(
        st.just("["), _ws, inner, _ws, st.just("]")
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])
    malformed = st.one_of(
        st.tuples(st.just("["), inner).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("["), inner, st.just(",]")).map(lambda t: t[0] + t[1] + t[2]),
        st.just("[]"),
        st.just("[,]"),
        st.just("[1,]"),
        st.just("[1,,2]"),
    )
    return st.one_of(bracketed, malformed)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=20,
)

def _deep_array(depth):
    return "[" * depth + "0" + "]" * depth

def _deep_object(depth):
    return '{"a":' * depth + "0" + "}" * depth

_depth_strategy = st.one_of(
    st.integers(min_value=990, max_value=1010),
    st.integers(min_value=0, max_value=50),
    st.sampled_from([500, 999, 1000, 1001, 1002]),
)

_deep = st.one_of(
    _depth_strategy.map(_deep_array),
    _depth_strategy.map(_deep_object),
)

_malformed = st.one_of(
    st.sampled_from([
        "", " ", "\n", "\t",
        "-", "+1", ".5", "-.5", "+.5",
        "01", "1.", "0x10",
        "NaN", "Infinity", "-Infinity",
        "[1,]", "[,]", "{,}", "{:}", "{'a':1}",
        "{a:1}", "['a']", "'abc'",
        '"\\ud800"', '"\\udfff"', '"\\u12"', '"\\uZZZZ"',
        '"\\x"', '"unterminated', '"',
        "[", "]", "{", "}", "[1", "{1", "{\"a\"", "{\"a\":",
        "tru", "fals", "nul", "truex", "falsey", "nullz",
        "\ufeff", "\ufeff1", "\ufeff{}",
        "\x00", "\x001", "1\x00", "\x00\x00",
    ]),
    st.tuples(_value, st.sampled_from(["abc", " 1 2", "\x00", "xyz", "{}[]"])).map(
        lambda t: t[0] + t[1]
    ),
    st.just('{"a":1,,"b":2}'),
    st.just('{"a" 1}'),
    st.just('{"a":1 "b":2}'),
    st.just("[1,,2]"),
    st.just('{"a":1,}'),
)

def _deep_mixed(depth):
    return "".join(
        ('{"a":[' if i % 2 else "[") for i in range(depth)
    ) + "0" + "".join(
        ("]}" if i % 2 else "]") for i in reversed(range(depth))
    )

_deep_mixed_strategy = _depth_strategy.map(_deep_mixed)

_ws_heavy = st.tuples(
    st.just("{"),
    st.just('"k"'),
    st.sampled_from([":", " :", ": ", " :\n", ":\t"]),
    st.just("1"),
    st.just(","),
    st.just('"j"'),
    st.sampled_from([":", " :", ": ", ": \n"]),
    st.just("2"),
    st.just("}"),
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5] + t[6] + t[7] + t[8])

_ws_heavy_arr = st.tuples(
    st.just("["),
    st.just("1"),
    st.sampled_from([",", " ,", ", ", " ,\n", ",\t"]),
    st.just("2"),
    st.just(","),
    st.just("3"),
    st.just("]"),
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5] + t[6])

_mutator = st.sampled_from([
    lambda s: s + ",",
    lambda s: s + ":",
    lambda s: s + "}",
    lambda s: s + "]",
    lambda s: "{" + s,
    lambda s: "[" + s,
    lambda s: s.replace(",", ",,", 1),
    lambda s: s.replace(":", "::", 1),
    lambda s: s.replace('"', "", 1),
    lambda s: s[:-1] if s else s,
    lambda s: s[1:] if s else s,
    lambda s: s[: len(s) // 2] + "," + s[len(s) // 2:] if s else s,
    lambda s: s[: len(s) // 2] + "\x00" + s[len(s) // 2:] if s else s,
])

_mutated = st.tuples(_value, _mutator).map(lambda t: t[1](t[0]))

_ws_inserted = st.tuples(_value, _ws).map(lambda t: t[0][:1] + t[1] + t[0][1:] if t[0] else t[0])

_resync_seed = st.sampled_from([
    '{"a":1', '[1,2', '{"a"', '[', '{',
    '"abc', '1', 'true', 'null',
])

_resync_suffix = st.sampled_from([
    ', "b":2}', ',3]', '}', ']', ',"c":3}', ',4]',
    ' 1', ' "x"', ' true', ' null',
])

_resync = st.tuples(_resync_seed, _resync_suffix).map(lambda t: t[0] + t[1])

def _truncate(s):
    if not s:
        return s
    n = min(len(s), 1 + (len(s) // 3))
    return s[:n]

_truncated = _value.map(_truncate)

# ---------- NEW: token-level error-recovery probes ----------
# Insert a single invalid token at a structural boundary inside an otherwise
# valid value. This drives the parser's error-reporting and resync paths at
# every grammar position (after key, after colon, after value, after comma),
# which the current coverage feedback shows are still under-exercised.
_bad_token = st.sampled_from([
    ":", ",", "]", "}", "@", "#", "&", "*", "$", "%", "!", "?",
    "\x00", "\x01", "\x7f", "\\", "'", "`", "~", "^", "|",
    "truex", "nul", "01", "0x", "1.2.3", "e5", "--", "++",
])

_structural_spot = st.sampled_from([
    # (prefix, suffix) around which the bad token is injected
    ('{"a"', ':1}'),
    ('{"a":', '}'),
    ('{"a":1', '}'),
    ('{"a":1,', '"b":2}'),
    ('[1', ']'),
    ('[1,', '2]'),
    ('[', '1]'),
    ('{"a":1}', ''),
    ('[1,2]', ''),
    ('"', '"'),
])

_token_probe = st.tuples(_structural_spot, _bad_token).map(
    lambda t: t[0][0] + t[1] + t[0][1]
)

# Valid value with a bad token spliced in at a random interior position,
# to hit recovery at arbitrary nesting depths.
def _splice(s, tok):
    if not s:
        return tok
    i = len(s) // 2
    return s[:i] + tok + s[i:]

_spliced = st.tuples(_value, _bad_token).map(lambda t: _splice(t[0], t[1]))

strategy = st.one_of(
    _value,
    _deep,
    _deep_mixed_strategy,
    _ws_heavy,
    _ws_heavy_arr,
    _malformed,
    _mutated,
    _ws_inserted,
    _resync,
    _truncated,
    _value.map(lambda v: "\ufeff" + v),
    _value.map(lambda v: v[: len(v) // 2] + "\x00" + v[len(v) // 2:]),
    _token_probe,
    _spliced,
)
```