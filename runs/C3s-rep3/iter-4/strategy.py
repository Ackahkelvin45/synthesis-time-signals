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
    # Concentrate depth sampling tightly around the crash boundary and
    # stack many independent perturbations on top of each base shape.
    depth = st.one_of(
        st.integers(min_value=1, max_value=400),
        # tight bands around the suspected boundaries
        st.integers(min_value=100, max_value=200),
        st.integers(min_value=180, max_value=220),
        st.integers(min_value=240, max_value=280),
        # exact-boundary bias values (dense)
        st.sampled_from([
            63, 64, 65, 100, 127, 128, 129, 150, 180, 200, 220,
            240, 255, 256, 257, 280, 300, 320, 350, 400,
        ]),
    )
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

    # --- intensified structural mutations around the crash ---
    # Deep nesting with a value/separator injected at the deepest point
    # (stresses the value-parsing branch at maximum recursion depth).
    deep_inner_value = st.tuples(
        depth, st.sampled_from(['1', 'null', 'true', '""', '{}', '[]', ',', ':', 'x'])
    ).map(lambda t: "[" * t[0] + t[1] + "]" * t[0])
    # Deep object nesting with an injected key/value pair at the deepest level.
    deep_obj_inner = st.tuples(
        depth, st.sampled_from(['"a":1', '"":', ':', ',', '1', '}'])
    ).map(lambda t: '{"a":' * t[0] + t[1] + "}" * t[0])
    # Deep nesting where a single bracket in the middle is flipped/mismatched.
    deep_flip = st.tuples(depth, st.integers(min_value=0, max_value=1)).map(
        lambda t: "[" * t[0] + ("]" if t[1] else "[") + "]" * t[0]
    )
    # Deep nesting with a trailing extra closer (unbalanced close).
    deep_extra_close = depth.map(lambda n: "[" * n + "]" * (n + 1))
    # Deep nesting with whitespace sprinkled inside the deepest level.
    deep_ws = st.tuples(depth, st.sampled_from([" ", "\t", "\n", "\r"])).map(
        lambda t: "[" * t[0] + t[1] + "]" * t[0]
    )
    # Alternating deep nesting with an off-by-one on the closing side.
    inter_off = depth.map(
        lambda n: "".join("[{"[i % 2] for i in range(n))
        + "".join("]}"[i % 2] for i in range(max(0, n - 1)))
    )
    # Deep array nesting containing a nested object at the bottom.
    deep_arr_obj = depth.map(lambda n: "[" * n + '{"a":1}' + "]" * n)
    # Deep object nesting containing a nested array at the bottom.
    deep_obj_arr = depth.map(lambda n: '{"a":' * n + "[1]" + "}" * n)
    # Nested arrays with commas between every level (stress list parsing).
    deep_commas = depth.map(lambda n: "[" + ",".join("[" for _ in range(n)) + ",".join("]" for _ in range(n)) + "]")
    # Deep nesting preceded by leading junk.
    deep_lead_junk = st.tuples(depth, st.sampled_from(["x", ",", ":", "1", "null"])).map(
        lambda t: t[1] + "[" * t[0] + "]" * t[0]
    )
    # Deep nesting with a string injected at the deepest level.
    deep_str = depth.map(lambda n: "[" * n + '"' + "]" * n)
    # Deep nesting with an unterminated string at the deepest level.
    deep_unterm_str = depth.map(lambda n: "[" * n + '"x' + "]" * n)

    # --- additional intensified mutations (near-crash focus) ---
    # Deep nesting with a random single bracket inserted at a random position.
    deep_insert = st.tuples(
        depth,
        st.integers(min_value=0, max_value=1),
        st.integers(min_value=0, max_value=1),
    ).map(
        lambda t: (
            lambda n, pos, br: (
                "[" * n + "]" * n
            )[: pos % (2 * n + 1)]
            + ("[" if br else "]")
            + ("[" * n + "]" * n)[pos % (2 * n + 1):]
        )(t[0], t[1], t[2])
    )
    # Deep nesting with a random single bracket removed.
    deep_remove = st.tuples(
        depth, st.integers(min_value=0, max_value=1)
    ).map(
        lambda t: (
            lambda s, pos: s[: pos % len(s)] + s[pos % len(s) + 1:]
            if len(s) > 1 else s
        )("[" * t[0] + "]" * t[0], t[1])
    )
    # Deep object nesting with mismatched closer type (array closer).
    obj_mismatch = depth.map(lambda n: '{"a":' * n + "]" * n)
    # Deep array nesting with mismatched closer type (object closer).
    arr_mismatch = depth.map(lambda n: "[" * n + "}" * n)
    # Deep nesting with a duplicated deepest bracket.
    deep_dup = depth.map(lambda n: "[" * n + "[" + "]" * n)
    # Deep nesting with an extra opener at the front.
    deep_pre_open = depth.map(lambda n: "[" + "[" * n + "]" * n)
    # Deep nesting with an extra closer at the end.
    deep_post_close = depth.map(lambda n: "[" * n + "]" * n + "]")
    # Deep nesting with a colon injected at the deepest point.
    deep_colon = depth.map(lambda n: "[" * n + ":" + "]" * n)
    # Deep nesting with a string of commas at the deepest point.
    deep_many_commas = depth.map(lambda n: "[" * n + ",,," + "]" * n)
    # Deep object nesting with an extra colon.
    obj_extra_colon = depth.map(lambda n: '{"a"::' * n + "1" + "}" * n)
    # Deep object nesting with a missing colon.
    obj_missing_colon = depth.map(lambda n: '{"a"' * n + "1" + "}" * n)
    # Deep nesting with a NUL byte at the deepest point.
    deep_nul = depth.map(lambda n: "[" * n + "\x00" + "]" * n)
    # Deep nesting with an unterminated object at the deepest point.
    deep_unterm_obj = depth.map(lambda n: "[" * n + '{"a":' + "]" * n)
    # Deep nesting with a backslash at the deepest point.
    deep_backslash = depth.map(lambda n: "[" * n + "\\" + "]" * n)
    # Deep nesting with a lone minus at the deepest point.
    deep_minus = depth.map(lambda n: "[" * n + "-" + "]" * n)
    # Deep nesting with a nested array at the deepest point.
    deep_nested_arr = depth.map(lambda n: "[" * n + "[" + "]" * n)
    # Deep nesting with a nested object at the deepest point.
    deep_nested_obj = depth.map(lambda n: "[" * n + "{" + "}" * n)
    # Deep nesting with a comma-separated list at the deepest point.
    deep_list_inner = depth.map(lambda n: "[" * n + "1,2,3" + "]" * n)
    # Deep nesting with a trailing comma before close.
    deep_trailing_comma = depth.map(lambda n: "[" * n + "1," + "]" * n)
    # Deep nesting with a leading comma after open.
    deep_leading_comma = depth.map(lambda n: "[" * n + ",1" + "]" * n)
    # Deep nesting with a whitespace run at the deepest point.
    deep_ws_run = depth.map(lambda n: "[" * n + "   " + "]" * n)
    # Deep nesting with a very long whitespace run at the deepest point.
    deep_ws_long = depth.map(lambda n: "[" * n + " " * 64 + "]" * n)
    # Deep nesting with an escaped quote at the deepest point.
    deep_esc_quote = depth.map(lambda n: "[" * n + '\\"' + "]" * n)
    # Deep nesting with a unicode escape at the deepest point.
    deep_unicode = depth.map(lambda n: "[" * n + "\\u0041" + "]" * n)
    # Deep nesting with a number at the deepest point.
    deep_number = depth.map(lambda n: "[" * n + "1e309" + "]" * n)
    # Deep nesting with a negative number at the deepest point.
    deep_neg_number = depth.map(lambda n: "[" * n + "-1" + "]" * n)
    # Deep nesting with a boolean at the deepest point.
    deep_bool = depth.map(lambda n: "[" * n + "true" + "]" * n)
    # Deep nesting with a null at the deepest point.
    deep_null = depth.map(lambda n: "[" * n + "null" + "]" * n)
    # Deep nesting with a nested array at the deepest point (unclosed).
    deep_unclosed_arr = depth.map(lambda n: "[" * n + "[" + "]" * n)
    # Deep nesting with a nested object at the deepest point (unclosed).
    deep_unclosed_obj = depth.map(lambda n: "[" * n + "{" + "}" * n)
    # Deep nesting with a nested array at the deepest point (closed).
    deep_closed_arr = depth.map(lambda n: "[" * n + "[]" + "]" * n)
    # Deep nesting with a nested object at the deepest point (closed).
    deep_closed_obj = depth.map(lambda n: "[" * n + "{}" + "]" * n)
    # Deep nesting with a nested array of objects at the deepest point.
    deep_arr_of_obj = depth.map(lambda n: "[" * n + '[{"a":1}]' + "]" * n)
    # Deep object nesting with a nested array of objects at the deepest point.
    deep_obj_of_arr = depth.map(lambda n: '{"a":' * n + '[{"a":1}]' + "}" * n)
    # Deep nesting with a string containing brackets at the deepest point.
    deep_str_brackets = depth.map(lambda n: "[" * n + '"[["' + "]" * n)
    # Deep nesting with a string containing braces at the deepest point.
    deep_str_braces = depth.map(lambda n: "[" * n + '"{{"' + "]" * n)
    # Deep nesting with a string containing a colon at the deepest point.
    deep_str_colon = depth.map(lambda n: "[" * n + '":"' + "]" * n)
    # Deep nesting with a string containing a comma at the deepest point.
    deep_str_comma = depth.map(lambda n: '","' + "]" * n)
    # Deep nesting with a string containing a NUL at the deepest point.
    deep_str_nul = depth.map(lambda n: "[" * n + '"\x00"' + "]" * n)
    # Deep nesting with a string containing a backslash at the deepest point.
    deep_str_backslash = depth.map(lambda n: "[" * n + '"\\"' + "]" * n)
    # Deep nesting with a string containing an escape at the deepest point.
    deep_str_escape = depth.map(lambda n: "[" * n + '"\\n"' + "]" * n)
    # Deep nesting with a string containing a unicode escape at the deepest point.
    deep_str_unicode = depth.map(lambda n: "[" * n + '"\\u0041"' + "]" * n)
    # Deep nesting with a string containing a surrogate escape at the deepest point.
    deep_str_surrogate = depth.map(lambda n: "[" * n + '"\\ud800"' + "]" * n)
    # Deep nesting with a string containing a high surrogate escape at the deepest point.
    deep_str_high_surrogate = depth.map(lambda n: "[" * n + '"\\ud83d"' + "]" * n)
    # Deep nesting with a string containing a low surrogate escape at the deepest point.
    deep_str_low_surrogate = depth.map(lambda n: "[" * n + '"\\ude00"' + "]" * n)
    # Deep nesting with a string containing a surrogate pair at the deepest point.
    deep_str_surrogate_pair = depth.map(lambda n: "[" * n + '"\\ud83d\\ude00"' + "]" * n)
    # Deep nesting with a string containing a bad unicode escape at the deepest point.
    deep_str_bad_unicode = depth.map(lambda n: "[" * n + '"\\uZZZZ"' + "]" * n)
    # Deep nesting with a string containing a bad escape at the deepest point.
    deep_str_bad_escape = depth.map(lambda n: "[" * n + '"\\x"' + "]" * n)
    # Deep nesting with a string containing a lone backslash at the deepest point.
    deep_str_lone_backslash = depth.map(lambda n: "[" * n + '"\\' + "]" * n)
    # Deep nesting with a string containing a lone quote at the deepest point.
    deep_str_lone_quote = depth.map(lambda n: "[" * n + '"' + "]" * n)
    # Deep nesting with a string containing a control char at the deepest point.
    deep_str_control = depth.map(lambda n: "[" * n + '"\x01"' + "]" * n)
    # Deep nesting with a string containing a DEL char at the deepest point.
    deep_str_del = depth.map(lambda n: "[" * n + '"\x7f"' + "]" * n)

    return st.one_of(
        sym, off_open, off_close, obj_deep, obj_deep_bad, inter,
        deep_junk, deep_comma, obj_open, obj_close,
        deep_inner_value, deep_obj_inner, deep_flip, deep_extra_close,
        deep_ws, inter_off, deep_arr_obj, deep_obj_arr, deep_commas,
        deep_lead_junk, deep_str, deep_unterm_str,
        deep_insert, deep_remove, obj_mismatch, arr_mismatch,
        deep_dup, deep_pre_open, deep_post_close, deep_colon,
        deep_many_commas, obj_extra_colon, obj_missing_colon,
        deep_nul, deep_unterm_obj, deep_backslash, deep_minus,
        deep_nested_arr, deep_nested_obj, deep_list_inner,
        deep_trailing_comma, deep_leading_comma, deep_ws_run,
        deep_ws_long, deep_esc_quote, deep_unicode, deep_number,
        deep_neg_number, deep_bool, deep_null, deep_unclosed_arr,
        deep_unclosed_obj, deep_closed_arr, deep_closed_obj,
        deep_arr_of_obj, deep_obj_of_arr, deep_str_brackets,
        deep_str_braces, deep_str_colon, deep_str_comma,
        deep_str_nul, deep_str_backslash, deep_str_escape,
        deep_str_unicode, deep_str_surrogate, deep_str_high_surrogate,
        deep_str_low_surrogate, deep_str_surrogate_pair,
        deep_str_bad_unicode, deep_str_bad_escape,
        deep_str_lone_backslash, deep_str_lone_quote,
        deep_str_control, deep_str_del,
    )

strategy = st.one_of(
    _json,
    _nul_heavy,
    _dup_keys,
    _deep_nesting,
    _malformed,
    _near_crash(),
)