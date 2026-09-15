from hypothesis import strategies as st
import json

# --- helpers to avoid emitting raw NUL (\x00) anywhere ---
non_nul_chars = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00")
# for contexts that must exclude newline (e.g. comments, BASIC_STRING content)
non_nul_no_nl = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00\n\r")
# restriction for unquoted keys: ASCII letters, digits, '_' and '-'
unquoted_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

# --- Key strategies ---
unquoted_key = st.text(alphabet=unquoted_key_chars, min_size=1, max_size=20)
# quoted keys: can be basic or literal; allow empty quoted key "" as well
def quoted_key_basic():
    # basic string semantics for keys: no newline inside
    pieces = st.lists(
        st.one_of(
            st.text(alphabet=non_nul_no_nl, min_size=1, max_size=10),
            st.sampled_from(['\\n', '\\t', '\\r', '\\\\', '\\"', '\\u0000', '\\U00000041'])
        ),
        min_size=0, max_size=6
    ).map("".join)
    return pieces.map(lambda s: '"' + s + '"')

def quoted_key_literal():
    # literal single-quoted key; cannot contain newline; no escapes
    body = st.text(alphabet=non_nul_no_nl, min_size=0, max_size=20)
    return body.map(lambda s: "'" + s + "'")

quoted_key = st.one_of(quoted_key_basic(), quoted_key_literal())

# dotted key: simple_key (DOT simple_key)+
simple_key = st.one_of(quoted_key, unquoted_key)
dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: ".".join(parts))

# A key for use in key-value lines (favor unquoted but allow quoted)
key_strategy = st.one_of(unquoted_key, quoted_key, dotted_key)

# --- String value strategies (all four forms) ---
# Avoid raw NUL; allow control characters except NUL.
basic_string_piece = st.one_of(
    st.text(alphabet=non_nul_no_nl, min_size=1, max_size=12),
    st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\\', '\\"', '\\/', '\\u0000', '\\U00000041', '\\q'])
)
basic_string = st.lists(basic_string_piece, min_size=0, max_size=8).map(lambda parts: '"' + "".join(parts) + '"')

# unterminated basic string (near-valid-but-malformed)
unterminated_basic_string = st.lists(basic_string_piece, min_size=1, max_size=8).map(lambda parts: '"' + "".join(parts))

# multiline basic string (""" ... """), allow multiline and ML_ESC sequences
ml_basic_piece = st.one_of(
    st.text(alphabet=non_nul_chars, min_size=0, max_size=30).filter(lambda s: '"""' not in s),
    st.sampled_from(['\\\n', '\\n', '\\t', '\\\\', '\\"', '\\u0000', '\\U00000041'])
)
ml_basic_string = st.lists(ml_basic_piece, min_size=0, max_size=6).map(lambda parts: '"""' + "".join(parts) + '"""')
# unterminated multiline
unterminated_ml_basic = st.lists(ml_basic_piece, min_size=1, max_size=6).map(lambda parts: '"""' + "".join(parts))

# literal string (single-quoted)
literal_string_body = st.text(alphabet=non_nul_no_nl, min_size=0, max_size=30)
literal_string = literal_string_body.map(lambda s: "'" + s + "'")
# multiline literal
ml_literal_piece = st.one_of(
    st.text(alphabet=non_nul_chars, min_size=0, max_size=40).filter(lambda s: "'''" not in s),
)
ml_literal_string = st.lists(ml_literal_piece, min_size=0, max_size=6).map(lambda parts: "'''" + "".join(parts) + "'''")
unterminated_ml_literal = st.lists(ml_literal_piece, min_size=1, max_size=6).map(lambda parts: "'''" + "".join(parts))

string_value = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    # include occasionally near-malformed strings
    unterminated_basic_string,
    unterminated_ml_basic,
    unterminated_ml_literal
)

# --- Integer strategies (decimal, hex, oct, bin), include leading zeros and underscores and extremes ---
@st.composite
def dec_int_strat(draw):
    # create a decimal with optional sign, random underscores and optional leading zeros
    n = draw(st.integers(min_value=0, max_value=10**40))
    s = str(n)
    if len(s) > 1:
        flags = draw(st.lists(st.booleans(), min_size=len(s)-1, max_size=len(s)-1))
        parts = []
        last = 0
        for i, b in enumerate(flags, start=1):
            if b:
                parts.append(s[last:i])
                parts.append("_")
                last = i
        parts.append(s[last:])
        if parts:
            s = "".join(parts)
    # occasionally add leading zeros (like 007)
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        s = "00" + s
    # optionally a minus sign (50/50)
    sign_negative = draw(st.booleans())
    sign = "-" if sign_negative else ""
    # occasional plus sign instead (rare)
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        sign = "+" if sign == "" else sign
    return sign + s

@st.composite
def hex_int_strat(draw):
    n = draw(st.integers(min_value=0, max_value=2**160))
    s = hex(n)[2:]
    # insert an underscore near the end occasionally
    if len(s) > 2 and draw(st.integers(min_value=0, max_value=9)) == 0:
        s = s[:-2] + "_" + s[-2:]
    return "0x" + s

def oct_int_strat():
    def build(n):
        s = oct(n)[2:]
        return "0o" + s
    return st.integers(min_value=0, max_value=2**160).map(build)

def bin_int_strat():
    def build(n):
        s = bin(n)[2:]
        return "0b" + s
    return st.integers(min_value=0, max_value=2**160).map(build)

int_value = st.one_of(dec_int_strat(), hex_int_strat(), oct_int_strat(), bin_int_strat())

# --- Float strategies: normal floats, '1.' and '.5', exponents extremes, inf/nan ---
@st.composite
def float_normal(draw):
    # produce float-like strings: might be '1.', '.5', '1.0', '1e309', '-.5', etc.
    kind = draw(st.integers(min_value=0, max_value=3))
    a = draw(st.integers(min_value=0, max_value=10**6))
    b = draw(st.integers(min_value=0, max_value=10**6))
    if kind == 0:
        # fractional with leading
        return f"{a}.{b}"
    if kind == 1:
        # trailing dot
        return f"{a}."
    if kind == 2:
        # leading dot
        return f".{b}"
    if kind == 3:
        # exponent form
        exp = draw(st.sampled_from(["e", "E"]))
        sign = draw(st.sampled_from(["", "+", "-"]))
        e = draw(st.integers(min_value=0, max_value=400))
        return f"{a}.{b}{exp}{sign}{e}"

float_special = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
float_value = st.one_of(float_normal(), float_special)

# --- Boolean ---
bool_value = st.sampled_from(["true", "false"])

# --- Date/time variants (simple generators) ---
def year():
    return st.integers(min_value=0, max_value=9999).map(lambda x: f"{x:04d}")
def two_digits(minv=0, maxv=99):
    return st.integers(min_value=minv, max_value=maxv).map(lambda x: f"{x:02d}")
date_local = st.tuples(year(), two_digits(1,12), two_digits(1,31)).map(lambda t: f"{t[0]}-{t[1]}-{t[2]}")
time_local = st.tuples(two_digits(0,23), two_digits(0,59), two_digits(0,59), st.one_of(st.none(), st.text(min_size=1, max_size=6, alphabet=st.characters(min_codepoint=48, max_codepoint=57)))).map(
    lambda t: f"{t[0]}:{t[1]}:{t[2]}" + (("."+t[3]) if t[3] else "")
)
offset = st.one_of(st.just("Z"), st.tuples(st.sampled_from(["+","-"]), two_digits(0,23), two_digits(0,59)).map(lambda tt: tt[0] + tt[1] + ":" + tt[2]))
offset_date_time = st.tuples(date_local, st.sampled_from(["T","t"," "]), time_local, offset).map(lambda t: f"{t[0]}{t[1]}{t[2]}{t[3]}")
local_date_time = st.tuples(date_local, st.sampled_from(["T","t"," "]), time_local).map(lambda t: f"{t[0]}{t[1]}{t[2]}")

date_time_value = st.one_of(offset_date_time, local_date_time, date_local, time_local)

# --- Primitive (non-recursive) values ---
primitive_value = st.one_of(string_value, int_value, float_value, bool_value, date_time_value)

# --- Recursive containers: arrays and inline tables ---
# We use st.recursive to allow deep nesting of arrays and inline tables.
def make_array(inner):
    # inner is a strategy producing textual TOML values (strings)
    # array formatting: [ val, val , ] with possible comments and newlines
    # include empty arrays
    commas = st.sampled_from([",", ",", ","])  # bias toward including commas
    def build_list(lst_and_style):
        vals, trailing_comma, multiline = lst_and_style
        if vals == []:
            content = ""
        else:
            sep = ", " if not multiline else ",\n  "
            content = sep.join(vals)
            if trailing_comma:
                content = content + ","
        if multiline:
            return "[\n  " + content.replace("\n", "\n  ") + "\n]"
        else:
            return "[" + content + "]"
    # produce list of values
    vals_strategy = st.lists(inner, min_size=0, max_size=6)
    trailing = st.booleans()
    multiline = st.booleans().filter(lambda b: True)  # allow both
    return st.tuples(vals_strategy, trailing, multiline).map(build_list)

def make_inline_table(inner):
    # inline table: { key = value, ... } allow trailing comma; newline inside sometimes to create invalid cases
    def build(entries_and_invalid):
        entries, trailing_comma, inject_newline = entries_and_invalid
        parts = []
        for (k, v) in entries:
            parts.append(f"{k} = {v}")
        sep = ", "
        if inject_newline:
            # introduce a newline inside inline table (this is grammar-rejected, but we want near-malformed inputs)
            text = (",\n  ").join(parts)
            if trailing_comma:
                if text:
                    text = text + ","
                else:
                    text = ""
            return "{" + ("\n  " + text + "\n" if text else "") + "}"
        else:
            text = sep.join(parts)
            if trailing_comma and text:
                text = text + ","
            return "{" + text + "}"
    entries = st.lists(st.tuples(st.one_of(unquoted_key, quoted_key_basic(), quoted_key_literal()), inner), min_size=0, max_size=6)
    return st.tuples(entries, st.booleans(), st.booleans()).map(build)

# Compose recursive strategy
# inner_strategy is deferred to allow recursion in arrays and inline tables
inner = st.deferred(lambda: value_text)

container_strategy = st.deferred(lambda: st.one_of(make_array(inner), make_inline_table(inner)))

# value_text includes primitives and containers
value_text = st.deferred(lambda: st.one_of(primitive_value, container_strategy))

# --- Expressions: key/value, table headers, array-table headers, comments, stray tokens ---
# key_value: key = value
@st.composite
def key_value_line(draw):
    # include possibilities like missing equals, doubled equals, extra token after value
    k = draw(key_strategy)
    eq_style = draw(st.integers(min_value=0, max_value=2))
    val = draw(value_text)
    stray = draw(st.booleans())
    if eq_style == 0:
        eq = " = "
    elif eq_style == 1:
        eq = " ="  # missing space after
    else:
        eq = " == "  # doubled delimiter (near-malformed)
    s = k + eq + val
    if stray:
        s = s + " " + draw(st.sampled_from(["}", "]", ".", "??"]))
    return s

# standard table [key]
def standard_table():
    return key_strategy.map(lambda k: "[" + k + "]")

# array table [[key]]
def array_table():
    return key_strategy.map(lambda k: "[[" + k + "]]")

# comment-only line
comment_line = st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00\n\r"), min_size=0, max_size=80).map(lambda s: "#" + s)

# stray token line (near malformed)
stray_token = st.sampled_from(["}", "]", "] ]", "==", ".", "???", "<<<"]).map(lambda s: s)

expression = st.one_of(
    key_value_line(),
    standard_table(),
    array_table(),
    comment_line,
    stray_token
)

# --- Document composition ---
# Build a document as a sequence of expressions separated by newlines (allow CRLF occasionally), include empty and comment-only docs.
newline = st.sampled_from(["\n", "\r\n"])
def join_lines(lines_and_end):
    lines, final_nl = lines_and_end
    sep = "\r\n" if lines and (len(lines) % 3 == 0) else "\n"
    doc = sep.join(lines)
    if final_nl:
        doc = doc + sep
    return doc

doc_body = st.lists(expression, min_size=0, max_size=12)
document = st.tuples(doc_body, st.booleans()).map(join_lines)

# Top-level exposed strategy
strategy = document.map(lambda s: s)