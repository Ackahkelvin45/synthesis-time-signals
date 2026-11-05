Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

_safe_chars = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " _-.,:;!?@#$%^&*()+=<>/|~`'"
)

_escapes = [
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u0001", "\\u001f", "\\u007f", "\\u00e9", "\\u20ac",
    "\\uD800", "\\uDC00", "\\uD83D", "\\uDE00", "\\uFFFF", "\\u000a",
]

def _string_body():
    return st.one_of(
        st.text(alphabet=_safe_chars, min_size=0, max_size=12),
        st.sampled_from(_escapes),
        st.lists(
            st.one_of(
                st.text(alphabet=_safe_chars, min_size=0, max_size=6),
                st.sampled_from(_escapes),
            ),
            min_size=0,
            max_size=4,
        ).map(lambda parts: "".join(parts)),
    )

def _string():
    return _string_body().map(lambda body: '"' + body + '"')

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=18)

def _number():
    sign = st.sampled_from(["", "-"])
    intpart = st.one_of(
        st.just("0"),
        st.from_regex(r"[1-9][0-9]{0,17}", fullmatch=True),
        _int_digits,
    )
    frac = st.one_of(
        st.just(""),
        st.tuples(st.just("."), _int_digits).map(lambda t: t[0] + t[1]),
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.text(alphabet="0123456789", min_size=1, max_size=4),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )
    normal = st.tuples(sign, intpart, frac, exp).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e999999", "1E+999", "-0e-999",
        "1.7976931348623159e308", "2.2250738585072014e-308",
        "1e-400", "0.0", "-0", "1e0", "123456789012345678901234567890",
        "1.0e308", "5e-324", "1e308",
    ])
    return st.one_of(normal, extreme)

def _literal():
    return st.sampled_from(["true", "false", "null"])

# ---------- malformed / near-valid fragments ----------

def _broken_string():
    return st.one_of(
        st.just('"'),
        st.just('"abc'),
        st.just('"abc\\'),
        st.just('"\\u12"'),
        st.just('"\\uZZZZ"'),
        st.just('"\\q"'),
        st.just('"unterminated'),
        st.tuples(
            st.just('"'),
            st.text(alphabet=_safe_chars, min_size=0, max_size=8),
        ).map(lambda t: t[0] + t[1]),
    )

def _broken_number():
    return st.sampled_from([
        "+1", ".5", "1.", "01", "00", "-.5", "-01", "+.5",
        "-", "-.", "1e", "1e+", "1e-", "0x10", "Infinity", "-Infinity",
        "NaN", "1..2", "--1", "1.2.3", "1e1e1",
    ])

# ---------- recursive JSON value ----------

def _value_leaf():
    return st.one_of(_string(), _number(), _literal())

def _build_value(children):
    return st.one_of(
        _value_leaf(),
        _obj(children),
        _arr(children),
    )

def _pair(value_st):
    key = _string()
    return st.tuples(key, st.just(":"), value_st).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _obj(value_st):
    empty = st.just("{}")
    nonempty = st.lists(
        _pair(value_st), min_size=1, max_size=5
    ).map(lambda pairs: "{" + ",".join(pairs) + "}")
    return st.one_of(empty, nonempty)

def _arr(value_st):
    empty = st.just("[]")
    nonempty = st.lists(
        value_st, min_size=1, max_size=6
    ).map(lambda items: "[" + ",".join(items) + "]")
    return st.one_of(empty, nonempty)

_value = st.recursive(
    _value_leaf(),
    _build_value,
    max_leaves=20,
)

# ---------- deep nesting near the 2048 cap ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=2100)
    kind = st.sampled_from(["arr", "obj"])

    def build(d, k):
        if k == "arr":
            return "[" * d + "]" * d
        return '{"a":' * d + "0" + "}" * d

    return st.tuples(depth, kind).map(lambda t: build(t[0], t[1]))

# ---------- malformed top-level inputs ----------

def _malformed():
    return st.one_of(
        st.just("[1,,2]"),
        st.just("{,}"),
        st.just('{"a":1,}'),
        st.just("[1,2,]"),
        st.just('{"a" 1}'),
        st.just('{"a"}'),
        st.just("{:1}"),
        st.just("[,]"),
        st.just("{}}"),
        st.just("[]]"),
        st.just("[1 2]"),
        st.just('{"a":1 "b":2}'),
        _broken_string(),
        _broken_number(),
        st.tuples(
            _value, st.text(min_size=1, max_size=8)
        ).map(lambda t: t[0] + t[1]),
    )

# ---------- duplicate keys ----------

def _duplicate_keys():
    return st.tuples(
        _string(),
        _value,
        _value,
    ).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}")

# ---------- whitespace wrapping ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

def _padded(value_st):
    return st.tuples(_ws, value_st, _ws).map(
        lambda t: t[0] + t[1] + t[2]
    )

# ---------- top-level strategy ----------

strategy = st.one_of(
    _padded(_value),
    _deep_nesting(),
    _malformed(),
    _duplicate_keys(),
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("0"),
    st.just("-"),
    st.just("1e309"),
    # boost near-cap nesting mass (cap_distance_mass was very low)
    st.tuples(
        st.integers(min_value=1900, max_value=2100),
        st.sampled_from(["arr", "obj"]),
    ).map(lambda t: ("[" * t[0] + "]" * t[0])
          if t[1] == "arr"
          else ('{"a":' * t[0] + "0" + "}" * t[0])),
    # empty / whitespace-only and bare trailing-junk near-valid inputs
    st.sampled_from(["", " ", "\n", "\t", "  \n\t ", "\r\n"]),
    st.tuples(_ws, _value, st.sampled_from(["]", "}", ",", ":", "x", "0"]))
        .map(lambda t: t[0] + t[1] + t[2]),
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 174,
    "reject": 176
  },
  "acceptance_rate": 0.497,
  "max_nesting_depth": 2093,
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
  "cap_distance_mass": 0.109,
  "novelty": 14,
  "divergences": 164,
  "divergence_examples": [
    "b'\"\"0'",
    "b'-9.54D=3P\\xc3\\x8b'",
    "b'{\"a\":1,}'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.