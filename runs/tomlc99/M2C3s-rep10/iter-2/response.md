```python
from hypothesis import strategies as st
import json

# --- helper alphabets (avoid raw NUL char 0) ---
_ascii_letters_digits = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_unquoted_extra = ["-", "_"]
_punct = list("!@#$%^&*()[]{}:;<>?/|\\.,~`+= ")
_non_ascii_samples = ["é", "å", "漢", "λ", "🙂", "€"]
_control_chars = [chr(i) for i in range(1, 32) if i != 0]  # include control chars but not NUL

_sample_chars = _ascii_letters_digits + _punct + _non_ascii_samples + _control_chars

# Escape sequences used inside basic strings (include some invalid escapes for near-malformed)
_escape_seqs = ['\\n', '\\r', '\\t', '\\b', '\\f', '\\\\', '\\"', '\\/', '\\u0000', '\\u00E9', '\\U0001F600', '\\q']

# --- key strategies ---
_unquoted_key = st.lists(st.sampled_from(_ascii_letters_digits + _unquoted_extra), min_size=1, max_size=12).map("".join)
_quoted_key_basic = st.just('""').filter(lambda _: True)  # placeholder; real quoted keys created below

@st.composite
def _basic_string_key(draw):
    # empty quoted key allowed and common; also non-empty quoted key
    choose_empty = draw(st.booleans())
    if choose_empty:
        return '""'
    # build content without raw NUL
    pieces = draw(st.lists(st.one_of(st.sampled_from(_sample_chars), st.sampled_from(_escape_seqs)), min_size=0, max_size=8))
    content = "".join(pieces)
    # ensure any internal double-quote is escaped
    content = content.replace('"', '\\"')
    return '"' + content + '"'

@st.composite
def _literal_string_key(draw):
    # single quoted key, can be empty too (''), but empty single-quoted key less common
    pieces = draw(st.lists(st.one_of(st.sampled_from(_sample_chars), st.sampled_from(['\''])), min_size=0, max_size=8))
    content = "".join(pieces)
    # single quotes inside literal must be represented by closing/opening; allow them raw to create edge cases
    return "'" + content + "'"

_key_simple = st.one_of(_unquoted_key, _basic_string_key(), _literal_string_key())

@st.composite
def key_strategy(draw):
    # build simple or dotted keys; sometimes produce many segments to test dotted keys and depth
    kind = draw(st.sampled_from(['simple', 'dotted', 'quoted_dotted']))
    if kind == 'simple':
        return draw(_key_simple)
    # dotted: join simple segments with dots
    parts = draw(st.lists(_key_simple, min_size=2, max_size=6))
    # occasionally produce doubled dot or missing dot to create near-malformed tokens
    if draw(st.booleans()):
        # well-formed dotted key
        return ".".join(parts)
    else:
        # malformed dotted (double dot or missing delimiter)
        if draw(st.booleans()):
            return "..".join(parts)  # double delimiter
        else:
            return "".join(parts)  # missing delimiter

# --- basic value constructors ---
@st.composite
def basic_string(draw):
    # forms: well-formed, unterminated, malformed escapes, extra quote misbalance
    form = draw(st.sampled_from(["good", "unterminated", "bad_escape", "misbalanced_triple"]))
    pieces = draw(st.lists(st.one_of(st.sampled_from(_sample_chars), st.sampled_from(_escape_seqs)), min_size=0, max_size=10))
    content = "".join(pieces)
    # escape internal double quotes where appropriate for well-formed
    if form == "good":
        safe = content.replace('"', '\\"')
        return '"' + safe + '"'
    elif form == "unterminated":
        # start quote but no end
        safe = content.replace('"', '\\"')
        return '"' + safe
    elif form == "bad_escape":
        # include an invalid escape explicitly (e.g., \q)
        return '"' + content + '\\q"'
    else:
        # misbalanced triple: open triple, close single -> near-malformed
        return '"""' + content + '"'

@st.composite
def literal_string(draw):
    # literal single-quoted string; include raw control chars; optionally unterminated
    pieces = draw(st.lists(st.sampled_from(_sample_chars + ["'"]), min_size=0, max_size=10))
    content = "".join(pieces)
    if draw(st.booleans()):
        return "'" + content + "'"
    else:
        # unterminated literal
        return "'" + content

@st.composite
def ml_basic_string(draw):
    # multiline basic string with triple quotes; include CRLF or LF line breaks and various escapes
    lines = draw(st.lists(st.one_of(st.just("\n"), st.just("\r\n"), st.sampled_from(_escape_seqs), st.sampled_from(_sample_chars)), min_size=0, max_size=6))
    content = "".join(lines)
    # sometimes produce unterminated
    if draw(st.booleans()):
        return '"""' + content + '"""'
    else:
        return '"""' + content  # unterminated

@st.composite
def ml_literal_string(draw):
    # multiline literal string with triple single quotes; can contain anything except NUL
    lines = draw(st.lists(st.one_of(st.just("\n"), st.just("\r\n"), st.sampled_from(_sample_chars)), min_size=0, max_size=6))
    content = "".join(lines)
    if draw(st.booleans()):
        return "'''" + content + "'''"
    else:
        return "'''" + content  # unterminated

# --- numeric strategies ---
_digits = st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=40).map("".join)

@st.composite
def decimal_int(draw):
    # include optional sign, underscores, leading zeros sometimes
    sign = draw(st.sampled_from(["", "+", "-"]))
    digits = draw(_digits)
    # randomly insert underscores
    if draw(st.booleans()):
        # insert underscores between digits at random positions
        pos = draw(st.lists(st.integers(min_value=1, max_value=max(1, len(digits)-1)), min_size=0, max_size=5))
        pos = sorted(set(pos))
        parts = []
        last = 0
        for p in pos:
            parts.append(digits[last:p])
            last = p
        parts.append(digits[last:])
        digits = "_".join([p for p in parts if p != ""])
    # occasionally produce leading zeros like 007
    if draw(st.booleans()):
        if not digits.startswith("0"):
            digits = "0" + digits
    return sign + digits

@st.composite
def hex_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    # hex digits with underscores
    hex_digits = draw(st.lists(st.sampled_from(list("0123456789abcdefABCDEF")), min_size=1, max_size=20).map("".join))
    if draw(st.booleans()):
        # insert underscores
        parts = draw(st.lists(st.just(1), min_size=0, max_size=4))
        # naive underscore insertion
        hex_digits = hex_digits[:1] + "_" + hex_digits[1:] if len(hex_digits) > 1 else hex_digits
    return sign + "0x" + hex_digits

@st.composite
def oct_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    oct_digits = draw(st.lists(st.sampled_from(list("01234567")), min_size=1, max_size=20).map("".join))
    return sign + "0o" + oct_digits

@st.composite
def bin_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    bin_digits = draw(st.lists(st.sampled_from(list("01")), min_size=1, max_size=50).map("".join))
    return sign + "0b" + bin_digits

@st.composite
def float_number(draw):
    kind = draw(st.sampled_from(["normal", "no_leading", "no_trailing", "exp_only", "infnan"]))
    sign = draw(st.sampled_from(["", "+", "-"]))
    if kind == "infnan":
        return sign + draw(st.sampled_from(["inf", "nan"]))
    if kind == "normal":
        int_part = draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=10).map("".join))
        frac = "." + draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=10).map("".join))
        if draw(st.booleans()):
            # optional exponent
            exp = draw(st.sampled_from(["e", "E"])) + draw(st.sampled_from(["", "+", "-"])) + draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=4).map("".join))
            return sign + int_part + frac + exp
        return sign + int_part + frac
    if kind == "no_leading":
        # .5 style
        frac = "." + draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=10).map("".join))
        if draw(st.booleans()):
            exp = draw(st.sampled_from(["e", "E"])) + draw(st.sampled_from(["", "+", "-"])) + draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=4).map("".join))
            return sign + frac + exp
        return sign + frac
    if kind == "no_trailing":
        # 1. style
        int_part = draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=10).map("".join))
        if draw(st.booleans()):
            exp = draw(st.sampled_from(["e", "E"])) + draw(st.sampled_from(["", "+", "-"])) + draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=4).map("".join))
            return sign + int_part + "." + exp
        return sign + int_part + "."
    if kind == "exp_only":
        # integer with exponent
        int_part = draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=10).map("".join))
        exp = draw(st.sampled_from(["e", "E"])) + draw(st.sampled_from(["", "+", "-"])) + draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=6).map("".join))
        return sign + int_part + exp

# --- booleans ---
_bool = st.sampled_from(["true", "false"])

# --- date/time forms (may include calendar-invalid dates) ---
@st.composite
def date_time(draw):
    # choose one of the four date/time forms, possibly invalid dates
    kind = draw(st.sampled_from(["offset", "local_dt", "local_date", "local_time"]))
    year = draw(st.integers(min_value=0, max_value=9999)).__str__().zfill(4)
    month = str(draw(st.integers(min_value=1, max_value=12))).zfill(2)
    day = str(draw(st.integers(min_value=1, max_value=31))).zfill(2)  # allow invalid like Feb 30
    hour = str(draw(st.integers(min_value=0, max_value=23))).zfill(2)
    minute = str(draw(st.integers(min_value=0, max_value=59))).zfill(2)
    second = str(draw(st.integers(min_value=0, max_value=59))).zfill(2)
    secfrac = ""
    if draw(st.booleans()):
        secfrac = "." + draw(st.lists(st.sampled_from(list("0123456789")), min_size=1, max_size=6).map("".join))
    delim = draw(st.sampled_from(["T", "t", " "]))
    if kind == "offset":
        offset = draw(st.sampled_from(["Z", "+" + str(draw(st.integers(min_value=0, max_value=23))).zfill(2) + ":" + str(draw(st.integers(min_value=0, max_value=59))).zfill(2),
                                      "-" + str(draw(st.integers(min_value=0, max_value=23))).zfill(2) + ":" + str(draw(st.integers(min_value=0, max_value=59))).zfill(2)]))
        return year + "-" + month + "-" + day + delim + hour + ":" + minute + ":" + second + secfrac + offset
    if kind == "local_dt":
        return year + "-" + month + "-" + day + delim + hour + ":" + minute + ":" + second + secfrac
    if kind == "local_date":
        return year + "-" + month + "-" + day
    return hour + ":" + minute + ":" + second + secfrac

# --- base (non-recursive) value strategy ---
base_value = st.one_of(
    basic_string(),
    literal_string(),
    ml_basic_string(),
    ml_literal_string(),
    decimal_int(),
    hex_int(),
    oct_int(),
    bin_int(),
    float_number(),
    _bool,
    date_time()
)

# --- recursive construction for arrays and inline tables ---
def _extend_array_and_inline(inner):
    # inner is a strategy producing a textual value representation (string)
    # array generator: allow empty arrays, trailing commas, mixed types, nested arrays
    array_elems = st.lists(inner, min_size=0, max_size=6)
    @st.composite
    def array_draw(draw):
        vals = draw(array_elems)
        # insert comments/newlines optionally to exercise comment_or_nl grammar
        pieces = []
        for v in vals:
            # occasionally insert comments inline
            if draw(st.booleans()):
                c = draw(st.one_of(st.just(" # inline comment"), st.just("")))
                pieces.append(v + c)
            else:
                pieces.append(v)
        # allow trailing comma
        trailing = draw(st.booleans())
        inner_text = ", ".join(pieces)
        if trailing and (pieces or draw(st.booleans())):
            if inner_text == "":
                # empty array with trailing comma (we'll just keep empty)
                return "[]"
            else:
                return "[" + inner_text + ",]"
        return "[" + inner_text + "]"
    # inline table generator: no newlines normally, allow trailing comma; keys and values
    @st.composite
    def inline_draw(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        items = []
        for _ in range(n):
            k = draw(_key_simple)
            v = draw(inner)
            items.append(k + " = " + v)
        trailing = draw(st.booleans())
        # occasionally introduce a newline inside inline table to create a rejected case
        if draw(st.booleans()):
            sep = ", "
        else:
            sep = ",\n"  # malformed by including newline in inline table
        body = sep.join(items)
        if trailing and n > 0:
            # parser accepts trailing comma in inline tables
            return "{" + body + ",}"
        return "{" + body + "}"
    return st.one_of(array_draw(), inline_draw())

# Allow deep recursion (many nesting levels). The max_leaves parameter controls max size;
# select a high cap to allow deep nested arrays/inline tables (see adaptation notes).
value_strategy = st.recursive(base_value, _extend_array_and_inline, max_leaves=2500)

# --- expressions: key/value lines, tables, array-of-tables, or comment-only ---
@st.composite
def key_value_line(draw):
    k = draw(key_strategy)
    # allow some malformed equals (missing or doubled)
    eq = draw(st.sampled_from([" = ", "=", "  =  ", "==", " = = "]))
    v = draw(value_strategy)
    # optionally append inline comment (control chars allowed)
    comment = ""
    if draw(st.booleans()):
        ctext = draw(st.lists(st.sampled_from(_sample_chars + ["#"]), min_size=0, max_size=20))
        comment = " #" + "".join(ctext)
    return k + eq + v + comment

@st.composite
def table_line(draw):
    k = draw(key_strategy)
    bracket_space = draw(st.sampled_from(["", " ", "  "]))
    # choose standard or array-of-tables
    if draw(st.booleans()):
        # standard table
        return "[" + bracket_space + k + bracket_space + "]"
    else:
        return "[[" + k + "]]"

@st.composite
def comment_only(draw):
    # comment or blank line
    if draw(st.booleans()):
        # comment containing control characters and non-ascii
        ctext = draw(st.lists(st.sampled_from(_sample_chars + ["#"]), min_size=0, max_size=40))
        return "#" + "".join(ctext)
    else:
        # blank line possibly with whitespace
        ws = "".join(draw(st.lists(st.sampled_from([" ", "\t"]), min_size=0, max_size=8)))
        return ws

_expression = st.one_of(key_value_line(), table_line(), comment_only())

# --- document assembly ---
@st.composite
def document(draw):
    # choose number of expressions; include empty documents and comment-only docs
    n = draw(st.integers(min_value=0, max_value=12))
    exprs = []
    # occasionally create deliberate duplicates by reusing a key
    reuse_key = None
    for i in range(n):
        kind = draw(st.sampled_from(["kv", "table", "comment"]))
        if kind == "kv":
            if reuse_key is None and draw(st.booleans()):
                # create one key and repeat it later
                k = draw(key_strategy)
                reuse_key = k
                v = draw(value_strategy)
                exprs.append(k + " = " + v)
            elif reuse_key is not None and draw(st.booleans()):
                # reuse duplicate key (to trigger duplicate key rejection)
                v = draw(value_strategy)
                exprs.append(reuse_key + " = " + v)
            else:
                exprs.append(draw(key_value_line()))
        elif kind == "table":
            exprs.append(draw(table_line()))
        else:
            exprs.append(draw(comment_only()))
    # assemble with varied newline separators (LF or CRLF)
    newline = draw(st.sampled_from(["\n", "\r\n"]))
    doc_text = newline.join(exprs)
    # optionally no trailing newline (documents without trailing newline are valid)
    if draw(st.booleans()):
        return doc_text
    else:
        return doc_text + newline

# Top-level strategy name required by the harness
strategy = document()
```