from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.lists(st.sampled_from(_hex), min_size=4, max_size=4).map("".join)

_escapes = st.one_of(
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    _hex4().map(lambda h: "\\u" + h),
)

# raw characters allowed inside a JSON string (SAFECODEPOINT): anything
# except quote, backslash, and U+0000..U+001F. We deliberately include
# NUL/control bytes as *raw* bytes too, since the parser takes a length.
_safe_char = st.characters(
    blacklist_categories=(),  # allow everything
)

# string body made of escapes and raw (possibly control) chars
_str_body = st.one_of(
    _escapes,
    _safe_char,
)

def _quoted(body):
    return '"' + body + '"'

# A "clean" JSON string: no raw control bytes, only escapes + safe chars.
_clean_char = st.characters(
    blacklist_categories=("Cs",),  # no lone surrogates in python str
    blacklist_characters='\\"',
).filter(lambda c: ord(c) >= 0x20)

_clean_body = st.one_of(
    _escapes,
    _clean_char,
)

# A "dirty" string: may contain raw control bytes and NUL.
_dirty_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
)

_dirty_body = st.one_of(
    _escapes,
    _dirty_char,
)

_clean_string = st.lists(_clean_body, max_size=8).map(lambda parts: _quoted("".join(parts)))
_dirty_string = st.lists(_dirty_body, max_size=8).map(lambda parts: _quoted("".join(parts)))

# ---------- numbers ----------

_digits = st.integers(min_value=0, max_value=9).map(str)

def _int_no_leading_zero():
    return st.one_of(
        st.just("0"),
        st.tuples(
            st.integers(min_value=1, max_value=9).map(str),
            st.lists(_digits, max_size=6).map("".join),
        ).map(lambda t: t[0] + t[1]),
    )

def _frac():
    return st.tuples(st.just("."), st.lists(_digits, min_size=1, max_size=6).map("".join)).map(
        lambda t: t[0] + t[1]
    )

def _exp():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.lists(_digits, min_size=1, max_size=4).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2])

# extreme magnitudes: huge/small exponents, overflow like 1e309
_extreme_exp = st.one_of(
    st.just("e309"),
    st.just("E309"),
    st.just("e-309"),
    st.just("e308"),
    st.just("e400"),
    st.just("e999"),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.lists(_digits, min_size=1, max_size=6).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_number = st.one_of(
    # plain integer
    _int_no_leading_zero(),
    # integer with fraction
    st.tuples(_int_no_leading_zero(), _frac()).map(lambda t: t[0] + t[1]),
    # integer with exponent
    st.tuples(_int_no_leading_zero(), _extreme_exp).map(lambda t: t[0] + t[1]),
    # integer with fraction and exponent
    st.tuples(_int_no_leading_zero(), _frac(), _extreme_exp).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # negative variants
    st.tuples(st.just("-"), _int_no_leading_zero()).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("-"), _int_no_leading_zero(), _frac()).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(st.just("-"), _int_no_leading_zero(), _extreme_exp).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # lone minus (accepted by parser)
    st.just("-"),
    # non-finite overflow forms
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-999"),
)

# malformed numbers the parser rejects — still valuable inputs
_bad_number = st.one_of(
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("00"),
    st.just("0x1F"),
    st.just("--1"),
    st.just("1e"),
    st.just("1e+"),
    st.just("1.2.3"),
    st.just("1..2"),
)

# ---------- malformed string fragments ----------

_bad_string = st.one_of(
    st.just('"unterminated'),
    st.just('"unterminated\\'),
    st.just('"bad\\x"'),
    st.just('"bad\\u12"'),
    st.just('"bad\\uZZZZ"'),
    st.just('"'),
    st.just('\\"'),
)

# ---------- recursive structure ----------

_true = st.just("true")
_false = st.just("false")
_null = st.just("null")

# whitespace (skipped by parser)
_ws = st.lists(st.sampled_from(" \t\n\r"), max_size=3).map("".join)

# We build obj/arr recursively. To bias toward objects with members,
# use a weighted strategy for the recursive expansion.

def _obj_with_members(value_st):
    # pair: STRING ':' value  with duplicate keys and trailing comma options
    key = st.one_of(_clean_string, _dirty_string)
    pair = st.tuples(key, st.just(":"), value_st).map(lambda t: t[0] + t[1] + t[2])
    members = st.lists(pair, min_size=1, max_size=5)
    trailing = st.booleans()

    def build(members_list):
        return "{" + ",".join(members_list) + "}"

    def build_trailing(members_list):
        if members_list:
            return "{" + ",".join(members_list) + ",}"
        return "{,}"

    return st.tuples(members, trailing).map(
        lambda t: build_trailing(t[0]) if t[1] else build(t[0])
    )

def _obj_empty():
    return st.just("{}")

def _arr_with_members(value_st):
    items = st.lists(value_st, min_size=1, max_size=5)
    trailing = st.booleans()

    def build(items_list):
        return "[" + ",".join(items_list) + "]"

    def build_trailing(items_list):
        if items_list:
            return "[" + ",".join(items_list) + ",]"
        return "[,]"

    return st.tuples(items, trailing).map(
        lambda t: build_trailing(t[0]) if t[1] else build(t[0])
    )

def _arr_empty():
    return st.just("[]")

# malformed structural fragments
_malformed = st.one_of(
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just("[,1]"),
    st.just("{,}"),
    st.just('{"a":1,,}'),
    st.just('{"a" 1}'),
    st.just('{"a":}'),
    st.just('{:1}'),
    st.just('{"a":1'),
    st.just('[1,2'),
    st.just('}'),
    st.just(']'),
    st.just('{]'),
    st.just('["]'),
    st.just('1abc'),
    st.just('[]xyz'),
    st.just('1 garbage'),
    st.just('true false'),
    st.just("//x"),
    st.just("/* */1"),
    st.just("'x'"),
    st.just("{a:1}"),
)

# deep nesting: raw bracket strings (no recursion cap in parser)
_deep_nesting = st.one_of(
    st.integers(min_value=1, max_value=200).map(lambda n: "[" * n + "]" * n),
    st.integers(min_value=1, max_value=200).map(lambda n: "[" * n),
    st.integers(min_value=1, max_value=200).map(lambda n: "]" * n),
    st.integers(min_value=1, max_value=100).map(
        lambda n: '{"a":' * n + "1" + "}" * n
    ),
    st.integers(min_value=1, max_value=100).map(lambda n: "{" * n + "}" * n),
)

# ---------- recursive value strategy ----------

_value = st.recursive(
    st.one_of(
        _clean_string,
        _dirty_string,
        _number,
        _bad_number,
        _bad_string,
        _true,
        _false,
        _null,
        _obj_empty(),
        _arr_empty(),
        _malformed,
        _deep_nesting,
    ),
    lambda children: st.one_of(
        _obj_with_members(children),
        _arr_with_members(children),
    ),
    max_leaves=30,
)

# top-level json: value EOF, plus optional surrounding whitespace
_json = st.tuples(_ws, _value, _ws).map(lambda t: t[0] + t[1] + t[2])

# Include some raw-NUL / control-byte sprinkled strings explicitly.
_nul_heavy = st.lists(
    st.one_of(
        st.just("\x00"),
        st.just("\x01"),
        st.just("\x1f"),
        st.just("\x7f"),
        st.characters(blacklist_categories=("Cs",), blacklist_characters='\\"'),
    ),
    min_size=1,
    max_size=10,
).map(lambda parts: '"' + "".join(parts) + '"')

# duplicate-key heavy objects (stressed path)
_dup_keys = st.lists(
    st.one_of(st.just("a"), st.just("b"), st.just("c"), st.just("a")),
    min_size=2,
    max_size=6,
).map(lambda keys: "{" + ",".join('"' + k + '":1' for k in keys) + "}")

# ---------- near-crash mutations ----------
# The parser crashed on deeply nested input. Intensify structurally around
# that crash: bracket/brace nesting right around the boundary, with small
# perturbations (mismatched closers, off-by-one depth, interleaved types,
# and trailing junk) to hit the exact failing branch.
def _near_crash():
    depth = st.integers(min_value=1, max_value=300)
    # symmetric deep nesting, the classic crash shape
    sym = depth.map(lambda n: "[" * n + "]" * n)
    # off-by-one: one extra opener
    off_open = depth.map(lambda n: "[" * n + "]" * (n - 1) if n > 0 else "[")
    # off-by-one: one extra closer
    off_close = depth.map(lambda n: "[" * (n - 1) + "]" * n if n > 0 else "]")
    # object nesting with a value at the deepest level
    obj_deep = depth.map(lambda n: '{"a":' * n + "1" + "}" * n)
    # object nesting missing the innermost value
    obj_deep_bad = depth.map(lambda n: '{"a":' * n + "}" * n)
    # interleaved array/object nesting
    inter = depth.map(lambda n: "".join("[{"[i % 2] for i in range(n)) + "".join("]}"[i % 2] for i in range(n)))
    # deep nesting followed by trailing junk
    deep_junk = st.tuples(depth, st.sampled_from(["", "x", ",", ":", "1", "null"])).map(
        lambda t: "[" * t[0] + "]" * t[0] + t[1]
    )
    # deep nesting with a comma inserted near the deepest point
    deep_comma = depth.map(lambda n: "[" * n + "," + "]" * n)
    # unbalanced deep object: openers only
    obj_open = depth.map(lambda n: '{"a":' * n)
    # unbalanced deep object: closers only
    obj_close = depth.map(lambda n: "}" * n)
    return st.one_of(
        sym, off_open, off_close, obj_deep, obj_deep_bad, inter,
        deep_junk, deep_comma, obj_open, obj_close,
    )

strategy = st.one_of(
    _json,
    _nul_heavy,
    _dup_keys,
    _deep_nesting,
    _malformed,
    _near_crash(),
)