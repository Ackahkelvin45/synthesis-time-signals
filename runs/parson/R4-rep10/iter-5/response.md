```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_SAFE = st.characters(
    blacklist_categories=("Cc", "Cs"),
    blacklist_characters='"\\',
)

_ESC = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
    ),
    # surrogate escapes
    st.sampled_from([
        "\\ud800", "\\udfff", "\\udc00", "\\ud83d\\ude00",
        "\\uD800\\uDC00", "\\u0000", "\\u001f", "\\u007f",
    ]),
)

_str_char = st.one_of(_SAFE, _ESC)


def _str_body():
    return st.lists(_str_char, min_size=0, max_size=8).map("".join)


def _quoted():
    return _str_body().map(lambda s: '"' + s + '"')


# ---------- numbers ----------

_EXTREME_NUMBERS = st.sampled_from([
    "0", "-0", "1", "-1", "1e309", "-1e309", "1e-309", "1e308",
    "1.7976931348623157e308", "1e400", "-1e400", "1e-400",
    "0.0", "-0.0", "123456789012345678901234567890",
    "9" * 40, "1" + "0" * 300, "1e" + "9" * 5,
    "1E+10", "1e-10", "0e0", "0e999", "1e01", "123.456e-789",
    "1.0e+308", "5e-324", "2.2250738585072014e-308",
])

_normal_number = st.builds(
    lambda sign, ip, frac, exp: sign + ip + frac + exp,
    st.sampled_from(["", "-"]),
    st.one_of(
        st.just("0"),
        st.from_regex(r"[1-9][0-9]{0,6}", fullmatch=True),
    ),
    st.one_of(
        st.just(""),
        st.from_regex(r"\.[0-9]{1,6}", fullmatch=True),
    ),
    st.one_of(
        st.just(""),
        st.builds(
            lambda e, s, d: e + s + d,
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.from_regex(r"[0-9]{1,4}", fullmatch=True),
        ),
    ),
)

_number = st.one_of(_EXTREME_NUMBERS, _normal_number)

# ---------- malformed fragments ----------

_MALFORMED = st.sampled_from([
    "", ",", ",,", ":", "::", "{,}", "[,]", "{,}", '{"a" 1}',
    '{"a":}', '{"a":1,}', "[1,]", "[1,,2]", '"unterminated',
    "+1", ".5", "01", "-", "-.", "1.", "truex", "nul", "tru",
    "fals", '{"a":1 "b":2}', "[1 2]", "{", "}", "[", "]",
    '{"a"::1}', '[,1]', '{"a":1,,"b":2}', '"\x00"',
    "1e", "1e+", "0x10", "Infinity", "NaN", "-Infinity",
    '{"a":1}garbage', "[]xyz", "1abc", "1 garbage",
])

# ---------- recursive JSON ----------

def _make_value(draw, children):
    leaf = st.one_of(
        _quoted(),
        _number,
        st.sampled_from(["true", "false", "null"]),
    )
    if children is None:
        return draw(leaf)
    return draw(st.one_of(leaf, children))


def _make_arr(draw, value):
    n = draw(st.integers(min_value=0, max_value=4))
    items = [draw(value) for _ in range(n)]
    return "[" + ",".join(items) + "]"


def _make_obj(draw, value):
    n = draw(st.integers(min_value=0, max_value=4))
    keys = draw(st.lists(_quoted(), min_size=n, max_size=n, unique=True))
    pairs = [k + ":" + draw(value) for k in keys]
    return "{" + ",".join(pairs) + "}"


def _build_value():
    return st.recursive(
        st.one_of(
            _quoted(),
            _number,
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda children: st.one_of(
            children.flatmap(lambda v: st.just(_make_arr_from(v))),
            children.flatmap(lambda v: st.just(_make_obj_from(v))),
        ),
        max_leaves=20,
    )


def _make_arr_from(v):
    return "[" + v + "]"


def _make_obj_from(v):
    return '{"a":' + v + "}"


_value = _build_value()

# ---------- deep nesting near 2048 ----------

def _deep():
    return st.integers(min_value=1, max_value=2100).flatmap(
        lambda d: st.sampled_from([
            "[" * d + "]" * d,
            "[" * d + "0" + "]" * d,
            '{"a":' * d + "0" + "}" * d,
            "[" * d,  # unterminated deep
            "[" * (d - 1) + "]" * (d - 1) if d > 0 else "[]",
        ])
    )


_deep_strategy = st.one_of(
    _deep(),
    st.integers(min_value=2040, max_value=2060).flatmap(
        lambda d: st.just("[" * d + "]" * d)
    ),
)

# ---------- duplicate keys ----------

def _dup_keys():
    return st.builds(
        lambda k, a, b: '{"' + k + '":' + a + ',"' + k + '":' + b + "}",
        st.text(alphabet="abc", min_size=1, max_size=3),
        _number,
        _number,
    )


# ---------- top-level assembly ----------

_json_value = st.one_of(
    _value,
    _deep_strategy,
    _dup_keys(),
    _MALFORMED,
)

# trailing content (accepted by parser)
def _trailing():
    return st.builds(
        lambda v, t: v + t,
        _value,
        st.sampled_from(["", " ", "x", "garbage", "1abc", "[]xyz", "\n\t"]),
    )


_final = st.one_of(
    _json_value,
    _trailing(),
    _deep_strategy,
    _dup_keys(),
    _MALFORMED,
)

# whitespace variants around a value
def _ws_around():
    return st.builds(
        lambda a, v, b: a + v + b,
        st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
        _value,
        st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
    )


# ---------- exercise serialize / copy / equals / validate paths ----------

# Strings containing every control char and special char so the
# serializer's switch arms (and slash-escaping branch) get hit.
_ALL_CTRL = "".join(chr(c) for c in range(0x00, 0x20))
_SPECIALS = '"\\/'

_serialize_strings = st.one_of(
    st.just(_ALL_CTRL),
    st.just(_ALL_CTRL + _SPECIALS),
    st.just(_SPECIALS),
    st.just("/" * 8),
    st.just("a/b/c\\d\"e"),
    st.lists(
        st.one_of(
            st.sampled_from(list(_ALL_CTRL + _SPECIALS + "abc")),
        ),
        min_size=0,
        max_size=16,
    ).map("".join),
)


def _json_string_escape(s):
    # Build a JSON string literal that decodes to a buffer containing
    # the raw control/special characters, so the serializer must
    # round-trip them through its escape switch.
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "/":
            out.append("/")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20 or o == 0x7F:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


_serialize_doc = st.one_of(
    _serialize_strings.map(_json_string_escape),
    st.builds(
        lambda a, b, c: "[" + _json_string_escape(a) + ","
        + _json_string_escape(b) + "," + _json_string_escape(c) + "]",
        _serialize_strings,
        _serialize_strings,
        _serialize_strings,
    ),
    st.builds(
        lambda s, v: '{"' + s.replace('"', '\\"').replace("\\", "\\\\")
        + '":' + v + "}",
        _serialize_strings.filter(lambda s: "\x00" not in s),
        _number,
    ),
)

# Documents with duplicate keys / equal subtrees to exercise
# json_value_equals and json_value_deep_copy.
_equals_doc = st.builds(
    lambda k, v: '{"' + k + '":' + v + ',"' + k + '":' + v + "}",
    st.text(alphabet="abc", min_size=1, max_size=3),
    _number,
)

_copy_doc = st.builds(
    lambda v: "[" + v + "," + v + "]",
    _number,
)


# ---------- validate / parse-error paths ----------

_validate_doc = st.one_of(
    _MALFORMED,
    st.builds(
        lambda v, t: v + t,
        _value,
        st.sampled_from(["", "x", "garbage", "1abc", "[]xyz", "\n\t"]),
    ),
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("{}"),
    st.just("[]"),
    st.just("0"),
    st.just('"x"'),
)


# ---------- IMPROVED: drive serialize/copy/equals/validate harder ----------

# The C API functions json_serialize_string, json_serialize_to_buffer_r,
# json_value_deep_copy, json_value_equals, and json_validate were never
# reached (0% branch coverage). These are reached by *parsing* a document
# that contains string values with control/special characters, then
# round-tripping. We bias heavily toward such documents.

# A string body that exercises every escape arm of json_serialize_string:
# individual control chars, slash, quote, backslash, and a mix.
_ALL_CTRL_BODY = "".join(chr(c) for c in range(0x00, 0x20))


def _escape_for_literal(ch):
    o = ord(ch)
    if ch == '"':
        return '\\"'
    if ch == "\\":
        return "\\\\"
    if ch == "/":
        return "/"
    if ch == "\b":
        return "\\b"
    if ch == "\f":
        return "\\f"
    if ch == "\n":
        return "\\n"
    if ch == "\r":
        return "\\r"
    if ch == "\t":
        return "\\t"
    if o < 0x20 or o == 0x7F:
        return "\\u%04x" % o
    return ch


def _literal(s):
    return '"' + "".join(_escape_for_literal(c) for c in s) + '"'


# Each entry is a document whose parsed string values cover a distinct
# set of serializer switch arms.
_serialize_arm_docs = st.sampled_from([
    # every control char as its own string value
    "[" + ",".join(_literal(chr(c)) for c in range(0x00, 0x20)) + "]",
    # slash (escape_slashes branch)
    _literal("/"),
    _literal("/" * 32),
    _literal("a/b/c"),
    # quote / backslash
    _literal('"'),
    _literal("\\"),
    _literal('a"b\\c'),
    # all specials + controls together
    _literal(_ALL_CTRL + '"\\/'),
    # object with these as keys and values (exercises serialize_to_buffer_r recursion)
    '{"' + _escape_for_literal('"') + '":' + _literal(_ALL_CTRL) + "}",
    '{"k":' + _literal(_ALL_CTRL + '"\\/') + "}",
    # nested arrays containing special strings
    "[[[" + _literal("\x01\x02\x03") + "]]]",
    '{"a":{"b":["' + _escape_for_literal("\\") + '"]}}',
])

# Docs that exercise json_value_deep_copy: nested structures with many
# equal subtrees and duplicate keys.
_copy_heavy = st.builds(
    lambda v, w: "[" + v + "," + v + "," + w + "," + w + "]",
    _number,
    _quoted(),
)

_equals_heavy = st.builds(
    lambda k, v: '{"' + k + '":' + v + ',"' + k + '":' + v
    + ',"x":' + v + ',"x":' + v + "}",
    st.text(alphabet="abc", min_size=1, max_size=3),
    st.one_of(_number, _quoted(), st.sampled_from(["true", "false", "null"])),
)

# json_validate: valid docs that stress all value kinds plus invalid ones
# that fail at each stage.
_validate_heavy = st.one_of(
    # valid docs
    _value,
    _ws_around(),
    # invalid at each structural position
    st.sampled_from([
        "[", "]", "{", "}", "[,", "{,", "[1,", '{"a":', '{"a":1',
        '"', '""x', 'tru', 'fals', 'nul', '1.', '.1', '+1', '-',
        '{"a":1,"a":2}',  # duplicate keys (valid)
        '{"a":1,"b":}',   # bad value
        '[1,2,3,]',       # trailing comma
        '{"a":[1,2,{"b":null}]}',  # deep valid
        '  [ 1 , 2 ]  ',  # whitespace
        '\t\n\r [\n1\r]\n',
    ]),
)

# Round-trip docs: parse then serialize (the C API's serialize path).
_roundtrip_doc = st.builds(
    lambda a, b: "[" + _literal(a) + "," + _literal(b) + "]",
    st.text(alphabet=_ALL_CTRL + '"\\/abc', max_size=20),
    st.text(alphabet=_ALL_CTRL + '"\\/abc', max_size=20),
)


strategy = st.one_of(
    _final,
    _ws_around(),
    _serialize_doc,
    _equals_doc,
    _copy_doc,
    _validate_doc,
    # --- new, higher-weight coverage of the uncovered C functions ---
    _serialize_arm_docs,
    _copy_heavy,
    _equals_heavy,
    _validate_heavy,
    _roundtrip_doc,
).filter(lambda s: "\x00" not in s)
```