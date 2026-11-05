Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _safe_char():
    # printable ASCII minus quote and backslash
    return st.characters(min_codepoint=0x20, max_codepoint=0x7e,
                         blacklist_characters='"\\')

def _escaped_string_body():
    pieces = st.one_of(
        _safe_char(),
        st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
        # \uXXXX
        st.integers(min_value=0, max_value=0xFFFF).map(lambda n: '\\u%04x' % n),
        # surrogate escapes (parser rejects lone ones)
        st.sampled_from(['\\ud800', '\\udc00', '\\udfff', '\\ud83d\\ude00']),
        # raw control / NUL bytes inside strings (parser accepts)
        st.sampled_from(['\x00', '\x01', '\x09', '\x0a', '\x1f']),
    )
    return st.lists(pieces, max_size=12).map(''.join)

def _string():
    return _escaped_string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _number():
    int_part = st.one_of(
        st.just('0'),
        st.integers(min_value=1, max_value=10**6).map(str),
        # leading zeros (accepted by parser)
        st.integers(min_value=0, max_value=10**6).map(lambda n: '0' + str(n)),
        st.sampled_from(['0x10', '0xdeadBEEF', '0X1f']),
    )
    frac = st.one_of(
        st.nothing(),
        st.integers(min_value=0, max_value=10**6).map(lambda n: '.' + str(n)),
        st.just('.'),  # trailing dot
    )
    exp = st.one_of(
        st.nothing(),
        st.tuples(
            st.sampled_from(['e', 'E']),
            st.sampled_from(['', '+', '-']),
            st.integers(min_value=0, max_value=10**4).map(str),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # extreme magnitudes
        st.sampled_from(['e309', 'e-309', 'E999', 'e+308', 'e-400']),
    )
    sign = st.one_of(st.nothing(), st.just('-'))
    return st.tuples(sign, int_part, frac, exp).map(
        lambda t: t[0] + t[1] + t[2] + t[3])

# ---------- recursive values ----------

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        # bias toward 'null' since it was the missing production
        st.sampled_from(['true', 'false', 'null', 'null', 'null']),
    )

def _value():
    return st.recursive(
        _leaf(),
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(lambda xs: '[' + ','.join(xs) + ']'),
            st.just('[]'),
            _pairs(children).map(lambda ps: '{' + ','.join(ps) + '}'),
            st.just('{}'),
        ),
        max_leaves=20,
    )

def _pairs(children):
    def one_pair(v):
        return st.tuples(_string(), st.just(':'), v).map(lambda t: t[0] + t[1] + t[2])
    return st.lists(one_pair(children), max_size=4)

# ---------- deep nesting near the 1000 limit ----------

def _deep(depth):
    depth = max(0, min(depth, 1200))
    return st.tuples(
        st.just('[' * depth),
        _value(),
        st.just(']' * depth),
    ).map(lambda t: t[0] + t[1] + t[2])

def _depth():
    return st.one_of(
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=990, max_value=1005),
        st.integers(min_value=995, max_value=1001),
    )

# ---------- malformed near-valid inputs ----------

def _malformed():
    return st.one_of(
        st.sampled_from([
            '[1,,2]', '[,]', '[1,]', '{"a":1,}', '{,}', '{"a"}',
            '{"a" 1}', '{"a":}', '{:1}', '"unterminated', "'single'",
            '{a:1}', '[1 2]', '-', '+1', '.5', '01', 'NaN', 'Infinity',
            '-Infinity', '1.', '0x', 'tru', 'nul', 'fals', '[]]', '{}}',
            '{"a":1 "b":2}', '\\', '"\x00', '"\\ud800"', '\ufeff',
            '1 2', '1abc', '\x00', '', '   ',
        ]),
        # double comma / missing colon generated
        st.tuples(_string(), st.just(','), _string()).map(
            lambda t: '{' + t[0] + t[1] + t[2] + '}'),
        st.tuples(_value(), st.just(','), st.just(','), _value()).map(
            lambda t: '[' + t[0] + t[1] + t[2] + t[3] + ']'),
    )

# ---------- top-level strategy ----------

def _top():
    return st.one_of(
        _value(),
        _depth().flatmap(_deep),
        _malformed(),
        # BOM prefix
        _value().map(lambda s: '\ufeff' + s),
        # trailing content after a complete value
        st.tuples(_value(), _leaf()).map(lambda t: t[0] + t[1]),
        # embedded NUL after value
        _value().map(lambda s: s + '\x00'),
        # empty containers exercising null
        st.sampled_from(['null', '[null]', '{"a":null}', '[null,null]',
                         '{"a":null,"b":null}']),
    )

strategy = _top()
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 123,
    "reject": 227
  },
  "acceptance_rate": 0.351,
  "max_nesting_depth": 1005,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "json",
    "null",
    "obj",
    "pair",
    "value"
  ],
  "productions_gap": [
    "true",
    "false"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 22,
  "divergences": 81,
  "divergence_examples": [
    "b'\\xef\\xbb\\xbf\"\"'",
    "b'\\xef\\xbb\\xbf-0575.14431e700'",
    "b'\\xef\\xbb\\xbf-0700.14431e700'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.