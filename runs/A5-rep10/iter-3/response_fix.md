```python
from hypothesis import strategies as st
import json

# --- leaf string contents ---

# safe codepoints allowed unescaped in JSON strings (excluding " \ and control chars)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

# control / NUL bytes and other weird raw bytes that are allowed in output
_control_chars = st.sampled_from(
    ["\x00", "\x01", "\x08", "\x0b", "\x0c", "\x1f", "\x7f", "\t", "\n", "\r"]
)

_escape_sequences = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex_digits = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.tuples(
    st.just("\\u"), _hex_digits, _hex_digits, _hex_digits, _hex_digits
).map(lambda t: "".join(t))

# surrogate escapes
_high_surrogate = st.tuples(
    st.just("\\u"),
    st.sampled_from("dD"),
    st.sampled_from("89abAB"),
    _hex_digits,
    _hex_digits,
).map(lambda t: "".join(t))

_low_surrogate = st.tuples(
    st.just("\\u"),
    st.sampled_from("dD"),
    st.sampled_from("cdefCDEF"),
    _hex_digits,
    _hex_digits,
).map(lambda t: "".join(t))

_surrogate_pair = st.tuples(_high_surrogate, _low_surrogate).map(lambda t: t[0] + t[1])

# lone / malformed surrogate escapes
_lone_surrogate = st.one_of(
    _high_surrogate,
    _low_surrogate,
    st.just("\\uD800"),
    st.just("\\udc00"),
)

# truncated / invalid unicode escapes (parser fuzzing)
_bad_unicode_escape = st.sampled_from(
    ["\\u", "\\u1", "\\u12", "\\u123", "\\uZZZZ", "\\u12g4", "\\u-123", "\\u 123", "\\U0041", "\\u{}", "\\u{41}"]
)

_string_piece = st.one_of(
    _safe_chars,
    _control_chars,
    _escape_sequences,
    _unicode_escape,
    _surrogate_pair,
    _lone_surrogate,
    _bad_unicode_escape,
)

# a valid-ish JSON string body (may contain raw control chars -> still "stringy")
_string_body = st.lists(_string_piece, min_size=0, max_size=12).map("".join)

_json_string = _string_body.map(lambda s: '"' + s + '"')

# unterminated string (malformed)
_unterminated_string = _string_body.map(lambda s: '"' + s)

# --- numbers ---

_int_digits = st.text("0123456789", min_size=1, max_size=18)
_no_leading_zero_int = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text("0123456789", min_size=0, max_size=18)).map(
        lambda t: t[0] + t[1]
    ),
)

_frac = st.tuples(st.just("."), st.text("0123456789", min_size=1, max_size=18)).map(
    lambda t: t[0] + t[1]
)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text("0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

_leading_minus = st.sampled_from(["", "-"])

_valid_number = st.tuples(
    _leading_minus,
    _no_leading_zero_int,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# extreme magnitudes / overflow
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e999999999",
        "1E+308",
        "1E-308",
        "0e0",
        "-0",
        "-0.0",
        "1.7976931348623157e308",
        "1.7976931348623157e309",
        "5e-324",
        "1e-324",
        "123456789012345678901234567890",
        "-123456789012345678901234567890.123456789e-123",
    ]
)

# malformed numbers
_bad_number = st.sampled_from(
    [
        "+1",
        ".5",
        "1.",
        "01",
        "00",
        "-01",
        "0x1F",
        "-",
        "--",
        "1e",
        "1e+",
        "1.2.3",
        "1..2",
        "1e1e1",
        "- 1",
        "1 ",
        "1e309x",
    ]
)

_number = st.one_of(_valid_number, _extreme_number, _bad_number)

# --- malformed fragments ---

_malformed_fragment = st.sampled_from(
    [
        ",,",
        ",",
        ":",
        "::",
        "{,}",
        "[,]",
        "[,1]",
        "[1,,2]",
        "{,}",
        '{"a" 1}',
        '{"a":}',
        '{:1}',
        '{"a":1,,}',
        "[1 2]",
        "{a:1}",
        "'x'",
        "//x",
        "/* */1",
        "true false",
        "1abc",
        "[]xyz",
        "1 garbage",
        "nul",
        "tru",
        "fals",
        "nulll",
        "truee",
        "undefined",
        "NaN",
        "Infinity",
        "-Infinity",
        "\x00",
        "\x00{}",
        "{}\x00",
        "\u0000",
    ]
)

# --- recursive value/obj/arr ---

json_value = st.recursive(
    st.one_of(
        _json_string,
        _number,
        st.sampled_from(["true", "false", "null"]),
        _malformed_fragment,
        _unterminated_string,
    ),
    lambda children: st.one_of(
        # array
        st.one_of(
            st.just("[]"),
            st.lists(children, min_size=1, max_size=6).map(lambda xs: "[" + ",".join(xs) + "]"),
            # trailing comma variant
            st.lists(children, min_size=1, max_size=6).map(lambda xs: "[" + ",".join(xs) + ",]"),
        ),
        # object
        st.one_of(
            st.just("{}"),
            st.lists(
                st.tuples(_json_string, children).map(lambda t: t[0] + ":" + t[1]),
                min_size=1,
                max_size=6,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
            # trailing comma variant
            st.lists(
                st.tuples(_json_string, children).map(lambda t: t[0] + ":" + t[1]),
                min_size=1,
                max_size=6,
            ).map(lambda ps: "{" + ",".join(ps) + ",}"),
        ),
    ),
    max_leaves=40,
)

# duplicate keys object
_duplicate_key_obj = st.tuples(
    _json_string,
    json_value,
    json_value,
).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}")

# deep nesting helper
_deep_nesting = st.integers(min_value=1, max_value=200).flatmap(
    lambda n: st.just("[" * n + "]" * n)
)

_deep_obj_nesting = st.integers(min_value=1, max_value=100).flatmap(
    lambda n: st.just('{"a":' * n + "1" + "}" * n)
)

# --- VALID-only JSON value/obj/arr (for raising acceptance rate) ---

_valid_json_string = _json_string

_valid_number_strict = _valid_number

_valid_value = st.recursive(
    st.one_of(
        _valid_json_string,
        _valid_number_strict,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        st.one_of(
            st.just("[]"),
            st.lists(children, min_size=1, max_size=6).map(lambda xs: "[" + ",".join(xs) + "]"),
        ),
        st.one_of(
            st.just("{}"),
            st.lists(
                st.tuples(_valid_json_string, children).map(lambda t: t[0] + ":" + t[1]),
                min_size=1,
                max_size=6,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
        ),
    ),
    max_leaves=40,
)

# top-level: bias toward objects with members, plus other shapes
_top_level = st.one_of(
    # bias toward objects with members
    st.lists(
        st.tuples(_json_string, json_value).map(lambda t: t[0] + ":" + t[1]),
        min_size=1,
        max_size=6,
    ).map(lambda ps: "{" + ",".join(ps) + "}"),
    st.lists(
        st.tuples(_json_string, json_value).map(lambda t: t[0] + ":" + t[1]),
        min_size=1,
        max_size=6,
    ).map(lambda ps: "{" + ",".join(ps) + ",}"),
    _duplicate_key_obj,
    json_value,
    _deep_nesting,
    _deep_obj_nesting,
    _malformed_fragment,
    st.just(""),
    st.just(" "),
    st.just("\x00"),
    st.just("{}"),
    st.just("[]"),
)

# occasionally append trailing garbage / whitespace
_trailing_noise = st.sampled_from(["", " ", "\n", "\t", "\x00", "x", "garbage", "{}", "[]"])

# occasionally prepend BOM / leading garbage
_leading_noise = st.sampled_from(["", "\ufeff", " ", "\n", "\x00", "x", "{", "["])

# --- improved: assemble top-level with structural mutations (truncation, unbalanced brackets) ---

def _mutate(s):
    # deterministic-ish structural mutations to exercise error paths
    if not s:
        return s
    choice = len(s) % 5
    if choice == 0:
        return s[:-1]                      # truncation
    if choice == 1:
        return s + "]"                     # unbalanced close
    if choice == 2:
        return "[" + s                     # unbalanced open
    if choice == 3:
        return s + "{"                     # dangling open brace
    return s.replace(",", ":", 1)          # comma -> colon swap

_mutation_wrapper = st.tuples(_top_level, st.booleans()).map(
    lambda t: _mutate(t[0]) if t[1] else t[0]
)

# The original noisy assembly (kept for reference but heavily de-emphasized)
_noisy_strategy = st.tuples(_leading_noise, _mutation_wrapper, _trailing_noise).map(
    lambda t: t[0] + t[1] + t[2]
)

# Valid-only top-level generator: bias strongly toward fully valid JSON documents.
_valid_top_level = st.one_of(
    _valid_value,
    st.lists(
        st.tuples(_valid_json_string, _valid_value).map(lambda t: t[0] + ":" + t[1]),
        min_size=1,
        max_size=6,
    ).map(lambda ps: "{" + ",".join(ps) + "}"),
    st.lists(
        st.tuples(_valid_json_string, _valid_value).map(lambda t: t[0] + ":" + t[1]),
        min_size=1,
        max_size=6,
    ).map(lambda ps: "{" + ",".join(ps) + ",}"),
)

# Emit mostly VALID JSON (raise_acceptance), with a small fraction of noisy inputs.
strategy = st.one_of(
    _valid_top_level,
    _valid_top_level,
    _valid_top_level,
    _valid_top_level,
    _valid_top_level,
    _valid_top_level,
    _valid_top_level,
    _valid_top_level,
    _valid_top_level,
    _noisy_strategy,
)
```