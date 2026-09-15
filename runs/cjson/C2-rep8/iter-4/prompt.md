Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- leaf pieces ----------

_hex = "0123456789abcdefABCDEF"

def _u_escape():
    return st.tuples(
        st.sampled_from(_hex),
        st.sampled_from(_hex),
        st.sampled_from(_hex),
        st.sampled_from(_hex),
    ).map(lambda t: "\\u" + "".join(t))

def _escaped_char():
    return st.one_of(
        st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
        _u_escape(),
    )

def _raw_char():
    # safe codepoints plus raw control / NUL bytes (parser accepts them)
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                      blacklist_categories=("Cs",),
                      blacklist_characters='"\\'),
        st.characters(min_codepoint=0x00, max_codepoint=0x1F),
        st.just("\x00"),
    )

def _string_body():
    return st.lists(
        st.one_of(_escaped_char(), _raw_char()),
        max_size=12,
    ).map(_join)

def _string():
    return st.builds(lambda b: '"' + b + '"', _string_body())

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=10, max_value=10**18).map(str),
        # leading zeros (accepted by parser)
        st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
    )

def _frac_part():
    return st.one_of(
        st.integers(min_value=0, max_value=10**18).map(lambda n: "." + str(n)),
        st.just("."),  # trailing dot: accepted
    )

def _exp_part():
    return st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.one_of(
            st.integers(min_value=0, max_value=400).map(str),
            st.just("309"),
            st.just("999"),
        ),
    ).map(_join)

def _number():
    sign = st.sampled_from(["", "-"])
    intp = _int_part()
    frac = st.one_of(st.none(), _frac_part())
    exp = st.one_of(st.none(), _exp_part())
    return st.tuples(sign, intp, frac, exp).map(
        lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or "")
    )

def _weird_number():
    return st.one_of(
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-999"),
        st.just("0x10"),
        st.just("-0x1F"),
        st.just("1."),
        st.just("01"),
        st.just("-01"),
        st.just("1e01"),
    )

# ---------- malformed fragments ----------

def _malformed():
    return st.one_of(
        st.just(","),
        st.just(":"),
        st.just("{"),
        st.just("}"),
        st.just("["),
        st.just("]"),
        st.just('"unterminated'),
        st.just("'single'"),
        st.just("NaN"),
        st.just("Infinity"),
        st.just("-Infinity"),
        st.just("+1"),
        st.just(".5"),
        st.just("-"),
        st.just("tru"),
        st.just("nul"),
        st.just("fals"),
        st.just("1abc"),
        st.just("1 2"),
        st.just("\x00"),
        st.just("\ufeff1"),
        st.just('"\\ud800"'),
        st.just('"\\uD800"'),
    )

# ---------- recursive structure ----------

def _bom():
    return st.just("\ufeff")

def _make_value(children):
    leaf = st.one_of(
        _string(),
        _number(),
        _weird_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )
    return st.one_of(
        leaf,
        children,
        _malformed(),
    )

def _obj(children):
    pair = st.tuples(
        _string(),
        st.just(":"),
        children,
    ).map(_join)
    # empty, single, and multi-pair objects; duplicate keys arise naturally
    return st.one_of(
        st.just("{}"),
        st.tuples(st.just("{"), pair, st.just("}")).map(_join),
        st.lists(pair, min_size=2, max_size=6).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        # malformed: trailing comma, missing colon
        st.tuples(st.just("{"), pair, st.just(",}")).map(_join),
        st.tuples(st.just("{"), _string(), children, st.just("}")).map(_join),
    )

def _arr(children):
    return st.one_of(
        st.just("[]"),
        st.tuples(st.just("["), children, st.just("]")).map(_join),
        st.lists(children, min_size=2, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        # malformed: double comma, trailing comma
        st.tuples(st.just("["), children, st.just(",]")).map(_join),
        st.tuples(st.just("["), children, st.just(",,"), children, st.just("]")).map(_join),
    )

# ---------- deep nesting near the 1000 limit ----------

def _deep_arr(depth):
    return "[" * depth + "1" + "]" * depth

def _deep_obj(depth):
    return '{"a":' * depth + "1" + "}" * depth

def _deep_nesting():
    return st.one_of(
        st.integers(min_value=0, max_value=1000).map(_deep_arr),
        st.integers(min_value=0, max_value=1000).map(_deep_obj),
        st.sampled_from([_deep_arr(998), _deep_arr(999), _deep_arr(1000),
                         _deep_arr(1001), _deep_arr(1002),
                         _deep_obj(998), _deep_obj(999), _deep_obj(1000),
                         _deep_obj(1001)]),
    )

# ---------- top-level ----------

_value = st.recursive(
    st.one_of(
        _string(),
        _number(),
        _weird_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _malformed(),
    ),
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=15,
)

# Upweight the boolean/null literals so the parser's true/false/null
# productions get exercised (they were missing from accepted productions).
_literal = st.sampled_from(["true", "false", "null"])

_top = st.one_of(
    _value,
    _literal,
    st.tuples(st.just("["), _literal, st.just("]")).map(_join),
    st.tuples(st.just('{"k":'), _literal, st.just("}")).map(_join),
    st.lists(_literal, min_size=2, max_size=6).map(lambda vs: "[" + ",".join(vs) + "]"),
    _deep_nesting(),
    # BOM-prefixed values (accepted)
    st.tuples(_bom(), _value).map(_join),
    # trailing content after a valid value (accepted)
    st.tuples(_value, st.sampled_from(["abc", " 1 2", "\x00", "xyz"])).map(_join),
)

strategy = _top
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 165,
    "reject": 185
  },
  "acceptance_rate": 0.471,
  "max_nesting_depth": 1002,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "false",
    "json",
    "null",
    "obj",
    "pair",
    "true",
    "value"
  ],
  "productions_gap": [],
  "cap_distance_mass": 0.018,
  "novelty": 22,
  "divergences": 47,
  "divergence_examples": [
    "b'\"\"abc'",
    "b'[\"\",\"\"]abc'",
    "b'\\xef\\xbb\\xbf\"\"'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **generate_nesting_toward_cap** — target depth 700-950.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.