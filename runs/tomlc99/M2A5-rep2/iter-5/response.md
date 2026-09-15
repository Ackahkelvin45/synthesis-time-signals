```python
from hypothesis import strategies as st
import json

# Helper small alphabets
_ASCII_UNQUOTED = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_ASCII_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
# Characters excluding NUL (0) because harness skips NUL-embedded inputs.
# We'll allow other control chars (1..31) in strings as required.
_ALLOWED_CHAR = st.characters(min_codepoint=1, max_codepoint=0xFFFD)

# --- Key generators ---
unquoted_key = st.one_of(
    st.text(alphabet=_ASCII_UNQUOTED, min_size=1, max_size=20),
    # sometimes generate an extremely long key (10k chars) to hit edge cases
    st.text(alphabet=_ASCII_UNQUOTED, min_size=1000, max_size=10000),
)

# Quoted key forms reuse the string generators below (BASIC_STRING or LITERAL_STRING)
# but we need simple quoted key strings (no newlines for BASIC_STRING; literal keys also no newline)
# We'll build quoted keys using the string content strategies to ensure coverage.

# --- String value generators (all 4 forms, with malformed variants included) ---

# Basic string content: cannot contain raw " or backslash or newline when unescaped.
basic_inner = st.text(alphabet=_ALLOWED_CHAR, min_size=0, max_size=40).map(
    lambda s: ''.join(ch for ch in s if ch not in ('"', '\\', '\n', '\x00'))
)

# Escapes allowed sequences
escape_short = st.sampled_from(['\\n', '\\t', '\\r', '\\"', '\\\\', '\\b', '\\f', '\\/'])
escape_unicode4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda i: '\\u%04x' % i)
escape_unicode8 = st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda i: '\\U%08x' % i)

escaped_piece = st.one_of(escape_short, escape_unicode4, escape_unicode8)

basic_with_escapes = st.lists(st.one_of(basic_inner, escaped_piece), min_size=0, max_size=6).map(''.join)

# Raw control bytes (excluding NUL) to include inside basic strings explicitly
control_chars = st.one_of(st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c != '\x00'),
                          st.text(alphabet=_ALLOWED_CHAR, min_size=0, max_size=0))  # allow empty
basic_raw = st.lists(st.one_of(basic_inner, escaped_piece, control_chars), min_size=0, max_size=6).map(''.join)

# Basic string variants, including malformed: missing closing quote, doubled delimiter, stray token inside
basic_string = st.one_of(
    basic_with_escapes.map(lambda s: '"' + s + '"'),
    basic_raw.map(lambda s: '"' + s + '"'),  # raw control chars permitted here
    # multiline-like mistake: triple quote started but not closed (unterminated)
    basic_with_escapes.map(lambda s: '"""' + s),  # unterminated ML (missing closing)
    # malformed: doubled quote in content (near-valid-but-malformed)
    basic_with_escapes.map(lambda s: '"' + s + '""'),
    # unterminated: missing final quote
    basic_with_escapes.map(lambda s: '"' + s),
)

# Multiline basic string (""" ... """) - may include escapes and newlines
ml_basic_inner = st.lists(st.one_of(st.text(alphabet=_ALLOWED_CHAR, min_size=0, max_size=80),
                                    escape_short, escape_unicode4, escape_unicode8,
                                    st.just('\\\n')  # line continuation
                                    ),
                          min_size=0, max_size=6).map(''.join)
ml_basic_string = st.one_of(
    ml_basic_inner.map(lambda s: '"""' + s + '"""'),
    # unterminated variant
    ml_basic_inner.map(lambda s: '"""' + s),
    # doubled delimiter
    ml_basic_inner.map(lambda s: '""""""' + s + '"""'),
)

# Literal string: single quotes (no escapes), and multiline literal ('''...''')
literal_inner = st.text(alphabet=_ALLOWED_CHAR, min_size=0, max_size=40).map(lambda s: s.replace("'", ""))
literal_string = st.one_of(
    literal_inner.map(lambda s: "'" + s + "'"),
    # unterminated literal
    literal_inner.map(lambda s: "'" + s),
    # multiline literal
    st.text(alphabet=_ALLOWED_CHAR, min_size=0, max_size=200).map(lambda s: "'''" + s + "'''"),
    # unterminated multiline literal
    st.text(alphabet=_ALLOWED_CHAR, min_size=0, max_size=200).map(lambda s: "'''" + s),
)

# Combined string value strategy
string_value = st.one_of(basic_string, ml_basic_string, literal_string)

# --- Integer generators (decimal, hex, octal, binary) with underscores and extremes ---
def digits_with_underscores(base_digits, min_len=1, max_len=40):
    # generator returns a string of digits possibly separated by underscores
    return st.integers(min_value=min_len, max_value=max_len).flatmap(
        lambda length: st.lists(st.sampled_from(list(base_digits)), min_size=length, max_size=length).map(''.join)
    ).map(
        lambda s: s if "_" not in s else s  # placeholder; we'll inject underscores differently below
    )

def inject_underscores(s):
    # randomly insert underscores into s (not at ends consecutively)
    if not s:
        return s
    out = []
    for ch in s:
        out.append(ch)
        # 20% chance to append underscore
        # We cannot use random; mimic by simple rule based on ord to keep deterministic per input
        if (ord(ch) % 5) == 0 and len(out) < 1000:
            out.append('_')
    # clean underscores at end
    res = ''.join(out).strip('_')
    if not res:
        return s
    return res

_dec_int = st.one_of(
    # typical decimal, possibly with sign and underscores and leading zeros
    st.integers(min_value=0, max_value=1).flatmap(lambda _: st.text(alphabet="0123456789", min_size=1, max_size=40)).map(inject_underscores).map(
        lambda s: s if s[0] != '+' and s[0] != '-' else s
    ).map(lambda s: s),
    # large extreme
    st.just('1' * 1024),
).map(lambda s: s if s else "0")

dec_int_with_sign = st.one_of(
    st.just("+" ) .map(lambda p: p) ,  # placeholder to allow sign mapping below
    st.just("")
)
# Simpler: produce signed decimal string
decimal_int = st.one_of(
    st.builds(lambda sign, s: sign + s, st.sampled_from(["", "+", "-"]), _dec_int),
    # leading zeros edge
    st.sampled_from(["007", "000123", "0000", "-0005"]),
    # extremely long integer
    st.just("9" * 5000),
)

hex_int = st.builds(lambda body: "0x" + inject_underscores(body),
                    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=40))
oct_int = st.builds(lambda body: "0o" + inject_underscores(body),
                    st.text(alphabet="01234567", min_size=1, max_size=40))
bin_int = st.builds(lambda body: "0b" + inject_underscores(body),
                    st.text(alphabet="01", min_size=1, max_size=40))

integer_value = st.one_of(decimal_int, hex_int, oct_int, bin_int)

# --- Floating point generators including INF/NAN, .5, 1., exponents, extremes ---
float_plain = st.one_of(
    # normal floats, possibly with fractional part or exponent
    st.builds(lambda s: s,
              st.one_of(
                  # forms like 123.456
                  st.builds(lambda a, b: a + "." + b,
                            st.text(alphabet="0123456789", min_size=1, max_size=10),
                            st.text(alphabet="0123456789", min_size=1, max_size=10)),
                  # leading dot .5
                  st.builds(lambda b: "." + b, st.text(alphabet="0123456789", min_size=1, max_size=10)),
                  # trailing dot 1.
                  st.builds(lambda a: a + ".", st.text(alphabet="0123456789", min_size=1, max_size=10)),
                  # exponent only
                  st.builds(lambda a, e: a + "e" + e,
                            st.text(alphabet="0123456789", min_size=1, max_size=10),
                            st.one_of(st.text(alphabet="0123456789", min_size=1, max_size=4),
                                      st.builds(lambda s: ("+" if s else "") + s, st.text(alphabet="0123456789", min_size=1, max_size=4)))
                            )
              )
              )
)
float_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
# extreme exponent like 1e309
float_extreme = st.one_of(
    st.just("1e309"),
    st.builds(lambda n: "1e" + str(n), st.integers(min_value=308, max_value=10000)),
)
float_value = st.one_of(float_plain, float_inf_nan, float_extreme)

# --- Boolean ---
bool_value = st.sampled_from(["true", "false"])

# --- Date/time forms: local date, local time, local date-time, offset date-time (may be calendar-invalid) ---
def digits(n):
    return st.integers(min_value=0, max_value=10 ** (n) - 1).map(lambda x: str(x).zfill(n))

year = st.integers(min_value=0, max_value=9999).map(lambda x: str(x).zfill(4))
month = st.integers(min_value=1, max_value=12).map(lambda x: str(x).zfill(2))
day = st.integers(min_value=1, max_value=31).map(lambda x: str(x).zfill(2))
hour = st.integers(min_value=0, max_value=23).map(lambda x: str(x).zfill(2))
minute = st.integers(min_value=0, max_value=59).map(lambda x: str(x).zfill(2))
second = st.integers(min_value=0, max_value=59).map(lambda x: str(x).zfill(2))
secfrac = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text(alphabet="0123456789", min_size=1, max_size=6)))
offset = st.one_of(st.just("Z"), st.builds(lambda s1, s2, s3: ("+" if (ord(s1[0]) % 2 == 0) else "-") + s1 + ":" + s2,
                                           hour, minute, st.just("")))

local_date = st.builds(lambda y, m, d: y + "-" + m + "-" + d, year, month, day)
local_time = st.builds(lambda h, m, s, sf: h + ":" + m + ":" + s + sf, hour, minute, second, secfrac)
local_date_time = st.builds(lambda d, sep, t: d + sep + t, local_date, st.sampled_from(["T", "t", " "]), local_time)
offset_date_time = st.builds(lambda d, sep, t, off: d + sep + t + off, local_date, st.sampled_from(["T", "t", " "]), local_time, offset)

datetime_value = st.one_of(offset_date_time, local_date_time, local_date, local_time)

# --- Primitive values union ---
primitive_value = st.one_of(string_value, integer_value, float_value, bool_value, datetime_value)

# --- Recursive values: arrays and inline tables ---
# We'll use st.recursive to allow nested arrays/inline tables while also providing a separate
# deep-nesting generator to exercise very deep levels (1500-2048).
def make_array_from(child):
    # child is a strategy that yields value strings
    # Construct arrays with optional comments and whitespace; include trailing comma sometimes
    return st.lists(child, min_size=0, max_size=6).map(
        lambda items: "[" + (", ".join(items) + ("," if (len(items) > 0 and (len(items) % 2 == 0)) else "") if items else "") + "]"
    )

def make_inline_table_from(child):
    # inline tables: { key = value, ... } - allow trailing comma and sometimes newline inside (malformed)
    def build(kvs):
        if not kvs:
            return "{}"
        pairs = []
        for i, (k, v) in enumerate(kvs):
            pairs.append(k + " = " + v)
        s = ", ".join(pairs)
        # sometimes add trailing comma
        if len(kvs) > 0 and (sum(len(k) for k, _ in kvs) % 2 == 0):
            s = s + ","
        return "{" + s + "}"
    # key generators for inline tables: use simple keys (quoted or unquoted)
    inline_key = st.one_of(unquoted_key.map(lambda s: s), string_value.map(lambda s: s))
    return st.lists(st.tuples(inline_key, child), min_size=0, max_size=6).map(build)

# Create recursive value strategy
# Use max_leaves moderate; deep nesting handled separately
value_recursive = st.recursive(
    primitive_value,
    lambda children: st.one_of(
        make_array_from(children),
        make_inline_table_from(children),
    ),
    max_leaves=200,
)

# Deep nesting strategies: arrays and inline tables with very deep nesting (up to 2048)
def deep_array_strategy():
    # choose depth biased towards large (1500-2048) but occasionally small
    depths = st.one_of(
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=50, max_value=300),
        st.integers(min_value=1500, max_value=2048)
    )
    return depths.flatmap(lambda d:
                          primitive_value.map(lambda v: ("[" * d) + v + ("]" * d))
                          )

def deep_inline_table_strategy():
    depths = st.one_of(
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=50, max_value=300),
        st.integers(min_value=1500, max_value=2048)
    )
    # build nested inline tables like {a={b={...}}}
    base_key = unquoted_key
    return depths.flatmap(lambda depth:
                          st.tuples(
                              st.just(depth),
                              primitive_value,
                              st.lists(base_key, min_size=depth, max_size=depth)
                          ).map(lambda t: ("{" * 0) or (
                              # assemble nested inline tables
                              ("".join("{" for _ in range(0)))  # placeholder, we'll build differently
                          ))
                          )

# For deep inline tables we will construct via a simpler deterministic builder to avoid overly complex draws:
def build_deep_inline_table(depth, key, value):
    # build nested inline table: {k1 = {k2 = { ... = value } } }
    if depth <= 0:
        return "{" + key + " = " + value + "}"
    # build chain of keys k0..kN using rotations of the provided key
    keys = [key + ("_" + str(i) if i else "") for i in range(depth)]
    s = value
    for k in reversed(keys):
        s = "{" + k + " = " + s + "}"
    return s

deep_inline_table = st.tuples(st.integers(min_value=0, max_value=2048), unquoted_key, primitive_value).map(
    lambda t: build_deep_inline_table(t[0], t[1], t[2])
)

# Value strategy includes primitives, recursive, and deep nested variants
value_strategy = st.one_of(value_recursive, deep_array_strategy(), deep_inline_table)

# --- Key (simple/dotted/quoted) for key_value and table names ---
simple_key = st.one_of(unquoted_key, string_value)
dotted_key = st.lists(simple_key, min_size=1, max_size=6).map(lambda parts: ".".join(parts))

# --- Comment generator ---
comment_text = st.text(alphabet=_ALLOWED_CHAR, min_size=0, max_size=80)
comment = st.one_of(st.just(""), comment_text.map(lambda s: "# " + s), comment_text.map(lambda s: "#" + s))

# --- Expression generators: key_value, table, array_table, stray tokens, comment-only ---
@st.composite
def key_value_line(draw):
    # sometimes create duplicate keys or malformed equals spacing; allow value to be generated with value_strategy
    k = draw(st.one_of(dotted_key, simple_key))
    v = draw(value_strategy)
    spacer_left = draw(st.one_of(st.just(" "), st.just(""), st.just("\t")))
    spacer_right = draw(st.one_of(st.just(" "), st.just(""), st.just("\t")))
    # sometimes create malformed: missing equals, double equals, stray token
    malformed = draw(st.booleans())
    if malformed:
        kind = draw(st.sampled_from(["missing_eq", "double_eq", "stray_token"]))
        if kind == "missing_eq":
            line = k + spacer_left + spacer_right + v
        elif kind == "double_eq":
            line = k + " " + "==" + " " + v
        else:
            line = k + " = " + v + " ]"
    else:
        line = k + spacer_left + "=" + spacer_right + v
    # append optional comment
    if draw(st.booleans()):
        c = draw(comment_text)
        line = line + " # " + c
    return line

@st.composite
def table_line(draw):
    # standard table [key] or array-of-tables [[key]]
    k = draw(dotted_key)
    kind = draw(st.sampled_from(["standard", "array"]))
    if kind == "standard":
        return "[" + k + "]"
    else:
        return "[[" + k + "]]"

@st.composite
def stray_line(draw):
    # stray tokens like ']' or '=' or an unterminated string line
    choice = draw(st.sampled_from(["]", "=", "[", "]]", "[[", "unterminated"]))
    if choice == "unterminated":
        s = draw(basic_with_escapes)
        return '"' + s  # missing end quote
    return choice

expression_line = st.one_of(
    key_value_line(),
    table_line(),
    comment.map(lambda c: c),
    stray_line()
)

# --- Document generator: sequence of expressions with varied newlines, CRLF, indentation ---
@st.composite
def document(draw):
    # choose number of expressions; allow empty document and comment-only docs
    n = draw(st.one_of(st.integers(min_value=0, max_value=0), st.integers(min_value=0, max_value=12)))
    lines = []
    for i in range(n):
        # optionally add blank lines or CRLF endings interspersed
        if draw(st.booleans()):
            # blank/comment-only line
            if draw(st.booleans()):
                lines.append(draw(comment))
            else:
                lines.append("")
        # add an expression
        lines.append(draw(expression_line))
    # sometimes add trailing table or array-of-tables with no newline after (document end)
    if draw(st.booleans()):
        lines.append(draw(table_line()))
    # occasionally insert a deeply nested table header (super-table after sub-table)
    if draw(st.booleans()):
        lines.append("[super.table.sub]")
    # join lines with either LF or CRLF (cover both)
    sep = "\r\n" if draw(st.booleans()) else "\n"
    doc = sep.join(lines)
    # sometimes ensure there's no trailing newline (document may end without newline)
    if draw(st.booleans()):
        return doc
    else:
        return doc + sep

# Top-level strategy: produce full TOML document strings
strategy = st.one_of(document(), st.just(""), comment.map(lambda c: c))  # include empty and comment-only docs
```