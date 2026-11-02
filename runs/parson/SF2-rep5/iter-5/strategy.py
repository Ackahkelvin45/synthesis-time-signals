from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Scalars ---------------------------------------------------------------

_safe_codepoints = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\"\\",
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_escapes = st.one_of(
    st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    st.sampled_from(
        [
            "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
            "\\uD83D\\uDE00",
            "\\uD800\\uD800",
            "\\uDC00",
        ]
    ),
    st.sampled_from(["\\u0000", "\\u001F", "\\u0007", "\\u001b"]),
)

_string_body = st.one_of(
    _safe_codepoints,
    _escapes,
    st.text(alphabet="abcXYZ019 _-.,:;{}[]", min_size=0, max_size=6),
)

_json_string = st.lists(_string_body, min_size=0, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Numbers ---------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.integers(1, 9).map(str), st.text(alphabet="0123456789", min_size=0, max_size=18)).map(
        lambda t: t[0] + t[1]
    ),
)

_frac_part = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=18)).map(
    lambda t: t[0] + t[1]
)

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=5),
).map(lambda t: t[0] + t[1] + t[2])

_extreme_magnitudes = st.sampled_from(
    [
        "1e309", "-1e309", "1e-309", "1e308", "1e999999",
        "2.2250738585072014e-308", "1.7976931348623157e308",
        "1.7976931348623159e308", "-1e400", "9" * 30,
        "0." + "0" * 20 + "1",
        "1e" + "0" * 30,
    ]
)

_number = st.one_of(
    _extreme_magnitudes,
    st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac_part),
        st.one_of(st.just(""), _exp_part),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

# Malformed numbers (lenient-accept / near-valid) -----------------------

_malformed_number = st.sampled_from(
    [
        "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "00", "007",
        "1e", "1e+", "1e-", "0x1", "1_000", "--1", "1..2", "1.2.3",
        "1e309abc",
    ]
)

# ---------------------------------------------------------------------------
# Recursive value structure
# ---------------------------------------------------------------------------

_leaf = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
)

_value = st.deferred(lambda: _value_strategy)


def _join_obj(pairs):
    return "{" + ",".join(pairs) + "}"


def _join_arr(items):
    return "[" + ",".join(items) + "]"


_obj_strategy = st.one_of(
    st.just("{}"),
    st.lists(
        st.tuples(_json_string, st.just(":"), _value).map(lambda t: t[0] + t[1] + t[2]),
        min_size=1,
        max_size=6,
    ).map(_join_obj),
)

_arr_strategy = st.one_of(
    st.just("[]"),
    st.lists(_value, min_size=1, max_size=6).map(_join_arr),
)

_value_strategy = st.one_of(_leaf, _obj_strategy, _arr_strategy)

# ---------------------------------------------------------------------------
# Duplicate keys (expect rejection by the parser)
# ---------------------------------------------------------------------------

_dup_key_obj = st.tuples(
    _json_string,
    _value,
    _value,
).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}")

_dup_key_obj3 = st.tuples(
    _json_string,
    _value,
).map(lambda t: "{" + t[0] + ":0," + t[0] + ":1," + t[0] + ":" + t[1] + "}")

# ---------------------------------------------------------------------------
# Deep nesting near the 2048 cap
# ---------------------------------------------------------------------------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth


_near_cap_depth = st.one_of(
    st.integers(min_value=1, max_value=16),
    st.integers(min_value=2000, max_value=2055),
    st.integers(min_value=1024, max_value=1030),
    st.sampled_from([2047, 2048, 2049, 2050]),
)

_deep_array = st.tuples(_near_cap_depth, _leaf).map(
    lambda t: _deep(t[0], "[", "]", t[1])
)

_deep_object = st.tuples(_near_cap_depth, _json_string, _leaf).map(
    lambda t: '{"k":' * t[0] + t[2] + "}" * t[0]
)

_deep_mixed = st.tuples(_near_cap_depth, _leaf).map(
    lambda t: "[{" * t[0] + t[1] + "}]" * t[0]
)

_deep_unterminated = st.tuples(_near_cap_depth).map(
    lambda t: "[" * t[0]
)

# ---------------------------------------------------------------------------
# Near-valid-but-malformed inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "[1,,2]", "[1,2,]", "[,]", "[,1]", '{"a":1,,"b":2}', '{"a":1,}',
        '{"a":1,"b":2,}', "{,}", "{,}",
        '{"a" 1}', '{"a"}', '{"a":}', '{:1}', '{"a":1 "b":2}',
        '"abc', '{"a":"unterminated}', '["x', '"', '"\\', '"\\u12',
        "1abc", "1 garbage", "[]xyz", "{}tail", "truefalse", "nullnull",
        "42 43", '{"a":1}{"b":2}', "[1] [2]",
        "+1", ".5", "1.", "01", "00", "-", "-.", "-.5",
        "]", "}", ",", ":", "tru", "nul", "falsey", "TRUE", "Null",
        '"\\x41"', '"\\uZZZZ"', '"\\u12"', '"\\"',
        "", " ", "\n", "\t\r ",
        '"\x01"', '"\x1f"',
        "[[[", "{{{", "[]]", "[}", "{]",
    ]
)

# ---------------------------------------------------------------------------
# Whitespace-padded valid values
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \t\n\r "])

_padded = st.tuples(_ws, _value, _ws).map(lambda t: t[0] + t[1] + t[2])

_padded_trailing = st.tuples(_value, st.text(alphabet="abcXYZ 0123[]{}", min_size=1, max_size=8)).map(
    lambda t: t[0] + t[1]
)

# ---------------------------------------------------------------------------
# Structural mutations of valid values (improves branch coverage)
# ---------------------------------------------------------------------------

_mutate_ops = st.sampled_from(
    ["truncate", "delete", "dup", "swap_bracket", "insert", "prefix", "suffix"]
)

_mutation_position = st.integers(min_value=0, max_value=40)

_stray_tokens = st.sampled_from(
    [",", ":", "[", "]", "{", "}", '"', "\\", "e", ".", "-", "+", "0", " "]
)


def _apply_mutation(value, op, pos, token):
    if not value:
        return token
    i = pos % (len(value) + 1)
    if op == "truncate":
        return value[:i]
    if op == "delete":
        if i >= len(value):
            return value[:-1]
        return value[:i] + value[i + 1:]
    if op == "dup":
        if i >= len(value):
            return value + value[-1:]
        return value[:i] + value[i] + value[i:]
    if op == "swap_bracket":
        swapped = value.replace("[", "\x00", 1).replace("]", "[", 1).replace("\x00", "]", 1)
        if swapped == value:
            swapped = value.replace("{", "\x00", 1).replace("}", "{", 1).replace("\x00", "}", 1)
        return swapped
    if op == "insert":
        return value[:i] + token + value[i:]
    if op == "prefix":
        return token + value
    if op == "suffix":
        return value + token
    return value


_mutated_value = st.tuples(
    _value,
    _mutate_ops,
    _mutation_position,
    _stray_tokens,
).map(lambda t: _apply_mutation(t[0], t[1], t[2], t[3]))

# ---------------------------------------------------------------------------
# Targeted UTF-8 / encoding edge cases (exercises byte-level / string
# decoding branches in the parser: multi-byte sequences, BOM, overlong
# encodings, invalid UTF-8 continuations, and lone surrogate escapes).
# ---------------------------------------------------------------------------

_utf8_edge_strings = st.sampled_from(
    [
        '"\u00e9"',            # 2-byte
        '"\u20ac"',            # 3-byte
        '"\U0001F600"',        # 4-byte (emoji)
        '"\U0001F600\U0001F601"',
        '"\u0000"',
        '"\ufeff"',            # BOM inside string
        '"\ufffd"',            # replacement char
        '"\u07ff\u0800"',      # boundary 2/3-byte
        '"\uffff\U00010000"',  # boundary 3/4-byte
        '"\U0010ffff"',        # max codepoint
        '"\\uD83D\\uDE00"',
        '"\\uD800"',
        '"\\uDC00"',
        '"\u00e9\u00e9\u00e9"',
    ]
)

_utf8_bom_prefix = st.sampled_from(["\ufeff", ""])

_bom_prefixed = st.tuples(_utf8_bom_prefix, _value).map(lambda t: t[0] + t[1])

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value,
    _padded,
    _padded_trailing,
    _mutated_value,
    _dup_key_obj,
    _dup_key_obj3,
    _deep_array,
    _deep_object,
    _deep_mixed,
    _deep_unterminated,
    _malformed,
    _malformed_number,
    _utf8_edge_strings,
    _bom_prefixed,
    st.sampled_from(
        [
            "{}", "[]", "null", "true", "false", "0", "-0", "0.0", "1e0",
            '"\\u0000"', '"\\uD800"', '"\\uDFFF"', '"\\uD83D\\uDE00"',
        ]
    ),
)