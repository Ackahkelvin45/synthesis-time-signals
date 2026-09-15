from hypothesis import strategies as st
import json

# Helper pools and small utilities
_ascii_printable = ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (34, 39, 92))  # exclude " ' \
_control_chars = [chr(i) for i in range(1, 32)]  # exclude NUL (0)
_escape_samples = ['\\n', '\\r', '\\t', '\\\\', '\\"', "\\'", '\\u0001', '\\u007f', '\\u1234', '\\U0001F600', '\\q']
_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

# Basic pieces
bare_key = st.text(_bare_key_chars, min_size=1, max_size=20)
empty_quoted_key = st.just('""')
quoted_key_basic = st.deferred(lambda: st.one_of(
    # complete basic quoted string (may include escapes or raw control chars)
    st.tuples(
        st.lists(st.one_of(
            st.text(_ascii_printable, min_size=1, max_size=6),
            st.sampled_from(_escape_samples),
            st.sampled_from(_control_chars)
        ), min_size=0, max_size=6).map(''.join),
        st.booleans().map(lambda b: b)  # whether to be unterminated
    ).map(lambda tup: ('"' + tup[0] + '"') if not tup[1] else ('"' + tup[0])),
    # multiline basic string (triple-quoted) - allow newlines, sometimes unterminated
    st.tuples(
        st.lists(st.one_of(
            st.text(_ascii_printable + '\n\t', min_size=1, max_size=12),
            st.sampled_from(_escape_samples),
            st.sampled_from(_control_chars)
        ), min_size=0, max_size=8).map(''.join),
        st.booleans()
    ).map(lambda tup: ('"""' + tup[0] + '"""') if not tup[1] else ('"""' + tup[0])),
))

quoted_key_literal = st.deferred(lambda: st.one_of(
    # literal single-line
    st.tuples(
        st.text(''.join(ch for ch in (_ascii_printable + '\t') if ch != "'"), min_size=0, max_size=20),
        st.booleans()
    ).map(lambda tup: ("'" + tup[0] + "'") if not tup[1] else ("'" + tup[0])),
    # multiline literal
    st.tuples(
        st.text(''.join(ch for ch in (_ascii_printable + '\n\t') if ch != "'"), min_size=0, max_size=100),
        st.booleans()
    ).map(lambda tup: ("'''"+tup[0]+"'''") if not tup[1] else ("'''"+tup[0]))
))

simple_key = st.one_of(quoted_key_basic, quoted_key_literal, bare_key, empty_quoted_key)

dotted_key = st.deferred(lambda: st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: '.'.join(parts)))

# Comments and newline variants
comment = st.one_of(st.just(''), st.text('#', min_size=1, max_size=1).map(lambda x: x)  # placeholder, will be extended
                     , st.lists(st.one_of(st.text(_ascii_printable, min_size=1, max_size=20),
                                         st.sampled_from(_control_chars)), min_size=0, max_size=6).map(lambda L: '#' + ''.join(L))
                     )

_crlf = st.sampled_from(['\n', '\r\n'])

# String value strategies
_basic_string_content = st.lists(st.one_of(
    st.text(_ascii_printable, min_size=1, max_size=8),
    st.sampled_from(_escape_samples),
    st.sampled_from(_control_chars)
), min_size=0, max_size=6).map(''.join)

basic_string = st.tuples(_basic_string_content, st.booleans()).map(
    lambda t: ('"' + t[0] + '"') if not t[1] else ('"' + t[0])
)

_ml_basic_string = st.tuples(
    st.lists(st.one_of(
        st.text(_ascii_printable + '\n\t', min_size=1, max_size=12),
        st.sampled_from(_escape_samples),
        st.sampled_from(_control_chars)
    ), min_size=0, max_size=8).map(''.join),
    st.booleans()
).map(lambda t: ('"""' + t[0] + '"""') if not t[1] else ('"""' + t[0]))

_literal_string = st.tuples(
    st.lists(st.one_of(
        st.text(''.join(ch for ch in (_ascii_printable + '\t') if ch != "'"), min_size=1, max_size=12),
        st.sampled_from(_control_chars)
    ), min_size=0, max_size=6).map(''.join),
    st.booleans()
).map(lambda t: ("'" + t[0] + "'") if not t[1] else ("'" + t[0]))

_ml_literal_string = st.tuples(
    st.lists(st.one_of(
        st.text(''.join(ch for ch in (_ascii_printable + '\n\t') if ch != "'"), min_size=1, max_size=40),
        st.sampled_from(_control_chars)
    ), min_size=0, max_size=4).map(''.join),
    st.booleans()
).map(lambda t: ("'''"+t[0]+"'''") if not t[1] else ("'''"+t[0]))

string_value = st.one_of(basic_string, _ml_basic_string, _literal_string, _ml_literal_string)

# Integer strategies
def _decimal_str_gen():
    digits = st.text('0123456789', min_size=1, max_size=30)
    sign = st.sampled_from(['', '+', '-'])
    unders = st.booleans()
    return st.tuples(sign, digits, unders).map(lambda t: t[0] + (_insert_underscores(t[1]) if t[2] else t[1]))

def _insert_underscores(s):
    # Insert underscores randomly but not at ends; simple deterministic insertion to avoid importing random
    if len(s) <= 2:
        return s
    parts = []
    i = 0
    # insert underscore every 2-3 digits
    while i < len(s):
        take = 2 if (i % 3 == 0) else 3
        parts.append(s[i:i+take])
        i += take
    return '_'.join(p for p in parts if p)

decimal_int = _decimal_str_gen()

hex_int = st.tuples(st.sampled_from(['', '+', '-']), st.text('0123456789abcdefABCDEF', min_size=1, max_size=20), st.booleans()).map(
    lambda t: (t[0] + '0x' + (_insert_underscores(t[1]) if t[2] else t[1]))
)

oct_int = st.tuples(st.sampled_from(['', '+', '-']), st.text('01234567', min_size=1, max_size=24), st.booleans()).map(
    lambda t: (t[0] + '0o' + (_insert_underscores(t[1]) if t[2] else t[1]))
)

bin_int = st.tuples(st.sampled_from(['', '+', '-']), st.text('01', min_size=1, max_size=64), st.booleans()).map(
    lambda t: (t[0] + '0b' + (_insert_underscores(t[1]) if t[2] else t[1]))
)

int_value = st.one_of(decimal_int, hex_int, oct_int, bin_int)

# Float strategies
_float_norm = st.deferred(lambda: st.one_of(
    # forms: 1., .5, 1.0, 1e10, 1.0e-10, 1._000 style if needed
    st.tuples(st.sampled_from(['','+','-']), st.text('0123456789', min_size=1, max_size=20),
              st.booleans(), st.booleans(), st.integers(min_value=-5000, max_value=5000)).map(
        lambda t: (
            t[0] + (
                (t[1] + '.') if t[2] and not t[3] else
                ('.' + t[1]) if t[2] and t[3] else
                (t[1] + ('.' + t[1][:3]) if t[3] else t[1])
            ) + ('e' + ('+' if t[4] >= 0 else '') + str(t[4])) if t[3] else (
                (t[0] + t[1] + '.') if t[2] else (t[0] + '.' + t[1]) if t[3] else (t[0] + t[1] + '.')
            )
        )
    ),
    # explicit exponent style using underscores in integer part occasionally
    st.tuples(st.sampled_from(['','+','-']), st.text('0123456789', min_size=1, max_size=15),
              st.integers(min_value=-10000, max_value=10000)).map(lambda t: t[0] + t[1] + 'e' + ('+' if t[2] >= 0 else '') + str(t[2])),
    st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
))

# Date/time strategies
_year = st.integers(min_value=0, max_value=9999).map(lambda y: str(y).zfill(4))
_month = st.integers(min_value=1, max_value=12).map(lambda m: str(m).zfill(2))
_day = st.integers(min_value=1, max_value=31).map(lambda d: str(d).zfill(2))
_hour = st.integers(min_value=0, max_value=23).map(lambda h: str(h).zfill(2))
_minute = st.integers(min_value=0, max_value=59).map(lambda m: str(m).zfill(2))
_second = st.integers(min_value=0, max_value=60).map(lambda s: str(s).zfill(2))
_frac = st.one_of(st.just(''), st.tuples(st.just('.'), st.text('0123456789', min_size=1, max_size=9)).map(lambda t: t[0] + t[1]))
_offset = st.one_of(st.just('Z'), st.tuples(st.sampled_from(['+', '-']), _hour, st.just(':'), _minute).map(lambda t: t[0] + t[1] + t[2] + t[3]))

offset_date_time = st.tuples(_year, st.sampled_from(['T','t',' ']), _month, st.just('-'), _day, st.sampled_from(['T',' ' ,'t']), _hour, st.just(':'), _minute, st.just(':'), _second, st.one_of(_frac, st.just('')), _offset).map(
    lambda t: t[0] + '-' + t[2] + '-' + t[4] + t[1] + t[6] + ':' + t[8] + ':' + t[10] + (t[11] if t[11] else '') + t[12]
)

local_date_time = st.tuples(_year, st.sampled_from(['T',' ']), _month, st.just('-'), _day, st.sampled_from(['T',' ']), _hour, st.just(':'), _minute, st.just(':'), _second, st.one_of(_frac, st.just(''))).map(
    lambda t: t[0] + '-' + t[2] + '-' + t[4] + t[1] + t[6] + ':' + t[8] + ':' + t[10] + (t[11] if t[11] else '')
)

local_date = st.tuples(_year, _month, _day).map(lambda t: t[0] + '-' + t[1] + '-' + t[2])
local_time = st.tuples(_hour, _minute, _second, st.one_of(_frac, st.just(''))).map(lambda t: t[0] + ':' + t[1] + ':' + t[2] + (t[3] if t[3] else ''))

date_time_value = st.one_of(offset_date_time, local_date_time, local_date, local_time)

bool_value = st.sampled_from(['true', 'false'])

# Forward declaration for recursive value strategy
# Base (non-array/non-inline-table) values:
primitive_value = st.one_of(string_value, int_value, _float_norm, date_time_value, bool_value)

# For arrays and inline tables we use recursive strategy
def make_recursive_values():
    base = primitive_value

    def extend(children):
        # children: strategy producing value strings (could include arrays/inline tables recursively)
        # Array generator
        array_elems = st.lists(children, min_size=0, max_size=6)
        array_with_comments = st.tuples(array_elems, st.booleans()).map(
            lambda t: '[' + (', '.join(t[0]) + (',' if t[1] and t[0] else (',' if t[1] else ''))) + ']'
        )
        # Nested array start token allowed to nest arrays
        nested_array = st.tuples(array_elems, st.booleans()).map(
            lambda t: '[' + (', '.join(t[0]) + (',' if t[1] and t[0] else (',' if t[1] else ''))) + ']'
        )
        # Inline table: single-line only, allow trailing comma
        inline_kv = st.builds(
            lambda kvs, trailing:
                '{' + (', '.join(kvs) + (',' if trailing and kvs else (',' if trailing else '')) ) + '}',
            st.lists(st.tuples(st.one_of(simple_key, dotted_key).map(lambda k: k if k else '""'),
                               children).map(lambda t: t[0] + ' = ' + t[1]), min_size=0, max_size=6),
            st.booleans()
        )
        return st.one_of(array_with_comments, nested_array, inline_kv)
    return st.recursive(base, extend, max_leaves=1000)

value = make_recursive_values()

# Key-value lines with variations: missing equals, double equals, stray token, duplicate keys, comments
def key_value_line():
    def build(k, eq_style, v, cm):
        if eq_style == 'normal':
            line = k + ' = ' + v
        elif eq_style == 'missing':
            line = k + ' ' + v  # missing '='
        else:
            line = k + ' == ' + v  # doubled equals
        if cm:
            return line + ' #' + cm
        return line
    eq_kind = st.sampled_from(['normal', 'missing', 'double'])
    return st.tuples(st.one_of(dotted_key, simple_key), eq_kind, value, st.one_of(st.just(''), st.text(_ascii_printable, min_size=0, max_size=40))).map(
        lambda t: build(t[0], t[1], t[2], t[3])
    )

# Table lines
table_line = st.one_of(
    st.deferred(lambda: dotted_key.map(lambda k: '[' + k + ']')),
    st.deferred(lambda: dotted_key.map(lambda k: '[[' + k + ']]'))
)

# Expression: key_value, table, or comment-only
expression = st.one_of(
    key_value_line(),
    table_line,
    st.lists(st.one_of(st.text(_ascii_printable, min_size=0, max_size=60), st.sampled_from(_control_chars)), min_size=0, max_size=6).map(lambda L: '#' + ''.join(L) if any(L) else '')
)

# Document: sequence of expressions separated by newlines (possibly CRLF), include empty documents and comment-only
document = st.lists(expression, min_size=0, max_size=40).flatmap(
    lambda lines:
        st.tuples(st.just(lines), st.lists(_crlf, min_size=1, max_size=1)).map(lambda t: (t[0], t[1][0]))
).map(
    lambda tup: tup[1].join(tup[0])  # join with chosen newline style
)

# Additional combinator to inject deep nested arrays/tables (to stress recursion depth)
def deep_nesting_fragment():
    # generate a nesting level between small and high (but avoid too huge often)
    depth = st.integers(min_value=0, max_value=300).map(int)
    def build(d):
        # build nested arrays like [[[[... "x"]]]]
        inner = '"deep"'
        parts = ['[' for _ in range(d)] + [inner] + [']' for _ in range(d)]
        return ''.join(parts)
    return depth.map(build)

# Compose final document with occasional duplicated keys/tables and appended deep nesting fragments
def document_with_edgecases():
    base_doc = document
    extra = st.one_of(st.just(''), deep_nesting_fragment(), st.tuples(st.lists(expression, min_size=0, max_size=6), st.just('\n')).map(lambda t: ('\n'.join(t[0]) + t[1])))
    # occasionally repeat a key to create duplicate key scenario by duplicating an existing key
    def maybe_dup(doc_text):
        # 30% chance to duplicate a key by repeating first key-value line
        lines = doc_text.splitlines()
        kv_lines = [ln for ln in lines if '=' in ln]
        if not kv_lines:
            return doc_text
        # duplicate first kv line sometimes
        if st.booleans().example():
            dup = kv_lines[0]
            # insert duplicate near start
            pos = 0
            lines.insert(pos, dup)
            return '\n'.join(lines)
        return doc_text
    # We cannot call .example() in final strategy; instead we simulate duplication probabilistically by producing either original or duplicated
    return st.tuples(base_doc, extra).map(lambda t: (lambda s: (lambda lines: '\n'.join(([next(ln for ln in lines if '=' in ln)] + lines) if any('=' in ln for ln in lines) else lines))(s.splitlines()))(t[0] + (('\n' + t[1]) if t[1] else '')))

# Final top-level strategy
strategy = document_with_edgecases()