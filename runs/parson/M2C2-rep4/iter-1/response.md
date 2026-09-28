```python
from hypothesis import strategies as st
import json

# Basic safe characters for JSON string content (avoid raw NUL and quotes/backslash which need escaping)
_SAFE_CHARS = st.characters(blacklist_characters=['"', '\\', '\x00'])

# Proper JSON string via json.dumps (produces quoted, escaped form)
proper_string = st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=30).map(json.dumps)

# Explicit \uXXXX escapes (including surrogate range) as raw escape sequences inside a quoted literal
unicode_escape = st.integers(min_value=0, max_value=0xFFFF).map(lambda i: '"\\u%04X"' % i)
surrogate_escape = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda i: '"\\u%04X"' % i)

# Strings containing raw control characters (but never the NUL '\x00')
control_char = st.sampled_from(['\x01', '\x02', '\x07', '\x1F']).map(lambda c: '"' + c + '"')

# Unterminated string: a valid json.dumps but drop the trailing quote -> near-valid-but-malformed
unterminated_string = st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=20).map(lambda s: json.dumps(s)[:-1])

# JSON literals
literals = st.sampled_from(["true", "false", "null"])

# Valid numbers per the grammar
nonzero_int = st.integers(min_value=1, max_value=999999).map(str)
zero = st.just("0")
signed_int = st.one_of(nonzero_int, zero).map(lambda s: s).map(lambda s: s)  # placeholder to allow negative in compose
valid_integer = st.one_of(zero, st.integers(min_value=1, max_value=999999).map(str))
valid_number = st.one_of(
    # simple ints (possibly negative)
    st.integers(min_value=-999999, max_value=999999).map(str),
    # fractions
    st.tuples(st.integers(min_value=-999999, max_value=999999).map(str), st.integers(min_value=0, max_value=999999).map(lambda d: ("%06d" % d).rstrip('0') or "0")).map(lambda t: t[0] + "." + t[1]),
    # exponents
    st.tuples(st.integers(min_value=-999999, max_value=999999).map(str), st.sampled_from(["e", "E"]), st.integers(min_value=-10, max_value=10).map(lambda s: ("+" if s >= 0 else "") + str(abs(s)))).map(lambda t: t[0] + t[1] + t[2])
)

# Malformed / near-valid numeric forms to exercise parser leniencies and edge cases
malformed_numbers = st.sampled_from([
    "+1",    # leading plus (near-valid-but-malformed)
    ".5",    # leading dot (may be leniently accepted)
    "1.",    # trailing dot
    "01",    # leading zero with extra digit (forbidden by grammar)
    "-",     # lone minus (parser accepts as 0)
    "-.",    # lone minus dot
    "1e309", # extreme exponent -> overflow
    "9e9999",# extreme exponent huge
    "-1e999" # negative extreme exponent
])

# Base (non-recursive) JSON value strategy: strings, numbers, literals.
base_value = st.one_of(
    proper_string,
    unicode_escape,
    surrogate_escape,
    control_char,
    unterminated_string,
    valid_number,
    malformed_numbers,
    literals
)

# Helper to build object strings from a list of (key, value) pairs (keys are already JSON-quoted)
def _make_object_from_pairs(pairs):
    if not pairs:
        return "{}"
    return "{" + ",".join(k + ":" + v for k, v in pairs) + "}"

# Helper to build array strings from a list of values
def _make_array(vals):
    if not vals:
        return "[]"
    return "[" + ",".join(vals) + "]"

# Extend function for st.recursive to produce arrays and objects (including duplicate-key objects)
def _extend(inner):
    # arrays: list of child values
    arrays = st.lists(inner, min_size=0, max_size=5).map(_make_array)

    # objects built from lists of (key,value) pairs to allow duplicate keys
    key_text = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=8).map(json.dumps)
    pair = st.tuples(key_text, inner)
    pairs_list = st.lists(pair, min_size=0, max_size=6)
    objects = pairs_list.map(_make_object_from_pairs)

    return st.one_of(arrays, objects)

# Recursive value strategy (uses st.recursive per requirement)
recursive_value = st.recursive(base_value, _extend, max_leaves=200)

# Deep nesting near parser limit (~2048). Build nested arrays like "[[[...0...]]]"
deep_nesting = st.integers(min_value=2000, max_value=2048).map(lambda depth: "[" * depth + "0" + "]" * depth)

# Generate explicit duplicate-keys object variants (concentrated technique)
def _duplicate_keys_obj():
    # key text (quoted) and a small set of values
    key = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=6).map(json.dumps)
    value_choices = st.lists(recursive_value, min_size=1, max_size=4)
    # produce objects where one key is duplicated intentionally
    return st.tuples(key, value_choices).map(lambda kv: _make_object_from_pairs([(kv[0], v) for v in kv[1]] + [(kv[0], kv[1][0])]))

duplicate_keys_obj = _duplicate_keys_obj()

# Trailing garbage after a complete value
trailing_garbage = st.tuples(recursive_value, st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=1, max_size=10)).map(lambda t: t[0] + t[1])

# Mutators: near-valid-but-malformed transformations applied to otherwise valid-looking JSON strings.
def _insert_double_comma(s):
    # If there is a comma, duplicate the first one, else try to create a double-comma inside brackets/braces
    idx = s.find(",")
    if idx != -1:
        return s[:idx+1] + "," + s[idx+1:]
    if s.startswith("["):
        return "[" + "," + s[1:]
    if s.startswith("{"):
        return "{" + "," + s[1:]
    # fallback: append ",,"
    return s + ",,"

def _remove_colon(s):
    # Remove the first colon found (common object key:value separator) to create missing-colon variant
    idx = s.find(":")
    if idx != -1:
        return s[:idx] + s[idx+1:]
    return s

def _remove_closing_bracket(s):
    # Drop the final closing bracket or brace to create unterminated container
    if s.endswith("]") or s.endswith("}"):
        return s[:-1]
    return s

def _remove_last_quote(s):
    # Remove the last double-quote character to unterminate a string literal inside the JSON text
    idx = s.rfind('"')
    if idx != -1:
        return s[:idx] + s[idx+1:]
    return s

def _prefix_plus_to_number(s):
    # Insert '+' before the first digit occurrence to create a leading plus numeric variant
    for i, ch in enumerate(s):
        if ch.isdigit():
            return s[:i] + "+" + s[i:]
    return "+" + s

def _prefix_dot_to_number(s):
    # Insert '.' before the first digit occurrence
    for i, ch in enumerate(s):
        if ch.isdigit():
            return s[:i] + "." + s[i:]
    return "." + s

def _force_leading_zero(s):
    # Turn first solitary '0' into '01' to create illegal leading-zero scenario
    idx = s.find("0")
    if idx != -1:
        return s[:idx] + "01" + s[idx+1:]
    return s

def _append_overflow_exponent(s):
    # Append an extreme exponent after first digit sequence
    for i, ch in enumerate(s):
        if ch.isdigit():
            # put e309 after that digit
            return s[:i+1] + "e309" + s[i+1:]
    return s + "e309"

# List of mutator functions
_MUTATORS = [
    _insert_double_comma,
    _remove_colon,
    _remove_closing_bracket,
    _remove_last_quote,
    _prefix_plus_to_number,
    _prefix_dot_to_number,
    _force_leading_zero,
    _append_overflow_exponent
]

# Mutated variants: pair a generated value with a sampled mutator, then apply it
mutated_variants = st.tuples(recursive_value, st.sampled_from(_MUTATORS)).map(lambda t: t[1](t[0]))

# Combine many strategies into final top-level strategy.
# Mix valid recursive JSON, mutated near-valid variants, deep nesting near the parser limit,
# explicit duplicate-keys objects, and trailing-garbage accepted-by-parser cases.
strategy = st.one_of(
    recursive_value,      # standard recursive JSON-ish values (may already include many edge cases)
    mutated_variants,     # near-valid malformed inputs
    deep_nesting,         # deep nesting near parser limit to exercise depth handling
    duplicate_keys_obj,   # explicit duplicate key objects (expected to be rejected by parser)
    trailing_garbage      # valid value followed by trailing content (accepted by parser)
)
```