```python
from hypothesis import strategies as st
import json

# Safe characters for JSON string content (no control chars, no quote or backslash)
_safe_char = st.characters(min_codepoint=0x20, blacklist_characters='"\\"')

# Common simple escapes as they appear in JSON text (each is two characters: backslash + char)
_simple_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

# Unicode escape sequences like \u00A9
_unicode_escape = st.integers(min_value=0, max_value=0xFFFF).map(lambda n: '\\u' + format(n, '04x'))

# Surrogate escapes explicitly (e.g. \uD800 .. \uDFFF)
_surrogate_escape = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda n: '\\u' + format(n, '04x'))

# Always allow the six-character \u0000 escape (represents NUL safely)
_escaped_nul = st.just('\\u0000')

# A token inside a JSON string: either a safe literal char or an escape sequence
_string_token = st.one_of(_safe_char.map(lambda s: s), _simple_esc, _unicode_escape, _surrogate_escape, _escaped_nul)

# Valid JSON STRING literal (may be empty). We produce safe content; malformed variants produced elsewhere.
_string_content = st.lists(_string_token, min_size=0, max_size=12).map(lambda parts: ''.join(parts))
_string_literal = _string_content.map(lambda s: '"' + s + '"')

# Number strategies: valid integers, decimals, exponents, plus intentionally "edge" and malformed numbers.
_valid_int = st.integers(min_value=0, max_value=10**12).map(lambda n: '0' if n == 0 else str(n))
_neg_int = st.integers(min_value=-10**12, max_value=-1).map(str)

_valid_decimal = st.tuples(_valid_int, st.integers(min_value=0, max_value=10**9)).map(
    lambda t: t[0] + '.' + (str(t[1]) if t[1] != 0 else '0')
)

# Exponent forms (including extreme exponents that may overflow e.g. 1e309)
_exponent_tail = st.one_of(
    st.just('e309'),  # known overflow-ish magnitude to test non-finite rejection
    st.integers(min_value=0, max_value=10000).map(lambda n: 'e' + str(n)),
    st.integers(min_value=0, max_value=10000).map(lambda n: 'E+' + str(n)),
    st.integers(min_value=0, max_value=10000).map(lambda n: 'E-' + str(n)),
)
_with_exponent = st.one_of(_valid_int, _valid_decimal).flatmap(
    lambda m: _exponent_tail.map(lambda e: m + e)
)

# Some deliberately malformed / near-valid number forms that exercise leniencies:
_malformed_number = st.sampled_from([
    '+1', '+1.0', '+', '.5', '-.5', '1.', '01', '-',
    '-.', '+.5', '1e309', '-1e309', '1e10000'
])

_number = st.one_of(_with_exponent, _valid_decimal, _valid_int, _neg_int, _malformed_number)

# Base leaf values for recursive JSON generation
_base_value = st.one_of(
    _string_literal,   # STRING
    _number,           # NUMBER or near-number
    st.just('true'),
    st.just('false'),
    st.just('null'),
)

# Recursive construction of arrays and objects using st.recursive. Objects use quoted STRING keys.
def _make_object_strategy(child):
    # list of pairs (STRING, value). Use smallish maps so we can also generate empty {}.
    return st.lists(st.tuples(_string_literal, child), min_size=0, max_size=6).map(
        lambda pairs: '{' + ','.join(k + ':' + v for (k, v) in pairs) + '}'
    )

def _make_array_strategy(child):
    return st.lists(child, min_size=0, max_size=8).map(lambda items: '[' + ','.join(items) + ']')

_json_struct = st.recursive(
    _base_value,
    lambda children: st.one_of(_make_array_strategy(children), _make_object_strategy(children)),
    max_leaves=50
)

# Deep nesting bias: concentrate near the parser's practical limit (~2048) but include shallow as well.
# We bias by repeating the deep-range strategy multiple times in the one_of call.
_deep_index = st.one_of(
    # deep region repeated to bias draws toward deep nesting
    *( [st.integers(min_value=1800, max_value=2050)] * 6 )
    + [st.integers(min_value=0, max_value=50)]
)

# Produce deeply nested arrays (valid JSON when balanced). Use a compact inner value '0'.
_deep_nested_arrays = _deep_index.map(lambda n: ('[' * n) + '0' + (']' * n))

# Also produce deeply nested objects like {"k": {"k": ... 0 ...}} using repeated pair wrappers.
_deep_index_obj = st.one_of(*( [st.integers(min_value=1800, max_value=2050)] * 4 + [st.integers(0, 50)] ))
_deep_nested_objects = _deep_index_obj.map(lambda n: ('{"k":' * n) + '0' + ('}' * n))

# Duplicate-keys object (the parser rejects duplicate keys; generator must produce them)
_duplicate_keys_obj = st.tuples(
    # choose a key string (without surrounding quotes string literal contains quotes already)
    _string_literal,
    _json_struct,
    _json_struct
).map(lambda t: '{' + t[0] + ':' + t[1] + ',' + t[0] + ':' + t[2] + '}')

# Strings focusing on escapes (mostly standalone)
_string_with_escapes = _string_content.map(lambda s: '"' + s + '"')

# Trailing garbage after a valid value (the parser accepts trailing content)
_trailing_garbage = st.tuples(_json_struct, st.text(min_size=1, max_size=40)).map(lambda t: t[0] + ' ' + t[1])

# Corruptions applied to otherwise valid JSON to create near-valid-but-malformed inputs.
@st.composite
def _corrupt_json(draw):
    base = draw(_json_struct)
    choice = draw(st.integers(min_value=0, max_value=6))
    s = base
    if choice == 0:
        # Insert a double-comma inside arrays/objects if possible
        if ',' in s:
            idx = s.find(',')
            s = s[:idx] + ',,' + s[idx+1:]
        else:
            # insert a spurious comma near the middle
            mid = len(s) // 2
            s = s[:mid] + ',,' + s[mid:]
    elif choice == 1:
        # Remove the first colon (missing colon)
        if ':' in s:
            idx = s.find(':')
            s = s[:idx] + s[idx+1:]
        else:
            # remove a random bracket
            s = s.replace('{', '', 1) if '{' in s else s
    elif choice == 2:
        # Unterminated string: remove a trailing double quote from the first string literal
        q = s.find('"')
        if q != -1:
            # find the next quote
            q2 = s.find('"', q + 1)
            if q2 != -1:
                s = s[:q2] + s[q2+1:]  # drop the closing quote
            else:
                # if only one quote, just leave as-is (already unterminated)
                pass
    elif choice == 3:
        # Trailing comma in array/object
        if s.endswith(']') or s.endswith('}'):
            s = s[:-1] + ',' + s[-1]
        else:
            s = s + ','
    elif choice == 4:
        # Leading plus or lone dot-number: prepend a '+' or '.' to a number occurrence if present
        import re
        m = re.search(r'(?<![A-Za-z0-9_"\'])\d+(\.\d+)?([eE][+-]?\d+)?', s)
        if m:
            start, end = m.span()
            kind = draw(st.sampled_from(['+', '.']))
            s = s[:start] + kind + s[start:]
        else:
            s = '+' + s
    elif choice == 5:
        # Remove a comma between two items (join two items) producing missing comma
        parts = s.split(',')
        if len(parts) >= 2:
            i = min(len(parts) - 2, 1)
            parts[i] = parts[i] + parts[i+1]
            del parts[i+1]
            s = ','.join(parts)
        else:
            s = s.replace('","', '"', 1)
    else:
        # Insert random ascii control characters (except NUL) into the text to probe control handling.
        # We never inject actual NUL ('\x00') into the generated str.
        ctrl = draw(st.sampled_from(['\x01', '\x02', '\x03', '\x07', '\x0b']))
        pos = draw(st.integers(min_value=0, max_value=max(0, len(s))))
        s = s[:pos] + ctrl + s[pos:]
    return s

# Standalone malformed examples to ensure coverage of listed edge-cases:
_standalone_malformed = st.sampled_from([
    '{"a":0,, "b":1}',    # double comma
    '{"a" 0}',           # missing colon
    '["unterminated-string]',  # unterminated string inside array
    '"unterminated',     # lone string without closing quote
    '+1',                # leading plus
    '.5',                # leading dot fraction
    '01',                # leading zero with extra digits (illegal per grammar)
    '-',                 # lone sign (parser accepts as 0)
    '-.',                # odd lone sign+dot
    '1e309',             # extreme exponent (overflow -> non-finite rejected)
    '{"k":0,"k":1}',     # duplicate keys (parser rejects)
])

# Combine many strategies into the final top-level strategy
strategy = st.one_of(
    # Valid-ish structured JSON
    _json_struct,
    # Deep nesting cases to exercise the parser's nesting limit
    _deep_nested_arrays,
    _deep_nested_objects,
    # Duplicate keys (intentional spec/subset divergence)
    _duplicate_keys_obj,
    # Strings emphasizing escape sequences
    _string_with_escapes,
    # Standalone numbers / edge numeric forms
    _number,
    # Trailing garbage after otherwise-valid JSON value
    _trailing_garbage,
    # Corrupted near-valid inputs
    _corrupt_json(),
    # Explicit malformed examples
    _standalone_malformed,
)
```