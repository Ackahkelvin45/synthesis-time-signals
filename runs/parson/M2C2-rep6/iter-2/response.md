```python
from hypothesis import strategies as st
import json

# Helper generators for pieces
_HEX4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda i: "%04X" % i)
_SURROGATE_HIGH = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda i: "%04X" % i)
_SURROGATE_LOW = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda i: "%04X" % i)

# safe printable chars excluding double-quote, backslash and NUL
_safe_char = st.characters(blacklist_characters='"\\\x00', min_codepoint=0x20, max_codepoint=0x10FFFF)

# small raw-control chars excluding NUL (to allow some malformed raw-control inside strings)
_control_char = st.sampled_from([chr(i) for i in range(1, 0x20)])  # excludes \x00

# Common escape sequences to embed as literal backslash sequences inside JSON strings
_escape_seq = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

# Generate JSON string content, sometimes well-formed, sometimes with escapes, surrogate escapes,
# sometimes unterminated (missing closing quote), sometimes containing raw control chars (but not NUL).
@st.composite
def json_string(draw, allow_unterminated=True):
    parts = []
    # choose length
    n = draw(st.integers(min_value=0, max_value=5))
    for _ in range(n):
        kind = draw(st.sampled_from(['safe', 'escape', 'unicode', 'surrogate', 'control', 'rawquote']))
        if kind == 'safe':
            parts.append(draw(st.text(alphabet=_safe_char, min_size=1, max_size=6)))
        elif kind == 'escape':
            parts.append(draw(_escape_seq))
        elif kind == 'unicode':
            # \uXXXX
            parts.append('\\u' + draw(_HEX4))
        elif kind == 'surrogate':
            # either a single surrogate escape or a valid surrogate pair
            if draw(st.booleans()):
                parts.append('\\u' + draw(_SURROGATE_HIGH))
            else:
                parts.append('\\u' + draw(_SURROGATE_HIGH) + '\\u' + draw(_SURROGATE_LOW))
        elif kind == 'control':
            parts.append(draw(_control_char))
        elif kind == 'rawquote':
            # insert an unescaped quote to create malformed string contents
            # we will include it inside the quoted literal (i.e., not escaped) -> syntactic error
            parts.append('"')
    inner = ''.join(parts)
    quoted = '"' + inner + '"'
    # sometimes emit unterminated string (missing closing quote) or missing opening quote
    if allow_unterminated and draw(st.booleans()):
        malformed_kind = draw(st.sampled_from(['unterminated', 'no_open', 'normal']))
        if malformed_kind == 'unterminated':
            return '"' + inner  # missing closing quote
        if malformed_kind == 'no_open':
            return inner + '"'  # missing opening quote
    return quoted

# Number generator: valid and many near-valid/malformed variants
@st.composite
def json_number(draw):
    # valid integer (strategy, not drawn yet)
    int_valid = st.integers(min_value=0, max_value=999999999).map(str)
    # valid negative
    neg_valid = st.integers(min_value=-999999999, max_value=-1).map(str)
    # fraction
    frac = st.tuples(st.one_of(int_valid, neg_valid), st.integers(min_value=0, max_value=999999)).map(
        lambda t: t[0] + '.' + ('%d' % t[1]))
    # exponent variants including overflow
    exp_big = st.sampled_from(['1e308', '1e309', '1e400', '-1e309', '9e9999'])
    # near-valid: leading plus, .5, 1., 01, +.5, +1, -. , -
    near_valid = st.sampled_from(['+1', '.5', '1.', '01', '+.5', '+', '-', '-.', '1e01', '1e+01', '-0', '00'])
    choice = draw(st.sampled_from(['int_valid', 'neg_valid', 'frac', 'exp_big', 'near_valid']))
    if choice == 'int_valid':
        return draw(int_valid)
    if choice == 'neg_valid':
        return draw(neg_valid)
    if choice == 'frac':
        return draw(frac)
    if choice == 'exp_big':
        return draw(exp_big)
    return draw(near_valid)

# Literal tokens
_literal = st.sampled_from(['true', 'false', 'null'])

# Helper to optionally append trailing content after a complete value (parser accepts trailing content).
_trailing = st.one_of(
    st.just(''),
    st.text(min_size=1, max_size=5, alphabet=st.characters(blacklist_characters='\x00', min_codepoint=0x20)),
    st.sampled_from([' ', '  ', '\n', ' trailing', 'XYZ', 'garbage123'])
)

# Build objects and arrays recursively using a composite that controls nesting depth.
@st.composite
def json_value(draw):
    # Decide on target max depth: most cases shallow, occasionally deep near the parser cap (~2048)
    deep_mode = draw(st.booleans().filter(lambda b: True))  # draw once to allow branching
    if draw(st.integers(min_value=0, max_value=99)) == 0:
        # rare extreme deep draw near the parser cap
        max_depth = draw(st.integers(min_value=1500, max_value=2048))
    else:
        if deep_mode:
            max_depth = draw(st.integers(min_value=3, max_value=12))
        else:
            max_depth = draw(st.integers(min_value=0, max_value=4))

    # internal recursive builder
    def build(depth_remaining):
        # When depth_remaining exhausted, force a base token
        if depth_remaining <= 0:
            return draw(st.one_of(json_string(), json_number(), _literal))
        choice = draw(st.sampled_from(['base', 'obj', 'arr']))
        if choice == 'base':
            return draw(st.one_of(json_string(), json_number(), _literal))
        if choice == 'arr':
            # decide number of elements; to encourage deep single-branch nesting, sometimes make single element
            if draw(st.booleans()):
                n = draw(st.integers(min_value=0, max_value=4))
            else:
                n = 1
            elems = []
            for i in range(n):
                elems.append(build(depth_remaining - 1))
            # sometimes inject malformed forms: double commas, trailing comma, missing comma
            mal = draw(st.booleans())
            if mal:
                malkind = draw(st.sampled_from(['doublecomma', 'trailingcomma', 'missingcomma']))
                if malkind == 'doublecomma' and len(elems) >= 1:
                    # produce something like [1,,2]
                    if len(elems) == 1:
                        body = elems[0] + ',,'
                    else:
                        body = ','.join(elems[:1]) + ',,' + ','.join(elems[1:])
                    return '[' + body + ']'
                if malkind == 'trailingcomma':
                    return '[' + (','.join(elems) + ',' if elems else ',') + ']'
                if malkind == 'missingcomma' and len(elems) >= 2:
                    # join first two without comma
                    body = elems[0] + elems[1]
                    if len(elems) > 2:
                        body += ',' + ','.join(elems[2:])
                    return '[' + body + ']'
            return '[' + ','.join(elems) + ']'
        # obj
        # decide number of pairs; for deep single-branch nesting, often 1
        if draw(st.booleans()):
            npairs = draw(st.integers(min_value=0, max_value=4))
        else:
            npairs = 1
        pairs = []
        # sometimes force duplicate keys
        force_dup = draw(st.booleans())
        dup_key = None
        if force_dup:
            # create a key that will be duplicated
            dup_key = draw(json_string(allow_unterminated=False))
        for i in range(npairs):
            if dup_key and draw(st.booleans()):
                key = dup_key
            else:
                # keys should be JSON strings but can be malformed sometimes
                key = draw(json_string(allow_unterminated=False))
            # sometimes generate missing colon or no quotes for key (malformed)
            if draw(st.booleans()):
                malformed_key = draw(st.sampled_from(['no_colon', 'no_quotes', 'normal']))
            else:
                malformed_key = 'normal'
            val = build(depth_remaining - 1)
            if malformed_key == 'no_colon':
                pairs.append(key + ' ' + val)  # missing colon
            elif malformed_key == 'no_quotes':
                # strip quotes if present to simulate unquoted key
                if key.startswith('"') and key.endswith('"'):
                    key_un = key[1:-1]
                else:
                    key_un = key
                pairs.append(key_un + ':' + val)
            else:
                pairs.append(key + ':' + val)
        # sometimes inject malformed commas or trailing comma/double comma
        if draw(st.booleans()):
            malkind = draw(st.sampled_from(['doublecomma', 'trailingcomma', 'normal']))
            if malkind == 'doublecomma' and len(pairs) >= 1:
                if len(pairs) == 1:
                    body = pairs[0] + ',,'
                else:
                    body = ','.join(pairs[:1]) + ',,' + ','.join(pairs[1:])
                return '{' + body + '}'
            if malkind == 'trailingcomma':
                return '{' + (','.join(pairs) + ',' if pairs else ',') + '}'
        return '{' + ','.join(pairs) + '}'

    root = build(max_depth)
    # sometimes append trailing content after a complete value (parser accepts trailing content)
    if draw(st.booleans()):
        root = root + draw(_trailing)
    return root

# Top-level strategy name required by the module
strategy = json_value()
```