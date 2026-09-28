```python
from hypothesis import strategies as st
import json

# Helper pieces for building JSON-ish text tokens.

HEX_DIGITS = "0123456789abcdefABCDEF"
HEX_DIGIT = st.sampled_from(list(HEX_DIGITS))
DIGIT_STR = "0123456789"
NONZERO_DIGIT = st.sampled_from(list("123456789"))

# safe character for inclusion inside a JSON string without escaping:
# avoid raw NUL, double-quote, and backslash so that produced quoted strings are well-formed.
SAFE_CHAR = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x10FFFF,
    blacklist_characters=['"', '\\', '\x00'],
)

# Escape sequences (literal backslash sequences) to include inside string content.
SIMPLE_ESC = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
UNICODE_ESC = HEX_DIGIT.flatmap(lambda a: HEX_DIGIT.flatmap(lambda b: HEX_DIGIT.flatmap(lambda c: HEX_DIGIT.map(lambda d: '\\u' + a + b + c + d))))
# A few explicit surrogate-style escape sequences as text (common near-valid edge cases).
SURROGATE_ESC = st.sampled_from(['\\uD800', '\\uDBFF', '\\uDC00', '\\uDFFF'])

ESC_PART = st.one_of(SIMPLE_ESC, UNICODE_ESC, SURROGATE_ESC)

# Valid (quoted) JSON STRING token built from safe chars and escape sequences.
VALID_STRING = st.lists(st.one_of(SAFE_CHAR, ESC_PART), min_size=0, max_size=8).map(lambda parts: '"' + ''.join(parts) + '"')

# Unterminated / malformed string variants (starts with " but missing end).
UNTERMINATED_STRING = st.lists(st.one_of(SAFE_CHAR, ESC_PART, st.sampled_from(['"', '\\'])), min_size=0, max_size=8).map(lambda parts: '"' + ''.join(parts))

# Numbers: produce both valid and near-invalid numeric tokens.
def valid_number_strategy():
    # integer part: either "0" or non-zero digit + digits
    int_part = st.one_of(
        st.just("0"),
        st.builds(lambda lead, rest: lead + rest, NONZERO_DIGIT, st.text(alphabet=DIGIT_STR, min_size=0, max_size=8)),
    )
    frac_part = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text(alphabet=DIGIT_STR, min_size=1, max_size=6)))
    exp_part = st.one_of(
        st.just(""),
        st.builds(lambda e, sfx, digs: e + sfx + digs,
                  st.sampled_from(["e", "E"]),
                  st.sampled_from(["", "+", "-"]),
                  st.text(alphabet=DIGIT_STR, min_size=1, max_size=6))
    )
    sign = st.one_of(st.just(""), st.just("-"))
    return st.builds(lambda s, i, f, e: s + i + f + e, sign, int_part, frac_part, exp_part)

VALID_NUMBER = valid_number_strategy()

# Malformed / near-valid number tokens (to exercise leniency and edge cases).
MALFORMED_NUMBER = st.one_of(
    # leading plus
    st.builds(lambda t: "+" + t, VALID_NUMBER),
    # leading zero with extra digits (e.g. 01)
    st.builds(lambda d: "0" + d, st.text(alphabet=DIGIT_STR, min_size=1, max_size=6)),
    # fractional without leading zero
    st.just(".5"),
    st.just("-.5"),
    # trailing dot
    st.just("1."),
    # lone sign(s)
    st.just("-"),
    st.just("-."),
    # extreme exponents (overflow candidates)
    st.sampled_from(["1e309", "9e9999", "1e+309", "123456789012345678901234567890e9999"]),
    # hugely long integer
    st.builds(lambda s: s, st.text(alphabet=DIGIT_STR, min_size=20, max_size=60)),
    # explicit malformed chars
    st.sampled_from(["+01", ".e1", "01.0", "00", "--1"]),
)

NUMBER = st.one_of(VALID_NUMBER, MALFORMED_NUMBER)

# Simple literal tokens
LITERALS = st.sampled_from(["true", "false", "null"])

# Helper to create an object pair: key ":" value (value is textual JSON produced by recursion)
def make_pair(key_s, value_s):
    return key_s + ":" + value_s

# The base values for recursion: include valid tokens, a few malformed tokens, and empty containers as text.
BASE_VALUES = st.one_of(
    NUMBER,  # upweight NUMBER by including it first as an additional occurrence
    VALID_STRING,
    UNTERMINATED_STRING,  # unterminated strings as near-valid malformed inputs
    NUMBER,
    LITERALS,
    st.just("[]"),
    st.just("{}"),
)

# Now build recursive arrays/objects using st.recursive. The children strategy yields textual JSON values.
def extend(children):
    # arrays: valid, trailing comma, double commas, missing elements
    def array_variants(child):
        # empty
        empty = st.just("[]")
        # normal: [v,v,...]
        normal = st.lists(child, min_size=1, max_size=6).map(lambda vals: "[" + ",".join(vals) + "]")
        # trailing comma: [v,v,]
        trailing_comma = st.lists(child, min_size=1, max_size=5).map(lambda vals: "[" + ",".join(vals) + ",]")
        # double comma: insert an extra comma between values
        double_comma = st.lists(child, min_size=2, max_size=5).map(lambda vals: "[" + ",".join(vals[:1]) + ",," + ",".join(vals[1:]) + "]")
        # missing element: [,v] or [v,]
        missing_head = st.builds(lambda v: "[," + v + "]", child)
        missing_tail = st.builds(lambda v: "[" + v + ",]", child)
        return st.one_of(empty, normal, trailing_comma, double_comma, missing_head, missing_tail)

    # objects: valid pairs, duplicate keys, missing colon, trailing comma, double commas
    def object_variants(child):
        # key options: valid quoted strings, unterminated keys, and raw (malformed) identifiers
        key_valid = VALID_STRING
        key_unterminated = UNTERMINATED_STRING
        key_raw = st.text(alphabet=st.characters(min_codepoint=0x21, blacklist_characters=['{', '}', '[', ']', ':', ',', '"', '\x00']), min_size=1, max_size=6)
        key_choice = st.one_of(key_valid, key_unterminated, key_raw)

        # normal pair generator
        pair = st.tuples(key_choice, child).map(lambda kv: make_pair(kv[0], kv[1]))

        # normal object
        normal_obj = st.lists(pair, min_size=1, max_size=6).map(lambda pairs: "{" + ",".join(pairs) + "}")

        # duplicate keys: construct pairs where some keys repeat
        def dup_builder(pairs):
            # duplicate first key twice
            if not pairs:
                return "{}"
            k, v = pairs[0]
            dup_key = k
            # create two pairs with the same key
            duplicated = [make_pair(dup_key, v), make_pair(dup_key, v)]
            rest = [make_pair(kv[0], kv[1]) for kv in pairs[1:]]
            return "{" + ",".join(duplicated + rest) + "}"
        duplicate_obj = st.lists(st.tuples(key_choice, child), min_size=1, max_size=5).map(dup_builder)

        # missing colon between key and value: produce '"k" value'
        missing_colon = st.lists(st.tuples(key_choice, child), min_size=1, max_size=4).map(lambda kvs: "{" + ",".join(k + " " + v for (k, v) in kvs) + "}")

        # trailing comma, double comma
        trailing_comma = st.lists(pair, min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + ",}")
        double_comma = st.lists(pair, min_size=2, max_size=5).map(lambda pairs: "{" + ",".join(pairs[:1]) + ",," + ",".join(pairs[1:]) + "}")

        empty = st.just("{}")

        return st.one_of(empty, normal_obj, duplicate_obj, missing_colon, trailing_comma, double_comma)

    # deep nesting generator that wraps a child many times to approach parser nesting limits.
    def deep_wrap(child):
        # choose a depth near the parser's limit (0..2050). We bias toward deep values.
        depth_choice = st.integers(min_value=0, max_value=2050)
        # wrap the child value in many array brackets (could use objects similarly)
        return st.tuples(depth_choice, child).map(lambda dt: ("[" * dt[0]) + dt[1] + ("]" * dt[0]))

    return st.one_of(
        array_variants(children),
        object_variants(children),
        deep_wrap(children),
    )

# Build recursive JSON-ish textual values
RECURSIVE_JSON = st.recursive(BASE_VALUES, extend, max_leaves=100)

# Finally, allow trailing garbage after a complete value (the parser accepts trailing content).
# Also ensure we never introduce an actual raw NUL character in generated trailing content.
TRAIL = st.text(alphabet=st.characters(min_codepoint=0x20, blacklist_characters=['\x00']), min_size=0, max_size=20)

strategy = st.one_of(
    # pure recursive JSON-ish candidates
    RECURSIVE_JSON,
    # with trailing garbage appended (accepted by parser)
    st.tuples(RECURSIVE_JSON, TRAIL).map(lambda t: t[0] + t[1]),
)
```