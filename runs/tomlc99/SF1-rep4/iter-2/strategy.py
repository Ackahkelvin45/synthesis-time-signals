from hypothesis import strategies as st

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- strings ----------

def _esc():
    return st.sampled_from([
        '\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t',
        '\\/', '\\u0000', '\\u00e9', '\\u0041', '\\uFFFF',
        '\\U0001F600', '\\U00000041',
        '\\q', '\\u12', '\\U0000', '\\',  # malformed escapes
    ])

_basic_char = st.one_of(
    st.sampled_from(list('abcXYZ019 _-./:;,!?')),
    st.sampled_from(['\x01', '\x02', '\x7f', '\x1f']),
    st.sampled_from(['é', 'ü', 'ß', 'Ω', '中', '😀', '\u00a0']),
)

def _basic_body(allow_nl=False):
    parts = [st.one_of(_basic_char, _esc())]
    if allow_nl:
        parts.append(st.just('\n'))
        parts.append(st.just('\r\n'))
    return st.lists(st.one_of(*parts), max_size=6).map(_join)

def basic_string():
    return st.builds(lambda b: '"' + b + '"', _basic_body())

def ml_basic_string():
    return st.builds(lambda b: '"""' + b + '"""', _basic_body(allow_nl=True))

def literal_string():
    body = st.lists(
        st.one_of(
            st.sampled_from(list("abcXYZ019 _-./")),
            st.sampled_from(['\x01', '\x7f', 'é', '中', '\\', '"']),
        ),
        max_size=6,
    ).map(_join)
    return st.builds(lambda b: "'" + b + "'", body)

def ml_literal_string():
    body = st.lists(
        st.one_of(
            st.sampled_from(list("abcXYZ019 _-./")),
            st.just('\n'),
            st.just('\r\n'),
            st.sampled_from(['\x01', 'é', '中', '"', "'"]),
        ),
        max_size=6,
    ).map(_join)
    return st.builds(lambda b: "'''" + b + "'''", body)

def any_string():
    return st.one_of(basic_string(), ml_basic_string(),
                     literal_string(), ml_literal_string())

# ---------- numbers ----------

def _digits(lo, hi, alphabet='0123456789'):
    return st.lists(st.sampled_from(list(alphabet)), min_size=lo, max_size=hi).map(_join)

def _underscored(alphabet='0123456789'):
    head = st.sampled_from(list(alphabet))
    tail = st.lists(st.sampled_from(list(alphabet) + ['_']), max_size=8).map(_join)
    return st.tuples(head, tail).map(lambda t: t[0] + t[1])

def dec_int():
    sign = st.sampled_from(['', '', '', '+', '-'])
    body = st.one_of(
        _digits(1, 4),
        _digits(1, 20),
        st.just('0'),
        st.just('007'),
        _underscored(),
        st.just('9' * 30),
        st.just('9223372036854775808'),
        st.just('18446744073709551616'),
    )
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])

def hex_int():
    return st.builds(
        lambda s, b: s + '0x' + b,
        st.sampled_from(['', '+', '-']),
        st.one_of(_underscored('0123456789abcdefABCDEF'), st.just('F' * 20)),
    )

def oct_int():
    return st.builds(
        lambda s, b: s + '0o' + b,
        st.sampled_from(['', '+', '-']),
        st.one_of(_underscored('01234567'), st.just('7' * 20)),
    )

def bin_int():
    return st.builds(
        lambda s, b: s + '0b' + b,
        st.sampled_from(['', '+', '-']),
        st.one_of(_underscored('01'), st.just('1' * 40)),
    )

def integer():
    return st.one_of(dec_int(), hex_int(), oct_int(), bin_int())

def _exp():
    return st.builds(
        lambda e, s, d: e + s + d,
        st.sampled_from(['e', 'E']),
        st.sampled_from(['', '', '+', '-']),
        _underscored(),
    )

def float_():
    sign = st.sampled_from(['', '', '+', '-'])
    body = st.one_of(
        st.builds(lambda a, b: a + '.' + b, _digits(1, 3), _digits(0, 3)),
        st.builds(lambda a, b: a + '.' + b, _digits(1, 3), _digits(1, 3)),
        st.just('1.'),
        st.just('.5'),
        st.builds(lambda a, e: a + e, _digits(1, 3), _exp()),
        st.builds(lambda a, b, e: a + '.' + b + e, _digits(1, 3), _digits(1, 3), _exp()),
        st.just('1e309'),
        st.just('1e-309'),
        st.just('1.7976931348623157e308'),
        st.just('0.000000000000000000001'),
    )
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])

def inf_nan():
    return st.builds(
        lambda s, w: s + w,
        st.sampled_from(['', '+', '-']),
        st.sampled_from(['inf', 'nan']),
    )

def floating_point():
    return st.one_of(float_(), inf_nan())

# ---------- dates ----------

def _two(lo=0, hi=99):
    return st.integers(min_value=lo, max_value=hi).map(lambda n: "%02d" % n)

def _four():
    return st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)

def _partial_time():
    return st.builds(
        lambda h, m, s, f: h + ':' + m + ':' + s + f,
        _two(0, 23), _two(0, 59), _two(0, 60),
        st.one_of(st.just(''), st.builds(lambda d: '.' + d, _digits(1, 6))),
    )

def _full_date():
    return st.builds(
        lambda y, m, d: y + '-' + m + '-' + d,
        _four(), _two(0, 13), _two(0, 32),
    )

def _offset():
    return st.one_of(
        st.just('Z'),
        st.just('z'),
        st.builds(lambda s, h, m: s + h + ':' + m,
                  st.sampled_from(['+', '-']), _two(0, 23), _two(0, 59)),
    )

def date_time():
    return st.one_of(
        st.builds(lambda d, t: d + 'T' + t, _full_date(), _partial_time()),
        st.builds(lambda d, t: d + 't' + t, _full_date(), _partial_time()),
        st.builds(lambda d, t: d + ' ' + t, _full_date(), _partial_time()),
        st.builds(lambda d, t, o: d + 'T' + t + o, _full_date(), _partial_time(), _offset()),
        st.builds(lambda d, t, o: d + ' ' + t + o, _full_date(), _partial_time(), _offset()),
        _full_date(),
        _partial_time(),
        st.just('1979-02-30'),
        st.just('1979-13-45T25:61:61Z'),
    )

# ---------- keys ----------

_unquoted_key = st.lists(
    st.sampled_from(list('abcXYZ019_-')),
    min_size=1, max_size=8,
).map(_join)

def simple_key():
    return st.one_of(
        _unquoted_key,
        basic_string(),
        literal_string(),
        st.just('""'),
        st.just("''"),
        st.just('k' * 50),
    )

def key():
    return st.one_of(
        simple_key(),
        st.lists(simple_key(), min_size=2, max_size=4).map(lambda xs: '.'.join(xs)),
    )

# ---------- values (recursive) ----------

def _scalar():
    return st.one_of(
        any_string(),
        integer(),
        floating_point(),
        st.sampled_from(['true', 'false']),
        date_time(),
    )

def _array_elem():
    return st.one_of(
        _scalar(),
        st.just(''),
    )

def _array_body(value_strategy):
    # produce array contents: elements separated by commas, optional trailing comma,
    # optional newlines/comments
    def build(items):
        pieces = []
        for i, it in enumerate(items):
            if i:
                pieces.append(',')
                if i % 3 == 0:
                    pieces.append('\n')
            pieces.append(it)
        if items and (len(items) % 2 == 0):
            pieces.append(',')
        return ''.join(pieces)

    elems = st.lists(
        st.one_of(
            _scalar(),
            value_strategy,
            st.just('# c\n'),
        ),
        max_size=4,
    )
    return elems.map(build)

def _value():
    return st.recursive(
        _scalar(),
        lambda children: st.one_of(
            st.builds(lambda b: '[' + b + ']', _array_body(children)),
            st.builds(lambda b: '[' + b + ']', _array_body(st.one_of(children, st.just('')))),
            st.builds(
                lambda items: '{' + ', '.join(items) + '}',
                st.lists(
                    st.builds(lambda k, v: k + ' = ' + v, key(), children),
                    max_size=3,
                ),
            ),
            st.builds(
                lambda items: '{' + ', '.join(items) + ',}',
                st.lists(
                    st.builds(lambda k, v: k + ' = ' + v, key(), children),
                    min_size=1, max_size=3,
                ),
            ),
            st.just('{}'),
            st.just('[]'),
        ),
        max_leaves=6,
    )

# ---------- expressions / documents ----------

def _comment():
    return st.lists(
        st.one_of(
            st.sampled_from(list('abc XYZ019_-!?')),
            st.sampled_from(['\x01', '\x7f', 'é', '中', '\t']),
        ),
        max_size=8,
    ).map(lambda cs: '#' + ''.join(cs))

def _key_value():
    return st.builds(
        lambda k, v, c: k + ' = ' + v + c,
        key(),
        _value(),
        st.one_of(st.just(''), _comment()),
    )

def _standard_table():
    return st.builds(
        lambda k, c: '[' + k + ']' + c,
        key(),
        st.one_of(st.just(''), _comment()),
    )

def _array_table():
    return st.builds(
        lambda k, c: '[[' + k + ']]' + c,
        key(),
        st.one_of(st.just(''), _comment()),
    )

def _expression():
    return st.one_of(
        _key_value(),
        _standard_table(),
        _array_table(),
        _comment(),
        st.just(''),
    )

def _deep_array():
    # deep nesting band 1500-2048
    def build(n):
        return '[' * n + ']' * n
    return st.integers(min_value=1500, max_value=2048).map(build)

def _deep_inline():
    def build(n):
        s = 'x'
        for _ in range(n):
            s = '{a = ' + s + '}'
        return s
    return st.integers(min_value=100, max_value=400).map(build)

def _malformed():
    return st.one_of(
        st.just('a = "unterminated'),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        st.just("a = '''unterminated"),
        st.just('a = [1, 2'),
        st.just('a = {b = 1'),
        st.just('a = ]'),
        st.just('a = }'),
        st.just('[t'),
        st.just('[[t]'),
        st.just('a = '),
        st.just('= 1'),
        st.just('a = = 1'),
        st.just('a = {b = 1\n}'),
        st.just('a = "\\q"'),
        st.just('a = 1\nb = 2\na = 3'),
        st.just('[t]\n[t]'),
        st.just('a = "x\ny"'),
        st.just('a = 1 b = 2'),
        st.just('a = [1, 2]]'),
        st.just('a = {{}}'),
        st.just('a = {b = 1,, c = 2}'),
        st.just('a.b = 1\na = 2'),
        st.just('a = [\n1,\n2,\n'),
        st.just('a = 1\n\n\n[t]\n'),
        st.just('a = 1\r\nb = 2\r\n'),
        st.just('a = 1\r\n\r\n[t]\r\n'),
        st.just('a = {b = [1, {c = 2}]}'),
        st.just('a = 1\n[t]\nb = 2\n[t.u]\nc = 3'),
        st.just('a = "\\u0000"'),
        st.just('a = "\x01\x02"'),
        st.just('# comment with \x01 control'),
        st.just('a = 007'),
        st.just('a = 1.'),
        st.just('a = .5'),
        st.just('a = {b = 1,}'),
        st.just('a = 1979-02-30'),
        st.just('\ufeffa = 1'),
        st.just('a = 1\n\ufeffb = 2'),
        st.just('a = 1\n'),
        st.just(''),
        st.just('\n'),
        st.just('# only a comment'),
        st.just('# only a comment\n'),
        st.just('[t]\n'),
        st.just('[[a]]\n[[a]]\n'),
        st.just('"" = 1'),
        st.just("'key with space' = 1"),
        st.just('a = 1e309'),
        st.just('a = -1e309'),
        st.just('a = 9223372036854775808'),
        st.just('a = 1_000_000'),
        st.just('a = 0x_1'),
        st.just('a = 0b1_'),
        st.just('a = 1__2'),
        st.just('a = [\n # c\n 1,\n # c\n 2,\n]'),
        st.just('a = {b = 1, c = 2,}'),
        st.just('a = {b = 1\nc = 2}'),
        st.just('a = [1 2]'),
        st.just('a = [1,,2]'),
        st.just('a = 1 = 2'),
        st.just('a = "x" "y"'),
        st.just('a = true false'),
        st.just('a = 1\nb = "unterminated'),
        st.just('a = "\\u12"'),
        st.just('a = "\\U0000"'),
        st.just('a = "\\U00110000"'),
        st.just('a = 0x'),
        st.just('a = 0o'),
        st.just('a = 0b'),
        st.just('a = 1e'),
        st.just('a = 1e+'),
        st.just('a = 1.2.3'),
        st.just('a = +-1'),
        st.just('a = "\\"'),
        st.just("a = '\\'"),
        st.just('a = """\\\n"""'),
        st.just('a = """\\\r\n"""'),
        st.just('a = """\n"""'),
        st.just('a = [\n]'),
        st.just('a = [ ]'),
        st.just('a = [\n\n]'),
        st.just('a = [\n# c\n]'),
        st.just('a = [\n# c\n1\n]'),
        st.just('a = [\n# c\n1,\n# c\n]'),
    )

def _document():
    exprs = st.lists(_expression(), min_size=0, max_size=8)
    def build(es):
        # avoid NUL
        return '\n'.join(es)
    return exprs.map(build)

def _big_doc():
    return st.builds(
        lambda head, body, tail: head + '\n' + body + '\n' + tail,
        _expression(),
        _document(),
        _expression(),
    )

strategy = st.one_of(
    _document(),
    _big_doc(),
    _malformed(),
    _deep_array(),
    _deep_inline(),
    st.builds(lambda kv: kv, _key_value()),
    st.builds(lambda e: e, _expression()),
    st.builds(lambda v: 'a = ' + v, _value()),
    st.builds(lambda v: 'a = ' + v + '\n', _value()),
    st.builds(lambda v: 'a = ' + v + '\r\n', _value()),
    st.builds(lambda k: k + ' = 1', key()),
    st.builds(lambda s: 'a = ' + s, any_string()),
    st.builds(lambda n: 'a = ' + n, integer()),
    st.builds(lambda f: 'a = ' + f, floating_point()),
    st.builds(lambda d: 'a = ' + d, date_time()),
)