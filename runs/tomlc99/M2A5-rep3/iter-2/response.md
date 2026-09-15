```python
from hypothesis import strategies as st
import json

# Helper character sets avoiding NUL (0x00) because the harness skips NUL-containing inputs.
_no_nul = ''.join([chr(c) for c in range(1, 0x110000) if c != 0 and c != 0xD800 and c != 0xDFFF])  # large; we'll restrict via ranges below

# Build restricted alphabets for different string contexts.
_basic_string_chars = st.characters(blacklist_characters='"\n\r\\\x00', min_codepoint=0x20, max_codepoint=0x10FFFF)
_literal_string_chars = st.characters(blacklist_characters="'\n\r\x00", min_codepoint=0x20, max_codepoint=0x10FFFF)
_ml_basic_chars = st.characters(blacklist_characters='\x00', min_codepoint=1, max_codepoint=0x10FFFF)  # allows newlines and control except NUL
_ml_literal_chars = st.characters(blacklist_characters='\x00', min_codepoint=1, max_codepoint=0x10FFFF)

# Small utility to insert underscores into digits
def with_underscores_digits(s):
    # randomly insert underscores between digits (not deterministic here; we'll drive via Hypothesis strategies)
    return s

# Escape fragments for basic strings
_basic_escapes = st.sampled_from(['\\n', '\\r', '\\t', '\\b', '\\f', '\\"', '\\\\', '\\/'])

# Unicode escapes
_unicode_4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda i: '\\u' + format(i, '04x'))
_unicode_8 = st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda i: '\\U' + format(i, '08x'))

# Raw control characters except NUL for inclusion inside strings (accepted by parser)
_control_char = st.sampled_from([chr(i) for i in range(1, 0x20) if i != 0])

# Basic string content: mix of safe raw chars, escapes, unicode escapes, and occasional control chars
_basic_piece = st.one_of(
    st.text(alphabet=_basic_string_chars, min_size=0, max_size=8),
    _basic_escapes,
    _unicode_4,
    _unicode_8,
    _control_char
)

basic_string = st.lists(_basic_piece, min_size=0, max_size=6).map(''.join).map(lambda s: f'"{s}"')

# Multiline basic string: triple quotes; include newlines, raw control chars (except NUL), escapes
_ml_basic_piece = st.one_of(
    st.text(alphabet=_ml_basic_chars, min_size=0, max_size=20),
    _basic_escapes,
    _unicode_4,
    _unicode_8
)
ml_basic_string = st.lists(_ml_basic_piece, min_size=0, max_size=6).map(''.join).map(lambda s: '"""' + s + '"""')

# Literal strings (single-quoted): raw content; no escapes. Exclude single-quote and newlines for single-line literal.
literal_string = st.text(alphabet=_literal_string_chars, min_size=0, max_size=12).map(lambda s: "'" + s + "'")
ml_literal_string = st.text(alphabet=_ml_literal_chars, min_size=0, max_size=60).map(lambda s: "'''" + s + "'''")

# Occasionally produce unterminated strings or invalid escapes to create near-valid-but-malformed inputs.
unterminated_basic = st.lists(_basic_piece, min_size=0, max_size=6).map(''.join).map(lambda s: '"' + s)  # missing closing quote
unterminated_ml_basic = st.lists(_ml_basic_piece, min_size=0, max_size=6).map(''.join).map(lambda s: '"""' + s)  # missing closing triple
invalid_escape_basic = st.lists(st.one_of(st.text(alphabet=_basic_string_chars, min_size=0, max_size=8), st.sampled_from(['\\q', '\\z'])), min_size=0, max_size=6).map(''.join').map(lambda s: '"' + s + '"')

# Strings strategy: include all four quoting forms and malformed variants
string_value = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    unterminated_basic,
    unterminated_ml_basic,
    # allow invalid single-character escape sequences occasionally
    st.builds(lambda s: s, invalid_escape_basic) if False else basic_string  # avoid repeated strategy duplicates (kept for clarity)
)

# Integers: decimal (with optional leading zeros), hex, octal, binary; include underscores and extremes.
def decimal_int_strs():
    # produce a variety of decimal forms, including leading zeros, underscores, sign.
    signs = st.sampled_from(['', '+', '-'])
    digits = st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=30)
    def insert_underscores(s):
        # insert underscores randomly between digits
        if len(s) < 2:
            return s
        parts = []
        for ch in s:
            parts.append(ch)
            # 30% chance to add underscore
            # We'll use Hypothesis to decide by splitting via integer; not possible here, so do simple heuristic
        return s  # keep simple; underscores will be added via explicit strategies below
    with_underscored = st.builds(lambda sg, d: sg + d.replace('', '_').strip('_'), signs, digits)
    # Simpler explicit forms:
    return st.one_of(
        st.builds(lambda sgn, d: sgn + d, signs, digits),
        st.builds(lambda sgn, d: sgn + d, signs, st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57 + 0), min_size=1, max_size=3)),  # small
        # leading zeros
        st.builds(lambda sgn, d: sgn + '0' + d, signs, digits),
        # underscores inserted using a controlled approach
        st.builds(lambda sgn, d: sgn + '_'.join([d[i:i+3] for i in range(0, len(d), 3)]), signs, digits),
        # extreme long integer
        st.builds(lambda sgn, n: sgn + ('9' * n), signs, st.integers(min_value=1, max_value=1000)),
    )

hex_int = st.builds(lambda sign, h: (sign or '') + '0x' + h, st.sampled_from(['', '+', '-']), st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57) | st.characters(min_codepoint=65, max_codepoint=70) | st.characters(min_codepoint=97, max_codepoint=102), min_size=1, max_size=20))
oct_int = st.builds(lambda sign, h: (sign or '') + '0o' + h, st.sampled_from(['', '+', '-']), st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=55), min_size=1, max_size=20))
bin_int = st.builds(lambda sign, h: (sign or '') + '0b' + h, st.sampled_from(['', '+', '-']), st.text(alphabet=st.characters(blacklist_characters='\x00', min_codepoint=48, max_codepoint=49), min_size=1, max_size=64))

# Combining decimal variations
decimal_int = st.one_of(*list(decimal_int_strs() for _ in range(1))).filter(lambda s: len(s) > 0)
integer_value = st.one_of(decimal_int, hex_int, oct_int, bin_int)

# Floating point values: include normal with frac/exponent, 1., .5, extremes, inf/nan with signs.
float_normal = st.one_of(
    st.builds(lambda sgn, a, b: (sgn or '') + a + '.' + b, st.sampled_from(['', '+', '-']), st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=0, max_size=5).filter(lambda s: s is not None), st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=6)),
    st.builds(lambda sgn, a: (sgn or '') + a + '.', st.sampled_from(['', '+', '-']), st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=6)),
    st.builds(lambda sgn, b: (sgn or '') + '.' + b, st.sampled_from(['', '+', '-']), st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=6)),
    st.builds(lambda sgn, mant, exp: (sgn or '') + mant + 'e' + exp, st.sampled_from(['', '+', '-']), st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57) | st.sampled_from(['.']), min_size=1, max_size=6), st.builds(lambda s, e: (('+' if s else '') + str(e)) if isinstance(e, int) else e, st.just(''), st.integers(min_value=-400, max_value=400)))
)
float_inf_nan = st.sampled_from(['inf', '-inf', '+inf', 'nan', '-nan', '+nan'])
float_value = st.one_of(float_normal, float_inf_nan)

# Booleans
bool_value = st.sampled_from(['true', 'false'])

# Date/time patterns: OFFSET_DATE_TIME, LOCAL_DATE_TIME, LOCAL_DATE, LOCAL_TIME (calendar-invalid allowed)
def two_digits(minv=0, maxv=99):
    return st.integers(min_value=minv, max_value=maxv).map(lambda i: f"{i:02d}")

year = st.integers(min_value=0, max_value=9999).map(lambda i: f"{i:04d}")
month = two_digits(1, 12)
day = two_digits(1, 31)  # allow 31 even if month invalid
hour = two_digits(0, 23)
minute = two_digits(0, 59)
second = two_digits(0, 59)
secfrac = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=9)))
offset = st.one_of(st.just('Z'), st.builds(lambda s1, s2, s3: s1 + s2 + ':' + s3, st.sampled_from(['+', '-']), hour, minute))

offset_date_time = st.builds(lambda y, m, d, t, off: f"{y}-{m}-{d}T{t}{off}", year, month, day, st.builds(lambda h, mi, s, sf: f"{h}:{mi}:{s}{sf}", hour, minute, second, secfrac), offset)
local_date_time = st.builds(lambda y, m, d, t: f"{y}-{m}-{d} {t}", year, month, day, st.builds(lambda h, mi, s, sf: f"{h}:{mi}:{s}{sf}", hour, minute, second, secfrac))
local_date = st.builds(lambda y, m, d: f"{y}-{m}-{d}", year, month, day)
local_time = st.builds(lambda t: t, st.builds(lambda h, mi, s, sf: f"{h}:{mi}:{s}{sf}", hour, minute, second, secfrac))

date_time_value = st.one_of(offset_date_time, local_date_time, local_date, local_time)

# Bare unquoted key (ASCII only)
_unquoted_key_chars = st.characters(whitelist_characters='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-')
unquoted_key = st.text(alphabet=_unquoted_key_chars, min_size=1, max_size=100)

# Quoted keys (allow empty quoted key "")
quoted_key_basic = basic_string  # basic string form
quoted_key_literal = literal_string

simple_key = st.one_of(unquoted_key, quoted_key_basic, quoted_key_literal)

# dotted key: simple_key (DOT simple_key)+
dotted_key = st.lists(simple_key, min_size=2, max_size=6).map(lambda parts: '.'.join(parts))

# Key strategy: choose simple or dotted; also sometimes produce very long keys and non-ASCII (to be rejected by parser as bare keys)
very_long_key = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=0x10FFFF).filter(lambda c: c != '\x00'), min_size=1, max_size=10000).map(lambda s: '"' + s + '"')
key_strategy = st.one_of(simple_key, dotted_key, very_long_key)

# Comments: start with '#' and then arbitrary text (comments may contain raw control chars accepted by parser)
comment_text = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c != '\x00'), min_size=0, max_size=60)
comment = comment_text.map(lambda t: '#' + t)

# Now define a recursive strategy for values: base types + arrays/inline tables via recursion
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value
)

# Helpers to create arrays and inline tables given a child strategy (values may be arrays or inline tables recursively)
def array_maker(child):
    # Valid array: [v, v, ...] with optional trailing comma, allow whitespace/newlines/comments between elements (we simulate with spaces/newlines comments)
    element = st.one_of(child, comment).map(lambda s: s if s.startswith('#') else s)  # allow comments as standalone
    # produce lists of elements (including empty)
    elems = st.lists(child, min_size=0, max_size=6)
    def mk_valid(lst):
        # join with commas and optional spaces; include trailing comma sometimes
        if not lst:
            return '[]'
        sep = ', '
        s = '[' + sep.join(lst)
        # optionally trailing comma
        s = s + (',]' if st.booleans().example() else ']')  # NOTE: .example() generally discouraged but here used only inside mapping; better to produce via strategies
        # The above use of .example() is not allowed in Hypothesis strategies; instead implement two branches
    # Implement proper strategies
    valid_list = elems.map(lambda lst: '[' + (', '.join(lst) if lst else '') + (',' if (len(lst) > 0 and (len(lst) % 2 == 0)) else '') + ']')
    # Create malformed variants: missing bracket, doubled comma, stray token, nested arrays using child
    malformed1 = elems.map(lambda lst: '[' + ', '.join(lst) + (',,' if lst else '') )  # missing closing bracket and doubled comma
    malformed2 = child.map(lambda v: '[ ' + v + ' ' )  # unterminated
    # combine
    return st.one_of(valid_list, malformed1, malformed2)

def inline_table_maker(child):
    # inline table keyvals: key = value, possibly trailing comma; newline inside inline table is invalid and we also produce such cases
    kv_value = st.tuples(simple_key, child).map(lambda t: f"{t[0]} = {t[1]}")
    kvs = st.lists(kv_value, min_size=0, max_size=6)
    valid = kvs.map(lambda lst: '{' + (', '.join(lst) if lst else '') + (',' if (len(lst) > 0 and (len(lst) % 2 == 1)) else '') + '}')
    # malformed: newline inside inline table
    malformed_newline = kvs.map(lambda lst: '{' + ('\n'.join(lst) if lst else '') + '}')
    # malformed: missing brace
    malformed_missing = kvs.map(lambda lst: '{' + (', '.join(lst) if lst else '') )
    return st.one_of(valid, malformed_newline, malformed_missing)

# Build the recursive value strategy: arrays and inline tables may contain values again
# Note: Hypothesis st.recursive expects a base strategy and an extension function that takes a strategy and returns a strategy.
def extend_children(children):
    return st.one_of(
        array_maker(children),
        inline_table_maker(children)
    )

value_strategy = st.recursive(base_value, extend_children, max_leaves=50)

# Build key_value line: key EQUALS value, with optional comments; include near-valid malformed forms like double equals or missing equals
def key_value_maker(k, v):
    # Occasionally produce duplicate equals, missing spaces, or value on next line / stray token
    variants = [
        f"{k} = {v}",
        f"{k}={v}",
        f"{k} == {v}",   # doubled delimiter (malformed)
        f"{k} =\n{v}",   # value on next line (malformed)
        f"{k} = {v} # inline comment"
    ]
    return st.sampled_from(variants)

kv_line = st.deferred(lambda: st.tuples(key_strategy, value_strategy).flatmap(lambda kv: key_value_maker(kv[0], kv[1])))

# Tables: standard table [key] and array of tables [[key]]
standard_table = key_strategy.map(lambda k: f"[{k}]")
array_table = key_strategy.map(lambda k: f"[[{k}]]")
# Malformed table variants
malformed_table = key_strategy.map(lambda k: f"[{k}" )  # missing closing bracket
malformed_array_table = key_strategy.map(lambda k: f"[[{k}]]]" )  # extra bracket

table_line = st.one_of(standard_table, array_table, malformed_table, malformed_array_table)

# Expression: key_value, table, or comment
expression = st.one_of(
    kv_line,
    table_line,
    comment
)

# Document: sequence of expressions separated by newlines. Include empty documents and documents with no trailing newline.
document = st.lists(expression, min_size=0, max_size=30).map(lambda parts: '\n'.join(parts))

# Top-level strategy must be named `strategy` and produce str
strategy = document
```