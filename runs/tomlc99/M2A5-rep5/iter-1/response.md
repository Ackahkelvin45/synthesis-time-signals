```python
from hypothesis import strategies as st
import json

# Basic building blocks

# Avoid raw NUL ('\x00') anywhere
non_nul_char = st.characters(blacklist_characters="\x00")
# Control chars excluding NUL (1..31)
control_char = st.characters(min_codepoint=1, max_codepoint=31, blacklist_characters="\x00")
# Visible non-quote, non-newline chars for basic strings (no " and no newline)
basic_raw_char = st.characters(blacklist_characters='\x00"\n\r')
# For literal strings, exclude single-quote and newline
literal_raw_char = st.characters(blacklist_characters="\x00'\n\r")
# For multiline strings allow newline but not NUL
ml_any_char = st.characters(blacklist_characters="\x00")

# Escapes allowed (and a couple invalid ones to exercise rejection)
escape_common = st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\\', '\\"', '\\/'])
escape_invalid = st.sampled_from(['\\q', '\\z'])
escape_unicode_u = st.integers(0, 0xFFFF).map(lambda i: '\\u' + format(i, '04x'))
escape_unicode_U = st.integers(0, 0x10FFFF).map(lambda i: '\\U' + format(i, '08x'))

escape_seq = st.one_of(escape_common, escape_invalid, escape_unicode_u, escape_unicode_U)

# Basic string content: mix of raw chars, escapes, and control characters (but no raw quotes/newlines)
basic_segment = st.one_of(basic_raw_char.map(lambda c: c), escape_seq, control_char.map(lambda c: c))
basic_string_content = st.lists(basic_segment, min_size=0, max_size=40).map(''.join)
basic_string = st.one_of(
    basic_string_content.map(lambda s: '"' + s + '"'),
    # Unterminated string variant (missing closing quote) to exercise near-valid malformed inputs
    basic_string_content.map(lambda s: '"' + s)
)

# Literal string (single-quoted) cannot contain newline for single-line literal; include unterminated too
literal_string_content = st.lists(literal_raw_char | control_char, min_size=0, max_size=40).map(''.join')
literal_string = st.one_of(
    literal_string_content.map(lambda s: "'" + s + "'"),
    # unterminated single-quoted
    literal_string_content.map(lambda s: "'" + s)
)

# Multiline basic string (triple quotes) allows escapes and newlines
ml_basic_segment = st.one_of(escape_seq, ml_any_char.map(lambda c: c))
ml_basic_content = st.lists(ml_basic_segment, min_size=0, max_size=40).map(''.join)
ml_basic_string = st.one_of(
    ml_basic_content.map(lambda s: '"""' + s + '"""'),
    # unterminated multiline
    ml_basic_content.map(lambda s: '"""' + s)
)

# Multiline literal string
ml_literal_segment = st.one_of(ml_any_char.map(lambda c: c))
ml_literal_content = st.lists(ml_literal_segment, min_size=0, max_size=40).map(''.join)
ml_literal_string = st.one_of(
    ml_literal_content.map(lambda s: "'''" + s + "'''"),
    # unterminated
    ml_literal_content.map(lambda s: "'''" + s)
)

# String value strategy covering all four quoting forms
string_value = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Integer formats: decimal (with possible leading zeros and underscores), hex, oct, bin
def insert_underscores(s):
    # Insert underscores randomly between digits (not at ends), implemented via strategy mapping externally
    return s

dec_int = st.integers(min_value=-10**40, max_value=10**40).map(lambda i: str(i))
# decimal with possible leading zeros
dec_leading_zeros = st.integers(min_value=0, max_value=9999).map(lambda i: '{:0{}d}'.format(i, (i.bit_length() // 3) + 1))
# formatted with underscores occasionally
dec_with_underscores = st.integers(min_value=0, max_value=10**12).map(
    lambda i: ('_' .join(str(i)[j:j+3] for j in range(0, len(str(i)), 3))) if i >= 1000 else str(i)
)
hex_int = st.integers(min_value=0, max_value=2**128).map(lambda i: '0x' + format(i, 'x'))
oct_int = st.integers(min_value=0, max_value=2**128).map(lambda i: '0o' + format(i, 'o'))
bin_int = st.integers(min_value=0, max_value=2**128).map(lambda i: '0b' + format(i, 'b'))
# Some extremes with explicit signs
extreme_int = st.sampled_from([
    str(10**40),
    '-' + str(10**40),
    '+123456789012345678901234567890'
])
integer_value = st.one_of(dec_int, dec_leading_zeros, dec_with_underscores, hex_int, oct_int, bin_int, extreme_int)

# Floating point: typical, missing leading/trailing digit, exponent extremes, inf/nan
float_normal = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.10g'))
# produce "1." and ".5" forms
float_trailing_dot = st.integers(min_value=0, max_value=1000).map(lambda i: str(i) + '.')
float_leading_dot = st.integers(min_value=1, max_value=999).map(lambda i: '.' + str(i))
float_expreme = st.sampled_from(['1e309', '-1e309', '1e-9999', '3.1415e+1000'])
float_inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
floating_value = st.one_of(float_normal, float_trailing_dot, float_leading_dot, float_expreme, float_inf_nan)

# Booleans
bool_value = st.sampled_from(['true', 'false'])

# Date/time forms (calendar-invalid allowed)
year = st.integers(min_value=0, max_value=9999).map(lambda y: '{:04d}'.format(y))
month = st.integers(min_value=0, max_value=99).map(lambda m: '{:02d}'.format(m))
day = st.integers(min_value=0, max_value=99).map(lambda d: '{:02d}'.format(d))
hour = st.integers(min_value=0, max_value=99).map(lambda h: '{:02d}'.format(h))
minute = st.integers(min_value=0, max_value=99).map(lambda m: '{:02d}'.format(m))
second = st.integers(min_value=0, max_value=99).map(lambda s: '{:02d}'.format(s))
secfrac = st.integers(min_value=0, max_value=10**6).map(lambda s: '.' + str(s)) | st.just('')
offset = st.one_of(st.just('Z'), st.integers(min_value=-23, max_value=23).map(lambda h: ('+' if h>=0 else '-') + '{:02d}:00'.format(abs(h))))
offset_datetime = st.tuples(year, month, day, st.sampled_from(['T', 't', ' ']), hour, minute, second, secfrac, offset).map(
    lambda t: '{}-{}-{}{}{}:{}:{}{}{}'.format(*t)
)
local_date_time = st.tuples(year, month, day, st.sampled_from(['T', 't', ' ']), hour, minute, second, secfrac).map(
    lambda t: '{}-{}-{}{}{}:{}:{}{}'.format(*t)
)
local_date = st.tuples(year, month, day).map(lambda t: '{}-{}-{}'.format(*t))
local_time = st.tuples(hour, minute, second, secfrac).map(lambda t: '{}:{}:{}{}'.format(*t))
date_time_value = st.one_of(offset_datetime, local_date_time, local_date, local_time)

# Base (non-recursive) value strategy: covers strings, ints, floats, bools, dates
base_value = st.one_of(string_value, integer_value, floating_value, bool_value, date_time_value)

# Key strategies
# Unquoted keys: ASCII letters/digits/_- using regex
unquoted_key = st.from_regex(r"[A-Za-z0-9_-]{1,20}", fullmatch=True)
# Quoted keys use the string strategies above (they include quotes)
quoted_key = st.one_of(basic_string, literal_string)
simple_key = st.one_of(quoted_key, unquoted_key)

# Dotted key: two to four simple keys joined by dot
dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: '.'.join(p if p.startswith(('"', "'")) else p for p in parts))

# Comments
comment_text = st.text(alphabet=st.characters(blacklist_characters="\x00\n\r"), min_size=0, max_size=40)
comment = st.one_of(st.just(''), comment_text.map(lambda s: '# ' + s))

# Helper to optionally append inline comment
def with_optional_comment(s_strat):
    return st.tuples(s_strat, st.one_of(st.just(''), comment)).map(lambda t: t[0] + ('' if not t[1] else ' ' + t[1]))

# Recursive containers: arrays and inline tables
# We must use st.recursive for grammar's recursive productions.
def array_builder(children):
    # build arrays with optional comments, newlines, trailing commas, mixed types
    return st.lists(children, min_size=0, max_size=6).map(
        lambda items: '[' +
        (', '.join(items) if items else '') +
        (',' if items and st.random_module().random() < 0.2 else '') +
        ']'
    )

def inline_table_builder(children):
    # inline table: { key = value, ... } - no newline inside for valid ones (but sometimes we'll inject newline later)
    def make_inline(kvs):
        if not kvs:
            return '{}'
        body = ', '.join(kvs)
        # sometimes add trailing comma (accepted)
        if st.random_module().random() < 0.2:
            body = body + ','
        return '{' + body + '}'
    # kv pairs with keys (unquoted or quoted) and children as values
    kv = st.tuples(st.one_of(unquoted_key, quoted_key), children).map(lambda t: '{} = {}'.format(t[0], t[1]))
    return st.lists(kv, min_size=0, max_size=6).map(make_inline)

# Use st.recursive to construct nested arrays and inline tables
recursive_values = st.recursive(
    base_value,
    lambda children: st.one_of(
        # arrays can contain children which themselves may be arrays or inline tables
        st.deferred(lambda: st.lists(children, min_size=0, max_size=6).map(lambda lst: '[' + (', '.join(lst) if lst else '') + (',' if lst and st.random_module().random() < 0.15 else '') + ']')),
        # inline tables (no newlines inside)
        st.deferred(lambda: st.lists(st.tuples(st.one_of(unquoted_key, quoted_key), children), min_size=0, max_size=6).map(
            lambda kvs: '{' + (', '.join('{} = {}'.format(k, v) for (k, v) in kvs) if kvs else '') + (',' if kvs and st.random_module().random() < 0.15 else '') + '}'
        ))
    ),
    max_leaves=200
)

# Additionally, create an explicit deep nesting generator (1500-2048 levels) using @st.composite (allowed)
@st.composite
def deep_nested_array(draw):
    depth = draw(st.integers(min_value=1500, max_value=2048))
    inner = draw(base_value)
    s = inner
    # build up nested arrays; this uses composite recursion (not st.recursive) to create targeted deep depth
    for _ in range(depth):
        s = '[' + s + ']'
    # occasionally append a newline/comment inside top-level to make it a full document line
    if draw(st.booleans()):
        s = s + '  # deep nesting'
    return s

# inline_table_no_newline validator: sometimes we intentionally insert a newline (malformed) into inline table
@st.composite
def inline_table_maybe_bad(draw):
    kv_count = draw(st.integers(min_value=0, max_value=6))
    kvs = []
    for _ in range(kv_count):
        k = draw(st.one_of(unquoted_key, quoted_key))
        v = draw(recursive_values)
        kvs.append(f"{k} = {v}")
    body = ', '.join(kvs)
    if kv_count and draw(st.booleans()):  # inject a newline into inline table (grammar rejects)
        # inject newline inside inline table (malformed)
        body = body.replace(', ', ',\n', 1)
    if kv_count and draw(st.booleans()):
        body = body + ','
    return '{' + body + '}'

# value strategy used in key_value lines and inside arrays/tables
value = st.one_of(recursive_values, string_value, integer_value, floating_value, bool_value, date_time_value, inline_table_maybe_bad())

# key_value expression
key_value = st.tuples(st.one_of(dotted_key, simple_key), value, st.one_of(st.just(''), comment)).map(
    lambda t: (t[0] + ' = ' + t[1]) + ('' if not t[2] else ' ' + t[2])
)

# table headings and array tables
standard_table = st.tuples(st.one_of(dotted_key, simple_key), st.one_of(st.just(''), comment)).map(
    lambda t: '[' + t[0] + ']' + ('' if not t[1] else ' ' + t[1])
)
array_table = st.tuples(st.one_of(dotted_key, simple_key), st.one_of(st.just(''), comment)).map(
    lambda t: '[[' + t[0] + ']]' + ('' if not t[1] else ' ' + t[1])
)

# comment-only expression
comment_only = comment.map(lambda c: c if c else '')

# expression can be key_value, table, or comment-only
expression = st.one_of(
    key_value,
    standard_table,
    array_table,
    comment_only
)

# Create documents: sequences of expressions separated by newlines; include empty and comment-only documents.
nl = st.sampled_from(['\n', '\r\n'])
@st.composite
def document(draw):
    # choose number of lines small to moderate, but occasionally allow larger docs
    size = draw(st.integers(min_value=0, max_value=12))
    lines = []
    for _ in range(size):
        lines.append(draw(expression))
    # Mix in explicit deep nested array lines occasionally
    if draw(st.booleans()):
        if draw(st.booleans()):
            lines.append(draw(deep_nested_array()))
    # Possibly introduce duplicate keys (allowed by generation; parser may reject)
    if lines and draw(st.booleans()):
        # pick an existing key_value line and duplicate it
        kvs = [ln for ln in lines if '=' in ln]
        if kvs and draw(st.booleans()):
            lines.append(draw(st.sampled_from(kvs)))
    # join with random newlines
    sep = draw(nl)
    doc = sep.join(lines)
    # optionally add trailing newline or not
    if draw(st.booleans()):
        doc = doc + ('' if draw(st.booleans()) else sep)
    # Occasionally append stray tokens or perform near-valid-but-malformed edits
    edit_choice = draw(st.integers(min_value=0, max_value=6))
    if edit_choice == 1:
        # remove a closing bracket/braces (missing delimiter)
        if ']' in doc:
            doc = doc.replace(']', '', 1)
        elif '}' in doc:
            doc = doc.replace('}', '', 1)
    elif edit_choice == 2:
        # double a delimiter (e.g., '==' or ',,')
        if '=' in doc:
            doc = doc.replace('=', '==', 1)
    elif edit_choice == 3:
        # unterminated string: remove last quote character if any
        if '"' in doc:
            idx = doc.rfind('"')
            doc = doc[:idx] + doc[idx+1:]
        elif "'" in doc:
            idx = doc.rfind("'")
            doc = doc[:idx] + doc[idx+1:]
    elif edit_choice == 4:
        # stray token appended
        doc = doc + '\n' + '??? stray_token'
    elif edit_choice == 5:
        # inject a newline inside an inline table (likely malformed)
        doc = doc.replace('{', '{\n', 1)
    # Ensure we never embed raw NUL characters (defensive)
    doc = doc.replace('\x00', '')
    return doc

# Final strategy: include diverse documents and occasionally purely-malleable ones
strategy = st.one_of(
    document(),
    # small focused documents: empty document, comment-only, single key-value of each type
    st.just(''),
    comment_only.map(lambda c: c if c else ''),
    st.tuples(simple_key, st.one_of(string_value, integer_value, floating_value, bool_value, date_time_value)).map(lambda t: t[0] + ' = ' + t[1]),
    # inline table only document
    inline_table_maybe_bad().map(lambda s: 'a = ' + s),
    # deep nested array as a whole document
    deep_nested_array(),
    # combine a few expressions into a document (to vary structure)
    st.lists(expression, min_size=1, max_size=5).map(lambda lst: '\n'.join(lst))
)
```