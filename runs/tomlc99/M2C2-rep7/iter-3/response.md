```python
from hypothesis import strategies as st
import json

# Top-level strategy name required by the task
# This module produces TOML documents as strings.

# Helper character alphabets (avoid raw NUL 0x00 anywhere in output)
_safe_no_nul = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00")
_safe_no_nul_no_nl = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00\n\r")
_ascii_key_chars = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")

# Unquoted keys: only ASCII as parser rejects non-ASCII bare keys
unquoted_key = st.text(alphabet=_ascii_key_chars, min_size=1, max_size=30)

# Basic (single-line) basic-string content: cannot contain newline characters
_basic_inner = st.text(alphabet=_safe_no_nul_no_nl, min_size=0, max_size=60)

# Multiline content can include newlines (but not raw NUL)
_ml_inner = st.text(alphabet=_safe_no_nul, min_size=0, max_size=300)

# Helper to escape for basic strings
def _escape_basic(s: str) -> str:
    # Escape backslash and double-quote for a well-formed basic string
    return s.replace("\\", "\\\\").replace('"', '\\"')

# Basic string strategy: include valid and near-malformed variants (unterminated, invalid escapes)
basic_string_valid = _basic_inner.map(lambda s: '"' + _escape_basic(s) + '"')
basic_string_unterminated = _basic_inner.map(lambda s: '"' + _escape_basic(s))  # missing closing quote
# deliberately malformed escape sequences included by allowing backslashes in content and not escaping them sometimes
basic_string_malformed = _basic_inner.map(lambda s: '"' + s.replace('"', '\\"') + '"')  # may contain raw backslashes -> invalid escape

basic_string = st.one_of(basic_string_valid, basic_string_unterminated, basic_string_malformed)

# Multiline basic string: triple quotes; can be unterminated sometimes
ml_basic_string_valid = _ml_inner.map(lambda s: '"""' + s + '"""')
ml_basic_string_unterminated = _ml_inner.map(lambda s: '"""' + s)  # missing closing delimiter
ml_basic_string = st.one_of(ml_basic_string_valid, ml_basic_string_unterminated)

# Literal single-quoted string (no escapes) - single-line
literal_inner = _basic_inner  # reuse no-newline
literal_string_valid = literal_inner.map(lambda s: "'" + s.replace("'", "''") + "'")  # simple-safe handling by doubling ' inside literal (not required by TOML but keeps it printable)
literal_string_unterminated = literal_inner.map(lambda s: "'" + s)  # unterminated
literal_string = st.one_of(literal_string_valid, literal_string_unterminated)

# Multiline literal
ml_literal_valid = _ml_inner.map(lambda s: "'''" + s + "'''")
ml_literal_unterminated = _ml_inner.map(lambda s: "'''" + s)
ml_literal_string = st.one_of(ml_literal_valid, ml_literal_unterminated)

# Quoted keys can be any of the quoted string forms above; the empty quoted key "" is allowed
quoted_key = st.one_of(
    basic_string_valid,  # valid quoted key
    literal_string_valid,
    basic_string_unterminated,  # deliberately include unterminated quoted key variants
)

# Simple key (for dotted keys): either unquoted or quoted
simple_key = st.one_of(unquoted_key.map(lambda s: s), quoted_key)

# Dotted key: one or more simple keys separated by dots (include both single and multiple segments)
dotted_key = st.lists(simple_key, min_size=1, max_size=5).map(lambda parts: ".".join(parts))

# Integer strategies
# Decimal with optional sign, underscores allowed, plus leading zeros allowed (parser accepts them)
def _make_dec_int_str(n: int, allow_underscores=True, sign=None):
    s = str(n)
    if allow_underscores and n >= 1000:
        # insert a few underscores
        s = s[:-3] + "_" + s[-3:]
    if sign == "-":
        s = "-" + s
    elif sign == "+":
        s = "+" + s
    return s

dec_small = st.integers(min_value=0, max_value=10**6).flatmap(lambda n: st.sampled_from(
    [_make_dec_int_str(n, allow_underscores=False),
     _make_dec_int_str(n, allow_underscores=True),
     _make_dec_int_str(int(str(n).zfill(3)), allow_underscores=True)]  # leading zeros variant
))

dec_big = st.integers(min_value=10**18, max_value=10**60).map(lambda n: _make_dec_int_str(n, allow_underscores=True, sign=None))
dec_signed = st.one_of(
    dec_small,
    dec_big,
    st.integers(min_value=0, max_value=10**10).map(lambda n: "+" + str(n)),
    st.integers(min_value=0, max_value=10**10).map(lambda n: "-" + str(n)),
)

hex_int = st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x"))
oct_int = st.integers(min_value=0, max_value=2**64).map(lambda n: "0o" + format(n, "o"))
bin_int = st.integers(min_value=0, max_value=2**64).map(lambda n: "0b" + format(n, "b"))

integer = st.one_of(dec_signed, hex_int, oct_int, bin_int)

# Float strategies: include '1.', '.5', exponent forms including huge exponent, inf/nan
float_regular = st.one_of(
    st.floats(allow_infinity=False, allow_nan=False).map(lambda f: repr(f)),
    st.integers(min_value=0, max_value=10**6).map(lambda n: str(n) + "."),
    st.floats(min_value=0.0, max_value=1.0).map(lambda f: "." + str(f).split(".",1)[1])  # crude ".5" style
)
float_exp = st.integers(min_value=-400, max_value=400).flatmap(lambda e: st.sampled_from(["1e" + str(e), "1E" + str(e), "9.99e" + str(e)]))
float_inf_nan = st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"])

floating_point = st.one_of(float_regular, float_exp, float_inf_nan)

# Boolean
bool_ = st.sampled_from(["true", "false"])

# Date/time forms: build strings that match/near-match grammar (including calendar-invalid dates)
def _date_choices():
    choices = []
    # FULL_DATE
    for y in ("1979", "0001", "9999", "2026"):
        for m in ("01", "02", "12"):
            for d in ("01", "30", "31", "00"):
                choices.append(f"{y}-{m}-{d}")
    # FULL_TIME partials
    times = ["07:32:00", "00:00:00", "23:59:59", "07:32:00.123"]
    offsets = ["Z", "+00:00", "-05:00", "+14:00"]
    for date in choices[:6]:
        for t in times:
            for off in offsets:
                choices.append(f"{date}T{t}{off}")
                choices.append(f"{date} {t}{off}")
            # local date-time
            choices.append(f"{date}T{t}")
            choices.append(f"{date} {t}")
    # Local date and local time alone
    choices += ["1979-05-27", "1979-02-30", "0001-01-01", "9999-12-31"]
    choices += ["07:32:00", "00:00:00.123"]
    return choices

date_time = st.sampled_from(_date_choices())

# String value strategy includes all four quoting forms
string_value = st.one_of(basic_string, ml_basic_string, literal_string, ml_literal_string)

# Base (non-container) values
base_value = st.one_of(
    string_value,
    integer,
    floating_point,
    bool_,
    date_time
)

# Recursive container strategies: arrays and inline tables
# Use st.recursive so arrays and inline tables can nest deeply.
def _make_array(elem):
    # elements list (0..6). Include options for comments/newlines between elements and trailing comma.
    elems = st.lists(elem, min_size=0, max_size=6)
    trailing_comma = st.booleans()
    # Insert random whitespace and comments around elements
    comment_piece = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00\r\n"), min_size=0, max_size=30).map(lambda s: (" # " + s) if s else "")
    sep = st.one_of(st.just(", "), st.just(","), st.just(",\n"), st.just(",\r\n"))
    return st.tuples(elems, trailing_comma, comment_piece).map(
        lambda tup: (
            "[" +
            ("" if not tup[0] else ",".join(v for v in tup[0])) +
            ("," if tup[1] and (tup[0] or True) else "") +
            "]"
        )
    )

def _make_inline_table(elem):
    # Inline table keyvals (no newlines normally, but sometimes introduce them to produce rejected inputs)
    # Keys inside inline table must be simple keys (unquoted or quoted)
    kv = st.lists(st.tuples(simple_key, elem), min_size=0, max_size=6)
    trailing_comma = st.booleans()
    allow_newline = st.booleans()
    def build(t):
        pairs, tc, allow_nl = t
        if not pairs:
            inner = ""
        else:
            pieces = []
            for k, v in pairs:
                pieces.append(f"{k} = {v}")
            sep = ", "
            inner = sep.join(pieces)
            if tc:
                inner = inner + ","
            if allow_nl:
                # insert a newline inside inline table (this is invalid per parser grammar; useful to fuzz)
                inner = inner.replace(", ", ",\n", 1)
        return "{" + inner + "}"
    return st.tuples(kv, trailing_comma, allow_newline).map(build)

# Use st.recursive to create a value strategy that can contain nested arrays and inline tables.
# Set max_leaves large so the recursive form *permits* deep nesting (the engine may not always draw extreme depth).
value_recursive = st.recursive(
    base_value,
    lambda children: st.one_of(
        st.deferred(lambda: st.tuples(st.lists(children, min_size=0, max_size=4), st.booleans()).map(
            lambda t: "[" + ("" if not t[0] else ", ".join(t[0])) + ("," if t[1] else "") + "]"
        )),
        st.deferred(lambda: st.tuples(st.lists(st.tuples(simple_key, children), min_size=0, max_size=4), st.booleans()).map(
            lambda t: "{" + ("" if not t[0] else ", ".join(f"{k} = {v}" for k, v in t[0])) + ("," if t[1] else "") + "}"
        ))
    ),
    max_leaves=1500
)

# Key/value line: key EQUALS value
key_value = st.tuples(
    st.one_of(dotted_key, simple_key),
    value_recursive
).map(lambda kv: f"{kv[0]} = {kv[1]}")

# Table header lines: [key] or [[key]]
standard_table_line = dotted_key.map(lambda k: f"[{k}]")
array_table_line = dotted_key.map(lambda k: f"[[{k}]]")
table_line = st.one_of(standard_table_line, array_table_line)

# Comments
comment_line = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00\r\n"), min_size=0, max_size=80).map(lambda s: ("# " + s) if s else "#")

# Blank line (possibly with CRLF)
blank_line = st.sampled_from(["", " ", "\r\n", "\n", "\r"])

# Expression: choose among key_value, table, comment-only
expression = st.one_of(key_value, table_line, comment_line, blank_line)

# Document: sequence of expressions separated by newlines; include possibility of no trailing newline
def _build_document(lines):
    # lines is a list of expression strings; join with newlines, randomizing CRLF occasionally
    if not lines:
        # empty document or just a comment-only
        if st.booleans().example():
            return ""
        return "\n"
    # join with random choice of newline characters to include CRLF cases
    nl_choices = ["\n", "\r\n"]
    # Create a joiner that may vary between joins - choose one newline for the document
    nl = st.sampled_from(nl_choices).example()
    doc = nl.join(lines)
    # Optionally omit trailing newline (documents without trailing newline should be produced)
    if st.booleans().example():
        return doc
    else:
        return doc + nl

# Because using .example() inside strategies is not allowed, implement document builder purely with strategies:
document_lines = st.lists(expression, min_size=0, max_size=40)

def _doc_builder(tup):
    lines, nl = tup
    doc = nl.join(lines)
    # Optionally include or omit trailing newline
    if st.booleans().example():
        return doc
    return doc + nl

# Avoid using .example() within map: instead, construct deterministically using nested strategies
newline_choice = st.sampled_from(["\n", "\r\n"])

# Build final document strategy without calling .example()
document = st.tuples(document_lines, newline_choice, st.booleans()).map(
    lambda tpl: tpl[1].join(tpl[0]) + (tpl[1] if not tpl[2] else "")
)

# Final exported strategy
strategy = document
```