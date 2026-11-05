Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- scalar building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_unicode_escape = _hex4().map(lambda h: "\\u" + h)

def _surrogate_escapes():
    hi = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda n: "\\u%04x" % n)
    lo = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda n: "\\u%04x" % n)
    pair = st.tuples(hi, lo).map(lambda t: t[0] + t[1])
    return st.one_of(hi, lo, pair)

_invalid_escapes = st.sampled_from(['\\x', '\\u12', '\\uZZZZ', '\\', '\\q', '\\U0041'])

_raw_printable = st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                               blacklist_characters='"\\')
_raw_control = st.integers(min_value=0x00, max_value=0x1F).map(chr)
_raw_high = st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF,
                          blacklist_categories=("Cs",))

def _string_body():
    pieces = st.one_of(
        _raw_printable,
        _raw_control,
        _raw_high,
        _simple_escapes,
        _unicode_escape,
        _surrogate_escapes(),
        _invalid_escapes,
    )
    return st.lists(pieces, max_size=8).map(lambda xs: "".join(xs))

def _valid_string():
    return _string_body().map(lambda b: '"' + b + '"')

def _unterminated_string():
    return _string_body().map(lambda b: '"' + b)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        _nonzero_digits,
        st.tuples(st.just("0"), _digits).map(lambda t: t[0] + t[1]),
    )

def _frac_part():
    return _digits.map(lambda d: "." + d)

def _exp_part():
    sign = st.sampled_from(["", "+", "-"])
    return st.tuples(st.sampled_from(["e", "E"]), sign, _digits).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _number():
    sign = st.sampled_from(["", "-"])
    base = _int_part()
    frac = st.one_of(st.none(), _frac_part(), st.just("."))
    exp = st.one_of(st.none(), _exp_part())
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e308", "-1e308",
        "1e9999", "1e-9999", "0e0", "-0", "0.0e-0",
        "123456789012345678901234567890",
    ])
    composed = st.tuples(sign, base, frac, exp).map(
        lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or "")
    )
    return st.one_of(extreme, composed)

_bad_number = st.sampled_from([
    "-", "+1", ".5", "-.5", "1..2", "1e", "1e+", "1e-", "--1",
    "0x", "NaN", "Infinity", "-Infinity", "1.2.3", "e5",
])

# ---------- recursive values ----------

def _value_base():
    # bias toward well-formed scalars so NUMBER/false/null get exercised
    scalar = st.one_of(
        _valid_string(),
        _number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )
    malformed = st.one_of(_bad_number, _unterminated_string())
    return st.one_of(
        st.tuples(st.just(0), scalar).map(lambda t: t[1]),
        st.tuples(st.just(1), scalar).map(lambda t: t[1]),
        st.tuples(st.just(2), scalar).map(lambda t: t[1]),
        st.tuples(st.just(3), malformed).map(lambda t: t[1]),
    )

def _arr(children):
    def build(items):
        return "[" + ",".join(items) + "]"
    return st.one_of(
        st.just("[]"),
        st.lists(children, min_size=1, max_size=5).map(build),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[" + ",".join(xs) + ",]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[" + ",,".join(xs) + "]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[," + ",".join(xs) + "]"
        ),
    )

def _obj(children):
    def pair(v):
        return st.tuples(_valid_string(), v).map(lambda t: t[0] + ":" + t[1])

    def build(pairs):
        return "{" + ",".join(pairs) + "}"

    return st.one_of(
        st.just("{}"),
        st.lists(pair(st.one_of(children)), min_size=1, max_size=5).map(build),
        st.tuples(_valid_string(), st.one_of(children)).map(
            lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[1] + "}"
        ),
        st.tuples(_valid_string(), st.one_of(children)).map(
            lambda t: "{" + t[0] + t[1] + "}"
        ),
        st.lists(pair(st.one_of(children)), min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        ),
        st.lists(pair(st.one_of(children)), min_size=1, max_size=4).map(
            lambda ps: "{" + ",,".join(ps) + "}"
        ),
    )

_base_value = _value_base()

_recursive_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        _arr(children),
        _obj(children),
    ),
    max_leaves=20,
)

# ---------- deep nesting near the 1000 limit ----------

def _deep_nesting():
    depth = st.integers(min_value=995, max_value=1005)
    open_bracket = st.sampled_from(["[", "{"])
    close_bracket = st.sampled_from(["]", "}"])

    def build(t):
        d, o, c = t
        opens = "".join(o if i % 2 == 0 else ("{" if o == "[" else "[") for i in range(d))
        closes = "".join(c if i % 2 == 0 else ("}" if c == "]" else "]") for i in range(d))
        if o == "[":
            inner = "0"
        else:
            inner = '"k":0'
        return opens + inner + closes

    return st.tuples(depth, open_bracket, close_bracket).map(build)

def _deep_nesting_exact(depth, kind):
    if kind == "arr":
        return "[" * depth + "0" + "]" * depth
    else:
        return '{"k":' * depth + "0" + "}" * depth

# ---------- top-level composition ----------

# bias toward well-formed top-level values to lift acceptance rate
_top_level = st.one_of(
    st.tuples(st.just(0), _recursive_value).map(lambda t: t[1]),
    st.tuples(st.just(1), _recursive_value).map(lambda t: t[1]),
    st.tuples(st.just(2), _recursive_value).map(lambda t: t[1]),
    st.tuples(st.just(3), _deep_nesting()).map(lambda t: t[1]),
    st.tuples(st.just(4), _recursive_value).map(lambda t: "\ufeff" + t[1]),
    st.tuples(st.just(5), _recursive_value,
              st.sampled_from(["", "abc", " 1 2", "\x00", "}]"])).map(
        lambda t: t[1] + t[2]
    ),
    st.just(""),
    st.text(alphabet=" \t\n\r", min_size=1, max_size=8),
    st.tuples(st.just(6), _recursive_value).map(lambda t: t[1] + "\x00"),
    _bad_number,
    _unterminated_string(),
    st.sampled_from([",", "]", "}", ":", ",,", "[,]", "{,}", "tru", "nul", "fals"]),
)

strategy = _top_level
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 51,
    "reject": 299
  },
  "acceptance_rate": 0.146,
  "max_nesting_depth": 1,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "json",
    "obj",
    "pair",
    "true",
    "value"
  ],
  "productions_gap": [
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 9,
  "divergences": 28,
  "divergence_examples": [
    "b'\"\"\\x00'",
    "b'\\xef\\xbb\\xbf\"\"'",
    "b'1e'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.