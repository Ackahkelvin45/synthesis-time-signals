from hypothesis import strategies as st
import json

# Primitive pieces

# 4-hex Unicode escape
hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
unicode_escape = hex4.map(lambda h: "\\u" + h)

# A few surrogate escapes (upper/lower cases)
surrogate_escape = st.sampled_from(["\\uD800", "\\uD801", "\\uDBFF", "\\uDC00", "\\uDFFF"])

# Common single-character escapes
simple_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

# Safe single characters for JSON string content (exclude quote, backslash, and NUL)
safe_char = st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(lambda c: c not in ('"', '\\', '\x00'))

# Fragments that can appear inside a JSON string literal (as text or escape sequences)
string_fragment = st.one_of(
    safe_char.map(lambda c: c),
    unicode_escape,
    surrogate_escape,
    simple_esc
)

# Complete quoted string, and some malformed variants (unterminated, missing opening quote)
quoted_string = st.lists(string_fragment, min_size=0, max_size=12).map(lambda parts: '"' + "".join(parts) + '"')
unterminated_string = st.lists(string_fragment, min_size=0, max_size=12).map(lambda parts: '"' + "".join(parts))  # missing closing quote
missing_open_quote = st.lists(string_fragment, min_size=0, max_size=12).map(lambda parts: "".join(parts) + '"')  # missing opening quote

# Key strategy for objects (mostly proper quoted keys, sometimes malformed/no-quotes)
key_strategy = st.one_of(
    quoted_string,
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", min_size=1, max_size=8).map(lambda s: s),  # bare token (malformed as a JSON key)
    unterminated_string
)

# Number generation: valid, extreme, and near-valid-but-malformed forms
valid_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**9).map(str),
    st.integers(min_value=-10**9, max_value=-1).map(str)
)

fraction = st.builds(
    lambda a, b: a + "." + b,
    st.one_of(st.just("0"), st.integers(min_value=1, max_value=10**6).map(str)),
    st.text(alphabet="0123456789", min_size=1, max_size=8)
)

exp_suffix = st.builds(
    lambda mant, e: mant + e,
    st.one_of(valid_int, fraction),
    st.one_of(
        st.builds(lambda s: "e" + s, st.text(alphabet="+-0123456789", min_size=1, max_size=6)),
        st.sampled_from(["e309", "e308", "e1000", "e-400", "e9999"])
    )
)

# Explicit extreme/overflow exponents and malformed numbers
extreme_exponent = st.sampled_from(["1e309", "-1e309", "1e1000", "1e9999", "9e4000"])
malformed_numbers = st.sampled_from(["+1", "+.5", ".5", "1.", "01", "-", "-.", "1e", "1e+", "1e-"])

number_value = st.one_of(valid_int, fraction, exp_suffix, extreme_exponent, malformed_numbers)

# Literal non-numeric values
literals = st.sampled_from(["true", "false", "null"])

# The base JSON "value" pieces (strings, numbers, literals). These are textual fragments.
base_value = st.one_of(
    quoted_string,
    unterminated_string,
    missing_open_quote,
    number_value,
    literals
)

# Helper to render an object from a list of (key, value) pairs, with variants:
def _render_object_from_pairs(pairs):
    # pairs is list of (k,v) strings (k may be quoted or bare/malformed)
    if not pairs:
        return "{}"
    # join with colon; allow intentional missing-colon variants if keys look malformed
    items = []
    for k, v in pairs:
        # Introduce a small chance for missing colon or missing value to create near-valid malformed
        items.append(k + ":" + v)
    return "{" + ",".join(items) + "}"

# Recursive construction for arrays/objects using textual composition (values are strings)
recursive_values = st.recursive(
    base_value,
    lambda children: st.one_of(
        # Well-formed arrays
        st.lists(children, min_size=0, max_size=5).map(lambda elems: "[" + ",".join(elems) + "]"),
        # Arrays with trailing comma
        st.lists(children, min_size=1, max_size=5).map(lambda elems: "[" + ",".join(elems) + ",]"),
        # Arrays with double commas (e.g., [a,,b])
        st.lists(children, min_size=2, max_size=5).map(lambda elems: "[" + ",, ".join(elems) + "]"),
        # Well-formed objects
        st.lists(st.tuples(key_strategy, children), min_size=0, max_size=5).map(
            lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs) + "}"
        ),
        # Objects with duplicate keys at the same level (generate duplicates intentionally)
        st.lists(children, min_size=1, max_size=4).flatmap(
            lambda vals: st.tuples(st.just(vals)).map(lambda t: "{" + ",".join('"dup":' + v for v in t[0]) + "}")
        ),
        # Objects with missing colons (malformed)
        st.lists(st.tuples(key_strategy, children), min_size=1, max_size=4).map(
            lambda pairs: "{" + ",".join(k + " " + v for (k, v) in pairs) + "}"
        ),
    ),
    max_leaves=1000
)

# Deep nesting generator concentrated near the parser's nesting limit (~2048).
@st.composite
def deep_nesting(draw):
    # Bias choice: often pick depths near 1950-2050, but sometimes small depths.
    depth_choice = draw(st.one_of(
        st.integers(min_value=1950, max_value=2050),
        st.integers(min_value=1000, max_value=2050),
        st.integers(min_value=0, max_value=50),
        st.integers(min_value=50, max_value=300)
    ))
    kind = draw(st.sampled_from(["array", "object"]))
    if depth_choice <= 0:
        return "0"
    if kind == "array":
        # Build nested arrays like [[[[0]]]]
        return ("[" * depth_choice) + "0" + ("]" * depth_choice)
    else:
        # Build nested objects like {"k":{"k": ... 0 ... }}
        return ('{"k":' * depth_choice) + "0" + ('}' * depth_choice)

# Trailing-content variant: a complete value followed by arbitrary trailing data (the parser accepts this)
trailing_garbage = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \t\r\n!@#$%^&*()-_=+[]{};:'\",.<>/?`~", min_size=1, max_size=40).filter(lambda s: "\x00" not in s)
value_with_trail = st.tuples(recursive_values, trailing_garbage).map(lambda t: t[0] + t[1])

# Additional stand-alone malformed variants to exercise parser leniencies and edge cases
near_valid_malformed = st.sampled_from([
    "1abc",    # trailing content without whitespace
    "1 garbage",
    "-",       # lone sign accepted as zero by parser
    "-.",      # lone sign + dot
    "+1",      # leading plus (near-valid)
    ".5",      # leading dot (near-valid)
    "01",      # leading zero on non-zero int
    '{"a":0,}', # trailing comma in object
    '["a",, "b"]', # double comma inside array
    '"unterminated', # unterminated string
    '"\\uD800"', # surrogate escape inside a string
    '"\\u0000"', # escaped NUL inside a string (safe)
    '1e309 garbage', # overflow exponent with trailing garbage
    '#include <stdio.h>\nint main(){return 0;}',  # C-style input to reach non-JSON parser branches
    '/* comment */0',  # comment before a value to exercise comment-handling branches
    '// comment\n0'   # single-line C++/C-style comment variant to reach single-line comment parsing branch
])

# Combine everything into the final strategy. Include deep nesting, recursive constructions,
# trailing-content variants, and explicit near-valid/malformed examples.
strategy = st.one_of(
    recursive_values,
    deep_nesting(),
    value_with_trail,
    near_valid_malformed,
    st.builds(lambda s: "\ufeff" + s, recursive_values),
)