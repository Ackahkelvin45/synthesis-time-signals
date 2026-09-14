```python
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Small helpers / atoms
# ---------------------------------------------------------------------------

# Characters that are safe to appear raw inside strings (no NUL, no newline;
# we add newlines only where the grammar permits them).
_SAFE_TEXT_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\n\r",
)

_BARE_KEY_CHARS = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)

_bare_key = st.text(_BARE_KEY_CHARS, min_size=1, max_size=10)

# A bare key with a leading digit / leading zeros is fine lexically.
_numeric_bare_key = st.builds(
    lambda d, rest: d + rest,
    st.integers(min_value=0, max_value=9).map(str),
    st.text(_BARE_KEY_CHARS, min_size=0, max_size=6),
)

_simple_unquoted_key = st.one_of(_bare_key, _numeric_bare_key)

# A long key (up to ~10k chars) - explicitly mentioned in the notes.
_long_key = st.text(_BARE_KEY_CHARS, min_size=1000, max_size=10000)


# ---------------------------------------------------------------------------
# Strings (all four quoting forms, with escapes and non-ASCII)
# ---------------------------------------------------------------------------

_ESCAPE_SIMPLE = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_ESCAPE_UNICODE = st.builds(
    lambda h: "\\u" + h,
    st.text("0123456789abcdefABCDEF", min_size=4, max_size=4),
)

_ESCAPE_EX_UNICODE = st.builds(
    lambda h: "\\U" + h,
    st.text("0123456789abcdefABCDEF", min_size=8, max_size=8),
)

# The notes mention `\u0000` inside a string is fine.
_ESCAPE_NUL = st.just("\\u0000")

_ESCAPE = st.one_of(
    _ESCAPE_SIMPLE, _ESCAPE_UNICODE, _ESCAPE_EX_UNICODE, _ESCAPE_NUL
)

# A raw control character that is not NUL / newline (parser accepts these).
_RAW_CONTROL = st.characters(
    min_codepoint=1,
    max_codepoint=0x1F,
    blacklist_characters="\n\r",
)

# Non-ASCII text (including astral planes) - safe in strings, not in bare keys.
_NON_ASCII = st.characters(min_codepoint=0x80, blacklist_categories=("Cs",))

_BASIC_STRING_INNER_CHAR = st.one_of(
    _SAFE_TEXT_CHARS,
    _RAW_CONTROL,
    _NON_ASCII,
)

# Basic string: `"..."` with escapes; no raw newline, no raw `"`.
_basic_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(
        st.one_of(_BASIC_STRING_INNER_CHAR, _ESCAPE),
        min_size=0,
        max_size=12,
    ),
)

# Literal string: `'...'`; no raw `'`, no newline.
_literal_string = st.builds(
    lambda parts: "'" + "".join(parts) + "'",
    st.lists(
        st.one_of(_SAFE_TEXT_CHARS, _RAW_CONTROL, _NON_ASCII),
        min_size=0,
        max_size=12,
    ),
)

# Multiline basic string: `"""..."""`; may contain raw newlines, escapes.
_ML_BASIC_INNER = st.one_of(
    _SAFE_TEXT_CHARS,
    _RAW_CONTROL,
    _NON_ASCII,
    st.just("\n"),
    _ESCAPE,
)

_ml_basic_string = st.builds(
    lambda parts: '"""' + "".join(parts) + '"""',
    st.lists(_ML_BASIC_INNER, min_size=0, max_size=12),
)

# Multiline literal string: `'''...'''`; no escapes, can contain anything
# except the closing delimiter sequence.
_ML_LITERAL_INNER = st.one_of(
    _SAFE_TEXT_CHARS,
    _RAW_CONTROL,
    _NON_ASCII,
    st.just("\n"),
)

_ml_literal_string = st.builds(
    lambda parts: "'''" + "".join(parts) + "'''",
    st.lists(_ML_LITERAL_INNER, min_size=0, max_size=12),
)

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)


# ---------------------------------------------------------------------------
# Integers (all bases, underscores, extremes)
# ---------------------------------------------------------------------------

_DEC_DIGIT = st.integers(min_value=0, max_value=9).map(str)
_DEC_DIGIT_NZ = st.integers(min_value=1, max_value=9).map(str)

_DEC_SIGN = st.sampled_from(["", "+", "-"])


def _dec_int():
    # Either a single digit (possibly 0, possibly leading zeros via repetition),
    # or a multi-digit number with optional underscores between digits.
    single = _DEC_DIGIT
    multi = st.builds(
        lambda head, tail: head + tail,
        _DEC_DIGIT_NZ,
        st.lists(
            st.one_of(_DEC_DIGIT, st.just("_")),
            min_size=0,
            max_size=20,
        ).map("".join),
    )
    leading_zero = st.builds(
        lambda zeros, tail: "0" + zeros + tail,
        st.text("0", min_size=1, max_size=10),
        st.text("0123456789_", min_size=0, max_size=10),
    )
    body = st.one_of(single, multi, leading_zero)
    return st.builds(lambda s, b: s + b, _DEC_SIGN, body)


# Extreme decimal magnitudes (beyond 64 bits, e.g. 1e309-like ints).
_extreme_dec_int = st.builds(
    lambda s, digits: s + digits,
    _DEC_SIGN,
    st.text("0123456789", min_size=20, max_size=400),
)

_HEX_DIGIT = st.text("0123456789abcdefABCDEF", min_size=1, max_size=1)
_OCT_DIGIT = st.text("01234567", min_size=1, max_size=1)
_BIN_DIGIT = st.text("01", min_size=1, max_size=1)


def _based_int(prefix, digit):
    first = digit
    rest = st.lists(
        st.one_of(digit, st.just("_")),
        min_size=0,
        max_size=20,
    ).map("".join)
    return st.builds(lambda p, f, r: p + f + r, st.just(prefix), first, rest)


_hex_int = _based_int("0x", _HEX_DIGIT)
_oct_int = _based_int("0o", _OCT_DIGIT)
_bin_int = _based_int("0b", _BIN_DIGIT)

_integer = st.one_of(
    _dec_int(),
    _extreme_dec_int,
    _hex_int,
    _oct_int,
    _bin_int,
)


# ---------------------------------------------------------------------------
# Floats (incl. inf / nan, extreme exponents, the lenient `1.` and `.5`)
# ---------------------------------------------------------------------------

_FLOAT_SIGN = st.sampled_from(["", "+", "-"])
_EXP_MARK = st.sampled_from(["e", "E"])
_EXP_SIGN = st.sampled_from(["", "+", "-"])


def _digits_with_underscores(min_size=1, max_size=20):
    return st.text("0123456789", min_size=min_size, max_size=max_size)


def _frac():
    return st.builds(
        lambda d: "." + d,
        _digits_with_underscores(min_size=0, max_size=20),
    )


def _exp():
    return st.builds(
        lambda mark, sign, digits: mark + sign + digits,
        _EXP_MARK,
        _EXP_SIGN,
        _digits_with_underscores(min_size=1, max_size=5),
    )


def _float():
    # integer part (possibly empty for `.5`), fractional part, exponent
    int_part = st.one_of(
        st.just(""),
        _digits_with_underscores(min_size=1, max_size=10),
        _digits_with_underscores(min_size=20, max_size=400),  # extreme magnitudes
    )
    frac_part = st.one_of(st.just(""), _frac())
    exp_part = st.one_of(st.just(""), _exp())

    def build(sign, ip, fp, ep):
        # ensure at least one of ip/fp is non-empty and there is a dot or exponent
        if not ip and not fp:
            ip = "0"
        if not fp and not ep:
            fp = ".0"
        return sign + ip + fp + ep

    return st.builds(build, _FLOAT_SIGN, int_part, frac_part, exp_part)


_inf = st.builds(lambda s: s + "inf", _FLOAT_SIGN)
_nan = st.builds(lambda s: s + "nan", _FLOAT_SIGN)

_floating_point = st.one_of(_float(), _inf, _nan)


# ---------------------------------------------------------------------------
# Booleans and date-times
# ---------------------------------------------------------------------------

_boolean = st.sampled_from(["true", "false"])

_TWO = st.text("0123456789", min_size=2, max_size=2)
_FOUR = st.text("0123456789", min_size=4, max_size=4)

_OFFSET = st.one_of(
    st.just("Z"),
    st.builds(
        lambda s, h, m: s + h + ":" + m,
        st.sampled_from(["+", "-"]),
        _TWO,
        _TWO,
    ),
)

_DELIM = st.sampled_from(["T", "t", " "])

_SECFRAC = st.builds(
    lambda d: "." + d, st.text("0123456789", min_size=1, max_size=9)
)

_PARTIAL_TIME = st.builds(
    lambda h, m, s, f: h + ":" + m + ":" + s + f,
    _TWO,
    _TWO,
    _TWO,
    st.one_of(st.just(""), _SECFRAC),
)

_FULL_DATE = st.builds(
    lambda y, mo, d: y + "-" + mo + "-" + d,
    _FOUR,
    _TWO,
    _TWO,
)

_OFFSET_DATE_TIME = st.builds(
    lambda d, sep, t, off: d + sep + t + off,
    _FULL_DATE,
    _DELIM,
    _PARTIAL_TIME,
    _OFFSET,
)

_LOCAL_DATE_TIME = st.builds(
    lambda d, sep, t: d + sep + t,
    _FULL_DATE,
    _DELIM,
    _PARTIAL_TIME,
)

_LOCAL_DATE = _FULL_DATE

_LOCAL_TIME = _PARTIAL_TIME

_date_time = st.one_of(
    _OFFSET_DATE_TIME,
    _LOCAL_DATE_TIME,
    _LOCAL_DATE,
    _LOCAL_TIME,
)

# Calendar-invalid dates (parser accepts them).
_bad_date = st.builds(
    lambda y, mo, d: y + "-" + mo + "-" + d,
    _FOUR,
    st.sampled_from(["00", "13", "19", "99"]),
    st.sampled_from(["00", "30", "31", "32", "99"]),
)


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_simple_unquoted_key, _quoted_key)

# Dotted keys: 2..4 components.
_dotted_key = st.builds(
    lambda parts: ".".join(parts),
    st.lists(_simple_key, min_size=2, max_size=4),
)

_key = st.one_of(_simple_key, _dotted_key)


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

_MAX_DEPTH = 2048

# We build a recursive strategy whose recursion is bounded by the size of the
# generated value. The depth is naturally bounded by `max_leaves`; nesting
# concentrates in the 1..2048 band because arrays/inline tables each consume
# at least one level of recursion per nesting.
_value = st.recursive(
    # Base (non-recursive) values.
    st.one_of(
        _string,
        _integer,
        _floating_point,
        _boolean,
        _date_time,
        _bad_date,
    ),
    # Recursive extension.
    lambda children: st.one_of(
        _array(children),
        _inline_table(children),
    ),
    max_leaves=30,
)


def _array(children):
    def render(items, trailing, comments):
        body = ", ".join(items)
        if trailing and items:
            body += ","
        if comments:
            body += "\n# c\n"
        return "[" + body + "]"

    return st.builds(
        render,
        st.lists(children, min_size=0, max_size=8),
        st.booleans(),
        st.booleans(),
    )


def _inline_table(children):
    def render(pairs, trailing):
        body = ", ".join(pairs)
        if trailing and pairs:
            body += ","
        return "{" + body + "}"

    pair = st.builds(
        lambda k, v: k + " = " + v,
        _key,
        children,
    )
    return st.builds(
        render,
        st.lists(pair, min_size=0, max_size=6),
        st.booleans(),
    )


# ---------------------------------------------------------------------------
# Key/value lines, tables, array-of-tables
# ---------------------------------------------------------------------------

_comment = st.builds(
    lambda body: "#" + body,
    st.one_of(
        st.just(""),
        st.text(_SAFE_TEXT_CHARS, min_size=1, max_size=40),
        st.text(_RAW_CONTROL, min_size=1, max_size=8),
    ),
)

_key_value = st.builds(
    lambda k, v: k + " = " + v,
    _key,
    _value,
)

_standard_table = st.builds(
    lambda k: "[" + k + "]",
    _key,
)

_array_table = st.builds(
    lambda k: "[[" + k + "]]",
    _key,
)


# ---------------------------------------------------------------------------
# Malformed / near-valid fragments
# ---------------------------------------------------------------------------

def _malformed():
    # A handful of hand-crafted malformed-but-close inputs, plus random
    # mutations that produce one missing/doubled delimiter, unterminated
    # strings, stray tokens, etc.
    fixed = st.sampled_from(
        [
            # unterminated basic string
            'a = "unterminated',
            # unterminated literal string
            "a = 'unterminated",
            # unterminated multiline basic string
            'a = """unterminated',
            # missing closing bracket
            "a = [1, 2, 3",
            # missing closing brace
            "a = {b = 1",
            # doubled delimiter
            "a = [[1, 2]]",
            # stray token
            "a = 1 2",
            # invalid escape
            'a = "\\q"',
            # value on the line after `=`
            "a =\n1",
            # newline inside inline table
            "a = {b = 1,\nc = 2}",
            # non-ASCII bare key
            "caf\u00e9 = 1",
            # empty document
            "",
            # comment-only document
            "# just a comment",
            # duplicate key
            "a = 1\na = 2",
            # duplicate table
            "[t]\n[t]",
            # table and array-of-tables with same name
            "[t]\n[[t]]",
            # bare key outside allowed set
            "missing =",
            # trailing garbage
            "a = 1\n]",
            # doubled equals
            "a == 1",
            # missing equals
            "a 1",
        ]
    )

    # Random "one missing/doubled delimiter" mutations over valid docs.
    valid_doc = _document()
    base = st.one_of(fixed, _mutate(valid_doc))
    return base


def _mutate(doc_strategy):
    def do_mutate(s):
        if not s:
            return s
        i = len(s) // 2
        choice = i % 4
        if choice == 0:
            # drop a character
            return s[:i] + s[i + 1:]
        if choice == 1:
            # duplicate a character
            return s[:i] + s[i : i + 1] + s[i:]
        if choice == 2:
            # insert a stray token
            return s[:i] + "]" + s[i:]
        # truncate
        return s[:i]

    return doc_strategy.map(do_mutate)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def _expression():
    return st.one_of(
        _key_value,
        _standard_table,
        _array_table,
        _comment,
    )


def _document():
    def render(lines, trailing_nl):
        body = "\n".join(lines)
        if trailing_nl:
            body += "\n"
        return body

    return st.builds(
        render,
        st.lists(_expression(), min_size=0, max_size=12),
        st.booleans(),
    )


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

# Mix valid documents, explicitly malformed documents, and a few
# hand-crafted edge cases (deep nesting, empty containers, duplicate keys).
_deep_array = st.builds(
    lambda depth: "a = " + ("[" * depth) + ("]" * depth),
    st.integers(min_value=0, max_value=_MAX_DEPTH),
)

_deep_inline_table = st.builds(
    lambda depth: "a = " + ("{x = " * depth) + "1" + ("}" * depth),
    st.integers(min_value=0, max_value=200),
)

_edge_documents = st.sampled_from(
    [
        "",
        "\n",
        "# comment only\n",
        "a = 1",
        "a = 1\n",
        "a = 1\r\n",
        "\ta = 1\n",
        "[t]\n",
        "[[a]]\n",
        "[[a]]\n[[a]]\n",
        '"" = 1\n',
        "a.b.c = 1\n",
        "a = {}\n",
        "a = []\n",
        "a = [1, 2, 3,]\n",
        "a = [\n 1,\n 2,\n]\n",
        "a = {b = 1,}\n",
        "a = 007\n",
        "a = 1.\n",
        "a = .5\n",
        "a = 1979-02-30\n",
        'a = "x\x01y"\n',
        "# comment \x01\n",
        "a = 1e309\n",
        "a = 9223372036854775808\n",
        "a = -9223372036854775809\n",
        "a = 0xFFFFFFFFFFFFFFFFFFFF\n",
        "a = 0o7777777777777777777777\n",
        "a = 0b1111111111111111111111111111111111111111111111111111111111111111111\n",
        "a = inf\n",
        "a = -inf\n",
        "a = nan\n",
        "a = 1979-05-27 07:32:00Z\n",
        "a = 1979-05-27T07:32:00\n",
        "a = 07:32:00\n",
        "a = 1979-05-27\n",
        "a = \"\\u0000\"\n",
        "a = \"\\U0001F600\"\n",
        "a = 'literal'\n",
        'a = """multi\nline"""\n',
        "a = '''multi\nline'''\n",
        "a = 1_000\n",
        "a = +1_000\n",
        "a = -1_000\n",
    ]
)

strategy = st.one_of(
    _document(),
    _malformed(),
    _edge_documents,
    _deep_array,
    _deep_inline_table,
)
```