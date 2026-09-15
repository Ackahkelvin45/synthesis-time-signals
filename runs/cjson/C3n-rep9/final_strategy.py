from hypothesis import strategies as st
import json

# ---------- primitives ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \t\n"])

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

def _esc():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    hexd = st.sampled_from("0123456789abcdefABCDEF")
    uni = st.tuples(hexd, hexd, hexd, hexd).map(lambda t: "\\u" + "".join(t))
    # lone surrogates: rejected by parser, but interesting
    lone_hi = st.sampled_from("d8d9dadb").flatmap(
        lambda hi: st.tuples(st.just(hi), st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"))
    ).map(lambda t: "\\u" + "".join(t))
    lone_lo = st.sampled_from("dcdddedf").flatmap(
        lambda lo: st.tuples(st.just(lo), st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"))
    ).map(lambda t: "\\u" + "".join(t))
    surrogate_pair = st.tuples(
        st.sampled_from("d8d9dadb"),
    ).flatmap(
        lambda _: st.tuples(
            st.sampled_from("0123456789abcdefABCDEF"), st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("dcdddedf"),
            st.sampled_from("0123456789abcdefABCDEF"), st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("0123456789abcdefABCDEF"),
        )
    ).map(lambda t: "\\u" + "".join(t[:3]) + "\\u" + "".join(t[3:]))
    return st.one_of(simple, uni, lone_hi, lone_lo, surrogate_pair)

# raw control / NUL bytes allowed inside strings per adaptation notes
_raw_ctrl = st.sampled_from(["\x00", "\x01", "\x1f", "\t", "\n", "\r", "\x0b", "\x0c"])

_str_body = st.one_of(
    st.text(_safe_chars, min_size=0, max_size=8),
    _esc(),
    _raw_ctrl,
)

_string = st.one_of(
    st.tuples(st.just('"'), _str_body, st.just('"')).map("".join),
    # unterminated string (near-valid)
    st.tuples(st.just('"'), _str_body).map("".join),
)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)
_nz_digits = st.text("123456789", min_size=1, max_size=1).flatmap(
    lambda d: st.text("0123456789", min_size=0, max_size=5).map(lambda rest: d + rest)
)

_int_part = st.one_of(
    st.just("0"),
    _nz_digits,
    _digits,          # leading zeros: accepted by parser
    st.just(""),
)

_frac = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map("".join),
    st.just("."),     # trailing dot: accepted
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map("".join),
)

# extreme exponents
_big_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text("0123456789", min_size=3, max_size=4),
).map("".join)

_number = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), _int_part, _frac, _exp).map("".join),
    st.tuples(st.sampled_from(["", "-"]), st.just("1"), st.just("."), st.just("0"), _big_exp).map("".join),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1E999999999"),
    st.just("0x10"),      # hex: accepted by parser
    st.just("0XFF"),
    # near-valid malformed
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("00"),
    st.just("1."),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just("1e"),
    st.just("1e+"),
)

# ---------- recursive values ----------

_json = st.deferred(lambda: _value)

def _value_strat():
    return st.one_of(
        _string,
        _number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _json,
    )

_value = _value_strat()

def _pair_strat():
    return st.tuples(_string, _ws, st.just(":"), _ws, _value).map("".join)

def _obj_strat():
    pairs = st.lists(_pair_strat(), min_size=0, max_size=4)
    return st.tuples(
        st.just("{"),
        _ws,
        pairs.map(lambda ps: ("," + "").join(ps)),
        _ws,
        st.just("}"),
    ).map("".join)

def _arr_strat():
    elems = st.lists(_value, min_size=0, max_size=4)
    return st.tuples(
        st.just("["),
        _ws,
        elems.map(lambda es: ",".join(es)),
        _ws,
        st.just("]"),
    ).map("".join)

_obj = _obj_strat()
_arr = _arr_strat()

_value = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _obj,
    _arr,
)

# ---------- deep nesting near the 1000 limit ----------

def _deep(depth):
    # build nested arrays or objects to a given depth
    open_c = st.sampled_from(["[", "{"])
    close_c = st.sampled_from(["]", "}"])
    return st.tuples(open_c, close_c).flatmap(
        lambda oc: st.tuples(
            st.just(oc[0] * depth),
            st.just(oc[1] * depth),
        )
    ).map(lambda t: t[0] + "0" + t[1])

_deep_nesting = st.one_of(
    st.integers(min_value=0, max_value=1000).flatmap(_deep),
    st.integers(min_value=995, max_value=1005).flatmap(_deep),
    st.just("[" * 1000 + "0" + "]" * 1000),
    st.just("[" * 1001 + "0" + "]" * 1001),
    st.just("{" + '"k":' * 1000 + "0" + "}" * 1000),
    st.just("{" + '"k":' * 1001 + "0" + "}" * 1001),
)

# ---------- near-valid / malformed ----------

_malformed = st.sampled_from([
    "{,}",
    "[,]",
    "[1,,2]",
    "[1,2,]",
    '{"a":1,}',
    '{"a":}',
    '{"a" 1}',
    "{a:1}",
    "'a'",
    '{"a":1 "b":2}',
    "[1 2]",
    '"unterminated',
    '"\\x"',
    '"\\u12"',
    '"\\ud800"',
    '"\\udc00"',
    "",
    " ",
    "\x00",
    "1\x00",
    "\ufeff1",
    "\ufeff{\"a\":1}",
    "1 2",
    "1abc",
    "{}extra",
    "[]trailing",
    '{"a":1}{"b":2}',
    "[[[[[",
    "{{{{",
    "]]]]",
    "}",
    "]",
    ":",
    ",",
])

# ---------- cJSON_Compare coverage ----------
# cJSON_Compare compares two parsed JSON values for equality. To exercise it we
# emit two JSON documents (the first is what the harness parses as the primary
# value; the second is the comparison operand) packed into a single string.
# cJSON_Compare walks both trees in parallel, so we must supply pairs that
# reach every branch: equal types, differing types, differing lengths, and
# differing scalar values at every nesting depth.

def _cmp_pair():
    # equal pair: same value serialized twice
    equal = _value.map(lambda v: v + "\x00" + v)
    # unequal pair: two independent values (covers type mismatch branches)
    unequal = st.tuples(_value, _value).map(lambda t: t[0] + "\x00" + t[1])
    # same shape, differing scalar: force deep structural comparison
    def diff_scalar(v):
        return st.sampled_from([v, v + " ", " " + v, v.replace("1", "2", 1)])
    same_shape = _value.flatmap(
        lambda v: st.tuples(st.just(v), diff_scalar(v)).map(lambda t: t[0] + "\x00" + t[1])
    )
    # nested containers with identical structure but one leaf changed
    nested = st.tuples(_arr, _arr).map(lambda t: t[0] + "\x00" + t[1])
    nested_obj = st.tuples(_obj, _obj).map(lambda t: t[0] + "\x00" + t[1])
    # explicit identical complex documents
    explicit = st.sampled_from([
        '{"a":1,"b":[1,2,3],"c":{"d":true}}\x00{"a":1,"b":[1,2,3],"c":{"d":true}}',
        '{"a":1,"b":[1,2,3],"c":{"d":true}}\x00{"a":1,"b":[1,2,3],"c":{"d":false}}',
        '[1,2,3,[4,5,{"x":null}]]\x00[1,2,3,[4,5,{"x":null}]]',
        '[1,2,3,[4,5,{"x":null}]]\x00[1,2,3,[4,5,{"x":0}]]',
        '{"x":1}\x00{"x":1.0}',
        '{"x":1}\x00{"x":"1"}',
        '[]\x00[]',
        '[]\x00[1]',
        'true\x00true',
        'true\x00false',
        'null\x00null',
    ])
    return st.one_of(equal, unequal, same_shape, nested, nested_obj, explicit)

_compare = _cmp_pair()

# ---------- assemble ----------

_value = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _obj,
    _arr,
    _deep_nesting,
    _malformed,
    _compare,
)

# top-level json = value optionally with leading BOM and trailing junk
_top = st.one_of(
    _value,
    st.tuples(st.just("\ufeff"), _value).map("".join),
    st.tuples(_value, st.sampled_from(["", "\x00", "1abc", " ", "junk", "\n"])).map("".join),
)

# ---------- cJSON_Compare direct coverage ----------
# The harness invokes cJSON_Compare on the primary parsed value and the
# comparison operand. Ensure a large fraction of generated inputs are
# explicitly two-document strings separated by NUL so cJSON_Compare is
# exercised on every run, covering equal/unequal/type-mismatch branches.

# Build structurally rich pairs so cJSON_Compare recurses through objects and
# arrays, hitting the per-type comparison branches (bool, number, string,
# array, object) and the length-mismatch / type-mismatch branches at depth.
_cmp_leaf = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

def _cmp_obj(inner):
    pairs = st.lists(
        st.tuples(_string, _ws, st.just(":"), _ws, inner).map("".join),
        min_size=0, max_size=3,
    )
    return st.tuples(
        st.just("{"),
        _ws,
        pairs.map(lambda ps: ",".join(ps)),
        _ws,
        st.just("}"),
    ).map("".join)

def _cmp_arr(inner):
    elems = st.lists(inner, min_size=0, max_size=3)
    return st.tuples(
        st.just("["),
        _ws,
        elems.map(lambda es: ",".join(es)),
        _ws,
        st.just("]"),
    ).map("".join)

_cmp_rich = st.deferred(lambda: _cmp_rich_value())

def _cmp_rich_value():
    return st.one_of(
        _cmp_leaf,
        _cmp_obj(_cmp_rich),
        _cmp_arr(_cmp_rich),
    )

# Pairs that share structure to force deep parallel traversal in cJSON_Compare.
_cmp_rich_pair = _cmp_rich.flatmap(
    lambda v: st.sampled_from([
        v + "\x00" + v,
        v + "\x00" + "null",
        "null" + "\x00" + v,
        v + "\x00" + "0",
        "0" + "\x00" + v,
        v + "\x00" + '""',
        '""' + "\x00" + v,
        v + "\x00" + "[]",
        "[]" + "\x00" + v,
        v + "\x00" + "{}",
        "{}" + "\x00" + v,
        v + "\x00" + "true",
        "true" + "\x00" + v,
    ])
)

# Explicit pairs targeting every cJSON_Compare branch:
# - different types at top level and nested
# - arrays with different lengths
# - objects with different key sets / missing keys
# - string vs number, bool vs null, etc.
_cmp_explicit_branches = st.sampled_from([
    # type mismatches at top level
    'true\x00false',
    'true\x00null',
    'true\x001',
    'true\x00"x"',
    'true\x00[]',
    'true\x00{}',
    'null\x00false',
    'null\x000',
    'null\x00""',
    'null\x00[]',
    'null\x00{}',
    '0\x00""',
    '0\x00[]',
    '0\x00{}',
    '""\x00[]',
    '""\x00{}',
    '[]\x00{}',
    # equal scalars
    'true\x00true',
    'false\x00false',
    'null\x00null',
    '0\x000',
    '1\x001',
    '1.5\x001.5',
    '1e2\x001e2',
    '"abc"\x00"abc"',
    '""\x00""',
    # number vs number, differing value
    '1\x002',
    '1\x00-1',
    '1\x001.0',
    '1\x001e0',
    '0\x00-0',
    # string vs string, differing length / content
    '"a"\x00"b"',
    '"ab"\x00"a"',
    '"a"\x00"ab"',
    '""\x00"a"',
    # arrays: same length differing elems
    '[1,2,3]\x00[1,2,4]',
    '[1,2,3]\x00[1,2,3]',
    # arrays: different lengths
    '[]\x00[1]',
    '[1]\x00[]',
    '[1,2]\x00[1]',
    '[1]\x00[1,2]',
    # arrays: nested
    '[[1],[2]]\x00[[1],[2]]',
    '[[1],[2]]\x00[[1],[3]]',
    '[[1],[2]]\x00[[1]]',
    # objects: same keys, differing values
    '{"a":1}\x00{"a":2}',
    '{"a":1}\x00{"a":1}',
    # objects: different key sets
    '{"a":1}\x00{"b":1}',
    '{"a":1}\x00{"a":1,"b":2}',
    '{"a":1,"b":2}\x00{"a":1}',
    '{"a":1}\x00{}',
    '{"a":1}\x00{"a":1,"b":2}',
    # objects: nested
    '{"a":{"b":1}}\x00{"a":{"b":1}}',
    '{"a":{"b":1}}\x00{"a":{"b":2}}',
    '{"a":{"b":1}}\x00{"a":{}}',
    '{"a":{"b":1}}\x00{"a":{"c":1}}',
    # mixed nesting
    '{"a":[1,2,{"b":true}]}\x00{"a":[1,2,{"b":true}]}',
    '{"a":[1,2,{"b":true}]}\x00{"a":[1,2,{"b":false}]}',
    '{"a":[1,2,{"b":true}]}\x00{"a":[1,2]}',
    '{"a":[1,2,{"b":true}]}\x00{"a":[1,2,{"b":true},3]}',
    # large equal containers to stress recursion
    '[' + ','.join(['1'] * 50) + ']\x00[' + ','.join(['1'] * 50) + ']',
    '[' + ','.join(['1'] * 50) + ']\x00[' + ','.join(['1'] * 49 + ['2']) + ']',
    '[' + ','.join(['1'] * 50) + ']\x00[' + ','.join(['1'] * 49) + ']',
    # equal strings with escapes
    '"\\n"\x00"\\n"',
    '"\\u0041"\x00"A"',
    '"\\t"\x00"\\t"',
])

_compare_direct = st.one_of(
    _compare,
    _cmp_rich_pair,
    _cmp_explicit_branches,
    st.tuples(_value, _value).map(lambda t: t[0] + "\x00" + t[1]),
    _value.map(lambda v: v + "\x00" + v),
    _value.map(lambda v: v + "\x00" + "null"),
    _value.map(lambda v: "null" + "\x00" + v),
)

strategy = st.one_of(_compare_direct, _top)