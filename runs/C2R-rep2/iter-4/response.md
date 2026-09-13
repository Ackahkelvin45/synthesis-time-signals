```python
from hypothesis import strategies as st
import json

# --- leaf strategies -------------------------------------------------------

# Valid JSON strings (double-quoted, with escapes and raw control bytes).
_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_unicode_esc = st.builds(
    lambda h: '\\u' + h,
    st.text(alphabet='0123456789abcdefABCDEF', min_size=4, max_size=4),
)
# lone / paired surrogate escapes
_surrogate_esc = st.builds(
    lambda h: '\\u' + h,
    st.sampled_from(['d800', 'DBFF', 'dc00', 'DFFF', 'd83d', 'de00', 'D83DDE00']),
)
_safe_cp = st.characters(
    blacklist_categories=('Cs',),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)
# raw control bytes / NUL explicitly allowed
_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_string_body = st.one_of(
    _safe_cp,
    _escapes,
    _unicode_esc,
    _surrogate_esc,
    _control,
)

_json_string = st.builds(
    lambda parts: '"' + ''.join(parts) + '"',
    st.lists(_string_body, max_size=8),
)

# Numbers: valid, extreme, and near-valid-but-malformed forms.
_valid_number = st.one_of(
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    st.builds(lambda i, f: f"{i}.{f}",
              st.integers(min_value=-10**6, max_value=10**6),
              st.integers(min_value=0, max_value=10**12).map(lambda x: str(x).lstrip('-'))),
    st.builds(lambda i, e: f"{i}e{e}",
              st.integers(min_value=-10**6, max_value=10**6),
              st.integers(min_value=-400, max_value=400)),
    st.builds(lambda i, e: f"{i}E{e}",
              st.integers(min_value=-10**6, max_value=10**6),
              st.integers(min_value=-400, max_value=400)),
    st.just('0'),
    st.just('-0'),
    st.just('1e309'),
    st.just('-1e309'),
    st.just('1E+308'),
    st.just('1e-9999'),
)

_malformed_number = st.sampled_from([
    '-', '+1', '.5', '1.', '01', '007', '0x1F', '1e', '1e+', '--1',
    '1.2.3', '1e1e1', '+', '.', '1_000', 'NaN', 'Infinity', '-Infinity',
])

_number = st.one_of(_valid_number, _malformed_number)

# --- malformed fragments ---------------------------------------------------

_unterminated_string = st.builds(
    lambda parts: '"' + ''.join(parts),
    st.lists(_string_body, max_size=6),
)

_bad_escapes = st.sampled_from(['\\x', '\\u12', '\\uZZZZ', '\\', '"'])

_malformed_token = st.one_of(
    _unterminated_string,
    _bad_escapes,
    st.sampled_from([',', ':', '}', ']', '{', '[', 'true false', 'nullx',
                     'tru', 'fals', 'nul', 'garbage', '  ', '\x00']),
)

# --- recursive value -------------------------------------------------------

_json_value = st.recursive(
    st.one_of(
        _json_string,
        _number,
        st.sampled_from(['true', 'false', 'null']),
        st.just('-'),
    ),
    lambda children: st.one_of(
        # arrays (empty, with members, trailing comma)
        st.builds(lambda vs: '[' + ','.join(vs) + ']',
                  st.lists(children, min_size=0, max_size=5)),
        st.builds(lambda vs: '[' + ','.join(vs) + ',]',
                  st.lists(children, min_size=1, max_size=5)),
        # objects with members (stressed path) + duplicates + trailing comma
        st.builds(lambda ps: '{' + ','.join(ps) + '}',
                  st.lists(
                      st.builds(lambda k, v: k + ':' + v,
                                _json_string, children),
                      min_size=0, max_size=5)),
        st.builds(lambda ps: '{' + ','.join(ps) + ',}',
                  st.lists(
                      st.builds(lambda k, v: k + ':' + v,
                                _json_string, children),
                      min_size=1, max_size=5)),
        # duplicate keys explicitly
        st.builds(lambda k, v1, v2: '{' + k + ':' + v1 + ',' + k + ':' + v2 + '}',
                  _json_string, children, children),
    ),
    max_leaves=40,
)

# --- near-valid-but-malformed whole documents ------------------------------

_malformed_doc = st.one_of(
    # double commas
    st.just('[1,,2]'),
    st.just('[,]'),
    st.just('[,1]'),
    st.just('{"a":1,, "b":2}'),
    # missing colons
    st.just('{"a" 1}'),
    st.just('{"a"}'),
    st.just('{1:2}'),
    # unterminated
    st.just('{"a":1'),
    st.just('[1,2'),
    st.just('"unterminated'),
    # trailing content
    st.just('1abc'),
    st.just('[]xyz'),
    st.just('true false'),
    # bare keys / single quotes / comments (rejected under default settings)
    st.just("{a:1}"),
    st.just("'x'"),
    st.just('//x\n1'),
    st.just('/* c */1'),
    # NUL / control bytes
    st.just('\x00'),
    st.just('{"a":\x00}'),
    st.just('[\x00]'),
    st.just('"a\x00b"'),
    st.just('\x01\x02\x03'),
    # deep nesting (no cap on parser side)
    st.integers(min_value=1, max_value=2000).map(lambda n: '[' * n + ']' * n),
    st.integers(min_value=1, max_value=2000).map(lambda n: '{"a":' * n + '1' + '}' * n),
    # lone dash / non-finite
    st.just('-'),
    st.just('1e309'),
)

# --- near-crash mutations around the crashing input '1e309' ----------------

# Structural mutations of the crashing number token: exponent-boundary and
# overflow-adjacent forms, plus the token embedded in containers.
_crash_num_variants = st.sampled_from([
    '1e309', '-1e309', '1E309', '1e+309', '1e-309',
    '1e308', '1e310', '1e999', '1e1000', '1e9999', '1e-9999',
    '9e309', '9e999', '0e309', '0e999', '1.0e309', '-1.0e309',
    '1e309e309', '1e3090', '1e30900',
])

_crash_token = st.one_of(
    _crash_num_variants,
    # digits + exponent overflow-shaped
    st.builds(lambda d, e: f"{d}e{e}",
              st.integers(min_value=0, max_value=10**9).map(str),
              st.integers(min_value=300, max_value=9999)),
)

# wrap the crashing token structurally (arrays / objects / whitespace)
_crash_wrapped = st.one_of(
    _crash_token,
    st.builds(lambda t: '[' + t + ']', _crash_token),
    st.builds(lambda t: '[' + t + ',' + t + ']', _crash_token),
    st.builds(lambda t: '{"a":' + t + '}', _crash_token),
    st.builds(lambda t: '{"a":' + t + ',"b":' + t + '}', _crash_token),
    st.builds(lambda t: '{"a":[' + t + ']}', _crash_token),
    st.builds(lambda n, t: '[' * n + t + ']' * n,
              st.integers(min_value=1, max_value=50), _crash_token),
    st.builds(lambda n, t: '{"a":' * n + t + '}' * n,
              st.integers(min_value=1, max_value=50), _crash_token),
    st.builds(lambda a, t, b: a + t + b, _whitespace_placeholder, _crash_token, _whitespace_placeholder),
)

# --- top-level strategy ----------------------------------------------------

_whitespace = st.text(alphabet=' \t\n\r', max_size=3)
_whitespace_placeholder = _whitespace

_document = st.one_of(
    _json_value,
    _malformed_doc,
    _crash_wrapped,
    # wrap with optional leading/trailing whitespace
    st.builds(lambda a, v, b: a + v + b, _whitespace, _json_value, _whitespace),
)

strategy = _document
```