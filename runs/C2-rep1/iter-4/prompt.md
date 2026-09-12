Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- leaf-level building blocks ----------

# Safe (unescaped) code points the grammar allows inside strings:
# anything except '"', '\\', and control chars 0x00-0x1F.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates as raw chars
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

# Escape sequences permitted by the grammar's ESC / UNICODE fragments.
_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_unicode_escape = st.tuples(st.just("\\u"), _hex_digit, _hex_digit, _hex_digit, _hex_digit).map(
    lambda t: "".join(t)
)

# Surrogate escapes, both lone and paired, plus high/low ranges.
_high_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda n: "\\u%04x" % n)
_low_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda n: "\\u%04x" % n)
_surrogate_escape = st.one_of(_high_surrogate, _low_surrogate)
_surrogate_pair = st.tuples(_high_surrogate, _low_surrogate).map(lambda t: t[0] + t[1])

_string_body_piece = st.one_of(
    _safe_chars.map(str),
    _simple_escapes,
    _unicode_escape,
    _surrogate_escape,
    _surrogate_pair,
)

# Raw control bytes (including NUL) emitted literally inside a string body.
# The grammar's SAFECODEPOINT excludes these, but the harness parses by length
# and we want to stress NUL/control handling.
_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_string_body = st.one_of(
    st.lists(_string_body_piece, min_size=0, max_size=8).map("".join),
    st.lists(_raw_control, min_size=1, max_size=4).map("".join),
    st.lists(st.one_of(_string_body_piece, _raw_control), min_size=0, max_size=8).map("".join),
)

# Quoted strings. Occasionally drop the closing quote to make malformed input.
_well_formed_string = _string_body.map(lambda b: '"' + b + '"')
_unterminated_string = _string_body.map(lambda b: '"' + b)
_string = st.one_of(_well_formed_string, _unterminated_string)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(
        st.integers(min_value=1, max_value=9).map(str),
        st.lists(st.integers(min_value=0, max_value=9).map(str), max_size=6).map("".join),
    ).map(lambda t: t[0] + t[1]),
)

_frac_part = st.tuples(
    st.just("."),
    st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=6).map("".join),
).map(lambda t: t[0] + t[1])

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=6).map("".join),
).map(lambda t: t[0] + t[1] + t[2])

_sign = st.sampled_from(["", "-"])

_well_formed_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.just(""), _frac_part),
    st.one_of(st.just(""), _exp_part),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Extreme magnitudes / exponents, including overflow like 1e309.
_extreme_number = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1e999999999"),
    st.just("-1e999999999"),
    st.just("0e0"),
    st.just("-0"),
    st.just("1.7976931348623157e308"),
    st.just("5e-324"),
    st.tuples(
        st.sampled_from(["", "-"]),
        st.just("1"),
        st.just("e"),
        st.integers(min_value=300, max_value=100000).map(str),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

# Malformed / non-RFC number forms the parser actually rejects.
_malformed_number = st.one_of(
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("-01"),
    st.just("0x1F"),
    st.just("00"),
    st.just("1e"),
    st.just("1e+"),
    st.just("--1"),
    st.just("-"),
    st.tuples(
        st.sampled_from(["01", "00", "007"]),
        st.lists(st.integers(min_value=0, max_value=9).map(str), max_size=4).map("".join),
    ).map(lambda t: t[0] + t[1]),
)

# Near-crash mutations of the observed divergence input "-1e999999999".
# Intensified: structurally mutate around the crashing input by embedding it
# inside JSON containers, wrapping it with malformed fragments, and generating
# a wide family of exponent-overflow variants.
_crash_core = st.sampled_from(
    [
        "-1e999999999",
        "-1e999999998",
        "-1e999999997",
        "-1e1000000000",
        "-1e99999999",
        "-1e9999999990",
        "-1e9999999999",
        "-1e99999999900",
        "-1e999999999000",
        "-2e999999999",
        "-9e999999999",
        "-1E999999999",
        "-1e+999999999",
        "-1e-999999999",
        "-1.0e999999999",
        "-1.0E999999999",
        "-1.5e999999999",
        "1e999999999",
        "-1e2147483647",
        "-1e2147483648",
        "-1e4294967295",
        "-1e4294967296",
        "-1e9223372036854775807",
        "-1e9223372036854775808",
        "-1e18446744073709551615",
        "-1e18446744073709551616",
    ]
)

# Exponent-only family around the crash shape.
_crash_exp_family = st.tuples(
    st.sampled_from(["", "-", "+"]),
    st.sampled_from(["1", "2", "9", "0", "1.0", "1.5", "9.9", "1.7976931348623157"]),
    st.sampled_from(["e", "E"]),
    st.one_of(
        st.integers(min_value=300, max_value=100000).map(str),
        st.sampled_from(
            [
                "999999999",
                "999999998",
                "9999999990",
                "9999999999",
                "1000000000",
                "2147483647",
                "2147483648",
                "4294967295",
                "4294967296",
                "9223372036854775807",
                "9223372036854775808",
            ]
        ),
    ),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# The crashing input embedded inside structural JSON contexts.
_crash_in_context = st.one_of(
    st.tuples(st.just("["), _crash_core, st.just("]")).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.just("["), _crash_core, st.just(",1]")).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.just("[1,"), _crash_core, st.just("]")).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.just('{"a":'), _crash_core, st.just("}")).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.just('{"a":1,"b":'), _crash_core, st.just("}")).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(st.just('{"a":'), _crash_core, st.just(",\"b\":2}")).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(st.just("[["), _crash_core, st.just("]]")).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.just('{"a":['), _crash_core, st.just("]}")).map(
        lambda t: t[0] + t[1] + t[2]
    ),
)

# The crashing input with adjacent malformed fragments (truncation, extra
# tokens, unterminated containers) to stress boundary handling.
_crash_with_fragment = st.tuples(
    st.one_of(
        st.just(""),
        st.just("["),
        st.just("{"),
        st.just('["'),
        st.just('{"a":'),
        st.just("[1,"),
    ),
    _crash_core,
    st.one_of(
        st.just(""),
        st.just("]"),
        st.just("}"),
        st.just(","),
        st.just(":]"),
        st.just(" ,"),
        st.just("1"),
        st.just('"'),
        st.just("["),
        st.just("{"),
    ),
).map(lambda t: t[0] + t[1] + t[2])

_near_crash_number = st.one_of(
    _crash_core,
    _crash_exp_family,
    _crash_in_context,
    _crash_with_fragment,
    st.tuples(
        st.sampled_from(["", "-", "+"]),
        st.sampled_from(["1", "0", "9", "1.0", "1.7976931348623157"]),
        st.sampled_from(["e", "E"]),
        st.integers(min_value=300, max_value=100000).map(str),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    st.tuples(
        st.sampled_from(["-1e", "-1E", "1e", "1E", "-0e", "0e"]),
        st.integers(min_value=300, max_value=100000).map(str),
    ).map(lambda t: t[0] + t[1]),
    st.just("-1e999999999"),
    st.just("-1e999999998"),
    st.just("-1e1000000000"),
    st.just("-1e99999999"),
    st.just("-1e9999999999"),
    st.just("-2e999999999"),
    st.just("-1e309"),
    st.just("-1e308"),
    st.just("-1e310"),
    st.just("-1E999999999"),
    st.just("-1e+999999999"),
    st.just("-1e-999999999"),
    st.just("-1.0e999999999"),
    st.just("-1e999999999000"),
    st.just("-1e9999999990"),
)

_number = st.one_of(
    _well_formed_number,
    _extreme_number,
    _near_crash_number,
    _malformed_number,
)

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null"])

# ---------- malformed structural fragments ----------

_malformed_fragment = st.sampled_from(
    [
        ",,",
        ",",
        ":",
        "::",
        "{,",
        "[,",
        "{:1}",
        "{1:2}",
        "[1,,2]",
        "[,]",
        "[,1]",
        "[1 2]",
        '{"a" 1}',
        '{"a":}',
        "{:}",
        "}",
        "]",
        "{",
        "[",
        '"',
        "\\",
        "1abc",
        "[]xyz",
        "true false",
        "{} {}",
        "nul",
        "tru",
        "fals",
        "{a:1}",
        "'x'",
        "//x",
        "/* */1",
        "\x00",
        "\x01\x02",
    ]
)

# ---------- recursive value ----------

def _pair(key_strategy):
    return st.tuples(key_strategy, st.just(":"), st.deferred(lambda: _value)).map(
        lambda t: t[0] + t[1] + t[2]
    )


_value = st.deferred(lambda: _value_strategy)

# Object with members (biased), empty object, and malformed object variants.
def _obj_strategy():
    key = _well_formed_string
    pair = st.tuples(key, st.just(":"), _value).map(lambda t: t[0] + t[1] + t[2])
    members = st.lists(pair, min_size=1, max_size=5)
    body_with_members = members.map(lambda ps: ",".join(ps))
    body_trailing_comma = members.map(lambda ps: ",".join(ps) + ",")
    body_dup_keys = st.tuples(
        st.lists(pair, min_size=1, max_size=3),
        st.just(","),
        st.lists(pair, min_size=1, max_size=3),
    ).map(lambda t: ",".join(t[0]) + t[1] + ",".join(t[2]))
    body_malformed = st.tuples(
        st.just('{"a":1'),
        _malformed_fragment,
    ).map(lambda t: t[0] + t[1])
    return st.one_of(
        st.just("{}"),
        body_with_members.map(lambda b: "{" + b + "}"),
        body_trailing_comma.map(lambda b: "{" + b + "}"),
        body_dup_keys.map(lambda b: "{" + b + "}"),
        body_malformed,
    )


def _arr_strategy():
    items = st.lists(_value, min_size=1, max_size=5)
    body = items.map(lambda vs: ",".join(vs))
    body_trailing = items.map(lambda vs: ",".join(vs) + ",")
    body_malformed = st.tuples(st.just("[1"), _malformed_fragment).map(lambda t: t[0] + t[1])
    return st.one_of(
        st.just("[]"),
        body.map(lambda b: "[" + b + "]"),
        body_trailing.map(lambda b: "[" + b + "]"),
        body_malformed,
    )


_value_strategy = st.one_of(
    _well_formed_string,
    _number,
    _literal,
    _obj_strategy(),
    _arr_strategy(),
    _malformed_fragment,
    _string,
)

# ---------- top-level strategy ----------

# Bias toward objects with members by weighting the object strategy heavily.
_top_object = _obj_strategy()
_top_array = _arr_strategy()

strategy = st.one_of(
    st.lists(_top_object, min_size=1, max_size=3).map(lambda xs: xs[0]),
    _top_object,
    _top_array,
    _value_strategy,
    _malformed_fragment,
    _near_crash_number,
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 5,
    "crash": 131,
    "reject": 3
  },
  "acceptance_rate": 0.036,
  "max_nesting_depth": 3,
  "productions_accepted": [
    "NUMBER",
    "json",
    "obj",
    "true",
    "value"
  ],
  "productions_gap": [
    "pair",
    "arr",
    "STRING",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 3,
  "divergences": 1,
  "divergence_examples": [
    "b'-1e999999999'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.