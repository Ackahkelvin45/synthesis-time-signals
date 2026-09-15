```python
from hypothesis import strategies as st
import json

# Helper alphabets (avoid raw NUL '\x00')
_ascii_printable_no_quote_backslash = "".join(
    chr(i)
    for i in range(1, 0x7F)
    if chr(i) not in ('"', "\\", "\n", "\r", "\x00")
)
_ascii_printable_no_singlequote = "".join(
    chr(i)
    for i in range(1, 0x7F)
    if chr(i) not in ("'", "\n", "\r", "\x00")
)
# Allow control chars except NUL, for raw-control-in-strings cases
_control_chars_no_nul = "".join(chr(i) for i in range(1, 0x20))

# Key strategies
unquoted_key = st.text(
    st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_"
    ),
    min_size=1,
    max_size=20
).filter(lambda s: all((c != '\x00') for c in s))

# Quoted basic string as key (a BASIC_STRING)
def basic_string_strategy(min_size=0, max_size=30, allow_control_raw=False, allow_escapes=True, unterminated=False):
    # produce content segments mixing raw chars and escapes
    raw_alpha = _ascii_printable_no_quote_backslash + ("\t" + _control_chars_no_nul if allow_control_raw else "")
    raw_piece = st.text(raw_alpha, min_size=0, max_size=8)
    # escape sequences
    esc_simple = st.sampled_from(['\\n','\\t','\\\\','\\\"','\\b','\\f','\\r','\\/'])
    esc_unicode = st.integers(0, 0xFFFF).map(lambda x: '\\u' + format(x, '04x'))
    esc_exunicode = st.integers(0, 0xFFFFFFFF).map(lambda x: '\\U' + format(x, '08x'))
    esc = st.one_of(esc_simple, esc_unicode, esc_exunicode)
    piece = st.one_of(raw_piece, esc) if allow_escapes else raw_piece
    return st.lists(piece, min_size=0, max_size=10).map(lambda parts: '"' + "".join(parts) + ('' if unterminated else '"'))

def literal_string_strategy(min_size=0, max_size=30, unterminated=False, allow_control_raw=False):
    raw_alpha = _ascii_printable_no_singlequote + ("\t" + _control_chars_no_nul if allow_control_raw else "")
    content = st.text(raw_alpha, min_size=0, max_size=40)
    return content.map(lambda c: "'" + c + ('' if unterminated else "'"))

def ml_basic_string_strategy(allow_escapes=True, unterminated=False):
    # Multiline basic allows newlines and escapes
    raw_piece = st.text(
        st.characters(whitelist_categories=("Lu","Ll","Nd","Zs"), blacklist_characters='\x00'),
        min_size=0, max_size=40
    )
    esc_simple = st.sampled_from(['\\n','\\t','\\\\','\\"','\\b','\\f','\\r','\\/'])
    esc_unicode = st.integers(0, 0xFFFF).map(lambda x: '\\u' + format(x, '04x'))
    esc_exunicode = st.integers(0, 0xFFFFFFFF).map(lambda x: '\\U' + format(x, '08x'))
    piece = st.one_of(raw_piece, esc_simple, esc_unicode, esc_exunicode) if allow_escapes else raw_piece
    return st.lists(piece, min_size=0, max_size=20).map(lambda parts: '"""' + "".join(parts) + ('' if unterminated else '"""'))

def ml_literal_string_strategy(unterminated=False):
    # Multiline literal string allows arbitrary except EOF terminator
    raw_piece = st.text(st.characters(blacklist_characters='\x00'), min_size=0, max_size=50)
    return st.lists(raw_piece, min_size=0, max_size=10).map(lambda parts: "'''" + "".join(parts) + ('' if unterminated else "'''"))

# Value strategies (non-recursive)
# Integers: decimal (allow leading zeros), hex, oct, bin with underscores and extremes
def dec_int_formatter(n):
    # allow leading zeros, underscores inserted randomly
    s = str(n)
    if n >= 0 and st.booleans().example():
        # sometimes add a '+' sign (use .example only to decide form; it's fine for diverse results)
        s = '+' + s
    # randomly insert underscores in decimal sequences
    # We create an underscore strategy instead of using example to avoid nondeterminism: do simple variants
    return s

dec_int = st.integers(min_value=-10**40, max_value=10**40).map(lambda n: str(n))
# Leading-zero variant
dec_leading_zero = st.integers(min_value=0, max_value=999).map(lambda n: ("0" + str(n)) if n < 1000 and n < 100 else str(n))

hex_int = st.integers(min_value=0, max_value=2**120).map(lambda n: "0x" + format(n, 'x'))
oct_int = st.integers(min_value=0, max_value=2**120).map(lambda n: "0o" + format(n, 'o'))
bin_int = st.integers(min_value=0, max_value=2**120).map(lambda n: "0b" + format(n, 'b'))

# Add underscores into ints occasionally
def with_underscores_int(s):
    # Insert underscores in digits sequences occasionally
    digits = list(s)
    if len(digits) <= 3:
        return s
    # insert up to 3 underscores at random positions (not at start)
    import random
    for _ in range(random.randint(0, 3)):
        pos = random.randint(1, len(digits)-1)
        digits.insert(pos, '_')
    return "".join(digits)

int_variants = st.one_of(
    dec_int.map(lambda s: s),
    dec_leading_zero,
    hex_int,
    oct_int,
    bin_int
).map(lambda s: with_underscores_int(s))

# Floats: normal, '1.', '.5', exponents, inf/nan
def make_float_variants():
    basic_float = st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: repr(f))
    # produce forms like '1.' or '.5'
    trailing_dot = st.integers(min_value=0, max_value=10).map(lambda n: str(n) + ".")
    leading_dot = st.integers(min_value=0, max_value=10).map(lambda n: "." + str(n))
    exponent = st.one_of(
        st.integers(min_value=-1000, max_value=1000).map(lambda e: "1e" + str(e)),
        st.integers(min_value=-1000, max_value=1000).map(lambda e: ".5e" + str(e)),
        st.integers(min_value=-1000, max_value=1000).map(lambda e: "1.234e" + str(e))
    )
    specials = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
    return st.one_of(basic_float, trailing_dot, leading_dot, exponent, specials)

float_variants = make_float_variants()

# Booleans
bool_variants = st.sampled_from(["true", "false"])

# Date/time variants (may be calendar-invalid as allowed)
def datetime_patterns():
    year = st.integers(min_value=0, max_value=9999).map(lambda x: format(x, '04d'))
    month = st.integers(min_value=1, max_value=12).map(lambda x: format(x, '02d'))
    day = st.integers(min_value=1, max_value=31).map(lambda x: format(x, '02d'))
    hour = st.integers(min_value=0, max_value=23).map(lambda x: format(x, '02d'))
    minute = st.integers(min_value=0, max_value=59).map(lambda x: format(x, '02d'))
    second = st.integers(min_value=0, max_value=59).map(lambda x: format(x, '02d'))
    frac = st.one_of(st.just(''), st.integers(min_value=0, max_value=999999999).map(lambda n: '.' + str(n)))
    offset = st.one_of(st.just('Z'), st.tuples(st.sampled_from(['+','-']), hour, minute).map(lambda t: t[0] + t[1] + ':' + t[2]))
    full_date = st.tuples(year, month, day).map(lambda t: t[0] + '-' + t[1] + '-' + t[2])
    partial_time = st.tuples(hour, minute, second, frac).map(lambda t: t[0] + ':' + t[1] + ':' + t[2] + (t[3] if t[3] else ''))
    offset_dt = st.tuples(full_date, st.sampled_from(['T','t',' ']), partial_time, offset).map(lambda t: t[0] + t[1] + t[2] + t[3])
    local_dt = st.tuples(full_date, st.sampled_from(['T','t',' ']), partial_time).map(lambda t: t[0] + t[1] + t[2])
    local_date = full_date
    local_time = partial_time
    return st.one_of(offset_dt, local_dt, local_date, local_time)

datetime_variants = datetime_patterns()

# String sorts (four kinds), including unterminated and malformed variants
basic_string = st.one_of(
    basic_string_strategy(allow_control_raw=False),
    basic_string_strategy(allow_control_raw=True),
    basic_string_strategy(allow_control_raw=True, unterminated=True)  # unterminated
)

literal_string = st.one_of(
    literal_string_strategy(),
    literal_string_strategy(unterminated=True)  # unterminated
)

ml_basic_string = st.one_of(
    ml_basic_string_strategy(),
    ml_basic_string_strategy(unterminated=True)
)

ml_literal_string = st.one_of(
    ml_literal_string_strategy(),
    ml_literal_string_strategy(unterminated=True)
)

string_variants = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Base values (non-recursive)
value_base = st.one_of(
    string_variants,
    int_variants,
    float_variants,
    bool_variants,
    datetime_variants
)

# Key as simple_key or dotted_key or quoted key variants
quoted_key_basic = basic_string_strategy().map(lambda s: s)  # already quoted
quoted_key_literal = literal_string_strategy().map(lambda s: s)
quoted_key = st.one_of(quoted_key_basic, quoted_key_literal)

simple_key = st.one_of(quoted_key, unquoted_key)
dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(lambda parts: ".".join(parts))

key = st.one_of(simple_key, dotted_key)

# Inline-table generation (recursive content allowed). Inline tables normally disallow newlines,
# but we include newline variants to produce near-valid malformed inputs.
def inline_table_factory(inner_values):
    # keyvals: zero or more "key = value" pairs separated by commas, allow trailing comma
    kv = st.tuples(
        st.one_of(quoted_key, unquoted_key, basic_string_strategy()),
        inner_values
    ).map(lambda t: (t[0] if isinstance(t[0], str) else str(t[0])) + " = " + t[1])
    kvs = st.lists(kv, min_size=0, max_size=5)
    # sometimes insert a newline inside to create malformed inline table
    def render(kv_list):
        if not kv_list:
            return "{ }"  # empty inline table with space
        import random
        if random.random() < 0.15:
            # malformed: include newline(s) inside inline table (parser rejects)
            inner = ", ".join(kv_list)
            # inject a newline inside
            inner = inner.replace(", ", ",\n", 1)
            # maybe leave trailing comma allowed
            if random.random() < 0.3:
                inner = inner + ","
            return "{" + inner + "}"
        else:
            # proper inline table; allow trailing comma occasionally
            inner = ", ".join(kv_list)
            if random.random() < 0.25:
                inner = inner + ","
            return "{" + inner + "}"
    return kvs.map(render)

# Array factory (recursive)
def array_factory(inner_values):
    # elements can be values with optional comments and newlines between (multi-line arrays)
    element = inner_values
    elements = st.lists(element, min_size=0, max_size=6)
    # include comments/newlines interleaved
    comment = st.text('#' + _ascii_printable_no_quote_backslash, min_size=0, max_size=30)
    def render(elts):
        # build array text, sometimes multiline with comments, sometimes trailing comma
        import random
        if not elts:
            return "[]"
        if random.random() < 0.4:
            # multiline with comments/newlines
            parts = []
            for e in elts:
                if random.random() < 0.3:
                    parts.append("\n  " + e + "  # comment")
                else:
                    parts.append("\n  " + e)
            trailing = "," if random.random() < 0.5 else ""
            return "[" + ",".join(parts) + trailing + "\n]"
        else:
            # single-line
            inner = ", ".join(elts)
            if random.random() < 0.25:
                inner = inner + ","
            return "[" + inner + "]"
    return elements.map(render)

# Compose recursive values: arrays and inline tables may contain nested arrays/inline tables
containers = lambda children: st.one_of(
    array_factory(children),
    inline_table_factory(children)
)

recursive_values = st.recursive(value_base, containers, max_leaves=2048)

# Key-value line, table header (standard or array table), or comment-only line
def key_value_line(value_strategy):
    # sometimes produce malformed variations: missing '=', '==', stray tokens
    def make(k, v):
        import random
        variant = random.random()
        if variant < 0.05:
            # missing equals (near-valid but malformed)
            return (k + " " + v)
        elif variant < 0.10:
            # double equals
            return (k + " == " + v)
        elif variant < 0.15:
            # stray token before/after
            return ("stray " + k + " = " + v + " extra")
        else:
            return k + " = " + v
    return st.tuples(key, value_strategy).map(lambda t: make(t[0], t[1]))

def table_line():
    # standard table [key] or array table [[key]]
    # sometimes malformed: missing closing bracket, extra bracket, triple-bracket
    def render(k):
        import random
        if random.random() < 0.08:
            return "[[" + k + "]]]"  # extra bracket
        if random.random() < 0.06:
            return "[" + k  # missing closing bracket
        if random.random() < 0.05:
            return "[[[%s]]" % k  # doubled start
        if random.random() < 0.2:
            # array table
            return "[[" + k + "]]"
        else:
            return "[" + k + "]"
    return key.map(render)

comment_line = st.one_of(
    st.just(""),  # empty line
    st.text("#" + _ascii_printable_no_quote_backslash, min_size=0, max_size=50),
    st.just("#")  # comment with no text
)

# Expression: key-value, table, or comment
expression = st.deferred(lambda: st.one_of(
    key_value_line(recursive_values),
    table_line(),
    comment_line
))

# Compose documents: multiple expressions separated by newlines. Include empty documents and comment-only docs.
def document_builder():
    # length varied, include possibility of very large key names and duplicate keys/tables
    def mk_doc(exprs):
        import random
        # ensure there's variety: sometimes inject long key name and super-deep nesting single expression
        if random.random() < 0.05:
            # produce a super-deep nested array (attempt deep nesting). Build a textual deep nesting literal.
            depth = random.choice([100, 512, 1024, 1500, 2048])
            inner = "1"
            for _ in range(depth):
                inner = "[" + inner + "]"
            return "deep = " + inner + "\n"
        # else join expressions with CRLF or LF occasionally
        sep = "\r\n" if random.random() < 0.1 else "\n"
        return sep.join(exprs)
    return st.lists(expression, min_size=0, max_size=20).map(mk_doc)

# Top-level strategy
strategy = document_builder()
```