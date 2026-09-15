from hypothesis import strategies as st
import json

# Helper: avoid emitting raw NUL byte (0x00) anywhere
_non_nul_control_chars = "".join(chr(c) for c in range(1, 32) if c != 0)
_printable_ascii = "".join(chr(c) for c in range(32, 127) if c != 0)
_ascii_bare_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_hex_digits = "0123456789abcdefABCDEF"

# ESC sequences for basic strings, include invalid escape as well for near-malformed cases
_escape_seq = st.one_of(
    st.sampled_from(['\\n', '\\r', '\\t', '\\b', '\\f', '\\"', "\\'", '\\\\', '\\/']),
    st.builds(lambda h: '\\u' + h, st.text(_hex_digits, min_size=4, max_size=4)),
    st.builds(lambda h: '\\U' + h, st.text(_hex_digits, min_size=8, max_size=8)),
    st.sampled_from(['\\q'])  # invalid escape to provoke rejection
)

# Small plain chunks for assembling strings
_plain_chunk = st.text(
    alphabet=_printable_ascii.replace('"', '').replace("'", "").replace("\\", "").replace("\n", "").replace("\r", ""),
    min_size=0,
    max_size=40
)

# Allow non-ASCII in quoted strings, but avoid NUL
_non_ascii_chunk = st.text(alphabet=_printable_ascii + "".join(chr(i) for i in range(128, 0x10FF)), min_size=0, max_size=20)

# Basic (double-quoted) string generator, sometimes unterminated
@st.composite
def basic_string(draw, allow_unterminated=True, multiline=False):
    # Build content from interleaving plain chunks, escape sequences, and raw control chars (except NUL)
    parts = draw(st.lists(st.one_of(_plain_chunk, _escape_seq, st.sampled_from(list(_non_nul_control_chars))), min_size=1, max_size=6))
    inner = "".join(parts)
    if multiline:
        opener = '"""'
        closer = '"""'
    else:
        opener = '"'
        closer = '"'
    # Occasionally omit the closing quote to produce unterminated string
    if allow_unterminated and draw(st.booleans()) and draw(st.integers(min_value=0, max_value=10)) == 0:
        return opener + inner  # unterminated
    return opener + inner + closer

# Literal (single-quoted) string generator, sometimes unterminated or with newline to provoke rejection
@st.composite
def literal_string(draw, allow_unterminated=True, multiline=False):
    if multiline:
        opener = "'''"
        closer = "'''"
        # multiline literal can include any char
        inner = draw(st.text(min_size=0, max_size=80))
    else:
        opener = "'"
        closer = "'"
        # single-line literal cannot contain newline according to grammar; include newline sometimes to explore rejection
        inner = draw(st.one_of(
            st.text(alphabet=_printable_ascii.replace("'", "").replace("\n", "").replace("\r", ""), min_size=0, max_size=60),
            st.text(min_size=0, max_size=20)  # may include newlines -> will be a near-malformed case
        ))
    if allow_unterminated and draw(st.integers(min_value=0, max_value=20)) == 0:
        return opener + inner  # unterminated
    return opener + inner + closer

# Integer generators: decimal (with optional leading zeros, underscores), hex, oct, bin
@st.composite
def decimal_int_str(draw):
    n = draw(st.integers(min_value=-10**40, max_value=10**40))
    s = str(abs(n))
    # randomly insert underscores
    if len(s) > 1 and draw(st.booleans()):
        parts = []
        i = 0
        while i < len(s):
            chunk = draw(st.integers(min_value=1, max_value=3))
            parts.append(s[i:i+chunk])
            i += chunk
        s = "_".join(filter(None, parts))
    # randomly add leading zeros (parser accepts them)
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=10)) == 0:
        zeros = draw(st.integers(min_value=1, max_value=5))
        s = "0"*zeros + s
    if n < 0:
        s = "-" + s
    elif draw(st.booleans()) and draw(st.integers(min_value=0, max_value=20)) == 0:
        # add explicit plus sign occasionally
        s = "+" + s
    return s

@st.composite
def hex_int_str(draw):
    n = draw(st.integers(min_value=0, max_value=2**200))
    s = format(n, 'x')
    # insert underscores between hex digits sometimes
    if len(s) > 1 and draw(st.booleans()):
        parts = []
        i = 0
        while i < len(s):
            chunk = draw(st.integers(min_value=1, max_value=4))
            parts.append(s[i:i+chunk])
            i += chunk
        s = "_".join(filter(None, parts))
    prefix = "0x"
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=20)) == 0:
        prefix = "0X"
    return prefix + s

@st.composite
def oct_int_str(draw):
    n = draw(st.integers(min_value=0, max_value=2**150))
    s = format(n, 'o')
    if len(s) > 1 and draw(st.booleans()):
        parts = []
        i = 0
        while i < len(s):
            chunk = draw(st.integers(min_value=1, max_value=3))
            parts.append(s[i:i+chunk])
            i += chunk
        s = "_".join(filter(None, parts))
    return "0o" + s

@st.composite
def bin_int_str(draw):
    n = draw(st.integers(min_value=0, max_value=2**150))
    s = format(n, 'b')
    if len(s) > 1 and draw(st.booleans()):
        parts = []
        i = 0
        while i < len(s):
            chunk = draw(st.integers(min_value=1, max_value=4))
            parts.append(s[i:i+chunk])
            i += chunk
        s = "_".join(filter(None, parts))
    return "0b" + s

int_value = st.one_of(decimal_int_str(), hex_int_str(), oct_int_str(), bin_int_str())

# Float generators, including '1.', '.5', scientific, inf/nan
@st.composite
def float_str(draw):
    kind = draw(st.sampled_from(['simple', 'dot_tail', 'leading_dot', 'exp', 'inf_nan']))
    if kind == 'simple':
        # typical float like 1.23 or with underscores
        whole = draw(st.integers(min_value=0, max_value=10**20))
        frac = draw(st.integers(min_value=0, max_value=10**6))
        s = f"{whole}.{str(frac).rjust(1, '0')}"
        if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=3)) == 0:
            # optionally add underscore patterns
            s = s.replace('.', '.', 1)
        if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=20)) == 0:
            # large exponent
            s = s + "e" + str(draw(st.integers(min_value=-1000, max_value=10000)))
        return s
    if kind == 'dot_tail':
        # like 1.
        whole = draw(st.integers(min_value=0, max_value=10**20))
        s = str(whole) + "."
        if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=50)) == 0:
            s = "+" + s
        return s
    if kind == 'leading_dot':
        # like .5
        frac = draw(st.integers(min_value=0, max_value=10**6))
        s = "." + str(frac)
        return s
    if kind == 'exp':
        base = draw(st.floats(allow_infinity=False, allow_nan=False, width=32)).hex()
        # simpler manual scientific
        mant = draw(st.floats(allow_nan=False, allow_infinity=False))
        # convert to decimal string with exponent
        m = ("%.15g" % mant)
        e = draw(st.integers(min_value=-10000, max_value=10000))
        return m + "e" + str(e)
    # inf_nan
    s = draw(st.sampled_from(['inf', '-inf', '+inf', 'nan', '-nan', '+nan']))
    return s

# Boolean
bool_value = st.sampled_from(['true', 'false'])

# Date/time generators, include calendar-invalid dates
@st.composite
def local_date(draw):
    year = draw(st.integers(min_value=0, max_value=9999))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=31))  # may be invalid calendar-wise
    return f"{year:04d}-{month:02d}-{day:02d}"

@st.composite
def local_time(draw):
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=10)) == 0:
        # seconds fraction
        frac = draw(st.text(alphabet="0123456789", min_size=1, max_size=6))
        return f"{hour:02d}:{minute:02d}:{second:02d}.{frac}"
    return f"{hour:02d}:{minute:02d}:{second:02d}"

@st.composite
def offset_date_time(draw):
    date = draw(local_date())
    delim = draw(st.sampled_from(['T', 't', ' ']))
    time = draw(local_time())
    off = draw(st.one_of(st.just('Z'), st.builds(lambda hh, mm, sgn: f"{sgn}{hh:02d}:{mm:02d}",
                                                st.integers(0,23), st.integers(0,59), st.sampled_from(['+','-']))))
    return date + delim + time + off

date_time_value = st.one_of(offset_date_time(), st.builds(lambda d,t: d + " " + t, local_date(), local_time()), local_date(), local_time())

# String choices for value (four quoting forms)
string_value = st.one_of(
    basic_string(allow_unterminated=True, multiline=False),
    basic_string(allow_unterminated=True, multiline=True),
    literal_string(allow_unterminated=True, multiline=False),
    literal_string(allow_unterminated=True, multiline=True)
)

# Base (non-recursive) values
base_value = st.one_of(
    string_value,
    int_value,
    float_str(),
    bool_value,
    date_time_value
)

# Function to build array text from a list of element strings, with comments/newlines/whitespace sprinkled
def _make_array_from_list(lst, allow_comments=True):
    # build elements separated by commas, allow trailing comma occasionally
    # Insert comments/newlines randomly by picking separators from a small pool
    sep_choices = [", ", ",\n", ",\r\n", ",  ", ","]
    parts = []
    for i, v in enumerate(lst):
        parts.append(v)
    sep = ", "
    body = ""
    if len(parts) == 0:
        body = ""
    else:
        # choose separators randomly based on complexity of elements
        body = sep.join(parts)
    # randomly insert a trailing comma
    if len(parts) > 0 and (len("".join(parts)) % 7 == 0):
        body = body + ","
    # occasionally add comments/newlines inside arrays (multiline)
    if allow_comments and len(body) > 0 and len(body) % 5 == 0:
        body = body.replace(", ", ",\n# comment\n")
    return "[" + body + "]"

# Function to build inline table text from list of (k,v) tuples
def _make_inline_table_from_items(items):
    # Items: list of (key_str, val_str)
    parts = []
    for k, v in items:
        parts.append(f"{k} = {v}")
    body = ", ".join(parts)
    # allow trailing comma
    if len(parts) > 0 and len(body) % 6 == 0:
        body = body + ","
    return "{" + body + "}"

# Now create recursive values using st.recursive
def _extend_with_containers(children):
    # children is a strategy producing value strings
    # arrays
    array_elems = st.lists(children, min_size=0, max_size=6)
    arrays = array_elems.map(lambda lst: _make_array_from_list(lst))
    # deep arrays: produce very deep nesting (1500-2048) wrapping a child
    @st.composite
    def deep_array(draw):
        depth = draw(st.integers(min_value=1500, max_value=2048))
        inner = draw(children)
        s = inner
        for _ in range(depth):
            s = "[" + s + "]"
        return s
    # inline tables: generate small inline tables, values drawn from children
    @st.composite
    def inline_table(draw):
        # up to 6 entries
        n = draw(st.integers(min_value=0, max_value=6))
        items = []
        for _ in range(n):
            # keys inside inline tables can be quoted or unquoted
            key = draw(_simple_or_quoted_key())
            val = draw(children)
            items.append((key, val))
        return _make_inline_table_from_items(items)
    return st.one_of(arrays, inline_table(), deep_array())

# Key generation: unquoted, quoted (basic or literal), dotted keys
def _simple_unquoted_key():
    return st.text(alphabet=_ascii_bare_key_chars, min_size=1, max_size=10000)

def _quoted_key():
    # allow empty quoted key "" as required
    return st.one_of(
        basic_string(allow_unterminated=False, multiline=False),
        literal_string(allow_unterminated=False, multiline=False)
    )

def _simple_or_quoted_key():
    return st.one_of(_simple_unquoted_key(), _quoted_key())

# Dotted key generator
@st.composite
def dotted_key(draw):
    parts = draw(st.lists(_simple_or_quoted_key(), min_size=1, max_size=5))
    # join with dots, but beware quoted parts already include quotes
    # if part contains a dot inside quotes it's fine
    expanded = []
    for p in parts:
        expanded.append(p)
    return ".".join(expanded)

# Key-value lines, with occasional malformed variants (missing '=', double '=')
@st.composite
def key_value_line(draw, values):
    key = draw(st.one_of(dotted_key(), _simple_or_quoted_key()))
    val = draw(values)
    eq_choice = draw(st.integers(min_value=0, max_value=20))
    if eq_choice == 0:
        # missing equals
        line = f"{key} {val}"
    elif eq_choice == 1:
        # doubled equals
        line = f"{key} == {val}"
    else:
        # normal
        line = f"{key} = {val}"
    # optionally add trailing inline comment
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=5)) == 0:
        comment = draw(st.text(alphabet=_printable_ascii, min_size=0, max_size=40))
        if not comment.startswith("#"):
            comment = "# " + comment
        line = line + " " + comment
    return line

# Table header generation ([key] or [[key]])
@st.composite
def table_header_line(draw):
    key = draw(dotted_key())
    if draw(st.booleans()):
        return "[" + key + "]"
    else:
        return "[[" + key + "]]"

# Comment lines
comment_line = st.one_of(
    st.just(""),
    st.builds(lambda s: "# " + s, st.text(alphabet=_printable_ascii, min_size=0, max_size=80)),
    st.builds(lambda s: "#"+s, st.text(alphabet=_printable_ascii, min_size=0, max_size=80))
)

# Expression (key_value, table, or comment)
@st.composite
def expression_line(draw, values):
    kind = draw(st.integers(min_value=0, max_value=10))
    if kind <= 6:
        return draw(key_value_line(values))
    elif kind == 7:
        return draw(table_header_line())
    else:
        return draw(comment_line)

# Build the recursive value strategy
value_strategy = st.recursive(base_value, _extend_with_containers, max_leaves=50)

# Document generator: a sequence of expressions separated by newlines (CRLF occasionally), allow empty document
@st.composite
def document(draw):
    n = draw(st.integers(min_value=0, max_value=20))
    lines = []
    for _ in range(n):
        lines.append(draw(expression_line(value_strategy)))
    # Occasionally inject a stray token or stray bracket line
    if draw(st.integers(min_value=0, max_value=30)) == 0:
        lines.append(draw(st.sampled_from(["]", "]]", "[", "[[", "=", "==", "}", "} }", "???"])))
    # Optionally introduce duplicate keys by copying a previous key-value line if present
    if lines and draw(st.integers(min_value=0, max_value=10)) == 0:
        # find a key_value line to duplicate
        kvs = [l for l in lines if "=" in l and not l.strip().startswith("#")]
        if kvs:
            dup = draw(st.sampled_from(kvs))
            lines.append(dup)
    # Mix in CRLF newlines sometimes
    newline = draw(st.sampled_from(["\n", "\r\n"]))
    doc = newline.join(lines)
    # Optionally no trailing newline (allowed)
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=5)) == 0:
        return doc
    return doc + newline

# Top-level strategy name required by harness
strategy = document()