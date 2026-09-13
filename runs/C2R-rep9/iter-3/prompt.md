Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- small building blocks ----------

# JSON string escapes (valid escapes)
_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    # \uXXXX
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04x" % n),
    # surrogate escapes
    st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda n: "\\u%04x" % n),
)

# safe code points: anything except " \ and control chars 0x00-0x1F
_safe_cp = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# control bytes / NUL embedded raw (allowed by harness)
_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_string_body = st.one_of(
    st.lists(st.one_of(_escape, _safe_cp, _raw_control), max_size=12).map("".join),
    st.sampled_from([
        "",  # empty
        "a" * 50,
        "\u0000",           # raw NUL
        "\u0000\u0001\u0002",
        "\\uD800",          # lone high surrogate escape
        "\\uDC00",          # lone low surrogate escape
        "\\uD800\\uDC00",   # surrogate pair
        "\\u0000",          # escaped NUL
        "\\uFFFF",
        "\t\n\r",
    ]),
)

# A STRING token (with quotes). Sometimes deliberately unterminated.
_quoted_string = _string_body.map(lambda s: '"' + s + '"')

_unterminated_string = _string_body.map(lambda s: '"' + s)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=1, max_value=10**18).map(lambda n: "-" + str(n)),
)

_frac = st.integers(min_value=0, max_value=10**18).map(lambda n: "." + str(n))
_exp = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.integers(min_value=-400, max_value=400).map(lambda n: "E+" + str(abs(n))),
    st.integers(min_value=-400, max_value=400).map(lambda n: "e-" + str(abs(n))),
)

_valid_number = st.one_of(
    _int_part,
    st.tuples(_int_part, _frac).map(lambda t: t[0] + t[1]),
    st.tuples(_int_part, _exp).map(lambda t: t[0] + t[1]),
    st.tuples(_int_part, _frac, _exp).map(lambda t: "".join(t)),
    # extreme magnitudes
    st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e308", "1e999999",
        "0e0", "-0", "0.0", "-0.0",
        "123456789012345678901234567890",
        "1.7976931348623157e308",
        "5e-324",
    ]),
)

# Malformed / near-valid numbers the parser rejects (but still valuable)
_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "-01", "0x1F", "1e", "1e+", "1e-",
    "--1", "1..2", "1.2.3", "00", "007",
])

# lone '-' is accepted by the parser
_lenient_number = st.just("-")

# ---------- recursive value ----------

_json_str = st.deferred(lambda: _value)

_pair = st.tuples(_quoted_string, _json_str).map(lambda t: t[0] + ":" + t[1])

# bias toward objects with members
_obj = st.one_of(
    st.just("{}"),
    st.lists(_pair, min_size=1, max_size=6).map(lambda ps: "{" + ",".join(ps) + "}"),
    # duplicate keys
    st.tuples(_quoted_string, _json_str).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[1] + "}"
    ),
    # trailing comma (accepted once)
    st.lists(_pair, min_size=1, max_size=5).map(
        lambda ps: "{" + ",".join(ps) + ",}"
    ),
)

_arr = st.one_of(
    st.just("[]"),
    st.lists(_json_str, min_size=1, max_size=6).map(lambda vs: "[" + ",".join(vs) + "]"),
    st.lists(_json_str, min_size=1, max_size=5).map(
        lambda vs: "[" + ",".join(vs) + ",]"
    ),
)

# near-valid-but-malformed containers
_malformed = st.one_of(
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just("[,1]"),
    st.just("{,}"),
    st.just('{"a" 1}'),          # missing colon
    st.just('{"a":}'),           # missing value
    st.just('{:1}'),             # missing key
    st.just('{"a":1 "b":2}'),    # missing comma
    st.just("[1 2]"),
    st.just("{a:1}"),            # bare key
    st.just("'x'"),              # single quotes
    st.just("//x"),
    st.just("/* */1"),
    st.just("1abc"),
    st.just("[]xyz"),
    st.just("true false"),
    st.just("1 garbage"),
    _unterminated_string,
    st.just('{"a":"unterminated'),
    st.just("[1,2"),
    st.just('{"a":1'),
)

_value = st.one_of(
    _quoted_string,
    _valid_number,
    _bad_number,
    _lenient_number,
    _obj,
    _arr,
    _malformed,
    st.sampled_from(["true", "false", "null"]),
)

# ---------- top-level with deep nesting ----------

_deep_obj = st.integers(min_value=1, max_value=40).map(
    lambda n: "{" + '"a":{' * (n - 1) + '"a":0' + "}" * n
)

_deep_arr = st.integers(min_value=1, max_value=60).map(
    lambda n: "[" * n + "0" + "]" * n
)

_deep_mixed = st.integers(min_value=1, max_value=30).map(
    lambda n: ('{"k":[' * n) + "0" + ("]}" * n)
)

# ---------- near-crash intensification ----------
# The crashing signature is a UBSan null-pointer-offset inside the parse
# function. The divergence examples involve lone surrogate escapes
# (e.g. "\uD800") and strings mixing surrogate escapes with raw control
# bytes. Structurally mutate around those crashing inputs: embed lone
# surrogate escapes inside quoted strings, surround them with raw control
# bytes, wrap them in containers, and vary the surrounding context.

_lone_surrogate_esc = st.integers(min_value=0xD800, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)

# raw control byte that appeared in the divergence example
_raw_ctrl_byte = st.integers(min_value=0, max_value=0x1F).map(chr)

# A string whose body is a lone surrogate escape, optionally padded with
# raw control bytes and other escapes/characters on either side.
_surrogate_body = st.tuples(
    st.lists(
        st.one_of(_raw_ctrl_byte, _escape, _safe_cp), max_size=6
    ),
    _lone_surrogate_esc,
    st.lists(
        st.one_of(_raw_ctrl_byte, _escape, _safe_cp), max_size=6
    ),
).map(lambda t: "".join(t[0]) + t[1] + "".join(t[2]))

_surrogate_string = _surrogate_body.map(lambda s: '"' + s + '"')

# Also allow sequences of multiple lone surrogate escapes interleaved with
# raw control bytes, matching the second divergence example.
_multi_surrogate_string = st.lists(
    st.one_of(_lone_surrogate_esc, _raw_ctrl_byte), min_size=1, max_size=8
).map(lambda parts: '"' + "".join(parts) + '"')

# Wrap surrogate-bearing strings in container contexts so the parser walks
# into them via different code paths (value, pair, array element).
_surrogate_in_obj = st.tuples(
    _surrogate_string, _surrogate_body
).map(lambda t: "{" + t[0] + ':"' + t[1] + '"}')

_surrogate_in_arr = st.lists(
    st.one_of(_surrogate_string, _multi_surrogate_string), min_size=1, max_size=4
).map(lambda vs: "[" + ",".join(vs) + "]")

_near_crash = st.one_of(
    _surrogate_string,
    _multi_surrogate_string,
    _surrogate_in_obj,
    _surrogate_in_arr,
    # the exact divergence examples, plus close variants
    st.sampled_from([
        '"\\uD800"',
        '"\\uDC00"',
        '"\\uDBFF"',
        '"\\uDFFF"',
        '"\\u011e\x17\\u007d\x17\\u0370\\u0e4d"',
        '"\\uD800\\x17"',
        '"\\x17\\uD800"',
        '"\\uD800\\uDC00\\x17"',
        '{"a":"\\uD800"}',
        '["\\uD800"]',
        '["\\uDC00",\\uD800]',
    ]),
)

_top = st.one_of(
    _value,
    _deep_obj,
    _deep_arr,
    _deep_mixed,
    _near_crash,
    # whitespace-padded variants
    st.tuples(
        st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]),
        _value,
        st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

strategy = _top
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 14,
    "reject": 31,
    "crash": 7
  },
  "acceptance_rate": 0.269,
  "max_nesting_depth": 37,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "json",
    "obj",
    "value"
  ],
  "productions_gap": [
    "pair",
    "true",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 5,
  "divergences": 5,
  "divergence_examples": [
    "b'1e309'",
    "b'-1e309'",
    "b'{\"\\\\ud800\":\"\\\\ud800\"}'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.