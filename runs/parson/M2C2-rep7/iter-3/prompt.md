Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# Primitive building blocks

# Safe character for unescaped content inside JSON strings:
# - exclude double-quote and backslash which must be escaped
# - exclude the raw NUL character '\x00' (the harness cannot handle raw NUL)
_safe_char = st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_characters=['"', '\\', '\x00'])

# Escape fragments that may appear inside JSON strings
_escape_simple = st.sampled_from(['\\b', '\\f', '\\n', '\\r', '\\t', '\\"', '\\\\', '\\/'])
# Unicode escape like \uXXXX (hex chars)
_unicode_escape = st.builds(lambda s: '\\u' + s, st.text('0123456789abcdefABCDEF', min_size=4, max_size=4))
# Surrogate high/low style escapes (explicitly include some common surrogate codepoints)
_surrogate_escape = st.sampled_from(['\\uD800', '\\uD801', '\\uDFFF', '\\uDBFF', '\\uDC00'])

_segment = st.one_of(_safe_char.map(lambda c: c), _escape_simple, _unicode_escape, _surrogate_escape)

@st.composite
def json_string(draw, allow_unterminated=False):
    """
    Produce a JSON string value (including quotes). Sometimes emit an unterminated
    string if allow_unterminated=True to exercise near-valid-but-malformed inputs.
    The strategy never produces a raw NUL character.
    """
    # number of segments
    n = draw(st.integers(min_value=0, max_value=20))
    segments = draw(st.lists(_segment, min_size=n, max_size=n))
    content = ''.join(segments)
    # Occasionally inject a long sequence of escapes (e.g. many \uXXXX) to hit edgecases.
    if draw(st.booleans()):
        extra = draw(st.lists(st.one_of(_unicode_escape, _surrogate_escape), min_size=0, max_size=5))
        if extra:
            # append some unicode escapes
            content = content + ''.join(extra)
    # sometimes insert an embedded \u0000 (six-char escape), which is allowed
    if draw(st.booleans()):
        if draw(st.integers(min_value=0, max_value=4)) == 0:
            content = content + '\\u0000'
    s = '"' + content
    if allow_unterminated and draw(st.booleans()):
        # omit the closing quote (unterminated string)
        return s
    return s + '"'

# Number generator: valid and near-valid/malformed variants
@st.composite
def json_number(draw):
    """
    Generate numeric lexical forms: valid JSON numbers and near-valid/malformed forms.
    Include extreme magnitudes (like 1e309), leading zeros, leading +, .5, trailing dot, etc.
    """
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        # small integers, valid
        i = draw(st.integers(min_value=0, max_value=2**31))
        return str(i)
    elif choice == 1:
        # negative integer
        i = draw(st.integers(min_value=0, max_value=2**31))
        return "-" + str(i)
    elif choice == 2:
        # decimal with fractional part (valid)
        intpart = draw(st.one_of(st.just('0'), st.integers(min_value=1, max_value=9999999).map(str)))
        frac = draw(st.text('0123456789', min_size=1, max_size=10))
        return intpart + "." + frac
    elif choice == 3:
        # exponent forms (valid typical)
        intpart = draw(st.one_of(st.just('0'), st.integers(min_value=1, max_value=9999).map(str)))
        exp = draw(st.integers(min_value=-400, max_value=400))
        # format with e
        return intpart + "e" + ("+" if exp >= 0 and draw(st.booleans()) else "") + str(exp)
    elif choice == 4:
        # extreme exponent that overflows (near-valid lexical)
        base = draw(st.one_of(st.just('1'), st.just('9'), st.floats(min_value=1.0, max_value=1e10).map(lambda f: ('%g' % f))))
        return "1e309"
    elif choice == 5:
        # leading plus, which is near-valid (parser may accept)
        n = draw(st.integers(min_value=0, max_value=12345))
        return "+" + str(n)
    elif choice == 6:
        # fractional without leading zero (".5")
        frac = draw(st.text('0123456789', min_size=1, max_size=6))
        return "." + frac
    elif choice == 7:
        # invalid leading zero variant "01"
        rest = draw(st.integers(min_value=0, max_value=99))
        return "0" + str(rest)
    elif choice == 8:
        # trailing dot (e.g. "1.")
        i = draw(st.integers(min_value=0, max_value=9999))
        return str(i) + "."
    else:
        # lone sign or dot variants
        return draw(st.sampled_from(["-", "-.", "+.", "+", "NaN", "Infinity", "-Infinity"]))

# Base (non-recursive) values: strings, numbers, true/false/null, and malformed primitives.
base_value = st.one_of(
    json_string().map(lambda s: s),
    json_string(allow_unterminated=True).map(lambda s: s),  # unterminated strings sometimes
    json_number(),
    st.sampled_from(["true", "false", "null"]),
    # some explicit near-valid or malformed tokens
    st.sampled_from(["", " ", "\t", "\n", "0x1", "0b101", "1abc"])
)

# Object and array constructors for recursion
def _obj_strategy(inner):
    @st.composite
    def _make_obj(draw):
        mode = draw(st.integers(min_value=0, max_value=6))
        if mode == 0:
            # empty object {}
            return "{}"
        # produce a pool of keys (valid JSON strings only)
        pool_size = draw(st.integers(min_value=1, max_value=3))
        key_pool = [draw(json_string()) for _ in range(pool_size)]
        # choose number of pairs
        n = draw(st.integers(min_value=1, max_value=6))
        pairs = []
        for _ in range(n):
            # sometimes reuse keys to create duplicates
            if draw(st.booleans()):
                key = draw(st.sampled_from(key_pool))
            else:
                key = draw(json_string())
            val = draw(inner)
            pairs.append((key, val))
        # build normal object
        core = ','.join(k + ':' + v for (k, v) in pairs)
        obj = "{" + core + "}"
        # Now inject malformed variants with small probability
        if mode == 1:
            # trailing comma
            if pairs:
                return "{" + ','.join(k + ':' + v for (k, v) in pairs) + ",}"
            else:
                return "{,}"
        elif mode == 2:
            # double commas
            if pairs:
                pieces = [k + ':' + v for (k, v) in pairs]
                # insert an extra comma randomly
                idx = draw(st.integers(min_value=0, max_value=len(pieces)))
                pieces.insert(idx, "")
                return "{" + ','.join(pieces) + "}"
            else:
                return "{,,}"
        elif mode == 3:
            # missing colon (turn one pair into "key value")
            if pairs:
                i = draw(st.integers(min_value=0, max_value=len(pairs)-1))
                pieces = [k + ':' + v for (k, v) in pairs]
                k, v = pairs[i]
                pieces[i] = k + ' ' + v
                return "{" + ','.join(pieces) + "}"
            else:
                return "{ \"a\" \"b\" }"
        elif mode == 4:
            # missing closing brace
            return "{" + ','.join(k + ':' + v for (k, v) in pairs)
        elif mode == 5:
            # duplicate keys explicit (even if pool had no duplicates)
            if pairs:
                # duplicate the first key pair twice
                first = pairs[0]
                rest = pairs[1:]
                pieces = [first, first] + rest
                return "{" + ','.join(k + ':' + v for (k, v) in pieces) + "}"
            else:
                return '{"k":1,"k":2}'
        else:
            return obj
    return _make_obj()

def _array_strategy(inner):
    @st.composite
    def _make_array(draw):
        mode = draw(st.integers(min_value=0, max_value=5))
        if mode == 0:
            # empty array []
            return "[]"
        n = draw(st.integers(min_value=0, max_value=8))
        elems = [draw(inner) for _ in range(n)]
        arr = "[" + ",".join(elems) + "]"
        if mode == 1:
            # trailing comma variant
            return "[" + ",".join(elems) + ",]"
        elif mode == 2:
            # double commas
            pieces = [e for e in elems]
            if pieces:
                idx = draw(st.integers(min_value=0, max_value=len(pieces)))
                pieces.insert(idx, "")
                return "[" + ",".join(pieces) + "]"
            else:
                return "[,,]"
        elif mode == 3:
            # missing closing bracket
            return "[" + ",".join(elems)
        elif mode == 4:
            # nested incomplete (missing comma between values)
            if len(elems) >= 2:
                return "[" + elems[0] + elems[1] + ("," + ",".join(elems[2:]) if len(elems) > 2 else "") + "]"
            else:
                return "[" + ",".join(elems) + "]"
        else:
            return arr
    return _make_array()

# deep nesting generator: create arrays nested around a single element to reach depths near the parser limit.
@st.composite
def deep_nesting(draw):
    # Choose depth concentrated near the parser cap (~2048), but allow some variance.
    depth = draw(st.one_of(
        st.integers(min_value=1900, max_value=2048),
        st.integers(min_value=1800, max_value=2050).filter(lambda d: d <= 2050)
    ))
    # Put a simple value in the center; prefer a small token ("0") to keep size predictable.
    center = draw(st.sampled_from(["0", "null", "false", '"deep"']))
    return '[' * depth + center + ']' * depth

# Values with trailing garbage (parser accepts trailing content after a complete value)
@st.composite
def value_with_trailing(draw, inner):
    val = draw(inner)
    trailing = draw(st.text('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \t\r\n', min_size=1, max_size=40))
    return val + trailing

# Compose recursive strategy: values may be nested objects/arrays built from the base primitives.
def _recursive_values():
    # inner strategy placeholder for st.recursive
    def extend(inner):
        return st.one_of(_obj_strategy(inner), _array_strategy(inner))
    return st.recursive(base_value, extend, max_leaves=200)

# Build the top-level strategy mixing recursive JSON, deep nesting, and trailing-content variants.
strategy = st.one_of(
    _recursive_values(),
    deep_nesting(),
    # Sometimes produce a valid value then arbitrary trailing content
    value_with_trailing(_recursive_values()),
    # Also emit a single primitive (including malformed) to exercise the lone-sign acceptance
    st.one_of(json_number(), json_string(allow_unterminated=True), st.sampled_from(["true","false","null","-","+",".5","1."]))
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 82,
    "reject": 268
  },
  "acceptance_rate": 0.234,
  "max_nesting_depth": 2046,
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
  "cap_distance_mass": 0.28,
  "novelty": 13,
  "divergences": 57,
  "divergence_examples": [
    "b'\"\\\\uDFFF\\xc4\\x9eO\\\\r\\\\uBb67\\\\u327a\\xc3\\xbd\\\\uCFC8\\\\uD800\\\\uDC00\\\\ubbBC\\\\ue06c\\\\uB75e\\\\uDC00\"'",
    "b'\"\\\\uDFFFo\\\\ubDcC\\xc3\\x82\\xc4\\x92\\\\uDFFF\\\\b\\\\uD801\\\\u0DB2\\\\u3131\\\\uD800\\\\uD801\"'",
    "b'\"\"0'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **broaden_exploration** — coverage saturated; diversify accepted structures.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.