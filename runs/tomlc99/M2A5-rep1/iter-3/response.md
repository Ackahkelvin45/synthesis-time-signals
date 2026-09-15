```python
from hypothesis import strategies as st
import json

# Helper alphabets avoiding raw NUL (\x00)
_ascii_printable = [chr(i) for i in range(32, 127) if i not in (34, 92)]  # exclude " and \
_control_chars = [chr(i) for i in range(1, 32) if i not in (10, 13, 0)]  # exclude newline, CR, NUL
_utf_nonascii = [chr(i) for i in range(0x80, 0x100)]  # some non-ascii bytes (will appear as unicode chars)
_hex_digits = "0123456789abcdefABCDEF"

# Basic pieces
_unquoted_key_char = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
_unquoted_key = st.text(alphabet=_unquoted_key_char, min_size=1, max_size=30)

# Allow very long keys rarely
_long_key = st.integers(min_value=0, max_value=1).flatmap(
    lambda _: st.text(alphabet=_unquoted_key_char, min_size=0, max_size=10000)
)

# Quoted keys: basic or literal quoted strings (reuse value string generators)
# Escape sequences for insertion into basic strings (literal backslash escapes)
_escape_seqs = [
    "\\n", "\\r", "\\t", "\\b", "\\f", "\\\\", "\\\"", "\\/",
] + ["\\u%04x" % i for i in (0, 0x20, 0x7f, 0x2603, 0x20AC)]

# Construct small segments for basic-string content: safe chars, control chars, escape sequences, and occasional unicode
_basic_content_piece = st.one_of(
    st.sampled_from(_ascii_printable),
    st.sampled_from(_control_chars),
    st.sampled_from(_escape_seqs),
    st.sampled_from(_utf_nonascii),
)

# For multiline basic strings we can include newlines
_ml_content_piece = st.one_of(
    st.sampled_from(_ascii_printable + ["\n"]),
    st.sampled_from(_control_chars + ["\n"]),
    st.sampled_from(_escape_seqs),
    st.sampled_from(_utf_nonascii),
)

# Literal string pieces (no escaping), single-line cannot contain newline
_literal_piece = st.one_of(
    st.sampled_from([c for c in _ascii_printable if c != "'"]),
    st.sampled_from(_control_chars),
    st.sampled_from(_utf_nonascii),
)

# Build string variants, sometimes intentionally malformed
def basic_string_strategy():
    valid = st.lists(_basic_content_piece, min_size=0, max_size=20).map("".join).map(lambda s: '"' + s + '"')
    # malformed forms:
    missing_close = st.lists(_basic_content_piece, min_size=0, max_size=20).map("".join).map(lambda s: '"' + s)  # unterminated
    doubled_delim = st.lists(_basic_content_piece, min_size=0, max_size=15).map("".join).map(lambda s: '""' + '"' + s + '"')
    stray_quote = st.just('"')  # a stray quote alone
    return st.one_of(valid, missing_close, doubled_delim, stray_quote)

def ml_basic_string_strategy():
    valid = st.lists(_ml_content_piece, min_size=0, max_size=40).map("".join).map(lambda s: '"""' + s + '"""')
    # unterminated
    unterminated = st.lists(_ml_content_piece, min_size=0, max_size=40).map("".join).map(lambda s: '"""' + s)
    # doubled triple delimiter sometimes inserted mid content
    doubled = st.lists(_ml_content_piece, min_size=0, max_size=30).map("".join).map(lambda s: '""""""' + s + '"""')
    return st.one_of(valid, unterminated, doubled)

def literal_string_strategy():
    valid = st.lists(_literal_piece, min_size=0, max_size=20).map("".join).map(lambda s: "'" + s + "'")
    # malformed: unterminated
    unterminated = st.lists(_literal_piece, min_size=0, max_size=20).map("".join).map(lambda s: "'" + s)
    # include single quote inside -> causes early termination (near-valid-but-malformed)
    internal_quote = st.lists(st.one_of(st.sampled_from([c for c in _ascii_printable if c != "'"]), st.sampled_from(_utf_nonascii), st.sampled_from(_control_chars), st.just("'")), min_size=1, max_size=10).map("".join).map(lambda s: "'" + s + "'")
    return st.one_of(valid, unterminated, internal_quote)

def ml_literal_string_strategy():
    valid = st.lists(st.one_of(st.sampled_from(_ascii_printable + ["\n"]), st.sampled_from(_utf_nonascii), st.sampled_from(_control_chars)), min_size=0, max_size=60).map("".join).map(lambda s: "'''" + s + "'''")
    unterminated = st.lists(st.one_of(st.sampled_from(_ascii_printable + ["\n"]), st.sampled_from(_utf_nonascii), st.sampled_from(_control_chars)), min_size=0, max_size=60).map("".join).map(lambda s: "'''" + s)
    return st.one_of(valid, unterminated)

# Integer strategies: decimal (with leading zeros sometimes), hex/oct/bin, extremes
def decimal_int_strategy():
    # allow leading zeros, underscores, sign; extreme magnitudes possible
    def make_decimal(n):
        # produce digits with optional underscores
        s = "".join(n)
        return st.just(s)
    digits = st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=30).map("".join)
    # Fixed: build a proper tuple of (digits_text, boolean) then map to insert underscores if requested.
    with_unders = st.tuples(st.text(alphabet=list("0123456789"), min_size=1, max_size=10), st.booleans()).map(
        lambda t: t[0] if not t[1] else (t[0][0] + "".join("_" + c for c in t[0][1:]) if len(t[0]) > 1 else t[0])
    )
    sign = st.sampled_from(["", "+", "-"])
    # sometimes produce weird leading zeros like 007
    return st.one_of(
        st.tuples(sign, digits).map(lambda t: t[0] + t[1]),
        st.tuples(sign, with_unders).map(lambda t: t[0] + t[1]),
        # extremes: a number with hundreds of digits
        st.tuples(sign, st.text(alphabet=list("0123456789"), min_size=50, max_size=200)).map(lambda t: t[0] + t[1]),
    )

def hex_int_strategy():
    body = st.text(alphabet=list(_hex_digits), min_size=1, max_size=20)
    with_unders = st.builds(lambda b: "0x" + b, body)
    return st.one_of(with_unders, st.builds(lambda b: "0x" + b, st.text(alphabet=list(_hex_digits), min_size=50, max_size=200)))

def oct_int_strategy():
    body = st.text(alphabet=list("01234567"), min_size=1, max_size=20)
    return st.builds(lambda b: "0o" + b, body)

def bin_int_strategy():
    body = st.text(alphabet=list("01"), min_size=1, max_size=40)
    return st.builds(lambda b: "0b" + b, body)

def integer_strategy():
    return st.one_of(decimal_int_strategy(), hex_int_strategy(), oct_int_strategy(), bin_int_strategy())

# Floats including forms like 1., .5, large exponents, inf/nan
def float_strategy():
    frac = st.tuples(st.text(alphabet=list("0123456789"), min_size=1, max_size=10)).map(lambda t: "." + t[0])
    pref = st.text(alphabet=list("0123456789"), min_size=1, max_size=10)
    exp = st.builds(lambda m, e: m + "e" + e, pref, st.text(alphabet=list("+-0123456789"), min_size=1, max_size=6))
    simple = st.one_of(
        st.builds(lambda a, b: a + b, pref, frac),  # 123.456
        st.builds(lambda a: a + ".", pref),  # 1.
        st.builds(lambda a: "." + a, st.text(alphabet=list("0123456789"), min_size=1, max_size=10)),  # .5
        exp,  # 1e10 etc
        st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"]),
    )
    return st.one_of(simple)

# Booleans
bool_strategy = st.sampled_from(["true", "false"])

# Date/time forms (may be calendar-invalid)
def date_time_strategy():
    # YEAR-MONTH-DAY [T| ] HH:MM:SS[.frac][Z|+/-HH:MM]
    year = st.integers(min_value=0, max_value=9999).map(lambda x: "%04d" % x)
    month = st.integers(min_value=1, max_value=12).map(lambda x: "%02d" % x)
    day = st.integers(min_value=1, max_value=31).map(lambda x: "%02d" % x)
    hour = st.integers(min_value=0, max_value=23).map(lambda x: "%02d" % x)
    minute = st.integers(min_value=0, max_value=59).map(lambda x: "%02d" % x)
    second = st.integers(min_value=0, max_value=59).map(lambda x: "%02d" % x)
    frac = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text(alphabet=list("0123456789"), min_size=1, max_size=9)))
    offset = st.one_of(st.just("Z"), st.builds(lambda h, m, sgn: ("%s%02d:%02d" % (sgn, h, m)), st.integers(0,23), st.integers(0,59), st.sampled_from(["+", "-"])))
    delim = st.sampled_from(["T", "t", " "])
    local_date = st.tuples(year, month, day).map(lambda t: "-".join(t))
    partial_time = st.tuples(hour, minute, second, frac).map(lambda t: "%s:%s:%s%s" % (t[0], t[1], t[2], t[3]))
    # combine into several variants
    offset_dt = st.tuples(local_date, delim, partial_time, offset).map(lambda t: t[0] + t[1] + t[2] + t[3])
    local_dt = st.tuples(local_date, delim, partial_time).map(lambda t: t[0] + t[1] + t[2])
    local_d = local_date
    local_t = partial_time
    return st.one_of(offset_dt, local_dt, local_d, local_t)

# Value recursion: base values then arrays/inline tables via st.recursive
basic_str = basic_string_strategy()
ml_basic_str = ml_basic_string_strategy()
literal_str = literal_string_strategy()
ml_literal_str = ml_literal_string_strategy()

base_value = st.one_of(
    basic_str,
    ml_basic_str,
    literal_str,
    ml_literal_str,
    integer_strategy(),
    float_strategy(),
    bool_strategy,
    date_time_strategy(),
)

# Key strategies: unquoted, quoted basic, quoted literal, empty quoted key
quoted_key_basic = basic_str
quoted_key_literal = literal_str
empty_quoted_key = st.just('""')

unquoted_key = _unquoted_key
key_strategy = st.one_of(empty_quoted_key, quoted_key_basic, quoted_key_literal, unquoted_key, _long_key)

# Inline table generator helper
def inline_table_from_pairs(pairs):
    # pairs is list of (k_str, v_str) where k_str is key token and v_str is value token
    if not pairs:
        return "{}"
    # occasionally put a stray newline inside (malformed by grammar)
    pieces = []
    for k, v in pairs:
        pieces.append(k + " = " + v)
    # maybe trailing comma
    trailing_comma = False  # small nondeterminism; we'll just use no trailing comma here
    inner = ", ".join(pieces)
    if trailing_comma:
        inner = inner + ","
    return "{" + inner + "}"

# Extend function used by st.recursive to create arrays and inline tables
def extend_values(elem):
    # elem is a strategy producing value text strings
    # arrays: produce lists of values, including comments/newlines/trailing comma variants and nested arrays
    def array_builder(vs, trailing):
        # vs is list of element strings
        parts = [val for val in vs]
        if trailing and len(parts) > 0:
            return "[" + ", ".join(parts) + ",]"
        return "[" + ", ".join(parts) + "]"

    arrays = st.builds(array_builder, st.lists(elem, min_size=0, max_size=6), st.booleans())

    # inline table: (possibly empty), but ensure keys possibly duplicate and newline inside occasionally
    def inline_table_builder(pairs, newline_flag, trailing_flag):
        # pairs: list of (key_str, value_str)
        if not pairs:
            return "{}"
        items = []
        for k, v in pairs:
            items.append(k + " = " + v)
        # sometimes include newline inside inline table (grammar rejects but we want to fuzz)
        if newline_flag:
            inner = ",\n".join(items)
        else:
            inner = ", ".join(items)
        # allow trailing comma (accepted by parser)
        if trailing_flag and len(items) > 0:
            inner = inner + ","
        return "{" + inner + "}"

    inline_tables = st.builds(inline_table_builder, st.lists(st.tuples(key_strategy, elem), min_size=0, max_size=6), st.booleans(), st.booleans())

    # nested arrays start with bracket and push mode - generate nested arrays by wrapping lists
    nested_arrays = st.lists(elem, min_size=1, max_size=6).map(lambda lst: "[" + ", ".join(lst) + "]")
    return st.one_of(arrays, inline_tables, nested_arrays)

# Build recursive value strategy allowing arrays and inline tables nested to moderate depth
value_strategy = st.recursive(base_value, extend_values, max_leaves=200)

# Expressions: key_value, table, array_table, comment-only, blank
def key_value_builder(k, eq_variation, v):
    # eq_variation sometimes missing '=' or duplicated '=='
    if eq_variation == "missing":
        return k + " " + v  # missing equals
    if eq_variation == "double":
        return k + " ==" + " " + v
    return k + " = " + v

key_value_expr = st.tuples(
    key_strategy,
    st.sampled_from(["normal", "missing", "double"]),
    value_strategy
).map(lambda t: key_value_builder(t[0], t[1], t[2]))

# Table header [key] and array of tables [[key]]
def table_header_builder(kind, k):
    if kind == "standard":
        return "[" + k + "]"
    else:
        return "[[" + k + "]]"

table_expr = st.tuples(st.sampled_from(["standard", "array"]), key_strategy).map(lambda t: table_header_builder(t[0], t[1]))

# Comment only or blank line
comment_piece = st.one_of(
    st.just(""),  # blank line
    st.builds(lambda s: "#" + s, st.text(alphabet=[chr(i) for i in range(32, 127)] , min_size=0, max_size=60)),
    # comment with control characters
    st.builds(lambda s: "#" + s, st.text(alphabet=_control_chars + _utf_nonascii, min_size=0, max_size=40))
)

# stray tokens: unmatched brace/bracket or isolated tokens
stray_tokens = st.sampled_from(["}", "]", "}", "] ]", "=", "==", "] }", "{", "[", "]]", "[["])

expression = st.one_of(
    key_value_expr,
    table_expr,
    comment_piece,
    stray_tokens
)

# Build top-level document: sequence of expressions separated by newline(s)
def join_lines(lines):
    # join using either \n or \r\n occasionally
    seps = ["\n", "\r\n"]
    sep = "\n"
    return sep.join(lines)

# To include duplicate keys/tables we allow repetition in generated lines
document_strategy = st.lists(expression, min_size=0, max_size=30).map(lambda lines: join_lines(lines))

# Add rare deep-nesting generator (explicit bracket nesting up to ~2048)
def deep_nested_array(n):
    # create a deeply nested array like [[[[...]]]] with empty arrays inside
    return "[" * n + "]" * n

deep_nest_choice = st.one_of(
    st.integers(min_value=1500, max_value=2048).map(lambda n: deep_nested_array(n)),
    st.integers(min_value=1500, max_value=2048).map(lambda n: "[" + ("[]" * (n // 2)) + "]"),
)

# Compose final strategy: mostly normal documents, occasionally inject a deep nesting or a giant key-only document
strategy = st.one_of(
    document_strategy,
    # inject single very deep line
    deep_nest_choice,
    # a document that is a single key-value with extreme integer/float/string values
    st.tuples(key_strategy, st.sampled_from([" = " ," = "]), st.one_of(
        integer_strategy(), float_strategy(), value_strategy, basic_str, literal_str
    )).map(lambda t: t[0] + t[1] + t[2]),
    # an inline table heavy document
    st.builds(lambda s: s, st.lists(st.one_of(
        st.tuples(key_strategy, st.just(" = "), value_strategy).map(lambda t: t[0] + t[1] + t[2]),
        table_expr,
        comment_piece
    ), min_size=1, max_size=80).map(lambda parts: ("\n".join(parts)))),
)
```