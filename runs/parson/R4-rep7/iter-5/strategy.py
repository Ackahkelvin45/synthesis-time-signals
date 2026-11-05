from hypothesis import strategies as st
import json

# ---------- helpers ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map("".join)

# A "safe" character for inside strings: printable ASCII excluding quote and backslash,
# plus a few unicode chars. Never a raw NUL or control char (parser is NUL-terminated).
_safe_chars = st.sampled_from(
    [chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c)]
    + ["\u00e9", "\u00fc", "\u4e2d", "\u6587", "\U0001F600", "\u2028", "\u007f"]
)

_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = st.tuples(st.just("\\u"), _hex4()).map("".join)

# Surrogate escapes (lone / paired) - these are interesting edge cases.
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\uD834\\uDD1E", "\\u0000"]
)

_string_char = st.one_of(_escapes, _unicode_esc, _surrogate_esc, _safe_chars)

def _string_body(max_size=12):
    return st.lists(_string_char, max_size=max_size).map("".join)

_string = st.tuples(st.just('"'), _string_body(), st.just('"')).map("".join)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", max_size=10)).map("".join),
    st.text(alphabet="0123456789", min_size=1, max_size=18),
)

_frac = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=10)).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map("".join)

_sign = st.sampled_from(["", "-"])

_number = st.one_of(
    # normal numbers
    st.tuples(_sign, _int_part, st.one_of(st.just(""), _frac), st.one_of(st.just(""), _exp)).map("".join),
    # extreme magnitudes / overflow
    st.sampled_from([
        "1e309", "-1e309", "1e400", "-1e400", "1e-400", "1e308", "1.7976931348623157e308",
        "1.8e308", "-1.8e308", "0e0", "0e999999", "1e999999999", "123456789012345678901234567890",
        "-123456789012345678901234567890", "1.0e-999999", "-0", "-0.0", "0.0000000000000000001",
    ]),
    # lone sign (parser quirk: parses as 0)
    st.just("-"),
    # leading + / .5 / 1. / 01 style near-valid
    st.sampled_from(["+1", ".5", "1.", "01", "-01", "+.5", "--1", "1..2", "1e", "1e+", "1e-"]),
)

# ---------- recursive value ----------

_literal = st.sampled_from(["true", "false", "null"])

_json_leaves = st.one_of(_string, _number, _literal)

def _build_value(children):
    return st.one_of(
        _json_leaves,
        st.tuples(st.just("{"), st.just("}")).map("".join),
        st.tuples(st.just("["), st.just("]")).map("".join),
        # object
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map("".join),
                min_size=0, max_size=4,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        # array
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=4).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map("".join),
    )

# Base values (depth 0) - small, non-recursive-ish
_base = st.one_of(_json_leaves)

_value = st.recursive(_base, _build_value, max_leaves=40)

# ---------- deep nesting near the 2048 cap ----------

def _deep(depth):
    # depth nested arrays around a leaf value; depth chosen near 2048
    return st.tuples(
        st.just("[" * depth),
        _json_leaves,
        st.just("]" * depth),
    ).map("".join)

def _deep_obj(depth):
    return st.tuples(
        st.just('{"k":' * depth),
        _json_leaves,
        st.just("}" * depth),
    ).map("".join)

_depth_choice = st.sampled_from([0, 1, 2, 100, 1000, 2000, 2047, 2048, 2049, 2050, 2100, 4096])

_deep_value = st.one_of(
    _depth_choice.flatmap(_deep),
    _depth_choice.flatmap(_deep_obj),
)

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    "{,}", "[,]", "[1,,2]", '{"a":1,}', "[1,]", '{"a" 1}', '{"a":}', "{:1}",
    '{"a":1 "b":2}', '"unterminated', '"esc\\', "[1 2]", "{", "}", "[", "]",
    '{"a":1', '[1,2', '"', '\\', "tru", "fals", "nul", "True", "NULL",
    '{"a":1}}', "[[[]]", '{"a":{"b":}}', "1,2", "1 2", "[] []", "{} {}",
    '{"a":1}garbage', "1abc", "[]xyz", "1 garbage", "nullx", "truefalse",
])

# ---------- round-trip helper: valid JSON that exercises serialize/copy/equals/validate ----------

# Strings that are valid JSON string literals and, when parsed, produce strings
# containing every control char and special char that json_serialize_string handles.
_serialize_probe_strings = st.sampled_from([
    '"\\u0000"', '"\\u0001"', '"\\u0002"', '"\\u0003"', '"\\u0004"', '"\\u0005"',
    '"\\u0006"', '"\\u0007"', '"\\b"', '"\\t"', '"\\n"', '"\\u000b"', '"\\f"',
    '"\\r"', '"\\u000e"', '"\\u000f"', '"\\u0010"', '"\\u0011"', '"\\u0012"',
    '"\\u0013"', '"\\u0014"', '"\\u0015"', '"\\u0016"', '"\\u0017"', '"\\u0018"',
    '"\\u0019"', '"\\u001a"', '"\\u001b"', '"\\u001c"', '"\\u001d"', '"\\u001e"',
    '"\\u001f"', '"\\""', '"\\\\"', '"\\/"', '"/"',
    '"a\\u0000b\\u001fc"', '"\\u0000\\u0001\\u0002\\u0003"',
    '"mix \\" \\\\ \\/ \\b \\f \\n \\r \\t / end"',
])

# Valid nested structures containing those probe strings, so serialize/copy/equals/validate
# all get exercised on rich values.
def _probe_value(children):
    return st.one_of(
        _serialize_probe_strings,
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_serialize_probe_strings, st.just(":"), children).map("".join),
                min_size=0, max_size=3,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=3).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map("".join),
    )

_probe_value_strategy = st.recursive(
    _serialize_probe_strings, _probe_value, max_leaves=15
)

# ---------- top-level composition ----------

_trailing = st.tuples(_value, st.text(alphabet=" \t\n\rabc{}[]0123", max_size=8)).map("".join)

_whitespace = st.text(alphabet=" \t\n\r", max_size=6)

def _wrap_ws(v):
    return st.tuples(_whitespace, v, _whitespace).map("".join)

# ---------- serialize/copy/equals/validate coverage boosters ----------
# The least-covered functions are all downstream of a *valid* parse, so we need
# many guaranteed-valid documents that stress every character class in
# json_serialize_string, deep-copy of nested containers, key-equality in
# json_value_equals, and json_validate.

# Every control char 0x00..0x1f plus quote, backslash, slash, and high bytes,
# as JSON string escapes, so serialize_string hits every switch case.
_all_ctrl_escapes = ["\\u%04x" % c for c in range(0x00, 0x20)]
_all_ctrl_string = '"' + "".join(_all_ctrl_escapes) + '"'

# A valid document whose single string value contains every serializable char.
_full_ctrl_doc = "[" + _all_ctrl_string + "]"

# Valid documents stressing equals: identical vs differing keys/values, order
# permutations, duplicate keys, nested structures.
_equals_docs = st.sampled_from([
    '{"a":1,"b":2}',
    '{"b":2,"a":1}',
    '{"a":1,"b":3}',
    '{"a":1}',
    '{"a":1,"a":1}',
    '{"a":1,"a":2}',
    '[]', '{}', '[1,2,3]', '[3,2,1]', '[1,[2,[3]]]',
    '{"a":{"b":{"c":1}}}',
    '{"a":{"b":{"c":2}}}',
    '{"a":[1,2],"b":[3]}',
    '{"a":[1,2],"b":[3,4]}',
    '[true,false,null]',
    '[true,false,null,0,""]',
    '{"":1}', '{" ":1}',
    '{"k":"v"}', '{"k":"V"}',
])

# Valid docs of many shapes for validate/copy to traverse.
_valid_shapes = st.one_of(
    _value,
    _probe_value_strategy,
    _equals_docs,
    st.just(_full_ctrl_doc),
    st.just(_all_ctrl_string),
    st.just('{"ctrl":' + _all_ctrl_string + '}'),
    st.just("[" + ",".join(_all_ctrl_escapes) + "]"),
)

# ---------- targeted valid docs to reach serialize/copy/equals/validate ----------
# Each of these is guaranteed-valid JSON. They are heavily weighted so that the
# downstream functions (which only run on a successful parse) get exercised.

# A single string containing every char that json_serialize_string switches on,
# split across multiple string values so both serialize_string and the buffer
# growth path (json_serialize_to_buffer_r) run repeatedly.
_serialize_stress = st.sampled_from([
    # every control char in one string
    _all_ctrl_string,
    # each control char as its own array element
    "[" + ",".join(_all_ctrl_escapes) + "]",
    # quote, backslash, slash, and the special short escapes together
    '"\\" \\\\ \\/ \\b \\f \\n \\r \\t /"',
    # nested containers full of control-char strings
    '{"a":' + _all_ctrl_string + ',"b":[' + ",".join(_all_ctrl_escapes[:8]) + "]}",
    '[[' + _all_ctrl_string + '],{"k":' + _all_ctrl_string + "}]",
    # a long-ish string of mixed printable chars (default branch of switch)
    '"' + "".join(chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c)) + '"',
    # empty string and slash-only (slash branch with/without escaping)
    '""',
    '"/"',
    '"///"',
])

# Deep-copy stress: large-ish valid trees so json_value_deep_copy walks many nodes.
def _copy_tree(children):
    return st.one_of(
        _json_leaves,
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map("".join),
                min_size=0, max_size=6,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=6).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map("".join),
    )

_copy_doc = st.recursive(_json_leaves, _copy_tree, max_leaves=60)

# Equals stress: pairs are not needed (the harness parses one doc), but a doc
# with many duplicate keys and repeated structures forces json_value_equals
# comparisons during object construction.
_equals_stress = st.sampled_from([
    '{"a":1,"a":2,"a":3,"a":4,"a":5}',
    '{"x":{"y":{"z":1}},"x":{"y":{"z":1}}}',
    '[{"a":1},{"a":1},{"a":2}]',
    '{"k":[1,2,3],"k":[1,2,3],"k":[1,2,4]}',
    '{"":0," ":1,"  ":2}',
])

# Validate stress: deeply-but-legally nested valid docs (well under the cap).
_validate_stress = st.sampled_from([
    "[" * 50 + "1" + "]" * 50,
    '{"k":' * 50 + "1" + "}" * 50,
    "[" * 200 + "true" + "]" * 200,
    "[" + ",".join(["1"] * 100) + "]",
    "{" + ",".join('"k%d":%d' % (i, i) for i in range(50)) + "}",
])

_downstream_boosters = st.one_of(
    _serialize_stress,
    _copy_doc,
    _equals_stress,
    _validate_stress,
    st.just(_full_ctrl_doc),
    st.just(_all_ctrl_string),
)

# ---------- top-level ----------
# The previous run showed the five downstream functions at 0% branch coverage,
# meaning the harness never got a successful parse into those code paths through
# the weighted mix. We now make guaranteed-valid "downstream booster" documents
# the dominant branch of the strategy, and add explicit raw-parseable strings
# (no surrounding whitespace) so the parser is fed valid input directly.

# A guaranteed-valid doc that forces json_serialize_string to hit *every* switch
# case: one string value containing all control chars, quote, backslash, slash,
# and printable default-branch chars.
_every_switch_case_string = (
    '"'
    + "".join(_all_ctrl_escapes)
    + '\\"\\\\\\/\\b\\f\\n\\r\\t'
    + "".join(chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c))
    + "/"
    + '"'
)
_every_switch_case_doc = "[" + _every_switch_case_string + "]"

# A guaranteed-valid doc that exercises json_value_deep_copy and
# json_value_equals on a broad tree: nested objects/arrays, duplicate keys,
# equal and unequal siblings.
_copy_equals_doc = (
    '{"a":1,"a":2,"b":[1,2,3],"b":[1,2,3],"c":{"d":{"e":[true,false,null]}},'
    '"f":"' + "x" * 40 + '","g":[' + ",".join(['{"k":%d}' % i for i in range(8)]) + "]}"
)

# A guaranteed-valid doc that exercises json_validate on a moderately deep tree.
_validate_doc = "[" * 100 + '{"k":[' + ",".join(["1"] * 20) + "]}" + "]" * 100

_valid_downstream_docs = st.sampled_from([
    _every_switch_case_doc,
    _full_ctrl_doc,
    _all_ctrl_string,
    "[" + ",".join(_all_ctrl_escapes) + "]",
    _copy_equals_doc,
    _validate_doc,
    '{"ctrl":' + _all_ctrl_string + ',"mix":"\\" \\\\ \\/ \\b \\f \\n \\r \\t /"}',
    "[" + ",".join(['"' + e + '"' for e in _all_ctrl_escapes]) + "]",
])

# Raw (unwrapped) valid docs so the parser accepts them without whitespace
# ambiguity; whitespace-wrapped variants are still covered by _wrap_ws below.
strategy = st.one_of(
    # Dominant branch: guaranteed-valid docs targeting the uncovered functions.
    _valid_downstream_docs,
    _valid_downstream_docs,
    _valid_downstream_docs,
    _valid_downstream_docs,
    _valid_downstream_docs,
    _valid_downstream_docs,
    _downstream_boosters,
    _downstream_boosters,
    _downstream_boosters,
    _downstream_boosters,
    # Whitespace-wrapped variants of the downstream boosters.
    _wrap_ws(_downstream_boosters),
    _wrap_ws(_valid_downstream_docs),
    # General valid shapes.
    _valid_shapes,
    _valid_shapes,
    _valid_shapes,
    _wrap_ws(_valid_shapes),
    # Generic recursive values.
    _value,
    _wrap_ws(_value),
    # Deep nesting near the cap.
    _deep_value,
    _wrap_ws(_deep_value),
    # Malformed / near-valid inputs.
    _malformed,
    _wrap_ws(_malformed),
    # Trailing-garbage variants.
    _trailing,
    _wrap_ws(_trailing),
    _probe_value_strategy,
    _wrap_ws(_probe_value_strategy),
    # Extra explicit edge cases.
    st.just(""),
    st.just("{}"),
    st.just("[]"),
    st.just('{"a":0,"a":1}'),
    st.just('{"k":0,"k":1}'),
    st.just("1e309"),
    st.just("-"),
    st.just(_full_ctrl_doc),
    st.just(_all_ctrl_string),
    st.just(_every_switch_case_doc),
    st.just(_copy_equals_doc),
    st.just(_validate_doc),
)