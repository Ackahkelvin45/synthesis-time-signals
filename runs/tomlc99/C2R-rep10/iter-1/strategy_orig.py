from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

BARE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

# Raw control bytes that are NOT NUL (NUL would make the harness skip input).
CTRL_BYTES = [chr(c) for c in range(1, 9)] + [chr(11), chr(12)] + [chr(14, 32)[0]] if False else [
    chr(c) for c in range(1, 9)
] + [chr(11), chr(12)] + [chr(c) for c in range(14, 32)] + [chr(127)]

NON_ASCII = [
    "\u00e9", "\u00ff", "\u0100", "\u4e2d", "\u6587", "\u05d0", "\u0627",
    "\U0001F600", "\U0001F4A9", "\u2603", "\u00a0", "\u2028", "\u2029",
    "\u0080", "\u07ff", "\uffff", "\U0001F1E6",
]

ESCAPE_SEQS = [
    "\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u00e9", "\\uFFFF", "\\U0001F600", "\\U00000000",
    "\\u0041", "\\U0010FFFF",
]

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

unquoted_key = st.text(alphabet=BARE_CHARS, min_size=1, max_size=12)

basic_key_char = st.one_of(
    st.sampled_from(list("abcXYZ019_- .:/")),
    st.sampled_from(NON_ASCII),
    st.sampled_from(ESCAPE_SEQS),
    st.sampled_from(CTRL_BYTES),
)

literal_key_char = st.one_of(
    st.sampled_from(list("abcXYZ019_- .:/")),
    st.sampled_from(NON_ASCII),
    st.sampled_from(CTRL_BYTES),
)


@st.composite
def basic_quoted_key(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    body = draw(st.lists(basic_key_char, min_size=n, max_size=n))
    return '"' + "".join(body) + '"'


@st.composite
def literal_quoted_key(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    body = draw(st.lists(literal_key_char, min_size=n, max_size=n))
    return "'" + "".join(body) + "'"


simple_key = st.one_of(unquoted_key, basic_quoted_key(), literal_quoted_key())


@st.composite
def dotted_key(draw):
    n = draw(st.integers(min_value=2, max_value=4))
    parts = draw(st.lists(simple_key, min_size=n, max_size=n))
    return ".".join(parts)


key = st.one_of(simple_key, dotted_key())


# ---------------------------------------------------------------------------
# Strings (all four quoting forms, escapes, non-ASCII, control bytes)
# ---------------------------------------------------------------------------

basic_body_char = st.one_of(
    st.sampled_from(list("abcXYZ019 _-.,;:!?@#$%^&*()[]{}<>|~`")),
    st.sampled_from(NON_ASCII),
    st.sampled_from(ESCAPE_SEQS),
    st.sampled_from(CTRL_BYTES),
)

literal_body_char = st.one_of(
    st.sampled_from(list("abcXYZ019 _-.,;:!?@#$%^&*()[]{}<>|~`\"")),
    st.sampled_from(NON_ASCII),
    st.sampled_from(CTRL_BYTES),
)

ml_basic_body_char = st.one_of(
    basic_body_char,
    st.sampled_from(["\n", "\r\n", "\t"]),
)

ml_literal_body_char = st.one_of(
    literal_body_char,
    st.sampled_from(["\n", "\r\n", "\t"]),
)


@st.composite
def basic_string(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    body = draw(st.lists(basic_body_char, min_size=n, max_size=n))
    return '"' + "".join(body) + '"'


@st.composite
def literal_string(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    body = draw(st.lists(literal_body_char, min_size=n, max_size=n))
    return "'" + "".join(body) + "'"


@st.composite
def ml_basic_string(draw):
    n = draw(st.integers(min_value=0, max_value=10))
    body = draw(st.lists(ml_basic_body_char, min_size=n, max_size=n))
    return '"""' + "".join(body) + '"""'


@st.composite
def ml_literal_string(draw):
    n = draw(st.integers(min_value=0, max_value=10))
    body = draw(st.lists(ml_literal_body_char, min_size=n, max_size=n))
    return "'''" + "".join(body) + "'''"


string_value = st.one_of(
    basic_string(),
    literal_string(),
    ml_basic_string(),
    ml_literal_string(),
)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

dec_int_simple = st.one_of(
    st.integers(min_value=-10**3, max_value=10**3).map(str),
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.integers(min_value=-(2**70), max_value=2**70).map(str),
    st.sampled_from(["0", "-0", "+0", "007", "0000", "123456789012345678901234567890"]),
)

underscored_int = st.integers(min_value=1, max_value=10**18).map(
    lambda v: "{:,}".format(v).replace(",", "_")
)

dec_int = st.one_of(dec_int_simple, underscored_int)


def _hex_digits(n):
    return "".join("0123456789abcdef"[d] for d in n)


hex_int = st.integers(min_value=0, max_value=2**64).map(lambda v: "0x" + format(v, "x"))
oct_int = st.integers(min_value=0, max_value=2**40).map(lambda v: "0o" + format(v, "o"))
bin_int = st.integers(min_value=0, max_value=2**40).map(lambda v: "0b" + format(v, "b"))

hex_int_us = st.integers(min_value=1, max_value=2**32).map(
    lambda v: "0x" + "_".join(format(v, "x"))
)

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int, hex_int_us)


@st.composite
def float_value(draw):
    choice = draw(st.integers(min_value=0, max_value=6))
    if choice == 0:
        return draw(st.sampled_from(["inf", "+inf", "-inf"]))
    if choice == 1:
        return draw(st.sampled_from(["nan", "+nan", "-nan"]))
    if choice == 2:
        return draw(st.sampled_from(["1.", "0.", "-1.", "+2.", ".5", "-.5", "+.25"]))
    if choice == 3:
        mant = draw(st.integers(min_value=-10**6, max_value=10**6))
        frac = draw(st.integers(min_value=0, max_value=10**6))
        return "{}.{}".format(mant, frac)
    if choice == 4:
        mant = draw(st.integers(min_value=-10**3, max_value=10**3))
        exp = draw(st.integers(min_value=-400, max_value=400))
        return "{}e{}".format(mant, exp)
    if choice == 5:
        return draw(st.sampled_from(["1e309", "-1e309", "1E-400", "0e0", "1_000.5", "1.5e+10"]))
    mant = draw(st.integers(min_value=-10**3, max_value=10**3))
    frac = draw(st.integers(min_value=0, max_value=999))
    exp = draw(st.integers(min_value=-300, max_value=300))
    return "{}.{}e{}".format(mant, frac, exp)


# ---------------------------------------------------------------------------
# Booleans, date-times
# ---------------------------------------------------------------------------

bool_value = st.sampled_from(["true", "false"])

DATES = [
    "1979-05-27",
    "0000-00-00",
    "1979-02-30",
    "2024-12-31",
    "9999-99-99",
]

TIMES = [
    "07:32:00",
    "00:00:00",
    "23:59:59.999999",
    "12:34:56.1",
    "99:99:99",
]

OFFSETS = ["Z", "z", "+00:00", "-07:00", "+23:59", "-00:00"]


def _make_offset_dt(d, t, off):
    sep = "T"
    return "{}{}{}{}".format(d, sep, t, off)


offset_date_time = st.builds(
    _make_offset_dt,
    st.sampled_from(DATES),
    st.sampled_from(TIMES),
    st.sampled_from(OFFSETS),
)

local_date_time = st.builds(
    lambda d, t: "{}T{}".format(d, t),
    st.sampled_from(DATES),
    st.sampled_from(TIMES),
)

local_date = st.sampled_from(DATES)
local_time = st.sampled_from(TIMES)

date_time_value = st.one_of(
    offset_date_time, local_date_time, local_date, local_time
)


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _join_lines(parts):
    return "\n".join(parts)


@st.composite
def array_value(draw, value_strategy):
    depth = draw(st.integers(min_value=0, max_value=4))
    n = draw(st.integers(min_value=0, max_value=5))
    items = draw(st.lists(value_strategy, min_size=n, max_size=n))
    multiline = draw(st.booleans())
    if multiline and items:
        body = ",\n".join("  " + it for it in items)
        if draw(st.booleans()):
            body += ","
        return "[\n" + body + "\n]"
    else:
        body = ", ".join(items)
        if items and draw(st.booleans()):
            body += ","
        return "[" + body + "]"


@st.composite
def inline_table_value(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=4))
    pairs = []
    for _ in range(n):
        k = draw(key)
        v = draw(value_strategy)
        pairs.append("{} = {}".format(k, v))
    body = ", ".join(pairs)
    if pairs and draw(st.booleans()):
        body += ","
    return "{" + body + "}"


# ---------------------------------------------------------------------------
# Build the recursive value strategy
# ---------------------------------------------------------------------------

leaf_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value,
)

value_strategy = st.recursive(
    leaf_value,
    lambda children: st.one_of(
        array_value(children),
        inline_table_value(children),
    ),
    max_leaves=40,
)


# ---------------------------------------------------------------------------
# Key/value pairs, tables, documents
# ---------------------------------------------------------------------------

@st.composite
def key_value_line(draw):
    k = draw(key)
    v = draw(value_strategy)
    comment = draw(st.one_of(st.none(), st.just("# comment")))
    line = "{} = {}".format(k, v)
    if comment:
        line += "  " + comment
    return line


@st.composite
def standard_table(draw):
    k = draw(key)
    return "[{}]".format(k)


@st.composite
def array_table(draw):
    k = draw(key)
    return "[[{}]]".format(k)


table_line = st.one_of(standard_table(), array_table())


@st.composite
def document(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    lines = []
    for _ in range(n):
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            lines.append(draw(key_value_line()))
        elif kind == 1:
            lines.append(draw(table_line))
        elif kind == 2:
            lines.append("# comment only")
        else:
            lines.append("")
    text = "\n".join(lines)
    if draw(st.booleans()):
        text += "\n"
    return text


# ---------------------------------------------------------------------------
# Malformed / edge-case strategies
# ---------------------------------------------------------------------------

@st.composite
def malformed(draw):
    base = draw(document())
    kind = draw(st.integers(min_value=0, max_value=8))
    if kind == 0:
        # drop a closing bracket
        return base + "\nkey = [1, 2\n"
    if kind == 1:
        # doubled delimiter
        return base + "\nkey = [[1, 2]]\n"
    if kind == 2:
        # unterminated string
        return base + '\nkey = "unterminated\n'
    if kind == 3:
        # stray token
        return base + "\n@invalid = 1\n"
    if kind == 4:
        # missing equals
        return base + "\nkey 1\n"
    if kind == 5:
        # value on next line
        return base + "\nkey =\n1\n"
    if kind == 6:
        # duplicate key
        return base + "\na = 1\na = 2\n"
    if kind == 7:
        # newline inside inline table
        return base + "\na = {b = 1,\nc = 2}\n"
    if kind == 8:
        # invalid escape
        return base + '\na = "\\q"\n'
    return base


empty_or_comment_doc = st.one_of(
    st.just(""),
    st.just("\n"),
    st.just("# just a comment"),
    st.just("# c1\n# c2\n"),
)


deep_nesting = st.integers(min_value=1500, max_value=2048).map(
    lambda d: "a = " + "[" * d + "]" * d
)


edge_values = st.sampled_from([
    'a = ""',
    "a = ''",
    'a = """"""',
    "a = ''''''",
    'a = "\\u0000"',
    'a = "\\U0001F600"',
    'a = "x\x01y"',
    "a = 007",
    "a = 1.",
    "a = .5",
    "a = 1e309",
    "a = inf",
    "a = -inf",
    "a = nan",
    "a = 0xDEAD_BEEF",
    "a = 0o755",
    "a = 0b1010",
    "a = 1_000_000",
    "a = 9223372036854775808",
    "a = 1979-02-30",
    "a = 1979-05-27 07:32:00Z",
    "a = 1979-05-27T07:32:00",
    "a = 07:32:00",
    "a = []",
    "a = {}",
    "a = {b = 1,}",
    "[t]",
    "[[a]]",
    '"" = 1',
    "'literal key' = 1",
    "a.b.c = 1",
    "a = {b = {c = {d = 1}}}",
    "a = [[[[1]]]]",
])


@st.composite
def full_strategy(draw):
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind == 0:
        return draw(document())
    if kind == 1:
        return draw(malformed())
    if kind == 2:
        return draw(empty_or_comment_doc)
    if kind == 3:
        return draw(deep_nesting)
    if kind == 4:
        return draw(edge_values)
    if kind == 5:
        # multiple edge values joined
        n = draw(st.integers(min_value=1, max_value=6))
        return "\n".join(draw(st.lists(edge_values, min_size=n, max_size=n)))
    return draw(document())


strategy = full_strategy()