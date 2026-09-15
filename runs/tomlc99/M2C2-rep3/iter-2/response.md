```python
from hypothesis import strategies as st
import json

# Helper character sets
_ASCII_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_PRINTABLE_ASCII = ''.join(chr(i) for i in range(32, 127) if chr(i) != '"' and chr(i) != "'" and chr(i) != '\\')

# --- String value strategies -------------------------------------------------
# Basic (double-quoted) string: no raw newline or unescaped backslash/quote inside
_basic_inner = st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters='"\n\r\\'),
    min_size=0,
    max_size=60,
)
_basic_escape = st.sampled_from(['\\n', '\\r', '\\t', '\\b', '\\f', '\\\\', '\\"', '\\u0000', '\\u263A', '\\U0001F600'])
basic_string = st.one_of(
    _basic_inner.map(lambda s: f'"{s}"'),
    st.lists(st.one_of(_basic_inner, _basic_escape), min_size=0, max_size=8).map(lambda parts: '"' + ''.join(parts) + '"'),
    # unterminated or malformed forms (near-valid but malformed)
    st.one_of(
        _basic_inner.map(lambda s: '"' + s),               # missing closing quote
        _basic_inner.map(lambda s: '"' + s + '\\"'),      # extra backslash at end
    ),
)

# Literal (single-quoted) string: cannot contain single-quote or newline raw
_literal_inner = st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="'\n\r"),
    min_size=0,
    max_size=60,
)
literal_string = st.one_of(
    _literal_inner.map(lambda s: f"'{s}'"),
    # unterminated
    _literal_inner.map(lambda s: "'" + s),
)

# Multiline basic and literal: allow newlines and various content
_ml_basic_inner = st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters='\\'),
    min_size=0,
    max_size=200,
)
ml_basic_string = st.one_of(
    _ml_basic_inner.map(lambda s: '"""' + s + '"""'),
    # unterminated/malformed
    _ml_basic_inner.map(lambda s: '"""' + s),
)

_ml_literal_inner = st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF),
    min_size=0,
    max_size=200,
)
ml_literal_string = st.one_of(
    _ml_literal_inner.map(lambda s: "'''" + s + "'''"),
    _ml_literal_inner.map(lambda s: "'''" + s),  # unterminated
)

string_value = st.one_of(
    basic_string,
    literal_string,
    ml_basic_string,
    ml_literal_string,
)

# --- Numeric strategies -----------------------------------------------------
# Decimal with optional underscores and leading zeros, extremes
_dec_digit = st.sampled_from([str(i) for i in range(10)])
def dec_with_underscores(min_len=1, max_len=30):
    return st.lists(_dec_digit, min_size=min_len, max_size=max_len).map(''.join).map(
        lambda s: s if st.randoms().example().randint(0, 3) else insert_underscores(s)
    )

def insert_underscores(s):
    # heuristic: insert some underscores between digits
    import random
    if len(s) < 2:
        return s
    chars = list(s)
    for _ in range(random.randint(0, max(0, len(s)//3))):
        i = random.randint(1, len(chars)-1)
        if chars[i-1] != '_' and chars[i] != '_':
            chars.insert(i, '_')
    return ''.join(chars)

dec_int = st.one_of(
    # plain integers, possibly with sign and leading zeros allowed
    st.integers(min_value=-10**40, max_value=10**40).map(lambda n: str(n)),
    # constructed decimal with underscores and optional leading zeros
    st.builds(lambda sign, d: (sign or '') + d, st.sampled_from(['', '+', '-']), st.text(alphabet="0123456789_", min_size=1, max_size=40)),
    # explicit leading-zero examples like 007
    st.sampled_from(["007", "0001", "000", "0", "-0", "+007"]),
)

hex_int = st.one_of(
    st.text(alphabet="0123456789abcdefABCDEF_", min_size=1, max_size=16).map(lambda s: '0x' + s),
    st.just('0x' + '0' * 60),  # extreme long hex
)

oct_int = st.one_of(
    st.text(alphabet="01234567_", min_size=1, max_size=22).map(lambda s: '0o' + s),
)

bin_int = st.one_of(
    st.text(alphabet="01_", min_size=1, max_size=64).map(lambda s: '0b' + s),
)

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int)

# Floats including 1., .5, exponent extremes, inf/nan
float_fractional = st.one_of(
    st.builds(lambda a,b: a + '.' + b, st.text(alphabet="0123456789_", min_size=1, max_size=10), st.text(alphabet="0123456789_", min_size=0, max_size=10)),
    st.builds(lambda a: a + '.', st.text(alphabet="0123456789_", min_size=1, max_size=10)),  # 1. form
    st.builds(lambda b: '.' + b, st.text(alphabet="0123456789_", min_size=1, max_size=10)),  # .5 form
)
float_exp = st.one_of(
    st.builds(lambda base, exp: base + ('e' + exp), st.text(alphabet="0123456789_", min_size=1, max_size=6), st.builds(lambda s,g: s + g, st.sampled_from(['', '+','-']), st.text(alphabet="0123456789_", min_size=1, max_size=5))),
    st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan']),
    st.just('1e309'),  # extreme
)
float_value = st.one_of(float_fractional, float_exp)

# Boolean
bool_value = st.sampled_from(['true', 'false'])

# --- Date/time strategies ---------------------------------------------------
_digit2 = st.text(alphabet="0123456789", min_size=2, max_size=2)
_digit4 = st.text(alphabet="0123456789", min_size=4, max_size=4)
def date_components():
    year = _digit4
    month = _digit2
    day = _digit2
    hour = _digit2
    minute = _digit2
    second = _digit2
    secfrac = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(alphabet="0123456789", min_size=1, max_size=6)))
    offset = st.one_of(st.just('Z'), st.builds(lambda s,t,u: s + t + ':' + u, st.sampled_from(['+','-']), _digit2, _digit2))
    return st.tuples(year, month, day, hour, minute, second, secfrac, offset)
datetime_value = st.one_of(
    date_components().map(lambda ymdhmso: f"{ymdhmso[0]}-{ymdhmso[1]}-{ymdhmso[2]}T{ymdhmso[3]}:{ymdhmso[4]}:{ymdhmso[5]}{ymdhmso[6]}{ymdhmso[7]}"),
    # local date/time variants (space separator allowed)
    date_components().map(lambda ymdhmso: f"{ymdhmso[0]}-{ymdhmso[1]}-{ymdhmso[2]} {ymdhmso[3]}:{ymdhmso[4]}:{ymdhmso[5]}{ymdhmso[6]}"),
    date_components().map(lambda ymdhmso: f"{ymdhmso[0]}-{ymdhmso[1]}-{ymdhmso[2]}"),
    date_components().map(lambda ymdhmso: f"{ymdhmso[3]}:{ymdhmso[4]}:{ymdhmso[5]}{ymdhmso[6]}"),
)

# --- Comments and spacing ---------------------------------------------------
comment = st.one_of(st.just(''), st.builds(lambda t: '# ' + t, st.text(alphabet=_PRINTABLE_ASCII, min_size=0, max_size=40)))
opt_space = st.one_of(st.just(''), st.just(' '), st.just('  '), st.just('\t'))

# --- Key strategies ---------------------------------------------------------
simple_unquoted_key = st.text(alphabet=_ASCII_KEY_CHARS, min_size=1, max_size=100)
# quoted keys: reuse string_value but ensure it's BASIC_STRING or LITERAL_STRING forms for quoted keys
quoted_key = st.one_of(
    _basic_inner.map(lambda s: f'"{s}"'),
    _literal_inner.map(lambda s: f"'{s}'"),
    st.just('""'),  # empty quoted key
)
simple_key = st.one_of(simple_unquoted_key, quoted_key)
dotted_key = st.lists(simple_key, min_size=2, max_size=5).map(lambda parts: '.'.join(parts))

key_strategy = st.one_of(simple_key, dotted_key)

# --- Value composition strategy (recursive for arrays and inline tables) ----
# Base values (non-recursive)
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    datetime_value,
    st.just(''),  # empty token to allow malformed stray tokens
)

# We'll use st.recursive to create arrays and inline tables which can nest.
def _extend(inner):
    # arrays: can contain values and nested arrays / inline tables (inner)
    array_elems = st.lists(st.one_of(inner, base_value), min_size=0, max_size=6).map(
        lambda lst: ", ".join([e for e in lst if e is not None and e != ''])
    )
    # allow optional trailing comma sometimes
    array_builder = st.one_of(
        array_elems.map(lambda s: '[' + s + ']'),
        array_elems.map(lambda s: '[' + s + ',]'),  # trailing comma allowed in arrays
        # multiline array with comments and CRLF
        st.lists(st.one_of(inner, base_value, comment), min_size=0, max_size=6).map(
            lambda parts: '[' + ("\r\n  ".join([p for p in parts if p])) + ']'
        ),
    )
    # inline tables: generate key=value pairs separated by commas; include optional trailing comma
    def make_inline(kv_pairs, allow_newline=False, trailing_comma=False):
        if not kv_pairs:
            body = ''
        else:
            body = ', '.join(kv_pairs)
        if trailing_comma:
            body = body + ','
        if allow_newline:
            # make deliberately malformed newline inside inline table
            return '{' + body.replace(', ', ',\n  ') + '}'
        return '{' + body + '}'

    kv_pair = st.tuples(
        st.one_of(simple_unquoted_key, quoted_key, st.text(alphabet=_ASCII_KEY_CHARS, min_size=0, max_size=100)),
        st.sampled_from([' = ', '=',' =']),
        inner
    ).map(lambda tpl: tpl[0] + tpl[1] + tpl[2])

    inline_table_builder = st.one_of(
        st.lists(kv_pair, min_size=0, max_size=6).map(lambda kvs: make_inline(kvs, allow_newline=False, trailing_comma=False)),
        st.lists(kv_pair, min_size=0, max_size=6).map(lambda kvs: make_inline(kvs, allow_newline=False, trailing_comma=True)),
        # sometimes include newline inside inline table to exercise malformed case (parser rejects)
        st.lists(kv_pair, min_size=0, max_size=6).map(lambda kvs: make_inline(kvs, allow_newline=True, trailing_comma=False)),
    )

    return st.one_of(array_builder, inline_table_builder)

# Use a high max_leaves so Hypothesis can explore deep nesting (subject to machine limits)
value_recursive = st.recursive(base_value, _extend, max_leaves=2048)

# Final value strategy includes recursive structures and base values
value_strategy = st.one_of(value_recursive, base_value)

# --- Expression generators --------------------------------------------------
# key = value lines, with optional spaces/comments, and sometimes malformed variants
def key_value_expression():
    # Possibly produce malformed variants: missing equals, double equals, stray token
    good = st.tuples(key_strategy, st.just('='), value_strategy, comment).map(
        lambda t: f"{t[0]} = {t[2]}" + ('' if t[3]=='' else ' ' + t[3])
    )
    malformed = st.one_of(
        st.tuples(key_strategy, value_strategy).map(lambda t: f"{t[0]} {t[1]}"),        # missing '='
        st.tuples(key_strategy, st.just('=='), value_strategy).map(lambda t: f"{t[0]}=={t[2]}"),  # double ==
        st.tuples(key_strategy, st.just('='), st.just('')).map(lambda t: f"{t[0]} = "),   # empty value
        st.tuples(key_strategy, st.just('='), value_strategy).map(lambda t: f"{t[0]} ={t[2]}"),  # odd spacing
    )
    return st.one_of(good, malformed)

# table expressions: [key] and [[key]] and malformed bracket variants
standard_table = st.tuples(st.just('['), key_strategy, st.just(']')).map(lambda t: t[0] + t[1] + t[2])
array_table = st.tuples(st.just('[['), key_strategy, st.just(']]')).map(lambda t: t[0] + t[1] + t[2])
table_malformed = st.one_of(
    st.tuples(st.just('['), key_strategy, st.just('')).map(lambda t: t[0] + t[1]),   # missing closing bracket
    st.tuples(st.just('[[['), key_strategy, st.just(']]')).map(lambda t: t[0] + t[1] + t[2]),  # extra [
)
table_expression = st.one_of(standard_table, array_table, table_malformed)

comment_expression = comment.map(lambda c: c if c != '' else '')  # allow empty

expression = st.one_of(
    key_value_expression(),
    table_expression,
    comment_expression,
)

# --- Document assembly ------------------------------------------------------
# Allow empty documents, comment-only, and multi-line documents. Include CRLF sometimes.
newline = st.sampled_from(['\n', '\r\n'])
def doc_builder():
    # number of expressions in document
    docs = st.lists(expression, min_size=0, max_size=12)
    joiner = st.one_of(newline, st.just('\n'), st.just('\r\n'))
    def assemble(exprs_and_nl):
        exprs, nl = exprs_and_nl
        # optionally create duplicate keys and duplicate tables by repeating some expressions
        if exprs:
            import random
            if random.random() < 0.15:
                # duplicate a random expression (to trigger duplicate key/table tests)
                i = random.randrange(len(exprs))
                exprs.insert(i, exprs[i])
        # occasionally create documents with no trailing newline
        if exprs and st.randoms().example().randint(0, 3) == 0:
            return nl.join(exprs)
        return nl.join(exprs) + ('' if not exprs else '')
    return st.tuples(docs, joiner).map(assemble)

document_strategy = doc_builder()

# Expose top-level name 'strategy' as required: produce full document strings
strategy = document_strategy
```