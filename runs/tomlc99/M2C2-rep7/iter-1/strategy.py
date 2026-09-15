from hypothesis import strategies as st
import json

# Helpers
_non_nul_control = ''.join(chr(i) for i in range(1, 0x20) if i != 0)  # control bytes except NUL
_non_quote_basic = ''.join(chr(i) for i in range(0x20, 0x7F) if i not in (0x22, 0x5C, 0x0A))  # exclude " \ and newline
_non_quote_basic += _non_nul_control  # allow raw control bytes (except NUL)
_unicode_letters = ''.join(chr(i) for i in range(0x80, 0x1000))  # some non-ASCII to use inside quoted strings

# Character strategies used for string content
basic_content = st.text(alphabet=st.characters(
    blacklist_characters='"\n\\\x00'), min_size=0, max_size=40).filter(lambda s: '\x00' not in s)
# allow explicit control bytes (except NUL)
control_inserts = st.text(alphabet=_non_nul_control, min_size=0, max_size=4)
extended_unicode = st.text(alphabet=_unicode_letters, min_size=0, max_size=10)

escape_seq = st.one_of(
    st.just('\\n'), st.just('\\t'), st.just('\\r'), st.just('\\\\'),
    st.builds(lambda h: '\\u%04x' % h, st.integers(0, 0xFFFF)),
    st.builds(lambda h: '\\U%08x' % h, st.integers(0, 0x10FFFF)),
    st.just('\\q')  # invalid escape to trigger near-valid-but-malformed
)

# Basic (double-quoted) string strategy: include well-formed, escaped, and unterminated variants
basic_string = st.one_of(
    st.builds(lambda a, b, e: '"' + a + e + b + '"',
              basic_content, extended_unicode, escape_seq),
    st.builds(lambda a, b: '"' + a + b + '"', basic_content, control_inserts),
    # unterminated (missing closing quote)
    st.builds(lambda a: '"' + a, st.text(alphabet=st.characters(blacklist_characters='"\x00\n\\'), max_size=40)),
    # raw control characters inside (accepted by parser)
    st.builds(lambda a: '"' + a + '"', st.text(alphabet=_non_nul_control + _non_quote_basic, max_size=30)),
)

# Literal (single-quoted) string strategy: no escapes, can be empty
literal_string = st.one_of(
    st.builds(lambda s: "'" + s + "'", st.text(alphabet=st.characters(blacklist_characters="'\n\x00"), max_size=40)),
    # unterminated literal
    st.builds(lambda s: "'" + s, st.text(alphabet=st.characters(blacklist_characters="'\x00\n"), max_size=40)),
    # empty literal key often used: ''
    st.just("''"),
)

# Multiline basic string (triple double quotes)
ml_basic_string = st.one_of(
    st.builds(lambda s: '"""' + s + '"""', st.text(alphabet=st.characters(blacklist_characters='\x00'), min_size=0, max_size=120)),
    st.builds(lambda s: '"""' + s, st.text(alphabet=st.characters(blacklist_characters='\x00'), min_size=0, max_size=120)),  # unterminated
)

# Multiline literal string (triple single quotes)
ml_literal_string = st.one_of(
    st.builds(lambda s: "'''" + s + "'''", st.text(alphabet=st.characters(blacklist_characters='\x00'), min_size=0, max_size=120)),
    st.builds(lambda s: "'''" + s, st.text(alphabet=st.characters(blacklist_characters='\x00'), min_size=0, max_size=120)),  # unterminated
)

# All string forms
string_value = st.one_of(basic_string, ml_basic_string, literal_string, ml_literal_string)

# Integer forms
def fmt_underscored_decimal(n):
    s = str(abs(n))
    # inject some underscores
    if len(s) > 3:
        s = '_'.join([s[max(0, i-3):i] for i in range(len(s) % 3 or 3, len(s)+1, 3)])
    if n < 0:
        return '-' + s
    return s

decimal_int = st.integers(min_value=-10**40, max_value=10**40).map(lambda n: fmt_underscored_decimal(n))
leading_zero_int = st.builds(lambda n: ('+' if n >= 0 and st.booleans().example() else '') + '0' + str(abs(n)), st.integers(min_value=0, max_value=999)).map(lambda s: s)  # will create leading zeros sometimes
hex_int = st.builds(lambda x: '0x' + x, st.text(alphabet='0123456789ABCDEFabcdef', min_size=1, max_size=16)).map(lambda s: s)
oct_int = st.builds(lambda x: '0o' + x, st.text(alphabet='01234567', min_size=1, max_size=22)).map(lambda s: s)
bin_int = st.builds(lambda x: '0b' + x, st.text(alphabet='01', min_size=1, max_size=64)).map(lambda s: s)

integer_value = st.one_of(decimal_int, hex_int, oct_int, bin_int, leading_zero_int)

# Float forms including .5, 1., exponent extremes, inf/nan
float_plain = st.one_of(
    st.builds(lambda s: s + '.0', st.text(alphabet='0123456789', min_size=1, max_size=20)),
    st.builds(lambda s: s + '.', st.text(alphabet='0123456789', min_size=1, max_size=20)),
    st.builds(lambda s: '.' + s, st.text(alphabet='0123456789', min_size=1, max_size=20)),
    st.builds(lambda a, e: a + 'e' + e, st.text(alphabet='0123456789', min_size=1, max_size=20), st.text(alphabet='+-' + '0123456789', min_size=1, max_size=5)),
)
float_inf_nan = st.one_of(st.just('inf'), st.just('-inf'), st.just('+inf'), st.just('nan'), st.just('-nan'), st.just('+nan'))
float_value = st.one_of(float_plain, float_inf_nan)

# Boolean
bool_value = st.one_of(st.just('true'), st.just('false'))

# Date/time forms (fields can be calendar-invalid)
def padded(n, width=2):
    return str(n).zfill(width)

date_field = st.tuples(st.integers(0, 9999), st.integers(1, 12), st.integers(1, 31)).map(
    lambda t: f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"
)
time_field = st.tuples(st.integers(0, 23), st.integers(0, 59), st.integers(0, 61), st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(alphabet='0123456789', min_size=1, max_size=6)))).map(
    lambda t: f"{t[0]:02d}:{t[1]:02d}:{t[2]:02d}{t[3]}"
)
offset = st.one_of(st.just('Z'), st.builds(lambda h, m, sgn: f"{'+' if sgn==0 else '-'}{h:02d}:{m:02d}", st.integers(0, 23), st.integers(0, 59), st.integers(0,1)))

offset_datetime = st.tuples(date_field, time_field, offset).map(lambda t: t[0] + 'T' + t[1] + t[2])
local_datetime = st.tuples(date_field, time_field).map(lambda t: t[0] + 'T' + t[1])
local_date = date_field
local_time = time_field

datetime_value = st.one_of(offset_datetime, local_datetime, local_date, local_time)

# Base non-recursive value strategy (all atomic, no arrays or inline tables)
base_value = st.one_of(string_value, integer_value, float_value, bool_value, datetime_value)

# Key generation: unquoted and quoted keys, include large keys and empty quoted key
unquoted_key = st.text(alphabet=st.characters(whitelist_categories=('Lu','Ll','Nd')) | st.just('-') | st.just('_'),
                       min_size=1, max_size=10000).filter(lambda s: all(ord(c) < 128 for c in s))  # bare keys must be ASCII
quoted_key_basic = basic_string
quoted_key_literal = literal_string
quoted_key = st.one_of(quoted_key_basic, quoted_key_literal)
key_simple = st.one_of(quoted_key, unquoted_key)

# Dotted key: join simple keys with dots
dotted_key = st.lists(key_simple, min_size=2, max_size=6).map(lambda parts: '.'.join(parts))

key = st.one_of(key_simple, dotted_key)

# Recursive generation for arrays and inline tables using st.recursive
def array_from_children(children):
    # children is a strategy that yields string representations of values
    # possible forms: [v, v, ...] with optional trailing comma and comments/newlines
    elems = st.lists(children, min_size=0, max_size=6)
    # include optional comments/newlines tokens sprinkled (simple)
    def mk_array(lst):
        # join with comma, allow trailing comma sometimes
        if not lst:
            return '[]'
        s = ', '.join(lst)
        if st.booleans().example():
            s = s + ','
        return '[' + s + ']'
    return elems.map(mk_array)

def inline_table_from_children(children):
    # inline table must be single-line; produce { k = v, ... } allowing trailing comma
    def mk_kv(child_val):
        # generate random key for inline table entries
        # choose unquoted simple or quoted
        k = st.one_of(unquoted_key, quoted_key).example()
        return f"{k} = {child_val}"
    # We cannot call .example() during strategy definition; instead build by combining strategies:
    entries = st.lists(children, min_size=0, max_size=6)
    def mk_table(lst):
        if not lst:
            return '{}'
        # generate keys deterministically from an internal pseudo-random choice based on lengths to avoid .example
        keys = []
        for i in range(len(lst)):
            # alternate between quoted and unquoted keys
            if i % 3 == 0:
                k = f"key{i}"
            elif i % 3 == 1:
                k = f"\"k{i}\""
            else:
                k = f"'k{i}'"
            keys.append(k)
        kvs = []
        for k, v in zip(keys, lst):
            kvs.append(f"{k} = {v}")
        s = ', '.join(kvs)
        if st.booleans().example():
            s = s + ','  # allow trailing comma (accepted by parser)
        return '{' + s + '}'
    return entries.map(mk_table)

# Because mk_array and mk_table used .example() in some branches, we will reimplement using only pure strategy maps:
def array_from_children_pure(children):
    elems = st.lists(children, min_size=0, max_size=6)
    def mk_array_pure(lst):
        if not lst:
            return '[]'
        s = ', '.join(lst)
        # use deterministic pseudo-randomness via lengths to choose trailing comma sometimes
        if sum(len(x) for x in lst) % 2 == 0:
            s = s + ','
        return '[' + s + ']'
    return elems.map(mk_array_pure)

def inline_table_from_children_pure(children):
    entries = st.lists(children, min_size=0, max_size=6)
    def mk_table_pure(lst):
        if not lst:
            return '{}'
        kvs = []
        for i, v in enumerate(lst):
            if i % 3 == 0:
                k = f"key{i}"
            elif i % 3 == 1:
                k = f"\"k{i}\""
            else:
                k = f"'k{i}'"
            kvs.append(f"{k} = {v}")
        s = ', '.join(kvs)
        if len(lst) % 2 == 0:
            s = s + ','  # trailing comma allowed
        return '{' + s + '}'
    return entries.map(mk_table_pure)

# Build recursive value strategy (arrays and inline tables recurse)
value_recursive = st.recursive(
    base_value,
    lambda children: st.one_of(array_from_children_pure(children), inline_table_from_children_pure(children)),
    max_leaves=4096
)

# Additionally include a special deep-nesting array generator to hit deep recursion extremes
deep_array = st.integers(min_value=1, max_value=2048).map(lambda n: '[' * n + '0' + ']' * n)

# Combine value strategies
value = st.one_of(value_recursive, deep_array)

# Expression strategies: key_value lines, table headers, array-of-tables headers, comment-only
# Key-value: key = value, with optional spaces and trailing comment
space = st.text(alphabet=' \t', min_size=0, max_size=4)
comment = st.one_of(st.just(''), st.builds(lambda c: '# ' + c, st.text(alphabet=st.characters(blacklist_characters='\x00\n'), min_size=0, max_size=40)))
def make_kv(k, v, sp, cm):
    return f"{k}{sp}={sp}{v}{(' ' + cm) if cm else ''}".rstrip()
kv_line = st.tuples(key, space, value, st.one_of(st.just(''), comment)).map(lambda t: make_kv(t[0], t[2], t[1], t[3]))

# Table headers: [key] or [[key]] optionally malformed (missing/doubled delimiter)
def std_table(k):
    return f"[{k}]"
def arr_table(k):
    return f"[[{k}]]"
standard_table = key.map(lambda k: '[' + k + ']')
array_table = key.map(lambda k: '[[' + k + ']]')
# malformed headers: missing bracket or doubled
malformed_table = key.map(lambda k: '[[' + k + ']' )  # double opening, single closing

table_line = st.one_of(standard_table, array_table, malformed_table).map(lambda s: s)

# Comment-only line
comment_line = comment.map(lambda c: c if c else '#')  # replace empty with a simple comment

# An expression is either key-value, a table header, or a comment
expression = st.one_of(kv_line, table_line, comment_line)

# Document: sequence of expressions separated by newlines; include empty docs and comment-only docs
def join_lines(lines):
    # join lines with CRLF or LF occasionally
    sep = '\r\n' if (sum(len(l) for l in lines) % 7 == 0) else '\n'
    doc = sep.join(lines)
    # optionally omit trailing newline (documents with no trailing newline)
    if sum(len(l) for l in lines) % 5 == 0:
        return doc
    return doc + sep

document = st.lists(expression, min_size=0, max_size=30).map(join_lines)

# Introduce near-valid-but-malformed variants at document level: stray token, missing equals, doubled equals, unterminated string injection
def inject_malformed(doc):
    # randomly insert a malformed snippet in the document
    snippets = [
        ' = 1',  # missing key
        'key == 1',  # double equals
        '[[[malformed]]]',  # too many brackets
        '"unterminated',  # unterminated string stray
        'stray_token $$',  # stray token
        '{ key = 1,\n}',  # newline inside inline table (parser rejects)
    ]
    s = snippets[len(doc) % len(snippets)]
    # insert at start or end depending on parity
    if len(doc) % 2 == 0:
        return s + '\n' + doc
    else:
        return doc + '\n' + s

# Final top-level strategy: produce a document, sometimes inject duplicates and malformed snippets and ensure no raw NUL
def finalize(doc):
    # Optionally duplicate keys: create a duplicate key line appended to doc
    if ' = ' not in doc:
        final = doc
    else:
        if len(doc) % 3 == 0:
            # append a duplicate key using one of existing keys
            lines = [l for l in doc.splitlines() if '=' in l]
            if lines:
                dup = lines[0]
                final = doc + '\n' + dup
            else:
                final = doc
        else:
            final = doc
    # occasionally inject a malformed snippet
    if len(final) % 11 == 0:
        final = inject_malformed(final)
    # ensure no raw NUL bytes
    if '\x00' in final:
        final = final.replace('\x00', '\\u0000')
    return final

strategy = st.one_of(document, document.map(inject_malformed), document.map(finalize))
# ensure type is SearchStrategy[str]