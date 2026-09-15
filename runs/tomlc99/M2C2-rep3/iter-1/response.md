```python
from hypothesis import strategies as st
import json

# Helper character sets
_ASCII_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
# Avoid raw NUL anywhere
_NO_NUL = '\x00'

# Basic pieces

# Unquoted key (ASCII only, as parser rejects non-ASCII bare keys)
unquoted_key = st.text(alphabet=_ASCII_KEY_CHARS, min_size=1, max_size=50)

# Very long key for edge-case tests (10k chars)
long_key = st.just("k" * 10000)

# Quoted key variants: use simple single-line quoted strings for keys
def basic_quoted_string_contents(min_size=0, max_size=20):
    # Basic string content may include control chars except newline and NUL and must escape quotes/backslashes
    return st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10ffff, blacklist_characters='"\n\\' + _NO_NUL),
                   min_size=min_size, max_size=max_size)

def literal_quoted_string_contents(min_size=0, max_size=20):
    # Literal strings cannot contain single-quote or newline
    return st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10ffff, blacklist_characters="'\n" + _NO_NUL),
                   min_size=min_size, max_size=max_size)

basic_quoted_key = basic_quoted_string_contents(min_size=0, max_size=10).map(lambda s: '"' + s + '"')
literal_quoted_key = literal_quoted_string_contents(min_size=0, max_size=10).map(lambda s: "'" + s + "'")
quoted_key = st.one_of(basic_quoted_key, literal_quoted_key, st.just('""'))  # include empty quoted key

simple_key = st.one_of(unquoted_key, quoted_key, long_key)
dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: ".".join(parts))

key = st.one_of(dotted_key, simple_key)

# Comment generator (may include control chars; comments start with #)
comment_text = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10ffff, blacklist_characters=_NO_NUL),
                       min_size=0, max_size=80)
comment = comment_text.map(lambda t: ("# " + t) if t else "#")

# String value generators
# Escape sequences for basic strings (include Unicode escapes and some invalid escapes for fuzzing)
escape_seq = st.one_of(
    st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\"', "\\'", '\\\\']),
    st.text(alphabet='0123456789abcdefABCDEF', min_size=4, max_size=8).map(lambda h: '\\u' + (h[:4])),
    st.text(alphabet='0123456789abcdefABCDEF', min_size=8, max_size=8).map(lambda h: '\\U' + h),
    st.sampled_from(['\\u0000', '\\u2603', '\\U0001F600']),  # include zero-codepoint only as escape
    st.sampled_from(['\\q', '\\z'])  # invalid escapes to create near-valid-but-malformed
)

basic_string_segment = st.one_of(
    basic_quoted_string_contents(min_size=0, max_size=20),
    escape_seq
)

basic_string = st.lists(basic_string_segment, min_size=0, max_size=6).map(lambda segs: '"' + "".join(segs) + '"')

# Multiline basic string (""" ... """) - can include newlines and many chars; avoid embedding the closing delimiter
ml_basic_string_content = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10ffff,
                                                         blacklist_characters='"""' + _NO_NUL),
                                 min_size=0, max_size=200).map(lambda s: s.replace('"""', '""'))  # avoid ending token
ml_basic_string = ml_basic_string_content.map(lambda s: '"""' + s + '"""')

# Literal string (single-line)
literal_string = literal_quoted_string_contents(min_size=0, max_size=20).map(lambda s: "'" + s + "'")

# Multiline literal string
ml_literal_string_content = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10ffff, blacklist_characters=_NO_NUL),
                                   min_size=0, max_size=200).map(lambda s: s.replace("'''", "''"))
ml_literal_string = ml_literal_string_content.map(lambda s: "'''" + s + "'''")

# Integer generators: decimal (including leading zeros), hex, oct, bin, with underscores and big magnitudes
def decimal_int_strat():
    sign = st.one_of(st.just(""), st.just("+"), st.just("-"))
    # allow leading zeros sometimes
    digits = st.one_of(
        st.text(alphabet='0123456789', min_size=1, max_size=1),
        st.text(alphabet='0123456789', min_size=1, max_size=20)
    )
    underscore_insert = digits.map(lambda s: s)  # we will insert underscores randomly with map below
    def add_underscores(s):
        # randomly insert underscores
        import random
        if len(s) <= 1 or random.random() < 0.5:
            return s
        parts = []
        i = 0
        while i < len(s):
            take = random.randint(1, min(3, len(s)-i))
            parts.append(s[i:i+take])
            i += take
            if i < len(s) and random.random() < 0.4:
                parts.append('_')
        return "".join(parts)
    return st.tuple(sign, underscore_insert).map(lambda t: t[0] + add_underscores(t[1]))

hex_int = st.tuple(st.one_of(st.just(""), st.just("-"), st.just("+")), st.text(alphabet='0123456789abcdefABCDEF', min_size=1, max_size=30)).map(lambda t: t[0] + "0x" + t[1])
oct_int = st.tuple(st.one_of(st.just(""), st.just("-"), st.just("+")), st.text(alphabet='01234567', min_size=1, max_size=30)).map(lambda t: t[0] + "0o" + t[1])
bin_int = st.tuple(st.one_of(st.just(""), st.just("-"), st.just("+")), st.text(alphabet='01', min_size=1, max_size=60)).map(lambda t: t[0] + "0b" + t[1])

dec_int = decimal_int_strat()

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int)

# Floats: include forms like 1., .5, exponent, inf/nan
def float_examples():
    # finite floats
    finite = st.one_of(
        st.text(alphabet='0123456789', min_size=1, max_size=30).map(lambda s: s + '.'),
        st.text(alphabet='0123456789', min_size=1, max_size=30).map(lambda s: '.' + s),
        st.text(alphabet='0123456789', min_size=1, max_size=30).map(lambda s: s + '.' + s[:random_len(s:=s)] )
    )
    # but it's easier to construct via formatted numbers with underscores and exponents
    def random_len(s): return min(len(s), 3)
    return finite

# Simpler explicit float generator
float_regular = st.one_of(
    # 1.  .5  1.0 1e10 1.234e-10 1_000.0 1_.
    st.tuples(st.one_of(st.just(""), st.just("+"), st.just("-")), st.text(alphabet='0123456789', min_size=1, max_size=20),
              st.one_of(st.just("."), st.just(".") ), st.one_of(st.just(""), st.text(alphabet='0123456789', min_size=0, max_size=20)),
              st.one_of(st.just(""), st.builds(lambda a,b: a + b, st.sampled_from(['e','E']), st.tuples(st.one_of(st.just(""), st.just("+"), st.just("-")), st.text(alphabet='0123456789', min_size=1, max_size=5)).map(lambda t: t[0] + t[1])) )
              ).map(lambda t: t[0] + t[1] + t[2] + t[3] + (t[4] if t[4] else "")),
    # scientific with explicit big exponents
    st.tuples(st.one_of(st.just(""), st.just("+"), st.just("-")), st.text(alphabet='0123456789', min_size=1, max_size=30),
              st.one_of(st.just("e"), st.just("E")), st.one_of(st.just(""), st.just("+"), st.just("-")), st.integers(min_value=0, max_value=1000).map(str)
              ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])
)

float_special = st.sampled_from(['inf', '-inf', '+inf', 'nan', '-nan', '+nan'])

float_value = st.one_of(float_regular, float_special)

# Boolean
bool_value = st.sampled_from(['true', 'false'])

# Date-time forms (strings exactly following grammar tokens)
def two_digits(min_d=0, max_d=99):
    return st.integers(min_value=min_d, max_value=max_d).map(lambda n: f"{n:02d}")

year = st.integers(min_value=0, max_value=9999).map(lambda n: f"{n:04d}")
month = st.integers(min_value=1, max_value=12).map(lambda n: f"{n:02d}")
day = st.integers(min_value=1, max_value=31).map(lambda n: f"{n:02d}")
hour = two_digits()
minute = two_digits()
second = two_digits()
secfrac = st.one_of(st.just(''), st.text(alphabet='0123456789', min_size=1, max_size=6).map(lambda s: '.' + s))

numoffset = st.tuples(st.one_of(st.just('+'), st.just('-')), hour, st.just(':'), minute).map(lambda t: t[0] + t[1] + t[2] + t[3])
offset = st.one_of(st.just('Z'), numoffset)

partial_time = st.tuples(hour, st.just(':'), minute, st.just(':'), second, secfrac).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5])
full_date = st.tuples(year, st.just('-'), month, st.just('-'), day).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])
offset_date_time = st.tuples(full_date, st.sampled_from(['T','t',' ']), partial_time, offset).map(lambda t: t[0] + t[1] + t[2] + t[3])
local_date_time = st.tuples(full_date, st.sampled_from(['T','t',' ']), partial_time).map(lambda t: t[0] + t[1] + t[2])
local_date = full_date
local_time = partial_time

date_time_value = st.one_of(offset_date_time, local_date_time, local_date, local_time)

# Helper: strip newlines (used for inline tables)
def strip_newlines(s):
    return s.replace('\r', ' ').replace('\n', ' ')

# Base (non-recursive) value strategy
base_value = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    integer_value,
    float_value,
    bool_value,
    date_time_value
)

# For inline table values we must avoid newlines; make a single-line variant of a value
single_line_base_value = st.one_of(
    # pick from base_value but map to single-line versions
    basic_string,
    literal_string,
    integer_value,
    float_value,
    bool_value,
    date_time_value
).map(lambda s: strip_newlines(s))

# Now build recursive values (arrays and inline tables)
def extend_with_containers(children):
    # children: strategy producing complete value strings (may include newlines)
    # inline table values must be single-line (no NL)
    inline_child = st.deferred(lambda: children).map(strip_newlines)

    # array builder: produce arrays with optional comments and newlines between elements
    def build_array(elems):
        # elems is a list of element strings which may include newlines; insert random comments/newlines occasionally
        if not elems:
            # empty array
            return "[]"
        parts = []
        for i, e in enumerate(elems):
            parts.append(e)
        # three presentation forms: compact, spaced, multiline with comments
        import random
        style = random.random()
        if style < 0.5:
            # compact, maybe trailing comma
            s = "[ " + ", ".join(parts) + (", " if random.random() < 0.2 else "") + "]"
            return s
        else:
            # multiline with comments/newlines
            lines = ["["]
            for p in parts:
                if random.random() < 0.3:
                    lines.append("  # " + "comment")
                lines.append("  " + p + ",")
            if random.random() < 0.5:
                # maybe remove last comma to vary
                lines[-1] = lines[-1].rstrip(',')
            lines.append("]")
            return "\n".join(lines)

    array_of_children = st.lists(children, min_size=0, max_size=6).map(build_array)

    # inline table builder: must not contain newlines (but we also want to sometimes create malformed newlines)
    def build_inline_table(pairs):
        # pairs is list of (k,v) tuples
        # create entries "k = v"
        entries = []
        for k, v in pairs:
            # ensure keys are single-line
            kk = k
            vv = strip_newlines(v)
            entries.append(f"{kk} = {vv}")
        import random
        s = "{ " + ", ".join(entries)
        # optionally add trailing comma
        if random.random() < 0.3:
            s += ","
        s += " }"
        return s

    inline_pairs = st.lists(st.tuples(st.one_of(simple_key, quoted_key), inline_child), min_size=0, max_size=6)
    inline_table = inline_pairs.map(build_inline_table)

    return st.one_of(array_of_children, inline_table)

# Use st.recursive to create nested arrays/inline tables combining base_value
# Allow deep recursion (max_leaves large to permit deep nesting)
value = st.recursive(base_value, extend_with_containers, max_leaves=2048)

# Key-value line
def key_value_builder(k, v):
    # optional spaces around equals, sometimes multiple equals for malformed
    import random
    eq = " = "
    if random.random() < 0.05:
        eq = "=="  # near-valid malformed
    elif random.random() < 0.1:
        eq = " =  "  # extra spaces
    # optional inline comment
    c = ""
    if random.random() < 0.3:
        c = "  # " + "comment"
    return f"{k}{eq}{v}{c}"

key_value = st.tuples(key, value).map(lambda kv: key_value_builder(kv[0], kv[1]))

# Table headers
standard_table = key.map(lambda k: "[" + k + "]")
array_table = key.map(lambda k: "[[" + k + "]]")

# Inline table as a top-level expression (inline tables as values on RHS are handled in value)
top_inline_table = st.deferred(lambda: st.lists(st.tuples(key, single_line_base_value), min_size=0, max_size=6).map(
    lambda pairs: "{ " + ", ".join(f"{k} = {strip_newlines(v)}" for k, v in pairs) + (" , }" if False else " }")
))

# Expression can be: key_value, table, comment-only
expression = st.one_of(
    key_value,
    standard_table,
    array_table,
    comment.map(lambda s: s)  # comment-only line
)

# Document generator: sequence of expressions separated by newlines, maybe no trailing newline
def build_document(lines):
    import random
    # Optionally insert extra stray tokens to create near-valid-but-malformed inputs
    doc = "\n".join(lines)
    # With low probability, remove a closing bracket to make unterminated/malformed document
    if random.random() < 0.05 and doc:
        # drop last character or a bracket
        if ']' in doc and random.random() < 0.6:
            doc = doc.replace(']', '', 1)
        else:
            doc = doc[:-1]
    # With small probability, inject a stray token at random position
    if random.random() < 0.05:
        insert = random.choice([' ]', ' }', ' [[', ' ]]', ' =', ' ==', '"'])
        idx = random.randint(0, len(doc)) if doc else 0
        doc = doc[:idx] + insert + doc[idx:]
    return doc

# Build a valid-ish document then map to include malformed variants too
document_body = st.lists(expression, min_size=0, max_size=12).map(lambda parts: parts)

document = document_body.map(build_document)

# Additionally, create some malformed-specific variants like unterminated strings or newline inside inline table
def make_unterminated_string(doc):
    # find first basic string opening quote and drop its closing quote
    idx = doc.find('"')
    if idx == -1:
        return doc  # nothing to do
    # remove closing quote if present
    i2 = doc.find('"', idx+1)
    if i2 != -1:
        return doc[:i2] + doc[i2+1:]
    else:
        return doc  # no change

def inject_newline_in_inline_table(doc):
    # replace first "{ " with "{\n  " to create a newline inside an inline table (causes rejection)
    idx = doc.find('{ ')
    if idx == -1:
        return doc
    return doc[:idx] + '{\n  ' + doc[idx+2:]

# Final strategy: sometimes valid document, sometimes transformed malformed variant
strategy = st.one_of(
    document,
    document.map(lambda s: make_unterminated_string(s)),
    document.map(lambda s: inject_newline_in_inline_table(s)),
    # Duplicate key scenario: repeat a key-value line twice
    st.tuples(key, value).map(lambda kv: f"{kv[0]} = {kv[1]}\n{kv[0]} = {kv[1]}"),
    # Minimal documents: empty or comment-only
    st.one_of(st.just(""), comment.map(lambda s: s)),
)
```