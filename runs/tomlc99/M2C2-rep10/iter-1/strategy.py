from hypothesis import strategies as st
import json

# Helper: avoid emitting raw NUL bytes in generated text
_no_nul = lambda s: '\x00' not in s

# Keys
_unquoted_key = st.from_regex(r"[A-Za-z0-9_-]+", fullmatch=True)
_quoted_basic_key = st.text(min_size=0, max_size=8).filter(_no_nul).map(lambda s: json.dumps(s))
_quoted_literal_key = st.text(min_size=0, max_size=8).filter(_no_nul).map(lambda s: "'" + s.replace("'", "''") + "'")
simple_key = st.one_of(_unquoted_key, _quoted_basic_key, _quoted_literal_key)
dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: ".".join(parts))

# Basic atomic values
_boolean = st.sampled_from(["true", "false"])

# Strings: produce many varieties including escapes, multiline, literal, malformed
_basic_text = st.text(min_size=0, max_size=20).filter(_no_nul)

_basic_string = st.one_of(
    # JSON-style escapes (covers \uXXXX sequences, common escapes)
    _basic_text.map(lambda s: json.dumps(s)),
    # raw-ish basic string (escape " and backslash)
    _basic_text.map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
    # broken escape inside
    _basic_text.map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '\\q' + '"'),
    # unterminated (missing closing quote)
    _basic_text.map(lambda s: '"' + s.replace('"', '\\"')),
    # include explicit control characters (except NUL) via hex escapes
    _basic_text.map(lambda s: '"' + s.replace('"', '\\"') + '\\n' + '"'),
)

_ml_basic_string = st.one_of(
    _basic_text.map(lambda s: '"""' + s + '"""'),
    # unterminated multiline
    _basic_text.map(lambda s: '"""' + s)
)

_literal_text = st.text(min_size=0, max_size=30).filter(_no_nul)
_literal_string = st.one_of(
    _literal_text.map(lambda s: "'" + s + "'"),
    # multiline literal
    _literal_text.map(lambda s: "'''" + s + "'''"),
    # unterminated literal
    _literal_text.map(lambda s: "'" + s)
)

_string_value = st.one_of(_basic_string, _ml_basic_string, _literal_string)

# Integers: decimal (allow leading zeros), hex, octal, bin, underscores, extremes
_dec_int = st.integers(min_value=-10**40, max_value=10**40).map(lambda i: str(i))
# add variants: leading zeros and underscores
_dec_int_var = st.one_of(
    _dec_int,
    st.integers(min_value=0, max_value=10**20).map(lambda n: ("0" + str(n)) if n % 10 == 7 else str(n)),
    st.integers(min_value=0, max_value=10**18).map(lambda n: "_".join(list(str(n)))),
)

_hex_int = st.integers(min_value=0, max_value=2**64).map(lambda n: hex(n).replace('0x', '0x'))
_hex_int_us = _hex_int.map(lambda s: s.replace('0x', '0x' + '_'.join(list(s[2:])) if len(s) > 3 and (len(s) % 2 == 0) else s))
_oct_int = st.integers(min_value=0, max_value=2**60).map(lambda n: oct(n).replace('0o', '0o'))
_bin_int = st.integers(min_value=0, max_value=2**32).map(lambda n: bin(n).replace('0b', '0b'))

_integer = st.one_of(_dec_int_var, _hex_int, _oct_int, _bin_int)

# Floats: include 1., .5, exponent, inf/nan, large exponents
_float_variants = st.one_of(
    # normal float string via formatting (may produce scientific)
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: repr(f)),
    # missing fraction
    st.integers(min_value=-1000, max_value=1000).map(lambda n: str(n) + "."),
    # no leading digit
    st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1.0).map(lambda f: repr(f)[1:] if repr(f).startswith("0") else repr(f)),
    # exponent extremes
    st.integers(min_value=1, max_value=400).map(lambda e: "1e" + str(e)),
    # explicit inf/nan with signs
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
)

# Date/time variants (calendar-invalid allowed)
_year = st.integers(min_value=0, max_value=9999).map(lambda y: str(y).zfill(4))
_month = st.integers(min_value=1, max_value=12).map(lambda m: str(m).zfill(2))
_day = st.integers(min_value=1, max_value=31).map(lambda d: str(d).zfill(2))
_hour = st.integers(min_value=0, max_value=23).map(lambda h: str(h).zfill(2))
_minute = st.integers(min_value=0, max_value=59).map(lambda m: str(m).zfill(2))
_second = st.integers(min_value=0, max_value=59).map(lambda s: str(s).zfill(2))
_frac = st.text(alphabet="0123456789", min_size=1, max_size=6)

_offset = st.one_of(
    st.just("Z"),
    st.tuples(st.sampled_from(["+", "-"]), _hour, st.just(":"), _minute).map(lambda t: t[0] + t[1] + ":" + t[3])
)

_offset_date_time = st.tuples(_year, st.just("-"), _month, st.just("-"), _day, st.sampled_from(["T", "t", " "]), _hour, st.just(":"), _minute, st.just(":"), _second, st.optionals(_frac).map(lambda x: ("." + x) if x else ""), _offset).map(
    lambda parts: parts[0] + "-" + parts[2] + "-" + parts[4] + parts[5] + parts[6] + ":" + parts[8] + ":" + parts[10] + parts[11] + parts[12]
)

_local_date_time = st.tuples(_year, st.just("-"), _month, st.just("-"), _day, st.sampled_from(["T", "t", " "]), _hour, st.just(":"), _minute, st.just(":"), _second, st.optionals(_frac).map(lambda x: ("." + x) if x else "")).map(
    lambda parts: parts[0] + "-" + parts[2] + "-" + parts[4] + parts[5] + parts[6] + ":" + parts[8] + ":" + parts[10] + parts[11]
)

_local_date = st.tuples(_year, st.just("-"), _month, st.just("-"), _day).map(lambda p: p[0] + "-" + p[2] + "-" + p[4])
_local_time = st.tuples(_hour, st.just(":"), _minute, st.just(":"), _second, st.optionals(_frac).map(lambda x: ("." + x) if x else "")).map(lambda p: p[0] + ":" + p[2] + ":" + p[4] + p[5])

_date_time = st.one_of(_offset_date_time, _local_date_time, _local_date, _local_time)

# Comments and whitespace
_comment = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0xFFFF).filter(_no_nul), min_size=0, max_size=30).map(lambda s: (" # " + s) if s else "")
_inline_comment = st.text(min_size=0, max_size=20).filter(_no_nul).map(lambda s: (" # " + s) if s else "")

# Base (non-recursive) values
_base_value = st.one_of(
    _string_value,
    _integer,
    _float_variants,
    _boolean,
    _date_time,
    # explicit empty array representation
    st.just("[]"),
    # explicit empty inline table
    st.just("{ }"),
)

# Recursive construction for arrays and inline tables using st.recursive
def _array_of(children):
    # Build arrays with optional trailing commas, comments, and nested newline forms
    @st.composite
    def _impl(draw):
        elts = draw(st.lists(children, min_size=0, max_size=6))
        # insert some comments or newlines between elements occasionally
        parts = []
        for i, e in enumerate(elts):
            # sometimes insert an inline comment before element
            if draw(st.booleans()) and i == 0:
                parts.append(draw(st.just("\n")) + "# before\n")
            parts.append(e)
            if draw(st.booleans()):
                parts.append(draw(_inline_comment))
            if i != len(elts) - 1:
                parts.append(", ")
        # optional trailing comma
        if draw(st.booleans()) and len(elts) > 0:
            parts.append(",")
        inner = "".join(parts)
        # sometimes produce multiline array with newlines and comments
        if draw(st.booleans()):
            items = draw(st.lists(children, min_size=0, max_size=6))
            inner_lines = []
            for it in items:
                inner_lines.append("  " + it + (draw(st.just(",")) or ","))
            inner = "\n".join(inner_lines)
            return "[\n" + inner + "\n]"
        return "[" + inner + "]"
    return _impl()

def _inline_table_of(children):
    @st.composite
    def _impl(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        kvs = []
        for i in range(n):
            k = draw(simple_key)
            v = draw(children)
            kv = f"{k} = {v}"
            # sometimes include trailing comma, sometimes a trailing newline (malformed)
            if draw(st.booleans()):
                kv += ","
            if draw(st.booleans()):  # inject newline inside inline table occasionally to create malformed input
                kv += "\n"
            kvs.append(kv)
        inner = ", ".join(kvs)
        # allow trailing comma (parser accepts)
        if draw(st.booleans()):
            inner = inner + "," if inner else ""
        return "{" + inner + "}"
    return _impl()

# Use st.recursive to allow nested arrays and inline tables
_value = st.recursive(
    _base_value,
    lambda children: st.one_of(_array_of(children), _inline_table_of(children)),
    max_leaves=2048
)

# Key-value line (may be malformed: missing '=', extra '=', value on next line, etc.)
@st.composite
def key_value_line(draw):
    k = draw(st.one_of(dotted_key, simple_key))
    eq_style = draw(st.sampled_from([" = ", "=", "  =  ", "="]))
    v = draw(_value)
    # optionally break the grammar: place value on next line or duplicate equals, or stray token
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        # value on next line (malformed)
        line = f"{k}{eq_style}\n{v}"
    elif draw(st.integers(min_value=0, max_value=9)) == 1:
        # doubled delimiter
        line = f"{k}{eq_style}=={v}"
    elif draw(st.integers(min_value=0, max_value=9)) == 2:
        # stray token appended
        line = f"{k}{eq_style}{v} STRAY"
    else:
        line = f"{k}{eq_style}{v}"
    # attach inline comment sometimes
    if draw(st.booleans()):
        line += draw(_inline_comment)
    return line

# Table header lines
@st.composite
def table_header(draw):
    # standard or array-table; produce possibility of malformed bracket counts
    is_array = draw(st.booleans())
    k = draw(dotted_key)
    if is_array:
        open_br = "[["
        close_br = "]]"
    else:
        open_br = "["
        close_br = "]"

    # Occasionally produce malformations: missing bracket, doubled bracket, extra spaces
    mal = draw(st.integers(min_value=0, max_value=9))
    if mal == 0:
        # missing closing bracket
        hdr = open_br + k
    elif mal == 1:
        # doubled delimiter
        hdr = open_br + open_br + k + close_br
    else:
        hdr = open_br + k + close_br
    # optional inline comment
    if draw(st.booleans()):
        hdr += draw(_inline_comment)
    return hdr

# Comment-only line
_comment_line = st.one_of(
    st.just(""),
    st.text(min_size=0, max_size=40).filter(_no_nul).map(lambda s: "#" + s),
    st.just("#\n")  # blank comment with newline
)

# An "expression" can be a key_value, table, or comment
_expression = st.one_of(
    key_value_line(),
    table_header(),
    _comment_line
)

# Document: sequence of expressions separated by newlines, including empty documents and comment-only docs
_document = st.lists(_expression, min_size=0, max_size=20).map(lambda parts: "\n".join([p for p in parts if p is not None]))

# Top-level strategy
strategy = _document