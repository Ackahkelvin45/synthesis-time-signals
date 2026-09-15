from hypothesis import strategies as st
import json

# Helper alphabets (avoid NUL '\x00')
_ctrl = [chr(c) for c in range(1, 32) if c not in (10, 13)]
_ascii_print = [chr(c) for c in range(32, 127) if c != 34 and c != 92]  # exclude " and \
_nonascii_sample = [chr(c) for c in range(0x80, 0xA0)]  # some non-ASCII bytes (not NUL)

# Basic building blocks
def _with_prob(prob, strat):
    return st.one_of(st.just(None).filter(lambda _: False), strat) if prob <= 0 else st.one_of(strat, st.nothing()).map(lambda x: x)

# String value strategies
def _basic_string():
    # contents: either raw chars (no " or \ or newline), or escaped sequences inserted
    raw_chars = _ctrl + _ascii_print + _nonascii_sample
    raw = st.text(alphabet=raw_chars, min_size=0, max_size=80)
    # escaped chunks: include sequences like \n, \t, \uXXXX, \UXXXXXXXX, and random escaped quote/backslash
    def mk_escape():
        hex4 = ''.join(st.sampled_from('0123456789abcdefABCDEF').example() for _ in range(4))
        # note: .example() used only to build a constant pattern; avoid heavy generation in escape; instead build via strategies:
    esc_atom = st.one_of(
        st.just('\\n'),
        st.just('\\t'),
        st.just('\\r'),
        st.just('\\\\'),
        st.just('\\"'),
        st.builds(lambda h: '\\u' + h, st.text(alphabet='0123456789abcdefABCDEF', min_size=4, max_size=4)),
        st.builds(lambda H: '\\U' + H, st.text(alphabet='0123456789abcdefABCDEF', min_size=8, max_size=8)),
    )
    # build content as pieces combining raw substrings and escapes
    pieces = st.lists(st.one_of(st.text(alphabet=raw_chars, min_size=0, max_size=20), esc_atom), min_size=0, max_size=8).map(''.join)
    # also include raw control characters unescaped sometimes (allowed by parser)
    return st.one_of(
        pieces.map(lambda s: '"' + s + '"'),
        raw.map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"'),
    )

def _ml_basic_string():
    # Multiline basic string: triple double quotes. May contain newlines but must not contain the closing triple sequence
    all_chars = _ctrl + [chr(c) for c in range(32, 127) if c != 92] + _nonascii_sample + ['\n', '\r', '\t']
    content = st.text(alphabet=all_chars, min_size=0, max_size=200).map(lambda s: s.replace('"""', '""'))  # avoid accidental terminator
    return content.map(lambda s: '"""' + s + '"""')

def _literal_string():
    # single-quoted literal (no newline)
    allowed = [c for c in ([_ for _ in _ascii_print] + _nonascii_sample + _ctrl) if c != "'"]
    return st.text(alphabet=allowed, min_size=0, max_size=80).map(lambda s: "'" + s + "'")

def _ml_literal_string():
    # triple single quotes; may contain anything (including quotes), avoid terminator
    all_chars = _ctrl + [chr(c) for c in range(32, 127)] + _nonascii_sample + ['\n', '\r', '\t']
    content = st.text(alphabet=all_chars, min_size=0, max_size=400).map(lambda s: s.replace("'''", "''"))
    return content.map(lambda s: "'''" + s + "'''")

string_value = st.one_of(_basic_string(), _ml_basic_string(), _literal_string(), _ml_literal_string())

# Integer strategies (decimal, hex, oct, bin) with underscores and leading zeros sometimes
def _int_with_underscores(sgn, digits):
    # insert underscores randomly between digits
    def ins_underscores(d):
        if len(d) <= 1:
            return d
        parts = []
        i = 0
        while i < len(d):
            take = 1
            parts.append(d[i:i+take])
            if i + take < len(d) and st.booleans().example():
                parts.append('_')
            i += take
        return ''.join(parts).strip('_')
    return st.integers(min_value=0, max_value=10**40).map(lambda n: sgn + ins_underscores(format(n, digits)))

dec_int = st.one_of(
    # plain decimal, sometimes with sign, sometimes with leading zeros
    st.integers(min_value=-10**60, max_value=10**60).map(lambda n: str(n)),
    st.integers(min_value=0, max_value=10**60).map(lambda n: ('%03d' % n) if st.booleans().example() and n < 1000 else str(n)),  # leading zeros option
).map(lambda s: s.replace('+', ''))  # ensure no stray plus from formatting

hex_int = st.integers(min_value=0, max_value=2**256).map(lambda n: hex(n).replace('0x', '0x') )
oct_int = st.integers(min_value=0, max_value=2**256).map(lambda n: oct(n).replace('0o', '0o') )
bin_int = st.integers(min_value=0, max_value=2**256).map(lambda n: bin(n).replace('0b', '0b') )

# Add underscore variations to hex/oct/bin
hex_int = st.one_of(hex_int, hex_int.map(lambda s: s.replace('a', 'a_').replace('A', 'A_') if len(s) > 3 else s))
oct_int = st.one_of(oct_int, oct_int.map(lambda s: s.replace('o', 'o_') if len(s) > 3 else s))
bin_int = st.one_of(bin_int, bin_int.map(lambda s: s.replace('b', 'b_') if len(s) > 3 else s))

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int)

# Floats: include 1., .5, exponents, inf, nan, huge exponents
float_plain = st.floats(width=32, allow_infinity=False, allow_nan=False).map(lambda f: repr(f))
float_edge = st.one_of(
    st.builds(lambda s: s, st.text(alphabet='0123456789', min_size=1, max_size=6)).map(lambda s: s + '.'),
    st.builds(lambda s: s, st.text(alphabet='0123456789', min_size=1, max_size=6)).map(lambda s: '.' + s),
    st.builds(lambda s,e: s + 'e' + e, st.text(alphabet='0123456789', min_size=1, max_size=6), st.one_of(st.just('+1'), st.just('-1'), st.just('999'), st.just('-999'))),
    st.just('inf'),
    st.just('-inf'),
    st.just('nan'),
    st.just('+nan'),
)
float_value = st.one_of(float_plain, float_edge)

bool_value = st.sampled_from(['true', 'false'])

# Date/time forms (not validating calendar correctness)
def _digits(n):
    return st.text(alphabet='0123456789', min_size=n, max_size=n)

year = _digits(4)
month = _digits(2)
day = _digits(2)
hour = _digits(2)
minute = _digits(2)
second = _digits(2)
secfrac = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(alphabet='0123456789', min_size=1, max_size=9)))
offset = st.one_of(st.just('Z'), st.builds(lambda s, t: ('+' if st.booleans().example() else '-') + s + ':' + t, hour, minute))

offset_dt = st.builds(lambda Y,M,D,sep,h,m,s,sf,off: ''.join([Y,'-',M,'-',D, sep, h,':',m,':',s, sf, off]),
                      year, month, day, st.sampled_from(['T','t',' ']), hour, minute, second, secfrac, offset)

local_dt = st.builds(lambda Y,M,D,sep,h,m,s,sf: ''.join([Y,'-',M,'-',D, sep, h+':'+m+':'+s+sf]),
                     year, month, day, st.sampled_from(['T','t',' ']), hour, minute, second, secfrac)

local_date = st.builds(lambda Y,M,D: Y+'-'+M+'-'+D, year, month, day)
local_time = st.builds(lambda h,m,sf: h+':'+m+':'+s+sf, hour, minute, secfrac)

datetime_value = st.one_of(offset_dt, local_dt, local_date, local_time)

# Base value strategy (non-recursive)
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    datetime_value,
    st.just('[]'),  # empty array
    st.just('{}'),  # empty inline table
)

# Recursive constructions for arrays and inline tables. Use deferred to refer to 'value' inside definitions.
def _array_of(inner):
    # arrays may be multi-line and may include comments/newlines; include optional trailing comma
    elements = st.lists(inner, min_size=0, max_size=6)
    def make(arr):
        # assemble with commas, sometimes include trailing comma, sometimes extra commas or missing
        if not arr:
            return '[]'
        pieces = []
        for v in arr:
            pieces.append(v)
        s = '[' + ', '.join(pieces)
        if st.booleans().example() and not s.endswith(','):
            s = s + ','
        s = s + ']'
        # occasionally produce a near-malformed variant: doubled comma or missing bracket
        if st.booleans().example():
            if st.booleans().example():
                s = s.replace(',', ',,', 1)
            else:
                s = s.rstrip(']')
        return s
    return elements.map(make)

def _inline_table_of(inner):
    # inline tables cannot contain newlines; produce key = value pairs; allow trailing comma
    def kv_pair():
        # key can be unquoted or quoted
        unquoted = st.text(alphabet=[c for c in _ascii_print if c.isalnum() or c in ('-','_')], min_size=1, max_size=10)
        quoted = st.one_of(_basic_string().map(lambda s: s), _literal_string().map(lambda s: s))
        key = st.one_of(unquoted, quoted)
        return st.tuples(key, inner).map(lambda kv: kv[0] + ' = ' + kv[1])
    pairs = st.lists(kv_pair(), min_size=0, max_size=6)
    def make(pairs_list):
        if not pairs_list:
            return '{}'
        body = ', '.join(pairs_list)
        if st.booleans().example():
            body = body + ','  # trailing comma accepted by parser
        # occasionally inject a newline (which the parser rejects for inline tables) to produce near-malformed inputs
        if st.booleans().example():
            body = body.replace(', ', ',\n', 1)
        return '{' + body + '}'
    return pairs.map(make)

# Deep nesting generator for arrays and inline tables (explicit nesting to reach high recursion depths)
def _deep_nesting():
    # choose bracket type randomly
    def build_depth(n, kind, inner_val):
        if n <= 0:
            return inner_val
        if kind == 'array':
            return '[' + build_depth(n-1, kind, inner_val) + ']'
        else:
            # inline table nesting: {k = <inner>}
            return '{k = ' + build_depth(n-1, kind, inner_val) + '}'
    # we include depths up to 2048, but bias towards smaller depths
    depth = st.integers(min_value=0, max_value=2048)
    kind = st.sampled_from(['array', 'inline'])
    base_inner = st.sampled_from(['1', '"x"', 'true', '{}'])
    return st.tuples(depth, kind, base_inner).map(lambda t: build_depth(t[0], t[1], t[2]))

# The recursive value strategy
def _extend(inner):
    return st.one_of(
        _array_of(inner),
        _inline_table_of(inner),
        _deep_nesting(),
    )

value = st.recursive(base_value, _extend, max_leaves=100)

# Key strategies: unquoted, quoted, dotted (dotted keys)
def _unquoted_key():
    alphabet = [c for c in _ascii_print if c.isalnum() or c in ('-','_')]
    return st.text(alphabet=alphabet, min_size=1, max_size=20)

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_unquoted_key(), _quoted_key())

def _dotted_key():
    # one to four simple_key parts
    parts = st.lists(_simple_key(), min_size=1, max_size=4)
    return parts.map(lambda ps: '.'.join(ps))

key = st.one_of(_simple_key(), _dotted_key())

# Key/value line (may be malformed sometimes: missing or doubled '=')
def _key_value_line():
    def build(kv):
        k, v = kv
        # sometimes omit equals, sometimes double it
        if st.booleans().example():
            eq = '='
        else:
            eq = st.one_of(st.just('=='), st.just('')).example()
        return (k + ' ' + eq + ' ' + v).strip()
    return st.tuples(key, value).map(build)

# Table and array-table lines
def _table_line():
    return key.map(lambda k: '[' + k + ']')

def _array_table_line():
    return key.map(lambda k: '[[' + k + ']]')

# Comment or blank line
comment = st.one_of(st.just(''), st.builds(lambda s: '# ' + s, st.text(alphabet=[c for c in _ascii_print if c != '\n'], min_size=0, max_size=60)))

# Expression: key_value, table, array_table, or comment line
expression = st.one_of(
    _key_value_line(),
    _table_line(),
    _array_table_line(),
    comment
)

# Document: sequence of expressions separated by newlines; allow documents with no trailing newline
def _document():
    lines = st.lists(expression, min_size=0, max_size=12)
    # optionally include stray tokens at the end to create near-malformed doc
    stray = st.one_of(st.just(''), st.just(']'), st.just('}'), st.just(','), st.just('unexpected'))
    def assemble(ls_s):
        ls, stray_tok = ls_s
        # filter out empty comment-only lines that are '', but keep them as blank lines
        text = '\n'.join(ls)
        if stray_tok and st.booleans().example():
            # append stray token on its own line
            text = (text + '\n' + stray_tok).strip()
        # sometimes produce no trailing newline
        if st.booleans().example():
            return text
        else:
            return text + '\n'
    return st.tuples(lines, stray).map(assemble)

# Top-level strategy exported
strategy = st.text()