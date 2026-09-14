```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Safe string characters (no raw NUL, no unescaped control chars, no quote/backslash)
_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\u0000"\\',
)

_ESCAPES = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_HEX = st.sampled_from("0123456789abcdefABCDEF")
_HEX4 = st.tuples(*([_HEX] * 4)).map("".join)


def _unicode_escape():
    return _HEX4.map(lambda h: "\\u" + h)


# Surrogate escapes (lone and paired) — valid text, potentially tricky
_SURROGATE_ESC = st.sampled_from(
    ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
     "\\uD800\\uDC00", "\\uDBFF\\uDFFF", "\\uD800\\uD800"]
)

# Escapes that produce NUL / control chars as text (six-char escape, not raw byte)
_NUL_ESC = st.just("\\u0000")
_CTRL_ESC = st.sampled_from(
    ["\\u0001", "\\u001F", "\\u0007", "\\u000B", "\\u000C", "\\u001B"]
)


def _string_body():
    """Content between the quotes of a JSON string (no surrounding quotes)."""
    return st.one_of(
        st.lists(
            st.one_of(
                _SAFE,
                _ESCAPES,
                _unicode_escape(),
                _SURROGATE_ESC,
                _NUL_ESC,
                _CTRL_ESC,
            ),
            max_size=12,
        ).map("".join),
    )


def _quoted_string():
    return _string_body().map(lambda s: '"' + s + '"')


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
)

_EXP = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(e)),
)

_FRAC = st.integers(min_value=0, max_value=10**12).map(lambda f: "." + str(f))


def _number():
    return st.one_of(
        # plain ints
        _INT,
        # negative ints
        _INT.map(lambda s: "-" + s),
        # fractional
        st.tuples(_INT, _FRAC).map(lambda t: t[0] + t[1]),
        st.tuples(_INT, _FRAC).map(lambda t: "-" + t[0] + t[1]),
        # exponents
        st.tuples(_INT, _EXP).map(lambda t: t[0] + t[1]),
        st.tuples(_INT, _FRAC, _EXP).map(lambda t: t[0] + t[1] + t[2]),
        # extreme magnitudes / overflow-ish
        st.sampled_from([
            "1e309", "-1e309", "1e-309", "1e308", "1e-308",
            "9" * 30, "-" + "9" * 30,
            "1" + "0" * 300, "1e" + "9" * 5,
            "0.0000000000000000000000000001",
            "123456789012345678901234567890.123456789",
        ]),
        # lenient / near-valid number forms (parser may accept)
        st.sampled_from(["-", "-.", ".5", "1.", "+1", "01", "-01", "007"]),
    )


# ---------------------------------------------------------------------------
# Malformed fragments
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from([
    '{"a":}', '{"a"}', '{:1}', '{,}', '[,]', '[1,,2]', '[1 2]',
    '{"a":1,}', '[1,]', '"unterminated', '{"a":"x', '{',
    '[', '}', ']', ':', ',', 'tru', 'fals', 'nul', 'True', 'NULL',
    '{"a":1"b":2}', '{"a" 1}', '[1,2,3', '{"a":1}}', '[[[]]',
    '"\\x"', '"\\u12"', '"\\uZZZZ"', '{"a":+1}', '{"a":.5}',
    '{"a":01}', "'single'", '{a:1}', '{"a":1,,"b":2}',
])


# ---------------------------------------------------------------------------
# Recursive JSON value
# ---------------------------------------------------------------------------

def _leaf():
    return st.one_of(
        _quoted_string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _MALFORMED,
    )


def _value():
    return st.recursive(
        _leaf(),
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(
                st.tuples(_quoted_string(), children),
                max_size=4,
            ).map(
                lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
            ),
        ),
        max_leaves=30,
    )


# ---------------------------------------------------------------------------
# Depth-targeted builders (near the 2048 cap)
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "0" + "]" * depth


def _deep_object(depth):
    return '{"a":' * depth + "0" + "}" * depth


def _deep_arrays():
    return st.one_of(
        st.integers(min_value=1, max_value=50),
        st.integers(min_value=2000, max_value=2050),
        st.sampled_from([2047, 2048, 2049, 2050, 2100, 3000]),
    ).map(_deep_array)


def _deep_objects():
    return st.one_of(
        st.integers(min_value=1, max_value=50),
        st.integers(min_value=2000, max_value=2050),
        st.sampled_from([2047, 2048, 2049, 2050, 2100]),
    ).map(_deep_object)


# ---------------------------------------------------------------------------
# Duplicate-key objects
# ---------------------------------------------------------------------------

def _dup_keys():
    return st.tuples(
        _quoted_string(),
        _leaf(),
        _leaf(),
    ).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}")


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

_WHITESPACE = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  "])

_TRAILING = st.sampled_from([
    "", " ", "x", "abc", "garbage", "[]xyz", "1abc", "\n\t", "null",
])


def _with_trailing(base):
    return st.tuples(base, _TRAILING).map(lambda t: t[0] + t[1])


def _with_ws(base):
    return st.tuples(_WHITESPACE, base, _WHITESPACE).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _empty_containers():
    return st.sampled_from(["{}", "[]", "{ }", "[ ]", "{\n}", "[\t]"])


# ---------------------------------------------------------------------------
# Serialization-targeted inputs (exercise json_serialize_string)
# ---------------------------------------------------------------------------

# Strings designed to force the serializer's escape/UTF-8 paths: control
# chars, quotes, backslashes, non-ASCII, and multi-byte UTF-8 boundaries.
_SERIALIZE_STRINGS = st.one_of(
    # control characters (0x00-0x1F) that must be escaped on serialize
    st.lists(
        st.integers(min_value=0, max_value=0x1F).map(chr),
        min_size=1,
        max_size=8,
    ).map("".join),
    # quote and backslash runs
    st.lists(
        st.sampled_from(['"', "\\", "/", "\b", "\f", "\n", "\r", "\t"]),
        min_size=1,
        max_size=8,
    ).map("".join),
    # non-ASCII / multi-byte UTF-8 boundary code points
    st.lists(
        st.sampled_from([
            "\u007f", "\u0080", "\u07ff", "\u0800", "\uffff",
            "\U00010000", "\U0010ffff", "\u00e9", "\u20ac", "\u4e2d",
            "\U0001f600", "\u2028", "\u2029",
        ]),
        min_size=1,
        max_size=6,
    ).map("".join),
    # mixed content
    st.lists(
        st.one_of(
            _SAFE,
            _ESCAPES,
            _unicode_escape(),
            st.integers(min_value=0, max_value=0x1F).map(chr),
            st.sampled_from(['"', "\\", "\u2028", "\u2029", "\U0001f600"]),
        ),
        min_size=1,
        max_size=10,
    ).map("".join),
    # long strings to exercise buffer growth
    st.integers(min_value=64, max_value=4096).map(lambda n: "a" * n),
    st.integers(min_value=64, max_value=4096).map(lambda n: "\n" * n),
)


def _serialize_doc():
    """Valid JSON documents containing strings, for serialize round-trips."""
    key = _quoted_string()
    val = st.one_of(
        _SERIALIZE_STRINGS.map(lambda s: json.dumps(s)),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )
    return st.one_of(
        # bare string document
        _SERIALIZE_STRINGS.map(lambda s: json.dumps(s)),
        # object with serializable string values
        st.lists(st.tuples(key, val), min_size=1, max_size=6).map(
            lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
        ),
        # array of serializable strings
        st.lists(val, min_size=1, max_size=6).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
    )


# ---------------------------------------------------------------------------
# Dedicated serializer-argument strings (cover json_serialize_string)
# ---------------------------------------------------------------------------

# These are passed as the *value* of a valid JSON document. They are chosen
# so that when the parser stores them and the serializer emits them, the
# escape/UTF-8 branches of json_serialize_string are all exercised: plain
# ASCII, escaped control chars, quotes, backslashes, and multi-byte UTF-8.
_SERIALIZE_STRING_ARGS = st.one_of(
    st.sampled_from([
        "", "a", "abc",
        '"', '\\', "/", "\b", "\f", "\n", "\r", "\t",
        '"\\', '\\"', "a\"b", "a\\b", "a/b",
        "\u0000", "\u0001", "\u001f", "\u007f",
        "\u0080", "\u07ff", "\u0800", "\uffff",
        "\u00e9", "\u20ac", "\u4e2d", "\u2028", "\u2029",
        "\U00010000", "\U0001f600", "\U0010ffff",
        "line1\nline2", "tab\there", "quote\"inside",
        "back\\slash", "mixed\u00e9\U0001f600\"\\\n",
    ]),
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=32),
    st.lists(
        st.one_of(
            st.integers(min_value=0, max_value=0x1F).map(chr),
            st.sampled_from(['"', "\\", "/", "\b", "\f", "\n", "\r", "\t"]),
            _SAFE,
        ),
        min_size=1,
        max_size=16,
    ).map("".join),
    st.integers(min_value=1, max_value=512).map(lambda n: "x" * n),
    st.integers(min_value=1, max_value=512).map(lambda n: "\u00e9" * n),
)


def _serialize_string_doc():
    """Valid JSON documents whose string values target json_serialize_string."""
    return st.one_of(
        # bare string value (top-level string)
        _SERIALIZE_STRING_ARGS.map(lambda s: json.dumps(s)),
        # string nested in an array
        st.lists(_SERIALIZE_STRING_ARGS, min_size=1, max_size=4).map(
            lambda xs: "[" + ",".join(json.dumps(x) for x in xs) + "]"
        ),
        # string values inside an object
        st.lists(
            st.tuples(_quoted_string(), _SERIALIZE_STRING_ARGS),
            min_size=1,
            max_size=4,
        ).map(
            lambda pairs: "{"
            + ",".join(k + ":" + json.dumps(v) for k, v in pairs)
            + "}"
        ),
    )


# ---------------------------------------------------------------------------
# json_serialize_string coverage: drive it via the library's own serialize
# entry point. The C parser's serialize path is exercised by feeding valid
# documents whose string values span every escape/UTF-8 branch. We also
# emit the serializer's own output back as input, so that round-tripping
# re-enters json_serialize_string with already-escaped content.
# ---------------------------------------------------------------------------

def _serialize_roundtrip():
    """Documents built from json.dumps output, ensuring the serializer path
    (json_serialize_string) is hit for every string value, including
    already-escaped forms produced by the serializer itself."""
    def _escaped(s):
        return json.dumps(s)

    def _double_escaped(s):
        # feed the serializer's own escape output back in as a JSON string
        return json.dumps(_escaped(s))

    return st.one_of(
        # every branch of the escape switch, as string values
        st.sampled_from([
            json.dumps('"'), json.dumps('\\'), json.dumps('/'),
            json.dumps('\b'), json.dumps('\f'), json.dumps('\n'),
            json.dumps('\r'), json.dumps('\t'),
            json.dumps('\u0000'), json.dumps('\u0001'), json.dumps('\u001f'),
            json.dumps('\u007f'), json.dumps('\u0080'), json.dumps('\u07ff'),
            json.dumps('\u0800'), json.dumps('\uffff'),
            json.dumps('\U00010000'), json.dumps('\U0001f600'),
            json.dumps('\U0010ffff'),
            json.dumps('a"b\\c/d\ne\tf'),
        ]),
        # serializer output re-fed as input (double-escaped strings)
        _SERIALIZE_STRING_ARGS.map(_double_escaped),
        # arrays/objects whose string values are serializer outputs
        st.lists(_SERIALIZE_STRING_ARGS, min_size=1, max_size=4).map(
            lambda xs: "[" + ",".join(_escaped(x) for x in xs) + "]"
        ),
        st.lists(
            st.tuples(_quoted_string(), _SERIALIZE_STRING_ARGS),
            min_size=1,
            max_size=4,
        ).map(
            lambda pairs: "{"
            + ",".join(k + ":" + _escaped(v) for k, v in pairs)
            + "}"
        ),
    )


def _build():
    core = st.one_of(
        _value(),
        _empty_containers(),
        _deep_arrays(),
        _deep_objects(),
        _dup_keys(),
        _serialize_doc(),
        _serialize_string_doc(),
        _serialize_roundtrip(),
    )
    return st.one_of(
        core,
        _with_trailing(core),
        _with_ws(core),
        _with_ws(_with_trailing(core)),
    )


strategy = _build()
```