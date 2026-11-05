```python
from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

_hex = "0123456789abcdefABCDEF"

_esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_esc_unicode = st.tuples(
    st.just("\\u"),
    st.text(alphabet=_hex, min_size=4, max_size=4),
).map(lambda t: "".join(t))

# lone surrogate escapes (parser rejects, but interesting)
_esc_surrogate = st.tuples(
    st.just("\\u"),
    st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DFFF"]),
).map(lambda t: "".join(t))

# surrogate pair (valid)
_esc_surrogate_pair = st.tuples(
    st.just("\\u"),
    st.sampled_from(["d800", "d83d", "dbff"]),
    st.just("\\u"),
    st.sampled_from(["dc00", "de00", "dfff"]),
).map(lambda t: "".join(t))

_esc = st.one_of(_esc_simple, _esc_unicode, _esc_surrogate, _esc_surrogate_pair)

# safe code points: printable ASCII minus quote and backslash, plus some unicode
_safe_ascii = st.characters(
    min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'
)
_safe_unicode = st.characters(
    min_codepoint=0x80, max_codepoint=0x2FFF, blacklist_categories=("Cs",)
)
_safe = st.one_of(_safe_ascii, _safe_unicode)

# raw control / NUL bytes (parser accepts raw control in strings)
_raw_control = st.characters(min_codepoint=0x00, max_codepoint=0x1F)

_str_piece = st.one_of(_esc, _safe, _raw_control)

_string_body = st.lists(_str_piece, max_size=8).map("".join)

_string = _string_body.map(lambda b: '"' + b + '"')

# malformed strings
_unterminated_string = st.tuples(
    st.just('"'), _string_body
).map(lambda t: t[0] + t[1])

_bad_escape = st.tuples(
    st.just('"'), st.sampled_from(["\\x", "\\q", "\\", "\\u12", "\\uZZZZ"]), st.just('"')
).map(lambda t: "".join(t))

_single_quoted = _string_body.map(lambda b: "'" + b + "'")

# ---------- numbers ----------

_int = st.one_of(
    st.just("0"),
    st.tuples(
        st.sampled_from("123456789"),
        st.text(alphabet="0123456789", max_size=20),
    ).map(lambda t: t[0] + t[1]),
)

_leading_zero = st.tuples(
    st.just("0"), st.text(alphabet="0123456789", min_size=1, max_size=10)
).map(lambda t: t[0] + t[1])

_frac = st.tuples(
    st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=20)
).map(lambda t: t[0] + t[1])

_trailing_dot = st.just(".")

_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map(lambda t: t[0] + t[1] + t[2])

_big_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.sampled_from(["308", "309", "310", "400", "1000", "99999"]),
).map(lambda t: t[0] + t[1] + t[2])

_opt_neg = st.one_of(st.just(""), st.just("-"))

_number = st.one_of(
    st.tuples(_opt_neg, _int).map(lambda t: t[0] + t[1]),
    st.tuples(_opt_neg, _int, _frac).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_opt_neg, _int, _exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_opt_neg, _int, _frac, _exp).map(lambda t: "".join(t)),
    st.tuples(_opt_neg, _int, _big_exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_opt_neg, _int, _frac, _big_exp).map(lambda t: "".join(t)),
    # deviations accepted by parser
    st.tuples(_opt_neg, _leading_zero).map(lambda t: t[0] + t[1]),
    st.tuples(_opt_neg, _int, _trailing_dot).map(lambda t: "".join(t)),
    st.tuples(_opt_neg, st.just("0x"), st.text(alphabet=_hex, min_size=1, max_size=8))
        .map(lambda t: "".join(t)),
    # malformed numbers (rejected)
    st.just("-"),
    st.tuples(st.just("+"), _int).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=6))
        .map(lambda t: t[0] + t[1]),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------- recursive values ----------

_json_null = st.just("null")
_json_true = st.just("true")
_json_false = st.just("false")

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

_key = st.one_of(_string, _unterminated_string, _single_quoted)

_pair = st.tuples(_key, _ws, st.just(":"), _ws, st.deferred(lambda: _value)).map(
    lambda t: "".join(t)
)

# malformed pair pieces
_bad_pair = st.one_of(
    st.tuples(_key, _ws, _ws, st.deferred(lambda: _value)).map(lambda t: "".join(t)),  # missing colon
    st.tuples(_key, _ws, st.just(":"), _ws).map(lambda t: "".join(t)),  # missing value
)

_value = st.deferred(lambda: _value_strategy)

# simpler object builder
_obj_members = st.lists(_pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps))
_obj = st.one_of(
    st.just("{}"),
    st.tuples(st.just("{"), _ws, _obj_members, _ws, st.just("}"))
        .map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
)

_arr_items = st.lists(_value, min_size=1, max_size=5).map(lambda vs: ",".join(vs))
_arr = st.one_of(
    st.just("[]"),
    st.tuples(st.just("["), _ws, _arr_items, _ws, st.just("]"))
        .map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
)

# malformed containers
_bad_obj = st.one_of(
    st.tuples(st.just("{"), _pair, st.just(","), st.just("}")).map(lambda t: "".join(t)),  # trailing comma
    st.tuples(st.just("{"), st.just(","), st.just("}")).map(lambda t: "".join(t)),
    st.tuples(st.just("{"), _pair, st.just(","), _pair).map(lambda t: "".join(t)),  # unterminated
    st.tuples(st.just("{"), _bad_pair, st.just("}")).map(lambda t: "".join(t)),
    st.just("{"),
    st.just("}"),
)

_bad_arr = st.one_of(
    st.tuples(st.just("["), _value, st.just(","), st.just("]")).map(lambda t: "".join(t)),  # trailing comma
    st.tuples(st.just("["), st.just(","), st.just("]")).map(lambda t: "".join(t)),
    st.tuples(st.just("["), st.just(","), _value).map(lambda t: "".join(t)),
    st.tuples(st.just("["), _value, st.just(","), _value).map(lambda t: "".join(t)),  # unterminated
    st.just("["),
    st.just("]"),
)

# deep nesting near the 1000-level limit
def _deep(depth, opener, closer):
    return opener * depth + closer * depth

_deep_arr = st.sampled_from([999, 1000, 1001, 1002, 1050]).map(
    lambda d: _deep(d, "[", "]")
)
_deep_obj = st.sampled_from([999, 1000, 1001, 1002]).map(
    lambda d: _deep(d, '{"a":', "}")
)
_deep_mixed = st.sampled_from([998, 999, 1000, 1001]).map(
    lambda d: ("[{" * d) + ("}]" * d)
)

_value_strategy = st.one_of(
    _string,
    _number,
    _json_null,
    _json_true,
    _json_false,
    _obj,
    _arr,
    _unterminated_string,
    _bad_escape,
    _single_quoted,
    _bad_obj,
    _bad_arr,
    _deep_arr,
    _deep_obj,
    _deep_mixed,
)

# ---------- top-level assembly ----------

_bom = st.one_of(st.just(""), st.just("\ufeff"))

_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\x00"),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("\x00\x00"),
    st.tuples(st.just(" "), _value).map(lambda t: t[0] + t[1]),
)

_documents = st.one_of(
    st.tuples(_bom, _ws, _value_strategy, _ws, _trailing).map(lambda t: "".join(t)),
    # empty input (rejected)
    st.just(""),
    st.just(" "),
    st.just("\x00"),
    # top-level junk
    st.just("{"),
    st.just("["),
    st.just(":"),
    st.just(","),
)

# ---------- improve_strategy: add whitespace-rich and structural edge documents ----------
# The parser's branch coverage was lagging behind region coverage, suggesting
# paths gated on whitespace handling and structural edge cases (empty
# containers with whitespace, nested empty, etc.) were under-exercised.
_ws_rich = st.lists(
    st.sampled_from([" ", "\t", "\n", "\r"]), min_size=0, max_size=6
).map("".join)

_empty_with_ws_obj = st.tuples(
    st.just("{"), _ws_rich, st.just("}"),
).map(lambda t: t[0] + t[1] + t[2])

_empty_with_ws_arr = st.tuples(
    st.just("["), _ws_rich, st.just("]"),
).map(lambda t: t[0] + t[1] + t[2])

_ws_around_value = st.tuples(
    _ws_rich, _value_strategy, _ws_rich,
).map(lambda t: t[0] + t[1] + t[2])

_ws_around_colon = st.tuples(
    _key, _ws_rich, st.just(":"), _ws_rich, _value_strategy,
).map(lambda t: "".join(t))

_ws_around_comma = st.tuples(
    _key, _ws_rich, st.just(":"), _ws_rich, _value_strategy,
    _ws_rich, st.just(","), _ws_rich,
    _key, _ws_rich, st.just(":"), _ws_rich, _value_strategy,
).map(lambda t: "".join(t))

_ws_obj = st.tuples(
    st.just("{"), _ws_rich, _ws_around_comma, _ws_rich, st.just("}"),
).map(lambda t: "".join(t))

_ws_arr = st.tuples(
    st.just("["), _ws_rich, _ws_around_value,
    st.lists(
        st.tuples(
            _ws_rich, st.just(","), _ws_rich, _value_strategy,
        ).map(lambda t: "".join(t)),
        min_size=0, max_size=3,
    ).map("".join),
    _ws_rich, st.just("]"),
).map(lambda t: "".join(t))

_ws_documents = st.one_of(
    _empty_with_ws_obj,
    _empty_with_ws_arr,
    _ws_around_value,
    _ws_around_colon,
    _ws_obj,
    _ws_arr,
)

_documents = st.one_of(_documents, _ws_documents)

# ---------- improve_strategy (round 2): branch-focused structural edge cases ----------
# Branch coverage (76.14%) still trails region coverage (93.73%), so the
# unexercised branches are likely decision points inside the value/container
# dispatch and the string/number scanners. Target those specifically:
#   * every container with each whitespace kind at each structural slot
#   * empty/one-element containers with surrounding ws at top level
#   * members that mix keys/values types to force dispatch branches
#   * partial tokens that hit the "unexpected char" branches mid-scan
#   * strings/numbers terminated by EOF vs by delimiter
_ws_kinds = ["", " ", "\t", "\n", "\r", " \t", "\n\r", "  \n "]

_ws_any = st.sampled_from(_ws_kinds)

# object with ws at every slot, single member (forces the "first member" branch)
_obj_one_ws = st.tuples(
    st.just("{"), _ws_any, _key, _ws_any, st.just(":"), _ws_any,
    _value_strategy, _ws_any, st.just("}"),
).map(lambda t: "".join(t))

# object with two members: forces the "subsequent member" branch
_obj_two_ws = st.tuples(
    st.just("{"), _ws_any, _key, _ws_any, st.just(":"), _ws_any,
    _value_strategy, _ws_any, st.just(","), _ws_any,
    _key, _ws_any, st.just(":"), _ws_any, _value_strategy,
    _ws_any, st.just("}"),
).map(lambda t: "".join(t))

# array with exactly one element (first element branch)
_arr_one_ws = st.tuples(
    st.just("["), _ws_any, _value_strategy, _ws_any, st.just("]"),
).map(lambda t: "".join(t))

# array with two elements (subsequent element branch)
_arr_two_ws = st.tuples(
    st.just("["), _ws_any, _value_strategy, _ws_any, st.just(","), _ws_any,
    _value_strategy, _ws_any, st.just("]"),
).map(lambda t: "".join(t))

# nested empty containers (dispatch through value inside a container)
_nested_empty = st.tuples(
    st.just("["), _ws_any, st.one_of(st.just("{}"), st.just("[]")),
    _ws_any, st.just("]"),
).map(lambda t: "".join(t))

_nested_empty_obj = st.tuples(
    st.just("{"), _ws_any, _key, _ws_any, st.just(":"), _ws_any,
    st.one_of(st.just("{}"), st.just("[]")), _ws_any, st.just("}"),
).map(lambda t: "".join(t))

# each scalar type as a bare top-level document with surrounding ws
_scalar_toplevel = st.tuples(
    _ws_any, st.one_of(_string, _number, _json_null, _json_true, _json_false),
    _ws_any,
).map(lambda t: "".join(t))

# partial tokens that should trip "unexpected char" / "unexpected eof" branches
_partial_tokens = st.sampled_from([
    "tru", "fals", "nul", "t", "f", "n",
    "truX", "falsX", "nulX",
    "-", "-.", "-e", "1e", "1e+", "1e-", "1.", "1.2e", "0x", "0xZ",
    '"', '""', '"\\', '"\\u', '"\\u0', '"\\u00', '"\\u000',
    "{", "}", "[", "]", "{,", "[,", "{:", "[}", "{]",
    '{"a"', '{"a":', '{"a":1', '{"a":1,', '{"a":1,}',
    "[1", "[1,", "[1,]", "[,1]",
    ":", ",", "::", ",,",
])

# valid-looking but truncated documents (EOF in the middle of a structure)
_truncated = st.sampled_from([
    '{"a":1', '{"a":1,', '{"a":1,"b":2', '[1,2', '[1,2,',
    '{"a":[1,2', '[[[[', '{{{{',
    '"abc', '"ab\\', '12', '12.', '12e', '-12e',
])

# key-only / value-only fragments to hit pair parsing branches
_pair_fragments = st.one_of(
    st.tuples(_key, _ws_any, st.just(":")).map(lambda t: "".join(t)),
    st.tuples(_key, _ws_any).map(lambda t: "".join(t)),
    st.tuples(_ws_any, st.just(":"), _ws_any, _value_strategy).map(lambda t: "".join(t)),
)

# whitespace-only and BOM-only documents
_ws_only = st.tuples(_bom, _ws_any).map(lambda t: "".join(t))

_branch_documents = st.one_of(
    _obj_one_ws,
    _obj_two_ws,
    _arr_one_ws,
    _arr_two_ws,
    _nested_empty,
    _nested_empty_obj,
    _scalar_toplevel,
    _partial_tokens,
    _truncated,
    _pair_fragments,
    _ws_only,
)

_documents = st.one_of(_documents, _branch_documents)

# ---------- improve_strategy (round 3): target remaining uncovered branches ----------
# Branch coverage (79.55%) still trails region coverage (94.25%). The gap is
# likely in: string scanning (escape dispatch, unicode escape validation,
# surrogate handling, control char handling, EOF vs delimiter termination),
# number scanning (sign, integer/frac/exp transitions, EOF vs delimiter),
# literal matching (true/false/null byte-by-byte failure points), and
# container member separators (missing comma, extra comma, key not string).
# Build explicit micro-fragments that force each decision point.

# string scanning fragments: each terminates either at EOF or at a delimiter
_str_frag_eof = st.sampled_from([
    '"', '"a', '"ab', '"abc',
    '"\\', '"\\"', '"\\\\', '"\\/', '"\\b', '"\\f', '"\\n', '"\\r', '"\\t',
    '"\\u', '"\\u0', '"\\u00', '"\\u000', '"\\u0000',
    '"\\uD800', '"\\uD800\\', '"\\uD800\\u', '"\\uD800\\uDC00',
    '"\\uZZZZ', '"\\u12', '"\\u123g',
    '"\x00', '"\x01', '"\x1f', '"\x7f',
    '"\\x', '"\\q', '"\\U0041',
])
_str_frag_delim = st.sampled_from([
    '"",', '""]', '""}', '"" ',
    '"a",', '"a"]', '"a"}',
    '"\\n",', '"\\u0041",', '"\\u0041"]',
])

# number scanning fragments: terminate at EOF or delimiter
_num_frag_eof = st.sampled_from([
    "0", "-0", "1", "-1", "12", "-12",
    "1.", "1.0", "1.23", "-1.5",
    "1e", "1e0", "1e+", "1e+0", "1e-", "1e-0", "1E10", "-1E-10",
    "0x", "0x0", "0xFF", "-0x1",
    "01", "0123", "-01",
    "+", "+1", "+1.5",
    ".", ".5", "-.5",
])
_num_frag_delim = st.sampled_from([
    "0,", "0]", "0}", "0 ",
    "1.5,", "1.5]", "-1e10,",
    "0x1f,", "0x1f]",
])

# literal matching: fail at each byte position
_literal_frag = st.sampled_from([
    "t", "tr", "tru", "true",
    "f", "fa", "fal", "fals", "false",
    "n", "nu", "nul", "null",
    "truX", "falsX", "nulX",
    "trueX", "falseX", "nullX",
    "True", "False", "Null",
    "TRUE", "FALSE", "NULL",
])

# container member separator edge cases
_obj_sep = st.sampled_from([
    '{"a":1 "b":2}',        # missing comma
    '{"a":1,,}',            # double comma
    '{"a":1,,"b":2}',       # double comma mid
    '{"a" 1}',              # missing colon
    '{"a"::1}',             # double colon
    '{a:1}',                # unquoted key
    '{1:2}',                # numeric key
    '{"a":1,}',             # trailing comma
    '{"a":1}',              # valid single
    '{"a":1,"b":2}',        # valid two
    '{"a":1,"b":2,}',       # valid + trailing
])

_arr_sep = st.sampled_from([
    '[1 2]',                # missing comma
    '[1,,2]',               # double comma
    '[,1]',                 # leading comma
    '[1,]',                 # trailing comma
    '[1,2,]',               # trailing comma two
    '[1,2]',                # valid
    '[[],[]]',              # nested empties
    '[{},{}]',              # nested empty objs
    '{"a":[]}',             # empty arr value
    '{"a":{}}',             # empty obj value
])

# deep nesting with content at the bottom (forces dispatch at each level)
def _deep_with_leaf(depth, opener, closer, leaf):
    return opener * depth + leaf + closer * depth

_deep_leaf = st.sampled_from([999, 1000, 1001]).flatmap(
    lambda d: st.sampled_from([
        _deep_with_leaf(d, "[", "]", "1"),
        _deep_with_leaf(d, "[", "]", '"x"'),
        _deep_with_leaf(d, '{"a":', "}", "1"),
        _deep_with_leaf(d, '{"a":', "}", "null"),
    ])
)

# unicode escape boundary cases
_unicode_esc = st.sampled_from([
    '"\\u0000"', '"\\u001f"', '"\\u0020"', '"\\u007f"', '"\\u0080"',
    '"\\uffff"', '"\\uFFFF"', '"\\uD7FF"', '"\\uE000"',
    '"\\uD800"', '"\\uDBFF"', '"\\uDC00"', '"\\uDFFF"',
    '"\\uD800\\uDC00"', '"\\uDBFF\\uDFFF"',
    '"\\uD800x"', '"\\uD800\\u"', '"\\uD800\\uXXXX"',
    '"\\u123"', '"\\u12345"', '"\\u123"',
])

# control chars and NUL inside strings, terminated by delimiter
_control_str = st.sampled_from([
    '"\x00",', '"\x01",', '"\x1f",', '"\x7f",',
    '"\x00\x01\x02",', '"\x1f\x1e",',
])

# number/literal/string at top level with each trailing delimiter
_top_terminators = st.sampled_from(["", " ", "\t", "\n", "\r", ",", "]", "}", ":"])

_scalar_terminated = st.tuples(
    st.one_of(
        st.sampled_from(["1", "1.5", "1e10", "true", "false", "null", '"x"']),
    ),
    _top_terminators,
).map(lambda t: t[0] + t[1])

# empty containers with each ws kind, plus nested empties
_empty_ws_any = st.tuples(
    st.sampled_from(["{", "["]),
    _ws_any,
    st.sampled_from(["}", "]"]),
).map(lambda t: t[0] + t[1] + t[2])

# arrays/objects with only whitespace and one structural char
_struct_frag = st.sampled_from([
    "{", "}", "[", "]", "{ ", " }", "[ ", " ]",
    "{,}", "[,]", "{:}", "[:]",
    '{"a":1,"b":2,"c":3}',
    '[1,2,3,4,5]',
    '[[[[[]]]]]',
    '{"a":{"b":{"c":1}}}',
])

_round3 = st.one_of(
    _str_frag_eof,
    _str_frag_delim,
    _num_frag_eof,
    _num_frag_delim,
    _literal_frag,
    _obj_sep,
    _arr_sep,
    _deep_leaf,
    _unicode_esc,
    _control_str,
    _scalar_terminated,
    _empty_ws_any,
    _struct_frag,
)

_documents = st.one_of(_documents, _round3)

strategy = _documents
```