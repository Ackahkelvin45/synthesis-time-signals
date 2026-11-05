import json
from hypothesis import strategies as st

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

def _join_comma(parts):
    return ",".join(parts)

# ---------- scalars ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "".join(t))

# \uXXXX escapes including surrogates
_unicode_escape = _hex4().map(lambda h: "\\u" + h)

# simple escapes
_simple_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# safe code points (excluding quote, backslash, control chars)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00',
).filter(lambda c: ord(c) >= 0x20)

_string_body_piece = st.one_of(
    _safe_char,
    _simple_escape,
    _unicode_escape,
)

_json_string = st.lists(_string_body_piece, max_size=8).map(_join).map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), _digits.map(lambda d: d)).map(_join),
    )

def _frac_part():
    return _digits.map(lambda d: "." + d)

def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(_join)

def _number():
    sign = st.sampled_from(["", "-"])
    frac = st.one_of(st.just(""), _frac_part())
    exp = st.one_of(st.just(""), _exp_part())
    return st.tuples(sign, _int_part(), frac, exp).map(_join)

# extreme magnitudes
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "-1e308", "1e400", "1e-400",
    "123456789012345678901234567890",
    "-123456789012345678901234567890",
    "1.7976931348623157e308",
    "2.2250738585072014e-308",
    "0e0", "0.0", "-0", "1E+10", "1e-10",
])

_number_strategy = st.one_of(_number(), _extreme_number)

# ---------- recursive values ----------

_key = _json_string

# forward reference via deferred strategy
_value_ref = st.deferred(lambda: _value)

def _pair():
    return st.tuples(_key, st.just(":"), _value_ref).map(_join)

def _obj():
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(), min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}"),
    )

def _arr():
    return st.one_of(
        st.just("[]"),
        st.lists(_value_ref, min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
    )

_leaf = st.one_of(
    _json_string,
    _number_strategy,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_obj(), _arr()),
    max_leaves=12,
)

# ---------- deep nesting near the 2048 limit ----------

def _deep_nesting():
    # depth concentrated near 2048
    depth = st.integers(min_value=1, max_value=2048)
    open_ch = st.sampled_from(["[", "{"])
    return st.tuples(depth, open_ch).map(lambda t: _build_deep(t[0], t[1]))

def _build_deep(depth, ch):
    if ch == "[":
        return "[" * depth + "]" * depth
    else:
        return ('{"k":' * depth) + "0" + ("}" * depth)

_deep = _deep_nesting()

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    '{"a":1,,}',
    '{"a":1,}',
    "[1,,2]",
    "[1,]",
    '{"a" 1}',
    '{"a":}',
    '{"a":1 "b":2}',
    '{"a":1,,"b":2}',
    '[,]',
    '{,}',
    '{"a":1',
    '[1,2',
    '"unterminated',
    '"unterminated\\',
    '{"a":"unterminated}',
    '+1',
    '.5',
    '-.5',
    '01',
    '-01',
    '1.',
    '00',
    '1e',
    '1e+',
    '-',
    '-.',
    'tru',
    'nul',
    'fals',
    '{"a":1}garbage',
    '[]xyz',
    '1abc',
    '1 garbage',
    'null extra',
    'true false',
    '{"a":1} {"b":2}',
    '"\\uD800"',
    '"\\uDFFF"',
    '"\\uD800\\uDC00"',
    '"\\u0000"',
    '"\\u00"',
    '"\\uZZZZ"',
    '"\\x"',
    '"\\"',
    '{"a":1,"a":2}',
    '{"k":0,"k":1}',
    '{"a":{"b":1},"a":2}',
])

# ---------- top-level combination ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "\n", "[]"])).map(_join)

_value_top = st.one_of(
    _value,
    _deep,
    _malformed,
)

# avoid raw NUL bytes in final output
_final = _value_top.map(lambda s: s.replace("\x00", ""))
_final = st.one_of(_final, _with_trailing(_value))

# Improve fuzzing: bias toward boundary depths and add whitespace-wrapped valid values
def _boundary_depths():
    return st.sampled_from([1, 2, 3, 16, 64, 128, 256, 512, 1024, 2047, 2048])

def _build_deep_boundary(depth, ch):
    if ch == "[":
        return "[" * depth + "]" * depth
    else:
        return ('{"k":' * depth) + "0" + ("}" * depth)

_deep_boundary = st.tuples(_boundary_depths(), st.sampled_from(["[", "{"])).map(
    lambda t: _build_deep_boundary(t[0], t[1])
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r\n"])

def _wrap_ws(v):
    return st.tuples(_ws, v, _ws).map(_join)

# NEW: whitespace injection inside structural tokens to stress the parser's
# handling of insignificant whitespace around delimiters, colons, and values.
_ws_tight = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  ", " \t "])

def _ws_obj():
    def pair():
        return st.tuples(
            _ws_tight, _key, _ws_tight, st.just(":"), _ws_tight, _value_ref, _ws_tight
        ).map(_join)
    return st.one_of(
        st.just("{" + "}"),
        st.tuples(
            _ws_tight,
            st.lists(pair(), min_size=1, max_size=3).map(lambda ps: ",".join(ps)),
            _ws_tight,
        ).map(lambda t: "{" + t[0] + t[1] + t[2] + "}"),
    )

def _ws_arr():
    return st.one_of(
        st.just("[" + "]"),
        st.tuples(
            _ws_tight,
            st.lists(
                st.tuples(_ws_tight, _value_ref, _ws_tight).map(_join),
                min_size=1, max_size=3,
            ).map(lambda vs: ",".join(vs)),
            _ws_tight,
        ).map(lambda t: "[" + t[0] + t[1] + t[2] + "]"),
    )

_ws_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_ws_obj(), _ws_arr()),
    max_leaves=10,
)

_value_top = st.one_of(
    _value,
    _deep,
    _deep_boundary,
    _malformed,
    _wrap_ws(_value),
    _ws_value,
)

_final = _value_top.map(lambda s: s.replace("\x00", ""))

# NEW: mutation-based fuzzing. Take a valid JSON value and apply a small number
# of byte-level mutations (delete, duplicate, replace with a structural token).
# This generates near-valid inputs that exercise parser error-recovery paths
# much more effectively than a fixed list of malformed samples.
_mutation_tokens = st.sampled_from(
    list('{}[],:"0123456789.eE-+ \t\n\\') + ["true", "false", "null", "\\u", "\\x"]
)

def _mutate(s):
    # single deterministic mutation chosen from a sampled op index
    return st.tuples(
        st.sampled_from(["del", "dup", "ins", "repl"]),
        st.integers(min_value=0, max_value=max(0, len(s) - 1)) if s else st.just(0),
        _mutation_tokens,
    ).map(lambda t: _apply_mutation(s, t[0], t[1], t[2]))

def _apply_mutation(s, op, pos, tok):
    if not s:
        return tok
    pos = min(pos, len(s))
    if op == "del":
        return s[:pos] + s[pos + 1:]
    if op == "dup":
        return s[:pos] + s[pos] + s[pos:]
    if op == "ins":
        return s[:pos] + tok + s[pos:]
    # repl
    return s[:pos] + tok + s[pos + 1:]

_mutated = _value.flatmap(_mutate)

# Also mutate deep-boundary samples to hit depth-limit error paths.
_mutated_deep = _deep_boundary.flatmap(_mutate)

_final = st.one_of(
    _final,
    _mutated,
    _mutated_deep,
    _with_trailing(_value),
)

# IMPROVEMENT: multi-site mutation. Apply 1-4 independent mutations to a valid
# value so the parser encounters compound errors (e.g. a broken string escape
# plus a stray comma plus a truncated object). This exercises error-recovery
# and resynchronisation paths far better than single-byte mutations.
def _mutate_many(s):
    n = st.integers(min_value=1, max_value=4)
    ops = st.lists(
        st.tuples(
            st.sampled_from(["del", "dup", "ins", "repl"]),
            st.integers(min_value=0, max_value=10**9),
            _mutation_tokens,
        ),
        min_size=1,
        max_size=4,
    )
    def _apply_all(t):
        cur = s
        for op, pos, tok in t:
            cur = _apply_mutation(cur, op, pos % (len(cur) + 1), tok)
        return cur
    return ops.map(_apply_all)

_mutated_multi = _value.flatmap(_mutate_many)
_mutated_multi_deep = st.one_of(_deep_boundary, _ws_value).flatmap(_mutate_many)

_final = st.one_of(_final, _mutated_multi, _mutated_multi_deep)

strategy = _final