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

# --- near-crash intensification --------------------------------------------
# The last run produced a UBSan crash ("applying-non-zero-offset-to-null-pointer")
# in the parse path. Intensify structurally around that crashing shape by
# generating documents that combine a NUL byte (the null-pointer trigger) with
# the surrounding structural context (containers, strings, keys, whitespace,
# trailing content) so the parser is exercised right at the null-offset site.

_near_crash_seed = st.sampled_from(['\x00', '\x00\x00', '\x01', '\x00a', 'a\x00'])

_near_crash_doc = st.one_of(
    # NUL embedded in each structural position
    st.builds(lambda s, v: s + v, _near_crash_seed, _json_value),
    st.builds(lambda v, s: v + s, _json_value, _near_crash_seed),
    st.builds(lambda a, s, b: a + s + b, _whitespace, _near_crash_seed, _whitespace),
    # NUL as / around object keys and values
    st.builds(lambda s, v: '{"' + s + '":' + v + '}', _near_crash_seed, _json_value),
    st.builds(lambda k, s: '{' + k + ':' + s + '}', _json_string, _near_crash_seed),
    st.builds(lambda s: '[' + s + ']', _near_crash_seed),
    st.builds(lambda s, v: '[' + s + ',' + v + ']', _near_crash_seed, _json_value),
    st.builds(lambda v, s: '[' + v + ',' + s + ']', _json_value, _near_crash_seed),
    # NUL inside strings, including unterminated
    st.builds(lambda s: '"' + s + '"', _near_crash_seed),
    st.builds(lambda s: '"' + s, _near_crash_seed),
    # NUL with trailing/leading structural fragments
    st.builds(lambda s, t: s + t, _near_crash_seed, _malformed_token),
    st.builds(lambda t, s: t + s, _malformed_token, _near_crash_seed),
    # NUL combined with deep nesting (stress offset arithmetic on deep frames)
    st.builds(lambda n, s: '[' * n + s + ']' * n,
              st.integers(min_value=1, max_value=64), _near_crash_seed),
    st.builds(lambda n, s: '{"a":' * n + s + '}' * n,
              st.integers(min_value=1, max_value=64), _near_crash_seed),
    # NUL adjacent to numbers / literals (token boundary offsets)
    st.builds(lambda s, n: s + n, _near_crash_seed, _number),
    st.builds(lambda n, s: n + s, _number, _near_crash_seed),
    st.builds(lambda s, lit: s + lit, _near_crash_seed,
              st.sampled_from(['true', 'false', 'null'])),
    # multiple NULs at varying offsets
    st.builds(lambda parts: ''.join(parts),
              st.lists(st.one_of(_near_crash_seed, _malformed_token),
                       min_size=1, max_size=6)),
)

# --- top-level strategy ----------------------------------------------------

_whitespace = st.text(alphabet=' \t\n\r', max_size=3)

_document = st.one_of(
    _json_value,
    _malformed_doc,
    _near_crash_doc,
    # wrap with optional leading/trailing whitespace
    st.builds(lambda a, v, b: a + v + b, _whitespace, _json_value, _whitespace),
)

strategy = _document