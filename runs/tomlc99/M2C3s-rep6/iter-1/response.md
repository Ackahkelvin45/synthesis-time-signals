```python
from hypothesis import strategies as st
import json

# Character pools avoiding raw NUL (0x00). NUL inside strings should be escaped as \u0000 if desired.
# Helpers for building string content pieces.
_ctrl_char = st.integers(min_value=1, max_value=0x1F).map(chr)  # control codes except NUL
_printable_safe = st.characters(min_codepoint=0x20, blacklist_characters='"\n\\\x00')  # excludes " \ and newline, NUL
_nonascii = st.characters(min_codepoint=0x80, blacklist_characters='\x00')  # higher plane unicode

_escape_basic = st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\\', '\\"', '\\/'])
_escape_invalid = st.just('\\q')  # invalid escape to create near-malformed inputs
_unicode_u = st.integers(min_value=0, max_value=0xFFFF).map(lambda x: '\\u%04X' % x)
_unicode_U = st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda x: '\\U%08X' % x)

_segment = st.one_of(
    _printable_safe,
    _ctrl_char,
    _nonascii,
    _escape_basic,
    _unicode_u,
    _unicode_U,
    _escape_invalid
)

# Build short to-medium sequences of segments for string bodies.
_segments_list = st.lists(_segment, min_size=0, max_size=20).map(''.join)

# Variants of TOML strings

# Basic (quoted) string: cannot contain raw newline; may include raw control chars per parser reality.
basic_string = st.one_of(
    # well-formed basic
    _segments_list.map(lambda s: '"' + s + '"'),
    # unterminated (missing closing quote)
    _segments_list.map(lambda s: '"' + s),
    # doubled quote (extra leading or trailing quote)
    _segments_list.map(lambda s: '""' + s + '"'),
)

# Literal string: single quotes, no escapes interpreted. No raw newline allowed in this form.
literal_body = st.lists(st.one_of(
    st.characters(min_codepoint=0x20, blacklist_characters="'\n\x00"),
    _ctrl_char,
    _nonascii
), min_size=0, max_size=20).map(''.join')
literal_string = st.one_of(
    literal_body.map(lambda s: "'" + s + "'"),
    literal_body.map(lambda s: "'" + s),  # unterminated
)

# Multiline basic string: triple quotes, may include newlines and escapes.
ml_basic_body = st.lists(st.one_of(
    st.characters(blacklist_characters='\x00'),  # allow almost anything except NUL at raw level
    _escape_basic,
    _unicode_u,
    _unicode_U,
    _escape_invalid
), min_size=0, max_size=200).map(''.join)
ml_basic_string = st.one_of(
    ml_basic_body.map(lambda s: '"""' + s + '"""'),
    ml_basic_body.map(lambda s: '"""' + s),  # unterminated
)

# Multiline literal string: triple single quotes, very permissive
ml_literal_body = st.lists(st.one_of(
    st.characters(blacklist_characters='\x00'),  # avoid raw NUL
), min_size=0, max_size=200).map(''.join)
ml_literal_string = st.one_of(
    ml_literal_body.map(lambda s: "'''" + s + "'''"),
    ml_literal_body.map(lambda s: "'''" + s),  # unterminated
)

string_value = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Integers in various bases, with underscores, leading zeros allowed per parser realities.
def int_with_underscores(prefix='', digits='0123456789', min_len=1, max_len=30):
    def mk(s):
        # randomly inject underscores
        if len(s) <= 1:
            return s
        out = []
        for ch in s:
            out.append(ch)
            # allow underscore insertion randomly
            # but using st is easier: we accept the passed string whole (we will generate randomly below)
        return ''.join(out)
    # Instead of complex insertion, produce digits with optional underscores
    pieces = st.lists(st.sampled_from(list(digits)), min_size=min_len, max_size=max_len).map(''.join)
    underscores_inserted = pieces.map(lambda s: '_'.join([s[i:i+max(1, max(1, len(s)//max(1, min_len)))] for i in range(0, len(s), max(1, len(s)//max(1, min_len)))]))
    return st.one_of(
        pieces.map(lambda s: prefix + s),
        underscores_inserted.map(lambda s: prefix + s),
    )

dec_int = st.one_of(
    st.integers(min_value=-10**40, max_value=10**40).map(str),
    int_with_underscores('', digits='0123456789', min_len=1, max_len=40)
)
hex_int = int_with_underscores('0x', digits='0123456789abcdefABCDEF', min_len=1, max_len=32)
oct_int = int_with_underscores('0o', digits='01234567', min_len=1, max_len=24)
bin_int = int_with_underscores('0b', digits='01', min_len=1, max_len=64)

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int)

# Floating point values including forms allowed by parser (1., .5), large exponents, inf/nan
float_plain = st.one_of(
    # normal floats with optional exponent
    st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, '.12g')),
    # explicit patterns: 1., .5, 1e309
    st.one_of(
        st.integers(min_value=-999999999, max_value=999999999).map(lambda x: str(x) + '.'),
        st.integers(min_value=0, max_value=9).map(lambda x: '.' + str(x)),
        st.integers(min_value=1, max_value=10**3).map(lambda x: '1e' + str(x)),
        st.integers(min_value=300, max_value=1000).map(lambda e: '1e' + str(e))  # huge exponent
    )
)
inf_nan = st.one_of(st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan']))

float_value = st.one_of(float_plain, inf_nan)

# Booleans
bool_value = st.sampled_from(['true', 'false'])

# Date/time forms (may be calendar-invalid)
def padded(n, width=2):
    return str(n).zfill(width)

date_value = st.one_of(
    # Local date
    st.tuples(st.integers(1900, 9999), st.integers(1, 12), st.integers(1, 31)).map(lambda t: f"{t[0]}-{padded(t[1])}-{padded(t[2])}"),
    # Local time
    st.tuples(st.integers(0, 23), st.integers(0, 59), st.integers(0, 59), st.one_of(st.none(), st.integers(0, 999999)).map(lambda x: ('.' + str(x)) if x is not None else '')).map(lambda t: f"{padded(t[0])}:{padded(t[1])}:{padded(t[2])}{t[3]}"),
    # Local date-time and offset date-time
    st.builds(lambda d, tm, off: f"{d} {tm}{off}",
              st.one_of(
                  st.tuples(st.integers(1900, 9999), st.integers(1, 12), st.integers(1, 31)).map(lambda t: f"{t[0]}-{padded(t[1])}-{padded(t[2])}"),
                  st.tuples(st.integers(0, 99), st.integers(1, 12), st.integers(1, 31)).map(lambda t: f"{t[0]}-{padded(t[1])}-{padded(t[2])}")  # intentionally allow odd years/months for invalid calendars
              ),
              st.tuples(st.integers(0, 23), st.integers(0, 59), st.integers(0, 59), st.one_of(st.none(), st.integers(0, 999999)).map(lambda x: ('.' + str(x)) if x is not None else '')).map(lambda t: f"{padded(t[0])}:{padded(t[1])}:{padded(t[2])}{t[3]}"),
              st.one_of(st.just('Z'), st.tuples(st.sampled_from(['+','-']), st.integers(0,23), st.integers(0,59)).map(lambda o: o[0] + padded(o[1]) + ':' + padded(o[2])))
             )
)

# Base (non-recursive) value strategy
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_value
)

# Recursive construction for arrays and inline tables
def _array_builder(children):
    # children is a strategy producing textual values (they may themselves be arrays or inline tables)
    def mk_array(lst):
        # lst is a list of element strings
        # insert occasional comments or whitespace fragments
        parts = []
        for v in lst:
            parts.append(v)
        if not parts:
            inner = ''
        else:
            inner = ', '.join(parts)
        # allow trailing comma sometimes
        return '[' + inner + (',' if st.booleans().example() else '') + ']'
    # Using lists of children and mapping
    return st.lists(children, min_size=0, max_size=6).map(lambda lst: '[' + (', '.join(lst) if lst else '') + (',' if st.randoms().example().randint(0,4)==0 else '') + ']')

def _inline_table_builder(children):
    # Create inline tables {key = value, ...}
    def make_key():
        # unquoted basic key or quoted empty key etc
        return st.one_of(
            # unquoted keys A-Za-z0-9_- up to 50 chars
            st.text(alphabet=st.characters(min_codepoint=0x30, max_codepoint=0x7A, blacklist_characters=' \t\r\n"\'{}=,[]#\\\x00'), min_size=1, max_size=20),
            # quoted basic string key
            _segments_list.map(lambda s: '"' + s + '"'),
            # literal quoted key
            literal_body.map(lambda s: "'" + s + "'")
        )
    # produce lists of (key, value)
    kv = st.lists(st.tuples(make_key(), children), min_size=0, max_size=6)
    def kv_to_inline(kvlist):
        if not kvlist:
            return '{ }'
        parts = []
        for k, v in kvlist:
            # avoid newlines in inline table header normally, but sometimes allow them to create invalid cases
            parts.append(f"{k} = {v}")
        s = '{' + ', '.join(parts) + (',' if st.randoms().example().randint(0,7)==0 else '') + '}'
        return s
    return kv.map(kv_to_inline)

# Use st.recursive to create arrays and inline tables that can nest
recursive_values = st.recursive(
    base_value,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=6).map(lambda lst: '[' + (', '.join(lst) if lst else '') + (',' if st.randoms().example().randint(0,4)==0 else '') + ']'),
        # nested array start (explicit nested arrays)
        st.builds(lambda inner: '[' + inner + ']', children),
        # inline table using children for values
        st.builds(lambda kvs: kvs, _inline_table_builder(children))
    ),
    max_leaves=200
)

# Additionally, a composite to produce extremely deep nesting arrays (up to ~2048).
@st.composite
def deep_nested_array(draw):
    # Pick a depth biased toward high values to exercise recursion limit band
    depth = draw(st.one_of(
        st.integers(min_value=0, max_value=40),  # many shallow cases
        st.integers(min_value=100, max_value=500),
        st.integers(min_value=1500, max_value=2048)
    ))
    # base inner element: a small atomic value
    inner = draw(st.one_of(
        integer_value,
        string_value,
        st.just('null'),  # stray token possibility
        float_value
    ))
    # Build nested brackets
    s = inner
    for _ in range(depth):
        s = '[' + s + ']'
    return s

# The overall value strategy: allow base, recursive arrays/inline tables, and occasional deep nesting
value_strategy = st.one_of(
    base_value,
    recursive_values,
    deep_nested_array()
)

# Key strategies (unquoted and quoted, dotted keys)
unquoted_key = st.text(alphabet=st.characters(min_codepoint=0x30, max_codepoint=0x7A, blacklist_characters=' \t\r\n"\'{}=,[]#\\\x00'), min_size=1, max_size=100)
quoted_key_basic = _segments_list.map(lambda s: '"' + s + '"')
quoted_key_literal = literal_body.map(lambda s: "'" + s + "'")
simple_key = st.one_of(unquoted_key, quoted_key_basic, quoted_key_literal)
dotted_key = st.lists(simple_key, min_size=1, max_size=5).map(lambda parts: '.'.join(parts))

key_strategy = st.one_of(simple_key, dotted_key)

# Comments (may include control chars in comments)
comment_line = st.one_of(
    st.just(''),  # no comment
    st.builds(lambda s: '# ' + s, st.text(alphabet=st.characters(blacklist_characters='\x00\r\n'), min_size=0, max_size=80)),
    st.builds(lambda s: '#'+s, st.text(alphabet=st.characters(blacklist_characters='\x00\r\n'), min_size=0, max_size=80))
)

# Generate a full document. Use a composite strategy so we can inject duplicates, malformed tokens, tables, etc.
@st.composite
def document(draw):
    n_lines = draw(st.integers(min_value=0, max_value=40))
    lines = []
    used_keys = []
    used_tables = []
    for i in range(n_lines):
        kind = draw(st.integers(min_value=0, max_value=7))
        nl = draw(st.sampled_from(['\n', '\r\n']))
        if kind == 0:
            # comment line or blank
            c = draw(comment_line)
            lines.append(c)
        elif kind == 1:
            # a table header, sometimes malformed (missing bracket or extra)
            k = draw(dotted_key)
            is_array_table = draw(st.booleans())
            header = ('[[' + k + ']]') if is_array_table else ('[' + k + ']')
            # introduce malformed variants
            if draw(st.booleans()):
                if draw(st.booleans()):
                    # missing closing bracket
                    header = header[:-1]
                else:
                    # doubled bracket or stray token
                    header = header + ']'
            lines.append(header)
            used_tables.append(k)
        elif kind == 2:
            # array table line with stray tokens
            k = draw(dotted_key)
            header = '[[' + k + ']]'
            if draw(st.booleans()):
                header = header + ' ???'  # stray token
            lines.append(header)
            used_tables.append(k)
        else:
            # key/value pair line
            # sometimes choose a previous key to create duplicates
            if used_keys and draw(st.booleans()):
                k = draw(st.sampled_from(used_keys))
            else:
                k = draw(key_strategy)
                used_keys.append(k)
            v = draw(value_strategy)
            # sometimes introduce malformed equals variants
            eq = '='
            if draw(st.integers(min_value=0, max_value=10)) == 0:
                eq = '=='  # doubled delimiter
            if draw(st.integers(min_value=0, max_value=30)) == 0:
                # missing equals: put space instead
                line = f"{k} {v}"
            else:
                # include a comment trailing sometimes
                if draw(st.booleans()):
                    c = draw(comment_line)
                    if c:
                        line = f"{k} {eq} {v} {c}"
                    else:
                        line = f"{k} {eq} {v}"
                else:
                    line = f"{k} {eq} {v}"
            lines.append(line)
    # Possibly add a final table section or empty table to cover empty tables
    if draw(st.booleans()):
        if draw(st.booleans()):
            # empty table
            t = draw(simple_key)
            lines.append('[' + t + ']')
        else:
            t = draw(dotted_key)
            lines.append('[[' + t + ']]')
    # Join lines using a sampled newline; include possibility of no trailing newline
    newline = draw(st.sampled_from(['\n', '\r\n']))
    doc = newline.join(lines)
    if draw(st.booleans()):
        doc += newline
    # Occasionally produce completely empty document or comment-only document (already possible)
    # Return final string
    return doc

# Top-level export named `strategy`
strategy = document()
```