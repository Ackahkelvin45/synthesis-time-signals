from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic building blocks
# ---------------------------------------------------------------------------

# Characters safe to use inside strings (no raw NUL).
_SAFE_CHARS = st.characters(
    blacklist_categories=(), blacklist_characters="\x00"
)

# Printable-ish text for keys and simple content.
_TEXT = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs", "Cc"),
        blacklist_characters="\x00",
    ),
    min_size=0,
    max_size=12,
)

# Characters allowed in bare keys.
_BARE_KEY_CHAR = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)

_BARE_KEY = st.text(_BARE_KEY_CHAR, min_size=1, max_size=20)


def _escape_seq():
    simple = st.sampled_from(list('"\\/bfnrt'))
    uni = st.integers(0, 0x10FFFF).map(lambda n: "u%04X" % (n & 0xFFFF))
    uni8 = st.integers(0, 0x10FFFF).map(lambda n: "U%08X" % n)
    # Include the NUL escape explicitly, plus raw control bytes as text chars.
    return st.one_of(
        simple.map(lambda c: "\\" + c),
        uni.map(lambda s: "\\" + s),
        uni8.map(lambda s: "\\" + s),
        st.just("\\u0000"),
        st.just("\\U00000000"),
    )


# A basic-string body: mixture of plain chars and escapes.
def _basic_body(max_size=24):
    plain = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\x00',
        ),
        max_size=max_size,
    )
    return st.lists(
        st.one_of(plain, _escape_seq()),
        max_size=6,
    ).map("".join)


_BASIC_STRING = _basic_body().map(lambda s: '"' + s + '"')

_LITERAL_BODY = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="'\x00",
    ),
    max_size=24,
)
_LITERAL_STRING = _LITERAL_BODY.map(lambda s: "'" + s + "'")

# Multiline strings: bodies may contain newlines. Avoid the closing delimiter.
_ML_BASIC_BODY = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
    max_size=40,
).filter(lambda s: '"""' not in s)
_ML_BASIC_STRING = _ML_BASIC_BODY.map(lambda s: '"""' + s + '"""')

_ML_LITERAL_BODY = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
    max_size=40,
).filter(lambda s: "'''" not in s)
_ML_LITERAL_STRING = _ML_LITERAL_BODY.map(lambda s: "'''" + s + "'''")

_STRING = st.one_of(
    _BASIC_STRING,
    _LITERAL_STRING,
    _ML_BASIC_STRING,
    _ML_LITERAL_STRING,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_DEC_INT = st.one_of(
    st.integers(-(2**80), 2**80).map(str),
    st.just("0"),
    st.just("007"),
    st.just("-0"),
    st.just("+42"),
    st.just("1_000_000"),
    st.just("9223372036854775807"),
    st.just("9223372036854775808"),
    st.just("-9223372036854775809"),
)

_HEX_INT = st.one_of(
    st.integers(0, 2**64).map(lambda n: "0x%X" % n),
    st.just("0xDEAD_BEEF"),
    st.just("0x0"),
    st.just("0xFF_FF"),
)

_OCT_INT = st.one_of(
    st.integers(0, 2**32).map(lambda n: "0o%o" % n),
    st.just("0o0"),
    st.just("0o7_7_7"),
)

_BIN_INT = st.one_of(
    st.integers(0, 2**32).map(lambda n: "0b" + bin(n)[2:]),
    st.just("0b0"),
    st.just("0b1_0_1"),
)

_INTEGER = st.one_of(_DEC_INT, _HEX_INT, _OCT_INT, _BIN_INT)

_FLOAT = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.just("1."),
    st.just(".5"),
    st.just("3.14159"),
    st.just("1e10"),
    st.just("1E-10"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("6.626e-34"),
    st.just("1_000.000_1"),
    st.just("inf"),
    st.just("-inf"),
    st.just("+inf"),
    st.just("nan"),
    st.just("-nan"),
    st.just("+nan"),
)

_BOOL = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Date-times
# ---------------------------------------------------------------------------

_DATE = st.builds(
    lambda y, m, d: "%04d-%02d-%02d" % (y, m, d),
    st.integers(0, 9999),
    st.integers(0, 99),
    st.integers(0, 99),
)

_TIME = st.builds(
    lambda h, mi, s: "%02d:%02d:%02d" % (h, mi, s),
    st.integers(0, 99),
    st.integers(0, 99),
    st.integers(0, 99),
)

_OFFSET = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.builds(
        lambda sign, h, m: "%s%02d:%02d" % (sign, h, m),
        st.sampled_from(["+", "-"]),
        st.integers(0, 99),
        st.integers(0, 99),
    ),
)

_OFFSET_DATETIME = st.builds(
    lambda d, sep, t, o: d + sep + t + o,
    _DATE,
    st.sampled_from(["T", "t", " "]),
    _TIME,
    _OFFSET,
)

_LOCAL_DATETIME = st.builds(
    lambda d, sep, t: d + sep + t,
    _DATE,
    st.sampled_from(["T", "t", " "]),
    _TIME,
)

_LOCAL_TIME = _TIME

_DATETIME = st.one_of(
    _OFFSET_DATETIME,
    _LOCAL_DATETIME,
    _DATE,
    _LOCAL_TIME,
    st.just("1979-02-30"),
    st.just("1979-05-27 07:32:00Z"),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_QUOTED_KEY = st.one_of(_BASIC_STRING, _LITERAL_STRING)

_SIMPLE_KEY = st.one_of(_BARE_KEY, _QUOTED_KEY, st.just('""'))

_DOTTED_KEY = st.lists(_SIMPLE_KEY, min_size=2, max_size=4).map(".".join)

_KEY = st.one_of(_SIMPLE_KEY, _DOTTED_KEY)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# Leaf values (non-recursive).
_LEAF_VALUE = st.one_of(
    _STRING,
    _INTEGER,
    _FLOAT,
    _BOOL,
    _DATETIME,
)

# We build value strategy via st.recursive so nesting is genuine.
# Depth band: concentrate on up to ~2048 levels; Hypothesis recursive
# naturally grows depth with size, and we add explicit deep-nesting cases.

def _array_of(value):
    # Arrays may contain values, newlines, comments, and trailing commas.
    inner = st.lists(
        st.one_of(
            value,
            st.just(""),
        ),
        max_size=6,
    ).map(lambda items: ", ".join(items))
    return st.builds(
        lambda body: "[" + body + "]",
        inner,
    )


def _inline_table_of(value):
    def _kv():
        return st.builds(
            lambda k, v: k + " = " + v,
            _KEY,
            value,
        )

    inner = st.lists(_kv(), max_size=4).map(lambda kvs: ", ".join(kvs))
    return st.builds(lambda body: "{" + body + "}", inner)


_value = st.recursive(
    _LEAF_VALUE,
    lambda children: st.one_of(
        _array_of(children),
        _inline_table_of(children),
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Deep nesting band (1500-2048) plus empty containers and edge cases
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "1" + "]" * depth


def _deep_inline(depth):
    return "{" + "a = " * depth + "1" + "}" * depth


_DEEP = st.integers(1500, 2048).flatmap(
    lambda d: st.one_of(
        st.just(_deep_array(d)),
        st.just(_deep_inline(d)),
    )
)

_EMPTY_CONTAINERS = st.sampled_from(
    ["[]", "{}", "[[]]", "[[a]]", "[a]", "[a.b]", '[a."b"]']
)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from(
    [
        # missing / doubled delimiters
        'a = [1, 2',
        "a = [1, 2]]",
        "a = {b = 1",
        "a = {b = 1}}",
        "a = [",
        "a = ]",
        "a = {",
        "a = }",
        "[a",
        "[[a]",
        "[[a]]]",
        # unterminated strings
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        # stray token
        "a = = 1",
        "a 1",
        "= 1",
        "a =",
        "a = \n1",
        # invalid escape
        'a = "\\q"',
        # newline inside inline table
        "a = {b = 1,\nc = 2}",
        # duplicate keys / tables
        "a = 1\na = 2",
        "[t]\n[t]",
        "[t]\n[[t]]",
        # non-ASCII bare key
        "caf\u00e9 = 1",
        "missing =",
        # dotted key redefining table
        "[a.b]\n[a]\nb.c = 1",
    ]
)

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _key_value():
    return st.builds(
        lambda k, v: k + " = " + v,
        _KEY,
        _value,
    )


def _comment():
    return st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\x00\n",
        ),
        max_size=20,
    ).map(lambda s: "# " + s if s else "#")


def _standard_table():
    return st.builds(lambda k: "[" + k + "]", _KEY)


def _array_table():
    return st.builds(lambda k: "[[" + k + "]]", _KEY)


_LINE = st.one_of(
    _key_value(),
    _comment(),
    _standard_table(),
    _array_table(),
    st.just(""),
)

_DOCUMENT = st.lists(_LINE, min_size=0, max_size=8).map("\n".join)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _DOCUMENT,
    _DEEP,
    _EMPTY_CONTAINERS,
    _MALFORMED,
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("[t]\n"),
    st.just("[[a]]\n"),
    st.just('"" = 1'),
    st.just("a = 1979-05-27 07:32:00Z"),
    st.just("a = 1_000"),
    st.just("a = 0xDEAD_BEEF"),
    st.just("a = 0o777"),
    st.just("a = 0b1010"),
    st.just("a = inf\na = nan"),
    st.just("a = 1e309"),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just('a = "x\x01y"'),
    st.just("a = {b = 1,}"),
    st.just("a = 1979-02-30"),
    st.just("a = [1, 2, 3,]"),
    st.just("a = [\n  1,\n  # c\n  2\n]"),
    st.just('a = "\\u0000"'),
    st.just('a = "\\U0001F600"'),
    st.just("a = '''\nraw\n'''"),
    st.just('a = """\nml\n"""'),
    st.just("a = \r\n"),
    st.just("\t[a]\r\n\tb = 1\r\n"),
    st.just("a." + "b." * 20 + "c = 1"),
    st.just("k" * 10000 + " = 1"),
    st.just("a = 1"),  # no trailing newline
)