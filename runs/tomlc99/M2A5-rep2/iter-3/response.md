```python
from hypothesis import strategies as st
import json

# Helper pieces
_no_nul_char = st.characters(blacklist_characters="\x00", min_codepoint=1, max_codepoint=0x10FFFF)
_no_newline_no_nul = st.characters(blacklist_characters='"\n\r\x00', min_codepoint=1, max_codepoint=0x10FFFF)
_simple_text = st.text(alphabet=_no_newline_no_nul, min_size=0, max_size=50)
_short_text = st.text(alphabet=_no_nul_char, min_size=0, max_size=30)
_small_ident = st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), blacklist_characters='\x00', min_codepoint=48),
                       min_size=1, max_size=20)

# Escape sequence choices (including some invalid ones for near-malformed inputs)
_escape_seqs = st.sampled_from([
    r'\n', r'\t', r'\r', r'\\', r'\"', r"\'", r'\b', r'\f',
    r'\u0001', r'\u00A9', r'\U0001F600', r'\q'  # invalid escape to probe parser
])

# Basic string content pieces: mixes raw characters (excluding newline) and explicit escapes
_basic_piece = st.one_of(_simple_text, _escape_seqs)
_basic_content = st.lists(_basic_piece, min_size=0, max_size=6).map(''.join)

# Literal string content (single-quoted): may include quotes but not newlines in single-line literal
_literal_piece = st.one_of(st.text(alphabet=st.characters(blacklist_characters="'\n\r\x00"), min_size=1, max_size=12))
_literal_content = st.lists(_literal_piece, min_size=0, max_size=6).map(''.join)

# Multiline content (allow newlines and control bytes except real NUL)
_ml_piece = st.one_of(st.text(alphabet=st.characters(blacklist_characters='\x00', min_codepoint=1, max_codepoint=0x10FFFF),
                              min_size=1, max_size=40), _escape_seqs)
_ml_content = st.lists(_ml_piece, min_size=0, max_size=10).map(''.join)

# String strategies for all four quoting forms, including unterminated and malformed variants
basic_string = st.one_of(
    # well-formed
    _basic_content.map(lambda s: '"' + s + '"'),
    # unterminated (missing closing quote)
    _basic_content.map(lambda s: '"' + s),
    # with an invalid escape explicitly present (to hit parser error paths)
    (_basic_content.flatmap(lambda s: st.just(s + r'\q'))).map(lambda s: '"' + s + '"'),
)

literal_string = st.one_of(
    _literal_content.map(lambda s: "'" + s + "'"),
    # unterminated literal
    _literal_content.map(lambda s: "'" + s),
    # empty quoted key variant (legal)
    st.just("''")
)

ml_basic_string = st.one_of(
    _ml_content.map(lambda s: '"""' + s + '"""'),
    # unterminated multiline
    _ml_content.map(lambda s: '"""' + s),
)

ml_literal_string = st.one_of(
    _ml_content.map(lambda s: "'''" + s + "'''"),
    _ml_content.map(lambda s: "'''" + s),
)

string_value = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Integer formatting helpers
def _insert_underscores(s):
    # randomly insert underscores between digits
    import random
    if len(s) <= 1:
        return s
    parts = []
    for ch in s:
        parts.append(ch)
        if random.random() < 0.15:
            parts.append('_')
    res = ''.join(parts).strip('_')
    if res == '':
        return '0'
    return res

def _format_dec_int(n):
    s = str(abs(n))
    s = _insert_underscores(s)
    sign = '-' if n < 0 else ('+' if n > 0 and (n % 7 == 0) else '')
    # allow leading zeros sometimes
    if (n % 5 == 0):
        s = ('0' * (n % 3 + 1)) + s
    return sign + s

dec_int = st.integers(min_value=-10**30, max_value=10**30).map(_format_dec_int)

hex_int = st.builds(lambda s: '0x' + s,
                    st.text(alphabet='0123456789abcdefABCDEF', min_size=1, max_size=30)
                    .map(lambda s: _insert_underscores(s)))

oct_int = st.builds(lambda s: '0o' + s,
                    st.text(alphabet='01234567', min_size=1, max_size=30)
                    .map(lambda s: _insert_underscores(s)))

bin_int = st.builds(lambda s: '0b' + s,
                    st.text(alphabet='01', min_size=1, max_size=80)
                    .map(lambda s: _insert_underscores(s)))

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int)

# Floating point forms, including inf/nan and weird forms like '1.' and '.5'
def _make_float_string(mantissa, frac, exp):
    s = ''
    if mantissa is None:
        s += ''
    else:
        s += mantissa
    if frac is not None:
        s += '.' + frac
    elif mantissa is not None and (mantissa.endswith('.') or mantissa == ''):
        s += '.'
    if exp is not None:
        s += 'e' + exp
    return s

float_mant = st.text(alphabet='0123456789', min_size=0, max_size=20).map(lambda s: _insert_underscores(s) if s != '' else s)
float_frac = st.text(alphabet='0123456789', min_size=0, max_size=20).map(lambda s: _insert_underscores(s) if s != '' else s)
float_exp = st.one_of(
    st.text(alphabet='0123456789+-', min_size=1, max_size=6),
    st.just('309'), st.just('4000')  # extreme exponents
)

float_regular = st.builds(lambda m, f, e: _make_float_string(m, f if f != '' else None, e if e != '' else None),
                          float_mant, float_frac, float_exp)

float_inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])

float_value = st.one_of(float_regular, float_inf_nan)

# Boolean
bool_value = st.sampled_from(['true', 'false'])

# Date/time forms: produce many variants including invalid calendar dates
def _pad(n, width=2):
    return str(n).zfill(width)

year = st.integers(min_value=0, max_value=9999).map(lambda x: _pad(x, 4))
month = st.integers(min_value=0, max_value=99).map(lambda x: _pad(x, 2))
day = st.integers(min_value=0, max_value=99).map(lambda x: _pad(x, 2))
hour = st.integers(min_value=0, max_value=23).map(lambda x: _pad(x, 2))
minute = st.integers(min_value=0, max_value=59).map(lambda x: _pad(x, 2))
second = st.integers(min_value=0, max_value=59).map(lambda x: _pad(x, 2))
secfrac = st.one_of(st.just(''), st.text(alphabet='0123456789', min_size=1, max_size=6))

offset = st.one_of(st.just('Z'), st.builds(lambda s1, s2: ('+' if (int(s1) % 2 == 0) else '-') + s1 + ':' + s2, hour, minute))

local_date = st.builds(lambda y, m, d: f"{y}-{m}-{d}", year, month, day)
partial_time = st.builds(lambda h, m, s, f: f"{h}:{m}:{s}" + ('.' + f if f else ''), hour, minute, second, secfrac)
offset_date_time = st.builds(lambda ld, sep, pt, off: ld + sep + pt + off, local_date, st.sampled_from(['T', 't', ' ']), partial_time, offset)

date_value = st.one_of(offset_date_time, st.builds(lambda d, t: d + 'T' + t, local_date, partial_time),
                       local_date, partial_time)

# Base primitive values
primitive = st.deferred(lambda: st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_value
))

# Deep nesting helpers: create very deep arrays or inline tables (1500-2048) to stress recursion
def _deep_array_str(depth):
    inner = '[]'
    for _ in range(depth - 1):
        inner = '[' + inner + ']'
    return inner

deep_array = st.integers(min_value=1500, max_value=2048).map(_deep_array_str)

def _deep_inline_table_str(depth):
    inner = '{}'
    for _ in range(depth - 1):
        inner = '{' + inner + '}'
    return inner

deep_inline_table = st.integers(min_value=1500, max_value=2048).map(_deep_inline_table_str)

# Recursive construction for arrays and inline tables with reasonable depth in most cases
def _make_array(s):
    # s is a strategy producing a value string
    # create lists of values with comments/newlines optionally interleaved
    elems = st.lists(st.one_of(s, st.just('')), min_size=0, max_size=5)
    def pack(lst):
        # allow trailing comma, comments, newlines inserted
        parts = []
        for v in lst:
            if v == '':
                parts.append('#'+(' ' + 'comment' if True else ''))
            else:
                parts.append(v)
        joined = ', '.join(parts)
        if lst and (len(lst) % 3 == 0):
            joined = joined + ','
        return '[' + joined + ']'
    return elems.map(pack)

def _make_inline_table(s):
    # dictionary mapping keys to values; include trailing comma sometimes and allow empty inline table
    keys = st.text(alphabet=st.characters(blacklist_characters='\x00\n\r', min_codepoint=48), min_size=1, max_size=10)
    entries = st.dictionaries(keys, s, min_size=0, max_size=5)
    def pack(d):
        if not d:
            return '{}'
        parts = []
        for k, v in d.items():
            # choose quoted or unquoted key sometimes
            kstr = k
            if any(c for c in k if ord(c) > 127):
                # ensure quoted key when non-ascii appears (bare keys reject non-ASCII)
                kstr = '"' + k.replace('"', '\\"') + '"'
            parts.append(f"{kstr} = {v}")
        joined = ', '.join(parts)
        if len(parts) % 2 == 0:
            joined = joined + ','
        # note: newline inside inline table is invalid per parser; we respect that but will sometimes generate malformed by inserting newline
        if len(parts) > 0 and len(parts) % 4 == 0:
            # insert a newline as a near-malformed case occasionally
            joined = joined.replace(', ', ',\n', 1)
        return '{' + joined + '}'
    return entries.map(pack)

# Now the recursive value strategy: include deep special-case strategies
value = st.recursive(
    primitive,
    lambda s: st.one_of(_make_array(s), _make_inline_table(s)),
    max_leaves=50
)

value = st.one_of(value, deep_array, deep_inline_table)

# Key strategies
unquoted_key = st.text(alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd'), blacklist_characters='\x00', min_codepoint=48),
                       min_size=1, max_size=10000)  # include very long keys
quoted_key = st.one_of(
    _simple_text.map(lambda s: '"' + s + '"'),
    _literal_content.map(lambda s: "'" + s + "'"),
    st.just('""')  # empty quoted key
)
simple_key = st.one_of(unquoted_key, quoted_key)

dotted_key = st.lists(simple_key, min_size=2, max_size=5).map(lambda parts: '.'.join(parts))

key = st.one_of(simple_key, dotted_key)

# Comments and newlines
comment = st.one_of(st.just(''), st.builds(lambda t: '# ' + t, _short_text))
newline = st.sampled_from(['\n', '\r\n'])
maybe_nl = st.one_of(st.just(''), newline)

# Key-value pair lines
@st.composite
def key_value_line(draw):
    k = draw(key)
    # sometimes produce malformed equal signs or doubled equals
    eq = draw(st.one_of(st.just(' = '), st.just('='), st.just(' == '), st.just(' =')))
    v = draw(value)
    # sometimes put value on next line (parser rejects) to exercise near-malformed
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=10)) == 0:
        # value on next line
        return k + eq + '\n' + v
    return k + eq + v

# Table header generation (including malformed variants)
@st.composite
def table_header(draw):
    k = draw(key)
    variant = draw(st.integers(min_value=0, max_value=4))
    if variant == 0:
        return '[' + k + ']'
    elif variant == 1:
        # array table
        return '[[' + k + ']]'
    elif variant == 2:
        # missing closing bracket
        return '[' + k
    else:
        # doubled delimiter or extra bracket
        return '[[[' + k + ']]]'  # near-malformed

# Build top-level expressions: key/value lines, table headers, or comment-only
expression = st.one_of(
    key_value_line(),
    table_header(),
    comment
)

# Build complete document: sequence of expressions separated by newlines. Ensure at least one expression.
@st.composite
def document(draw):
    # number of expressions (allow empty documents and comment-only)
    n = draw(st.integers(min_value=0, max_value=12))
    parts = []
    # sometimes include arrays-of-tables blocks and inline nested sections
    for i in range(n):
        expr = draw(expression)
        parts.append(expr)
        # random comment appended on same line sometimes
        if draw(st.booleans()):
            c = draw(comment)
            if c:
                parts[-1] = parts[-1] + ' ' + c
        # append newline occasionally (documents with no trailing newline are valid)
        if draw(st.booleans()):
            parts.append(draw(maybe_nl))
    # ensure at least one complete key/value or table for a "complete" document
    if not parts:
        # generate minimal valid document: a = 1
        parts = ['a = 1']
    doc = ''.join(parts)
    # occasionally append stray tokens to create near-malformed inputs
    if draw(st.integers(min_value=0, max_value=20)) == 0:
        doc = doc + '\n' + ']'  # stray token
    # sometimes include trailing comment-only doc or huge key
    if draw(st.integers(min_value=0, max_value=50)) == 0:
        huge_key = draw(st.text(alphabet=st.characters(blacklist_characters='\x00', min_codepoint=48), min_size=1000, max_size=10000))
        doc = huge_key + ' = ' + draw(value) + '\n' + doc
    return doc

# Final exported strategy: choose among document, occasionally produce just deep structures or single value lines
strategy = st.one_of(
    document(),
    deep_array,
    deep_inline_table,
    st.builds(lambda kv: kv + '\n', key_value_line()),  # single key-value line with newline
    st.builds(lambda t: t + '\n', table_header()),      # single table header
)
```