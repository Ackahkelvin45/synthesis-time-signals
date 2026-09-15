Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# Helper small strategies
_hexdigits = "0123456789abcdefABCDEF"
_digits = "0123456789"
_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Basic building blocks
unquoted_key = st.from_regex(r"[A-Za-z0-9_-]{1,20}", fullmatch=True)

# Quoted key: reuse basic string generator for content, but allow empty quoted key ""
@st.composite
def quoted_key_strategy(draw):
    # Use a simple basic-string content (no raw newlines)
    content = draw(
        st.lists(
            st.one_of(
                # printable chars excluding " and backslash and newline
                st.characters(blacklist_characters='"\n\\\r', min_codepoint=0x20),
                # unicode escape sequences
                st.builds(lambda h: "\\u" + h, st.text(_hexdigits, min_size=4, max_size=4)),
                st.builds(lambda h: "\\U" + h, st.text(_hexdigits, min_size=8, max_size=8)),
                # valid common escapes
                st.sampled_from(["\\n", "\\t", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\/"]),
                # invalid escape to generate near-malformed inputs
                st.just("\\q"),
                # raw control characters (not NUL, avoid 10,13 which are newline/CR)
                st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c not in ("\x00", "\n", "\r")),
                # some non-ASCII
                st.characters(min_codepoint=0x80, max_codepoint=0x1FFFF),
            ),
            min_size=0,
            max_size=8,
        ).map("".join)
    )
    return f'"{content}"'

# Basic string variants
def basic_string_content():
    # tokens for basic string content (no raw newline or raw double quote/backslash unescaped)
    token = st.one_of(
        st.characters(blacklist_characters='"\n\\\r', min_codepoint=0x20),
        st.builds(lambda h: "\\u" + h, st.text(_hexdigits, min_size=4, max_size=4)),
        st.builds(lambda h: "\\U" + h, st.text(_hexdigits, min_size=8, max_size=8)),
        st.sampled_from(["\\n", "\\t", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\/"]),
        st.just("\\q"),  # invalid escape
        # raw control char (not NUL)
        st.characters(min_codepoint=1, max_codepoint=31).filter(lambda c: c not in ("\x00", "\n", "\r")),
        st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
    )
    return st.lists(token, min_size=0, max_size=10).map("".join)

basic_string = st.one_of(
    # well-formed basic string
    basic_string_content().map(lambda s: f'"{s}"'),
    # unterminated string (near-malformed)
    basic_string_content().map(lambda s: f'"{s}'),
    # extra quote doubled at end
    basic_string_content().map(lambda s: f'"{s}""'),
)

# Literal string (single-quoted) - no escapes processed
literal_string = st.one_of(
    st.lists(
        st.characters(blacklist_characters="'\n\r", min_codepoint=0x20, max_codepoint=0x10FFFF),
        min_size=0,
        max_size=12,
    ).map("".join).map(lambda s: f"'{s}'"),
    # unterminated literal
    st.lists(
        st.characters(blacklist_characters="'\n\r", min_codepoint=0x20, max_codepoint=0x10FFFF),
        min_size=0,
        max_size=12,
    ).map("".join).map(lambda s: f"'{s}"),
)

# Multiline basic and literal strings
ml_basic_string = st.one_of(
    st.lists(
        st.one_of(
            st.characters(blacklist_characters='\\', min_codepoint=0x0A, max_codepoint=0x10FFFF),
            st.just("\\n"),
            st.builds(lambda h: "\\u" + h, st.text(_hexdigits, min_size=4, max_size=4)),
            st.builds(lambda h: "\\U" + h, st.text(_hexdigits, min_size=8, max_size=8)),
            st.just("\\q"),
        ),
        min_size=0,
        max_size=20,
    ).map("".join).map(lambda s: f'"""{s}"""'),
    # Unterminated multiline
    st.lists(
        st.characters(min_codepoint=0x0A, max_codepoint=0x10FFFF),
        min_size=0,
        max_size=20,
    ).map("".join).map(lambda s: f'"""{s}'),
)

ml_literal_string = st.one_of(
    st.lists(
        st.characters(min_codepoint=0x0A, max_codepoint=0x10FFFF),
        min_size=0,
        max_size=20,
    ).map("".join).map(lambda s: f"'''{s}'''"),
    st.lists(
        st.characters(min_codepoint=0x0A, max_codepoint=0x10FFFF),
        min_size=0,
        max_size=20,
    ).map("".join).map(lambda s: f"'''{s}"),
)

string_value = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Integer generators
def dec_int():
    # allow leading zeros (adaptation note)
    digits = st.one_of(
        st.from_regex(r"[0-9]+", fullmatch=True),
        st.from_regex(r"[+-]?[0-9]+", fullmatch=True),
    )
    # add underscores randomly
    def with_underscores(s):
        if len(s) <= 1:
            return s
        parts = []
        i = 0
        while i < len(s):
            chunk = s[i : i + max(1, min(3, len(s) - i))]
            parts.append(chunk)
            i += len(chunk)
            if i < len(s) and st.randoms().example().randint(0, 1) == 0:
                parts.append("_")
        return "".join(parts)
    # Because using with randoms().example() is not ideal, instead produce underscores via strategy compositions:
    return st.integers(min_value=0, max_value=1).flatmap(
        lambda signflag: st.text(_digits, min_size=1, max_size=40).map(
            lambda s, sf=signflag: (("" if sf == 0 else "-") + s)
        )
    )

hex_int = st.builds(
    lambda body, sign: (("+" if sign == "+" else "-") if sign else "") + "0x" + body,
    st.text(_hexdigits, min_size=1, max_size=40),
    st.sampled_from(["", "+", "-"]),
)

oct_int = st.builds(lambda body: "0o" + body, st.from_regex(r"[0-7](_?[0-7])*", fullmatch=True))
bin_int = st.builds(lambda body: "0b" + body, st.from_regex(r"[01](_?[01])*", fullmatch=True))

# More deterministic decimal integer with underscores inserted
@st.composite
def dec_int_with_underscores(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    digits = draw(st.text(_digits, min_size=1, max_size=60))
    # randomly insert underscores
    parts = []
    i = 0
    while i < len(digits):
        chunk_len = draw(st.integers(min_value=1, max_value=min(4, len(digits) - i)))
        parts.append(digits[i : i + chunk_len])
        i += chunk_len
        if i < len(digits) and draw(st.booleans()):
            parts.append("_")
    s = sign + "".join(parts)
    # sometimes create leading zeros like 007
    if draw(st.booleans()):
        s = sign + ("0" * draw(st.integers(0, 3))) + s.lstrip("+-")
    return s

integer_value = st.one_of(dec_int_with_underscores(), hex_int, oct_int, bin_int)

# Floats including weird forms
@st.composite
def float_value(draw):
    kind = draw(st.sampled_from(["normal", "dot_trail", "no_lead", "exp_big", "inf_nan"]))
    if kind == "normal":
        # e.g. 1.234 or 1. or .5 (we include other forms separately)
        a = draw(st.text(_digits, min_size=1, max_size=10))
        frac = draw(st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text(_digits, min_size=1, max_size=10))))
        exp = draw(st.one_of(st.just(""), st.builds(lambda e: "e" + e, st.text(_digits, min_size=1, max_size=4))))
        return a + frac + exp
    if kind == "dot_trail":
        a = draw(st.text(_digits, min_size=1, max_size=10))
        return a + "."
    if kind == "no_lead":
        frac = draw(st.text(_digits, min_size=1, max_size=10))
        return "." + frac
    if kind == "exp_big":
        a = draw(st.text(_digits, min_size=1, max_size=10))
        e = draw(st.integers(min_value=100, max_value=10000))
        return a + "e" + ("+" if draw(st.booleans()) else "") + str(e)
    if kind == "inf_nan":
        sign = draw(st.sampled_from(["", "+", "-"]))
        val = draw(st.sampled_from(["inf", "nan"]))
        return sign + val
    return "0.0"

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time forms (generate many with calendar-invalid allowed)
@st.composite
def date_values(draw):
    year = draw(st.integers(min_value=0, max_value=9999))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=31))  # calendar-invalid allowed
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    secfrac = draw(st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text(_digits, min_size=1, max_size=6))))
    delim = draw(st.sampled_from(["T", "t", " "]))
    # offset or Z
    off = draw(st.one_of(st.just("Z"), st.builds(lambda s, m: s + ":" + m, st.text(_digits, min_size=2, max_size=2), st.text(_digits, min_size=2, max_size=2))))
    kind = draw(st.sampled_from(["offset_dt", "local_dt", "local_date", "local_time"]))
    if kind == "offset_dt":
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{secfrac}{off}"
    if kind == "local_dt":
        return f"{year:04d}-{month:02d}-{day:02d}{delim}{hour:02d}:{minute:02d}:{second:02d}{secfrac}"
    if kind == "local_date":
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{hour:02d}:{minute:02d}:{second:02d}{secfrac}"

date_value = date_values()

# Placeholder for empty inline table
empty_inline_table = st.just("{}")

# Recursive value strategy to produce arrays and inline tables
# Base (non-recursive) values:
base_value = st.one_of(
    string_value,
    integer_value, integer_value, integer_value,
    float_value(),
    bool_value,
    date_value,
    empty_inline_table,
)

def array_of(children):
    # children is a strategy producing value strings
    # Generate elements with optional comments/newlines between them
    elem = children
    # Allow nested comments/newlines: simulate with adding "#c" comments and newlines
    sep_elem = st.tuples(elem, st.one_of(st.just(""), st.just(" "), st.just("  "), st.just("\n"), st.just("\r\n"), st.just(" #c\n")))
    return st.lists(sep_elem, min_size=0, max_size=6).map(
        lambda items: "[" + ", ".join(i[0] for i in items) + ("," if len(items) and (len(items) % 4 == 0) else "") + "]"
    )

def inline_table_of(children):
    # inline table entries: key = value, separated by commas; allow trailing comma
    @st.composite
    def _inline(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        parts = []
        for _ in range(n):
            # choose key form: unquoted or quoted
            k = draw(st.one_of(unquoted_key, quoted_key_strategy()))
            v = draw(children)
            parts.append(f"{k} = {v}")
        # sometimes insert a newline inside (near-malformed)
        if draw(st.booleans()):
            sep = ", "
        else:
            sep = ",\n" if draw(st.booleans()) else ", "
        s = sep.join(parts)
        # allow trailing comma
        if draw(st.booleans()) and parts:
            s = s + ","
        return "{" + s + "}"
    return _inline()

# Use st.recursive to allow nested arrays and inline tables
# We must ensure recursion is used for array/inline table creation.
value_strategy = st.recursive(
    base_value,
    lambda children: st.one_of(
        st.deferred(lambda: array_of(children)),
        st.deferred(lambda: inline_table_of(children)),
    ),
    max_leaves=50,
)

# Keys for dotted keys: simple_key or quoted_key
simple_key = st.one_of(unquoted_key, quoted_key_strategy())

@st.composite
def dotted_key_strategy(draw):
    # produce 1-4 segments
    n = draw(st.integers(min_value=1, max_value=4))
    parts = [draw(simple_key) for _ in range(n)]
    # sometimes make it a long key (10k chars) as adaptation note
    if draw(st.booleans()):
        # produce extremely long segment
        longseg = draw(st.text(min_size=1000, max_size=10000))
        parts[-1] = '"' + longseg.replace('"', '\\"') + '"'
    return ".".join(parts)

# Table header strategies
table_header = st.one_of(
    dotted_key_strategy().map(lambda k: f"[{k}]"),
    dotted_key_strategy().map(lambda k: f"[[{k}]]"),
    # malformed/missing bracket variants
    dotted_key_strategy().map(lambda k: f"[{k}"),   # missing closing
    dotted_key_strategy().map(lambda k: f"[[{k}]"), # missing one closing
    st.just("]"),  # stray token
)

# Key-value line
@st.composite
def key_value_line(draw, allow_malformed=True):
    key = draw(st.one_of(simple_key, dotted_key_strategy()))
    eq_variant = draw(st.one_of(st.just(" = "), st.just("= "), st.just(" ="), st.just("== "), st.just(" =  = ")))
    val = draw(value_strategy)
    # sometimes produce a stray token after value
    if draw(st.booleans()):
        trailing = ""
    else:
        trailing = draw(st.one_of(st.just(""), st.just(" #comment"), st.just(" stray")))
    return f"{key}{eq_variant}{val}{trailing}"

# Comment-only line
comment_line = st.one_of(
    st.just(""),
    st.builds(lambda s: "#" + s, st.text(min_size=0, max_size=50)).map(lambda s: s),
)

# Malformed stray tokens generator
malformed_line = st.one_of(
    st.just("="),
    st.just("=="),
    st.just("["),
    st.just("]]"),
    st.just("'''unterminated"),
    st.just('"unterminated'),
)

# Expression strategy: key_value, table, comment, or malformed
expression = st.one_of(
    key_value_line(),
    table_header,
    comment_line,
    malformed_line,
)

# Document generator: list of expressions joined by newline variants
newline = st.sampled_from(["\n", "\r\n"])
strategy = st.tuples(st.lists(expression, min_size=0, max_size=30), newline).map(lambda t: t[1].join(t[0]))
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 27,
    "reject": 229,
    "skip": 94
  },
  "acceptance_rate": 0.105,
  "max_nesting_depth": 0,
  "productions_accepted": [
    "BASIC_STRING",
    "COMMENT",
    "NL",
    "UNQUOTED_KEY",
    "array_table",
    "comment",
    "document",
    "dotted_key",
    "expression",
    "key",
    "key_value",
    "quoted_key",
    "simple_key",
    "standard_table",
    "string",
    "table",
    "unquoted_key",
    "value"
  ],
  "productions_gap": [
    "integer",
    "floating_point",
    "bool_",
    "date_time",
    "array_",
    "array_values",
    "comment_or_nl",
    "nl_or_comment",
    "inline_table",
    "inline_table_keyvals",
    "inline_table_keyvals_non_empty",
    "LITERAL_STRING",
    "BOOLEAN",
    "ML_BASIC_STRING",
    "ML_LITERAL_STRING",
    "FLOAT",
    "INF",
    "NAN",
    "DEC_INT",
    "HEX_INT",
    "OCT_INT",
    "BIN_INT",
    "OFFSET_DATE_TIME",
    "LOCAL_DATE_TIME",
    "LOCAL_DATE",
    "LOCAL_TIME"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 14,
  "divergences": 0,
  "divergence_examples": [],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **add_or_upweight_production** — integer.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.