```python
from hypothesis import strategies as st
import json

# Top-level strategy: produces a TOML document as str
# Helpers to build pieces of TOML text

# Basic allowed characters for unquoted keys: ALPHA | DIGIT | '-' | '_'
_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

# Some unicode characters for quoted keys/strings
_unicode_extras = ["é", "ñ", "Ω", "λ", "漢", "字", "🌟", "🙂"]

# Disallow raw NUL in produced strings. We'll allow the six-character escape "\u0000".
_control_chars = [chr(i) for i in range(1, 32) if i != 0]  # includes control bytes except NUL

# Simple utilities
def _maybe_underscorize(s: str):
    # Insert underscores randomly into digits sequences for integers
    import random
    if not s:
        return s
    chars = list(s)
    for i in range(1, len(chars)):
        if chars[i].isdigit() and chars[i-1].isdigit() and random.random() < 0.2:
            chars.insert(i, "_")
    return "".join(chars)

# Key strategies
unquoted_key = st.text(alphabet=list(_key_chars), min_size=1, max_size=100) | \
              st.text(alphabet=list(_key_chars), min_size=1, max_size=10000).filter(lambda s: len(s) > 500)  # include very long keys

# Quoted keys: basic or literal strings (use same generators as values but constrained)
def _make_basic_string_inner():
    # produce inner content segments including escapes and control bytes (no raw NUL)
    pieces = [
        st.text(alphabet=list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_/.,"), min_size=0, max_size=10),
        st.sampled_from(["\\n", "\\t", "\\r", "\\\\", "\\\"", "\\u0000", "\\b", "\\f", "\\/"]),
        st.sampled_from(_control_chars).map(lambda c: c),  # raw control characters (except NUL)
        st.sampled_from(_unicode_extras)
    ]
    return st.lists(st.one_of(*pieces), min_size=1, max_size=8).map("".join)

basic_string = st.one_of(
    _make_basic_string_inner().map(lambda s: f'"{s}"'),
    # near-malformed: unterminated string (missing ending quote)
    _make_basic_string_inner().map(lambda s: f'"{s}'),
    # near-malformed: invalid escape like \q
    _make_basic_string_inner().map(lambda s: f'"{s}\\q"')
)

literal_string = st.one_of(
    st.text(min_size=0, max_size=30, alphabet=tuple(_control_chars + _unicode_extras + list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.,/"))).map(lambda s: f"'{s}'"),
    # single quote content that may contain a single quote -> malformed if not properly escaped; include it to test rejection
    st.just("'unclosed"),
)

# Multiline basic and literal strings
ml_basic_string = st.one_of(
    st.lists(st.one_of(
        st.text(alphabet=list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.,/"), min_size=0, max_size=20),
        st.sampled_from(["\\n", "\\t", "\\r", "\\\"", "\\u0000", "\\\\"]),
        st.sampled_from(_unicode_extras),
        st.sampled_from(_control_chars)
    ), min_size=1, max_size=6).map(lambda parts: '"""' + "\n".join(parts) + '"""'),
    # malformed unterminated multiline
    st.just('"""unterminated\nline')
)

ml_literal_string = st.one_of(
    st.lists(st.one_of(
        st.text(alphabet=list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.,/"), min_size=0, max_size=20),
        st.sampled_from(_unicode_extras),
        st.sampled_from(_control_chars)
    ), min_size=1, max_size=6).map(lambda parts: "'''"+ "\n".join(parts) + "'''"),
    st.just("'''unterminated")
)

# Strings union
string_value = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Integer strategies (various bases and edgecases)
@st.composite
def decimal_int_strategy(draw):
    sign = draw(st.one_of(st.just(""), st.just("+"), st.just("-")))
    # Allow leading zeros occasionally
    allow_leading_zero = draw(st.booleans())
    if allow_leading_zero:
        num = draw(st.integers(min_value=0, max_value=10**20))
        s = f"{num:0{draw(st.integers(1,4))}d}" if draw(st.booleans()) else str(num)
    else:
        num = draw(st.integers(min_value=0, max_value=10**30))
        s = str(num)
    if draw(st.booleans()):
        s = _maybe_underscorize(s)
    return sign + s

@st.composite
def hex_int_strategy(draw):
    digits = "0123456789abcdefABCDEF"
    # at least one hex digit
    n = draw(st.integers(min_value=1, max_value=20))
    raw = "".join(draw(st.sampled_from(list(digits))) for _ in range(n))
    if draw(st.booleans()):
        # insert underscores
        raw = _maybe_underscorize(raw)
    return "0x" + raw

@st.composite
def oct_int_strategy(draw):
    digits = "01234567"
    n = draw(st.integers(min_value=1, max_value=20))
    raw = "".join(draw(st.sampled_from(list(digits))) for _ in range(n))
    if draw(st.booleans()):
        raw = _maybe_underscorize(raw)
    return "0o" + raw

@st.composite
def bin_int_strategy(draw):
    digits = "01"
    n = draw(st.integers(min_value=1, max_value=64))
    raw = "".join(draw(st.sampled_from(list(digits))) for _ in range(n))
    if draw(st.booleans()):
        raw = _maybe_underscorize(raw)
    return "0b" + raw

integer_value = st.one_of(decimal_int_strategy(), hex_int_strategy(), oct_int_strategy(), bin_int_strategy())

# Floating-point numbers incl. special forms and extreme exponents
@st.composite
def float_strategy(draw):
    # include forms like "1.", ".5", "1.0", "1e309", "-inf", "nan"
    choice = draw(st.integers(min_value=0, max_value=6))
    if choice == 0:
        # normal float with maybe exponent
        intpart = draw(st.integers(min_value=0, max_value=10**6))
        frac = draw(st.one_of(st.just(""), st.just(".")))
        if frac == ".":
            # either .5 or 1.
            if draw(st.booleans()):
                # 1.
                return f"{intpart}."
            else:
                # .5 style
                fracpart = draw(st.integers(min_value=1, max_value=999))
                return f".{fracpart}"
        else:
            fracpart = draw(st.integers(min_value=0, max_value=999999))
            if draw(st.booleans()):
                exp = draw(st.integers(min_value=-400, max_value=400))
                return f"{intpart}.{fracpart}e{exp}"
            else:
                return f"{intpart}.{fracpart}"
    elif choice == 1:
        # inf/nan
        sign = draw(st.one_of(st.just(""), st.just("+"), st.just("-")))
        return sign + draw(st.sampled_from(["inf", "nan"]))
    else:
        # extreme exponent
        base = draw(st.integers(min_value=1, max_value=9))
        exp = draw(st.integers(min_value=308, max_value=2000)).map(str) if False else draw(st.integers(min_value=308, max_value=2000))
        return f"{base}e{exp}"

# Booleans
bool_value = st.sampled_from(["true", "false"])

# Date/time forms
@st.composite
def date_time_strategy(draw):
    # produce offset date-time, local date-time, local date, or local time
    kind = draw(st.integers(min_value=0, max_value=3))
    year = draw(st.integers(min_value=0, max_value=9999))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=31))  # calendar-invalid dates allowed
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    secfrac = ""
    if draw(st.booleans()):
        secfrac = "." + str(draw(st.integers(min_value=0, max_value=999999999))).rjust(1, "0")
    if kind == 0:
        # offset date-time with 'T' or space
        delim = draw(st.sampled_from(["T", "t", " "]))
        offset = draw(st.one_of(st.just("Z"), st.just("+00:00"), st.text(alphabet="+-", min_size=1, max_size=1) + "01:00"))
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{secfrac}{offset}"
    elif kind == 1:
        delim = draw(st.sampled_from(["T", "t", " "]))
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{secfrac}"
    elif kind == 2:
        return f"{year:04d}-{month:02d}-{day:02d}"
    else:
        return f"{hour:02d}:{minute:02d}:{second:02d}{secfrac}"

date_time_value = date_time_strategy()

# Base non-recursive value pieces
non_recursive_value = st.one_of(string_value, integer_value, float_strategy(), bool_value, date_time_value)

# Create recursive values: arrays and inline tables may nest
# We'll build textual representations for arrays and inline tables, using st.recursive
def _array_builder(child_strategy):
    # build arrays: allow comments/newlines inside per grammar, trailing commas allowed
    @st.composite
    def build_array(draw):
        # decide empty vs non-empty vs multiline with comments
        empty = draw(st.booleans())
        if empty:
            return "[]"
        # pick length small to moderate or create deep nesting sentinel
        if draw(st.booleans()):
            # normal array with elements chosen from child_strategy
            n = draw(st.integers(min_value=0, max_value=6))
            elems = [draw(child_strategy) for _ in range(n)]
            # optionally include comments/newlines between elements
            parts = []
            for i, e in enumerate(elems):
                if draw(st.booleans()):
                    parts.append(f"# comment")
                parts.append(e)
                if i != len(elems)-1:
                    parts.append(",")
            # optionally trailing comma
            if draw(st.booleans()):
                parts.append(",")
            content = " ".join(parts)
            # allow multiline with NLs
            if draw(st.booleans()):
                content = content.replace(" ", "\n")
            return "[" + content + "]"
        else:
            # produce a deliberately deep nested array to stress recursion: choose depth between 1500 and 2048 or smaller
            depth = draw(st.one_of(
                st.integers(min_value=1500, max_value=2048),
                st.integers(min_value=20, max_value=200)
            ))
            # pick a simple element inside
            inner = draw(st.one_of(st.just("1"), st.just('"x"'), st.just("true")))
            # build nested brackets: [ [ [ inner ] ] ]
            return "[" * depth + inner + "]" * depth
    return build_array()

def _inline_table_builder(child_strategy):
    # inline tables cannot contain newlines as per grammar (parser rejects newlines inside), but trailing comma allowed
    @st.composite
    def build_inline_table(draw):
        # empty inline table
        if draw(st.booleans()):
            return "{}"
        # produce a few key=value pairs
        n = draw(st.integers(min_value=1, max_value=6))
        pairs = []
        for _ in range(n):
            # key can be quoted or unquoted key
            k = draw(st.one_of(unquoted_key, basic_string, literal_string))
            # if k is a quoted string, ensure it's raw string, not including surrounding spaces accidentally
            # ensure EQUALS sign and a value
            v = draw(child_strategy)
            pairs.append(f"{k} = {v}")
        sep = ", "
        s = sep.join(pairs)
        # optionally trailing comma
        if draw(st.booleans()):
            s = s + ","
        # Optionally produce a malformed variant: include a newline inside inline table (which parser rejects)
        if draw(st.booleans()):
            s = s.replace(", ", ",\n")
        return "{" + s + "}"
    return build_inline_table()

# Construct the recursive value strategy using st.recursive
# base = non_recursive_value
# extend produces arrays and inline tables nesting child values
value_recursive = st.deferred(lambda:
    st.recursive(
        non_recursive_value,
        lambda children: st.one_of(
            _array_builder(children),
            _inline_table_builder(children)
        ),
        max_leaves=50  # allow reasonable recursion in strategy generation; deep nesting special-case included in _array_builder
    )
)

# Sometimes produce a stray token or near-valid-but-malformed values
near_malformed_value = st.one_of(
    # stray token
    st.just("+++"),
    # missing closing bracket for array
    value_recursive.map(lambda v: "[" + v),
    # doubled delimiter in array context
    value_recursive.map(lambda v: "[[" + v + "]]"),
    # unterminated basic string
    _make_basic_string_inner().map(lambda s: '"' + s),
    # stray equals
    st.just("="),
    # legit value
    value_recursive
)

# Build key (simple_key or dotted_key)
@st.composite
def simple_key_strategy(draw):
    # can be unquoted or quoted
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        return draw(unquoted_key)
    elif choice == 1:
        return draw(basic_string)
    else:
        return draw(literal_string)

@st.composite
def dotted_key_strategy(draw):
    # join multiple simple keys with dots (1..4 parts)
    parts = [draw(simple_key_strategy()) for _ in range(draw(st.integers(min_value=1, max_value=4)))]
    return ".".join(parts)

key_strategy = st.one_of(simple_key_strategy(), dotted_key_strategy())

# Key-value pair builder: sometimes intentionally produce duplicate keys by generating same key twice in doc construction stage
@st.composite
def key_value_line(draw):
    k = draw(key_strategy)
    v = draw(st.one_of(value_recursive, near_malformed_value))
    # Possibly append a comment
    if draw(st.booleans()):
        c = draw(st.one_of(st.just(""), st.just(f" # {draw(st.text(min_size=1,max_size=20))}")))
    else:
        c = ""
    return f"{k} = {v}{c}"

# Table builders
@st.composite
def standard_table_line(draw):
    k = draw(key_strategy)
    # well-formed or malformed (missing bracket or doubled bracket)
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        return f"[{k}]"
    elif choice == 1:
        return f"[{k}"  # missing closing bracket
    elif choice == 2:
        return f"[[{k}]]"  # doubled bracket wrongly for standard table
    else:
        # correct but with extra whitespace or comment
        return f"[ {k} ]"

@st.composite
def array_table_line(draw):
    k = draw(key_strategy)
    # proper or malformed
    if draw(st.booleans()):
        return f"[[{k}]]"
    else:
        # malformed like missing one bracket
        return f"[[{k}]"  # missing closing double bracket

# Comments and blank lines
comment_line = st.one_of(
    st.just(""),
    st.just("# comment"),
    st.builds(lambda s: "# " + s, st.text(min_size=0, max_size=60))
)

# Expression is key_value, table, or comment
expression = st.one_of(
    key_value_line(),
    standard_table_line(),
    array_table_line(),
    comment_line
)

# Document builder: combine expressions with newlines; include also empty document and comment-only
@st.composite
def document_builder(draw):
    # decide size
    # include some cases with many lines, duplicates, and also minimal docs
    size = draw(st.one_of(st.just(0), st.integers(min_value=1, max_value=20)))
    lines = []
    seen_keys = []
    for i in range(size):
        expr_type = draw(st.integers(min_value=0, max_value=6))
        if expr_type == 0:
            # comment
            lines.append(draw(comment_line))
        elif expr_type == 1:
            # table
            lines.append(draw(standard_table_line()))
        elif expr_type == 2:
            # array table
            lines.append(draw(array_table_line()))
        else:
            # key value; sometimes intentionally produce duplicate keys
            kv = draw(key_value_line())
            # maybe create duplicates by reusing a previous key name (if any)
            if draw(st.booleans()) and seen_keys:
                # create duplicate by reusing earlier key's left-hand side
                prev_key = draw(st.sampled_from(seen_keys))
                # create different RHS
                v = draw(st.one_of(value_recursive, near_malformed_value))
                kv = f"{prev_key} = {v}"
            else:
                # register this key if it's a simple key_value (extract before '=')
                if "=" in kv:
                    left = kv.split("=", 1)[0].strip()
                    seen_keys.append(left)
            lines.append(kv)
    # ensure document can be empty or comment-only
    doc = "\n".join(lines)
    # optionally add a trailing newline or not (documents with no trailing newline are allowed)
    if draw(st.booleans()):
        doc = doc + ("\r\n" if draw(st.booleans()) else "\n")
    # Add possibility of stray token appended at the end
    if draw(st.booleans()):
        doc = doc + draw(st.one_of(st.just("+++"), st.just("###"), st.just("="), st.just("[")))
    return doc

# Final top-level strategy: mix document builder with some specially-crafted extreme documents
deep_table_doc = st.integers(min_value=1500, max_value=2048).map(lambda n: "[" + ("a." * (n//2)) + "x" + "]\nkey = 1")
# Another extreme: deeply nested inline tables manually constructed (use braces)
def _deep_inline_table(depth):
    # build nested inline table text like {a = {a = { ... } } }
    inner = "1"
    for i in range(depth):
        inner = "{a = " + inner + "}"
    return inner

deep_inline_table_doc = st.integers(min_value=1500, max_value=2048).map(lambda n: _deep_inline_table(n))

# Compose final strategy: mix generated documents, deep stress cases, and tiny corner cases
strategy = st.one_of(
    document_builder(),
    deep_table_doc,
    deep_inline_table_doc,
    # empty document and comment-only docs
    st.just(""),
    st.just("# just a comment"),
    # a document with many duplicate keys to test rejection behavior
    st.builds(lambda k: f"{k} = 1\n{k} = 2", unquoted_key),
)
```