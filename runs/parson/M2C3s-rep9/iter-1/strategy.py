from hypothesis import strategies as st
import json

# Helper: text without raw NUL (0x00) because the parser uses C NUL-terminated strings.
_no_nul_text = st.text(min_size=0, max_size=12).filter(lambda s: '\x00' not in s)

# Well-formed string literal (escaped correctly via json.dumps)
well_formed_string = _no_nul_text.map(json.dumps)

# Strings that include explicit \uXXXX escapes (including a surrogate escape)
unicode_escape_string = _no_nul_text.map(lambda s: '"' + s.replace('"', '') + r'\u0041"')
surrogate_escape_string = _no_nul_text.map(lambda s: '"' + s.replace('"', '') + r'\uD800"')

# Unterminated string (near-malformed)
unterminated_string = _no_nul_text.map(lambda s: '"' + s.replace('"', ''))

# Quoted string that contains a raw control byte (not NUL) inside (near-malformed)
raw_control_char = st.sampled_from([chr(1), chr(2), chr(7), chr(8), chr(10), chr(13)])
raw_control_string = st.tuples(_no_nul_text, raw_control_char).map(
    lambda t: '"' + t[0].replace('"', '') + t[1] + '"'
)

string_value = st.one_of(
    well_formed_string,
    unicode_escape_string,
    surrogate_escape_string,
    unterminated_string,
    raw_control_string,
)

# Number variants: valid, near-malformed, extreme exponents/overflows, lone-signs, leading +, .5, 01
valid_integer = st.integers(min_value=-10_000_000, max_value=10_000_000).map(str)
leading_zero_like = st.integers(min_value=0, max_value=999).map(lambda n: "0" + str(n))  # '01' etc.
float_with_frac = st.tuples(st.integers(min_value=-10000, max_value=10000), st.integers(0, 999999)).map(
    lambda t: f"{t[0]}.{abs(t[1])}"
)
float_trailing_dot = st.integers(min_value=-10000, max_value=10000).map(lambda n: f"{n}.")  # '1.'
leading_plus = st.integers(min_value=0, max_value=1000000).map(lambda n: f"+{n}")  # '+1'
dot_leading = st.integers(min_value=1, max_value=999999).map(lambda n: f".{n}")  # '.5'
lone_signs = st.sampled_from(["-", "-.", "+", "+."])  # parser is lenient about lone '-'
extreme_exponents = st.sampled_from(["1e309", "1e10000", "-1e4000", "9e9999", "1E9999"])
near_invalids = st.sampled_from(["01", "+01", "00", "1e"])  # other near-malformed

number_value = st.one_of(
    valid_integer,
    leading_zero_like,
    float_with_frac,
    float_trailing_dot,
    leading_plus,
    dot_leading,
    lone_signs,
    extreme_exponents,
    near_invalids,
)

# JSON literals
literal_value = st.sampled_from(["true", "false", "null"])

# Base (non-recursive) JSON values as text
base_value = st.one_of(string_value, number_value, literal_value)

# Key strategy for object members: keys are normally strings; use json.dumps to escape properly
key_text = _no_nul_text.map(json.dumps)

# Extension function for st.recursive to build arrays and objects from child "value strings"
def extend(children):
    # Arrays: several variants to hit edge cases (empty, trailing comma, double commas, unterminated)
    arrays = []

    # well-formed arrays from 0..6 children
    arrays.append(
        st.lists(children, min_size=0, max_size=6).map(lambda xs: "[" + ",".join(xs) + "]")
    )

    # trailing comma: e.g. [1,2,] and even for empty produce [,]
    arrays.append(
        st.lists(children, min_size=0, max_size=6).map(
            lambda xs: "[" + (",".join(xs) if xs else "") + "," + "]"
        )
    )

    # double commas inside: create normal join then introduce a double comma between two elements if possible
    def make_double_comma(xs):
        if len(xs) >= 2:
            # inject a double comma between first two elements
            return "[" + xs[0] + ",," + ",".join(xs[1:]) + "]"
        elif len(xs) == 1:
            return "[" + xs[0] + ",,]"  # something like [x,,]
        else:
            return "[,,]"  # purely malformed
    arrays.append(st.lists(children, min_size=0, max_size=6).map(make_double_comma))

    # unterminated array (no closing bracket)
    arrays.append(st.lists(children, min_size=0, max_size=6).map(lambda xs: "[" + ",".join(xs)))

    # Objects: several variants (empty, duplicate keys, trailing comma, missing colon, double commas)
    objects = []

    # well-formed object
    objects.append(
        st.lists(st.tuples(key_text, children), min_size=0, max_size=6).map(
            lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs) + "}"
        )
    )

    # duplicate keys: pick a key and repeat it (generate at least one pair)
    def dup_pairs(pairs):
        if not pairs:
            # create a simple duplicate: {"a":0,"a":1}
            return '{"dup":0,"dup":1}'
        # choose a key from generated ones and duplicate it
        k0 = pairs[0][0]
        # ensure at least two entries so duplication exists
        if len(pairs) == 1:
            return "{" + k0 + ":" + pairs[0][1] + "," + k0 + ":null}"
        else:
            return "{" + k0 + ":" + pairs[0][1] + "," + ",".join(k + ":" + v for (k, v) in pairs[1:]) + "," + k0 + ":0" + "}"
    objects.append(st.lists(st.tuples(key_text, children), min_size=0, max_size=6).map(dup_pairs))

    # trailing comma in object
    objects.append(
        st.lists(st.tuples(key_text, children), min_size=0, max_size=6).map(
            lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs) + ",}"
        )
    )

    # missing colon (replace ':' with nothing)
    objects.append(
        st.lists(st.tuples(key_text, children), min_size=0, max_size=6).map(
            lambda pairs: "{" + ",".join(k + v for (k, v) in pairs) + "}"
        )
    )

    # double commas in object
    def obj_double_comma(pairs):
        if len(pairs) >= 2:
            return "{" + pairs[0][0] + ":" + pairs[0][1] + ",," + ",".join(k + ":" + v for (k, v) in pairs[1:]) + "}"
        elif len(pairs) == 1:
            return "{" + pairs[0][0] + ":" + pairs[0][1] + ",,}"
        else:
            return "{,,}"
    objects.append(st.lists(st.tuples(key_text, children), min_size=0, max_size=6).map(obj_double_comma))

    # unterminated object
    objects.append(
        st.lists(st.tuples(key_text, children), min_size=0, max_size=6).map(
            lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs)
        )
    )

    return st.one_of(*(arrays + objects))

# Recursive JSON-ish value strategy (strings that represent a JSON value; arrays/objects are built recursively)
recursive_values = st.recursive(base_value, extend, max_leaves=200)

# Deep nesting generator: explicitly construct deep arrays or objects near the parser limit.
# We avoid emitting raw NUL. This generator is separate (allowed) to concentrate depth near 2048.
deep_nesting = st.integers(min_value=1920, max_value=2060).map(
    lambda depth: ("[" * depth) + "0" + ("]" * depth)
)

# Optionally append trailing content (parser accepts trailing data after a value)
trailing_tail = st.one_of(
    st.just(""),
    _no_nul_text.map(lambda s: " " + s),
    st.sampled_from([" abc", "TRAILING", "\n/*garbage*/"]),
)

# A top-level wrapper to occasionally append trailing content to exercise that leniency.
with_trailing = st.tuples(st.one_of(recursive_values, deep_nesting), trailing_tail).map(lambda t: t[0] + t[1])

# Final strategy: include the core recursive style, explicit deep nesting variant, and some pure malformed standalone cases
malformed_standalone = st.one_of(
    # unterminated string by itself
    unterminated_string,
    # double commas at top level (invalid JSON but near-structure)
    st.just("1,,2"),
    # missing colon in object-like text
    st.just('{"a" 1}'),
    # leading plus number
    leading_plus,
    # lone dot-leading number
    dot_leading,
    # raw control char as top-level (not quoted)
    raw_control_char.map(lambda c: c),
    # a JSON value followed by lots of trailing garbage
    st.tuples(recursive_values, _no_nul_text).map(lambda t: t[0] + " " + t[1]),
)

# Combine everything: prefer with_trailing half the time, otherwise core recursive or malformed
strategy = st.one_of(with_trailing, recursive_values, deep_nesting, malformed_standalone)