Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# Helper character pools avoiding NUL (\x00) but allowing other control bytes and lots of unicode
_control_chars = [chr(c) for c in range(1, 0x20) if c != 0]
_sample_unicode = ['é', 'Ω', '漢', '\u2028', '\u00A0']
_printable_chars = st.characters(
    blacklist_characters="\x00",  # never emit raw NUL
    whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po', 'Sc', 'Sm', 'Sk', 'Pc')
)
_char_token = st.one_of(
    _printable_chars,
    st.sampled_from(_control_chars),
    st.sampled_from(_sample_unicode),
    st.sampled_from(['"', "'", '\\', '/', '\n', '\r', '\t'])
)

# Small helpers to build escaped Unicode sequences
_hex4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda x: format(x, '04x'))
_hex8 = st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda x: format(x, '08x'))

# Build inner contents by joining small lists of tokens
_small_text = st.lists(_char_token, min_size=0, max_size=20).map(''.join)
_small_no_nl = st.lists(st.one_of(_printable_chars, st.sampled_from(_control_chars + _sample_unicode)), min_size=0, max_size=20).map(''.join)

# Escaped pieces for basic strings: valid and invalid escapes
_escape_piece = st.one_of(
    st.sampled_from(['\\\\', '\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    _hex4.map(lambda h: '\\u' + h),
    _hex8.map(lambda h: '\\U' + h),
    st.just('\\q')  # intentionally invalid escape sometimes
)

_basic_inner_piece = st.one_of(
    _small_no_nl,
    _escape_piece,
    st.sampled_from(['\t', '\r', '\n', '\x01', '\x02', '\x1b'])  # raw control bytes allowed by parser
)

_basic_inner = st.lists(_basic_inner_piece, min_size=0, max_size=8).map(''.join)

# Basic quoted string
basic_string = st.one_of(
    _basic_inner.map(lambda s: f'"{s}"'),
    # unterminated
    _basic_inner.map(lambda s: f'"{s}'),
    # include possibility of raw closing-quote inside without escape (near-malformed)
    _basic_inner.map(lambda s: f'"{s}"\""')
)

# Multiline basic string (""" ... """)
ml_basic_inner = st.lists(st.one_of(_basic_inner_piece, st.just('\\\r\n'), st.just('\\\n')), min_size=0, max_size=12).map(''.join)
ml_basic_string = st.one_of(
    ml_basic_inner.map(lambda s: f'"""{s}"""'),
    ml_basic_inner.map(lambda s: f'"""{s}'),  # unterminated
)

# Literal string '...'
literal_inner = st.lists(st.one_of(_printable_chars, st.sampled_from(_control_chars + _sample_unicode)), min_size=0, max_size=20).map(
    lambda s: ''.join(s).replace("'", "")  # avoid internal single quote to keep simple (we still generate edge cases elsewhere)
)
literal_string = st.one_of(
    literal_inner.map(lambda s: f"'{s}'"),
    literal_inner.map(lambda s: f"'{s}")  # unterminated
)

# Multiline literal string '''...'''
ml_literal_inner = st.lists(st.one_of(_printable_chars, st.sampled_from(_control_chars + _sample_unicode), st.just('\n'), st.just('\r')), min_size=0, max_size=40).map(''.join)
ml_literal_string = st.one_of(
    ml_literal_inner.map(lambda s: f"'''{s}'''"),
    ml_literal_inner.map(lambda s: f"'''{s}")  # unterminated
)

string_value = st.one_of(basic_string, ml_basic_string, literal_string, ml_literal_string)

# Keys: unquoted and quoted
unquoted_key = st.text(alphabet=st.characters(whitelist_categories=('Lu','Ll','Nd')), min_size=1, max_size=40).map(
    lambda s: ''.join(ch if ch.isalnum() else '_' for ch in s)  # ensure only allowed unquoted chars
)
quoted_key = st.one_of(basic_string, literal_string).map(lambda s: s)  # already quoted forms
simple_key = st.one_of(quoted_key, unquoted_key)
dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: '.'.join(p if p.startswith('"') or p.startswith("'") else p for p in parts))

# Integer forms, include extremes and variations
def dec_digits_with_underscores(min_len=1, max_len=50):
    return st.integers(min_value=0, max_value=10**(max_len) - 1).map(lambda n: str(n)).map(
        lambda s: s if len(s) >= min_len else s.zfill(min_len)
    ).flatmap(
        lambda s: st.just(s) if len(s) < 2 else st.one_of(
            st.just(s),
            # insert underscores in random positions
            st.just('_'.join([s[i:i+3] for i in range(0, len(s), 3)]))
        )
    )

dec_int = st.one_of(
    st.integers(min_value=-10**100, max_value=10**100).map(lambda n: str(n)),  # big ints
    dec_digits_with_underscores(1, 60).map(lambda s: s),
    # leading zeros case
    st.integers(min_value=0, max_value=999).map(lambda n: f"{n:03d}")
)

hex_int = st.integers(min_value=0, max_value=2**256).map(lambda n: hex(n)).map(lambda s: s.replace('0x', '0x' + s[2:]).replace('0x', '0x'))  # ensure prefix
# more controlled hex with underscores
hex_int2 = st.integers(min_value=0, max_value=2**64).map(lambda n: format(n, 'x')).map(lambda s: '0x' + s)
oct_int = st.integers(min_value=0, max_value=2**80).map(lambda n: oct(n)).map(lambda s: '0o' + s[2:])
bin_int = st.integers(min_value=0, max_value=2**80).map(lambda n: bin(n)).map(lambda s: '0b' + s[2:])

integer_value = st.one_of(dec_int, hex_int2, oct_int, bin_int)

# Floating forms including weird cases
float_normal = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: repr(f)),
    st.integers(min_value=0, max_value=10**50).map(lambda n: f"{n}.0"),
    st.integers(min_value=0, max_value=10**50).map(lambda n: f"{n}."),
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: ("." + repr(abs(f))[0:10].lstrip('0')) if abs(f) < 1 else repr(f))
)
float_inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
float_value = st.one_of(float_normal, float_inf_nan)

# Bool
bool_value = st.sampled_from(['true', 'false'])

# Date-time forms (not strictly validated calendar-wise)
def two(n): return str(n).zfill(2)
year = st.integers(0, 9999).map(lambda y: str(y).zfill(4))
month = st.integers(1, 12).map(two)
day = st.integers(1, 31).map(two)
hour = st.integers(0, 23).map(two)
minute = st.integers(0, 59).map(two)
second = st.integers(0, 59).map(two)
secfrac = st.one_of(st.just(''), st.integers(1, 999999999).map(lambda n: '.' + str(n)))
offset = st.one_of(st.just('Z'), st.integers(-23, 23).flatmap(lambda h: st.integers(0, 59).map(lambda m: f"{'+' if h>=0 else '-'}{abs(h):02d}:{m:02d}")))
date_sep = st.sampled_from(['T', 't', ' '])

offset_dt = st.tuples(year, month, day, date_sep, hour, minute, second, secfrac, offset).map(lambda t: f"{t[0]}-{t[1]}-{t[2]}{t[3]}{t[4]}:{t[5]}:{t[6]}{t[7]}{t[8]}")
local_dt = st.tuples(year, month, day, date_sep, hour, minute, second, secfrac).map(lambda t: f"{t[0]}-{t[1]}-{t[2]}{t[3]}{t[4]}:{t[5]}:{t[6]}{t[7]}")
local_date = st.tuples(year, month, day).map(lambda t: f"{t[0]}-{t[1]}-{t[2]}")
local_time = st.tuples(hour, minute, second, secfrac).map(lambda t: f"{t[0]}:{t[1]}:{t[2]}{t[3]}")

date_time_value = st.one_of(offset_dt, local_dt, local_date, local_time)

# Base non-recursive value kinds
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value
)

# Now make recursive values: arrays and inline tables (which are recursive)
def extend_values(child):
    # deep nested arrays: repeated wrapping to achieve deep nesting (up to 1024 in practice)
    deep_array = st.integers(min_value=0, max_value=1024).flatmap(
        lambda depth: child.flatmap(lambda inner: st.just('[' * depth + inner + ']' * depth))
    )
    # arrays of children with comments, trailing commas, mixed types, empty arrays
    array_elements = st.lists(child, min_size=0, max_size=6).flatmap(
        lambda items: st.one_of(
            st.just('[' + ', '.join(items) + ']'),
            st.just('[' + ',\n  '.join(items) + (',]' if items and False else ']'))  # occasionally trailing comma
        )
    )
    # inline tables: { k = v, ... } allow trailing comma and sometimes newline inserted (which is a rejection case)
    inline_kv = st.tuples(
        unquoted_key,
        child
    ).map(lambda kv: f"{kv[0]} = {kv[1]}")
    inline_table = st.lists(inline_kv, min_size=0, max_size=6).map(lambda kvs:
        '{' + (', '.join(kvs) + (',' if kvs and True else '')) + '}'
    )
    # nested inline tables by wrapping a child value inside a table repeatedly
    deep_inline = st.integers(min_value=0, max_value=256).flatmap(
        lambda depth: child.flatmap(lambda inner: st.just('{' * depth + 'a = ' + inner + '}' * depth))
    )
    # mix these possibilities
    return st.one_of(deep_array, array_elements, inline_table, deep_inline)

# Use st.recursive to create a value strategy
value = st.recursive(base_value, extend_values, max_leaves=50)

# Comments and whitespace
comment = st.one_of(st.just(''), st.text(alphabet=st.characters(blacklist_characters="\x00"), min_size=0, max_size=40).map(lambda s: '# ' + s))
maybe_comment = st.one_of(st.just(''), comment)
newline = st.one_of(st.just('\n'), st.just('\r\n'))

# Key/value lines, with edge cases like missing '=', double '=' etc.
kv_equal = st.one_of(st.just(' = '), st.just('='), st.just('  =  '), st.just(' == '), st.just(' '))
key_value_line = st.tuples(
    st.one_of(dotted_key, simple_key),
    kv_equal,
    value,
    maybe_comment
).map(lambda t: f"{t[0]}{t[1]}{t[2]}{(' ' + t[3]) if t[3] else ''}")

# Table headers and array table headers with possible malformed delimiters
def table_header_variant(kind):  # kind: 'standard' or 'array'
    # create possibilities: correct, missing bracket, doubled bracket, extra token
    br = st.sampled_from([
        ('[', ']'),  # correct
        ('[', ''),   # missing closing
        ('[[', ']]'),  # array table correct
        ('[[', ']'),   # malformed
        ('[', ']]'),   # malformed
    ])
    return br

standard_table = st.one_of(
    dotted_key.map(lambda k: f'[{k}]'),
    dotted_key.map(lambda k: f'[{k}')  # missing closing bracket
)
array_table = st.one_of(
    dotted_key.map(lambda k: f'[[{k}]]'),
    dotted_key.map(lambda k: f'[[{k}]')  # malformed
)

# stray tokens: random near-valid tokens or stray punctuation
stray_token = st.sampled_from([
    '===', '...', '???', 'truefalse', '[[[', ']]]', '{', '}', '= =', 'nope', '# just a comment line'
])

# Expressions: key/value, table, comment-only, stray token
expression = st.one_of(
    key_value_line,
    standard_table,
    array_table,
    comment.map(lambda c: c if c else ''),  # comment or empty line
    stray_token
)

# Documents: sequences of expressions joined by newlines; include empty documents and no trailing newline
document = st.lists(expression, min_size=0, max_size=12).map(
    lambda exprs: '\n'.join(exprs)
)

# Make sure strategy is a SearchStrategy[str] named 'strategy'
strategy = document
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 16,
    "reject": 244
  },
  "acceptance_rate": 0.062,
  "max_nesting_depth": 0,
  "productions_accepted": [
    "BASIC_STRING",
    "COMMENT",
    "LITERAL_STRING",
    "NL",
    "UNQUOTED_KEY",
    "array_table",
    "comment",
    "document",
    "dotted_key",
    "expression",
    "key",
    "key_value",
    "quoted_key",
    "simple_key",
    "standard_table",
    "string",
    "table",
    "unquoted_key",
    "value"
  ],
  "productions_gap": [
    "integer",
    "floating_point",
    "bool_",
    "date_time",
    "array_",
    "array_values",
    "comment_or_nl",
    "nl_or_comment",
    "inline_table",
    "inline_table_keyvals",
    "inline_table_keyvals_non_empty",
    "BOOLEAN",
    "ML_BASIC_STRING",
    "ML_LITERAL_STRING",
    "FLOAT",
    "INF",
    "NAN",
    "DEC_INT",
    "HEX_INT",
    "OCT_INT",
    "BIN_INT",
    "OFFSET_DATE_TIME",
    "LOCAL_DATE_TIME",
    "LOCAL_DATE",
    "LOCAL_TIME"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 11,
  "divergences": 1,
  "divergence_examples": [
    "b'# \\xc3\\xa0\\xc3\\xb4K\\x06\\x03f\\x1c'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **add_or_upweight_production** — integer.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.