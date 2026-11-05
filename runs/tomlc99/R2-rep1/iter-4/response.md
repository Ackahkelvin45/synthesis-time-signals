```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character / atom helpers
# ---------------------------------------------------------------------------

# Characters that may appear raw inside a basic single-line string.
# Excludes NUL (harness skip), newline, backslash, double quote.
_basic_raw_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\\\"\n\r",
)

# Characters allowed raw in literal strings (no backslash escaping at all).
_literal_raw_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00'\n\r",
)

# Bare-key characters (ASCII only; non-ASCII bare keys are rejected).
_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

# Whitespace / control bytes we may sprinkle in strings and comments.
_control_chars = st.sampled_from(
    ["\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f", "\t"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_hex8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)


def _escape() -> st.SearchStrategy:
    simple = st.sampled_from([r"\"", r"\\", r"\/", r"\b", r"\f", r"\n", r"\r", r"\t"])
    uni = _hex4.map(lambda h: "\\u" + h)
    exuni = _hex8.map(lambda h: "\\U" + h)
    # Also the six-character escape for NUL, which is fine inside strings.
    nul = st.just("\\u0000")
    return st.one_of(simple, uni, exuni, nul)


def _basic_body(max_elems: int) -> st.SearchStrategy:
    piece = st.one_of(
        _basic_raw_chars,
        _control_chars,
        _escape(),
    )
    return st.lists(piece, min_size=0, max_size=max_elems).map("".join)


def _literal_body(max_elems: int) -> st.SearchStrategy:
    piece = st.one_of(_literal_raw_chars, _control_chars)
    return st.lists(piece, min_size=0, max_size=max_elems).map("".join)


# ---------------------------------------------------------------------------
# Strings (all four quoting forms)
# ---------------------------------------------------------------------------

def _string(max_elems: int = 12) -> st.SearchStrategy:
    basic = _basic_body(max_elems).map(lambda b: '"' + b + '"')
    literal = _literal_body(max_elems).map(lambda b: "'" + b + "'")

    # Multiline basic: content may include newlines, but not a bare """ run.
    ml_piece = st.one_of(
        st.characters(blacklist_categories=("Cs",), blacklist_characters='\x00"\\'),
        _control_chars,
        st.sampled_from(["\n", "\r\n"]),
        _escape(),
    )
    ml_basic = (
        st.lists(ml_piece, min_size=0, max_size=max_elems)
        .map("".join)
        .map(lambda b: '"""' + b + '"""')
    )

    # Multiline literal: raw content, no ''' run.
    ml_lit_piece = st.one_of(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00'"),
        _control_chars,
        st.sampled_from(["\n", "\r\n"]),
    )
    ml_literal = (
        st.lists(ml_lit_piece, min_size=0, max_size=max_elems)
        .map("".join)
        .map(lambda b: "'''" + b + "'''")
    )

    return st.one_of(basic, literal, ml_basic, ml_literal)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _dec_int() -> st.SearchStrategy:
    digits = st.text(alphabet="0123456789", min_size=1, max_size=20)
    # Underscore-grouped form.
    grouped = st.tuples(
        st.text(alphabet="123456789", min_size=1, max_size=1),
        st.lists(
            st.text(alphabet="0123456789", min_size=1, max_size=1),
            min_size=1,
            max_size=20,
        ),
    ).map(lambda t: t[0] + "".join(t[1]))
    grouped_us = st.tuples(
        st.text(alphabet="123456789", min_size=1, max_size=1),
        st.lists(
            st.text(alphabet="0123456789", min_size=1, max_size=1),
            min_size=1,
            max_size=20,
        ),
    ).map(lambda t: t[0] + "_" + "_".join(t[1]))
    body = st.one_of(digits, grouped, grouped_us)
    sign = st.sampled_from(["", "+", "-"])
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])


def _hex_int() -> st.SearchStrategy:
    d = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=16)
    grouped = st.lists(d, min_size=1, max_size=8).map(lambda xs: "_".join(xs))
    return st.one_of(d, grouped).map(lambda s: "0x" + s)


def _oct_int() -> st.SearchStrategy:
    d = st.text(alphabet="01234567", min_size=1, max_size=16)
    grouped = st.lists(d, min_size=1, max_size=8).map(lambda xs: "_".join(xs))
    return st.one_of(d, grouped).map(lambda s: "0o" + s)


def _bin_int() -> st.SearchStrategy:
    d = st.text(alphabet="01", min_size=1, max_size=32)
    grouped = st.lists(d, min_size=1, max_size=8).map(lambda xs: "_".join(xs))
    return st.one_of(d, grouped).map(lambda s: "0b" + s)


def _integer() -> st.SearchStrategy:
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())


def _float() -> st.SearchStrategy:
    frac = st.text(alphabet="0123456789", min_size=1, max_size=18)
    exp = st.one_of(
        st.text(alphabet="0123456789", min_size=1, max_size=4),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.text(alphabet="0123456789", min_size=1, max_size=4),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )
    # Various forms, including the lenient ones the parser accepts.
    forms = st.one_of(
        st.tuples(_dec_int(), st.just("."), frac).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(_dec_int(), st.just("."), frac, exp).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        ),
        st.tuples(st.just("."), frac).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("."), frac, exp).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(_dec_int(), st.just(".")).map(lambda t: t[0] + t[1]),
        st.tuples(_dec_int(), exp).map(lambda t: t[0] + t[1]),
    )
    inf_nan = st.one_of(
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )
    return st.one_of(forms, inf_nan)


# ---------------------------------------------------------------------------
# Dates / times
# ---------------------------------------------------------------------------

def _two() -> st.SearchStrategy:
    return st.text(alphabet="0123456789", min_size=2, max_size=2)


def _four() -> st.SearchStrategy:
    return st.text(alphabet="0123456789", min_size=4, max_size=4)


def _partial_time() -> st.SearchStrategy:
    secfrac = st.one_of(
        st.just(""),
        st.text(alphabet="0123456789", min_size=1, max_size=9).map(lambda s: "." + s),
    )
    return st.tuples(_two(), _two(), _two(), secfrac).map(
        lambda t: t[0] + ":" + t[1] + ":" + t[2] + t[3]
    )


def _full_date() -> st.SearchStrategy:
    return st.tuples(_four(), _two(), _two()).map(
        lambda t: t[0] + "-" + t[1] + "-" + t[2]
    )


def _offset() -> st.SearchStrategy:
    num = st.tuples(
        st.sampled_from(["+", "-"]), _two(), st.just(":"), _two()
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])
    return st.one_of(st.just("Z"), num)


def _date_time() -> st.SearchStrategy:
    delim = st.sampled_from(["T", "t", " "])
    offset_dt = st.tuples(_full_date(), delim, _partial_time(), _offset()).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )
    local_dt = st.tuples(_full_date(), delim, _partial_time()).map(
        lambda t: t[0] + t[1] + t[2]
    )
    return st.one_of(offset_dt, local_dt, _full_date(), _partial_time())


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _unquoted_key() -> st.SearchStrategy:
    return st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)


def _quoted_key() -> st.SearchStrategy:
    # Empty quoted key is legal.
    basic = _basic_body(6).map(lambda b: '"' + b + '"')
    literal = _literal_body(6).map(lambda b: "'" + b + "'")
    return st.one_of(basic, literal)


def _simple_key() -> st.SearchStrategy:
    return st.one_of(_unquoted_key(), _quoted_key())


def _key() -> st.SearchStrategy:
    dotted = st.lists(_simple_key(), min_size=2, max_size=4).map(
        lambda xs: ".".join(xs)
    )
    return st.one_of(_simple_key(), dotted)


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _scalar_value() -> st.SearchStrategy:
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        st.sampled_from(["true", "false"]),
        _date_time(),
    )


def _value(depth_band: int = 2048) -> st.SearchStrategy:
    # Recursive production: arrays and inline tables nest.
    def extend(children: st.SearchStrategy) -> st.SearchStrategy:
        # Array: elements may be values; allow empty, trailing comma, newlines,
        # comments, mixed types.
        array = st.one_of(
            st.just("[]"),
            st.tuples(
                st.lists(children, min_size=1, max_size=4),
                st.sampled_from(["", ","]),
            ).map(lambda t: "[" + ", ".join(t[0]) + t[1] + "]"),
            st.tuples(
                st.lists(children, min_size=1, max_size=3),
                st.sampled_from(["\n", "\n# c\n", "\r\n"]),
            ).map(lambda t: "[" + ",\n".join(t[0]) + t[1] + "]"),
        )

        # Inline table: key = value pairs. Allow empty and trailing comma.
        pair = st.tuples(_key(), children).map(lambda t: t[0] + " = " + t[1])
        inline = st.one_of(
            st.just("{}"),
            st.tuples(
                st.lists(pair, min_size=1, max_size=3),
                st.sampled_from(["", ","]),
            ).map(lambda t: "{" + ", ".join(t[0]) + t[1] + "}"),
        )
        return st.one_of(array, inline)

    return st.recursive(_scalar_value(), extend, max_leaves=6)


# ---------------------------------------------------------------------------
# Malformed / near-valid mutations
# ---------------------------------------------------------------------------

def _malformed() -> st.SearchStrategy:
    # Build small valid fragments then break one delimiter.
    valid = st.one_of(
        _string(max_elems=4),
        _integer(),
        _float(),
        _date_time(),
        st.just("true"),
        st.just("false"),
        st.just("[]"),
        st.just("{}"),
        st.just("[1, 2]"),
        st.just("{a = 1}"),
    )

    def mutate(v: str) -> str:
        return v

    missing = valid.map(lambda v: v[:-1] if v else v)
    doubled = valid.map(lambda v: v + v[-1:] if v else v)
    unterminated = st.one_of(
        _basic_body(5).map(lambda b: '"' + b),
        _literal_body(5).map(lambda b: "'" + b),
        st.text(alphabet="abc ", min_size=1, max_size=5).map(lambda s: '"""' + s),
    )
    stray = st.sampled_from(
        ["=", "]", "}", ",", "[[", "]]", "[", "{", ".", "=", "#x"]
    )
    return st.one_of(missing, doubled, unterminated, stray)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _comment() -> st.SearchStrategy:
    body = st.lists(
        st.one_of(
            st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00\n\r"),
            _control_chars,
        ),
        min_size=0,
        max_size=10,
    ).map("".join)
    return body.map(lambda b: "#" + b)


def _key_value_line(value: st.SearchStrategy) -> st.SearchStrategy:
    return st.tuples(_key(), value, st.one_of(st.just(""), _comment())).map(
        lambda t: t[0] + " = " + t[1] + (" " + t[2] if t[2] else "")
    )


def _table_header() -> st.SearchStrategy:
    std = _key().map(lambda k: "[" + k + "]")
    arr = _key().map(lambda k: "[[" + k + "]]")
    return st.one_of(std, arr)


def _line(value: st.SearchStrategy) -> st.SearchStrategy:
    return st.one_of(
        _key_value_line(value),
        _table_header(),
        _comment(),
        st.just(""),
    )


@st.composite
def _document(draw) -> str:
    value = _value()
    lines = draw(st.lists(_line(value), min_size=0, max_size=8))
    # Occasionally append a malformed token line.
    if draw(st.booleans()):
        lines.append(draw(_malformed()))
    nl = draw(st.sampled_from(["\n", "\r\n"]))
    doc = nl.join(lines)
    # Sometimes no trailing newline.
    if draw(st.booleans()):
        doc += nl
    return doc


def _deep_nesting() -> st.SearchStrategy:
    # Concentrate in the interesting depth band (1500-2048), but keep it
    # bounded so tests remain fast; a single level is just brackets.
    depth = st.integers(min_value=1, max_value=64)

    def build(d: int) -> str:
        return "[" * d + "1" + "]" * d

    return depth.map(build)


def _nested_doc() -> st.SearchStrategy:
    return st.tuples(
        _deep_nesting(),
        _key(),
    ).map(lambda t: t[1] + " = " + t[0])


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

# A small set of fully-formed, realistic documents. These exercise the
# happy-path parser branches (table headers, arrays of tables, nested
# dotted keys, inline tables, multiline strings, comments and blank
# lines) that random assembly rarely hits together. Coverage feedback
# showed region/branch coverage stuck below half, largely because the
# random documents seldom produced coherent multi-line structure.
def _realistic_doc() -> st.SearchStrategy:
    return st.sampled_from(
        [
            # Simple keys and values.
            'title = "TOML Example"\n'
            'enabled = true\n'
            'count = 42\n'
            'pi = 3.14159\n'
            'date = 1979-05-27T07:32:00Z\n',

            # Tables and nested tables.
            '[owner]\n'
            'name = "Tom"\n'
            'dob = 1979-05-27T07:32:00-08:00\n'
            '\n'
            '[owner.address]\n'
            'city = "San Francisco"\n'
            'zip = 94110\n',

            # Array of tables.
            '[[products]]\n'
            'name = "Hammer"\n'
            'sku = 738594937\n'
            '\n'
            '[[products]]\n'
            'name = "Nail"\n'
            'sku = 284758393\n'
            'color = "gray"\n',

            # Arrays, inline tables, mixed.
            'ports = [ 8001, 8001, 8002 ]\n'
            'data = [ ["delta", "phi"], [3.14] ]\n'
            'point = { x = 1, y = 2 }\n'
            'animals = { type.name = "pug" }\n',

            # Multiline strings and comments.
            'str1 = """\n'
            'Roses are red\n'
            'Violets are blue"""\n'
            '# a comment\n'
            "str2 = '''\n"
            "line one\n"
            "line two'''\n",

            # Dotted keys and quoted keys.
            'physical.color = "orange"\n'
            'physical.shape = "round"\n'
            'site."google.com" = true\n',

            # Whitespace / blank lines / comments interleaved.
            '\n'
            '# leading comment\n'
            'key = "value"  # trailing comment\n'
            '\n'
            '[section]\n'
            '  indented = 1\n'
            '  other = 2\n',
        ]
    )


# Structured documents that deliberately combine many grammar features
# (tables, arrays-of-tables, dotted keys, inline tables, all string forms,
# comments, blank lines) so the parser's happy-path branches are exercised
# together rather than piecemeal. This targets the region/branch coverage
# gap left by purely random assembly.
@st.composite
def _structured_doc(draw) -> str:
    nl = draw(st.sampled_from(["\n", "\r\n"]))
    parts = []

    # A leading comment / blank line region.
    if draw(st.booleans()):
        parts.append(draw(_comment()))
    if draw(st.booleans()):
        parts.append("")

    # Top-level key/value pairs, including dotted keys.
    root_pairs = []
    for _ in range(draw(st.integers(min_value=0, max_value=4))):
        root_pairs.append(draw(_key_value_line(_value())))
    parts.extend(root_pairs)

    # A few table sections with their own key/value lines.
    n_tables = draw(st.integers(min_value=0, max_value=3))
    for _ in range(n_tables):
        header = draw(_table_header())
        parts.append(header)
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            parts.append(draw(_key_value_line(_value())))
        if draw(st.booleans()):
            parts.append("")

    doc = nl.join(parts)
    if draw(st.booleans()):
        doc += nl
    return doc


# Focused strategies that hammer particular grammar corners so coverage
# feedback can reach branches random assembly under-samples.
def _string_zoo() -> st.SearchStrategy:
    return st.tuples(
        _key(),
        st.one_of(
            _string(max_elems=8),
            _string(max_elems=8),
            st.just('""'),
            st.just("''"),
            st.just('""""""'),
            st.just("''''''"),
        ),
    ).map(lambda t: t[0] + " = " + t[1])


def _number_zoo() -> st.SearchStrategy:
    return st.tuples(
        _key(),
        st.one_of(
            _dec_int(),
            _hex_int(),
            _oct_int(),
            _bin_int(),
            _float(),
            st.sampled_from(["0", "-0", "+0", "0.0", "-0.0", "1e10", "1E-10"]),
        ),
    ).map(lambda t: t[0] + " = " + t[1])


def _datetime_zoo() -> st.SearchStrategy:
    return st.tuples(
        _key(),
        st.one_of(
            _full_date(),
            _partial_time(),
            _date_time(),
            st.sampled_from(
                [
                    "1979-05-27T07:32:00Z",
                    "1979-05-27T00:32:00-07:00",
                    "1979-05-27T00:32:00.999999-07:00",
                    "1979-05-27 07:32:00Z",
                    "07:32:00",
                    "00:32:00.999999",
                ]
            ),
        ),
    ).map(lambda t: t[0] + " = " + t[1])


def _table_zoo() -> st.SearchStrategy:
    return st.one_of(
        _key().map(lambda k: "[" + k + "]" + "\n" + k + " = 1"),
        _key().map(lambda k: "[[" + k + "]]" + "\n" + k + " = 1"),
        _key().map(lambda k: "[" + k + "]\n[" + k + ".sub]\nx = 1"),
        _key().map(lambda k: "[[a]]\n[[a]]\n[[a]]"),
        st.just("[a.b.c]\nx = 1"),
        st.just("[[fruit]]\nname = \"apple\"\n[fruit.physical]\ncolor = \"red\""),
    )


def _inline_zoo() -> st.SearchStrategy:
    return st.tuples(
        _key(),
        st.one_of(
            _value(),
            st.just("{}"),
            st.just("{ a = 1 }"),
            st.just("{ a = 1, b = 2 }"),
            st.just("{ a.b = 1 }"),
            st.just("[ ]"),
            st.just("[1, 2, 3]"),
            st.just("[ [1], [2] ]"),
            st.just("[1,]"),
        ),
    ).map(lambda t: t[0] + " = " + t[1])


def _comment_zoo() -> st.SearchStrategy:
    return st.one_of(
        _comment(),
        st.just("#"),
        st.just("# "),
        st.just("key = 1 # trailing"),
        st.just("#\n#\n#"),
        st.just("\n\n\n"),
        st.just("\r\n\r\n"),
    )


strategy = st.one_of(
    _realistic_doc(),
    _structured_doc(),
    _document(),
    _nested_doc(),
    _key_value_line(_value()),
    _malformed(),
    _string_zoo(),
    _number_zoo(),
    _datetime_zoo(),
    _table_zoo(),
    _inline_zoo(),
    _comment_zoo(),
)
```