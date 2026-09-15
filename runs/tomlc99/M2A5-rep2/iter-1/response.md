```python
from hypothesis import strategies as st
import json

# Helper pieces

# Characters allowed inside various string forms (avoid NUL '\x00'; allow control bytes except newline/CR)
raw_basic_char = st.characters(
    blacklist_characters='\x00"\n\r\\',
    min_codepoint=0x01,
    max_codepoint=0x10FFFF,
)
# Allow explicit low-control raw characters (except NUL and newline) for "raw control inside basic string"
raw_control_char = st.characters(
    min_codepoint=1,
    max_codepoint=0x1F,
    blacklist_characters='\x00\n\r',
)
# Escape sequences examples (valid and some invalid to create near-malformed inputs)
escape_seq_examples = [
    r'\n', r'\t', r'\r', r'\"', r'\\', r'\/', r'\b', r'\f',
    r'\u0000', r'\u00A9', r'\u2603', r'\U0001F600', r'\U0010FFFF',
    r'\q'  # invalid escape to provoke near-malformed strings
]
escape_seq = st.sampled_from(escape_seq_examples)

# Build inner content for basic strings mixing raw chars and escape sequences
basic_inner_piece = st.one_of(raw_basic_char.map(lambda c: c), raw_control_char.map(lambda c: c), escape_seq)
basic_inner = st.lists(basic_inner_piece, min_size=0, max_size=30).map(''.join)

# Basic (double-quoted) string variants: valid, unterminated, doubled delimiter (extra quote at start or end)
basic_string_valid = basic_inner.map(lambda s: f'"{s}"')
basic_string_unterminated = basic_inner.map(lambda s: f'"{s}')  # missing closing quote
basic_string_doubled_start = basic_inner.map(lambda s: f'""{s}"')  # doubled starting quotes (near-malformed)
basic_string_doubled_end = basic_inner.map(lambda s: f'"{s}""')  # doubled ending quotes

basic_string = st.one_of(
    basic_string_valid,
    basic_string_unterminated,
    basic_string_doubled_start,
    basic_string_doubled_end,
)

# Literal strings (single-quoted) - no escapes interpreted; sometimes unterminated
literal_inner = st.text(st.characters(blacklist_characters="\x00'\n\r", min_codepoint=0x01, max_codepoint=0x10FFFF), min_size=0, max_size=30)
literal_string = st.one_of(
    literal_inner.map(lambda s: f"'{s}'"),
    literal_inner.map(lambda s: f"'{s}")  # unterminated
)

# Multiline basic string triple quotes. Allow embedded newlines, raw control, and escapes.
ml_basic_piece = st.one_of(
    st.characters(blacklist_characters='\x00', min_codepoint=1, max_codepoint=0x10FFFF).map(lambda c: c),
    escape_seq
)
ml_basic_inner = st.lists(ml_basic_piece, min_size=0, max_size=200).map(''.join)
ml_basic_string = st.one_of(
    ml_basic_inner.map(lambda s: f'"""{s}"""'),
    # unterminated multiline
    ml_basic_inner.map(lambda s: f'"""{s}'),
    # doubled delimiter near-malformed
    ml_basic_inner.map(lambda s: f'""""{s}"""'),
)

# Multiline literal string triple single quotes
ml_literal_inner = st.lists(st.characters(blacklist_characters="\x00", min_codepoint=1, max_codepoint=0x10FFFF), min_size=0, max_size=200).map(''.join')
ml_literal_string = st.one_of(
    ml_literal_inner.map(lambda s: f"'''{s}'''"),
    ml_literal_inner.map(lambda s: f"'''{s}"),  # unterminated
)

# Combined string value strategy covering all four forms
string_value = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Integers: decimal (allow leading zeros), hex, oct, bin; include underscores and signs and extremes
def dec_int_builder(sign, digits):
    return (('-' if sign < 0 else '+') if sign != 0 else '') + digits

dec_digits = st.one_of(
    # single zero or leading zero sequence
    st.sampled_from(['0', '007', '0001', '00']),
    # normal digits with underscores
    st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=30).map(''.join).map(
        lambda s: s if '_' not in s else s  # keep as-is
    ),
    # grouped with underscores
    st.builds(lambda groups: '_'.join(groups),
        st.lists(st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=4), min_size=1, max_size=8))
)

decimal_integer = st.tuples(st.integers(min_value=-1, max_value=1), dec_digits).map(
    lambda p: dec_int_builder(p[0], p[1])
)

hex_digits_piece = st.sampled_from(list('0123456789abcdefABCDEF'))
hex_digits = st.lists(hex_digits_piece, min_size=1, max_size=16).map(''.join)
hex_integer = hex_digits.map(lambda s: '0x' + s)

oct_digits_piece = st.sampled_from(list('01234567'))
oct_digits = st.lists(oct_digits_piece, min_size=1, max_size=22).map(''.join)
oct_integer = oct_digits.map(lambda s: '0o' + s)

bin_digits_piece = st.sampled_from(list('01'))
bin_digits = st.lists(bin_digits_piece, min_size=1, max_size=64).map(''.join')
bin_integer = bin_digits.map(lambda s: '0b' + s)

integer_value = st.one_of(decimal_integer, hex_integer, oct_integer, bin_integer)

# Floating point values: forms like 1.0, 1., .5, exponent, inf, nan
float_frac = st.builds(
    lambda a, b: a + '.' + b,
    st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=10),
    st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=0, max_size=10)
)
float_leading_dot = st.builds(lambda b: '.' + b, st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=10))
float_trailing_dot = st.builds(lambda a: a + '.', st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=10))
float_exp = st.builds(lambda base, exp: base + ('e' + exp if exp else ''), st.one_of(float_frac, float_leading_dot, float_trailing_dot, st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=10)), st.one_of(
    st.just('1'), st.just('-1'), st.just('309'), st.just('10000')
))
inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
float_value = st.one_of(float_frac, float_leading_dot, float_trailing_dot, float_exp, inf_nan)

# Booleans
bool_value = st.sampled_from(['true', 'false'])

# Date-time forms: local date, local time, local datetime, offset datetime (space or T)
def simple_number(n):
    return st.integers(min_value=0, max_value=9).map(str)  # single digit
year = st.integers(min_value=0, max_value=9999).map(lambda y: f"{y:04d}")
month = st.integers(min_value=1, max_value=12).map(lambda m: f"{m:02d}")
day = st.integers(min_value=1, max_value=31).map(lambda d: f"{d:02d}")
hour = st.integers(min_value=0, max_value=23).map(lambda h: f"{h:02d}")
minute = st.integers(min_value=0, max_value=59).map(lambda m: f"{m:02d}")
second = st.integers(min_value=0, max_value=59).map(lambda s: f"{s:02d}")
secfrac = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=6)))
offset = st.one_of(st.just('Z'), st.builds(lambda s: s, st.sampled_from(['+00:00', '-05:00', '+14:00', '+00:30'])))
date_sep = st.sampled_from(['T', 't', ' '])

local_date = st.tuples(year, month, day).map(lambda p: f"{p[0]}-{p[1]}-{p[2]}")
local_time = st.tuples(hour, minute, second, secfrac).map(lambda p: f"{p[0]}:{p[1]}:{p[2]}{p[3]}")
local_datetime = st.tuples(local_date, date_sep, local_time).map(lambda p: f"{p[0]}{p[1]}{p[2]}")
offset_datetime = st.tuples(local_date, date_sep, local_time, offset).map(lambda p: f"{p[0]}{p[1]}{p[2]}{p[3]}")

datetime_value = st.one_of(offset_datetime, local_datetime, local_date, local_time)

# Key strategies: unquoted keys and quoted keys. Bare keys must be ASCII; quoted keys can be any string forms
unquoted_key = st.text(st.characters(whitelist_categories=('Ll','Lu','Nd'), blacklist_characters='\x00', min_codepoint=48, max_codepoint=122), min_size=1, max_size=50).filter(lambda s: all(ch.isascii() for ch in s) and all(c.isalnum() or c in '-_' for c in s))
quoted_key_basic = basic_inner.map(lambda s: f'"{s}"')
quoted_key_literal = literal_inner.map(lambda s: f"'{s}'")
key_token = st.one_of(unquoted_key, quoted_key_basic, quoted_key_literal)

# Inline table building (recursive)
# We'll use a deferred strategy for values so arrays and inline tables can nest.
def make_inline_table_strategy(value_strat):
    # Key=Value pairs, allow duplicates and optional trailing comma, optionally include a newline (which would be invalid)
    kv = st.tuples(key_token, value_strat).map(lambda p: f"{p[0]} = {p[1]}")
    kv_list = st.lists(kv, min_size=0, max_size=8)
    trailing_comma = st.booleans().map(lambda b: ',' if b else '')
    # Optionally insert a literal newline inside (to create near-malformed cases), with small probability
    def assemble(kvs_and_comma):
        kvs, comma, include_nl = kvs_and_comma
        inner = ','.join(kvs)
        if inner and include_nl:
            # insert newline inside inline table to provoke invalid inline table (parser rejects newline inside inline table)
            inner = inner.replace(',', ',\n', 1)
        if inner and comma:
            inner = inner + comma
        return '{' + inner + '}'
    return st.tuples(kv_list, trailing_comma, st.sampled_from([False] * 9 + [True])).map(assemble)

# Array building: bracketed arrays, allow nested arrays and inline tables; allow trailing commas and comments/newlines inside
def make_array_strategy(value_strat):
    # array elements can be separated by commas, allow trailing comma, allow comments/newlines tokens inserted
    elem = value_strat
    elems = st.lists(elem, min_size=0, max_size=8)
    trailing_comma = st.booleans().map(lambda b: ',' if b else '')
    # allow stray tokens (like extra comma or bracket) to create near-malformed arrays with small probability
    def assemble(parts):
        elements, comma, stray = parts
        inner = ', '.join(elements)
        if comma:
            inner = inner + comma
        if stray:
            inner = inner + ' ]'  # stray token
        return '[' + inner + ']'
    return st.tuples(elems, trailing_comma, st.sampled_from([False] * 9 + [True])).map(assemble)

# Build a deferred recursive value strategy
# Base values: string_value, integer_value, float_value, bool_value, datetime_value
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    datetime_value
)

# Use st.recursive to allow arrays and inline tables to nest. Limit max_leaves to permit deep nesting (Hypothesis controls size)
def expand_children(inner):
    inline_table_s = make_inline_table_strategy(inner)
    array_s = make_array_strategy(inner)
    # Also allow mixed-type arrays represented as lines starting with stray token sometimes
    return st.one_of(inline_table_s, array_s)

value = st.recursive(base_value, expand_children, max_leaves=100)

# Key-value line generation
def key_value_line():
    # sometimes produce duplicate keys by sampling same key twice in the doc builder
    return st.tuples(key_token, value).map(lambda p: f"{p[0]} = {p[1]}")

kv_line = key_value_line()

# Table header lines and array-table headers
table_header = key_token.map(lambda k: f"[{k}]")
array_table_header = key_token.map(lambda k: f"[[{k}]]")

# Comment line
comment_line = st.one_of(st.just(''), st.builds(lambda s: f"# {s}", st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters='\x00'), min_size=0, max_size=60))))

# Expression line: could be key_value, table header, array table header, or comment
expression_line = st.one_of(kv_line, table_header, array_table_header, comment_line)

# Document: sequence of expressions separated by newlines, possibly no trailing newline (documents with no trailing newline allowed)
# Include also empty document and comment-only doc
def assemble_document(lines_and_end):
    lines, end_nl = lines_and_end
    doc = '\n'.join(lines)
    if end_nl:
        doc = doc + '\n'
    return doc

document = st.tuples(st.lists(expression_line, min_size=0, max_size=40), st.booleans()).map(assemble_document)

# To intentionally include some deep nesting cases in arrays and inline tables, create a special deep-nesting generator
def deep_nested_array(depth):
    # Build a nested array like [[[[... 0 ...]]]] with '0' at innermost to keep length reasonable
    # depth up to ~2048 allowed per parser; choose occasionally high depths
    if depth <= 0:
        return '0'
    inner = deep_nested_array(depth - 1)
    return '[' + inner + ']'

deep_nested_array_strategy = st.integers(min_value=0, max_value=2048).map(lambda d: deep_nested_array(d)).map(lambda s: f"deep = {s}")

# Sometimes put a massive integer or float (extreme magnitude/exponent)
extreme_number = st.sampled_from([
    "bigint = 1234567890123456789012345678901234567890",
    "hugeexp = 1e309",
    "tiny = 1e-9999",
    "underscore = 1_000_000_000_000_000_000_000",
    "leadingzero = 007",
    "hexbig = 0x" + ("F" * 200)
])

# Combine document and occasional deep or extreme snippets to form the final strategy
final_doc = st.one_of(
    document,
    st.lists(expression_line, min_size=0, max_size=10).map(lambda lst: '\n'.join(lst)),  # shorter form
    deep_nested_array_strategy,
    extreme_number
)

# The top-level exported strategy must be a SearchStrategy producing str values
strategy = final_doc
```