Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Characters that are safe inside strings (no raw NUL).
_SAFE_CHARS = [chr(c) for c in range(0x20, 0x7F)] + [
    "\t", "\r", "\n",
    "\x01", "\x02", "\x07", "\x0b", "\x0c", "\x1b", "\x7f",
    "\u00e9", "\u00ff", "\u0100", "\u4e2d", "\u6587", "\U0001f600",
]

_basic_esc = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)


@st.composite
def _unicode_escape(draw):
    kind = draw(st.sampled_from(["u", "U"]))
    n = 4 if kind == "u" else 8
    digits = draw(st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n))
    return "\\" + kind + digits


@st.composite
def _basic_string_body(draw, allow_ml):
    n = draw(st.integers(min_value=0, max_value=12))
    parts = []
    for _ in range(n):
        choice = draw(st.integers(min_value=0, max_value=2))
        if choice == 0:
            parts.append(draw(st.sampled_from(_SAFE_CHARS)))
        elif choice == 1:
            parts.append(draw(_basic_esc))
        else:
            parts.append(draw(_unicode_escape()))
    return "".join(parts)


@st.composite
def _basic_string(draw):
    body = draw(_basic_string_body(allow_ml=False))
    return '"' + body + '"'


@st.composite
def _literal_string(draw):
    n = draw(st.integers(min_value=0, max_value=12))
    chars = []
    for _ in range(n):
        c = draw(st.sampled_from(_SAFE_CHARS))
        if c == "'":
            c = "x"
        chars.append(c)
    return "'" + "".join(chars) + "'"


@st.composite
def _ml_basic_string(draw):
    body = draw(_basic_string_body(allow_ml=True))
    return '"""' + body + '"""'


@st.composite
def _ml_literal_string(draw):
    n = draw(st.integers(min_value=0, max_value=12))
    chars = []
    for _ in range(n):
        c = draw(st.sampled_from(_SAFE_CHARS))
        chars.append(c)
    body = "".join(chars)
    body = body.replace("'''", "''")
    return "'''" + body + "'''"


@st.composite
def _string(draw):
    return draw(st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    ))


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-10**25, max_value=10**25).map(str),
    st.sampled_from(["0", "+0", "-0", "007", "000", "1_000", "9_999_999",
                     "9223372036854775807", "-9223372036854775808",
                     "99999999999999999999999999999999",
                     "-99999999999999999999999999999999"]),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "+" + str(n)),
)


@st.composite
def _hex_int(draw):
    n = draw(st.integers(min_value=1, max_value=20))
    digits = draw(st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n))
    if draw(st.booleans()):
        digits = "_".join(digits)
    return "0x" + digits


@st.composite
def _oct_int(draw):
    n = draw(st.integers(min_value=1, max_value=20))
    digits = draw(st.text(alphabet="01234567", min_size=n, max_size=n))
    if draw(st.booleans()):
        digits = "_".join(digits)
    return "0o" + digits


@st.composite
def _bin_int(draw):
    n = draw(st.integers(min_value=1, max_value=20))
    digits = draw(st.text(alphabet="01", min_size=n, max_size=n))
    if draw(st.booleans()):
        digits = "_".join(digits)
    return "0b" + digits


_int = st.one_of(_dec_int, _hex_int(), _oct_int(), _bin_int())


@st.composite
def _float(draw):
    choice = draw(st.integers(min_value=0, max_value=5))
    if choice == 0:
        return draw(st.sampled_from([
            "inf", "+inf", "-inf", "nan", "+nan", "-nan",
            "1e309", "-1e309", "1e-309", "0.0", "-0.0",
            "1.", ".5", "1_000.000_1", "3.14159",
            "1e6", "1E6", "1e+6", "1e-6", "6.626e-34",
            "1.7976931348623157e308",
        ]))
    if choice == 1:
        return draw(st.integers(min_value=-10**6, max_value=10**6).map(
            lambda n: "{}.{}".format(n, abs(n) % 1000)))
    if choice == 2:
        return draw(st.integers(min_value=-10**6, max_value=10**6).map(
            lambda n: "{}.e{}".format(n, n % 30)))
    if choice == 3:
        return draw(st.integers(min_value=-10**6, max_value=10**6).map(
            lambda n: "{}e{}".format(n, n % 30)))
    if choice == 4:
        return draw(st.sampled_from([".5", "1.", "-.5", "+.5", "1.e5"]))
    return draw(st.sampled_from(["0.0", "0e0", "1e0"]))


# ---------------------------------------------------------------------------
# Booleans, dates
# ---------------------------------------------------------------------------

_bool = st.sampled_from(["true", "false"])

_date = st.one_of(
    st.sampled_from([
        "1979-05-27", "1979-05-27T07:32:00Z",
        "1979-05-27T07:32:00", "1979-05-27 07:32:00Z",
        "1979-05-27 07:32:00", "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27T00:32:00+07:00", "1979-05-27T00:32:00-07:00",
        "07:32:00", "00:32:00.999999", "1979-02-30",
        "1979-05-27t07:32:00z", "1979-05-27T07:32:00z",
    ]),
    st.builds(
        lambda y, mo, d, h, mi, s: "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
            y, mo, d, h, mi, s),
        st.integers(min_value=0, max_value=9999),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ),
    st.builds(
        lambda h, mi, s: "{:02d}:{:02d}:{:02d}".format(h, mi, s),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
)

_unquoted_key = st.text(alphabet=_unquoted_char, min_size=1, max_size=12)

_quoted_key = st.one_of(_basic_string(), _literal_string())

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key, st.just('""'))


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _value_strat(value):
    """Build the value strategy given the recursive value strategy."""
    scalar = st.one_of(
        _string(),
        _int,
        _float(),
        _bool,
        _date,
    )

    @st.composite
    def _array(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        items = [draw(value) for _ in range(n)]
        if not items:
            return "[]"
        sep = draw(st.sampled_from([", ", ",\n", ",", " , ", ",\n# c\n"]))
        body = sep.join(items)
        trailing = draw(st.sampled_from(["", ",", ",\n"]))
        return "[" + body + trailing + "]"

    @st.composite
    def _inline_table(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        pairs = []
        used = set()
        for _ in range(n):
            k = draw(_key)
            if k in used:
                continue
            used.add(k)
            v = draw(value)
            pairs.append("{} = {}".format(k, v))
        if not pairs:
            return "{}"
        sep = draw(st.sampled_from([", ", ","]))
        trailing = draw(st.sampled_from(["", ","]))
        return "{" + sep.join(pairs) + trailing + "}"

    return st.one_of(scalar, _array(), _inline_table())


# Build the recursive value strategy with a bounded depth.
_value = st.recursive(
    _value_strat(st.nothing()),
    lambda inner: _value_strat(inner),
    max_leaves=40,
)


# ---------------------------------------------------------------------------
# Deep nesting generators (arrays / inline tables) in the 1500-2048 band
# ---------------------------------------------------------------------------

@st.composite
def _deep_array(draw):
    depth = draw(st.integers(min_value=1500, max_value=2048))
    inner = draw(st.one_of(_int, _string(), _bool))
    return "[" * depth + inner + "]" * depth


@st.composite
def _deep_inline_table(draw):
    depth = draw(st.integers(min_value=1500, max_value=2048))
    inner = draw(st.one_of(_int, _string(), _bool))
    # nested inline tables: a = {a = {a = ... = v}}
    return "{" + "a = {" * (depth - 1) + "a = " + inner + "}" * depth


# ---------------------------------------------------------------------------
# Key/value lines, tables, arrays of tables
# ---------------------------------------------------------------------------

_kv_line = st.builds(
    lambda k, v: "{} = {}".format(k, v),
    _key,
    _value,
)

_std_table = st.builds(
    lambda k: "[{}]".format(k),
    _key,
)

_array_table = st.builds(
    lambda k: "[[{}]]".format(k),
    _key,
)

_comment = st.one_of(
    st.just("#"),
    st.text(alphabet=_SAFE_CHARS, max_size=20).map(lambda s: "# " + s),
)


@st.composite
def _document(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    lines = []
    for _ in range(n):
        choice = draw(st.integers(min_value=0, max_value=5))
        if choice == 0:
            lines.append(draw(_comment))
        elif choice == 1:
            lines.append(draw(_std_table))
        elif choice == 2:
            lines.append(draw(_array_table))
        elif choice == 3:
            lines.append(draw(_kv_line))
        elif choice == 4:
            lines.append("")
        else:
            lines.append(draw(_kv_line))
    nl = draw(st.sampled_from(["\n", "\r\n"]))
    doc = nl.join(lines)
    if draw(st.booleans()):
        doc += nl
    return doc


# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

@st.composite
def _malformed(draw):
    kind = draw(st.integers(min_value=0, max_value=12))
    if kind == 0:
        return draw(_key) + " = " + draw(_value) + draw(st.sampled_from(["", "x", "="]))
    if kind == 1:
        # unterminated basic string
        return draw(_key) + ' = "unterminated'
    if kind == 2:
        # unterminated literal string
        return draw(_key) + " = 'unterminated"
    if kind == 3:
        # missing bracket
        return "[" + draw(_key)
    if kind == 4:
        # doubled bracket
        return "[" + draw(_key) + "]]"
    if kind == 5:
        # stray token
        return draw(st.sampled_from(["= 1", "]", "}", ",", ".", "[[", "]]", "="]))
    if kind == 6:
        # newline inside inline table
        return draw(_key) + " = {a = 1,\nb = 2}"
    if kind == 7:
        # invalid escape
        return draw(_key) + ' = "bad \\q escape"'
    if kind == 8:
        # value on next line
        return draw(_key) + " =\n1"
    if kind == 9:
        # duplicate key
        k = draw(_key)
        return "{} = 1\n{} = 2".format(k, k)
    if kind == 10:
        # non-ascii bare key
        return "caf\u00e9 = 1"
    if kind == 11:
        # unterminated array
        return draw(_key) + " = [1, 2"
    # unterminated inline table
    return draw(_key) + " = {a = 1"


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

@st.composite
def _root(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        return draw(_document())
    if choice == 1:
        return draw(_deep_array())
    if choice == 2:
        return draw(_deep_inline_table())
    if choice == 3:
        return draw(_malformed())
    if choice == 4:
        # empty document
        return draw(st.sampled_from(["", "\n", "\r\n", "# only comment"]))
    if choice == 5:
        # embedded control bytes / non-ascii text in strings
        return draw(_key) + " = " + draw(_basic_string())
    if choice == 6:
        # extreme numbers
        return "big = " + draw(st.sampled_from(
            ["1e309", "-1e309", "1e-309", "99999999999999999999999999999999"]))
    if choice == 7:
        # all four quoting forms
        return "a = {}\nb = {}\nc = {}\nd = {}".format(
            draw(_basic_string()),
            draw(_literal_string()),
            draw(_ml_basic_string()),
            draw(_ml_literal_string()),
        )
    if choice == 8:
        # duplicate tables
        k = draw(_key)
        return "[{}]\na = 1\n[{}]\nb = 2".format(k, k)
    # complete document with mixed content
    return draw(_document())


# ---------------------------------------------------------------------------
# Structured, semantically-richer documents (improved coverage)
# ---------------------------------------------------------------------------

@st.composite
def _structured_document(draw):
    """Generate a coherent document with related keys, tables of tables,
    arrays of tables, dotted keys, and matching value types."""
    simple_key = st.text(alphabet=_unquoted_char, min_size=1, max_size=8)
    keys = draw(st.lists(simple_key, min_size=1, max_size=5, unique=True))
    lines = []
    for k in keys:
        form = draw(st.integers(min_value=0, max_value=4))
        if form == 0:
            lines.append("{} = {}".format(k, draw(_value)))
        elif form == 1:
            lines.append("[{}]".format(k))
            for sub in draw(st.lists(simple_key, min_size=0, max_size=3, unique=True)):
                lines.append("{} = {}".format(sub, draw(_value)))
        elif form == 2:
            lines.append("[[{}]]".format(k))
            for sub in draw(st.lists(simple_key, min_size=0, max_size=2, unique=True)):
                lines.append("{} = {}".format(sub, draw(_value)))
        elif form == 3:
            # dotted key
            sub = draw(simple_key)
            lines.append("{}.{} = {}".format(k, sub, draw(_value)))
        else:
            # table with dotted name
            sub = draw(simple_key)
            lines.append("[{}.{}]".format(k, sub))
            lines.append("{} = {}".format(draw(simple_key), draw(_value)))
    nl = draw(st.sampled_from(["\n", "\r\n"]))
    doc = nl.join(lines)
    if draw(st.booleans()):
        doc += nl
    return doc


@st.composite
def _root2(draw):
    choice = draw(st.integers(min_value=0, max_value=4))
    if choice == 0:
        return draw(_structured_document())
    if choice == 1:
        # multiple documents concatenated (stress parser state)
        parts = [draw(_structured_document()) for _ in range(draw(st.integers(1, 3)))]
        return "\n".join(parts)
    if choice == 2:
        # long flat array / table with many entries
        n = draw(st.integers(min_value=1, max_value=200))
        items = [draw(_int) for _ in range(n)]
        return "long = [" + ", ".join(items) + "]"
    if choice == 3:
        # many keys
        n = draw(st.integers(min_value=1, max_value=200))
        lines = ["k{} = {}".format(i, draw(_value)) for i in range(n)]
        return "\n".join(lines)
    # deeply nested but bounded arrays with mixed content
    depth = draw(st.integers(min_value=1, max_value=64))
    inner = draw(_value)
    return "[" * depth + inner + "]" * depth


strategy = st.one_of(_root(), _root2())
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.