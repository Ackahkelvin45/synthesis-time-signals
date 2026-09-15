from hypothesis import strategies as st
import json

# Helper character pools (exclude NUL '\x00')
_DIGITS = "0123456789"
_HEX = "0123456789abcdefABCDEF"
_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_UNDERSCORE_DASH = "_-"
_BARE_KEY_CHARS = _ALPHA + _DIGITS + _UNDERSCORE_DASH
_PRINTABLE_NO_QUOTE = ''.join(
    c for c in (chr(i) for i in range(32, 127))
    if c not in ('"', '\\')
)
# allow many Unicode letters for quoted strings (including non-ASCII)
_EXTRA_UNICODE = ''.join(chr(i) for i in range(0x00A0, 0x017F) if chr(i) not in ('"', "'", "\\"))
# control chars allowed inside basic strings (raw, except NUL and newline/CR)
_CONTROL_CHARS = ''.join(chr(i) for i in range(1, 32) if i not in (0, 10, 13))

# Basic small utilities
def _join(parts):
    return ''.join(parts)

# Key strategies
unquoted_key = st.text(alphabet=st.sampled_from(list(_BARE_KEY_CHARS)), min_size=1, max_size=20)
# allow long keys (10k character edge case)
long_key = st.text(alphabet=st.sampled_from(list(_BARE_KEY_CHARS)), min_size=1000, max_size=10000)
quoted_basic_key = st.one_of(
    st.just('""'),  # empty quoted key
    st.text(alphabet=st.sampled_from(list(_PRINTABLE_NO_QUOTE + _EXTRA_UNICODE + _CONTROL_CHARS))),
).map(lambda s: '"' + s.replace('"', '\\"') + '"')
quoted_literal_key = st.text(alphabet=st.sampled_from(list((_PRINTABLE_NO_QUOTE + _EXTRA_UNICODE + _CONTROL_CHARS).replace("'", "")))), 

# String generators
# Escape sequence choices for inclusion in Basic Strings
simple_escapes = st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\"', '\\\\', '\\/'])
unicode_4 = st.lists(st.sampled_from(list("0123456789abcdefABCDEF")), min_size=4, max_size=4).map(''.join).map(lambda h: '\\u' + h)
unicode_8 = st.lists(st.sampled_from(list("0123456789abcdefABCDEF")), min_size=8, max_size=8).map(''.join).map(lambda h: '\\U' + h)
escape_fragment = st.one_of(simple_escapes, unicode_4, unicode_8)

# content pieces: printable chars, unicode, control, or escape sequences
basic_char = st.one_of(
    st.sampled_from(list(_PRINTABLE_NO_QUOTE)),
    st.sampled_from(list(_EXTRA_UNICODE)),
    st.sampled_from(list(_CONTROL_CHARS)),
    escape_fragment,
)

# Build basic string with possible untermination
basic_string = st.lists(basic_char, min_size=0, max_size=60).map(''.join).map(lambda s: '"' + s + '"')
unterminated_basic_string = st.lists(basic_char, min_size=1, max_size=60).map(''.join).map(lambda s: '"' + s)  # missing closing quote

# Literal strings (single quoted) - allow raw characters except single-quote and newline
literal_char = st.one_of(
    st.sampled_from([c for c in (_PRINTABLE_NO_QUOTE + _EXTRA_UNICODE + _CONTROL_CHARS) if c != "'"]),
)
literal_string = st.lists(literal_char, min_size=0, max_size=60).map(''.join).map(lambda s: "'" + s + "'")
unterminated_literal_string = st.lists(literal_char, min_size=1, max_size=60).map(''.join).map(lambda s: "'" + s)

# Multiline basic string (triple quotes) - include CRLF/newlines and escapes
ml_basic_content = st.lists(st.one_of(
    basic_char,
    st.just('\n'),
    st.just('\r'),
    st.sampled_from(list(_PRINTABLE_NO_QUOTE + _EXTRA_UNICODE))
), min_size=0, max_size=200).map(''.join)
ml_basic_string = ml_basic_content.map(lambda s: '"""' + s + '"""')
unterminated_ml_basic_string = ml_basic_content.map(lambda s: '"""' + s)  # unterminated

# Multiline literal (triple single quotes)
ml_literal_content = st.lists(st.one_of(
    literal_char,
    st.just('\n'),
    st.just('\r'),
), min_size=0, max_size=200).map(''.join)
ml_literal_string = ml_literal_content.map(lambda s: "'''" + s + "'''")
unterminated_ml_literal_string = ml_literal_content.map(lambda s: "'''" + s)

# Integer generators
# Decimal with optional underscores and leading zeros allowed
def _decimal_str(min_digits=1, max_digits=50):
    return st.integers(min_value=min_digits, max_value=max_digits).flatmap(
        lambda n: st.lists(st.sampled_from(list(_DIGITS)), min_size=n, max_size=n).map(''.join)
    )

dec_int = st.one_of(
    st.builds(lambda sgn, dig: (sgn if sgn else '') + dig,
              st.sampled_from(['', '+', '-']), _decimal_str(1, 100)),
    # groups with underscores inserted
    st.builds(
        lambda sgn, parts: (sgn if sgn else '') + '_'.join(parts),
        st.sampled_from(['', '+', '-']),
        st.lists(st.text(alphabet=st.sampled_from(list(_DIGITS)), min_size=1, max_size=6), min_size=1, max_size=10)
    )
)

hex_int = st.builds(lambda sgn, h: (sgn if sgn else '') + '0x' + h,
                    st.sampled_from(['', '+', '-']), st.lists(st.sampled_from(list("0123456789abcdefABCDEF")), min_size=1, max_size=40).map(''.join))
oct_int = st.builds(lambda sgn, h: (sgn if sgn else '') + '0o' + h,
                    st.sampled_from(['', '+', '-']), st.lists(st.sampled_from(list("01234567")), min_size=1, max_size=40).map(''.join))
bin_int = st.builds(lambda sgn, h: (sgn if sgn else '') + '0b' + h,
                    st.sampled_from(['', '+', '-']), st.lists(st.sampled_from(list("01")), min_size=1, max_size=64).map(''.join))

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int)

# Floating point generators incl. inf and nan
float_normal = st.one_of(
    # forms: 1. , .5 , 1.23, 1e10, 1.23e-10
    st.builds(lambda a, b: a + '.' + b, st.text(alphabet=st.sampled_from(list(_DIGITS)), min_size=1, max_size=20), st.text(alphabet=st.sampled_from(list(_DIGITS)), min_size=0, max_size=20)),
    st.builds(lambda a, exp: a + exp, st.one_of(
        st.text(alphabet=st.sampled_from(list(_DIGITS)), min_size=1, max_size=20),
        st.just('.' + st.text(alphabet=st.sampled_from(list(_DIGITS)), min_size=1, max_size=20))  # .5 like
    ), st.one_of(
        st.builds(lambda sgn, e: 'e' + (sgn if sgn else '') + e, st.sampled_from(['', '+', '-']), st.text(alphabet=st.sampled_from(list(_DIGITS)), min_size=1, max_size=5)),
        st.just('')
    )),
    # explicit forms using underscores
    st.builds(lambda s: s, st.text(alphabet=st.sampled_from(list(_DIGITS + '_')), min_size=1, max_size=20)).map(lambda s: s if '.' in s or 'e' in s or 'E' in s else s + '.0')
)
inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])

float_value = st.one_of(float_normal, inf_nan)

# Boolean
bool_value = st.sampled_from(['true', 'false'])

# Date/time forms (strings but lexical tokens)
def _padded(num, width):
    return str(num).zfill(width)

year = st.integers(min_value=0, max_value=9999).map(lambda n: _padded(n, 4))
month = st.integers(min_value=0, max_value=99).map(lambda n: _padded(n, 2))
day = st.integers(min_value=0, max_value=99).map(lambda n: _padded(n, 2))
hour = st.integers(min_value=0, max_value=99).map(lambda n: _padded(n, 2))
minute = st.integers(min_value=0, max_value=99).map(lambda n: _padded(n, 2))
second = st.integers(min_value=0, max_value=99).map(lambda n: _padded(n, 2))
secfrac = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(alphabet=st.sampled_from(list(_DIGITS)), min_size=1, max_size=6)))
offset = st.one_of(
    st.just('Z'),
    st.builds(lambda sgn, h, m: (sgn if sgn else '+') + h + ':' + m, st.sampled_from(['', '+', '-']), hour, minute)
)

offset_date_time = st.builds(
    lambda Y, M, D, delim, h, mi, s, frac, off: Y + '-' + M + '-' + D + delim + h + ':' + mi + ':' + s + (frac or '') + (off or ''),
    year, month, day, st.sampled_from(['T', 't', ' ']), hour, minute, second, secfrac, offset
)
local_date_time = st.builds(lambda Y, M, D, delim, h, mi, s, frac: Y + '-' + M + '-' + D + delim + h + ':' + mi + ':' + s + (frac or ''), year, month, day, st.sampled_from(['T', 't', ' ']), hour, minute, second, secfrac)
local_date = st.builds(lambda Y, M, D: Y + '-' + M + '-' + D, year, month, day)
local_time = st.builds(lambda h, mi, s, frac: h + ':' + mi + ':' + s + (frac or ''), hour, minute, second, secfrac)

date_time_value = st.one_of(offset_date_time, local_date_time, local_date, local_time)

# Base (non-recursive) value strategy - includes malformed variants too
base_value = st.one_of(
    basic_string,
    unterminated_basic_string,
    literal_string,
    unterminated_literal_string,
    ml_basic_string,
    unterminated_ml_basic_string,
    ml_literal_string,
    unterminated_ml_literal_string,
    integer_value,
    float_value,
    bool_value,
    date_time_value
)

# Recursive construction for arrays and inline tables
def _array_of(inner):
    # array elements may be separated by whitespace/comments/newlines; we simply insert spaces/comments randomly
    elems = st.lists(inner, min_size=0, max_size=6)
    def mk_array(vs):
        # insert some comments/newlines randomly into the array text
        pieces = []
        for i, v in enumerate(vs):
            if i:
                pieces.append(', ')
            pieces.append(v)
        # allow trailing comma
        if st.randoms().example().randint(0, 3) == 0:
            pieces.append(',')
        return '[' + ''.join(pieces) + ']'
    return elems.map(lambda vs: '[' + ', '.join(vs) + (',' if len(vs) and st.randoms().example().randint(0, 4) == 0 else '') + ']')

def _inline_table_of(inner):
    # generating inline tables: { key = value, ... } - usually no newlines
    def build_table(pairs):
        items = []
        for k, v in pairs:
            items.append(f"{k} = {v}")
        # allow trailing comma
        s = '{' + ', '.join(items)
        if st.randoms().example().randint(0, 4) == 0:
            s += ','
        s += '}'
        return s
    # keys can duplicate
    key_choice = st.one_of(unquoted_key, quoted_basic_key, literal_string)
    pairs = st.lists(st.tuples(key_choice, inner), min_size=0, max_size=6)
    # Occasionally inject a newline inside (parser rejects this)
    return pairs.map(build_table)

# Use st.recursive to enable nested arrays and inline tables
# The extend function receives the strategy for smaller values and must construct arrays/inline tables around it
value = st.recursive(
    base_value,
    lambda inner: st.one_of(
        st.lists(inner, min_size=0, max_size=6).map(lambda vs: '[' + ', '.join(vs) + (',' if len(vs) and True else '') + ']'),
        st.lists(st.tuples(st.one_of(unquoted_key, quoted_basic_key, literal_string), inner), min_size=0, max_size=6)
          .map(lambda pairs: '{' + ', '.join(k + ' = ' + v for k, v in pairs) + (',' if pairs and True else '') + '}'),
    ),
    max_leaves=2048
)

# Key selection for key_value pairs
key_for_kv = st.one_of(unquoted_key, quoted_basic_key, literal_string, long_key)

# Key/value line generator
key_value_line = st.builds(lambda k, v: f"{k} = {v}", key_for_kv, value)

# Table header and array-table header
def dotted_key():
    # generate dotted key: simple_key (DOT simple_key)+
    part = st.one_of(unquoted_key, quoted_basic_key, literal_string)
    return st.lists(part, min_size=1, max_size=4).map(lambda parts: '.'.join(parts))

standard_table = dotted_key().map(lambda k: '[' + k + ']')
array_table = dotted_key().map(lambda k: '[[' + k + ']]')

# Section: either several key-values, or a table header followed by kvs
section = st.one_of(
    st.lists(key_value_line, min_size=1, max_size=6).map(lambda lines: '\n'.join(lines)),
    st.builds(lambda hdr, kvs: hdr + '\n' + '\n'.join(kvs),
              st.one_of(standard_table, array_table),
              st.lists(key_value_line, min_size=0, max_size=6))
)

# Document builder: sequences of sections, possibly with comments and blank lines
comment_or_blank = st.one_of(st.just(''), st.just('# a comment'), st.just('#\n'), st.just('\n'))
document_core = st.lists(st.one_of(section, comment_or_blank), min_size=0, max_size=8).map(lambda parts: '\n'.join([p for p in parts if p is not None and p != '']))

# To ensure we often produce a "complete document" include at least one key_value or table
document_with_required = st.one_of(
    document_core.filter(lambda s: s.strip() != ''),  # non-empty
    st.builds(lambda req, rest: req + '\n' + rest, st.one_of(section, key_value_line), document_core)
)

# Corruption mutations to produce near-valid-but-malformed inputs
def _mutate_document(s, choice):
    if choice == 'missing_bracket':
        # remove a single ']' or '}' if present
        if ']' in s:
            return s.replace(']', '', 1)
        if '}' in s:
            return s.replace('}', '', 1)
        return s[:-1] if s else s
    if choice == 'double_delim':
        # duplicate a bracket or equals sign
        if '=' in s:
            return s.replace('=', '==', 1)
        if '[' in s:
            return s.replace('[', '[[', 1)
        return s
    if choice == 'unterminated_string':
        # remove a trailing quote from the first quoted string
        idx = s.find('"')
        if idx >= 0:
            # remove a following quote
            j = s.find('"', idx + 1)
            if j >= 0:
                return s[:j] + s[j+1:]
        # fallback: chop last char
        return s[:-1] if s else s
    if choice == 'stray_token':
        return s + ' ~!'
    if choice == 'extra_bracket':
        return s + ']'
    return s

mutation_choice = st.one_of(st.just(None), st.sampled_from(['missing_bracket', 'double_delim', 'unterminated_string', 'stray_token', 'extra_bracket']))

# Final document strategy with occasional corruption
strategy = st.builds(
    lambda doc, mut: (_mutate_document(doc, mut) if mut else doc),
    document_with_required,
    mutation_choice
).map(lambda s: s)  # ensure type is str