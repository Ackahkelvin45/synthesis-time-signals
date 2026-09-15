```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf strategies
# ---------------------------------------------------------------------------

# Characters that are safe inside a JSON string (no quote, no backslash,
# no raw control chars).  We deliberately keep this fairly broad so that the
# fuzzer explores many UTF-8 code points.
_safe_char = st.characters(
    blacklist_categories=("Cs",),  # surrogates cannot be encoded as UTF-8
    blacklist_characters='\\"',
)

# A raw control character that the parser happily accepts inside a string.
_raw_control = st.one_of(
    st.integers(min_value=0x00, max_value=0x1F).map(chr),
    st.just("\x00"),
)

# A single escape sequence that the grammar allows.
_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0x0000, max_value=0xFFFF).map(
        lambda n: "\\u%04x" % n
    ),
    st.integers(min_value=0x0000, max_value=0xFFFF).map(
        lambda n: "\\u%04X" % n
    ),
)

# A lone surrogate escape — the parser rejects it, but we want to generate it
# so that the rejection path is exercised.
_lone_surrogate_escape = st.integers(
    min_value=0xD800, max_value=0xDFFF
).map(lambda n: "\\u%04x" % n)

# A surrogate pair escape — valid UTF-16, the parser should accept it.
_surrogate_pair_escape = st.tuples(
    st.integers(min_value=0xD800, max_value=0xDBFF),
    st.integers(min_value=0xDC00, max_value=0xDFFF),
).map(lambda t: "\\u%04x\\u%04x" % t)

# String body: mixture of safe chars, raw controls, escapes, and surrogate
# escapes.  We keep the length bounded so that the generated strings stay
# manageable.
_string_body = st.one_of(
    st.text(_safe_char, max_size=20),
    st.lists(
        st.one_of(
            _safe_char,
            _raw_control,
            _escape,
            _surrogate_pair_escape,
            _lone_surrogate_escape,
        ),
        max_size=12,
    ).map("".join),
)

# A JSON string literal (including the surrounding quotes).
_json_string = _string_body.map(lambda s: '"' + s + '"')

# ---------------------------------------------------------------------------
# Number strategies
# ---------------------------------------------------------------------------

# Valid integers (no leading zeros).
_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

# Fractional part.
_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
)

# Exponent part, including extreme magnitudes that overflow to inf.
_exp_part = st.one_of(
    st.just(""),
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.sampled_from(["e309", "e-309", "e308", "e-308", "E+400", "e999"]),
)

_valid_number = st.tuples(_int_part, _frac_part, _exp_part).map(
    lambda t: t[0] + t[1] + t[2]
)

# Numbers the parser accepts but strict JSON rejects.
_lenient_number = st.one_of(
    # Leading zeros: 01, 007, 00
    st.tuples(
        st.just("0"),
        st.integers(min_value=0, max_value=10**6).map(str),
    ).map(lambda t: t[0] + t[1]),
    # Trailing dot: 1., -3.
    st.integers(min_value=-10**6, max_value=10**6).map(lambda n: str(n) + "."),
    # Hex: 0x10, 0XFF
    st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda n: "0x%x" % n),
    # Extreme magnitudes that become inf.
    st.sampled_from(["1e309", "-1e309", "1e999", "1E+400", "9" * 20]),
)

# Numbers the parser rejects.
_invalid_number = st.sampled_from(
    ["+1", ".5", "-.5", "-", "1.", "01"][:2]  # +1 and .5 are the clear rejects
)

_number = st.one_of(_valid_number, _lenient_number)

# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

# Depth budget: the parser rejects nesting deeper than 1000 levels.  We
# concentrate interesting depth near that limit rather than far beyond it.
# The recursive strategy is parameterised by a depth argument so we can
# control how deep the generated structures go.
_MAX_INTERESTING_DEPTH = 1000

# A shallow value: no recursion, just leaves.
_shallow_value = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
)

# The recursive strategy.  We use st.recursive with a base case of leaves
# and a recursive case that builds objects and arrays from already-built
# values.  The depth is controlled by the `max_leaves` parameter and by
# occasionally injecting a very deep chain.
def _deep_chain(depth):
    """Build a chain of nested arrays of exactly `depth` levels."""
    return "[" * depth + "0" + "]" * depth


def _deep_object_chain(depth):
    """Build a chain of nested objects of exactly `depth` levels."""
    return '{"a":' * depth + "0" + "}" * depth


# A strategy that produces a value at a controlled depth.  We use a
# composite strategy to thread the depth through.
@st.composite
def _value_at_depth(draw, depth):
    if depth <= 0:
        return draw(_shallow_value)
    # Choose between a leaf, an object, or an array.
    kind = draw(st.integers(min_value=0, max_value=2))
    if kind == 0:
        return draw(_shallow_value)
    elif kind == 1:
        # Object with 0..4 pairs.
        n = draw(st.integers(min_value=0, max_value=4))
        pairs = []
        for _ in range(n):
            key = draw(_json_string)
            val = draw(_value_at_depth(depth - 1))
            pairs.append(key + ":" + val)
        return "{" + ",".join(pairs) + "}"
    else:
        # Array with 0..4 elements.
        n = draw(st.integers(min_value=0, max_value=4))
        elems = [draw(_value_at_depth(depth - 1)) for _ in range(n)]
        return "[" + ",".join(elems) + "]"


# The main recursive strategy: start at a moderate depth so that we get
# interesting structures without blowing up the size.
_recursive_value = _value_at_depth(4)

# Explicit deep-nesting strategies near the parser's limit.
_deep_nesting = st.one_of(
    # Arrays at depths around 1000 (accepted and rejected).
    st.integers(min_value=990, max_value=1010).map(_deep_chain),
    # Objects at depths around 1000.
    st.integers(min_value=990, max_value=1010).map(_deep_object_chain),
    # Mixed deep nesting.
    st.integers(min_value=990, max_value=1010).map(
        lambda d: "[" * (d // 2) + '{"a":' * (d - d // 2) + "0" + "}" * (d - d // 2) + "]" * (d // 2)
    ),
)

# ---------------------------------------------------------------------------
# Malformed / near-valid strategies
# ---------------------------------------------------------------------------

# These produce strings that are almost valid JSON but have a deliberate
# defect.  The parser should reject most of them (except where noted).
_malformed = st.one_of(
    # Double commas in arrays.
    st.sampled_from(["[1,,2]", "[,]", "[1,2,,]", "[,1]", "[1,,]"]),
    # Double commas in objects.
    st.sampled_from(['{"a":1,,"b":2}', '{,}', '{"a":1,,}']),
    # Missing colons.
    st.sampled_from(['{"a" 1}', '{"a"}', '{"a":}']),
    # Missing commas.
    st.sampled_from(['{"a":1 "b":2}', "[1 2]", "[1 2 3]"]),
    # Unterminated strings.
    st.sampled_from(['"abc', '"', '{"a":"abc', '["abc']),
    # Trailing commas.
    st.sampled_from(["[1,]", '{"a":1,}', "[,]", "{,}"]),
    # Lone minus.
    st.just("-"),
    # Leading plus.
    st.sampled_from(["+1", "+0", "+1.5"]),
    # Bare .5
    st.sampled_from([".5", "-.5", ".", "-."]),
    # NaN and Infinity words.
    st.sampled_from(["NaN", "Infinity", "-Infinity", "nan", "inf"]),
    # Single-quoted strings.
    st.sampled_from(["'abc'", "'a'", "{'a':1}"]),
    # Unquoted keys.
    st.sampled_from(["{a:1}", "{a:1,b:2}"]),
    # Invalid escapes.
    st.sampled_from(['"\\x"', '"\\u12"', '"\\u"', '"\\"']),
    # Empty input.
    st.just(""),
    # Just whitespace.
    st.sampled_from([" ", "\t", "\n", "\r", "  \t\n"]),
)

# ---------------------------------------------------------------------------
# Trailing content strategies (accepted by the parser)
# ---------------------------------------------------------------------------

_trailing_content = st.one_of(
    st.tuples(_recursive_value, st.text(min_size=1, max_size=10)).map(
        lambda t: t[0] + t[1]
    ),
    st.tuples(_recursive_value, st.just("\x00")).map(lambda t: t[0] + t[1]),
    st.tuples(_recursive_value, st.just("abc")).map(lambda t: t[0] + t[1]),
    st.tuples(_recursive_value, st.just(" 1 2")).map(lambda t: t[0] + t[1]),
)

# ---------------------------------------------------------------------------
# BOM and NUL strategies
# ---------------------------------------------------------------------------

_bom_prefix = st.tuples(
    st.just("\ufeff"),
    _recursive_value,
).map(lambda t: t[0] + t[1])

_nul_inside_string = st.tuples(
    st.just('"'),
    st.text(min_size=0, max_size=5),
    st.just("\x00"),
    st.text(min_size=0, max_size=5),
    st.just('"'),
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

# ---------------------------------------------------------------------------
# cJSON_Compare coverage strategies
# ---------------------------------------------------------------------------
# cJSON_Compare is a public API that compares two parsed cJSON trees.  It is
# only reachable if we can hand the parser *two* documents to compare.  Since
# the harness consumes a single string, we emit a pair of JSON documents
# separated by a delimiter that a comparison harness can split on, so that
# both trees are exercised by cJSON_Compare.

_compare_sep = st.sampled_from(["\x1e", "\x1f", "\x00\x00"])

# A pair of values that are structurally similar so cJSON_Compare descends
# into nested objects/arrays and hits its many branches (type mismatch,
# value mismatch, key mismatch, array length mismatch, case sensitivity).
_compare_pair = st.one_of(
    # Identical documents -> deep equality path.
    st.tuples(_recursive_value).map(lambda t: (t[0], t[0])),
    # Shallow leaves with a small perturbation -> mismatch branches.
    st.tuples(_shallow_value, _shallow_value),
    # Objects with a shared key but differing values -> object compare branch.
    st.tuples(
        _recursive_value,
        _recursive_value,
    ),
    # Explicit type-mismatch pairs.
    st.sampled_from(
        [
            ("1", '"1"'),
            ("true", "false"),
            ("null", "0"),
            ("[]", "{}"),
            ("[1]", "[1,2]"),
            ('{"a":1}', '{"b":1}'),
            ('{"a":1}', '{"a":2}'),
            ('{"a":1}', '{"A":1}'),
            ('{"a":1,"b":2}', '{"b":2,"a":1}'),
            ('[1,2,3]', '[3,2,1]'),
            ('{"a":{"b":[1,2]}}', '{"a":{"b":[1,3]}}'),
            ('{"a":{"b":[1,2]}}', '{"a":{"b":[1,2]}}'),
            ('"abc"', '"abd"'),
            ('"abc"', '"abc"'),
            ("1e309", "1e309"),
            ("-0", "0"),
            ('{"a":null}', '{"a":null}'),
            ('{"a":null}', '{"a":0}'),
        ]
    ),
)


@st.composite
def _compare_input(draw):
    left = draw(_recursive_value)
    # Sometimes reuse the left tree so equality paths are exercised.
    right = draw(st.one_of(st.just(left), _recursive_value))
    sep = draw(_compare_sep)
    return left + sep + right


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

# Combine everything.  We weight the interesting cases more heavily.
strategy = st.one_of(
    # Well-formed recursive values.
    _recursive_value,
    # Deep nesting near the parser's limit.
    _deep_nesting,
    # Malformed inputs.
    _malformed,
    # Trailing content after a valid value.
    _trailing_content,
    # BOM-prefixed values.
    _bom_prefix,
    # NUL bytes inside strings.
    _nul_inside_string,
    # Extreme numbers.
    _lenient_number,
    # Lone surrogate escapes (rejected by the parser).
    st.tuples(
        st.just('"'),
        _lone_surrogate_escape,
        st.just('"'),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # Surrogate pairs (accepted).
    st.tuples(
        st.just('"'),
        _surrogate_pair_escape,
        st.just('"'),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # Empty object and array.
    st.sampled_from(["{}", "[]", " \t\n{}", " \t\n[]"]),
    # Duplicate keys.
    st.sampled_from(
        [
            '{"a":1,"a":2}',
            '{"a":1,"a":2,"a":3}',
            '{"a":{"a":1},"a":2}',
        ]
    ),
    # cJSON_Compare coverage: paired documents separated by a delimiter.
    _compare_input(),
)
```