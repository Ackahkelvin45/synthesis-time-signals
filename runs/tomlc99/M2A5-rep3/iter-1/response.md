```python
from hypothesis import strategies as st
import json

# Characters excluding NUL (avoid raw NUL bytes), but allow other control bytes
_non_nul_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters=['\x00'])

# Simple ASCII alphabet for unquoted bare keys (parser rejects non-ASCII bare keys)
_ASCII_KEY_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

# Basic building blocks

unquoted_key = st.text(alphabet=_ASCII_KEY_ALPHABET, min_size=1, max_size=40)

# Small helper to produce escape sequences as textual sequences (\\n etc.)
_escape_tokens = st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\\', '\\"', '\\/', '\\u0041', '\\U00000041'])

# BASIC_STRING generator: avoid unescaped newlines and unescaped quotes/backslashes
basic_string_content = st.text(
    alphabet=st.characters(blacklist_characters=['"', '\\', '\n', '\x00']),
    min_size=0,
    max_size=60
)

basic_string = st.one_of(
    # generated content without escapes
    basic_string_content.map(lambda s: '"' + s + '"'),
    # content built from fragments and explicit escape tokens
    st.lists(st.one_of(
        st.text(alphabet=st.characters(blacklist_characters=['"', '\n', '\x00']), min_size=1, max_size=10),
        _escape_tokens,
        # include raw control characters (but not NUL)
        st.characters(min_codepoint=1, max_codepoint=0x1F, blacklist_characters=['\x00']).map(lambda c: c)
    ), min_size=0, max_size=10).map(lambda parts: '"' + ''.join(parts) + '"'),
    # raw control example explicitly (accepted by the parser)
    st.just('"x\x01y"'),
    # explicit common escape sequences
    st.just('"\\n\\t\\u03B1"'),
    # empty quoted string
    st.just('""'),
    # malformed: unterminated string (no closing quote)
    st.sampled_from(['"unterminated', '"bad\\q', '"""unterminated_ml'])
)

# MULTILINE basic string (""" ... """), allow newlines inside
ml_basic_string = st.one_of(
    st.text(alphabet=st.characters(blacklist_characters=['\x00']), min_size=0, max_size=200).map(lambda s: '"""' + s + '"""'),
    # include explicit escapes and newlines
    st.just('"""line1\nline2\n\\nend"""'),
    # malformed: no ending triple quote
    st.just('"""no_end'),
)

# LITERAL and ML literal strings (single quotes; no escape processing)
literal_string = st.one_of(
    st.text(alphabet=st.characters(blacklist_characters=["'", '\n', '\x00']), min_size=0, max_size=60).map(lambda s: "'" + s + "'"),
    st.text(alphabet=st.characters(blacklist_characters=['\x00']), min_size=0, max_size=200).map(lambda s: "'''" + s + "'''"),
    st.just("'''multi\nline literal\n'''"),
    # malformed literal (unterminated)
    st.just("'unterminated_literal"),
)

string_value = st.one_of(basic_string, ml_basic_string, literal_string, st.just('"""odd"""'))


# Integers: decimal (including leading zeros), hex, oct, bin, underscores, extreme lengths
def _with_underscores(s: str):
    # insert underscores at random positions (not at ends)
    if len(s) <= 2:
        return s
    parts = []
    i = 0
    while i < len(s):
        take = 1
        parts.append(s[i:i+take])
        i += take
        # occasionally put underscore
        if i < len(s) and st.booleans().example():
            parts.append('_')
    res = ''.join(parts).strip('_')
    return res or s

decimal_int = st.integers(min_value=-10**30, max_value=10**30).map(lambda n: str(n))
# include leading zeros case like 007
leading_zero_int = st.integers(min_value=0, max_value=999).map(lambda n: ('00' + str(n)) if st.booleans().example() else str(n))
# hex/oct/bin
hex_int = st.integers(min_value=0, max_value=2**64).map(lambda n: '0x' + format(n, 'x'))
oct_int = st.integers(min_value=0, max_value=2**64).map(lambda n: '0o' + format(n, 'o'))
bin_int = st.integers(min_value=0, max_value=2**64).map(lambda n: '0b' + format(n, 'b'))
# underscore variants
int_with_underscores = st.integers(min_value=0, max_value=10**20).map(lambda n: _with_underscores(str(n)))

integer_value = st.one_of(
    decimal_int,
    leading_zero_int,
    hex_int,
    oct_int,
    bin_int,
    int_with_underscores,
    # very large integer beyond 64 bits
    st.integers(min_value=10**20, max_value=10**100).map(str),
)

# Floats: include 1., .5, exponent extremes, inf/nan
float_value = st.one_of(
    st.just('1.'),
    st.just('.5'),
    st.floats(min_value=-1e300, max_value=1e300, allow_nan=False, allow_infinity=False).map(lambda f: repr(f)),
    # explicitly create 1e309 (overflow), large exponents, underscores not typical but include
    st.sampled_from(['1e309', '1E309', '-1e309', '1.0e-10000', '3.1415', '6.02e23']),
    st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
)

bool_value = st.sampled_from(['true', 'false'])

# Date/time forms (including calendar-invalid dates)
date_value = st.one_of(
    # offset datetime
    st.sampled_from(['1979-05-27T07:32:00Z', '1979-05-27 07:32:00Z', '1979-02-30T07:32:00Z']),
    # local date-time
    st.sampled_from(['1979-05-27T07:32:00', '1979-05-27 07:32:00']),
    # local date
    st.sampled_from(['1979-05-27', '1979-02-30']),
    # local time
    st.sampled_from(['07:32:00', '23:59:60'])  # leap second-ish / invalid but parser accepts
)

# Comments: optional, generate either empty or "# ..." form
comment_strategy = st.one_of(
    st.just(''),
    st.builds(lambda s: '#' + s, st.text(alphabet=st.characters(blacklist_characters=['\x00']), min_size=0, max_size=80))
)

# Key forms: unquoted or quoted (basic or literal)
quoted_key_basic = basic_string
quoted_key_literal = literal_string

simple_key = st.one_of(unquoted_key, quoted_key_basic, quoted_key_literal)

# Dotted key: join 1-4 simple keys by dots
dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: '.'.join(parts))

# Deferred value strategy to enable recursion for arrays and inline tables
value_strategy = st.deferred()

# Arrays: allow deep nesting via recursion; include optional trailing comma
array_strategy = st.lists(value_strategy, min_size=0, max_size=6).map(
    lambda lst: '[' + (', '.join(lst) if lst else '') + (',' if lst and (st.booleans().example()) else '') + ']'
)

# Inline tables: { key = value, ... } - sometimes include trailing comma, optionally illegally include newline to generate near-invalid input
def _format_inline_table(d):
    # d is list of (k,v) pairs to allow duplicate keys
    if not d:
        return '{}'
    parts = [k + ' = ' + v for (k, v) in d]
    s = '{' + ', '.join(parts)
    if st.booleans().example():
        s += ','
    s += '}'
    # occasionally insert a newline inside inline table (which is disallowed by the parser) to create near-invalid inputs
    if st.booleans().example():
        s = s.replace('{', '{\n', 1)
    return s

@st.composite
def inline_table_builder(draw):
    # keys here must be simple_key textual forms (unquoted or quoted)
    count = draw(st.integers(min_value=0, max_value=6))
    pairs = []
    for _ in range(count):
        k = draw(simple_key)
        v = draw(value_strategy)
        pairs.append((k, v))
    return _format_inline_table(pairs)

# Now define the deferred value strategy including recursion
value_strategy.define(
    st.one_of(
        string_value,
        integer_value,
        float_value,
        bool_value,
        date_value,
        # recursive containers
        array_strategy,
        inline_table_builder(),
        # empty inline table explicitly
        st.just('{}'),
        # empty array
        st.just('[]')
    )
)

# Expression / document builder: produce full documents (list of expressions)
@st.composite
def document_builder(draw):
    # number of expressions (lines). allow 0 for empty document.
    count = draw(st.integers(min_value=0, max_value=12))
    lines = []
    seen_keys = []  # to enable duplicate-key generation
    for _ in range(count):
        kind = draw(st.integers(min_value=0, max_value=6))
        if kind == 0:
            # key_value expression
            # choose whether to reuse a key (duplicate keys) or create a new one
            reuse = False
            if seen_keys and draw(st.booleans()):
                reuse = draw(st.booleans())
            if reuse:
                key = draw(st.sampled_from(seen_keys))
            else:
                key = draw(st.one_of(unquoted_key, quoted_key_basic, quoted_key_literal))
                seen_keys.append(key)
            val = draw(value_strategy)
            # optionally create near-valid-but-malformed variations
            mal_choice = draw(st.integers(min_value=0, max_value=5))
            if mal_choice == 0:
                # proper key = value
                line = key + ' = ' + val
            elif mal_choice == 1:
                # missing equals
                line = key + ' ' + val
            elif mal_choice == 2:
                # double equals
                line = key + ' == ' + val
            elif mal_choice == 3:
                # stray token appended
                line = key + ' = ' + val + ' ]'
            elif mal_choice == 4:
                # a value on next line (unterminated style)
                line = key + ' ='
                # place value on next line to be near-invalid
                line = line + '\n' + val
            else:
                line = key + ' = ' + val
            # maybe append a trailing comment
            if draw(st.booleans()):
                cm = draw(comment_strategy)
                if cm:
                    line = line + ' ' + cm
            lines.append(line)
        elif kind == 1:
            # standard table [key]
            key = draw(dotted_key)
            tbl = '[' + key + ']'
            if draw(st.booleans()):
                tbl = tbl + ' ' + draw(comment_strategy)
            lines.append(tbl)
            seen_keys.append(key)
        elif kind == 2:
            # array of tables [[key]]
            key = draw(dotted_key)
            tbl = '[[' + key + ']]'
            if draw(st.booleans()):
                tbl = tbl + ' ' + draw(comment_strategy)
            lines.append(tbl)
            seen_keys.append(key)
        elif kind == 3:
            # comment-only line
            lines.append(draw(comment_strategy) or '')
        elif kind == 4:
            # stray token line (near-malformed)
            lines.append(draw(st.sampled_from([']', '}', '=', ',,', '[[', ']]', '"""', '[' , '{'])))
        else:
            # blank line
            lines.append('')
    doc = '\n'.join(lines)
    # optionally add a trailing newline or omit it (documents with no trailing newline allowed)
    if draw(st.booleans()):
        doc = doc + '\n'
    # occasionally produce extremely deep nested arrays or inline tables as standalone document
    if draw(st.booleans()):
        if draw(st.booleans()):
            # deep nested arrays like [[[[...]]]] up to a few hundred levels (bounded)
            depth = draw(st.integers(min_value=1, max_value=300))
            inner = draw(st.one_of(string_value, integer_value, st.just('true'), date_value))
            arr = inner
            for _ in range(depth):
                arr = '[' + arr + ']'
            doc = arr if draw(st.booleans()) else (doc + '\n' + arr)
        else:
            # deep inline tables {a={b={...}}}
            depth = draw(st.integers(min_value=1, max_value=300))
            inner_key = 'k'
            inner_value = draw(st.one_of(string_value, integer_value, st.just('true')))
            tbl = inner_key + ' = ' + inner_value
            # build nested inline tables by wrapping
            nested = '{' + tbl + '}'
            for i in range(depth):
                nested = '{a' + str(i) + ' = ' + nested + '}'
            doc = nested if draw(st.booleans()) else (doc + '\n' + nested)
    return doc

# The top-level strategy producing str values (TOML documents)
strategy = document_builder()
```