```python
from hypothesis import strategies as st
import json

# ---------- scalar building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

# escapes: valid simple, valid unicode, lone surrogates, and invalid escapes
_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_unicode_escape = _hex4().map(lambda h: "\\u" + h)

# surrogate escapes: high (d800-dbff), low (dc00-dfff), and pairs
def _surrogate_escapes():
    hi = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda n: "\\u%04x" % n)
    lo = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda n: "\\u%04x" % n)
    pair = st.tuples(hi, lo).map(lambda t: t[0] + t[1])
    return st.one_of(hi, lo, pair)

_invalid_escapes = st.sampled_from(['\\x', '\\u12', '\\uZZZZ', '\\', '\\q', '\\U0041'])

# raw characters inside strings: printable, control bytes, NUL, high unicode
_raw_printable = st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                               blacklist_characters='"\\')
_raw_control = st.integers(min_value=0x00, max_value=0x1F).map(chr)
_raw_high = st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF,
                          blacklist_categories=("Cs",))

def _string_body():
    pieces = st.one_of(
        _raw_printable,
        _raw_control,
        _raw_high,
        _simple_escapes,
        _unicode_escape,
        _surrogate_escapes(),
        _invalid_escapes,
    )
    return st.lists(pieces, max_size=8).map(lambda xs: "".join(xs))

def _valid_string():
    return _string_body().map(lambda b: '"' + b + '"')

def _unterminated_string():
    return _string_body().map(lambda b: '"' + b)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        _nonzero_digits,
        # leading zeros (accepted by parser)
        st.tuples(st.just("0"), _digits).map(lambda t: t[0] + t[1]),
    )

def _frac_part():
    return _digits.map(lambda d: "." + d)

def _exp_part():
    sign = st.sampled_from(["", "+", "-"])
    return st.tuples(st.sampled_from(["e", "E"]), sign, _digits).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _number():
    sign = st.sampled_from(["", "-"])
    base = _int_part()
    frac = st.one_of(st.none(), _frac_part(), st.just("."))  # trailing dot accepted
    exp = st.one_of(st.none(), _exp_part())
    # extreme magnitudes
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e308", "-1e308",
        "1e9999", "1e-9999", "0e0", "-0", "0.0e-0",
        "123456789012345678901234567890",
    ])
    composed = st.tuples(sign, base, frac, exp).map(
        lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or "")
    )
    return st.one_of(extreme, composed)

# malformed numbers (rejected by parser)
_bad_number = st.sampled_from([
    "-", "+1", ".5", "-.5", "1..2", "1e", "1e+", "1e-", "--1",
    "0x", "NaN", "Infinity", "-Infinity", "1.2.3", "e5",
])

# ---------- recursive values ----------

def _value_base():
    return st.one_of(
        _valid_string(),
        _number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _bad_number,
        _unterminated_string(),
    )

def _arr(children):
    def build(items):
        return "[" + ",".join(items) + "]"
    return st.one_of(
        st.just("[]"),
        st.lists(children, min_size=1, max_size=5).map(build),
        # malformed: double comma, trailing comma, leading comma
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[" + ",".join(xs) + ",]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[" + ",,".join(xs) + "]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[," + ",".join(xs) + "]"
        ),
    )

def _obj(children):
    def pair(v):
        return st.tuples(_valid_string(), v).map(lambda t: t[0] + ":" + t[1])

    def build(pairs):
        return "{" + ",".join(pairs) + "}"

    return st.one_of(
        st.just("{}"),
        st.lists(pair(st.one_of(children)), min_size=1, max_size=5).map(build),
        # duplicate keys
        st.tuples(_valid_string(), st.one_of(children)).map(
            lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[1] + "}"
        ),
        # malformed: missing colon, trailing comma, double comma
        st.tuples(_valid_string(), st.one_of(children)).map(
            lambda t: "{" + t[0] + t[1] + "}"
        ),
        st.lists(pair(st.one_of(children)), min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        ),
        st.lists(pair(st.one_of(children)), min_size=1, max_size=4).map(
            lambda ps: "{" + ",,".join(ps) + "}"
        ),
    )

_base_value = _value_base()

_recursive_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        _arr(children),
        _obj(children),
    ),
    max_leaves=20,
)

# ---------- deep nesting near the 1000 limit ----------

def _deep_nesting():
    # depth near the limit: 995..1005
    depth = st.integers(min_value=995, max_value=1005)
    open_bracket = st.sampled_from(["[", "{"])
    close_bracket = st.sampled_from(["]", "}"])

    def build(t):
        d, o, c = t
        # alternate brackets for variety
        opens = "".join(o if i % 2 == 0 else ("{" if o == "[" else "[") for i in range(d))
        closes = "".join(c if i % 2 == 0 else ("}" if c == "]" else "]") for i in range(d))
        # object needs a key:value; array needs a value
        if o == "[":
            inner = "0"
        else:
            inner = '"k":0'
        return opens + inner + closes

    return st.tuples(depth, open_bracket, close_bracket).map(build)

def _deep_nesting_exact(depth, kind):
    if kind == "arr":
        return "[" * depth + "0" + "]" * depth
    else:
        return '{"k":' * depth + "0" + "}" * depth

# ---------- print-path exercising values (cJSON_Print / Compare) ----------

def _print_value():
    # Rich values that exercise print_number, print_string_ptr, print_object,
    # print_value, and cJSON_Compare (which recurses over all node types).
    return st.one_of(
        _recursive_value,
        # numbers with varied formatting to hit print_number branches
        st.sampled_from([
            "0", "-0", "1", "-1", "0.0", "-0.0", "1.5", "-1.5",
            "1e10", "1E10", "1e-10", "-1e-10", "1.234567890123456789",
            "123456789012345678901234567890",
            "1e308", "-1e308", "1e-308", "5e-324", "1.7976931348623157e308",
            "100", "1000000", "0.000001", "0.1", "0.123456789",
        ]),
        # strings with characters that exercise print_string_ptr escaping
        st.one_of(_valid_string(), st.sampled_from([
            '"\\u0000"', '"\\u001f"', '"\\u007f"', '"\\u0080"',
            '"\\u00ff"', '"\\u07ff"', '"\\u0800"', '"\\uffff"',
            '"\\ud83d\\ude00"', '"\\"\\\\\\/\\b\\f\\n\\r\\t"',
            '"abcdefghijklmnopqrstuvwxyz"',
            '"\x7f"', '"\x80"',
        ])),
        # objects/arrays with nested structures to exercise Compare recursion
        st.sampled_from([
            '{"a":1,"b":2}', '{"a":{"b":{"c":[1,2,3]}}}',
            '[1,2,3,4,5]', '[[[[1]]]]', '{"x":[{"y":null}]}',
            '{"a":1,"a":2}', '{"":""}', '{"\\u0000":1}',
            '[true,false,null]', '[0,-0,0.0]',
        ]),
    )

# ---------- top-level composition ----------

_top_level = st.one_of(
    _recursive_value,
    _print_value(),
    _deep_nesting(),
    # BOM prefix (accepted)
    st.one_of(_recursive_value).map(lambda s: "\ufeff" + s),
    # trailing content after a value (accepted)
    st.tuples(_recursive_value, st.sampled_from(["", "abc", " 1 2", "\x00", "}]"])).map(
        lambda t: t[0] + t[1]
    ),
    # empty input (rejected)
    st.just(""),
    # whitespace only (rejected)
    st.text(alphabet=" \t\n\r", min_size=1, max_size=8),
    # raw NUL after value
    st.one_of(_recursive_value).map(lambda s: s + "\x00"),
    # malformed top-level pieces
    _bad_number,
    _unterminated_string(),
    st.sampled_from([",", "]", "}", ":", ",,", "[,]", "{,}", "tru", "nul", "fals"]),
)

# ---------- improve_strategy: drive the uncovered print/compare functions ----------
# The run feedback shows cJSON_Compare, print_value, print_string_ptr,
# print_number, and print_object got 0% branch coverage. Those functions are
# only reached when the parser successfully parses input *and* the harness then
# prints/compares it. To hit them we bias heavily toward fully valid documents
# built from the constructs each print/compare branch cares about.

def _valid_scalar():
    return st.one_of(
        _number(),
        _valid_string(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )

# A guaranteed-valid recursive JSON value (no malformed pieces) so the parser
# accepts it and the harness proceeds to print/compare it.
_valid_value = st.recursive(
    _valid_scalar(),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=5).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(
            st.tuples(_valid_string(), children).map(lambda t: t[0] + ":" + t[1]),
            min_size=0, max_size=5,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
    max_leaves=15,
)

# Numbers that specifically exercise print_number's branches: integral vs
# fractional, positive/negative, very small/large exponents, and the special
# formatting boundaries.
_print_number_doc = st.sampled_from([
    "0", "-0", "1", "-1", "100", "-100",
    "0.0", "-0.0", "0.5", "-0.5", "1.5", "-1.5",
    "0.1", "0.123456789", "0.000001", "0.0000001",
    "1000000", "10000000", "1e10", "1E10", "1e-10", "-1e-10",
    "1e308", "-1e308", "1e-308", "5e-324",
    "1.7976931348623157e308", "123456789012345678901234567890",
])

# Strings that exercise print_string_ptr: control chars, high bytes, escapes,
# and surrogate-pair escapes in both raw and escaped form.
_print_string_doc = st.one_of(
    _valid_string(),
    st.sampled_from([
        '""', '"a"', '"abcdefghijklmnopqrstuvwxyz"',
        '"\\u0000"', '"\\u0001"', '"\\u001f"', '"\\u007f"',
        '"\\u0080"', '"\\u00ff"', '"\\u07ff"', '"\\u0800"',
        '"\\uffff"', '"\\ud83d\\ude00"', '"\\ud800"', '"\\udc00"',
        '"\\"\\\\\\/\\b\\f\\n\\r\\t"',
        '"\x00"', '"\x01"', '"\x1f"', '"\x7f"', '"\x80"', '"\xff"',
    ]),
)

# Objects/arrays to exercise print_object/print_array/print_value recursion
# and cJSON_Compare's per-type comparison branches.
_print_structure_doc = st.sampled_from([
    "[]", "{}",
    "[0]", "[true]", "[false]", "[null]", '[""]',
    "[1,2,3,4,5]", "[[],[[]],[[[]]]]",
    '{"a":1}', '{"a":1,"b":2}', '{"a":{"b":{"c":[1,2,3]}}}',
    '{"x":[{"y":null}]}', '{"a":1,"a":2}', '{"":""}',
    '{"\\u0000":1}', '{"k":[]}', '{"k":{}}',
    '[true,false,null]', '[0,-0,0.0]',
    '[{"a":[1,{"b":2}]},{"c":[3,4]}]',
])

# A valid document plus a structurally similar one, so a harness that compares
# two parses will exercise both equal and unequal cJSON_Compare paths.
def _compare_pair():
    def build(t):
        a, b = t
        return a + "\n" + b
    return st.tuples(_valid_value, _valid_value).map(build)

_improve_strategy = st.one_of(
    # heavily weight fully-valid documents that reach the print/compare paths
    _valid_value,
    _print_number_doc,
    _print_string_doc,
    _print_structure_doc,
    # nested valid structures mixing all node types
    st.recursive(
        st.one_of(_print_number_doc, _print_string_doc,
                  st.just("true"), st.just("false"), st.just("null")),
        lambda children: st.one_of(
            st.lists(children, min_size=0, max_size=5).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(_print_string_doc, children).map(
                    lambda t: t[0] + ":" + t[1]
                ),
                min_size=0, max_size=5,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
        ),
        max_leaves=12,
    ),
    # two documents on separate lines to drive compare paths
    _compare_pair(),
)

strategy = _improve_strategy
```