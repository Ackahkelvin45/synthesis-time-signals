```python
from hypothesis import strategies as st
import json

# Helper character sets (avoid NUL (codepoint 0) everywhere)
_safe_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters='"\n\r\\')
_safe_char_allow_quote = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters='\n\r\\')
_safe_key_char = st.characters(min_codepoint=0x30, max_codepoint=0x7A)  # rough ascii range for keys

# Unquoted key (may include non-ASCII occasionally to exercise rejection)
unquoted_key = st.one_of(
    st.from_regex(r'[A-Za-z0-9_-]{1,20}', fullmatch=True),
    st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF))  # non-ASCII bare key (likely rejected)
)

# Very long key (10k chars) to hit extremes
very_long_key = st.just("k" * 10000)

# Quoted keys (BASIC or LITERAL forms included as full textual tokens)
def basic_string_token(content):
    return '"' + content + '"'

def literal_string_token(content):
    return "'" + content + "'"

# Escapes to include inside basic strings (valid and invalid)
_escape_choices = st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\"', '\\\\', '\\u0000', '\\u00E9', '\\U0001F600', '\\q'])

# Basic (single-line) string content: mix of safe raw chars and escapes; raw control chars (except NUL) are allowed
basic_string_content = st.lists(st.one_of(_safe_char, _escape_choices), min_size=0, max_size=20).map(lambda pieces: "".join(pieces))
basic_string = basic_string_content.map(lambda c: '"' + c + '"')

# Unterminated basic string (near-valid-but-malformed)
unterminated_basic_string = basic_string_content.map(lambda c: '"' + c)  # missing closing quote

# Multiline basic string
ml_basic_string_content = st.lists(st.one_of(
    st.text(min_size=0, max_size=10, alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters='\\')),  # allow newlines below by joining
    _escape_choices
), min_size=0, max_size=30).map(lambda parts: "\n".join(parts))
ml_basic_string = ml_basic_string_content.map(lambda c: '"""' + c + '"""')

# Literal string (single-line) - no escapes interpreted
literal_string_content = st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="'\n\r"))
literal_string = literal_string_content.map(lambda c: "'" + c + "'")

# Multiline literal string (triple single quotes)
ml_literal_string_content = st.text(min_size=0, max_size=200, alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF))
ml_literal_string = ml_literal_string_content.map(lambda c: "'''" + c + "'''")

# Aggregate string strategy, include unterminated and invalid escapes occasionally
string_value = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    unterminated_basic_string,  # malformed
)

# Integer formatting helpers
def insert_underscores(s):
    # insert underscores randomly between digits
    import random
    if len(s) <= 3:
        return s
    parts = []
    i = 0
    while i < len(s):
        take = random.randint(1, 3)
        parts.append(s[i:i+take])
        i += take
    return "_".join(parts)

@st.composite
def dec_int_str(draw):
    n = draw(st.integers(min_value=-10**50, max_value=10**50))
    s = str(n)
    # occasionally produce leading zeros like '007'
    if draw(st.booleans()):
        if s.startswith('-'):
            body = s[1:]
            s = '-' + ('0' * draw(st.integers(min_value=1, max_value=3))) + body
        else:
            s = ('0' * draw(st.integers(min_value=1, max_value=3))) + s
    # occasionally add underscores
    if draw(st.booleans()):
        sign = ''
        if s.startswith('-') or s.startswith('+'):
            sign, s = s[0], s[1:]
        s = sign + insert_underscores(s)
    return s

@st.composite
def hex_int_str(draw):
    n = draw(st.integers(min_value=0, max_value=2**128))
    s = format(n, 'x')
    # insert underscores sometimes
    if draw(st.booleans()):
        s = insert_underscores(s)
    return "0x" + s

@st.composite
def oct_int_str(draw):
    n = draw(st.integers(min_value=0, max_value=2**100))
    s = format(n, 'o')
    if draw(st.booleans()):
        s = insert_underscores(s)
    return "0o" + s

@st.composite
def bin_int_str(draw):
    n = draw(st.integers(min_value=0, max_value=2**100))
    s = format(n, 'b')
    if draw(st.booleans()):
        s = insert_underscores(s)
    return "0b" + s

integer_value = st.one_of(dec_int_str(), hex_int_str(), oct_int_str(), bin_int_str())

# Floating point: include formats like '1.', '.5', scientific, inf/nan variants, extremes
@st.composite
def float_value(draw):
    choice = draw(st.integers(min_value=0, max_value=6))
    if choice == 0:
        # 1.  (no digits after dot)
        i = draw(st.integers(min_value=-10**10, max_value=10**10))
        return str(i) + "."
    if choice == 1:
        # .5 (no leading digit)
        frac = draw(st.integers(min_value=0, max_value=9999))
        return "." + str(frac)
    if choice == 2:
        # normal float with optional exponent
        f = draw(st.floats(allow_nan=False, allow_infinity=False, min_value=-1e308, max_value=1e308))
        # produce scientific sometimes
        if draw(st.booleans()):
            return "{:.6e}".format(f)
        else:
            return repr(f)
    if choice == 3:
        # big exponent overflowing (1e309)
        sign = "-" if draw(st.booleans()) else ""
        return sign + "1e" + str(draw(st.integers(min_value=308, max_value=5000)))
    if choice == 4:
        return draw(st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan"]))
    return draw(st.sampled_from(["1.", ".5", "0.0", "3.14159"]))

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time generation (calendar-invalid allowed)
@st.composite
def date_time_value(draw):
    year = draw(st.integers(min_value=0, max_value=9999))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=31))  # allow invalid days deliberately
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    frac = ""
    if draw(st.booleans()):
        frac = "." + str(draw(st.integers(min_value=0, max_value=999999)))
    # choose form
    form = draw(st.integers(min_value=0, max_value=3))
    if form == 0:
        # offset date-time
        offset = draw(st.sampled_from(["Z", "+00:00", "-05:00", "+12:34"]))
        return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}{frac}{offset}"
    if form == 1:
        # local date-time
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}{frac}"
    if form == 2:
        # local date
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{hour:02d}:{minute:02d}:{second:02d}{frac}"

date_time_value = date_time_value()

# Atomic (non-recursive) values
atomic_value = st.one_of(
    string_value,
    integer_value,
    float_value(),
    bool_value,
    date_time_value
)

# Key representations: unquoted, quoted (basic/literal), or very long key
quoted_key_variant = st.one_of(
    basic_string.map(lambda s: s),
    literal_string.map(lambda s: s),
    st.just('""')  # empty quoted key
)
key_repr = st.one_of(unquoted_key, quoted_key_variant, very_long_key)

# Now build recursive values (arrays and inline tables) using st.recursive
def make_array_from_children(children):
    # arrays: empty arrays, arrays with multiple values, nested single-element arrays (to deepen)
    return st.one_of(
        st.lists(children, min_size=0, max_size=5).map(
            lambda items: "[" + ", ".join(items) + ("," if (len(items) and len(items) % 2 == 0) else "") + "]"
        ),
        # single-nested array (increase depth)
        children.map(lambda c: "[" + c + "]"),
        # multiline arrays with comments-like fragments inserted (simulate comments/newlines)
        st.lists(children, min_size=0, max_size=4).map(lambda items: "[\n" + ",\n".join("# comment\n" + it if i % 2 == 0 else it for i, it in enumerate(items)) + (",\n" if items else "") + "]")
    )

def make_inline_table_from_children(children):
    # inline tables: empty, with keyvals, with trailing comma, sometimes with a newline inside (malformed)
    keyval = st.tuples(key_repr, children).map(lambda kv: (kv[0], kv[1]))
    normal = st.lists(keyval, min_size=0, max_size=5).map(
        lambda kvs: "{" + ", ".join(k + " = " + v for k, v in kvs) + ("," if (len(kvs) and len(kvs) % 2 == 1) else "") + "}"
    )
    with_newline = st.lists(keyval, min_size=1, max_size=4).map(
        lambda kvs: "{" + ",\n".join(k + " = " + v for k, v in kvs) + "}"
    )  # newline inside inline table (grammar rejects; include as malformed)
    return st.one_of(normal, with_newline)

# recursive values strategy
recursive_value = st.recursive(
    atomic_value,
    lambda children: st.one_of(
        make_array_from_children(children),
        make_inline_table_from_children(children)
    ),
    max_leaves=2000
)

# Value strategy used in key_value (also include stray tokens and near-valid malformed values)
value_repr = st.one_of(
    recursive_value,
    st.just("]"),            # stray token
    st.just("=="),           # doubled delimiter
    st.just(""),             # empty (missing value)
)

# Key-value line variants (including malformed like missing '=')
@st.composite
def key_value_line(draw):
    k = draw(key_repr)
    v = draw(value_repr)
    form = draw(st.integers(min_value=0, max_value=5))
    if form == 0:
        # normal
        return f"{k} = {v}"
    if form == 1:
        # missing equals
        return f"{k} {v}"
    if form == 2:
        # doubled equals
        return f"{k} == {v}"
    if form == 3:
        # stray bracket prefix
        return f"] {k} = {v}"
    return f"{k} = {v}"  # fallback

# Table lines: standard and array of tables
standard_table = st.tuples(st.just('['), key_repr, st.just(']')).map(lambda t: t[0] + t[1] + t[2])
array_table = st.tuples(st.just('[['), key_repr, st.just(']]')).map(lambda t: t[0] + t[1] + t[2])

# Comment-only line (including control characters inside comment)
comment_line = st.one_of(
    st.just(""),  # empty line
    st.text(min_size=0, max_size=80, alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF)).map(lambda s: "#" + s),
    st.just("#\tcomment with tab"),
    st.just("# comment with ASCII and 控制")  # non-ASCII comment
)

# An expression is key_value, table (standard or array), or comment
expression = st.one_of(
    key_value_line(),
    standard_table,
    array_table,
    comment_line
)

# Document: zero or more expressions separated by newlines; also include documents with no trailing newline
@st.composite
def document(draw):
    lines = draw(st.lists(expression, min_size=0, max_size=30))
    # Occasionally produce very deep nested single-line array (1500-2048) to exercise recursion depth
    if draw(st.booleans()):
        if draw(st.integers(min_value=0, max_value=10)) == 0:
            depth = draw(st.integers(min_value=1500, max_value=2048))
            inner = draw(st.one_of(atomic_value, st.just("1")))
            deep = ("[" * depth) + inner + ("]" * depth)
            lines.append("deep = " + deep)
    doc = "\n".join(lines)
    # Occasionally drop final newline (documents with no trailing newline)
    return doc

# Top-level exported strategy producing str (complete TOML candidate documents)
strategy = document()
```