Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# Helper character strategies (never emit raw NUL '\x00')
_non_nul_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c != "\x00")
# For basic strings disallow raw double-quote, backslash, newline, CR
_basic_char = _non_nul_char.filter(lambda c: c not in {'"', '\\', '\n', '\r'})
# For literal strings disallow single-quote, newline, CR
_literal_char = _non_nul_char.filter(lambda c: c not in {"'", '\n', '\r'})
# For multiline strings allow newline and most characters but avoid embedding the terminator sequence often
_ml_char = _non_nul_char.filter(lambda c: c != '\x00')

# Escape sequences (as literal two-character or longer sequences placed into basic strings)
_escape_sequences = st.sampled_from([
    r'\n', r'\r', r'\t', r'\\', r'\"', r"\'", r'\b', r'\f',
    # Unicode escapes, including \u0000 (allowed), and high codepoint
    r'\u0000', r'\u0041', r'\U0001F600',
    # Occasionally include an invalid escape to exercise parser rejection
    r'\q',
    # include a hex escape to exercise parser handling of \xNN
    r'\x7f'
])

# Simple helper to build quoted string content from pieces (mix of raw chars and escape sequences)
_piece_basic = st.one_of(_basic_char.map(lambda c: c), _escape_sequences)
_piece_literal = st.one_of(_literal_char.map(lambda c: c))
_piece_ml = st.one_of(_ml_char.map(lambda c: c), _escape_sequences)

# Keys: unquoted, quoted (basic or literal), dotted combinations, and extremely long keys
_unquoted_key = st.one_of(
    # typical shorter keys
    st.text(alphabet=list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"), min_size=1, max_size=20),
    # occasional very long key to test limits (up to 10k chars)
    st.text(alphabet=list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"), min_size=1, max_size=10000)
)

@st.composite
def quoted_basic_key(draw):
    pieces = draw(st.lists(_piece_basic, min_size=0, max_size=40))
    return '"' + ''.join(pieces) + '"'

@st.composite
def quoted_literal_key(draw):
    pieces = draw(st.lists(_piece_literal, min_size=0, max_size=40))
    return "'" + ''.join(pieces) + "'"

# simple_key can be quoted or unquoted
simple_key = st.one_of(_unquoted_key, quoted_basic_key(), quoted_literal_key())

# dotted_key: simple_key ( '.' simple_key )+
@st.composite
def dotted_key(draw):
    n = draw(st.integers(min_value=2, max_value=5))
    parts = [draw(simple_key) for _ in range(n)]
    return '.'.join(parts)

key = st.one_of(simple_key, dotted_key())

# Numeric generators
@st.composite
def decimal_int_str(draw):
    # Generate an integer value then randomly format with underscores or leading zeros
    n = draw(st.integers(min_value=-10**120, max_value=10**120))
    s = str(abs(n))
    # Possibly add leading zeros (leading zeros accepted by parser)
    if draw(st.booleans()):
        leading = draw(st.integers(min_value=0, max_value=5))
        s = '0' * leading + s
    # Optionally insert underscores between digits
    if len(s) > 1 and draw(st.booleans()):
        parts = []
        i = 0
        while i < len(s):
            take = draw(st.integers(min_value=1, max_value=min(3, len(s)-i)))
            parts.append(s[i:i+take])
            i += take
        s = '_'.join(parts)
    if n < 0:
        s = '-' + s
    else:
        if draw(st.booleans()):
            s = '+' + s
    return s

@st.composite
def base_int_str(draw):
    kind = draw(st.sampled_from(['hex', 'oct', 'bin']))
    # create several digits and optional underscores
    if kind == 'hex':
        digits = '0123456789abcdefABCDEF'
        body = ''.join(draw(st.lists(st.sampled_from(list(digits)), min_size=1, max_size=40)))
        # insert underscores sometimes
        if draw(st.booleans()):
            body = '_'.join([body[i:i+draw(st.integers(1,4))] for i in range(0, len(body), 4)])
        return '0x' + body
    if kind == 'oct':
        digits = '01234567'
        body = ''.join(draw(st.lists(st.sampled_from(list(digits)), min_size=1, max_size=40)))
        if draw(st.booleans()):
            body = '_'.join([body[i:i+draw(st.integers(1,3))] for i in range(0, len(body), 3)])
        return '0o' + body
    else:
        digits = '01'
        body = ''.join(draw(st.lists(st.sampled_from(list(digits)), min_size=1, max_size=80)))
        if draw(st.booleans()):
            body = '_'.join([body[i:i+draw(st.integers(1,4))] for i in range(0, len(body), 4)])
        return '0b' + body

integer_value = st.one_of(decimal_int_str(), base_int_str())

@st.composite
def float_str(draw):
    # include INF/NAN forms sometimes
    special = draw(st.booleans())
    if special:
        s = draw(st.sampled_from(['inf', '-inf', '+inf', 'nan', '-nan', '+nan']))
        return s
    # normal float: choose patterns like 1.23, 1., .5, 1e10, 1.0e-5
    part_digits = lambda maxd=10: ''.join(draw(st.lists(st.sampled_from(list('0123456789')), min_size=1, max_size=maxd)))
    choose = draw(st.integers(min_value=0, max_value=3))
    if choose == 0:
        # frac only like .5
        frac = part_digits(10)
        if draw(st.booleans()):
            return '.' + frac
        else:
            return '.' + frac + (draw(st.sampled_from(['e+10','E-5','e309','e+309'])) if draw(st.booleans()) else '')
    if choose == 1:
        # number with dot maybe no digits after
        intpart = part_digits(10)
        if draw(st.booleans()):
            return intpart + '.'
        else:
            frac = part_digits(10)
            s = intpart + '.' + frac
            if draw(st.booleans()):
                s += draw(st.sampled_from(['e10','e+100','E-308','e309','E+309']))
            return s
    else:
        # exponent only like 1e10
        intpart = part_digits(10)
        s = intpart + draw(st.sampled_from(['e10','e+10','e-5','E+309','e309']))
        return s

# Date/time strings (various forms, allow calendar-invalid dates)
@st.composite
def date_time_str(draw):
    year = draw(st.integers(min_value=0, max_value=9999))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=31))  # may be invalid (allowed)
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    secfrac = ''
    if draw(st.booleans()):
        secfrac = '.' + ''.join(draw(st.lists(st.sampled_from(list('0123456789')), min_size=1, max_size=6)))
    delim = draw(st.sampled_from(['T', 't', ' ']))
    offset_choice = draw(st.integers(min_value=0, max_value=2))
    if offset_choice == 0:
        # offset-date-time
        offset = draw(st.one_of(st.just('Z'), st.just('+00:00'), st.just('-05:30'),
                                st.text(alphabet=list('+-0123456789:'), min_size=3, max_size=6)))
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{secfrac}{offset}"
    elif offset_choice == 1:
        # local date-time (no offset)
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{secfrac}"
    else:
        # local date or local time only
        if draw(st.booleans()):
            return f"{year:04d}-{month:02d}-{day:02d}"
        else:
            return f"{hour:02d}:{minute:02d}:{second:02d}{secfrac}"

# Boolean
bool_str = st.sampled_from(['true', 'false'])

# String value generators: basic, multiline basic, literal, multiline literal
@st.composite
def basic_string(draw):
    pieces = draw(st.lists(_piece_basic, min_size=0, max_size=60))
    return '"' + ''.join(pieces) + '"'

@st.composite
def literal_string(draw):
    pieces = draw(st.lists(_piece_literal, min_size=0, max_size=60))
    return "'" + ''.join(pieces) + "'"

@st.composite
def ml_basic_string(draw):
    # avoid embedding the terminator '"""' too often; allow newlines
    parts = draw(st.lists(_piece_ml, min_size=0, max_size=200))
    content = ''.join(parts)
    # sometimes include explicit backslash + newline sequences (line continuation)
    if draw(st.booleans()):
        content = content.replace('\n', '\\\n')
    # ensure we don't accidentally create the closing triple sequence too early
    content = content.replace('"""', '\"\"')  # nudge to avoid terminator
    return '"""' + content + '"""'

@st.composite
def ml_literal_string(draw):
    parts = draw(st.lists(_ml_char, min_size=0, max_size=200))
    content = ''.join(parts)
    # avoid ''' sequence
    content = content.replace("'''", "''")
    return "'''" + content + "'''"

string_value = st.one_of(basic_string(), ml_basic_string(), literal_string(), ml_literal_string())

# Base non-container values
base_value = st.one_of(
    string_value,
    integer_value,
    float_str(),
    bool_str,
    date_time_str()
)

# Now build recursive container values (arrays and inline tables), using st.recursive
def array_builder(inner):
    # arrays may contain values and allow trailing comma; allow empty arrays
    # also allow comments between elements (we will represent comments inline like '#c')
    list_of_values = st.lists(inner, min_size=0, max_size=6)
    @st.composite
    def build(draw):
        items = draw(list_of_values)
        # Optionally interleave comments/newlines between entries
        def maybe_comment():
            if draw(st.booleans()):
                # comment may include raw control characters (except NUL)
                c = draw(st.text(alphabet=_non_nul_char, min_size=0, max_size=30))
                return ' #'+c
            return ''
        pieces = []
        for v in items:
            pieces.append(v + maybe_comment())
        # allow trailing comma
        joiner = ', '
        s = '[' + (joiner.join(pieces))
        if len(pieces) > 0 and draw(st.booleans()):
            s += ','
        s += ']'
        return s
    return build()

def inline_table_wellformed(inner):
    # inline tables should not contain newlines; pick values without newline to be well-formed
    inner_no_nl = inner.filter(lambda s: '\n' not in s)
    @st.composite
    def build(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        pairs = []
        for _ in range(n):
            k = draw(st.one_of(_unquoted_key, quoted_basic_key(), quoted_literal_key()))
            v = draw(inner_no_nl)
            pairs.append(f"{k} = {v}")
        s = '{' + ', '.join(pairs)
        # allow trailing comma
        if draw(st.booleans()) and len(pairs) > 0:
            s += ','
        s += '}'
        return s
    return build()

def inline_table_malformed(inner):
    # inline table that may include newlines (which the parser rejects) to exercise that codepath
    @st.composite
    def build(draw):
        n = draw(st.integers(min_value=1, max_value=4))
        pairs = []
        for _ in range(n):
            k = draw(st.one_of(_unquoted_key, quoted_basic_key(), quoted_literal_key()))
            v = draw(inner)
            pairs.append(f"{k} = {v}")
        # insert a newline inside to make it malformed or sometimes keep single-line
        if draw(st.booleans()):
            content = ',\n'.join(pairs)
        else:
            content = ', '.join(pairs)
        if draw(st.booleans()):
            content += ','
        return '{' + content + '}'
    return build()

def recursive_extender(inner):
    return st.one_of(
        array_builder(inner),
        inline_table_wellformed(inner),
        inline_table_malformed(inner)
    )

# Compose the recursive value strategy with a high max_leaves to allow deep nesting
value = st.recursive(base_value, recursive_extender, max_leaves=2048)

# Key-value line
@st.composite
def key_value_line(draw):
    k = draw(key)
    v = draw(value)
    # spacing variations
    left_space = draw(st.sampled_from(['', ' ', '  ']))
    right_space = draw(st.sampled_from(['', ' ', '  ']))
    eq = '='
    line = f"{k}{left_space}{eq}{right_space}{v}"
    # optional inline comment
    if draw(st.booleans()):
        c = draw(st.text(alphabet=_non_nul_char, min_size=0, max_size=60))
        line += ' #' + c
    return line

# Table header (standard and array-of-tables)
@st.composite
def table_header(draw):
    k = draw(key)
    if draw(st.booleans()):
        return f"[{k}]"
    else:
        return f"[[{k}]]"

# Comment-only line
@st.composite
def comment_line(draw):
    c = draw(st.text(alphabet=_non_nul_char, min_size=0, max_size=80))
    # include raw control characters in comments too (allowed by parser)
    return '#' + c

# Expression: key_value, table, or comment
expression = st.one_of(key_value_line(), table_header(), comment_line())

# Document: zero or more expressions separated by NL; include CRLF sometimes; may have no trailing newline
@st.composite
def document(draw):
    count = draw(st.integers(min_value=0, max_value=25))
    lines = [draw(expression) for _ in range(count)]
    # Optionally include blank lines and CRLF in random positions
    for i in range(draw(st.integers(min_value=0, max_value=max(0, count)))):
        if lines:
            idx = draw(st.integers(min_value=0, max_value=len(lines)-1))
            if draw(st.booleans()):
                lines.insert(idx, '')
            else:
                # turn line into CRLF variant
                lines[idx] = lines[idx]  # actual newline handling below
    # join using '\n' and sometimes include '\r\n' randomly
    sep = draw(st.sampled_from(['\n', '\r\n']))
    doc = sep.join(lines)
    # optionally no trailing newline, or ensure trailing newline
    if draw(st.booleans()):
        # ensure trailing newline
        doc = doc + sep
    # Possibly mutate the document to create near-valid-but-malformed inputs (small probability)
    if draw(st.booleans()):
        mutation = draw(st.sampled_from(['missing_delim', 'doubled_delim', 'unterminated_string', 'stray_token', 'none']))
        if mutation == 'missing_delim':
            # Remove one bracket from a random table header if present
            doc = doc.replace('[[', '[', 1)
            doc = doc.replace(']]', ']', 1)
        elif mutation == 'doubled_delim':
            doc = doc.replace(']', ']]', 1)
        elif mutation == 'unterminated_string':
            # remove a closing quote from a basic string somewhere if present, else append an unterminated string
            if '"' in doc:
                doc = doc.replace('"', '', 1)  # remove first quote to unterminate
            else:
                doc += '\n' + 'a = "'  # unterminated
        elif mutation == 'stray_token':
            # insert a stray token in random place
            insert_at = draw(st.integers(min_value=0, max_value=len(doc)))
            doc = doc[:insert_at] + ' ?? ' + doc[insert_at:]
        # 'none' does nothing
    return doc

# Top-level strategy name required by the harness
strategy = document()
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 74.29,
  "region_coverage_pct": 75.55
}

Make EXACTLY ONE change to the strategy: **revert_last_edit** — score 65.6 < best 74.3.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.