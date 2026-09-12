Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.text(alphabet=_hex, min_size=4, max_size=4)

def _unicode_escape():
    return st.builds(lambda h: "\\u" + h, _hex4())

def _simple_escape():
    return st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _escape():
    return st.one_of(_simple_escape(), _unicode_escape())

# control bytes and NUL allowed inside strings
_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_safe_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(
        lambda c: c not in '"\\'
    ),
    _control,
)

_string_body = st.one_of(_escape(), _safe_char)

def _string():
    return st.lists(_string_body, max_size=12).map(lambda cs: '"' + "".join(cs) + '"')

def _unterminated_string():
    return st.lists(_string_body, min_size=1, max_size=8).map(
        lambda cs: '"' + "".join(cs)
    )

# numbers: valid + edge + malformed
_int_part = st.one_of(
    st.just("0"),
    st.tuples(
        st.integers(min_value=1, max_value=9),
        st.text(alphabet="0123456789", max_size=18),
    ).map(lambda t: str(t[0]) + t[1]),
)

_frac = st.text(alphabet="0123456789", min_size=1, max_size=18).map(lambda s: "." + s)

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map(lambda t: t[0] + t[1] + t[2])

def _number():
    return st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.none(), _frac),
        st.one_of(st.none(), _exp),
    ).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or ""))

def _extreme_number():
    return st.one_of(
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-309"),
        st.just("1e999999"),
        st.just("0e0"),
        st.just("-"),
        st.just("1e01"),
        st.just("1E+01"),
        st.just("1234567890123456789012345678901234567890"),
        st.just("1.7976931348623157e309"),
        st.just("2.2250738585072014e-308"),
        st.just("1e-999999"),
    )

def _malformed_number():
    return st.one_of(
        st.just("+1"),
        st.just(".5"),
        st.just("1."),
        st.just("01"),
        st.just("00"),
        st.just("0x1F"),
        st.just("-01"),
        st.just("1e"),
        st.just("1e+"),
        st.just("--1"),
        st.just("1..2"),
        st.just("1ee2"),
    )

# ---------- recursive values ----------

def _leaf_value():
    return st.one_of(
        _string(),
        _number(),
        _extreme_number(),
        _malformed_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        # malformed literals
        st.just("True"),
        st.just("nul"),
        st.just("NULL"),
        _unterminated_string(),
    )

def _key():
    return st.one_of(
        _string(),
        _string(),
        _string(),
        st.just('"a"'),
        st.just('"a"'),
        st.just('"\\u0000"'),
        st.just('"\\ud800"'),
        st.just('"\\udfff"'),
        st.just('"\\ud800\\udc00"'),
        st.just('"\x00"'),
        st.just('"\x01"'),
        st.just('"\x1f"'),
        _unterminated_string(),
    )

def _pair(value_st):
    return st.tuples(_key(), value_st).map(lambda t: t[0] + ":" + t[1])

def _obj(value_st):
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(value_st), min_size=1, max_size=6).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        # trailing comma
        st.lists(_pair(value_st), min_size=1, max_size=6).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        ),
        # duplicate keys
        st.tuples(_key(), value_st).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[1] + "}"),
        # malformed: missing colon
        st.tuples(_key(), value_st).map(lambda t: "{" + t[0] + t[1] + "}"),
        # malformed: double comma
        st.tuples(_pair(value_st), _pair(value_st)).map(
            lambda t: "{" + t[0] + ",," + t[1] + "}"
        ),
        # malformed: leading comma
        st.tuples(_pair(value_st),).map(lambda t: "{," + t[0] + "}"),
        # unterminated
        st.tuples(_pair(value_st),).map(lambda t: "{" + t[0]),
        st.just("{"),
    )

def _arr(value_st):
    return st.one_of(
        st.just("[]"),
        st.lists(value_st, min_size=1, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(value_st, min_size=1, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
        st.lists(value_st, min_size=2, max_size=6).map(
            lambda vs: "[" + vs[0] + ",," + ",".join(vs[1:]) + "]"
        ),
        st.lists(value_st, min_size=1, max_size=6).map(
            lambda vs: "[," + ",".join(vs) + "]"
        ),
        st.lists(value_st, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs)
        ),
        st.just("["),
        st.just("[,]"),
    )

def _value():
    return st.recursive(
        _leaf_value(),
        lambda children: st.one_of(_obj(children), _arr(children)),
        max_leaves=20,
    )

# ---------- deep nesting ----------

def _deep_obj(depth):
    return st.just("{" + '"a":' * depth + "null" + "}" * depth)

def _deep_arr(depth):
    return st.just("[" * depth + "null" + "]" * depth)

def _deep_mixed(depth):
    return st.just(("[{\"a\":" * depth) + "0" + ("}]" * depth))

_deep = st.one_of(
    st.integers(min_value=1, max_value=8).flatmap(_deep_obj),
    st.integers(min_value=1, max_value=8).flatmap(_deep_arr),
    st.integers(min_value=1, max_value=6).flatmap(_deep_mixed),
    st.integers(min_value=100, max_value=2000).flatmap(_deep_arr),
    st.integers(min_value=100, max_value=1000).flatmap(_deep_obj),
)

# ---------- control-byte / NUL noise ----------

_control_noise = st.lists(
    st.integers(min_value=0, max_value=0x1F).map(chr),
    min_size=1,
    max_size=8,
).map(lambda cs: "".join(cs))

# ---------- near-crash mutations around b'-' ----------

# The crashing input was a lone '-' (b'-'). Intensify structural mutations
# around that exact byte: prefixes/suffixes, repeats, and nearby numeric
# fragments that push the parser into the same near-crash code path.

def _near_crash_mutation():
    return st.one_of(
        # exact crash seed
        st.just("-"),
        # lone sign variants
        st.just("+"),
        st.just("--"),
        st.just("---"),
        st.just("+"),
        st.just("++"),
        # sign with trailing whitespace / controls
        st.tuples(st.just("-"), _control_noise).map(lambda t: t[0] + t[1]),
        st.tuples(_control_noise, st.just("-")).map(lambda t: t[0] + t[1]),
        st.tuples(_control_noise, st.just("-"), _control_noise).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        # sign with leading/trailing whitespace
        st.tuples(_ws, st.just("-"), _ws).map(lambda t: t[0] + t[1] + t[2]),
        # sign followed by partial number fragments
        st.sampled_from([
            "-0", "-0.", "-0.0", "-0e", "-0e0", "-0e+", "-0e-",
            "-e", "-e0", "-e+0", "-e-0",
            "-.", "-.0", "-..", "-.e",
            "-1", "-1.", "-1e", "-1e+", "-1e-", "-1ee",
            "-1.2.3", "-1..2",
        ]),
        # sign embedded in containers
        st.just("[-]"),
        st.just("[-,"),
        st.just("[,-]"),
        st.just("[-,-]"),
        st.just("{\"a\":-}"),
        st.just("{\"a\":-,}"),
        st.just("{\"a\":-"),
        st.just("{\"a\":-}"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
        # sign preceded/followed by other tokens
        st.tuples(st.just("-"), _value()).map(lambda t: t[0] + t[1]),
        st.tuples(_value(), st.just("-")).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("-"), st.just("-"), _value()).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        # repeated lone signs with noise
        st.lists(
            st.one_of(st.just("-"), _control_noise),
            min_size=1,
            max_size=8,
        ).map(lambda cs: "".join(cs)),
        # sign with deep nesting
        st.tuples(st.just("-"), _deep).map(lambda t: t[0] + t[1]),
        st.tuples(_deep, st.just("-")).map(lambda t: t[0] + t[1]),
        # sign at boundaries of arrays/objects
        st.just("[-]"),
        st.just("[-]"),
        st.just("[-]"),
    )

# ---------- top-level ----------

_ws = st.text(alphabet=" \t\n\r", max_size=4)

def _top_level():
    return st.one_of(
        # well-formed values
        _value(),
        # values wrapped in whitespace
        st.tuples(_ws, _value(), _ws).map(lambda t: t[0] + t[1] + t[2]),
        # deep nesting
        _deep,
        # trailing content (rejected)
        st.tuples(_value(), st.sampled_from(["abc", " xyz", " garbage", "false", "null"])).map(
            lambda t: t[0] + t[1]
        ),
        # NUL / control noise
        _control_noise,
        st.tuples(_value(), _control_noise).map(lambda t: t[0] + t[1]),
        st.tuples(_control_noise, _value()).map(lambda t: t[0] + t[1]),
        # empty / trivial
        st.just(""),
        st.just(" "),
        st.just("\x00"),
        st.just("{}"),
        st.just("[]"),
        st.just("null"),
        st.just("true"),
        st.just("false"),
        st.just("-"),
        st.just("1e309"),
        # malformed top-level
        st.just("{,}"),
        st.just("[,,]"),
        st.just("{\"a\"}"),
        st.just("{\"a\":}"),
        st.just("{:1}"),
        st.just("[1 2]"),
        st.just("{\"a\" 1}"),
        st.just('"unterminated'),
        st.just("'single'"),
        st.just("{a:1}"),
        st.just("//x\n1"),
        st.just("/* */1"),
        st.just("+1"),
        st.just(".5"),
        st.just("01"),
        # intensified near-crash mutations around b'-'
        _near_crash_mutation(),
    )

strategy = _top_level()
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 6,
    "reject": 10,
    "crash": 5
  },
  "acceptance_rate": 0.286,
  "max_nesting_depth": 0,
  "productions_accepted": [
    "STRING",
    "json",
    "value"
  ],
  "productions_gap": [
    "obj",
    "pair",
    "arr",
    "NUMBER",
    "true",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 2,
  "divergences": 5,
  "divergence_examples": [
    "b'-'",
    "b'[-]'",
    "b'[-]'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.