from hypothesis import strategies as st
import json

# Helper character classes (avoid raw NUL \x00)
_ASCII_LETTERS = ''.join([chr(c) for c in range(0x20, 0x7f) if chr(c) != '\x00'])
_ASCII_PRINTABLE = ''.join([chr(c) for c in range(0x21, 0x7f) if chr(c) != '\x00'])
_CONTROL_BYTES = ''.join(chr(c) for c in range(1, 0x20) if c != 0)  # allow control bytes except NUL
_NON_ASCII = ''.join(chr(c) for c in range(0x80, 0x100))

# Basic building blocks

# Unquoted bare key: ASCII letters, digits, '-' and '_' only (parser rejects non-ASCII bare keys)
unquoted_key = st.text(
    alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')).filter(lambda ch: ch.isascii()) | st.just('-') | st.just('_'),
    min_size=1,
    max_size=10000
).map(lambda s: ''.join(c for c in s if (c.isalnum() or c in '-_'))[:10000]).filter(lambda s: len(s) > 0)

# Quoted keys (BASIC_STRING or LITERAL_STRING) may include non-ASCII and escapes
_basic_string_content = st.text(alphabet=st.characters(blacklist_characters=['"', '\n', '\r', '\x00']))  # raw content (no raw newline or NUL or quote)
# allow control bytes inside basic strings (except NUL) by explicit sampling
_basic_string_with_ctrl = st.one_of(
    _basic_string_content,
    st.text(alphabet=st.characters(whitelist_categories=(), blacklist_characters=['\n', '\r', '\x00'])).filter(lambda s: any('\x01' <= ch <= '\x1f' for ch in s)).map(lambda s: s)
)

def escape_basic(s: str) -> str:
    # Replace special backslashable chars with escapes or keep raw control bytes sometimes
    out = []
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\t':
            out.append('\\t')
        elif ch == '\b':
            out.append('\\b')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        else:
            # for control bytes (except NUL) choose raw or \uXXXX escape
            code = ord(ch)
            if 1 <= code <= 0x1f:
                # mix raw and escaped control bytes
                if code % 3 == 0:
                    out.append('\\u%04x' % code)
                else:
                    out.append(ch)
            elif code >= 0x80:
                # sometimes use \uXXXX or raw non-ascii
                if code % 2 == 0:
                    out.append('\\u%04x' % code)
                else:
                    out.append(ch)
            else:
                out.append(ch)
    return ''.join(out)

# Basic string strategy (valid, with escapes, and near-invalid variants)
basic_string_valid = _basic_string_with_ctrl.map(lambda s: '"' + escape_basic(s) + '"')

# Unterminated or malformed basic strings (near-valid-but-malformed)
basic_string_unterminated = _basic_string_with_ctrl.map(lambda s: '"' + escape_basic(s))  # missing trailing quote
basic_string_bad_escape = st.text(alphabet=st.characters(blacklist_characters=['"', '\n', '\r', '\x00', '\\'])) \
    .map(lambda s: '"' + s + '\\q' + '"' )  # invalid escape \q inside

basic_string = st.one_of(basic_string_valid, basic_string_unterminated, basic_string_bad_escape)

# Multiline basic triple-quoted strings (valid and unterminated)
ml_basic_inner = st.text(alphabet=st.characters(blacklist_characters=['\x00']))  # allow newlines
ml_basic_valid = ml_basic_inner.map(lambda s: '"""' + s + '"""')
ml_basic_unterminated = ml_basic_inner.map(lambda s: '"""' + s)  # missing closing
ml_basic = st.one_of(ml_basic_valid, ml_basic_unterminated)

# Literal single-quoted strings (no escapes inside) and multiline literal
literal_inner = st.text(alphabet=st.characters(blacklist_characters=["'", '\x00', '\r']))  # no raw NUL
literal_valid = literal_inner.map(lambda s: "'" + s + "'")
ml_literal_inner = st.text(alphabet=st.characters(blacklist_characters=['\x00']))  # allow multiline
ml_literal_valid = ml_literal_inner.map(lambda s: "'''" + s + "'''")
literal_string = st.one_of(literal_valid, ml_literal_valid)

# Integer strategies: decimal (with leading zeros allowed), hex/octal/bin, big magnitudes and underscores
def decimal_with_underscores():
    # produce leading zeros sometimes and underscores
    base = st.integers(min_value=0, max_value=10**40).map(str)
    with_leading = st.one_of(base, base.map(lambda s: (('0'*(s.count('0')%3)) + s)))  # sometimes add leading zeros
    def insert_underscores(s):
        if len(s) < 2:
            return s
        parts = []
        i = 0
        while i < len(s):
            take = 1 + (i % 3 == 0)
            parts.append(s[i:i+take])
            i += take
        return '_'.join(parts)
    return st.one_of(with_leading, with_leading.map(insert_underscores)).map(lambda s: s if s != '' else '0')

dec_int = st.one_of(
    # positive and negative
    decimal_with_underscores().map(lambda s: s),
    st.integers(min_value=-10**40, max_value=10**40).map(str)
)

hex_int = st.integers(min_value=0, max_value=2**128).map(lambda v: hex(v).replace('0x', '0x') )
# allow underscores in hex digits
hex_with_underscores = hex_int.map(lambda s: s[:2] + '_'.join([s[i:i+2] for i in range(2, len(s), 2)]))

oct_int = st.integers(min_value=0, max_value=2**80).map(lambda v: oct(v).replace('0o', '0o'))
bin_int = st.integers(min_value=0, max_value=2**80).map(lambda v: bin(v).replace('0b', '0b'))

integer = st.one_of(
    dec_int,
    hex_with_underscores,
    oct_int,
    bin_int
)

# Floating point: include 1., .5, exponentials, inf/nan
float_decimal = st.one_of(
    # standard floats
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, 'g')),
    # 1. and .5 forms
    st.one_of(st.integers(min_value=0, max_value=10**6).map(lambda i: str(i) + '.'),
              st.integers(min_value=0, max_value=10**6).map(lambda i: '.' + str(i))),
    # large exponents
    st.integers(min_value=-400, max_value=400).flatmap(lambda e: st.integers(min_value=1, max_value=10**10).map(lambda m: f"{m}e{e}")),
)
float_inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
floating_point = st.one_of(float_decimal, float_inf_nan)

# Booleans
bool_ = st.sampled_from(['true', 'false'])

# Date/time forms (no need to be calendar-valid always)
def gen_date():
    year = st.integers(min_value=0, max_value=9999).map(lambda y: f"{y:04d}")
    month = st.integers(min_value=1, max_value=12).map(lambda m: f"{m:02d}")
    day = st.integers(min_value=1, max_value=31).map(lambda d: f"{d:02d}")
    hour = st.integers(min_value=0, max_value=23).map(lambda h: f"{h:02d}")
    minute = st.integers(min_value=0, max_value=59).map(lambda m: f"{m:02d}")
    second = st.integers(min_value=0, max_value=59).map(lambda s: f"{s:02d}")
    frac = st.one_of(st.just(''), st.integers(min_value=1, max_value=999999999).map(lambda x: '.' + str(x)))
    offset = st.one_of(st.just('Z'), st.tuples(st.one_of(st.just('+'), st.just('-')), hour, st.just(':'), minute).map(lambda t: t[0] + t[1] + t[2] + t[3]))
    # Compose different date/time forms
    odt = st.tuples(year, month, day, st.one_of(st.just('T'), st.just(' ')), hour, st.just(':'), minute, st.just(':'), second, frac, offset) \
        .map(lambda t: f"{t[0]}-{t[1]}-{t[2]}{t[3]}{t[4]}{t[5]}{t[6]}{t[7]}{t[8]}{t[9]}{t[10]}")
    ldt = st.tuples(year, month, day, st.one_of(st.just('T'), st.just(' ')), hour, st.just(':'), minute, st.just(':'), second, frac) \
        .map(lambda t: f"{t[0]}-{t[1]}-{t[2]}{t[3]}{t[4]}{t[5]}{t[6]}{t[7]}{t[8]}{t[9]}")
    ld = st.tuples(year, month, day).map(lambda t: f"{t[0]}-{t[1]}-{t[2]}")
    lt = st.tuples(hour, st.just(':'), minute, st.just(':'), second, frac).map(lambda t: f"{t[0]}{t[1]}{t[2]}{t[3]}{t[4]}{t[5]}")
    return st.one_of(odt, ldt, ld, lt)

date_time = gen_date()

# Base value strategy (non-recursive)
base_value = st.one_of(
    basic_string,
    ml_basic,
    literal_string,
    integer,
    floating_point,
    bool_,
    date_time
)

# Now recursive construction for arrays and inline tables
# Use deferred strategy to allow recursion
value = st.deferred()

# Helper: make array strings from child value strategy
def array_of(child):
    # Elements possibly separated with commas, spaces, comments, newlines; allow trailing comma
    elems = st.lists(child, min_size=0, max_size=6)
    # Format either inline or multiline
    inline = elems.map(lambda L: "[" + ", ".join(L) + ("," if (len(L)>0 and (len(L)%2==0)) else "") + "]")
    # multiline with comments and optional commas and newlines
    def mk_multiline(L):
        if not L:
            return "[]"
        lines = []
        for i, v in enumerate(L):
            # embed occasional comments
            c = (" #"+json.dumps(v)[:10]) if (i % 3 == 0) else ""
            comma = "," if i != len(L)-1 or (len(L) % 2 == 0) else ""
            lines.append("  " + v + comma + c)
        return "[\n" + "\n".join(lines) + "\n]"
    multiline = elems.map(mk_multiline)
    # Malformed variants: missing closing bracket, doubled comma, stray token
    malformed = elems.map(lambda L: "[" + ", ".join(L) + (",," if len(L)%2==0 else "") )
    return st.one_of(inline, multiline, malformed)

# Helper: inline table creation from child
def inline_table_of(child):
    kvs = st.lists(st.tuples(unquoted_key, child), min_size=0, max_size=6)
    def mk_inline(pairs):
        # occasionally insert newline (which is invalid for inline tables per grammar)
        parts = []
        for k, v in pairs:
            parts.append(f"{k} = {v}")
        body = ", ".join(parts)
        # allow trailing comma occasionally
        if len(parts) and (len(parts) % 2 == 0):
            body = body + ","
        if pairs and (len(parts) % 3 == 0):
            # insert newline inside inline table (near-invalid)
            body = body.replace(", ", ",\n", 1)
        return "{" + body + "}"
    # malformed: missing closing brace or stray tokens
    malformed_missing = kvs.map(lambda pairs: "{" + ", ".join(f"{k} = {v}" for k, v in pairs))
    malformed_stray = kvs.map(lambda pairs: "{" + ", ".join(f"{k} = {v}" for k, v in pairs) + " :: }")
    return st.one_of(kvs.map(mk_inline), malformed_missing, malformed_stray)

# Compose recursive strategy (arrays and inline tables can nest)
value_strategy = st.recursive(
    base_value,
    lambda children: st.one_of(
        array_of(children),
        inline_table_of(children)
    ),
    max_leaves=2500
)

# Assign deferred
value.strategy = value_strategy

# Keys: simple_key or dotted (combination)
simple_key = st.one_of(
    unquoted_key,
    basic_string_valid,  # quoted key as basic string (valid)
    literal_valid        # quoted key as literal string
)

dotted_key = st.lists(simple_key, min_size=2, max_size=5).map(lambda parts: ".".join(p.strip() for p in parts))

key = st.one_of(simple_key, dotted_key)

# key-value line generator: include space variants around '=', comments, near-malformed equals
def kv_line(k, v):
    # randomness handled by strategies; allow missing =, double =, or correct
    return st.one_of(
        st.just(f"{k} = {v}"),
        st.just(f"{k}={v}"),
        st.just(f"{k}  =  {v}"),
        st.just(f"{k} == {v}"),   # doubled equals (near-malformed)
        st.just(f"{k} {v}")       # missing equals (near-malformed)
    )

kv_strategy = st.tuples(key, value).flatmap(lambda kv: kv_line(kv[0], kv[1]))

# Table lines
standard_table = key.map(lambda k: "[" + k + "]")
array_table = key.map(lambda k: "[[" + k + "]]")

table_strategy = st.one_of(standard_table, array_table)

# Comment line (including empty comment or raw control characters)
comment_line = st.one_of(
    st.just(""),
    st.text(alphabet=st.characters(blacklist_characters=['\n', '\r', '\x00'])).map(lambda s: "#" + s),
    st.just("#")  # empty comment
)

# Expression can be key_value, table, or comment. Allow comment-only and empty documents.
expression = st.one_of(kv_strategy, table_strategy, comment_line)

# Document: sequence of expressions separated by newlines. Include empty doc and comment-only.
def mk_doc(exprs):
    # join with CRLF or LF sometimes
    sep = "\r\n" if (len(exprs) % 5 == 0) else "\n"
    doc = sep.join(exprs)
    # occasionally append stray token at end
    if len(exprs) % 7 == 0:
        doc = doc + ("" if len(exprs) % 2 else "\n") + "]"
    # sometimes no trailing newline
    return doc

# Build possibility of duplicate keys by intentionally repeating some keys
def with_duplicates(exprs):
    # randomly duplicate some lines to create duplicate keys/tables
    if not exprs:
        return exprs
    out = list(exprs)
    if len(exprs) > 0 and len(exprs) % 2 == 0:
        # duplicate the first kv if it's a kv-like (contains '=')
        for i, e in enumerate(exprs):
            if '=' in e:
                out.insert(i+1, e)
                break
    return out

doc_core = st.lists(expression, min_size=0, max_size=20).map(lambda L: with_duplicates(L)).map(mk_doc)

# Also add targeted deep-nesting array documents (concentrate interesting depth in 1500-2048)
def deep_array_doc_strategy():
    # depth between 1500 and 2048 occasionally, else smaller depths
    depth = st.one_of(
        st.integers(min_value=1500, max_value=2048),
        st.integers(min_value=0, max_value=50)
    )
    # inner value choose from small literals
    inner = st.one_of(st.just("1"), basic_string_valid, literal_valid)
    return st.tuples(depth, inner).map(lambda di: ("[" * di) + di[1] + ("]" * di[0]))

deep_array_value = deep_array_doc_strategy()

# Final strategy: occasionally produce a deep array as whole document, else general document
strategy = st.one_of(
    doc_core,
    deep_array_value,
    st.just("")  # empty document
)