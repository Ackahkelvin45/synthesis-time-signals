from hypothesis import strategies as st
import json

# Helper character pools (avoid NUL \x00 in raw output)
_ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_KEY_CHARS = _ASCII_LETTERS + _DIGITS + "_-"
_PUNCT = "!@#$%^&*()[]:;<>/?\\,.-+=|~"  # note: will filter out " and \
# Build a pool for raw string content excluding double-quote (34) and backslash (92) and NUL (0)
_RAW_POOL = "".join(chr(i) for i in range(1, 127) if i not in (34, 92))
# Allow some unicode escapes as explicit sequences (safe re: NUL: include \u0000 as escape, not raw)
_ESCAPE_SEQ = ['\\n', '\\r', '\\t', '\\b', '\\f', '\\\\', '\\"', "\\u0000", "\\u00A9", "\\U0001F600"]

# Basic helpers
def _join(parts):
    return "".join(parts)

# Key strategies
_unquoted_key = st.text(alphabet=_KEY_CHARS, min_size=1, max_size=20)
# Extremely long key (10_000 chars) occasionally
_long_key = st.text(alphabet=_KEY_CHARS, min_size=1000, max_size=10000)
# Quoted keys: basic or literal string variants (reuse string parts below)
# We'll construct them later to avoid forward reference issues.

# String strategies
_basic_string_content = st.lists(
    st.one_of(
        st.text(alphabet=_RAW_POOL, min_size=0, max_size=30),
        st.sampled_from(_ESCAPE_SEQ),
    ),
    min_size=0,
    max_size=6,
).map(_join)

_basic_string = st.one_of(
    _basic_string_content.map(lambda s: f'"{s}"'),
    # Unterminated variations (near-valid-but-malformed)
    _basic_string_content.map(lambda s: f'"{s}'),  # missing closing quote
)

_literal_string_content = st.text(
    alphabet="".join(chr(i) for i in range(1, 127) if i != 39), min_size=0, max_size=40
)
_literal_string = st.one_of(
    _literal_string_content.map(lambda s: f"'{s}'"),
    # Unterminated single-quote literal
    _literal_string_content.map(lambda s: f"'{s}"),
)

_ml_basic_string_content = st.lists(
    st.one_of(
        st.text(alphabet=_RAW_POOL + "\n\r\t", min_size=0, max_size=80),
        st.sampled_from(_ESCAPE_SEQ),
    ),
    min_size=0,
    max_size=10,
).map(_join)
_ml_basic_string = st.one_of(
    _ml_basic_string_content.map(lambda s: f'"""{s}"""'),
    # Unterminated multiline basic
    _ml_basic_string_content.map(lambda s: f'"""{s}'),
)

_ml_literal_string_content = st.text(
    alphabet="".join(chr(i) for i in range(1, 127) if i != 39), min_size=0, max_size=80
)
_ml_literal_string = st.one_of(
    _ml_literal_string_content.map(lambda s: f"'''{s}'''"),
    _ml_literal_string_content.map(lambda s: f"'''{s}"),
)

# Quoted keys (quoted_key: BASIC_STRING or LITERAL_STRING)
_quoted_key = st.one_of(
    _basic_string.map(lambda s: s),  # already quoted
    _literal_string.map(lambda s: s),
)

# Numeric strategies
def _underscore_join(digits: str):
    # Insert underscores randomly into digits (but not start/end)
    if len(digits) <= 1:
        return digits
    parts = []
    for ch in digits:
        parts.append(ch)
        # randomly insert underscores
        if st.shared(st.booleans(), key="u") is not None:
            pass
    # Simpler: use random placement via Hypothesis strategies
    return st.just(digits)  # fallback not used directly; handled below

_dec_int = st.one_of(
    # Leading zeros allowed per parser realities
    st.text(alphabet=_DIGITS, min_size=1, max_size=20).map(lambda s: s),
    # With sign and underscores
    st.tuples(st.sampled_from(["+", "-", ""]), st.text(alphabet=_DIGITS, min_size=1, max_size=20)).map(
        lambda t: f"{t[0]}{t[1]}"
    ),
)
# Now make variants with underscores
_dec_int_with_underscore = st.builds(
    lambda sign, digits, us: (f"{sign}{''.join(d + ('_' if i < len(us) and us[i] else '') for i, d in enumerate(digits))}"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet=_DIGITS, min_size=1, max_size=20),
    st.lists(st.booleans(), min_size=0, max_size=20),
)

_hex_digits = "0123456789abcdefABCDEF"
_hex_int = st.builds(
    lambda body: "0x" + body,
    st.text(alphabet=_hex_digits, min_size=1, max_size=30),
)

_oct_digits = "01234567"
_oct_int = st.builds(
    lambda body: "0o" + body,
    st.text(alphabet=_oct_digits, min_size=1, max_size=30),
)

_bin_digits = "01"
_bin_int = st.builds(
    lambda body: "0b" + body,
    st.text(alphabet=_bin_digits, min_size=1, max_size=64),
)

_integer = st.one_of(
    _dec_int_with_underscore,
    _hex_int,
    _oct_int,
    _bin_int,
)

# Floats, infinities, NaN, variants like '1.' and '.5' and extreme exponents
_float_basic = st.one_of(
    # normal float with frac
    st.builds(
        lambda intp, frac, exp: f"{intp}.{frac}{exp}",
        st.text(alphabet=_DIGITS, min_size=1, max_size=10),
        st.text(alphabet=_DIGITS, min_size=1, max_size=10),
        st.one_of(st.just(""), st.builds(lambda s: f"e{('+' if s[0] else '-')}{s[1]}", st.tuples(st.booleans(), st.text(alphabet=_DIGITS, min_size=1, max_size=4)))),  # exponents
    ),
    # '1.' form
    st.text(alphabet=_DIGITS, min_size=1, max_size=10).map(lambda s: s + "."),
    # '.5' form
    st.text(alphabet=_DIGITS, min_size=1, max_size=10).map(lambda s: "." + s),
    # exponential only
    st.builds(lambda i, e: f"{i}e{e}", st.text(alphabet=_DIGITS, min_size=1, max_size=5), st.text(alphabet=_DIGITS, min_size=1, max_size=4)),
    # extremes: huge exponent or huge mantissa
    st.builds(lambda m, e: f"{m}e{e}", st.text(alphabet=_DIGITS, min_size=300, max_size=600), st.integers(min_value=100, max_value=10000).map(str)),
)

_float_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_float = st.one_of(_float_basic, _float_inf_nan)

# Boolean
_bool = st.sampled_from(["true", "false"])

# Date-time forms: offset date-time, local date-time, local date, local time
_date_component = st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}")
_year = st.integers(min_value=0, max_value=9999).map(lambda y: f"{y:04d}")
_hour = st.integers(min_value=0, max_value=23).map(lambda h: f"{h:02d}")
_min_sec = st.integers(min_value=0, max_value=59).map(lambda m: f"{m:02d}")
_secfrac = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text(alphabet=_DIGITS, min_size=1, max_size=9)))
_offset = st.one_of(st.just("Z"), st.builds(lambda s1, s2: f"+{s1}:{s2}", _hour, _min_sec), st.builds(lambda s1, s2: f"-{s1}:{s2}", _hour, _min_sec))

_offset_date_time = st.builds(
    lambda y, mo, d, hh, mm, ss, of: f"{y}-{mo}-{d}T{hh}:{mm}:{ss}{of}",
    _year,
    _date_component,
    _date_component,
    _hour,
    _min_sec,
    st.builds(lambda s, f: s + f, _min_sec, _secfrac),
    _offset,
)

_local_date_time = st.builds(
    lambda y, mo, d, hh, mm, ss: f"{y}-{mo}-{d} {hh}:{mm}:{ss}",
    _year,
    _date_component,
    _date_component,
    _hour,
    _min_sec,
    st.builds(lambda s, f: s + f, _min_sec, _secfrac),
)

_local_date = st.builds(lambda y, mo, d: f"{y}-{mo}-{d}", _year, _date_component, _date_component)
_local_time = st.builds(lambda hh, mm, ss: f"{hh}:{mm}:{ss}", _hour, _min_sec, st.builds(lambda s, f: s + f, _min_sec, _secfrac))

_date_time = st.one_of(_offset_date_time, _local_date_time, _local_date, _local_time)

# Base (non-recursive) values strategy: produce textual representation of a single TOML value
_base_value = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
    _integer,
    _float,
    _bool,
    _date_time,
    st.just("[]"),     # empty array
    st.just("{}"),     # empty inline table
)

# Now recursive construction for arrays and inline tables
def _array_of(elem_strategy):
    # Construct arrays with 0..6 elements, allow trailing comma, newlines/comments inside
    @st.composite
    def _arr(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        elems = [draw(elem_strategy) for _ in range(n)]
        # Optionally insert comments or newlines between elements
        parts = []
        for i, e in enumerate(elems):
            # occasionally add a stray token or malformed delimiter (near-miss)
            if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=20)) == 0:
                parts.append(" " + e + " " + draw(st.sampled_from([",", ";;", ""])) )
            else:
                parts.append(e)
        joiner = draw(st.sampled_from([", ", ",\n", ",\t", ","]))
        body = joiner.join(parts)
        # trailing comma sometimes
        if draw(st.booleans()):
            if body.strip() == "":
                body = ""
            else:
                body = body + ","
        # allow comments/newlines around
        prefix = "" if draw(st.booleans()) else "\n"
        suffix = "" if draw(st.booleans()) else "\n"
        return f"[{prefix}{body}{suffix}]"
    return _arr()

def _inline_table_of(elem_strategy):
    # Inline tables: { key = value, ... } ; newline inside inline table is usually rejected, but we sometimes produce it for malformed inputs
    @st.composite
    def _tbl(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        kvs = []
        for _ in range(n):
            # keys: either unquoted or quoted (basic or literal)
            k = draw(st.one_of(_unquoted_key, _quoted_key, _long_key))
            v = draw(elem_strategy)
            # Ensure no newline inside most inline tables; optionally insert newline to create a malformed case
            if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=30)) == 0:
                # force a newline inside inline table (malformed per parser)
                kvs.append(f"{k} = {v}\n")
            else:
                kvs.append(f"{k} = {v}")
        sep = draw(st.sampled_from([", ", ",", ",\t"]))
        body = sep.join(kvs)
        # optional trailing comma is accepted by the parser
        if draw(st.booleans()):
            body = body + ","
        return "{" + body + "}"
    return _tbl()

# The recursive value strategy: values can be base or arrays or inline tables (which themselves contain values)
value_strategy = st.deferred(lambda: st.recursive(
    _base_value,
    lambda children: st.one_of(
        _array_of(children),
        _inline_table_of(children),
    ),
    max_leaves=100
))

# Deep nesting generator for concentrated depth (1500..2048) - rare but included
@st.composite
def _deep_nesting(draw):
    depth = draw(st.integers(min_value=1500, max_value=2048))
    # Choose a small base value
    base = draw(st.one_of(st.just("1"), st.just('"deep"'), st.just("true")))
    # Build nested arrays: '[' * depth + base + ']' * depth
    return "[" * depth + base + "]" * depth

# Key (simple or dotted)
_dotted_key = st.lists(st.one_of(_unquoted_key, _quoted_key, _long_key), min_size=1, max_size=4).map(lambda parts: ".".join(parts))

# Line/comment builders
@st.composite
def _key_value_line(draw, val_strategy):
    # Occasionally produce malformed variants: doubled equals, missing equals, stray token
    key = draw(st.one_of(_unquoted_key, _quoted_key, _long_key, _dotted_key))
    val = draw(val_strategy)
    malformed = draw(st.integers(min_value=0, max_value=40))
    if malformed == 0:
        # doubled equals
        return f"{key} == {val}"
    elif malformed == 1:
        # missing equals
        return f"{key} {val}"
    elif malformed == 2:
        # stray token before
        return f"= {key} = {val}"
    else:
        # normal case
        # occasional comment after
        if draw(st.booleans()):
            comment = draw(st.one_of(st.just(""), st.builds(lambda s: "# " + s, st.text(min_size=0, max_size=40))))
            return f"{key} = {val}{(' ' + comment) if comment else ''}"
        return f"{key} = {val}"

@st.composite
def _table_line(draw):
    # Standard table [key] or array table [[key]] ; include dotted keys
    key = draw(st.one_of(_dotted_key, _unquoted_key, _quoted_key, _long_key))
    if draw(st.booleans()):
        # array table
        return "[[" + key + "]]"
    else:
        return "[" + key + "]"

@st.composite
def _comment_line(draw):
    # Comments may contain control characters too (accepted)
    content = draw(st.text(alphabet="".join(chr(i) for i in range(1, 127)), min_size=0, max_size=60))
    return "#" + content

# Expression: key_value, table, or comment-only line
_expression = st.one_of(
    _key_value_line(value_strategy),
    _table_line(),
    _comment_line(),
)

# Document builder: sequence of expressions separated by newlines; allow empty or comment-only documents and missing trailing newline
@st.composite
def _document(draw):
    # Sometimes return an empty document or just comments
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        # empty document
        return ""
    if choice == 1:
        # comment-only document (single or multiple comments)
        n = draw(st.integers(min_value=1, max_value=5))
        lines = [draw(_comment_line()) for _ in range(n)]
        # maybe no trailing newline
        if draw(st.booleans()):
            return "\n".join(lines)
        else:
            return "\n".join(lines)
    # otherwise build a mixed document
    n_lines = draw(st.integers(min_value=1, max_value=30))
    lines = []
    for _ in range(n_lines):
        # Occasionally insert a deep nesting giant array as a whole document
        if draw(st.integers(min_value=0, max_value=200)) == 0:
            lines.append(draw(_deep_nesting()))
            continue
        lines.append(draw(_expression))
    # Insert some table headers and key values relation: allow duplicate keys occasionally
    doc = "\n".join(lines)
    # Optionally add final trailing newline or omit
    if draw(st.booleans()):
        doc = doc + ("\n" if draw(st.booleans()) else "")
    return doc

# Top-level strategy: produce the document string
strategy = _document()