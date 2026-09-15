```python
from hypothesis import strategies as st
import json

# Helper character pools (exclude NUL U+0000)
_ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_digits = "0123456789"
_bare_key_chars = _ascii_letters + _digits + "-_"
_printable_no_quote_backslash = ''.join(
    chr(c) for c in range(32, 127)
    if chr(c) not in {'"', "\\", "'"} and c != 0x0A and c != 0x0D
)
# allow control chars except NUL and newline/CR (which are special)
_control_chars = ''.join(chr(c) for c in range(1, 32) if c not in (0x0A, 0x0D))

# Escape sequences for basic strings (some valid, some intentionally invalid)
_basic_escapes = ["\\n", "\\t", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\/", "\\u%04x", "\\U%08x", "\\q"]
# We'll render unicode escapes by formatting with codepoints
_unicode_escapes = [
    lambda: "\\u%04x" % st.integers(min_value=0, max_value=0xFFFF).example(),
    lambda: "\\U%08x" % st.integers(min_value=0, max_value=0x10FFFF).example(),
]

# Basic building blocks
def _underscored_digits(digits: str):
    # Insert underscores in-between digits randomly but not at ends
    if len(digits) <= 1:
        return digits
    parts = []
    for ch in digits:
        parts.append(ch)
        if st.booleans().example():
            parts.append("_")
    s = ''.join(parts)
    # trim potential trailing underscore(s)
    s = s.rstrip("_")
    # ensure not starting underscore
    s = s.lstrip("_")
    if s == "":
        return digits
    return s

# Key strategies
short_bare_key = st.text(alphabet=list(_bare_key_chars), min_size=1, max_size=20)
long_bare_key = st.text(alphabet=list(_bare_key_chars), min_size=1000, max_size=10000)
bare_key = st.one_of(short_bare_key, long_bare_key)

@st.composite
def quoted_key_basic(draw):
    # quoted key with basic string syntax; allow empty quoted key ""
    content = draw(st.text(alphabet=list(_printable_no_quote_backslash + _control_chars), min_size=0, max_size=30))
    # Escape double quotes and backslashes for representation
    # We want to represent the literal BASIC_STRING form, so embed backslashes as needed
    escaped = content.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'

@st.composite
def quoted_key_literal(draw):
    content = draw(st.text(alphabet=list(''.join(chr(c) for c in range(1, 127) if chr(c) != "'")), min_size=0, max_size=30))
    # single-quoted literal, raw content except single quotes
    content2 = content.replace("'", "")  # to keep grammar simpler; sometimes we will produce malformed by leaving them
    return f"'{content2}'"

simple_key = st.one_of(bare_key, quoted_key_basic(), quoted_key_literal())

@st.composite
def dotted_key(draw):
    # create dotted keys of 1..5 components
    n = draw(st.integers(min_value=1, max_value=5))
    parts = [draw(simple_key) for _ in range(n)]
    return ".".join(parts)

# String productions
def _choose_basic_string_content(draw, max_parts=6):
    parts = []
    for _ in range(draw(st.integers(min_value=0, max_value=max_parts))):
        kind = draw(st.sampled_from(["plain", "control", "escape", "invalid_escape"]))
        if kind == "plain":
            parts.append(draw(st.text(alphabet=list(_printable_no_quote_backslash), min_size=1, max_size=10)))
        elif kind == "control":
            parts.append(draw(st.sampled_from(list(_control_chars))))
        elif kind == "escape":
            esc = draw(st.sampled_from(["\\n", "\\t", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\/"]))
            parts.append(esc)
        else:
            # invalid escape like \q
            parts.append("\\q")
    return "".join(parts)

@st.composite
def basic_string(draw, allow_unterminated=False):
    # Basic double-quoted string
    content = _choose_basic_string_content(draw, max_parts=8)
    if allow_unterminated and draw(st.booleans()):
        # produce unterminated: omit closing quote
        return '"' + content
    return '"' + content + '"'

@st.composite
def ml_basic_string(draw, allow_unterminated=False):
    # Multiline basic string: triple double quotes; allow newlines and raw escapes
    lines = []
    for _ in range(draw(st.integers(min_value=0, max_value=6))):
        # include CRLF sometimes
        line = draw(st.text(alphabet=list(_printable_no_quote_backslash + _control_chars + "\t "), min_size=0, max_size=50))
        lines.append(line)
    content = "\n".join(lines)
    if allow_unterminated and draw(st.booleans()):
        return '"""' + content
    return '"""' + content + '"""'

@st.composite
def literal_string(draw, allow_unterminated=False):
    # single-quoted literal string (no escapes)
    content = draw(st.text(alphabet=list(''.join(chr(c) for c in range(1, 127) if chr(c) != "'")), min_size=0, max_size=30))
    # sometimes include single quote to create malformed
    if "'" in content and not allow_unterminated and draw(st.booleans()):
        # convert some single quotes to escaped variants to keep validity
        content = content.replace("'", "")
    if allow_unterminated and draw(st.booleans()):
        return "'" + content
    return "'" + content + "'"

@st.composite
def ml_literal_string(draw, allow_unterminated=False):
    # triple single quotes, allow anything except maybe triple sequence
    content = draw(st.text(alphabet=list(''.join(chr(c) for c in range(1, 127) if c != 0)), min_size=0, max_size=200))
    if allow_unterminated and draw(st.booleans()):
        return "'''" + content
    return "'''" + content + "'''"

string_value = st.one_of(
    basic_string(),
    ml_basic_string(),
    literal_string(),
    ml_literal_string(),
)

# Numbers
@st.composite
def dec_int(draw):
    # allow leading zeros, underscores, signs
    sign = draw(st.sampled_from(["", "+", "-"]))
    # occasionally extremely large
    digits = draw(st.one_of(
        st.text(alphabet=list(_digits), min_size=1, max_size=20),
        st.text(alphabet=list(_digits), min_size=300, max_size=500),
        st.text(alphabet=list(_digits), min_size=1000, max_size=20000),
    ))
    # insert underscores occasionally
    if draw(st.booleans()):
        digits = _underscored_digits(digits)
    return sign + digits

@st.composite
def hex_int(draw):
    sign = ""
    digits = draw(st.text(alphabet=list("0123456789abcdefABCDEF"), min_size=1, max_size=40))
    if draw(st.booleans()):
        digits = _underscored_digits(digits)
    return "0x" + digits

@st.composite
def oct_int(draw):
    digits = draw(st.text(alphabet=list("01234567"), min_size=1, max_size=40))
    if draw(st.booleans()):
        digits = _underscored_digits(digits)
    return "0o" + digits

@st.composite
def bin_int(draw):
    digits = draw(st.text(alphabet=list("01"), min_size=1, max_size=80))
    if draw(st.booleans()):
        digits = _underscored_digits(digits)
    return "0b" + digits

integer_value = st.one_of(dec_int(), hex_int(), oct_int(), bin_int())

@st.composite
def float_value(draw):
    # include forms: 1., .5, normal floats, exponents, inf/nan
    choice = draw(st.sampled_from(["digit_dot", "dot_digit", "normal", "exp_large", "infnan", "underscore"]))
    if choice == "digit_dot":
        return draw(st.integers(min_value=-1000, max_value=1000)).__str__() + "."
    if choice == "dot_digit":
        frac = draw(st.text(alphabet=list(_digits), min_size=1, max_size=10))
        return "." + frac
    if choice == "normal":
        intpart = draw(st.integers(min_value=0, max_value=100000))
        frac = draw(st.text(alphabet=list(_digits), min_size=1, max_size=10))
        if draw(st.booleans()):
            return f"{intpart}.{frac}"
        else:
            return f"{intpart}.{frac}e{draw(st.integers(min_value=-400, max_value=400))}"
    if choice == "exp_large":
        # extreme exponent
        mant = draw(st.integers(min_value=1, max_value=9))
        exp = draw(st.integers(min_value=308, max_value=10000))
        return f"{mant}e{exp}"
    if choice == "infnan":
        sign = draw(st.sampled_from(["", "+", "-"]))
        return sign + draw(st.sampled_from(["inf", "nan"]))
    if choice == "underscore":
        # underscores in floats possible in integral part
        intpart = _underscored_digits("".join(draw(st.lists(st.sampled_from(list(_digits)), min_size=1, max_size=10))))
        return intpart + "." + draw(st.text(alphabet=list(_digits), min_size=1, max_size=5))

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time forms (may include calendar-invalid dates)
@st.composite
def date_time_value(draw):
    year = draw(st.integers(min_value=0, max_value=9999))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=31))  # allow invalid days (e.g., Feb 30)
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    frac = ""
    if draw(st.booleans()):
        frac = "." + "".join(str(draw(st.integers(min_value=0, max_value=9))) for _ in range(draw(st.integers(min_value=1, max_value=6))))
    offset = draw(st.sampled_from(["Z", f"+{draw(st.integers(min_value=0,max_value=23)):02d}:{draw(st.integers(min_value=0,max_value=59)):02d}", f"-{draw(st.integers(min_value=0,max_value=23)):02d}:{draw(st.integers(min_value=0,max_value=59)):02d}"]))
    delim = draw(st.sampled_from(["T", " ", "t"]))
    form = draw(st.sampled_from(["offset", "local_date_time", "local_date", "local_time"]))
    if form == "offset":
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{frac}{offset}"
    if form == "local_date_time":
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{frac}"
    if form == "local_date":
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{hour:02d}:{minute:02d}:{second:02d}{frac}"

# Base value strategy (non-recursive)
base_value = st.one_of(
    string_value,
    integer_value,
    float_value(),
    bool_value,
    date_time_value(),
)

# Recursive containers: arrays and inline tables
def array_of(values):
    # values is a SearchStrategy producing str (value text)
    # build arrays with optional comments, newlines, trailing commas
    inner = st.lists(values, min_size=0, max_size=6)
    @st.composite
    def arr(draw):
        elems = draw(inner)
        # insert comments/newlines randomly between elements
        chosen = []
        for i, e in enumerate(elems):
            chosen.append(e)
            if draw(st.booleans()):
                # append a comment
                chosen.append("#" + draw(st.text(alphabet=list(_printable_no_quote_backslash + _control_chars), min_size=0, max_size=30)))
            if draw(st.booleans()):
                chosen.append("\n")
        if draw(st.booleans()):
            # trailing comma allowed
            tail = ","
        else:
            tail = ""
        body = ", ".join([c for c in chosen if c != "\n"])
        # If there were newlines, format them properly
        if "\n" in chosen:
            # construct a multiline array
            lines = []
            for part in chosen:
                if part == "\n":
                    lines.append("\n")
                else:
                    lines.append(part)
            # naive join: replace consecutive \n as line breaks
            body = ""
            for part in chosen:
                if part == "\n":
                    body += "\n"
                else:
                    if body.endswith("\n"):
                        body += part
                    else:
                        if body != "":
                            body += ", " + part
                        else:
                            body += part
            # keep trailing comma if chosen
            if tail and not body.endswith(","):
                body = body + tail
        return "[" + body + ("," if tail and body=="" else "") + "]"
    return arr()

@st.composite
def inline_table_of(draw, values):
    # produce inline table text, maybe empty, maybe with trailing comma, maybe newline inside (malformed)
    n = draw(st.integers(min_value=0, max_value=6))
    kvs = []
    for _ in range(n):
        k = draw(st.one_of(simple_key, quoted_key_basic(), quoted_key_literal()))
        v = draw(values)
        kvs.append(f"{k} = {v}")
    # sometimes include trailing comma
    if draw(st.booleans()):
        body = ", ".join(kvs) + ("," if kvs else "")
    else:
        body = ", ".join(kvs)
    # sometimes inject a newline inside inline table to create a near-valid-but-malformed input
    if draw(st.booleans()):
        # insert a newline before a comma or between keyvals
        if "," in body:
            parts = body.split(",")
            idx = draw(st.integers(min_value=0, max_value=max(0, len(parts)-1)))
            parts[idx] = parts[idx] + "\n"
            body = ",".join(parts)
        else:
            # just add newline
            body = body + "\n"
    return "{" + body + "}"

# Compose recursive values with arrays and inline tables
values = st.recursive(
    base_value,
    lambda children: st.one_of(array_of(children), inline_table_of(children)),
    max_leaves=200,
)

# Deep nesting strategy (explicit deeply nested empty arrays)
deep_nesting = st.integers(min_value=1500, max_value=2048).map(lambda n: "[" * n + "]" * n)

# Key-value line generator
@st.composite
def key_value_line(draw, value_strategy):
    # choose a key (simple or dotted), maybe quoted empty key
    key = draw(st.one_of(simple_key, dotted_key, quoted_key_basic(), quoted_key_literal()))
    # Occasionally produce duplicate keys (we just return lines; duplicates are detected by parser)
    val = draw(value_strategy)
    # Insert some malformed possibilities: missing equal, double equals, value on next line, stray token
    malformed = draw(st.sampled_from([None, "missing_eq", "double_eq", "next_line_val", "stray_token", "ok"]))
    if malformed == "missing_eq":
        return f"{key} {val}"  # missing '='
    if malformed == "double_eq":
        return f"{key} == {val}"
    if malformed == "next_line_val":
        # put equal sign but no value on same line (value on next line)
        return f"{key} =\n{val}"
    if malformed == "stray_token":
        stray = draw(st.sampled_from(["???", "!!!", "/*", "]]"]))
        return f"{key} = {val} {stray}"
    # ok
    return f"{key} = {val}"

# Table header generator
@st.composite
def table_header(draw):
    key = draw(st.one_of(dotted_key, simple_key, quoted_key_basic(), quoted_key_literal()))
    kind = draw(st.sampled_from(["standard", "array_table", "malformed_missing_bracket", "malformed_double_bracket"]))
    if kind == "standard":
        return f"[{key}]"
    if kind == "array_table":
        return f"[[{key}]]"
    if kind == "malformed_missing_bracket":
        # missing closing bracket
        return f"[{key}"
    return f"[[{key}]"  # doubled opening bracket but missing closing

# Comment-only line
comment_line = st.one_of(
    st.just(""),  # empty line
    st.builds(lambda s: "#" + s, st.text(alphabet=list(_printable_no_quote_backslash + _control_chars), min_size=0, max_size=60))
)

# Expression (key_value, table, or comment)
@st.composite
def expression(draw, value_strategy):
    typ = draw(st.sampled_from(["kv", "table", "comment"]))
    if typ == "kv":
        return draw(key_value_line(value_strategy))
    if typ == "table":
        return draw(table_header())
    return draw(comment_line)

# Document generator
@st.composite
def document(draw):
    # number of lines
    n = draw(st.integers(min_value=0, max_value=25))
    exprs = []
    # allow injection of deep nesting occasionally
    if draw(st.booleans()):
        # insert a deep nested empty array as a value assigned to a key
        k = draw(st.one_of(simple_key, quoted_key_basic(), quoted_key_literal()))
        exprs.append(f"{k} = {draw(deep_nesting)}")
    for _ in range(n):
        exprs.append(draw(expression(values)))
    # maybe append an array-of-tables header and body
    if draw(st.booleans()):
        arr_tbl_key = draw(dotted_key)
        exprs.append(f"[[{arr_tbl_key}]]")
        # maybe include inline table as row
        if draw(st.booleans()):
            kvs = []
            for _ in range(draw(st.integers(min_value=0, max_value=4))):
                k = draw(st.one_of(simple_key, quoted_key_basic(), quoted_key_literal()))
                v = draw(values)
                kvs.append(f"{k} = {v}")
            exprs.append(" ".join(kvs) if kvs else "")
    # occasionally create duplicate key lines to trigger rejection
    if draw(st.booleans()):
        dup_key = draw(simple_key)
        exprs.append(f"{dup_key} = {draw(values)}")
        exprs.append(f"{dup_key} = {draw(values)}")  # duplicate
    # join with newlines; sometimes CRLF
    use_crlf = draw(st.booleans())
    newline = "\r\n" if use_crlf and draw(st.booleans()) else "\n"
    doc = newline.join(exprs)
    # sometimes omit trailing newline (documents without trailing newline are allowed)
    if draw(st.booleans()):
        return doc
    else:
        return doc + newline

# Final strategy for a TOML document as str
strategy = document()
```