```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helper building blocks
# ---------------------------------------------------------------------------

def _join(parts):
    return lambda t: "".join(t)

# A safe, ordinary string body (no need to be JSON-escaped since we build raw)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in raw text
    blacklist_characters='"\\',
)

def _raw_string_body():
    # Raw (unescaped) content, including control chars and NUL.
    return st.text(
        alphabet=st.one_of(
            _safe_chars,
            st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
        ),
        max_size=12,
    )

def _escape_seq():
    simple = st.sampled_from(
        ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
    )
    hexdigits = "0123456789abcdefABCDEF"
    unicode_esc = st.tuples(
        st.just("\\u"),
        st.text(alphabet=hexdigits, min_size=4, max_size=4),
    ).map("".join)
    # Deliberately include surrogate escapes (\ud800-\udfff)
    surrogate_esc = st.tuples(
        st.just("\\u"),
        st.sampled_from(["d", "D"]),
        st.text(alphabet="89abAB", min_size=1, max_size=1),
        st.text(alphabet=hexdigits, min_size=2, max_size=2),
    ).map("".join)
    return st.one_of(simple, unicode_esc, surrogate_esc)

def _json_string():
    body = st.one_of(
        _raw_string_body(),
        st.lists(st.one_of(_raw_string_body(), _escape_seq()), max_size=6).map(
            lambda parts: "".join(parts)
        ),
    )
    return st.tuples(st.just('"'), body, st.just('"')).map("".join)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _number():
    digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
    int_part = st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), digits).map("".join),
        # leading-zero deviation (accepted by parser)
        st.tuples(st.just("0"), digits).map("".join),
        # hex deviation (accepted by parser)
        st.tuples(st.just("0x"), st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=4)).map("".join),
    )
    sign = st.one_of(st.just(""), st.just("-"))
    frac = st.one_of(
        st.just(""),
        st.tuples(st.just("."), digits).map("".join),
        # trailing dot deviation
        st.just("."),
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.one_of(st.just(""), st.just("+"), st.just("-")),
            digits,
        ).map("".join),
    )
    # extreme magnitudes / overflow
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e999", "1e-999", "9" * 30, "-" + "9" * 30,
        "0e0", "1E+400", "1e-400",
    ])
    composed = st.tuples(sign, int_part, frac, exp).map("".join)
    return st.one_of(composed, extreme)

# ---------------------------------------------------------------------------
# Malformed fragments (near-valid but broken)
# ---------------------------------------------------------------------------

def _malformed():
    return st.sampled_from([
        "",            # empty input
        ",", "[,]", "{,}", "[1,,2]", '{"a":1,,"b":2}',
        "[1,2,]", '{"a":1,}', '{"a" 1}', '{"a":}', '{:1}',
        '"unterminated', "'single'", "{a:1}", "{'a':1}",
        "-", "+1", ".5", "NaN", "Infinity", "-Infinity",
        '["\\ud800"]', '["\\udfff"]',
        "tru", "fals", "nul", "truex", "01", "1.", "0x10",
        "[", "]", "{", "}", ":", "\\",
        '"\\q"', '"\\u12"', '"\\uZZZZ"',
    ])

# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

def _leaf():
    return st.one_of(
        _json_string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _ws():
    return st.text(alphabet=" \t\n\r", max_size=2)

def _value(draw_strategy):
    # draw_strategy is a SearchStrategy for nested values
    leaf = _leaf()

    def make_array(t):
        items = t
        return "[" + ",".join(items) + "]"

    def make_object(pairs):
        return "{" + ",".join(pairs) + "}"

    arr = st.lists(
        st.tuples(_ws(), draw_strategy, _ws()).map(lambda p: p[1]),
        max_size=4,
    ).map(make_array)

    def make_pair(kv):
        k, v = kv
        return k + ":" + v

    obj = st.lists(
        st.tuples(_json_string(), st.just(":"), draw_strategy).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        max_size=4,
    ).map(make_object)

    special = st.sampled_from(["{}", "[]"])

    return st.one_of(leaf, arr, obj, special)

# Depth-controlled recursive generation concentrating near the ~1000 limit.
def _nested(depth):
    # Build a value nested exactly `depth` levels deep using arrays.
    return st.just("[" * depth + "0" + "]" * depth)

def _deep_values():
    # Concentrate interesting depths near the limit.
    return st.one_of(
        st.integers(min_value=0, max_value=50).map(lambda d: "[" * d + "]" * d),
        st.integers(min_value=990, max_value=1010).map(
            lambda d: "[" * d + "0" + "]" * d
        ),
        st.integers(min_value=990, max_value=1010).map(
            lambda d: '{"a":' * d + "0" + "}" * d
        ),
        st.sampled_from([999, 1000, 1001]).map(
            lambda d: "[" * d + "]" * d
        ),
    )

# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

_base = st.recursive(
    _leaf(),
    _value,
    max_leaves=20,
)

_bom = st.one_of(st.just(""), st.just("\ufeff"))

_trailing = st.one_of(
    st.just(""),
    st.sampled_from(["abc", " 2", "\x00", " xyz", "1 2", "\n"]),
)

_valid = st.tuples(_bom, _base, _trailing).map("".join)

_malformed_top = st.tuples(_bom, _malformed()).map("".join)

# ---------------------------------------------------------------------------
# Values tailored to exercise comparison / printing paths.
# These are still valid JSON, but deliberately chosen to be structurally
# similar (so cJSON_Compare recurses deeply) and to contain a wide variety
# of types (so print_* functions are exercised).
# ---------------------------------------------------------------------------

_compare_leaf = st.one_of(
    _json_string(),
    _number(),
    st.sampled_from(["true", "false", "null"]),
)

def _compare_value(depth):
    # Build a value with controlled depth that is structurally rich.
    if depth <= 0:
        return _compare_leaf
    arr = st.lists(_compare_value(depth - 1), max_size=4).map(
        lambda items: "[" + ",".join(items) + "]"
    )
    obj = st.lists(
        st.tuples(_json_string(), st.just(":"), _compare_value(depth - 1)).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        max_size=4,
    ).map(lambda pairs: "{" + ",".join(pairs) + "}")
    return st.one_of(_compare_leaf, arr, obj, st.sampled_from(["{}", "[]"]))

def _compare_pair():
    # Two structurally similar values (often identical) to exercise Compare.
    v = _compare_value(3)
    return st.tuples(v, v).map(lambda p: p[0] + "\n" + p[1])

# A value designed to hit many print_* branches: mixed types, escapes,
# unicode, control characters, numbers of varying magnitude, nested
# containers, and raw-ish strings.
_print_value = st.one_of(
    _compare_value(4),
    st.sampled_from([
        '"\\u0000\\u001f\\u007f"',
        '"\\ud83d\\ude00"',       # valid surrogate pair
        '"\\ud800"',              # lone high surrogate
        '"\\udfff"',              # lone low surrogate
        '"a\\tb\\nc\\rd\\be\\ff"',
        '"\\/slash"',
        '""',
        "0", "-0", "1", "-1", "1.5", "-1.5", "1e10", "1e-10",
        "123456789012345678901234567890",
        "[]", "{}", "[[]]", "[{}]", '{"a":[]}', '{"a":{}}',
        '[1,"two",true,false,null,{},[]]',
        '{"a":1,"b":"two","c":true,"d":false,"e":null,"f":[],"g":{}}',
    ]),
)

# ---------------------------------------------------------------------------
# Structured documents that, when parsed, produce values that are then
# compared and printed via cJSON_Compare / cJSON_Print.  We emit pairs of
# JSON documents separated by a NUL sentinel so the harness can split them.
# ---------------------------------------------------------------------------

def _rich(depth):
    """A structurally rich value with controlled depth."""
    if depth <= 0:
        return _leaf()
    arr = st.lists(_rich(depth - 1), max_size=3).map(
        lambda items: "[" + ",".join(items) + "]"
    )
    obj = st.lists(
        st.tuples(_json_string(), st.just(":"), _rich(depth - 1)).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        max_size=3,
    ).map(lambda pairs: "{" + ",".join(pairs) + "}")
    return st.one_of(_leaf(), arr, obj, st.sampled_from(["{}", "[]"]))

def _print_doc():
    # Single documents crafted to exercise print_value / print_string_ptr /
    # print_number / print_object on every type and nesting shape.
    return st.one_of(
        _rich(3),
        st.sampled_from([
            '"\\u0000\\u0001\\u001f\\u007f\\u0080\\uffff"',
            '"\\ud83d\\ude00"',
            '"\\ud800"',
            '"\\udfff"',
            '"\\ud800\\ud800"',
            '"\\udc00\\ud800"',
            '"a\\tb\\nc\\rd\\be\\ff\\/g\\\\h\\"i"',
            '""',
            "0", "-0", "1", "-1", "1.5", "-1.5",
            "1e10", "1e-10", "1e308", "-1e308", "1e-308",
            "123456789012345678901234567890",
            "4.9406564584124654e-324",
            "1.7976931348623157e308",
            "[]", "{}", "[[]]", "[{}]", "[null]",
            '{"a":[]}', '{"a":{}}', '{"":1}',
            '[1,"two",true,false,null,{},[]]',
            '{"a":1,"b":"two","c":true,"d":false,"e":null,"f":[],"g":{}}',
            '{"a":{"b":{"c":{"d":[1,2,3]}}}}',
            '[[[[[[[[[[1]]]]]]]]]]',
        ]),
    )

def _compare_doc_pair():
    # Two documents intended to be compared with cJSON_Compare.  We bias
    # toward structurally similar pairs, sometimes identical, sometimes
    # differing by a leaf, sometimes differing in length.
    base = _rich(3)
    same = st.tuples(base, base).map(lambda p: p[0] + "\x00" + p[1])
    near = st.tuples(_rich(2), _rich(2)).map(lambda p: p[0] + "\x00" + p[1])
    return st.one_of(same, near)

def _compare_special_pairs():
    return st.sampled_from([
        # identical scalars
        "0\x000", "-0\x000", "1\x001", "true\x00true", "false\x00false",
        "null\x00null", '""\x00""', '"a"\x00"a"',
        # differing scalars
        "1\x002", "0\x001", "true\x00false", "null\x00false",
        '"a"\x00"b"', '"A"\x00"a"', '"a"\x00""',
        # numeric edge comparison (compare_double paths)
        "1\x001.0", "1e10\x0010000000000", "1e-10\x000.0000000001",
        "1e309\x001e309", "-1e309\x001e309",
        "4.9406564584124654e-324\x004.9406564584124654e-324",
        "1.7976931348623157e308\x001.7976931348623157e308",
        # array length mismatch
        "[]\x00[1]", "[1]\x00[]", "[1,2]\x00[1]", "[1]\x00[1,2]",
        # nested structural equality / inequality
        "[1,[2,[3]]]\x00[1,[2,[3]]]",
        "[1,[2,[3]]]\x00[1,[2,[4]]]",
        '{"a":{"b":1}}\x00{"a":{"b":1}}',
        '{"a":{"b":1}}\x00{"a":{"b":2}}',
        # object vs array (type mismatch -> early false)
        "[]\x00{}", "{}\x00[]",
        # object key ordering (should be equal regardless of order)
        '{"a":1,"b":2}\x00{"b":2,"a":1}',
        # object key sets differ
        '{"a":1}\x00{"a":1,"b":2}',
        '{"a":1,"b":2}\x00{"a":1}',
        # string escapes compared after decoding
        '"\\u0041"\x00"A"',
        '"\\n"\x00"\\u000a"',
        '"\\ud83d\\ude00"\x00"\\ud83d\\ude00"',
    ])

# A combined "document mode" strategy: emit a document that the harness can
# parse, print, and compare.  We use \x00 as an internal separator so the
# harness can split; the parser never sees the NUL in a single document.
_structured = st.one_of(
    _print_doc(),
    _compare_doc_pair(),
    _compare_special_pairs(),
)

strategy = st.one_of(
    _valid,
    _malformed_top,
    _deep_values(),
    _compare_pair(),
    _print_value,
    _structured,
)
```