```python
from hypothesis import strategies as st
import json

# Utility: avoid generating raw NUL character anywhere
_non_nul_char = st.characters(blacklist_characters='"\'\n\\\x00', min_codepoint=1, max_codepoint=0x10FFFF)

# Basic pieces
newline = st.sampled_from(["\n", "\r\n"])
ws = st.sampled_from(["", " ", "  ", "\t", " \t"])

# Keys
unquoted_key = st.from_regex(r"[A-Za-z0-9_-]{1,10000}", fullmatch=True)
# Quoted keys: reuse string token producers below but ensure they are used as keys (may be empty "")
@st.composite
def basic_string_key(draw):
    # a simple basic string (quoted)
    pieces = draw(st.lists(st.one_of(_non_nul_char, st.sampled_from(["\\n","\\t","\\r","\\\\","\\\"","\\u0000","\\u263A","\\q"])),
                           min_size=0, max_size=20))
    s = "".join(pieces)
    # occasionally produce unterminated quoted key (malformed)
    if draw(st.booleans()) and draw(st.booleans()):
        return '"' + s  # unterminated
    return '"' + s + '"'

@st.composite
def literal_string_key(draw):
    pieces = draw(st.lists(st.characters(blacklist_characters="'\n\x00"), min_size=0, max_size=20))
    s = "".join(pieces)
    if draw(st.booleans()) and draw(st.booleans()):
        return "'" + s  # unterminated single-quoted
    return "'" + s + "'"

key_token = st.one_of(unquoted_key, basic_string_key(), literal_string_key())

# Compose dotted keys (including quoted segments and dots, sometimes malformed doubling dots)
@st.composite
def dotted_key(draw):
    segs = draw(st.lists(key_token, min_size=1, max_size=6))
    parts = []
    for i, seg in enumerate(segs):
        parts.append(seg)
        if draw(st.booleans()):  # sometimes insert an extra dot (malformed)
            parts.append(".")
    # ensure we don't end with a trailing dot unless intended
    s = "".join(parts)
    # collapse occasional accidental leading/trailing dots to test near-valid malformed inputs
    return s

# String value variants
@st.composite
def basic_string(draw):
    pieces = draw(st.lists(st.one_of(_non_nul_char,
                                     st.sampled_from(["\\n","\\t","\\r","\\\\","\\\"","\\u0000","\\u263A","\\q"])),
                           min_size=0, max_size=60))
    s = "".join(pieces)
    # choose malformed sometimes (unterminated)
    if draw(st.booleans()) and draw(st.booleans()):
        return '"' + s
    return '"' + s + '"'

@st.composite
def ml_basic_string(draw):
    # multiline basic: triple quotes, allow embedded escapes and newlines
    lines = draw(st.lists(st.one_of(
        st.text(alphabet=st.characters(blacklist_characters='\\\x00', min_codepoint=1), min_size=0, max_size=40),
        st.sampled_from(["\\n","\\t","\\\\","\\\"","\\u0000","\\u263A","\\q"])
    ), min_size=1, max_size=6))
    body = "\n".join(lines)
    if draw(st.booleans()) and draw(st.booleans()):
        # unterminated triple
        return '"""' + body
    return '"""' + body + '"""'

@st.composite
def literal_string(draw):
    # single-quoted literal cannot contain newline or single quote
    pieces = draw(st.lists(st.characters(blacklist_characters="'\n\x00"), min_size=0, max_size=60))
    s = "".join(pieces)
    if draw(st.booleans()) and draw(st.booleans()):
        return "'" + s  # unterminated
    return "'" + s + "'"

@st.composite
def ml_literal_string(draw):
    # multiline literal triple single quotes: allow anything except raw NUL
    pieces = draw(st.lists(st.characters(blacklist_characters='\x00', min_codepoint=1), min_size=0, max_size=100))
    body = "".join(pieces)
    if draw(st.booleans()) and draw(st.booleans()):
        return "'''" + body  # unterminated
    return "'''" + body + "'''"

string_value = st.one_of(basic_string(), ml_basic_string(), literal_string(), ml_literal_string())

# Integer formatting helpers: produce underscores optionally and different bases
def _insert_underscores(s):
    if len(s) <= 2:
        return s
    parts = []
    i = 0
    while i < len(s):
        take = 1 if st.booleans().example() else (1 + (i % 3))
        parts.append(s[i:i+take])
        i += take
    return "_".join([p for p in parts if p])

@st.composite
def decimal_int(draw):
    sign = draw(st.sampled_from(["","-","+"]))
    # generate either small or very large
    if draw(st.booleans()):
        n = draw(st.integers(min_value=0, max_value=10**40))
        s = str(n)
        # occasionally allow leading zeros (parser accepts them)
        if draw(st.booleans()):
            s = ("0" * draw(st.integers(min_value=0, max_value=5))) + s
    else:
        # create digits with underscores
        digits = "".join(draw(st.lists(st.characters(whitelist_categories=('Nd',)), min_size=1, max_size=40)))
        s = digits
    # insert underscores sometimes
    if draw(st.booleans()):
        s = _insert_underscores(s)
    return sign + s

@st.composite
def hex_int(draw):
    sign = draw(st.sampled_from(["","-","+"]))
    n = draw(st.integers(min_value=0, max_value=2**160))
    s = format(n, "x")
    # possibly add underscores between hex digits
    if draw(st.booleans()):
        s = _insert_underscores(s)
    # ensure at least one digit
    return sign + "0x" + (s or "0")

@st.composite
def oct_int(draw):
    sign = draw(st.sampled_from(["","-","+"]))
    n = draw(st.integers(min_value=0, max_value=2**160))
    s = format(n, "o")
    if draw(st.booleans()):
        s = _insert_underscores(s)
    return sign + "0o" + (s or "0")

@st.composite
def bin_int(draw):
    sign = draw(st.sampled_from(["","-","+"]))
    n = draw(st.integers(min_value=0, max_value=2**160))
    s = format(n, "b")
    if draw(st.booleans()):
        s = _insert_underscores(s)
    return sign + "0b" + (s or "0")

integer_value = st.one_of(decimal_int(), hex_int(), oct_int(), bin_int())

# Floating point: normal, special, edge forms like "1.", ".5", large exponents
@st.composite
def float_number(draw):
    # special INF/NAN variants
    if draw(st.booleans()):
        return draw(st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"]))
    # else numeric float
    sign = draw(st.sampled_from(["", "-", "+"]))
    # choose style
    style = draw(st.sampled_from(["plain", "leading_dot", "trailing_dot", "exp"]))
    if style == "plain":
        a = draw(st.integers(min_value=0, max_value=99999))
        b = draw(st.integers(min_value=0, max_value=999999))
        s = f"{a}.{b}"
    elif style == "leading_dot":
        b = draw(st.integers(min_value=1, max_value=999999))
        s = "." + str(b)
    elif style == "trailing_dot":
        a = draw(st.integers(min_value=0, max_value=999999))
        s = str(a) + "."
    else:  # exp
        mant = draw(st.one_of(st.integers(min_value=0, max_value=9999).map(str),
                              st.just("1")))
        exp = draw(st.integers(min_value=-1000, max_value=2000))
        s = mant + "e" + ("+" if exp >= 0 and draw(st.booleans()) else "") + str(exp)
    # optionally insert underscores within integer parts (allowed style lenient)
    return sign + s

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time forms: we craft numeric strings, allowing invalid dates (parser accepts)
@st.composite
def date_value(draw):
    # choose one of four forms
    year = draw(st.integers(min_value=0, max_value=9999)).map(str).example()
    month = "{:02d}".format(draw(st.integers(min_value=1, max_value=12)).example())
    day = "{:02d}".format(draw(st.integers(min_value=1, max_value=31)).example())
    hour = "{:02d}".format(draw(st.integers(min_value=0, max_value=23)).example())
    minute = "{:02d}".format(draw(st.integers(min_value=0, max_value=59)).example())
    second = "{:02d}".format(draw(st.integers(min_value=0, max_value=59)).example())
    secfrac = ""
    if draw(st.booleans()):
        secfrac = "." + str(draw(st.integers(min_value=0, max_value=999999)).example())
    delim = draw(st.sampled_from(["T","t"," "]))
    offset = draw(st.sampled_from(["Z", "+" + hour + ":" + minute, "-" + hour + ":" + minute]))
    form = draw(st.sampled_from(["offset_dt", "local_dt", "local_date", "local_time"]))
    if form == "offset_dt":
        return f"{year}-{month}-{day}{delim}{hour}:{minute}:{second}{secfrac}{offset}"
    if form == "local_dt":
        return f"{year}-{month}-{day}{delim}{hour}:{minute}:{second}{secfrac}"
    if form == "local_date":
        return f"{year}-{month}-{day}"
    return f"{hour}:{minute}:{second}{secfrac}"

# Atomic value strategy (strings, numbers, bools, dates)
atomic_value = st.one_of(string_value, integer_value, float_number, bool_value, date_value())

# Recursive values: arrays and inline tables that may nest; use st.recursive
def array_of(element):
    # element is a strategy producing textual representation of a value
    @st.composite
    def _array(draw):
        # allow empty arrays
        if draw(st.booleans()):
            elems = []
        else:
            count = draw(st.integers(min_value=1, max_value=6))
            elems = [draw(element) for _ in range(count)]
            # occasionally include trailing comma
            if draw(st.booleans()):
                trailing = True
            else:
                trailing = False
        # insert comments/newlines between items sometimes
        parts = []
        for i, e in enumerate(elems):
            # optional comment or newline
            if draw(st.booleans()) and i != 0:
                parts.append(" ")
            parts.append(e)
            # comma separation (may double comma to create near-valid malformed)
            if i != len(elems)-1:
                if draw(st.booleans()):  # sometimes double comma
                    parts.append(",")
                    if draw(st.booleans()):
                        parts.append(",")
                else:
                    parts.append(",")
                if draw(st.booleans()):
                    parts.append(draw(newline))
        s = "[" + "".join(parts)
        if 'trailing' in locals() and trailing:
            s += ","
        s += "]"
        return s
    return _array()

def inline_table_of(element):
    @st.composite
    def _itable(draw):
        # empty inline table sometimes
        if draw(st.booleans()):
            body = ""
        else:
            count = draw(st.integers(min_value=1, max_value=6))
            items = []
            for i in range(count):
                k = draw(st.one_of(unquoted_key, basic_string_key(), literal_string_key()))
                v = draw(element)
                # occasional duplicate key to exercise duplicate-key rejection
                if draw(st.booleans()) and i > 0 and draw(st.booleans()):
                    k = items[0].split("=",1)[0].strip()
                items.append(f"{k} = {v}")
            # sometimes insert newline inside inline table to create malformed input
            if draw(st.booleans()) and draw(st.booleans()):
                sep = draw(st.sampled_from([", ", ",\n", ",\r\n"]))
            else:
                sep = ", "
            body = sep.join(items)
            # optionally add trailing comma (parser accepts)
            if draw(st.booleans()):
                body = body + ","
        return "{" + body + "}"
    return _itable()

# Use st.recursive to allow nested arrays/inline tables; allow deep nesting with a high max_leaves
value = st.recursive(
    atomic_value,
    lambda children: st.one_of(array_of(children), inline_table_of(children)),
    max_leaves=300
)

# Key/value line
@st.composite
def key_value_line(draw):
    k = draw(st.one_of(dotted_key(), key_token))
    # sometimes produce malformed double-equals or missing equals
    mal = draw(st.sampled_from(["ok","double_eq","missing_eq"]))
    if mal == "double_eq":
        eqs = "=="
    elif mal == "missing_eq":
        eqs = "" if draw(st.booleans()) else "="  # sometimes missing completely
    else:
        eqs = "="
    # spaces around equals
    left_space = draw(ws)
    right_space = draw(ws)
    v = draw(value)
    # stray tokens sometimes appended
    stray = ""
    if draw(st.booleans()) and draw(st.booleans()):
        stray = draw(st.sampled_from([" ]", " }", " ,", " stray_token", " # stray comment"]))
    return f"{k}{left_space}{eqs}{right_space}{v}{stray}"

# Table headers
@st.composite
def standard_table(draw):
    k = draw(dotted_key())
    # occasionally malformed: missing closing bracket or doubled bracket
    mal = draw(st.sampled_from(["ok","missing_bracket","extra_bracket"]))
    if mal == "missing_bracket":
        return "[" + k  # missing closing bracket
    if mal == "extra_bracket":
        return "[[" + k + "]]"  # looks like array table (near mismatch)
    return "[" + k + "]"

@st.composite
def array_table(draw):
    k = draw(dotted_key())
    # sometimes malformed with one bracket
    if draw(st.booleans()) and draw(st.booleans()):
        return "[[" + k + "]"
    return "[[" + k + "]]"

# Comments and stray lines
comment_line = st.one_of(
    st.just(""),
    st.just("#"),
    st.builds(lambda c: "# " + c, st.text(min_size=0, max_size=60)),
    st.builds(lambda c: c, st.sampled_from(["[", "]", "] ]", "}", "{", "==", "???"]))
)

# Expression: key_value | table | comment
expression = st.one_of(
    key_value_line(),
    st.one_of(standard_table(), array_table()),
    comment_line
)

# Document: sequence of expressions separated by newlines; include empty documents and comment-only too
@st.composite
def document(draw):
    # produce between 0 and 12 expressions
    count = draw(st.integers(min_value=0, max_value=12))
    exprs = []
    for i in range(count):
        expr = draw(expression)
        # occasionally produce duplicate key lines to exercise parser rejection
        if draw(st.booleans()) and expr and "=" in expr and exprs:
            if draw(st.booleans()):
                # duplicate a previous key line intentionally
                exprs.append(exprs[0])
                continue
        exprs.append(expr)
    # Compose with newlines, sometimes no trailing newline (allowed)
    parts = []
    for i, e in enumerate(exprs):
        parts.append(e)
        if i != len(exprs)-1:
            parts.append(draw(newline))
    # Occasionally append a table after content to test super-table defined after subtables
    if draw(st.booleans()) and draw(st.booleans()):
        parts.append(draw(newline))
        parts.append(draw(standard_table()))
    # Occasionally produce deep nested array roots to test recursion depth (embedding strings of many brackets)
    if draw(st.booleans()) and draw(st.booleans()):
        depth = draw(st.integers(min_value=1, max_value=200))
        # create nested array representation like [[[ ... 1 ... ]]]
        inner = "1"
        for _ in range(depth):
            inner = "[" + inner + "]"
        # append as a key-value to the document
        parts.append(draw(newline))
        parts.append("deep = " + inner)
    return "".join(parts)

# Top-level exported strategy
strategy = document().map(lambda s: s)
```