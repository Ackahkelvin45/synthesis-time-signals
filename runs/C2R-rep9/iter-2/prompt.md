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

_top = st.one_of(
    _value,
    _deep_obj,
    _deep_arr,
    _deep_mixed,
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
    "valid": 10,
    "reject": 7,
    "crash": 6
  },
  "acceptance_rate": 0.435,
  "max_nesting_depth": 30,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "json",
    "null",
    "obj",
    "value"
  ],
  "productions_gap": [
    "pair",
    "arr",
    "true",
    "false"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 5,
  "divergences": 2,
  "divergence_examples": [
    "b'\"\\\\uD800\"'",
    "b'\"\\\\u011e\\x17\\\\u007d\\x17\\\\u0370\\\\u0e4d\"'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.