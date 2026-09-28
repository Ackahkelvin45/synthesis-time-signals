```python
from hypothesis import strategies as st
import json

# Helper: text that avoids raw NUL (min_codepoint=1) and excludes quotes/backslash for easy json.dumps
_safe_py_text = st.text(
    st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters=['"', "\\"]),
    min_size=0,
    max_size=30,
)

# Valid JSON string via json.dumps (guarantees proper escaping, no raw NUL)
valid_json_string = _safe_py_text.map(json.dumps)

# Explicit string forms that exercise unicode escapes, surrogate halves/pairs, and control escape sequences
unicode_escape_strings = st.sampled_from(
    [
        # explicit \uXXXX escapes inside the string literal (backslash characters must be present)
        '"\\u0000"',            # escaped NUL (six chars) - allowed
        '"\\u0001"',            # control escape
        '"\\uD800"',            # unpaired high surrogate
        '"\\uDC00"',            # unpaired low surrogate
        '"\\uD834\\uDD1E"',     # surrogate pair (musical G clef)
        '"\\uFFFF"',            # high codepoint escape
        '"line\\nbreak"',       # common escape sequences
        '"quote:\\""',
        '"backslash:\\\\"',
    ]
)

# Unterminated / malformed string variants (no closing quote, bad escape, raw control char inserted)
unterminated_or_bad_strings = st.one_of(
    # missing closing quote
    _safe_py_text.map(lambda s: '"' + s),
    # bad/unknown escape like \x or a backslash at end
    _safe_py_text.map(lambda s: '"' + s + '\\'),
    # raw control character injected (malformed w.r.t. JSON grammar) but not NUL
    st.text(st.characters(min_codepoint=1, max_codepoint=0x1F), min_size=1, max_size=3).map(lambda s: '"' + s + '"'),
)

# Key strategy for objects: allow valid strings and also the unicode-escape variants and malformed keys
key_string = st.one_of(valid_json_string, unicode_escape_strings, unterminated_or_bad_strings)

# Number strategies: valid, extreme, and malformed/near-valid
# Valid integer (no leading zeros except "0")
_valid_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
)

# Valid fractional/exp numbers
_valid_frac_exp = st.one_of(
    st.tuples(_valid_int, st.floats(allow_infinity=False, allow_nan=False)).map(lambda t: t[0]),  # fallback to int form via tuple->str mixing (rare)
    st.builds(lambda a, b: a + "." + b, _valid_int, st.text(st.characters("0123456789"), min_size=1, max_size=6)),
    st.builds(lambda a, e: a + e, _valid_int, st.sampled_from(["e1", "E2", "e+10", "e-3", "E01"])),
    st.builds(lambda a, b, e: a + "." + b + e, _valid_int, st.text(st.characters("0123456789"), min_size=1, max_size=6), st.sampled_from(["e1", "E2", "e+10", "e-3", "E01"])),
)

valid_number = st.one_of(_valid_int, _valid_frac_exp)

# Malformed/near-valid numbers to hit parser leniencies and pitfalls (leading +, .5, 1., 01, lone '-', '-.')
malformed_number = st.sampled_from(
    ["+1", ".5", "1.", "01", "-", "-.", "+Infinity", "NaN"]
)

# Extreme magnitudes/exponents (may overflow -> parser rejects as non-finite)
extreme_number = st.sampled_from(
    ["1e309", "9e9999", "-1e9999", "1e308", "-1e308", "1E10000", "2.5e4000"]
)

number_value = st.one_of(valid_number, malformed_number, extreme_number)

# Literal tokens
literals = st.sampled_from(["true", "false", "null"])

# A leaf value strategy producing a JSON "value" textual representation (valid or intentionally malformed)
leaf_value = st.one_of(
    valid_json_string,
    unicode_escape_strings,
    unterminated_or_bad_strings,
    number_value,
    literals,
)

# Helper functions for constructing composites from lists/tuples (ensures we map tuples to joined strings)
def make_array_from_list(lst):
    return "[" + ",".join(lst) + "]"

def make_array_trailing_comma(lst):
    if not lst:
        return "[]"
    return "[" + ",".join(lst) + ",]"

def make_array_double_commas(lst):
    # insert a double comma somewhere if length >=1
    if not lst:
        return "[]"
    if len(lst) == 1:
        return "[" + lst[0] + ",,]"
    i = len(lst)//2
    return "[" + ",".join(lst[:i]) + ",," + ",".join(lst[i:]) + "]"

def make_object_from_pairs(pairs):
    if not pairs:
        return "{}"
    return "{" + ",".join(k + ":" + v for (k, v) in pairs) + "}"

def make_object_missing_colon(pairs):
    if not pairs:
        return "{}"
    # drop a colon between one random pair (simulate missing colon)
    out = []
    for i, (k, v) in enumerate(pairs):
        if i == 0:
            out.append(k + v)  # missing colon for first pair
        else:
            out.append(k + ":" + v)
    return "{" + ",".join(out) + "}"

def make_object_trailing_comma(pairs):
    if not pairs:
        return "{}"
    return "{" + ",".join(k + ":" + v for (k, v) in pairs) + ",}"

def make_object_double_commas(pairs):
    if not pairs:
        return "{}"
    if len(pairs) == 1:
        return "{" + pairs[0][0] + ":" + pairs[0][1] + ",,}"
    i = len(pairs)//2
    left = ",".join(k + ":" + v for (k, v) in pairs[:i])
    right = ",".join(k + ":" + v for (k, v) in pairs[i:])
    return "{" + left + ",," + right + "}"

# Use st.recursive to build arrays/objects from leaves, exercising many edge cases.
# children strategy will produce textual JSON values (possibly malformed).
composite_container = st.recursive(
    leaf_value,
    lambda children: st.one_of(
        # normal arrays and variations (including trailing/double commas)
        st.lists(children, min_size=0, max_size=6).map(make_array_from_list),
        st.lists(children, min_size=0, max_size=6).map(make_array_trailing_comma),
        st.lists(children, min_size=1, max_size=6).map(make_array_double_commas),

        # normal objects: keys may be valid or malformed strings; allow duplicate keys intentionally
        # produce pairs (key_string, child)
        st.lists(st.tuples(key_string, children), min_size=0, max_size=6).map(make_object_from_pairs),
        # trailing comma in object
        st.lists(st.tuples(key_string, children), min_size=0, max_size=6).map(make_object_trailing_comma),
        # missing colon in first pair
        st.lists(st.tuples(key_string, children), min_size=1, max_size=6).map(make_object_missing_colon),
        # double commas inside object
        st.lists(st.tuples(key_string, children), min_size=1, max_size=6).map(make_object_double_commas),

        # intentionally produce objects with duplicate keys (pick some keys then duplicate)
        st.builds(
            lambda keys, vals: "{" + ",".join(k + ":" + v for k, v in zip(keys + keys[:1], vals[: len(keys)+1])) + "}",
            st.lists(key_string, min_size=1, max_size=3),
            st.lists(children, min_size=1, max_size=4),
        ),
    ),
    max_leaves=50,
)

# Deep nesting strategy: concentrates depth near the parser limit (~2048), but sometimes small depths too.
@st.composite
def deep_nesting(draw):
    # choose small or very deep (near limit)
    depth = draw(st.one_of(st.integers(min_value=0, max_value=8), st.integers(min_value=2000, max_value=2048)))
    # choose either nested arrays or nested objects (objects use a simple "k": ... pattern)
    inner = draw(st.one_of(st.just("null"), st.just("0"), st.just("\"x\""), st.just("{}"), st.just("[]")))
    form = draw(st.sampled_from(["array", "object"]))
    if depth == 0:
        return inner
    if form == "array":
        # produce [...[inner]...]
        return "[" * depth + inner + "]" * depth
    else:
        # for objects, wrap with {"k": ...}
        # use short keys to avoid enormous size; duplicate key names can appear
        return ("{" + "\"k\":" ) * depth + inner + ( "}" * depth )

# Trailing garbage branch: produce a valid leading value then arbitrary trailing characters (parser accepts trailing content)
trailing_content = st.tuples(composite_container, st.text(st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters=["\x00"]), min_size=1, max_size=20)).map(lambda t: t[0] + t[1])

# Top-level strategy: mix recursive containers, deep nesting, and trailing content variants
strategy = st.one_of(
    composite_container,
    deep_nesting(),
    trailing_content,
    # also allow standalone leaf values (strings/numbers/literals)
    leaf_value,
)
```