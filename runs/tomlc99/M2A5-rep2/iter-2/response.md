```python
from hypothesis import strategies as st
import json

# Top-level strategy must be named `strategy` and produce str (TOML document).
# We build many small strategies and combine them. We avoid embedding raw NUL (\x00).
# We deliberately include edge cases: empty containers, deep nesting, duplicate keys,
# extreme numbers, escapes, non-ASCII, control bytes (except NUL), and near-malformed pieces.

# Allowed characters for unquoted keys: ASCII letters, digits, '-' and '_'
_unquoted_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
_unquoted_key = st.text(alphabet=_unquoted_key_chars, min_size=1, max_size=20)

# Control characters to include inside strings (exclude NUL '\x00').
_control_chars = ''.join(chr(i) for i in range(1, 32) if i != 0)

# Helper to create escape sequences inside basic strings
_escape_sequences = [
    '\\\\', '\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
    # Unicode escapes (short and long)
    lambda: '\\u%04x' % st.integers(min_value=0, max_value=0xFFFF).example(),
    lambda: '\\U%08x' % st.integers(min_value=0, max_value=0x10FFFF).example(),
]

# Strategy for pieces of content to be used inside basic strings.
_basic_string_content_fragment = st.one_of(
    # raw printable Unicode (no NUL)
    st.text(alphabet=st.characters(blacklist_characters=['\x00', '"', '\\']), min_size=0, max_size=12),
    # inject control characters raw
    st.text(alphabet=_control_chars, min_size=1, max_size=4),
    # backslash escapes as two-character sequences
    st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\"', '\\\\', '\\/']),
    # Unicode escapes
    st.builds(lambda u: '\\u%04x' % u, st.integers(min_value=0, max_value=0xFFFF)),
    st.builds(lambda U: '\\U%08x' % U, st.integers(min_value=0, max_value=0x10FFFF)),
)

@st.composite
def basic_string(draw, allow_unescaped_control=True):
    # Build a BASIC_STRING: " ... "
    parts = draw(st.lists(_basic_string_content_fragment, min_size=0, max_size=6))
    content = ''.join(parts)
    # Ensure quotes and backslashes are escaped
    content = content.replace('\\', '\\\\').replace('"', '\\"')
    # Occasionally inject raw control characters (parser accepts them)
    if allow_unescaped_control and draw(st.booleans()): 
        ctrl = draw(st.text(alphabet=_control_chars, min_size=1, max_size=3))
        insert_at = draw(st.integers(min_value=0, max_value=len(content)))
        content = content[:insert_at] + ctrl + content[insert_at:]
    # Occasionally include a \u0000 escape (six-character text) but not raw NUL
    if draw(st.booleans()):
        u0000 = '\\u0000'
        content = content + u0000
    return '"' + content + '"'

@st.composite
def literal_string(draw):
    # LITERAL_STRING: single-quoted, no escapes
    # Allow embedding any characters except single quote and newline inside single-line literal
    content = draw(st.text(alphabet=st.characters(blacklist_characters=['\x00', '\n', '\r', "'"]), min_size=0, max_size=20))
    # Occasionally include non-ASCII characters (bare keys reject non-ASCII, but strings accept)
    if draw(st.booleans()):
        content += draw(st.text(min_size=0, max_size=5))
    return "'" + content + "'"

@st.composite
def ml_basic_string(draw):
    # Multiline basic: triple-quoted, content may include escapes and newlines.
    # Avoid producing actual unclosed triple-quote in >95% cases; small chance to produce unterminated string.
    content = draw(st.text(min_size=0, max_size=60))
    # Replace any occurrence of triple-quote with safe variant to avoid accidental termination
    content = content.replace('"""', '\\"""')
    if draw(st.booleans()):  # inject some escapes
        content = content + '\\n' + draw(st.text(min_size=0, max_size=10))
    terminated = draw(st.booleans() if draw(st.integers(min_value=1, max_value=50)) > 1 else st.just(False))
    if terminated:
        return '"""' + content + '"""'
    else:
        # Small chance of unterminated multiline string (near-malformed)
        return '"""' + content  # no closing quotes

@st.composite
def ml_literal_string(draw):
    # Multiline literal: triple single-quotes
    content = draw(st.text(min_size=0, max_size=60))
    content = content.replace("'''", "'''")  # keep but if occurs rare
    terminated = draw(st.booleans() if draw(st.integers(min_value=1, max_value=50)) > 1 else st.just(False))
    if terminated:
        return "'''" + content + "'''"
    else:
        return "'''" + content  # unterminated rare

# Key strategies
@st.composite
def quoted_key(draw):
    # Either basic or literal quoted key
    choice = draw(st.sampled_from(['basic', 'literal']))
    if choice == 'basic':
        return draw(basic_string())
    else:
        return draw(literal_string())

key_simple_unquoted = _unquoted_key.map(lambda s: s)
key_simple_quoted = quoted_key()
key_simple = st.one_of(key_simple_unquoted, key_simple_quoted)

@st.composite
def dotted_key(draw):
    # simple_key (DOT simple_key)+
    first = draw(key_simple)
    rest_count = draw(st.integers(min_value=1, max_value=4))
    rest = [draw(key_simple) for _ in range(rest_count)]
    return '.'.join([first] + rest)

key_any = st.one_of(dotted_key(), key_simple)

# Boolean
bool_strat = st.sampled_from(['true', 'false'])

# Integers: DEC_INT, HEX_INT, OCT_INT, BIN_INT
@st.composite
def decimal_integer(draw):
    sign = draw(st.sampled_from(['', '+', '-']))
    # allow leading zeros occasionally
    if draw(st.booleans()):
        # potentially extreme magnitude
        digits = draw(st.text(alphabet='0123456789', min_size=1, max_size=120))
    else:
        # normal-ish with underscores
        n = draw(st.integers(min_value=1, max_value=20))
        groups = []
        for _ in range(n):
            groups.append(draw(st.text(alphabet='0123456789', min_size=1, max_size=4)))
        digits = '_'.join(groups)
    # occasionally insert leading zeros like 007
    if draw(st.booleans()):
        digits = draw(st.text(alphabet='0123456789', min_size=1, max_size=3)) + digits
    return sign + digits

@st.composite
def hex_integer(draw):
    sign = draw(st.sampled_from(['', '+', '-']))
    body = draw(st.text(alphabet='0123456789abcdefABCDEF', min_size=1, max_size=40))
    # add underscores occasionally
    if draw(st.booleans()):
        body = '_'.join([body[i:i+2] for i in range(0, len(body), 2)])
    return sign + '0x' + body

@st.composite
def oct_integer(draw):
    sign = draw(st.sampled_from(['', '+', '-']))
    body = draw(st.text(alphabet='01234567', min_size=1, max_size=40))
    if draw(st.booleans()):
        body = '_'.join([body[i:i+3] for i in range(0, len(body), 3)])
    return sign + '0o' + body

@st.composite
def bin_integer(draw):
    sign = draw(st.sampled_from(['', '+', '-']))
    body = draw(st.text(alphabet='01', min_size=1, max_size=64))
    if draw(st.booleans()):
        body = '_'.join([body[i:i+4] for i in range(0, len(body), 4)])
    return sign + '0b' + body

integer_strat = st.one_of(decimal_integer(), hex_integer(), oct_integer(), bin_integer())

# Floats: FLOAT, INF, NAN
@st.composite
def float_normal(draw):
    sign = draw(st.sampled_from(['', '+', '-']))
    # variants: 1.0, 1., .5, 1e10, 1.2e-5, 1_000.5
    variant = draw(st.sampled_from(['frac', 'trailingdot', 'leadingdot', 'exp', 'underscore']))
    if variant == 'frac':
        intpart = draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        frac = draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        s = intpart + '.' + frac
    elif variant == 'trailingdot':
        intpart = draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        s = intpart + '.'
    elif variant == 'leadingdot':
        frac = draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        s = '.' + frac
    elif variant == 'exp':
        intpart = draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        exp = draw(st.integers(min_value=-400, max_value=400))
        s = intpart + 'e' + str(exp)
    else:
        intpart = draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        frac = draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        intpart = intpart + '_' + draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
        s = intpart + '.' + frac
    return sign + s

float_inf_nan = st.one_of(st.sampled_from(['inf', '-inf', '+inf', 'nan', '-nan', '+nan']))
float_strat = st.one_of(float_normal(), float_inf_nan)

# Date/time strings (OFFSET_DATE_TIME, LOCAL_DATE_TIME, LOCAL_DATE, LOCAL_TIME)
@st.composite
def date_time(draw):
    # Generate calendar-invalid dates sometimes; allowed by parser.
    year = draw(st.integers(min_value=0, max_value=9999)).__format__('04d')
    month = draw(st.integers(min_value=1, max_value=12)).__format__('02d')
    day = draw(st.integers(min_value=1, max_value=31)).__format__('02d')
    hour = draw(st.integers(min_value=0, max_value=23)).__format__('02d')
    minute = draw(st.integers(min_value=0, max_value=59)).__format__('02d')
    second = draw(st.integers(min_value=0, max_value=59)).__format__('02d')
    # optional fractional
    frac = ''
    if draw(st.booleans()):
        frac = '.' + draw(st.integers(min_value=0, max_value=10)).__str__().zfill(1)
        # or produce longer fractional
        if draw(st.booleans()):
            frac = '.' + draw(st.text(alphabet='0123456789', min_size=1, max_size=9))
    sep = draw(st.sampled_from(['T', ' ', 't']))
    # choose form
    form = draw(st.sampled_from(['offset', 'local_dt', 'local_date', 'local_time']))
    if form == 'offset':
        # timezone
        offset = draw(st.one_of(st.just('Z'), st.builds(lambda s,m: ('+' if draw_sign else '-') + s + ':' + m,
                                                       st.integers(min_value=0, max_value=23).__format__ if False else st.just('00'),
                                                       st.just('00'))))  # fallback, simpler
        # simpler construction for offset
        if draw(st.booleans()):
            tz = 'Z'
        else:
            tz_sign = draw(st.sampled_from(['+', '-']))
            tz_h = draw(st.integers(min_value=0, max_value=23)).__format__('02d')
            tz_m = draw(st.integers(min_value=0, max_value=59)).__format__('02d')
            tz = tz_sign + tz_h + ':' + tz_m
        return f"{year}-{month}-{day}{sep}{hour}:{minute}:{second}{frac}{tz}"
    elif form == 'local_dt':
        return f"{year}-{month}-{day}{sep}{hour}:{minute}:{second}{frac}"
    elif form == 'local_date':
        return f"{year}-{month}-{day}"
    else:
        return f"{hour}:{minute}:{second}{frac}"

# Simple (non-container) values
simple_value = st.one_of(
    basic_string(), literal_string(), ml_basic_string(), ml_literal_string(),
    integer_strat, float_strat, bool_strat, date_time()
)

# Recursive construction for arrays and inline tables
def array_of(element_strategy):
    # elements may be separated by commas, comments/newlines; allow empty arrays and trailing comma
    @st.composite
    def _arr(draw):
        # decide empty vs filled
        if draw(st.booleans()):
            elems = draw(st.lists(element_strategy, min_size=0, max_size=5))
        else:
            elems = draw(st.lists(element_strategy, min_size=0, max_size=8))
        # optionally inject comments/newlines between elements
        parts = []
        for e in elems:
            # small chance to add comment or newline before element
            if draw(st.booleans()):
                if draw(st.booleans()):
                    parts.append('#'+draw(st.text(min_size=0, max_size=20)))
                    parts.append('\n')
                else:
                    parts.append('\n')
            parts.append(e)
        # join with commas, occasionally produce double comma (near-malformed)
        if parts:
            if draw(st.integers(min_value=1, max_value=20)) == 1:
                body = ','.join(parts)  # compact
            else:
                body = ', '.join(parts)
            # trailing comma sometimes
            if draw(st.booleans()):
                body = body + ','
        else:
            body = ''
        # Optionally create deeply nested bracket form by wrapping multiple brackets (rare)
        if draw(st.integers(min_value=1, max_value=200)) > 195:
            depth = draw(st.integers(min_value=50, max_value=1200))
            # create nested arrays like [[[ ... ]]]
            inner = body
            for _ in range(depth):
                inner = '[' + inner + ']'
            return inner
        return '[' + body + ']'
    return _arr()

def inline_table_of(value_strategy):
    @st.composite
    def _it(draw):
        # inline tables cannot contain newlines per parser; keep single-line
        kvs = []
        # empty inline table occasionally
        count = draw(st.integers(min_value=0, max_value=4))
        for _ in range(count):
            k = draw(st.one_of(key_simple_unquoted, key_simple_quoted))
            v = draw(value_strategy)
            kvs.append(f"{k} = {v}")
        body = ', '.join(kvs)
        # allow trailing comma (parser accepts)
        if draw(st.booleans()) and body:
            body = body + ','
        # near-malformed: sometimes include a newline inside inline table (parser rejects)
        if draw(st.integers(min_value=1, max_value=50)) == 1 and body:
            body = body.replace(', ', ',\n')
        return '{' + body + '}'
    return _it()

# Build recursive value strategy that allows arrays and inline tables
# Use st.recursive to ensure proper recursion control
value_rec = st.recursive(
    simple_value,
    lambda children: st.one_of(array_of(children), inline_table_of(children)),
    max_leaves=200,
)

# Key-value line
@st.composite
def key_value_line(draw, allow_duplicate=False):
    k = draw(key_any)
    # Occasionally produce dotted key with quoted parts
    v = draw(value_rec)
    # Occasionally insert stray token or doubled delimiter near-malformed
    if draw(st.integers(min_value=1, max_value=40)) == 1:
        # insert stray token after equals
        return f"{k} = {v} ???"
    if draw(st.integers(min_value=1, max_value=80)) == 1:
        # doubled equals
        return f"{k} == {v}"
    return f"{k} = {v}"

# Table header and array table header
@st.composite
def table_header(draw):
    k = draw(key_any)
    # sometimes produce extra whitespace, CRLF, or stray tokens
    newline = draw(st.sampled_from(['\n', '\r\n']))
    header = f"[{k}]"
    if draw(st.integers(min_value=1, max_value=40)) == 1:
        header = header + ' ' + draw(st.text(min_size=1, max_size=5))
    return header

@st.composite
def array_table_header(draw):
    k = draw(key_any)
    return f"[[{k}]]"

# Comment or blank line
comment_line = st.one_of(
    st.just(''),  # blank line
    st.builds(lambda c: '#' + c, st.text(min_size=0, max_size=40))
)

# Document: a sequence of expressions (key_value, table, array_table, or comment)
@st.composite
def document_strategy(draw):
    parts = []
    # Possibly produce empty document
    if draw(st.booleans()):
        # produce comment-only or empty
        if draw(st.integers(min_value=1, max_value=10)) == 1:
            return ''
    # Choose number of expressions
    n = draw(st.integers(min_value=0, max_value=30))
    # Keep track of keys to sometimes deliberately duplicate (to exercise duplicate-key behavior)
    seen_keys = []
    for i in range(n):
        kind = draw(st.sampled_from(['kv', 'table', 'array_table', 'comment']))
        if kind == 'kv':
            # sometimes intentionally duplicate key by reusing one from seen_keys
            if seen_keys and draw(st.integers(min_value=1, max_value=20)) == 1:
                k = draw(st.sampled_from(seen_keys))
                # produce a value and duplicate key verbatim
                v = draw(value_rec)
                parts.append(f"{k} = {v}")
            else:
                line = draw(key_value_line())
                # parse out key if simple for tracking duplicates
                # naive extraction: up to first '='
                if '=' in line:
                    kpart = line.split('=', 1)[0].strip()
                    seen_keys.append(kpart)
                parts.append(line)
        elif kind == 'table':
            parts.append(draw(table_header()))
        elif kind == 'array_table':
            parts.append(draw(array_table_header()))
        else:
            parts.append(draw(comment_line))
    # Optionally append a stray token at document end (near-malformed)
    if draw(st.integers(min_value=1, max_value=40)) == 1:
        parts.append('???')
    # Join parts with newlines; choose line ending style randomly, include no trailing newline sometimes
    sep = draw(st.sampled_from(['\n', '\r\n']))
    doc = sep.join(parts)
    # Occasionally ensure document has no trailing newline (allowed)
    if draw(st.booleans()):
        return doc
    else:
        return doc + sep

# Provide top-level strategy
strategy = document_strategy()
```