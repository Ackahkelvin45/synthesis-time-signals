from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- strings ----------

_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\x00"\\',
)

_ESC_SIMPLE = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_HEX = st.sampled_from("0123456789abcdefABCDEF")
_ESC_UNICODE = st.tuples(st.just("\\u"), _HEX, _HEX, _HEX, _HEX).map(_join)

_SURROGATE = st.tuples(
    st.just("\\u"),
    st.sampled_from(["D", "d"]),
    st.sampled_from("89ABab"),
    _HEX,
    _HEX,
).map(_join)

_ESC = st.one_of(_ESC_SIMPLE, _ESC_UNICODE, _SURROGATE)

_string_body = st.one_of(_SAFE, _ESC)

_STRING = st.tuples(
    st.just('"'),
    st.lists(_string_body, max_size=8).map(_join),
    st.just('"'),
).map(_join)

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), st.lists(st.sampled_from("0123456789"), max_size=5).map(_join)).map(_join),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=40).map(_join),
    )

def _frac_part():
    return st.tuples(st.just("."), st.lists(st.sampled_from("0123456789"), min_size=1, max_size=25).map(_join)).map(_join)

def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=4).map(_join),
    ).map(_join)

_EXTREME_EXP = st.sampled_from([
    "e308", "e309", "e400", "e999", "e-308", "e-400", "e-999",
    "E+308", "E+309", "e+999", "e-999", "e0000000000000001",
])

_NUMBER = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part(),
    st.one_of(st.none(), _frac_part()),
    st.one_of(st.none(), _exp_part(), _EXTREME_EXP),
).map(lambda p: p[0] + p[1] + (p[2] or "") + (p[3] or ""))

# ---------- keywords ----------

_LITERAL = st.sampled_from(["true", "false", "null"])

# ---------- recursive structure ----------

# depth control: concentrate near 2048 occasionally, but keep most small
_depth_choice = st.one_of(
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=4, max_value=16),
    st.sampled_from([32, 64, 128, 256, 512, 1024, 2000, 2047, 2048, 2049, 2100]),
)

def _wrap_depth(depth, inner):
    # produce nested arrays/objects of the given depth around inner
    if depth <= 0:
        return inner
    opener = st.sampled_from(["[", '{"k":'])
    closer = st.sampled_from(["]", "}"])
    return st.tuples(opener, inner, closer).map(_join)

def _nest(depth, inner):
    if depth <= 0:
        return inner
    opener, closer = ("[", "]")
    s = inner
    for _ in range(depth):
        s = st.tuples(st.just(opener), s, st.just(closer)).map(_join)
    return s

# base values
_base = st.one_of(_STRING, _NUMBER, _LITERAL)

# shallow recursive structure
def _obj_or_arr(children):
    pair = st.tuples(_STRING, st.just(":"), children).map(_join)
    obj_full = st.tuples(
        st.just("{"),
        st.lists(pair, min_size=1, max_size=3).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(_join)
    obj_empty = st.just("{}")
    arr_full = st.tuples(
        st.just("["),
        st.lists(children, min_size=1, max_size=3).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(_join)
    arr_empty = st.just("[]")
    return st.one_of(obj_empty, arr_empty, obj_full, arr_full)

_value = st.recursive(_base, _obj_or_arr, max_leaves=8)

# ---------- malformed / near-valid ----------

_malformed = st.one_of(
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just('{"a":1,,}'),
    st.just('{"a" 1}'),
    st.just('{"a":}'),
    st.just("{:1}"),
    st.just('{"a":1,}'),
    st.just("[1,]"),
    st.just('"unterminated'),
    st.just("'single'"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("-01"),
    st.just("-"),
    st.just("-."),
    st.just("tru"),
    st.just("nul"),
    st.just("fals"),
    st.just(""),
    st.just(" "),
    st.just("\t\n\r "),
    st.just("{}{}"),
    st.just("[]x"),
    st.just("1abc"),
    st.just("1 garbage"),
    st.just("null trailing"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just('{"k":0,"k":1}'),
    st.just('{"a":1,"a":2,"b":3}'),
    st.just('"\\uD800"'),
    st.just('"\\uDC00"'),
    st.just('"\\uD800\\uDC00"'),
    st.just('"\\u0000"'),
    st.just('"a\\u0000b"'),
    st.just('"\\q"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('{"a":1 "b":2}'),
    st.just("[1 2]"),
    st.just("[[[["),
    st.just("]]]]"),
    st.just("{{}}"),
    st.just('{"a":{"b":{"c":}}}'),
)

# ---------- deep nesting near cap ----------

def _deep(depth):
    return st.tuples(
        st.just("["),
        st.just("0"),
        st.just("]" * depth),
    ).map(_join).map(lambda s: "[" * depth + "0" + "]" * depth)

_deep_strategy = st.builds(
    lambda d: "[" * d + "0" + "]" * d,
    st.one_of(
        st.sampled_from([2047, 2048, 2049, 2050, 2100, 3000]),
        st.integers(min_value=0, max_value=2048),
    ),
)

_deep_obj = st.builds(
    lambda d: '{"a":' * d + "0" + "}" * d,
    st.one_of(st.sampled_from([2047, 2048, 2049, 2100]), st.integers(min_value=0, max_value=2048)),
)

# ---------- combined ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "1", "[]", "null"])).map(_join)

# ---------- serializer-focused strings ----------
# The parser's serializer branches (json_serialize_string) are entirely
# uncovered. To hit them, the parser must successfully parse a value whose
# decoded string content contains every special/control char, then a
# serialize call must be triggered. We also generate strings whose raw
# content exercises each escape branch and every control byte.

# Map each escape sequence to the raw control byte it decodes to. This lets
# us build strings whose *decoded* content hits every switch case in
# json_serialize_string (the serializer switches on raw bytes, not escapes).
_ESC_TO_BYTE = {
    '\\"': '"',
    '\\\\': '\\',
    '\\/': '/',
    '\\b': '\x08',
    '\\f': '\x0c',
    '\\n': '\x0a',
    '\\r': '\x0d',
    '\\t': '\x09',
    '\\u0000': '\x00', '\\u0001': '\x01', '\\u0002': '\x02', '\\u0003': '\x03',
    '\\u0004': '\x04', '\\u0005': '\x05', '\\u0006': '\x06', '\\u0007': '\x07',
    '\\u000b': '\x0b', '\\u000e': '\x0e', '\\u000f': '\x0f', '\\u0010': '\x10',
    '\\u0011': '\x11', '\\u0012': '\x12', '\\u0013': '\x13', '\\u0014': '\x14',
    '\\u0015': '\x15', '\\u0016': '\x16', '\\u0017': '\x17', '\\u0018': '\x18',
    '\\u0019': '\x19', '\\u001a': '\x1a', '\\u001b': '\x1b', '\\u001c': '\x1c',
    '\\u001d': '\x1d', '\\u001e': '\x1e', '\\u001f': '\x1f',
}

_CTRL_ESC = st.sampled_from(list(_ESC_TO_BYTE.keys()))

# A string that, once decoded, is densely packed with every control/escape
# character, maximizing serializer switch coverage in one pass.
_serializer_bomb = st.tuples(
    st.just('"'),
    st.lists(_CTRL_ESC, min_size=1, max_size=40).map(_join),
    st.just('"'),
).map(_join)

# Also embed the raw literal chars (slash especially) that trigger the
# escape-slash branch and default branch.
_serializer_mixed = st.tuples(
    st.just('"'),
    st.lists(
        st.one_of(
            _CTRL_ESC,
            st.sampled_from(list('abcABC0123 /~!@#$%^&*()_+-=[]{};:,.<>?')),
            st.just("/"),
        ),
        min_size=1,
        max_size=40,
    ).map(_join),
    st.just('"'),
).map(_join)

# Wrap such strings so a full parse+serialize round-trip is plausible.
_serializer_value = st.one_of(
    _serializer_bomb,
    _serializer_mixed,
    st.tuples(st.just("["), _serializer_bomb, st.just("]")).map(_join),
    st.tuples(st.just('{"k":'), _serializer_bomb, st.just("}")).map(_join),
    st.tuples(st.just("["), _serializer_mixed, st.just(","), _serializer_mixed, st.just("]")).map(_join),
)

# ---------- round-trip / serialize-value focused ----------

# Build *valid* JSON whose decoded string content contains every byte the
# serializer's switch handles. The serializer is only reached after a
# successful parse, so these must be well-formed. We construct the raw JSON
# by re-escaping each target decoded byte appropriately.
def _escape_byte_for_json(b):
    if b == '"':
        return '\\"'
    if b == '\\':
        return '\\\\'
    # control chars and slash: use \\uXXXX for full coverage of decode path
    return "\\u%04x" % ord(b)

# All bytes the serializer switch distinguishes.
_SERIALIZE_BYTES = (
    ['"', '\\', '/']
    + ['\x08', '\x0c', '\n', '\r', '\t']
    + [chr(c) for c in range(0x00, 0x20)]
    + list('abcXYZ0123 ~!@#$%^&*()_+-=[]{};:,.<>?')
)

# A single valid JSON string literal whose decoded content is exactly the
# given byte sequence (escaped as needed).
def _make_valid_string_from_bytes(bs):
    return '"' + "".join(_escape_byte_for_json(b) for b in bs) + '"'

# Full-coverage string: one valid literal containing every serializer byte.
_full_coverage_literal = st.just(
    _make_valid_string_from_bytes(_SERIALIZE_BYTES)
)

# Randomized subset (still valid) for variety.
_random_serialize_literal = st.lists(
    st.sampled_from(_SERIALIZE_BYTES), min_size=1, max_size=60
).map(_make_valid_string_from_bytes)

# Wrap in containers so parse->serialize round-trips through objects/arrays.
def _wrap_serialize(lit):
    return st.one_of(
        st.just(lit),
        st.tuples(st.just("["), st.just(lit), st.just("]")).map(_join),
        st.tuples(st.just('{"k":'), st.just(lit), st.just("}")).map(_join),
        st.tuples(st.just("["), st.just(lit), st.just(","), st.just(lit), st.just("]")).map(_join),
    )

_roundtrip_value = st.one_of(
    _wrap_serialize(_full_coverage_literal),
    st.lists(
        st.one_of(_full_coverage_literal, _random_serialize_literal),
        min_size=1, max_size=3,
    ).map(lambda lits: "[" + ",".join(lits) + "]"),
    st.lists(
        st.one_of(_full_coverage_literal, _random_serialize_literal),
        min_size=1, max_size=3,
    ).map(lambda lits: "{" + ",".join('"k%d":%s' % (i, l) for i, l in enumerate(lits)) + "}"),
)

# ---------- deep-copy / equals focused ----------
# json_value_deep_copy and json_value_equals need *valid* parsed values of
# varied shape. The recursive _value already covers this, but add a few
# targeted multi-field/deep structures that the copy walk must traverse.
_copy_equals_value = st.one_of(
    st.just('{"a":{"b":{"c":{"d":[1,2,3,{"e":null}]}}}}'),
    st.just('[{"a":1},{"a":1},{"a":[1,2,3]}]'),
    st.just('{"x":[true,false,null,1,-2,3.5e10,"s"],"y":{"z":[]}}'),
    st.just('[[[[[[[[[[1]]]]]]]]]]'),
    st.just('{"a":1,"b":2,"c":3,"d":4,"e":5,"f":6,"g":7,"h":8}'),
    st.just('[1,2,3,4,5,6,7,8,9,10]'),
    st.just('{"arr":[{"n":1},{"n":2}],"obj":{"deep":{"deeper":{"deepest":true}}}}'),
)

# ---------- validate focused ----------
# json_validate walks the whole document; give it both valid and subtly
# invalid inputs to exercise its accept/reject branches.
_validate_value = st.one_of(
    _value,
    st.just('{"a":1}'),
    st.just('[1,2,3]'),
    st.just('{"a":[1,{"b":null}],"c":"d"}'),
    st.just('{"a":1,}'),
    st.just('[1,2,]'),
    st.just('{"a":}'),
    st.just('[1 2]'),
    st.just('{"a" 1}'),
    st.just('"\\uD800"'),
    st.just('"\\uDC00"'),
    st.just('"\\uD800\\uDC00"'),
    st.just('{"a":1 "b":2}'),
)

strategy = st.one_of(
    _value,
    _malformed,
    _deep_strategy,
    _deep_obj,
    _with_trailing(_value),
    _with_trailing(_NUMBER),
    _with_trailing(_STRING),
    _serializer_value,
    _roundtrip_value,
    _copy_equals_value,
    _validate_value,
)