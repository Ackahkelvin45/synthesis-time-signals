```python
from hypothesis import strategies as st
import json

# Helper primitives
_ASCII_ALNUM = st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7F), min_size=1, max_size=12).map(
    lambda s: ''.join(ch for ch in s if ch.isalnum() or ch in "-_") or "a"
)

# Avoid emitting raw NUL (\x00) in outputs (harness skips NUL-containing files).
_NON_NUL_CONTROL = st.one_of(
    st.characters(min_codepoint=1, max_codepoint=0x1F).filter(lambda c: c != '\x00'),
    st.characters(min_codepoint=0x7F, max_codepoint=0x9F)
)

# Escapes (including some invalid ones to create near-valid-but-malformed inputs)
_ESCAPES = st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\"', '\\\\', '\\/', '\\u0000', '\\u00E9', '\\U0001F600', '\\q'])

# Basic string content: mix printable ASCII, Unicode, and control bytes except NUL.
_BASIC_CHUNK = st.one_of(
    st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7F).filter(lambda c: c != '"'), min_size=0, max_size=8),
    st.text(alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF), min_size=1, max_size=6),
    _NON_NUL_CONTROL.map(lambda c: c)
)

# Compose content with some escapes interspersed
_BASIC_CONTENT = st.lists(st.one_of(_BASIC_CHUNK, _ESCAPES), min_size=0, max_size=6).map(''.join)

# Literal string content (no escapes processed)
_LITERAL_CONTENT = st.text(min_size=0, max_size=20).map(lambda s: s.replace("'", "’"))  # avoid closing quote by replacement

# Multi-line content
_ML_CONTENT = st.lists(st.one_of(st.text(min_size=0, max_size=40), _ESCAPES, _NON_NUL_CONTROL.map(lambda c: c)), min_size=0, max_size=6).map('\n'.join)

# Integer generators: decimal (with optional leading zeros and underscores), hex/octal/bin
_DEC_INT = st.one_of(
    st.integers(min_value=-10**40, max_value=10**40).map(lambda n: str(n)),  # arbitrary magnitude
    st.integers(min_value=0, max_value=9999).map(lambda n: ("0" + str(n)) if st.booleans().example() else str(n)),
    st.integers(min_value=0, max_value=10**12).map(lambda n: '_'.join([str(n)])[0:1] + str(n))  # will be mostly normal but keep underscores possibility
)

_HEX_INT = st.text(alphabet='0123456789abcdefABCDEF_', min_size=1, max_size=16).map(lambda s: "0x" + s.strip("_"))
_OCT_INT = st.text(alphabet='01234567_', min_size=1, max_size=12).map(lambda s: "0o" + s.strip("_"))
_BIN_INT = st.text(alphabet='01_', min_size=1, max_size=64).map(lambda s: "0b" + s.strip("_"))

_INTEGER = st.one_of(_DEC_INT, _HEX_INT, _OCT_INT, _BIN_INT)

# Float generators: include forms like 1., .5, exponent extremes, inf/nan
_FLOAT_SIMPLE = st.one_of(
    st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, '.6g')),
    st.integers(min_value=-10**6, max_value=10**6).map(lambda n: f"{n}."),
    st.floats(allow_nan=True, allow_infinity=True).map(lambda f: "inf" if f == float('inf') else ("-inf" if f == float('-inf') else ("nan" if str(f) == 'nan' else format(f, '.6g')))),
    st.integers(min_value=0, max_value=999999999).map(lambda m: f".{str(m)}"),
    st.integers(min_value=1, max_value=9999).flatmap(lambda e: st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f"{abs(f):.3f}e{e}"))
)

# Date/time: generate several calendar and time formats (may be invalid calendar dates as allowed)
_DATE = st.one_of(
    st.tuples(st.integers(0, 9999), st.integers(1, 12), st.integers(1, 31)).map(lambda t: f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"),
    st.tuples(st.integers(0, 9999), st.integers(1, 12), st.integers(1, 31), st.integers(0, 23), st.integers(0, 59), st.integers(0, 59)).map(
        lambda t: f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}T{t[3]:02d}:{t[4]:02d}:{t[5]:02d}Z"
    ),
    st.tuples(st.integers(0, 9999), st.integers(1, 12), st.integers(1, 31), st.integers(0, 23), st.integers(0, 59), st.integers(0, 59), st.integers(-12, 14), st.integers(0, 59)).map(
        lambda t: f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}{'+' if t[6]>=0 else '-'}{abs(t[6]):02d}:{t[7]:02d}"
    ),
    st.tuples(st.integers(0, 9999), st.integers(0, 23), st.integers(0, 59), st.integers(0, 59)).map(lambda t: f"{t[0]:04d}T{t[1]:02d}:{t[2]:02d}:{t[3]:02d}")
)

# Boolean
_BOOL = st.sampled_from(["true", "false"])

# String producers (including unterminated and malformed variants)
@st.composite
def basic_string(draw, allow_unterminated=False):
    content = draw(_BASIC_CONTENT)
    # Sometimes inject raw control bytes (except NUL) directly
    if draw(st.booleans()):
        ctrl = draw(_NON_NUL_CONTROL)
        content += ctrl
    if allow_unterminated and draw(st.booleans()):
        # produce an unterminated string (no closing quote) or doubled quote
        if draw(st.booleans()):
            return '"' + content  # no closing quote
        else:
            return '""' + content + '"'  # stray extra opening quotes cause near-valid malformed input
    return '"' + content + '"'

@st.composite
def literal_string(draw, allow_unterminated=False):
    content = draw(_LITERAL_CONTENT)
    if allow_unterminated and draw(st.booleans()):
        return "'" + content  # unterminated
    return "'" + content + "'"

@st.composite
def ml_basic_string(draw):
    content = draw(_ML_CONTENT)
    return '"""' + content + '"""'

@st.composite
def ml_literal_string(draw):
    content = draw(_ML_CONTENT)
    return "'''" + content + "'''"

# Inline table: no newlines inside; allow trailing comma
@st.composite
def inline_table(draw, max_nesting=0):
    # produce between 0 and 6 key=val pairs
    n = draw(st.integers(min_value=0, max_value=6))
    pairs = []
    for i in range(n):
        k = draw(st.one_of(_ASCII_ALNUM, basic_string(), literal_string()))
        # ensure quoted key strings are proper source text (we allow the quotes to be present)
        v = draw(st.one_of(
            basic_string(),
            literal_string(),
            ml_basic_string(),
            ml_literal_string(),
            _INTEGER,
            _FLOAT_SIMPLE,
            _BOOL,
            _DATE
        ))
        pairs.append(f"{k} = {v}")
    # Optionally include trailing comma
    if draw(st.booleans()) and pairs:
        s = ", ".join(pairs) + ","
    else:
        s = ", ".join(pairs)
    return "{" + s + "}"

# Arrays: allow nested arrays; include comments and newlines inside arrays
@st.composite
def array_value(draw, max_nesting=0):
    # Decide nesting depth: sometimes shallow, sometimes deep (including band 1500-2048)
    deep_choice = draw(st.one_of(
        st.integers(min_value=0, max_value=4),
        st.integers(min_value=1500, max_value=2048),
        st.integers(min_value=5, max_value=50)
    ))
    # Build an inner element (non-recursive to avoid huge growth)
    inner = draw(st.one_of(
        basic_string(),
        literal_string(),
        ml_basic_string(),
        ml_literal_string(),
        _INTEGER,
        _FLOAT_SIMPLE,
        _BOOL,
        _DATE,
        inline_table()
    ))
    # If deep_choice is large, build nested arrays iteratively to reach desired nesting depth
    if deep_choice > 100:
        # build nested brackets quickly: [[[[ ... inner ... ]]]]
        s = inner
        for _ in range(deep_choice):
            # sometimes leave empty inner arrays to create empty containers
            if draw(st.booleans()):
                s = "[" + s + "]"
            else:
                s = "[" + (" " if draw(st.booleans()) else "") + s + "]"
        # Possibly make it an explicit array (with commas)
        if draw(st.booleans()):
            s = "[" + s + "]"
        return s
    else:
        # Build a list with possibly comments and newlines; allow trailing comma
        m = draw(st.integers(min_value=0, max_value=6))
        elements = []
        for i in range(m):
            elem = draw(st.one_of(
                basic_string(),
                literal_string(),
                ml_basic_string(),
                ml_literal_string(),
                _INTEGER,
                _FLOAT_SIMPLE,
                _BOOL,
                _DATE,
                inline_table(),
                array_value(max_nesting=max(0, max_nesting - 1))
            ))
            # Insert comment or newline occasionally
            if draw(st.booleans()):
                if draw(st.booleans()):
                    elem = elem + " # " + draw(st.text(min_size=0, max_size=20))
                else:
                    elem = elem + ("\r\n" if draw(st.booleans()) else "\n")
            elements.append(elem)
        if draw(st.booleans()) and elements:
            body = ", ".join(elements) + ","
        else:
            body = ", ".join(elements)
        return "[" + body + "]"

# Key generator: unquoted (ASCII), quoted, dotted keys, long keys, non-ASCII bare keys (to trigger rejection)
@st.composite
def key_name(draw):
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind == 0:
        # unquoted key with possibility of being very long
        if draw(st.booleans()):
            # very long key up to 10000 characters (rare)
            length = draw(st.one_of(st.integers(min_value=1000, max_value=10000), st.integers(min_value=1, max_value=50)))
            # build from safe characters
            key = ''.join(draw(st.sampled_from(list("abcdefghijklmnopqrstuvwxyz0123456789_-"))) for _ in range(length))
            return key
        else:
            return draw(_ASCII_ALNUM)
    elif kind == 1:
        return draw(basic_string())
    elif kind == 2:
        return draw(literal_string())
    elif kind == 3:
        # dotted key: join multiple simple keys
        parts = [draw(st.one_of(_ASCII_ALNUM, basic_string(), literal_string())) for _ in range(draw(st.integers(min_value=2, max_value=4)))]
        return '.'.join(parts)
    else:
        # non-ASCII bare key (expected to be rejected by parser) — produce to test rejection path
        return draw(st.text(min_size=1, max_size=10).filter(lambda s: any(ord(c) > 127 for c in s)))

# Value generator: covers all kinds, includes malformed examples like missing '=' handled at expression level
@st.composite
def value_text(draw, max_nesting=6):
    choices = [
        basic_string(),
        literal_string(),
        ml_basic_string(),
        ml_literal_string(),
        _INTEGER,
        _FLOAT_SIMPLE,
        _BOOL,
        _DATE,
        inline_table(max_nesting=max_nesting),
        array_value(max_nesting=max_nesting)
    ]
    # Prefer non-recursive when max_nesting low
    if max_nesting <= 0:
        choices = [c for c in choices if c is not inline_table and c is not array_value]
    # include also malformed possibilities: unterminated string or stray token
    malformed = draw(st.integers(min_value=0, max_value=6))
    if malformed == 0:
        return draw(basic_string(allow_unterminated=True))
    if malformed == 1:
        return draw(literal_string(allow_unterminated=True))
    if malformed == 2:
        # stray token or doubled delimiter
        return choice := draw(st.sampled_from(["@", "==", "=", " , , ", "[]]", "[[", "]", "???"]))
    return draw(st.one_of(*choices))

# Key-value line generator
@st.composite
def key_value_line(draw, max_nesting=6):
    k = draw(key_name())
    # sometimes produce a missing '=' or double '=' to produce near-valid malformed inputs
    eq_choice = draw(st.integers(min_value=0, max_value=10))
    if eq_choice == 0:
        sep = " "  # missing equals
    elif eq_choice == 1:
        sep = " == "
    else:
        sep = " = "
    v = draw(value_text(max_nesting=max_nesting))
    # optionally add inline comment
    if draw(st.booleans()):
        comment = " # " + draw(st.text(min_size=0, max_size=40))
    else:
        comment = ""
    return k + sep + v + comment

# Table line generators
@st.composite
def standard_table_line(draw):
    k = draw(key_name())
    return "[" + k + "]"

@st.composite
def array_table_line(draw):
    k = draw(key_name())
    return "[[" + k + "]]"

# Expression: key_value, table, or comment-only
@st.composite
def expression_line(draw, max_nesting=6):
    choice = draw(st.integers(min_value=0, max_value=6))
    if choice <= 3:
        return draw(key_value_line(max_nesting=max_nesting))
    elif choice == 4:
        return draw(standard_table_line())
    elif choice == 5:
        return draw(array_table_line())
    else:
        # comment-only
        if draw(st.booleans()):
            return "#" + draw(st.text(min_size=0, max_size=80))
        else:
            return ""  # empty line

# Document generator: produce multiple expressions; include comment-only and empty documents
@st.composite
def toml_document(draw):
    # Decide document complexity and nesting band
    max_nesting = draw(st.one_of(
        st.integers(min_value=0, max_value=6),
        st.integers(min_value=50, max_value=200),
        st.integers(min_value=1500, max_value=2048)
    ))
    # Number of top-level expressions
    count = draw(st.integers(min_value=0, max_value=20))
    lines = []
    seen_keys = []
    for i in range(count):
        # Occasionally insert duplicate keys or duplicate tables to hit rejection cases
        if draw(st.booleans()) and seen_keys and draw(st.integers(min_value=0, max_value=20)) == 0:
            # Repeat a previous key line to create duplicate
            lines.append(seen_keys[-1])
            continue
        expr = draw(expression_line(max_nesting=max_nesting))
        # track simple key lines for duplication
        if '=' in expr and not expr.strip().startswith('#'):
            seen_keys.append(expr.split('=')[0].strip())
        lines.append(expr)
    # Also include possibility of a super-table defined after sub-table (allowed)
    if draw(st.booleans()):
        # add a couple table definitions
        lines.append(draw(standard_table_line()))
        lines.append(draw(key_value_line(max_nesting=max_nesting)))
    # Combine lines with random newline styles and optional missing trailing newline
    newline = draw(st.sampled_from(["\n", "\r\n"]))
    doc = newline.join(lines)
    # Optionally append a stray token or comment or no trailing newline
    tail_choice = draw(st.integers(min_value=0, max_value=6))
    if tail_choice == 0:
        doc += newline + "# final comment"
    elif tail_choice == 1:
        doc += newline + "@@@"
    elif tail_choice == 2:
        # No trailing newline
        doc = doc
    else:
        # ensure document sometimes ends with newline
        doc += newline
    return doc

# The top-level strategy required by the harness
strategy = toml_document()
```