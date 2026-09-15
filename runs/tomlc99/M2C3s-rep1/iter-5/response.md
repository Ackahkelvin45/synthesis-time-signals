```python
from hypothesis import strategies as st
import json

# ASCII helpers (exclude NUL and quotes/backslash for single-line basic strings)
_ASCII_PRINTABLE_NO_QUOTE = "".join(
    chr(i) for i in range(1, 127) if i not in (34, 92, 0, 10, 13)
)
# For multiline basic/literal strings allow newline and more controls (still no NUL)
_ASCII_MULTILINE = "".join(chr(i) for i in range(1, 127) if i != 0)

# Key strategies
unquoted_key = st.from_regex(r"[A-Za-z0-9_-]{1,20}", fullmatch=True)
# Quoted key forms reuse string generators below

# Boolean
bool_strat = st.sampled_from(["true", "false"])

# Integer strategy: decimal (with underscores, leading zeros), hex, oct, bin
int_mag = st.integers(min_value=-10 ** 50, max_value=10 ** 50)
int_kind = st.sampled_from(["dec", "dec_leading_zero", "dec_underscored", "hex", "oct", "bin"])
@st.composite
def integer_strat(draw):
    n = draw(int_mag)
    kind = draw(int_kind)
    sign = "-" if n < 0 else "+" if n > 0 and draw(st.booleans()) and draw(st.booleans()) else ""
    absn = abs(n)
    if kind == "dec":
        s = sign + str(absn)
    elif kind == "dec_leading_zero":
        # deliberately allow leading zeros (e.g., 007)
        width = draw(st.integers(min_value=1, max_value=5))
        s = sign + str(absn).zfill(width)
    elif kind == "dec_underscored":
        base = str(absn)
        if len(base) <= 1:
            s = sign + base
        else:
            parts = []
            i = len(base)
            while i > 3:
                parts.insert(0, base[i - 3:i])
                i -= 3
            parts.insert(0, base[:i])
            s = sign + "_".join(parts)
    elif kind == "hex":
        hx = format(absn, "x")
        # uppercase/lowercase hex digits mixed possible
        if draw(st.booleans()):
            hx = hx.upper()
        # insert underscores occasionally
        if len(hx) > 2 and draw(st.booleans()):
            p = max(1, len(hx) // 3)
            hx = "_".join([hx[i:i+p] for i in range(0, len(hx), p)])
        s = sign + "0x" + hx
    elif kind == "oct":
        # produce octal digits possibly invalid leading zeros accepted by parser
        oc = format(absn, "o")
        if len(oc) > 2 and draw(st.booleans()):
            p = max(1, len(oc) // 3)
            oc = "_".join([oc[i:i+p] for i in range(0, len(oc), p)])
        s = sign + "0o" + oc
    else:  # bin
        bi = format(absn, "b")
        if len(bi) > 2 and draw(st.booleans()):
            p = max(1, len(bi) // 4)
            bi = "_".join([bi[i:i+p] for i in range(0, len(bi), p)])
        s = sign + "0b" + bi
    return s

# Floating-point strings: include 1., .5, exponent extremes, inf/nan
@st.composite
def float_strat(draw):
    choice = draw(st.sampled_from(["normal", "dot_end", "dot_start", "exp_big", "inf_nan"]))
    if choice == "normal":
        # allow underscores in integral part
        whole = draw(st.integers(min_value=0, max_value=10 ** 8))
        frac = draw(st.integers(min_value=0, max_value=10 ** 8))
        w = str(whole)
        if draw(st.booleans()) and len(w) > 1:
            # insert underscores
            p = max(1, len(w) // 3)
            w = "_".join([w[i:i+p] for i in range(0, len(w), p)])
        f = str(frac).rjust(1, "0")
        s = f"{w}.{f}"
    elif choice == "dot_end":
        s = str(draw(st.integers(min_value=0, max_value=10 ** 9))) + "."
    elif choice == "dot_start":
        s = "." + str(draw(st.integers(min_value=1, max_value=9999999)))
    elif choice == "exp_big":
        base = draw(st.integers(min_value=1, max_value=9))
        exp = draw(st.integers(min_value=100, max_value=4000))
        s = f"{base}e{exp}"
    else:
        signed = "-" if draw(st.booleans()) else ""
        s = signed + draw(st.sampled_from(["inf", "nan"]))
    return s

# Date/time forms
@st.composite
def date_strat(draw):
    # produce calendar-invalid dates sometimes
    year = draw(st.integers(min_value=0, max_value=9999)).to_bytes(2, "big")  # just to consume draw; we format below
    y = draw(st.integers(min_value=0, max_value=9999))
    mm = draw(st.integers(min_value=0, max_value=99))
    dd = draw(st.integers(min_value=0, max_value=99))
    hh = draw(st.integers(min_value=0, max_value=23))
    mi = draw(st.integers(min_value=0, max_value=59))
    ss = draw(st.integers(min_value=0, max_value=59))
    frac = ""
    if draw(st.booleans()):
        frac = "." + "".join(str(draw(st.integers(min_value=0, max_value=9))) for _ in range(draw(st.integers(min_value=1, max_value=6))))
    offset_choice = draw(st.sampled_from(["Z", "+", "-"]))
    if offset_choice == "Z":
        off = "Z"
    else:
        oh = draw(st.integers(min_value=0, max_value=23))
        om = draw(st.integers(min_value=0, max_value=59))
        off = f"{offset_choice}{str(oh).zfill(2)}:{str(om).zfill(2)}"
    form = draw(st.sampled_from(["offset_dt", "local_dt", "local_date", "local_time"]))
    if form == "offset_dt":
        s = f"{str(y).zfill(4)}-{str(mm).zfill(2)}-{str(dd).zfill(2)} T {str(hh).zfill(2)}:{str(mi).zfill(2)}:{str(ss).zfill(2)}{frac}{off}"
        # allow alternate 'T' as space or lowercase 't' sometimes
        s = s.replace(" T ", draw(st.sampled_from(["T", " ", "t"])))
    elif form == "local_dt":
        s = f"{str(y).zfill(4)}-{str(mm).zfill(2)}-{str(dd).zfill(2)} {str(hh).zfill(2)}:{str(mi).zfill(2)}:{str(ss).zfill(2)}{frac}"
    elif form == "local_date":
        s = f"{str(y).zfill(4)}-{str(mm).zfill(2)}-{str(dd).zfill(2)}"
    else:
        s = f"{str(hh).zfill(2)}:{str(mi).zfill(2)}:{str(ss).zfill(2)}{frac}"
    return s

# String generators
@st.composite
def basic_string(draw, allow_unterminated=False, allow_invalid_escape=False):
    # single-line basic string: cannot include raw newlines; may include control characters (except NUL)
    body = draw(st.text(alphabet=_ASCII_PRINTABLE_NO_QUOTE, min_size=0, max_size=60))
    # sometimes inject escape sequences
    if draw(st.booleans()):
        # choose some insertion positions
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            pos = draw(st.integers(min_value=0, max_value=len(body)))
            esc = draw(st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\\', '\\"', '\\u' + format(draw(st.integers(min_value=0, max_value=0xFFFF)), '04x')]))
            body = body[:pos] + esc + body[pos:]
    # invalid escape sometimes
    if allow_invalid_escape and draw(st.booleans()):
        pos = draw(st.integers(min_value=0, max_value=len(body)))
        body = body[:pos] + "\\q" + body[pos:]
    # sometimes include non-ASCII
    if draw(st.booleans()):
        body = body + draw(st.text(min_size=1, max_size=10))
    if allow_unterminated and draw(st.booleans()):
        return '"' + body  # unterminated
    return '"' + body + '"'

@st.composite
def literal_string(draw, multiline=False, allow_unterminated=False):
    if multiline:
        body = draw(st.text(alphabet=_ASCII_MULTILINE, min_size=0, max_size=80))
        if allow_unterminated and draw(st.booleans()):
            return "'''" + body  # unterminated
        return "'''" + body + "'''"
    else:
        body = draw(st.text(alphabet=_ASCII_PRINTABLE_NO_QUOTE, min_size=0, max_size=60))
        if allow_unterminated and draw(st.booleans()):
            return "'" + body  # unterminated
        return "'" + body + "'"

@st.composite
def ml_basic_string(draw, allow_unterminated=False):
    body = draw(st.text(alphabet=_ASCII_MULTILINE, min_size=0, max_size=200))
    # sometimes insert escaped newlines sequences and unicode escapes
    if draw(st.booleans()):
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            pos = draw(st.integers(min_value=0, max_value=len(body)))
            esc = draw(st.sampled_from(['\\\n', '\\u' + format(draw(st.integers(min_value=0, max_value=0xFFFF)), '04x')]))
            body = body[:pos] + esc + body[pos:]
    if allow_unterminated and draw(st.booleans()):
        return '"""' + body  # unterminated
    return '"""' + body + '"""'

@st.composite
def ml_literal_string(draw, allow_unterminated=False):
    body = draw(st.text(alphabet=_ASCII_MULTILINE, min_size=0, max_size=200))
    if allow_unterminated and draw(st.booleans()):
        return "'''" + body  # unterminated
    return "'''" + body + "'''"

# A general string strategy picking between forms and including edge cases
string_base = st.one_of(
    basic_string(),
    basic_string(allow_invalid_escape=True),
    basic_string(allow_unterminated=True),
    literal_string(multiline=False),
    literal_string(multiline=False, allow_unterminated=True),
    ml_basic_string(),
    ml_basic_string(allow_unterminated=True),
    ml_literal_string(),
    ml_literal_string(allow_unterminated=True),
)

# Now use st.recursive to create nested arrays and inline tables
# Base values include strings, integers, floats, booleans, dates
base_value = st.one_of(string_base, integer_strat(), float_strat(), bool_strat, date_strat())

# Build array and inline table makers that accept the child strategy
def array_strategy(children):
    # arrays may include comments/newlines interleaved; allow trailing comma
    @st.composite
    def arr(draw):
        # choose size up to moderate to keep examples manageable but allow empty arrays
        n = draw(st.integers(min_value=0, max_value=6))
        elems = []
        for i in range(n):
            v = draw(children)
            # sometimes wrap with inline comments or newlines between values
            if draw(st.booleans()):
                if draw(st.booleans()):
                    v = v + draw(st.sampled_from(["", " ", "\t"]))
            elems.append(v)
        sep = ", "
        joined = sep.join(elems)
        # occasional trailing comma
        if n > 0 and draw(st.booleans()):
            joined = joined + ","
        # multiline formatting with comments/newlines allowed in arrays
        if draw(st.booleans()):
            # insert newlines and comments around elements
            parts = []
            for e in elems:
                parts.append(e)
                if draw(st.booleans()):
                    parts.append("\n")
                    if draw(st.booleans()):
                        parts.append("#" + draw(st.text(alphabet=_ASCII_PRINTABLE_NO_QUOTE, min_size=0, max_size=20)) + "\n")
            joined = ", ".join([p for p in parts if p != "\n"])
            if draw(st.booleans()):
                joined = "[" + "\n" + joined + "\n" + "]"
                return joined
        return "[" + joined + "]"
    return arr()

def inline_table_strategy(children):
    # inline tables cannot contain newlines (parser rejects newline inside inline table)
    @st.composite
    def itab(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        pairs = []
        # allow duplicate keys for edge-case generation
        keys = []
        for i in range(n):
            # key may be quoted or unquoted
            if draw(st.booleans()):
                k = draw(unquoted_key)
            else:
                # quoted key: use a basic or literal string but without newline
                k = draw(basic_string()) if draw(st.booleans()) else draw(literal_string(multiline=False))
                # remove surrounding quotes if basic_string returned unterminated sometimes, ensure key stays quoted
            v = draw(children)
            # strip newline if accidentally inside value (inline tables disallow newline)
            v = v.replace("\n", " ")
            pairs.append(f"{k} = {v}")
            keys.append(k)
        joined = ", ".join(pairs)
        # allow trailing comma
        if n > 0 and draw(st.booleans()):
            joined = joined + ","
        return "{" + joined + "}"
    return itab()

# Construct the recursive value strategy (arrays and inline tables nest)
value = st.recursive(base_value, lambda children: st.one_of(array_strategy(children), inline_table_strategy(children)), max_leaves=2048)

# Key generation for key-value lines and tables, allow dotted keys
@st.composite
def simple_key(draw):
    if draw(st.booleans()):
        return draw(unquoted_key)
    else:
        # quoted key forms
        return draw(st.one_of(basic_string(), literal_string(multiline=False)))

@st.composite
def dotted_key(draw):
    parts = draw(st.lists(simple_key(), min_size=1, max_size=4))
    return ".".join(parts)

# Key-value line generator
@st.composite
def key_value_line(draw, val_strategy=None):
    if val_strategy is None:
        val_strategy = value
    # choose whether to use dotted or simple key
    key = draw(st.one_of(simple_key(), dotted_key()))
    val = draw(val_strategy)
    # sometimes add extra spaces or tabs around equals
    left_ws = draw(st.one_of(st.just(" "), st.just(""), st.just("\t"), st.just("  ")))
    right_ws = draw(st.one_of(st.just(" "), st.just(""), st.just("\t"), st.just("  ")))
    line = f"{key}{left_ws}={right_ws}{val}"
    # optionally append a comment
    if draw(st.booleans()):
        comment_text = draw(st.text(alphabet=_ASCII_PRINTABLE_NO_QUOTE, min_size=0, max_size=30))
        line = line + " #" + comment_text
    return line

# Table header generators
@st.composite
def standard_table_header(draw):
    key = draw(dotted_key())
    return "[" + key + "]"

@st.composite
def array_table_header(draw):
    key = draw(dotted_key())
    return "[[" + key + "]]"

# Expression: key-value, table, or comment-only line
@st.composite
def expression_line(draw, val_strategy=None):
    if val_strategy is None:
        val_strategy = value
    kind = draw(st.sampled_from(["kv", "table", "array_table", "comment"]))
    if kind == "kv":
        return draw(key_value_line(val_strategy))
    elif kind == "table":
        return draw(standard_table_header())
    elif kind == "array_table":
        return draw(array_table_header())
    else:
        # comment or blank
        if draw(st.booleans()):
            return "#" + draw(st.text(alphabet=_ASCII_PRINTABLE_NO_QUOTE, min_size=0, max_size=60))
        else:
            return ""  # blank line

# Build a complete document: sequence of expressions, optionally ending without newline
@st.composite
def document_strat(draw):
    # choose how many top-level expressions
    n = draw(st.integers(min_value=0, max_value=12))
    lines = []
    # Keep track of defined tables/keys to optionally generate duplicate-key scenarios
    defined_keys = []
    for i in range(n):
        # sometimes produce a table header followed by some key-value lines belonging to it
        if draw(st.booleans()):
            # produce a table or array_table occasionally
            if draw(st.booleans()):
                hdr = draw(standard_table_header())
            else:
                hdr = draw(array_table_header())
            lines.append(hdr)
            # add some key-values in the table
            for _ in range(draw(st.integers(min_value=0, max_value=3))):
                kv = draw(key_value_line(value))
                lines.append(kv)
                # record key name maybe for duplicates
                # attempt to parse key from kv (naively)
                if "=" in kv:
                    k = kv.split("=", 1)[0].strip()
                    defined_keys.append(k)
        else:
            # plain expression line
            ln = draw(expression_line(value))
            lines.append(ln)
            if "=" in ln:
                k = ln.split("=", 1)[0].strip()
                defined_keys.append(k)
    doc = "\n".join(lines)
    # optionally append a trailing newline or not (documents with no trailing newline allowed)
    if draw(st.booleans()):
        doc = doc + "\n"
    # sometimes deliberately insert duplicate keys on purpose to exercise rejection path
    if draw(st.booleans()) and defined_keys:
        dup = draw(st.sampled_from(defined_keys))
        # append duplicate assignment
        dup_val = draw(value)
        doc = doc + dup + " = " + dup_val + "\n"
    return doc

# Corruption layer: near-valid-but-malformed inputs
@st.composite
def corrupted_document(draw):
    base = draw(document_strat())
    # choose corruption type
    corruption = draw(st.sampled_from(["double_delim", "missing_delim", "stray_token", "drop_quote", "insert_invalid_token", "nothing"]))
    if corruption == "nothing":
        return base
    if len(base) == 0:
        return base + " "  # keep non-empty
    if corruption == "double_delim":
        # double a delimiter such as comma or bracket or equals
        pos = draw(st.integers(min_value=0, max_value=len(base) - 1))
        ch = base[pos]
        if ch in ",=[]#":
            return base[:pos] + ch + ch + base[pos + 1:]
        else:
            # fallback: duplicate a random bracket if present
            for d in "=[],":
                idx = base.find(d)
                if idx != -1:
                    return base[:idx] + d + d + base[idx + 1:]
            # else duplicate char at pos
            return base[:pos] + base[pos] + base[pos:]
    elif corruption == "missing_delim":
        # remove a delimiter like comma or bracket somewhere
        for d in [",", "]", "[", "=", "}"]:
            idxs = [i for i, c in enumerate(base) if c == d]
            if idxs:
                pos = draw(st.sampled_from(idxs))
                return base[:pos] + base[pos + 1:]
        # fallback remove a random character
        pos = draw(st.integers(min_value=0, max_value=len(base) - 1))
        return base[:pos] + base[pos + 1:]
    elif corruption == "stray_token":
        # insert a stray token such as '!' or '??' or ']]' at a random place
        tok = draw(st.sampled_from(["!", "??", "]]", "[[", "@", "/*"]))
        pos = draw(st.integers(min_value=0, max_value=len(base)))
        return base[:pos] + tok + base[pos:]
    elif corruption == "drop_quote":
        # make an unterminated string by removing a closing quote if present
        # find a closing quote
        idx = base.rfind('"')
        if idx != -1:
            # remove that final quote
            return base[:idx] + base[idx + 1:]
        idx2 = base.rfind("'")
        if idx2 != -1:
            return base[:idx2] + base[idx2 + 1:]
        # fallback: return base with trailing quote removed
        if base.endswith("\n"):
            return base[:-1] + '"'
        return base + '"'
    else:  # insert invalid token
        tok = draw(st.sampled_from(["\\q", "\\x", "\\uZZZZ"]))
        pos = draw(st.integers(min_value=0, max_value=len(base)))
        return base[:pos] + tok + base[pos:]

# Top-level strategy: sometimes valid doc, sometimes corrupted, favor valid
strategy = st.one_of(
    document_strat(),
    corrupted_document(),
    st.builds(lambda d: "\ufeff" + d, document_strat())
)
```