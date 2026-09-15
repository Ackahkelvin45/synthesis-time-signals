```python
from hypothesis import strategies as st
import json

# Helper character sets (no raw NUL \x00)
_ascii_letters = "".join(chr(c) for c in range(ord("A"), ord("Z") + 1)) + "".join(chr(c) for c in range(ord("a"), ord("z") + 1))
_ascii_digits = "".join(chr(c) for c in range(ord("0"), ord("9") + 1))
_punct = "!#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
# control characters except NUL(0), LF(10), CR(13) (LF/CR handled separately)
_ctrls_no_nl = "".join(chr(c) for c in range(1, 32) if c not in (10, 13))
# some non-ASCII to exercise unicode
_unicode_samples = "".join(chr(c) for c in [0x00A9, 0x20AC, 0x03A9, 0x0416, 0x4E2D, 0x1F600])

# Helpers for constructing escaped sequences
def _u4():
    # generate a \uXXXX escape sequence (as characters backslash + u + hex)
    import random
    return "\\u" + "".join("%X" % x for x in [random.randint(0, 15) for _ in range(4)])


# Basic pieces as strategies producing TOML tokens (strings)
# 1) Keys
unquoted_key = st.one_of(
    # Common safe unquoted key
    st.from_regex(r"[A-Za-z0-9_-]{1,20}", fullmatch=True),
    # Very long key to exercise limits
    st.from_regex(r"[A-Za-z0-9_-]{100,10000}", fullmatch=True),
    # Non-ASCII bare keys (to test rejection cases)
    st.from_regex(r"[\w\-\u00A0-\uFFFF]{1,20}", fullmatch=True),
)

# Quoted keys use the same string strategies as values for BASIC_STRING or LITERAL_STRING
# We'll define string strategies below and reuse for quoted keys.

# 2) Primitive values (strings, numbers, booleans, datetimes)
# Strategy for basic (double-quoted) string token
@st.composite
def basic_string(draw, allow_unterminated=False, multiline=False):
    # choose content characters; multiline allows newlines
    max_len = draw(st.integers(min_value=0, max_value=120))
    # candidate characters: letters, digits, punctuation except double-quote/backslash (will be escaped), some control chars
    chars = []
    for _ in range(max_len):
        choice = draw(st.integers(min_value=0, max_value=7))
        if choice == 0:
            chars.append(draw(st.sampled_from(list(_ascii_letters))))
        elif choice == 1:
            chars.append(draw(st.sampled_from(list(_ascii_digits))))
        elif choice == 2:
            chars.append(draw(st.sampled_from(list(_punct))))
        elif choice == 3:
            # raw control (allowed except newline in basic-string)
            c = draw(st.sampled_from(list(_ctrls_no_nl)))
            chars.append(c)
        elif choice == 4:
            # unicode sample
            chars.append(draw(st.sampled_from(list(_unicode_samples))))
        elif choice == 5:
            # explicit escape sequences like \n, \t, \r, \" , \\ , \uXXXX
            esc = draw(st.sampled_from(["\\n", "\\r", "\\t", "\\b", "\\f", "\\\"", "\\\\", "\\/"]))
            chars.append(esc)
        else:
            # arbitrary hex unicode escape
            # build a \uXXXX escape
            hex4 = draw(st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4))
            chars.append("\\u" + hex4)
    content = "".join(chars)
    if multiline:
        # triple-quoted basic string allows newlines and carriage returns
        # add some newline characters occasionally
        if draw(st.booleans()):
            content = content + "\n" + draw(st.text(min_size=0, max_size=50))
        out = '"""' + content + '"""'
        if allow_unterminated and draw(st.just(True)) and draw(st.booleans()):
            # drop closing triple quotes -> unterminated
            out = out[:-3]
        return out
    else:
        # ensure internal double quotes/backslashes are escaped
        content_escaped = content.replace("\\", "\\\\").replace('"', '\\"')
        out = '"' + content_escaped + '"'
        if allow_unterminated and draw(st.booleans()):
            # possibly drop the closing quote to create unterminated string (near-malformed)
            if draw(st.booleans()):
                out = out[:-1]  # remove trailing quote
        return out

# Literal string (single-quoted)
@st.composite
def literal_string(draw, allow_unterminated=False, multiline=False):
    max_len = draw(st.integers(min_value=0, max_value=80))
    chars = []
    for _ in range(max_len):
        choice = draw(st.integers(min_value=0, max_value=5))
        if choice == 0:
            chars.append(draw(st.sampled_from(list(_ascii_letters))))
        elif choice == 1:
            chars.append(draw(st.sampled_from(list(_ascii_digits))))
        elif choice == 2:
            # punctuation except single-quote
            c = draw(st.sampled_from([p for p in list(_punct) if p != "'"]))
            chars.append(c)
        elif choice == 3:
            chars.append(draw(st.sampled_from(list(_unicode_samples))))
        else:
            # raw control allowed? literal single-quoted cannot include newlines; include some other controls
            c = draw(st.sampled_from(list(_ctrls_no_nl)))
            chars.append(c)
    content = "".join(chars)
    if multiline:
        out = "'''" + content + "'''"
        if allow_unterminated and draw(st.booleans()):
            out = out[:-3]
        return out
    else:
        out = "'" + content + "'"
        if allow_unterminated and draw(st.booleans()):
            out = out[:-1]
        return out

# Numeric strategies
# Decimal int with underscores and optional leading zeros and signs
@st.composite
def dec_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    # allow leading zeros like 007
    leading_zero = draw(st.booleans())
    if leading_zero:
        # generate a string of digits with possible underscores
        num = draw(st.from_regex(r"[0-9]([0-9_]{0,20})", fullmatch=True))
    else:
        # normal no-leading-zero pattern but we allow single zero
        num = draw(st.from_regex(r"[1-9]([0-9_]{0,20})|0", fullmatch=True))
    return sign + num

@st.composite
def hex_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    body = draw(st.from_regex(r"0x[0-9A-Fa-f]([0-9A-Fa-f_]{0,30})", fullmatch=True))
    return sign + body

@st.composite
def oct_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    body = draw(st.from_regex(r"0o[0-7]([0-7_]{0,30})", fullmatch=True))
    return sign + body

@st.composite
def bin_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    body = draw(st.from_regex(r"0b[01]([01_]{0,30})", fullmatch=True))
    return sign + body

# Floating point including weird forms: 1., .5, exponents, huge exponents, inf/nan
@st.composite
def float_tok(draw):
    choice = draw(st.integers(min_value=0, max_value=5))
    if choice == 0:
        # normal float with optional fraction and exponent
        intpart = draw(st.from_regex(r"[0-9]([0-9_]{0,10})", fullmatch=True))
        frac = draw(st.one_of(st.just(""), st.from_regex(r"\.[0-9]([0-9_]{0,10})", fullmatch=True)))
        exp = draw(st.one_of(st.just(""), st.from_regex(r"[eE][+-]?[0-9]([0-9_]{0,5})", fullmatch=True)))
        return intpart + frac + exp
    elif choice == 1:
        # 1. style
        intpart = draw(st.from_regex(r"[0-9]([0-9_]{0,10})", fullmatch=True))
        return intpart + "."
    elif choice == 2:
        # .5 style
        frac = draw(st.from_regex(r"\.[0-9]([0-9_]{0,10})", fullmatch=True))
        return frac
    elif choice == 3:
        # huge exponent
        base = draw(st.from_regex(r"[0-9]([0-9_]{0,5})", fullmatch=True))
        exp = draw(st.from_regex(r"[eE][+-]?[0-9]{3,4}", fullmatch=True))
        return base + exp
    else:
        # inf or nan
        sign = draw(st.sampled_from(["", "+", "-"]))
        special = draw(st.sampled_from(["inf", "nan"]))
        return sign + special

# Boolean
bool_tok = st.sampled_from(["true", "false"])

# Date/time forms (allow calendar-invalid dates per notes)
date_tok = st.one_of(
    # LOCAL_DATE
    st.from_regex(r"\d{4}-\d{2}-\d{2}", fullmatch=True),
    # LOCAL_TIME
    st.from_regex(r"\d{2}:\d{2}:\d{2}(\.\d+)?", fullmatch=True),
    # LOCAL_DATE_TIME with space or T
    st.from_regex(r"\d{4}-\d{2}-\d{2}[ Tt]\d{2}:\d{2}:\d{2}(\.\d+)?", fullmatch=True),
    # OFFSET_DATE_TIME
    st.from_regex(r"\d{4}-\d{2}-\d{2}[ Tt]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})", fullmatch=True),
    # Calendar-invalid example
    st.just("1979-02-30"),
)

# 3) A value strategy that recursively allows arrays and inline tables
# We'll build a recursive strategy using st.deferred + st.recursive; base values are primitives

# Primitive value tokens (strings/numbers/booleans/dates)
primitive_value = st.one_of(
    basic_string(allow_unterminated=True, multiline=False),
    basic_string(allow_unterminated=True, multiline=True),
    literal_string(allow_unterminated=True, multiline=False),
    literal_string(allow_unterminated=True, multiline=True),
    dec_int(),
    hex_int(),
    oct_int(),
    bin_int(),
    float_tok(),
    bool_tok,
    date_tok,
)

# Helper to produce a comment (may include control bytes, but not NUL)
comment_tok = st.builds(lambda s: "#" + s, st.text(
    alphabet="".join([c for c in (_ascii_letters + _ascii_digits + _punct + _unicode_samples + _ctrls_no_nl)]),
    min_size=0, max_size=80
))

# Inline table generator - must not contain newlines inside
def make_inline_table(inner):
    # inner is a strategy producing a value token string (no newlines inside when used here)
    key_val = st.tuples(
        st.one_of(unquoted_key, basic_string(allow_unterminated=True, multiline=False), literal_string(allow_unterminated=True, multiline=False)),
        st.just(" = "),
        inner
    ).map(lambda parts: "".join(parts))
    # inline table can be empty {}, or have one or more keyvals separated by commas, possibly trailing comma
    kvs = st.lists(key_val, min_size=0, max_size=4)
    trailing_comma = st.booleans()
    def build(kv_list_trail):
        kv_list, trail = kv_list_trail
        if len(kv_list) == 0:
            return "{}"
        inner_txt = ", ".join(kv_list)
        if trail:
            inner_txt = inner_txt + ","
        return "{" + inner_txt + "}"
    return st.tuples(kvs, trailing_comma).map(build)

# Array generator - arrays can be multiline and contain comments/newlines and mixed types
def make_array(inner):
    # inner can be a value string (could itself be array or inline table)
    # create lists of values with possible comments/newlines between values
    element = inner
    # allow empty array
    elements = st.lists(element, min_size=0, max_size=6)
    # Insert optional comments/newlines between elements
    def build_list(elems):
        if len(elems) == 0:
            return "[]"
        # Mix in comments or newlines occasionally
        parts = []
        for i, e in enumerate(elems):
            # optionally add a comment before the value
            if draw_comment := False:
                pass
            parts.append(e)
        return "[" + ", ".join(parts) + "]"
    # We can't reference local draw here; instead construct using mapping
    return elements.map(lambda elems: "[" + ", ".join(elems) + "]")

# Because st.recursive requires functions, define the recursive value strategy
def _extend_for_recursive(inner):
    # inner is a strategy that produces a value token (string)
    return st.one_of(
        # Inline table containing inner-values (no newlines inside)
        make_inline_table(inner),
        # Array containing inner-values
        st.lists(inner, min_size=0, max_size=6).map(lambda elems: "[" + ", ".join(elems) + "]"),
    )

# Use st.recursive to create nested arrays and inline tables
# Set a generous max_leaves to allow deeper structures; Hypothesis will still temper generation
value_recursive = st.recursive(primitive_value, _extend_for_recursive, max_leaves=200)

# Additionally include a specific deep nesting generator that constructs extremely deep nested arrays (1..2048)
@st.composite
def deep_nested_array(draw):
    # pick depth with bias toward smaller but allow very deep
    depth = draw(st.one_of(
        st.integers(min_value=1, max_value=8),
        st.integers(min_value=8, max_value=64),
        st.integers(min_value=64, max_value=512),
        st.integers(min_value=512, max_value=2048),
    ))
    # pick a base primitive (not another nested structure) to place at the core
    base = draw(primitive_value)
    # Build nested brackets: "[" * depth + base + "]" * depth
    return "[" * depth + base + "]" * depth

# Combine both recursive and deep nested possibilities into a final value strategy
value_with_deep = st.one_of(value_recursive, deep_nested_array())

# 4) Key production: simple_key or dotted_key (allow quoted/unquoted)
simple_key = st.one_of(
    unquoted_key,
    basic_string(allow_unterminated=True, multiline=False),
    literal_string(allow_unterminated=True, multiline=False),
)

# Dotted key: simple_key (DOT simple_key)+
dotted_key = st.tuples(simple_key, st.lists(simple_key, min_size=1, max_size=4)).map(
    lambda t: t[0] + "." + ".".join(t[1])
)

key_any = st.one_of(simple_key, dotted_key)

# 5) Key-value line
@st.composite
def key_value_line(draw):
    k = draw(key_any)
    # sometimes produce malformed variants: missing '=', doubled '=', newline instead of value, stray token
    malformed_choice = draw(st.integers(min_value=0, max_value=9))
    if malformed_choice == 0:
        # missing equals: "k  value" or "k value" with no equals -> malformed
        v = draw(value_with_deep)
        sep = draw(st.sampled_from([" ", "  ", "\t", " \t "]))
        return k + sep + v
    elif malformed_choice == 1:
        # doubled equals
        v = draw(value_with_deep)
        return k + " == " + v
    elif malformed_choice == 2:
        # value on next line (grammar forbids a newline after '=' before the value)
        v = draw(value_with_deep)
        return k + " =" + "\n" + v
    elif malformed_choice == 3:
        # stray token after value
        v = draw(value_with_deep)
        junk = draw(st.text(alphabet="@#$%^&*", min_size=1, max_size=5))
        return k + " = " + v + " " + junk
    else:
        v = draw(value_with_deep)
        # normal well-formed
        # Occasionally include inline comment after = value
        if draw(st.booleans()):
            c = draw(comment_tok)
            return k + " = " + v + " " + c
        return k + " = " + v

# 6) Table and array-of-table lines
@st.composite
def standard_table_line(draw):
    k = draw(key_any)
    # possibility of missing closing bracket or doubled brackets to create near-malformed
    bad = draw(st.integers(min_value=0, max_value=9))
    if bad == 0:
        return "[" + k  # missing closing bracket
    elif bad == 1:
        return "[[" + k + "]]"  # actually an array-table in form of double brackets -> but for standard table this is a variant
    else:
        return "[" + k + "]"

@st.composite
def array_table_line(draw):
    k = draw(key_any)
    bad = draw(st.integers(min_value=0, max_value=9))
    if bad == 0:
        return "[[" + k  # missing closing double brackets
    elif bad == 1:
        return "[" + k + "]]"  # mismatched
    else:
        return "[[" + k + "]]"

# 7) Comment-only line or blank line
blank_or_comment = st.one_of(st.just(""), comment_tok)

# 8) Expression line: key_value, table, array_table, or comment
expression_line = st.one_of(
    key_value_line(),
    standard_table_line(),
    array_table_line(),
    comment_tok,
)

# Build full document: zero or more expressions separated by newlines.
# Include cases: empty documents, comment-only, no trailing newline.
document_lines = st.lists(expression_line, min_size=0, max_size=12)

# Optionally include CRLF line endings or LF. We'll produce join using either "\n" or "\r\n"
@st.composite
def document(draw):
    lines = draw(document_lines)
    # optionally include a final newline or not
    include_trailing_newline = draw(st.booleans())
    # choose line ending
    line_ending = draw(st.sampled_from(["\n", "\r\n"]))
    txt = line_ending.join(lines)
    if include_trailing_newline and txt != "":
        txt = txt + line_ending
    # Occasionally insert a stray NUL escape sequence (escaped) inside a string: '\u0000' allowed, but never raw \x00
    if draw(st.booleans()):
        # embed a \u0000 escape somewhere in the document as text
        insert = "\\u0000"
        pos = draw(st.integers(min_value=0, max_value=len(txt)))
        txt = txt[:pos] + insert + txt[pos:]
    # Also sometimes inject raw control characters (but not NUL) into comments or lines
    if draw(st.booleans()):
        ctrl = draw(st.sampled_from(list(_ctrls_no_nl)))
        pos = draw(st.integers(min_value=0, max_value=max(0, len(txt))))
        txt = txt[:pos] + ctrl + txt[pos:]
    return txt

# Final exported top-level strategy
strategy = document()
```