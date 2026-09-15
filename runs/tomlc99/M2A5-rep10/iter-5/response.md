```python
from hypothesis import strategies as st
import json

# Character sets (exclude NUL '\x00' because the harness skips NUL-terminated inputs)
ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
ASCII_DIGITS = "0123456789"
BARE_KEY_CHARS = ASCII_LETTERS + ASCII_DIGITS + "-_"
# Control chars allowed in strings except NUL
CONTROL_CHARS = "".join(chr(c) for c in range(1, 32)) + chr(127)
PRINTABLE = "".join(chr(c) for c in range(32, 127) if chr(c) != '"')
# For basic-string content: allow printable excluding double-quote and backslash and newline
BASIC_CONTENT_ALPHABET = "".join(
    ch for ch in (PRINTABLE + CONTROL_CHARS + "\t")
    if ch not in ['"', '\\', '\n', '\r', '\x00']
)
# For literal strings: single-quote cannot appear inside
LITERAL_CONTENT_ALPHABET = "".join(
    ch for ch in (PRINTABLE + CONTROL_CHARS + "\t")
    if ch not in ["'", "\n", "\r", "\x00"]
)

# Helper small strategies
_sign = st.sampled_from(["", "+", "-"])
underscore_inserter = lambda s: st.just(s)  # placeholder to keep code clear; we'll construct strings manually

# Key generators
_unquoted_key = st.text(alphabet=BARE_KEY_CHARS, min_size=1, max_size=30)
_empty_quoted_key = st.just('""')
_quoted_basic_key = st.text(alphabet=BASIC_CONTENT_ALPHABET, min_size=0, max_size=20).map(lambda s: '"' + s.replace('"', '') + '"')
_quoted_literal_key = st.text(alphabet=LITERAL_CONTENT_ALPHABET, min_size=0, max_size=20).map(lambda s: "'" + s.replace("'", "") + "'")
simple_key = st.one_of(_unquoted_key, _quoted_basic_key, _quoted_literal_key, _empty_quoted_key)

# Dotted keys
dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: ".".join(parts))

# Quoted string generators (four forms)
def _basic_string_strategy():
    # Include variants: clean content, with valid escapes, with invalid escapes, with control chars raw, and unterminated
    content_clean = st.text(alphabet=BASIC_CONTENT_ALPHABET, min_size=0, max_size=40)
    # produce valid escapes e.g. \n \t \\ \" \u1234 etc
    esc_choices = ["\\n", "\\t", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\/"]
    esc_unicode = st.builds(lambda h: "\\u%04x" % h, st.integers(0, 0xFFFF))
    esc_exunicode = st.builds(lambda h: "\\U%08x" % h, st.integers(0, 0xFFFFFFFF))
    with_valid_escapes = st.lists(st.one_of(st.text(alphabet=BASIC_CONTENT_ALPHABET, min_size=0, max_size=6), st.sampled_from(esc_choices), esc_unicode, esc_exunicode), min_size=1, max_size=8).map("".join)
    # invalid escape example
    invalid_escape = st.just("\\q")
    with_invalid = st.lists(st.one_of(st.text(alphabet=BASIC_CONTENT_ALPHABET, min_size=0, max_size=6), invalid_escape), min_size=1, max_size=6).map("".join)
    # unterminated: missing final quote
    unterminated = st.text(alphabet=BASIC_CONTENT_ALPHABET + "\\", min_size=1, max_size=40).map(lambda s: '"' + s)  # missing end quote
    return st.one_of(
        content_clean.map(lambda s: '"' + s + '"'),
        with_valid_escapes.map(lambda s: '"' + s + '"'),
        with_invalid.map(lambda s: '"' + s + '"'),
        unterminated
    )

def _ml_basic_string_strategy():
    # Multiline basic: """ ... """
    # allow backslash-newline sequences (line continuation) and escapes
    inner = st.lists(st.one_of(
        st.text(alphabet=BASIC_CONTENT_ALPHABET, min_size=0, max_size=20),
        st.just('\\\n'),
        st.just('\\\r\n'),
        st.builds(lambda h: "\\u%04x" % h, st.integers(0, 0xFFFF))
    ), min_size=0, max_size=8).map("".join)
    # possibility of unterminated triple quote
    unterminated = inner.map(lambda s: '"""' + s)
    return st.one_of(
        inner.map(lambda s: '"""' + s + '"""'),
        unterminated
    )

def _literal_string_strategy():
    content = st.text(alphabet=LITERAL_CONTENT_ALPHABET, min_size=0, max_size=50).map(lambda s: "'" + s + "'")
    return content

def _ml_literal_string_strategy():
    inner = st.text(alphabet=LITERAL_CONTENT_ALPHABET + "\n\r", min_size=0, max_size=200)
    # allow unterminated
    return st.one_of(
        inner.map(lambda s: "'''" + s + "'''"),
        inner.map(lambda s: "'''" + s)  # unterminated
    )

basic_string = _basic_string_strategy()
ml_basic_string = _ml_basic_string_strategy()
literal_string = _literal_string_strategy()
ml_literal_string = _ml_literal_string_strategy()

string_value = st.one_of(basic_string, ml_basic_string, literal_string, ml_literal_string)

# Integer generators (dec, hex, oct, bin; allow leading zeros, underscores, extremes)
def _dec_int():
    # produce strings like +007, -1_000, 9223372036854775808
    sign = st.sampled_from(["", "+", "-"])
    # allow leading zeros
    digits = st.one_of(
        st.from_regex(r"[0-9]+", fullmatch=True),
        st.builds(lambda n: "0" * n + "7", st.integers(0, 5)),  # leading zeros variant
        st.builds(lambda s: s, st.text(alphabet=ASCII_DIGITS + "_", min_size=1, max_size=20))
    )
    return st.tuples(sign, digits).map(lambda t: t[0] + t[1])

def _hex_int():
    hex_digits = st.text(alphabet="0123456789abcdefABCDEF_", min_size=1, max_size=20)
    return st.builds(lambda h: "0x" + h, hex_digits)

def _oct_int():
    oct_digits = st.text(alphabet="01234567_", min_size=1, max_size=20)
    return st.builds(lambda h: "0o" + h, oct_digits)

def _bin_int():
    bin_digits = st.text(alphabet="01_", min_size=1, max_size=20)
    return st.builds(lambda h: "0b" + h, bin_digits)

integer_value = st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

# Float generators (including INF/NAN, 1., .5, exponentials, extremes)
def _float_standard():
    sign = st.sampled_from(["", "+", "-"])
    # variants: 1., .5, 1.0, 1e10, 1.0e-10, 1e309
    integer_part = st.one_of(st.integers(min_value=0, max_value=9999999999).map(str),
                             st.from_regex(r"[0-9_]+", fullmatch=True))
    frac_part = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.from_regex(r"[0-9_]+", fullmatch=True)))
    expo = st.one_of(st.just(""), st.builds(lambda e: "e" + e, st.from_regex(r"[+-]?[0-9_]+", fullmatch=True)))
    return st.tuples(sign, integer_part, frac_part, expo).map(lambda t: t[0] + t[1] + t[2] + t[3])

def _float_inf_nan():
    signed = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
    return signed

float_value = st.one_of(_float_standard(), _float_inf_nan())

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time generators (offset date-time, local date-time, local date, local time)
def _two(dmin, dmax):
    return st.integers(min_value=dmin, max_value=dmax).map(lambda n: "%02d" % n)

_year = st.integers(min_value=0, max_value=9999).map(lambda y: "%04d" % y)
_month = _two(1, 12)
_day = _two(1, 31)  # calendar-invalid allowed
_hour = _two(0, 23)
_minute = _two(0, 59)
_second = _two(0, 60)
frac = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.from_regex(r"[0-9]+", fullmatch=True)))
offset = st.one_of(st.just("Z"), st.tuples(st.sampled_from(["+", "-"]), _hour, st.just(":"), _minute).map(lambda t: t[0] + t[1] + t[2] + t[3]))
delim = st.sampled_from(["T", "t", " "])

offset_datetime = st.tuples(_year, st.just("-"), _month, st.just("-"), _day, delim, _hour, st.just(":"), _minute, st.just(":"), _second, frac, offset).map(lambda t: "".join(t))
local_datetime = st.tuples(_year, st.just("-"), _month, st.just("-"), _day, delim, _hour, st.just(":"), _minute, st.just(":"), _second, frac).map(lambda t: "".join(t))
local_date = st.tuples(_year, st.just("-"), _month, st.just("-"), _day).map(lambda t: "".join(t))
local_time = st.tuples(_hour, st.just(":"), _minute, st.just(":"), _second, frac).map(lambda t: "".join(t))

date_time_value = st.one_of(offset_datetime, local_datetime, local_date, local_time)

# Base primitive values (non-recursive)
primitive_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value
)

# We'll use st.recursive to build arrays and inline tables recursively.
# Each strategy returns a string representing the TOML textual value.

# Comments and NLs to intersperse (including tabs, CRLF)
_comment_text = st.text(alphabet=PRINTABLE + CONTROL_CHARS, min_size=0, max_size=40)
comment = _comment_text.map(lambda s: "#" + s)
nl = st.sampled_from(["\n", "\r\n"])

# Helper to maybe add inline comments or whitespace
def maybe_ws_and_comment(s):
    # randomly add whitespace and comment after a value inside constructions
    # But here we return a string; we'll use in composites instead of a pure function.
    return s

# Compose recursive containers
def _extend_children(child):
    # child is a strategy producing TOML value strings
    # Build arrays and inline tables that contain child values
    # Note: these generators must return strings
    @st.composite
    def array_builder(draw):
        # Optionally produce an explicitly deeply nested array (band up to 2048)
        deep_choice = draw(st.booleans())
        if deep_choice:
            # Prefer small depth but sometimes produce extreme depths
            depth = draw(st.one_of(
                st.integers(min_value=1, max_value=8),
                st.integers(min_value=9, max_value=64),
                st.integers(min_value=65, max_value=512),
                st.integers(min_value=513, max_value=2048)
            ))
            # Use '0' as leaf; ensure no NULs
            inner = "0"
            return "[" * depth + inner + "]" * depth
        # Otherwise produce a normal array with comments/newlines and mixed types
        size = draw(st.integers(min_value=0, max_value=6))
        # elements may include comments or NLs between and around
        elems = []
        for i in range(size):
            # sometimes use nested child value, sometimes add a stray token or malformed element
            v = draw(child)
            # random chance to introduce trailing comma or stray token as malformed
            if draw(st.booleans()):
                # sometimes append a stray token like ']' or '=' to create near-malformed inputs
                if draw(st.booleans()):
                    v = v + draw(st.sampled_from(["", " ", " ]", " = ", " ,", " stray"]))
            elems.append(v)
        # Join elements with commas; allow trailing comma
        trailing_comma = draw(st.booleans())
        # Insert comments/newlines randomly between elements
        parts = []
        for i, e in enumerate(elems):
            parts.append(e)
            if i != len(elems) - 1:
                # separator with comma and optional space and optional comment
                sep = ","
                if draw(st.booleans()):
                    sep += " "
                if draw(st.booleans()):
                    sep += "#" + draw(_comment_text)
                parts.append(sep)
        if trailing_comma and len(elems) > 0:
            parts.append(",")
        inner_text = "".join(parts)
        # Allow multiline arrays with newlines and comments around
        if draw(st.booleans()):
            # wrap with newlines and comments
            prefix = ""
            suffix = ""
            if draw(st.booleans()):
                prefix = draw(nl)
            if draw(st.booleans()):
                suffix = draw(nl)
            return "[" + prefix + inner_text + suffix + "]"
        return "[" + inner_text + "]"

    @st.composite
    def inline_table_builder(draw):
        # Allow empty inline table
        if draw(st.booleans()):
            # sometimes include trailing comma in empty inline table: "{,}" is malformed; produce "{}" or "{ }"
            if draw(st.booleans()):
                return "{}"
            else:
                return "{ }"
        # Non-empty inline table: key = value pairs separated by commas
        n = draw(st.integers(min_value=1, max_value=6))
        kvs = []
        for i in range(n):
            k = draw(simple_key)
            v = draw(child)
            # optionally include newline inside inline table to produce invalid case (parser rejects)
            if draw(st.booleans()):
                # create newline inside (malformed per parser)
                kv = k + " = " + v + draw(st.sampled_from(["\n", "\r\n"]))  # newline inside inline table
            else:
                kv = k + " = " + v
            kvs.append(kv)
        # Join with commas; allow trailing comma
        trailing = draw(st.booleans())
        body = ", ".join(kvs)
        if trailing:
            body = body + ","
        # allow inserted stray token sometimes
        if draw(st.booleans()):
            body = body + draw(st.sampled_from(["", " ]", " }", " stray"]))
        return "{" + body + "}"

    # Also allow nested inline-table-as-value like nested inline table literal string for extra recursion
    @st.composite
    def nested_inline_table(draw):
        # build a one-key inline table whose value is another inline table (use child to allow many types)
        k = draw(simple_key)
        v = draw(child)
        return "{" + k + " = " + v + "}"

    return st.one_of(array_builder(), inline_table_builder(), nested_inline_table())

# Build the recursive value strategy
value = st.recursive(primitive_value, _extend_children, max_leaves=2000)

# Expression generators: key = value, table headers, array tables, comment-only lines
@st.composite
def key_value_line(draw):
    # choose dotted or simple key
    key_choice = draw(st.one_of(simple_key, dotted_key))
    # introduce possibility of duplicate keys by drawing same key from global later in document builder
    eq_ws = draw(st.one_of(st.just(" = "), st.just("="), st.just(" ="), st.just("= "), st.just(" =  "), st.just("=  ")))
    val = draw(value)
    # Occasionally produce a value on the next line (malformed) or stray token
    if draw(st.booleans()):
        # malformed: put newline after '=' and then the value on the following line (parser rejects)
        if draw(st.booleans()):
            return key_choice + eq_ws + draw(nl) + val
        # stray token
        if draw(st.booleans()):
            return key_choice + eq_ws + val + draw(st.sampled_from(["", " ]", " #stray"]))
    return key_choice + eq_ws + val

@st.composite
def table_header(draw):
    # standard table: [key]
    k = draw(st.one_of(simple_key, dotted_key))
    # sometimes produce missing bracket or doubled delimiter errors
    malformed = draw(st.booleans())
    if malformed:
        choice = draw(st.sampled_from(["missing_r", "extra_l", "double_double", "ok"]))
        if choice == "missing_r":
            return "[" + k  # missing closing bracket
        if choice == "extra_l":
            return "[[[" + k + "]]"
        if choice == "double_double":
            # produce an ambiguous double bracket mismatch
            return "[[" + k + "]"
    # valid standard table
    return "[" + k + "]"

@st.composite
def array_table_header(draw):
    k = draw(st.one_of(simple_key, dotted_key))
    malformed = draw(st.booleans())
    if malformed and draw(st.booleans()):
        # produce malformed triple brackets or missing closing
        return "[[[" + k + "]]"
    return "[[" + k + "]]"

@st.composite
def comment_line(draw):
    if draw(st.booleans()):
        return "#" + draw(_comment_text)
    else:
        # blank line
        return ""

# Document generator: sequences of expressions separated by newlines
@st.composite
def document_builder(draw):
    # number of top-level lines
    n = draw(st.integers(min_value=0, max_value=64))
    parts = []
    # To intentionally produce duplicate keys sometimes, decide whether to pick some keys to duplicate
    duplicate_mode = draw(st.booleans())
    dup_key = None
    if duplicate_mode:
        dup_key = draw(st.one_of(simple_key, dotted_key))
    for i in range(n):
        line_type = draw(st.sampled_from(["kv", "table", "array_table", "comment"]))
        if line_type == "kv":
            if duplicate_mode and draw(st.booleans()) and dup_key is not None:
                # produce a duplicate key entry
                val = draw(value)
                parts.append(dup_key + " = " + val)
            else:
                parts.append(draw(key_value_line()))
        elif line_type == "table":
            parts.append(draw(table_header()))
        elif line_type == "array_table":
            parts.append(draw(array_table_header()))
        else:
            parts.append(draw(comment_line()))
    # ensure possibility of documents with no trailing newline
    doc_text = "\n".join(parts)
    if draw(st.booleans()):
        # add a trailing newline or CRLF sometimes
        doc_text = doc_text + draw(st.one_of(st.just("\n"), st.just("\r\n"), st.just("")))
    # Occasionally produce an entirely empty document or comment-only
    if draw(st.booleans()):
        if draw(st.booleans()):
            return ""
        else:
            return "#" + draw(_comment_text)
    return doc_text

# Top-level strategy: produce complete TOML documents as strings
improve_strategy = st.one_of(
    document_builder(),
    # concatenate two documents to create larger and potentially interacting inputs
    st.builds(lambda a, b: a + "\n" + b, document_builder(), document_builder()),
    # interleave a table header in front of a document to test header parsing
    st.builds(lambda h, s: "[" + h + "]\n" + s, simple_key, document_builder()),
    # duplicate a document to test large repeated content and key duplicate handling
    st.builds(lambda s: s + "\n" + s, document_builder()),
    # glue two documents without separator to create malformed concatenations
    st.builds(lambda a, b: a + b, document_builder(), document_builder())
)
strategy = improve_strategy
```