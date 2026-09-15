```python
from hypothesis import strategies as st
import json

# Atomic building blocks

# Characters usable inside basic strings (no NUL, no raw newline characters)
_basic_string_char = st.characters(
    blacklist_characters=['\x00', '"', '\\', '\n', '\r']
)
# Allow control characters except NUL and newlines for raw control tests
_control_char = st.characters(
    min_codepoint=1, max_codepoint=0x1F, blacklist_characters=['\x00', '\n', '\r']
)
# Printable characters for keys (ASCII only for unquoted)
_key_char = st.characters(
    whitelist_categories=('Ll', 'Lu', 'Nd'), blacklist_characters=['\x00']
)
_key_extra = st.sampled_from(list("-_"))
_unquoted_key = st.text(alphabet=st.one_of(_key_char, _key_extra), min_size=1, max_size=50)

# Quoted key: allow empty quoted key "" and literal quoted
_basic_quoted_key = st.one_of(
    st.just('""'),  # empty quoted key
    st.builds(lambda s: '"' + s + '"', st.text(alphabet=st.characters(blacklist_characters=['"', '\r', '\n', '\x00']), min_size=0, max_size=30)),
    st.builds(lambda s: "'" + s + "'", st.text(alphabet=st.characters(blacklist_characters=["'", '\r', '\n', '\x00']), min_size=0, max_size=30)),
)
# dotted key: mix simple keys separated by dots
_dotted_key = st.lists(st.one_of(_unquoted_key, _basic_quoted_key), min_size=2, max_size=4).map(lambda parts: ".".join(parts))

key = st.one_of(_unquoted_key, _basic_quoted_key, _dotted_key)

# String value strategies: basic, multiline basic, literal, multiline literal, and malformed (unterminated)
def _json_escaped(s):
    # json.dumps returns a quoted string with escapes appropriate for many cases
    return json.dumps(s)

_basic_string = st.one_of(
    # raw basic string with possibly raw control chars (except NUL and newline)
    st.builds(lambda s: '"' + s + '"',
              st.text(alphabet=st.one_of(_basic_string_char, _control_char, st.characters(whitelist_categories=('Zs',))), min_size=0, max_size=60)),
    # JSON-escaped version (safe escapes like \uXXXX)
    st.builds(lambda s: s, st.text()).map(_json_escaped),
)

_ml_basic_string = st.builds(
    lambda s: '"""' + s + '"""',
    # allow escaped line continuation and raw newlines inside triple quoted
    st.text(alphabet=st.characters(blacklist_characters=['\x00']), min_size=0, max_size=200)
)

_literal_string = st.builds(lambda s: "'" + s + "'", st.text(alphabet=st.characters(blacklist_characters=["'", '\r', '\n', '\x00']), min_size=0, max_size=80))
_ml_literal = st.builds(lambda s: "'''" + s + "'''", st.text(alphabet=st.characters(blacklist_characters=['\x00']), min_size=0, max_size=200))

# Occasionally produce unterminated strings (missing closing quote) or stray tokens
_unterminated_basic = st.builds(lambda s: '"' + s, st.text(alphabet=st.one_of(_basic_string_char, _control_char), min_size=0, max_size=60))
_stray_token = st.sampled_from(['=', ']]', '[[', '}', '{', '"""', "'''"])

string_value = st.one_of(
    _basic_string,
    _ml_basic_string,
    _literal_string,
    _ml_literal,
    # edge-case malformed constructs
    st.one_of(_unterminated_basic, _stray_token.map(lambda s: s)),
)

# Integer variations: decimal (with leading zeros allowed), hex, oct, bin, extremes
_sign = st.sampled_from(['', '+', '-'])
_digits = st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=1, max_size=50)
_underscored_digits = st.builds(
    # allow underscores within digits by including '_' in the characters alphabet
    lambda sign, ds: sign + ds,
    _sign, st.text(alphabet=st.characters(whitelist_categories=('Nd',), whitelist_characters='_'), min_size=1, max_size=30)
)

decimal_int = st.one_of(
    # simple decimal with optional sign and optional underscores
    st.builds(lambda sgn, d: sgn + d,
              _sign,
              st.text(alphabet=st.characters(whitelist_categories=('Nd',), whitelist_characters='_'), min_size=1, max_size=40)),
    # leading zeros like 007
    st.builds(lambda sgn, d: sgn + d, _sign, st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=1, max_size=4)),
    # very large integer
    st.builds(lambda sgn, n: sgn + "9" * n, _sign, st.integers(min_value=19, max_value=500).map(lambda x: x)),
)

hex_int = st.builds(lambda s: "0x" + s, st.text(alphabet=st.characters(whitelist_categories=('Nd', 'Lu', 'Ll'), whitelist_characters='_'), min_size=1, max_size=40))
oct_int = st.builds(lambda s: "0o" + s, st.text(alphabet=st.characters(whitelist_categories=('Nd',), whitelist_characters='_'), min_size=1, max_size=40))
bin_int = st.builds(lambda s: "0b" + s, st.text(alphabet=st.characters(whitelist_categories=('Nd',), whitelist_characters='_'), min_size=1, max_size=40))

integer = st.one_of(decimal_int, hex_int, oct_int, bin_int)

# Floats: normal, 1. and .5, exponent large, inf/nan with sign
_float_normal = st.builds(
    lambda sgn, a, b, exp: sgn + a + '.' + b + (exp or ''),
    _sign,
    st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=0, max_size=5).map(lambda x: x or "0"),
    st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=0, max_size=6).map(lambda x: x or "0"),
    st.one_of(st.just(''), st.builds(lambda e,s: 'e' + s + str(e), st.integers(min_value=-999, max_value=999), st.sampled_from(['+', '-'])) )
)
_float_dot_trailing = st.builds(lambda s: s + '.', st.one_of(st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=1, max_size=10), decimal_int))
_float_dot_leading = st.builds(lambda s: '.' + s, st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=1, max_size=10))
_inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])

floating_point = st.one_of(_float_normal, _float_dot_trailing, _float_dot_leading, _inf_nan)

# Booleans
boolean = st.sampled_from(['true', 'false'])

# Date/time forms (may be calendar-invalid)
_year = st.integers(min_value=0, max_value=9999).map(lambda y: f"{y:04d}")
_two = lambda x: st.integers(min_value=0, max_value=x).map(lambda z: f"{z:02d}")
_month = _two(99)  # allow invalid month
_day = _two(99)
_hour = _two(99)
_minute = _two(99)
_second = _two(99)
_frac = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=1, max_size=9)))
_offset = st.one_of(st.just('Z'), st.builds(lambda sign, h, m: sign + h + ':' + m, st.sampled_from(['+', '-']), _hour, _minute))
LOCAL_DATE = st.builds(lambda Y,M,D: f"{Y}-{M}-{D}", _year, _month, _day)
LOCAL_TIME = st.builds(lambda H,Mi,S,Fr: f"{H}:{Mi}:{S}{Fr}", _hour, _minute, _second, _frac)
LOCAL_DATE_TIME = st.builds(lambda d,t: d + 'T' + t, LOCAL_DATE, LOCAL_TIME)
OFFSET_DATE_TIME = st.builds(lambda d,sep,t,off: d + sep + t + off, LOCAL_DATE, st.sampled_from(['T','t',' ']), LOCAL_TIME, _offset)

date_time = st.one_of(OFFSET_DATE_TIME, LOCAL_DATE_TIME, LOCAL_DATE, LOCAL_TIME)

# Atomic value strategy (non-container)
atomic_value = st.one_of(
    string_value,
    integer,
    floating_point,
    boolean,
    date_time,
)

# Helper to build key = value pair
@st.composite
def key_value_pair(draw, value_strategy):
    k = draw(key)
    v = draw(value_strategy)
    # sometimes add a comment at end
    if draw(st.booleans()):
        c = draw(st.text(alphabet=st.characters(blacklist_characters=['\r','\n','\x00']), min_size=0, max_size=40))
        if c:
            return f"{k} = {v} # {c}"
    return f"{k} = {v}"

# Inline table builder: no newlines inside (parser rejects newlines inside inline table)
def inline_table_from_children(children):
    # children: a strategy producing values as str
    # produce list of key=value entries, possibly empty, allow trailing comma
    kv = st.builds(lambda pairs, trail: "{" + (", ".join(pairs) + ("," if trail and pairs else "")) + "}",
                   st.lists(st.tuples(_unquoted_key, children), min_size=0, max_size=4).map(lambda lst: [f"{k} = {v}" for (k,v) in lst]),
                   st.booleans())
    return kv

# Recursive container strategy: arrays and inline tables
def arrays_and_inline_tables(base):
    # children is a strategy for allowed nested values
    array_builder = st.builds(
        lambda items, trailing: "[" + ", ".join(items) + ("," if trailing and items else "") + "]",
        st.lists(base, min_size=0, max_size=6),
        st.booleans()
    )
    inline_builder = inline_table_from_children(base)
    # nested array start (explicit nested brackets) helps create deep nesting
    nested_array = st.deferred(lambda: st.builds(lambda s: "[" + s + "]", base))
    return st.one_of(array_builder, inline_builder, nested_array)

# Use st.recursive to produce nested arrays and inline tables up to a reasonable complexity.
value = st.recursive(atomic_value, arrays_and_inline_tables, max_leaves=50)

# Deep nesting special-case: create extremely nested arrays (up to 2048 levels)
@st.composite
def deep_nested_array(draw):
    # Probability to produce extremely deep nesting is low but allowed
    depth = draw(st.integers(min_value=1, max_value=2048))
    # choose a simple element inside
    inner = draw(st.one_of(st.just("1"), string_value, integer, floating_point))
    # build nested string: [ [ [ inner ] ] ]
    s = "[" * depth + inner + "]" * depth
    return s

# Inline table sometimes with an explicit empty inline table
inline_table = st.one_of(inline_table_from_children(value), st.just("{}"))

# Array values also can be deep nested arrays occasionally
array_value = st.one_of(value, deep_nested_array())

# key_value using generated value strategy
kv = key_value_pair(value)

# Table header strategies: standard table [key] and array of tables [[key]]
standard_table = st.builds(lambda k: "[" + k + "]", key)
array_table = st.builds(lambda k: "[[" + k + "]]", key)
table_header = st.one_of(standard_table, array_table)

# Comment-only line
comment_line = st.builds(lambda c: "#" + c, st.text(alphabet=st.characters(blacklist_characters=['\x00', '\r', '\n']), min_size=0, max_size=80))

# Expression lines: key_value or table or comment; include possibility of malformed stray tokens or duplicate keys by repetition
@st.composite
def expression_line(draw):
    choice = draw(st.integers(min_value=0, max_value=6))
    if choice == 0:
        return draw(kv)
    if choice == 1:
        return draw(table_header)
    if choice == 2:
        return draw(comment_line)
    if choice == 3:
        # malformed: missing or doubled delimiter
        base = draw(kv)
        if draw(st.booleans()):
            # remove the '=' sometimes
            return base.replace(" = ", " ")
        else:
            # double equals
            return base.replace(" = ", " == ")
    if choice == 4:
        # duplicate keys: emit same key twice on one line separated by newline (parser will reject duplicate keys)
        k = draw(_unquoted_key)
        v1 = draw(value)
        v2 = draw(value)
        return f"{k} = {v1}\n{k} = {v2}"
    # stray token line
    return draw(st.one_of(st.just("]"), st.just("["), st.just("="), st.just("}"), st.just("{"), st.just("'''")))

# Build a document: sequence of expression lines and optional final newline (documents may have no trailing newline)
@st.composite
def document(draw):
    # number of top-level lines (allow empty documents and very large docs)
    n = draw(st.integers(min_value=0, max_value=30))
    parts = []
    for _ in range(n):
        parts.append(draw(expression_line()))
    # Optionally include some table + following keyvals (to create realistic tables)
    if draw(st.booleans()):
        # add a table header and some keyvals under it
        th = draw(table_header)
        parts.append(th)
        m = draw(st.integers(min_value=0, max_value=6))
        for _ in range(m):
            parts.append(draw(kv))
    # Optionally include an inline table assignment
    if draw(st.booleans()):
        k = draw(key)
        it = draw(inline_table)
        parts.append(f"{k} = {it}")
    # Optionally include comment-only or blank lines
    if draw(st.booleans()):
        # include blank line or comment
        if draw(st.booleans()):
            parts.insert(0, "")
        else:
            parts.insert(0, draw(comment_line))
    doc = "\n".join(parts)
    # Occasionally introduce CRLF endings or tabs indentation
    if draw(st.booleans()):
        doc = doc.replace("\n", draw(st.sampled_from(["\r\n", "\n"])))
    # Sometimes intentionally append a stray NUL escape \u0000 inside a string (safe as textual escape)
    if draw(st.booleans()):
        if '\\u0000' not in doc and draw(st.booleans()):
            # place a textual \u0000 somewhere in the document inside quotes if possible
            doc = doc + ("\n" + 'a = "\\u0000"')
    return doc

# Final top-level strategy: combine documents, but also include some specialized heavy/deep generators
strategy = st.one_of(
    document(),
    st.builds(lambda s: s, deep_nested_array()),
    # single-line documents focusing on specific value kinds
    st.builds(lambda v: "value = " + v, st.one_of(string_value, integer, floating_point, boolean, date_time, inline_table, array_value)),
    # empty document
    st.just(""),
    # comment-only document
    comment_line,
)
```