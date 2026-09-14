from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Low-level character/atom strategies
# ---------------------------------------------------------------------------

# Characters that are safe inside bare keys (per grammar: ALPHA | DIGIT | - | _)
_BARE_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

# Non-ASCII / control-ish characters that are valid inside strings (not NUL raw)
# We never emit a raw NUL byte anywhere in the document.
_SAFE_NON_ASCII = st.sampled_from(
    [
        "é", "ü", "ñ", "ß", "ø", "å", "ç", "λ", "中", "文", "日", "本",
        "🎉", "🦄", "𝕏", "Ω", "π", "→", "€", "£", "¥", "©", "®", "™",
        "\u0080", "\u00ff", "\u07ff", "\u0800", "\ufffd", "\uffff",
        "\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x0e", "\x1f",
        "\x7f",
    ]
)

# Characters that are valid in a basic string body (not " or \ or newline)
_BASIC_STRING_BODY_CHAR = st.one_of(
    st.characters(
        whitelist_categories=("L", "M", "N", "P", "S", "Z"),
        blacklist_characters='"\\\n\r',
    ),
    _SAFE_NON_ASCII,
)

# Characters valid in a literal string body (not ' or newline)
_LITERAL_STRING_BODY_CHAR = st.one_of(
    st.characters(
        whitelist_categories=("L", "M", "N", "P", "S", "Z"),
        blacklist_characters="'\n\r",
    ),
    _SAFE_NON_ASCII,
)

# Multiline basic string body char (not " or \)
_ML_BASIC_BODY_CHAR = st.one_of(
    st.characters(blacklist_characters='"\\'),
    _SAFE_NON_ASCII,
)

# Multiline literal string body char (not ')
_ML_LITERAL_BODY_CHAR = st.one_of(
    st.characters(blacklist_characters="'"),
    _SAFE_NON_ASCII,
)

# ---------------------------------------------------------------------------
# Escape sequences
# ---------------------------------------------------------------------------

_SIMPLE_ESCAPES = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_HEX4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_HEX8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)

_UNICODE_ESCAPES = st.one_of(
    _HEX4.map(lambda h: "\\u" + h),
    _HEX8.map(lambda h: "\\U" + h),
    # Deliberately malformed escapes (near-valid)
    st.just("\\u12"),
    st.just("\\U0011"),
    st.just("\\q"),
    st.just("\\x41"),
)

_ESCAPE = st.one_of(_SIMPLE_ESCAPES, _UNICODE_ESCAPES)

# ---------------------------------------------------------------------------
# Strings (all four quoting forms)
# ---------------------------------------------------------------------------

def _basic_string():
    body = st.lists(
        st.one_of(_BASIC_STRING_BODY_CHAR, _ESCAPE), max_size=12
    ).map("".join)
    return body.map(lambda b: '"' + b + '"')

def _literal_string():
    body = st.lists(_LITERAL_STRING_BODY_CHAR, max_size=12).map("".join)
    return body.map(lambda b: "'" + b + "'")

def _ml_basic_string():
    # Can contain newlines, quotes (up to 2), escapes
    body = st.lists(
        st.one_of(
            _ML_BASIC_BODY_CHAR,
            _ESCAPE,
            st.just("\n"),
            st.just("\r\n"),
            st.just('"'),
            st.just('""'),
        ),
        max_size=16,
    ).map("".join)
    return body.map(lambda b: '"""' + b + '"""')

def _ml_literal_string():
    body = st.lists(
        st.one_of(
            _ML_LITERAL_BODY_CHAR,
            st.just("\n"),
            st.just("\r\n"),
            st.just("'"),
            st.just("''"),
        ),
        max_size=16,
    ).map("".join)
    return body.map(lambda b: "'''" + b + "'''")

# Unterminated / malformed string variants for near-valid coverage
def _malformed_string():
    return st.one_of(
        st.just('"unterminated'),
        st.just("'unterminated"),
        st.just('"""unterminated'),
        st.just("'''unterminated"),
        st.just('"esc\\'),
        st.just('"bad\\qescape"'),
        st.just('"'),
        st.just("'"),
        st.just('"""'),
        st.just("'''"),
    )

_string = st.one_of(
    _basic_string(),
    _literal_string(),
    _ml_basic_string(),
    _ml_literal_string(),
    _malformed_string(),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_bare_key = st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=10)

_quoted_key = st.one_of(
    _basic_string(),
    _literal_string(),
    st.just('""'),  # empty quoted key
    st.just("''"),
)

_simple_key = st.one_of(_bare_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(
    lambda parts: ".".join(parts)
)

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-(2**80), max_value=2**80).map(str),
    st.integers(min_value=-(2**10), max_value=2**10).map(str),
    # leading zeros (accepted by this parser)
    st.just("007"),
    st.just("00"),
    st.just("0000"),
    # underscores
    st.just("1_000"),
    st.just("1_2_3_4_5"),
    st.just("-1_000"),
    st.just("+1_000"),
    # extremes
    st.just(str(2**63 - 1)),
    st.just(str(2**63)),
    st.just(str(2**64)),
    st.just("-" + str(2**63)),
    st.just("9" * 30),
    st.just("-" + "9" * 30),
)

_hex_int = st.one_of(
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8).map(
        lambda h: "0x" + h
    ),
    st.just("0xdead_beef"),
    st.just("0x0"),
    st.just("0x" + "f" * 20),
)

_oct_int = st.one_of(
    st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda o: "0o" + o),
    st.just("0o0"),
    st.just("0o7_7_7"),
    st.just("0o" + "7" * 20),
)

_bin_int = st.one_of(
    st.text(alphabet="01", min_size=1, max_size=12).map(lambda b: "0b" + b),
    st.just("0b0"),
    st.just("0b1_0_1"),
    st.just("0b" + "1" * 40),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.just("1."),
    st.just(".5"),
    st.just("0.0"),
    st.just("-0.0"),
    st.just("1e309"),
    st.just("1e-309"),
    st.just("1E+10"),
    st.just("6.626e-34"),
    st.just("1_000.000_1"),
    st.just("3.14159"),
    st.just("1e0"),
    st.just("1_0.0_1e1_0"),
    st.just("inf"),
    st.just("-inf"),
    st.just("+inf"),
    st.just("nan"),
    st.just("-nan"),
    st.just("+nan"),
)

_bool = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Date-times (all four forms)
# ---------------------------------------------------------------------------

_year = st.integers(min_value=0, max_value=9999).map(lambda y: f"{y:04d}")
_month = st.integers(min_value=0, max_value=99).map(lambda m: f"{m:02d}")
_day = st.integers(min_value=0, max_value=99).map(lambda d: f"{d:02d}")
_hour = st.integers(min_value=0, max_value=99).map(lambda h: f"{h:02d}")
_minute = st.integers(min_value=0, max_value=99).map(lambda m: f"{m:02d}")
_second = st.integers(min_value=0, max_value=99).map(lambda s: f"{s:02d}")

_full_date = st.tuples(_year, _month, _day).map(lambda t: "-".join(t))
_partial_time = st.tuples(_hour, _minute, _second).map(lambda t: ":".join(t))

_secfrac = st.one_of(
    st.integers(min_value=0, max_value=999999).map(lambda f: "." + str(f)),
    st.just(".1"),
    st.just(".123456789"),
)

_delim = st.sampled_from(["T", "t", " "])

_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _hour, st.just(":"), _minute
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

_full_time = st.tuples(_partial_time, _secfrac, _offset).map(
    lambda t: t[0] + t[1] + t[2]
)

_offset_date_time = st.tuples(_full_date, _delim, _full_time).map(
    lambda t: t[0] + t[1] + t[2]
)

_local_date_time = st.tuples(_full_date, _delim, _partial_time).map(
    lambda t: t[0] + t[1] + t[2]
)

_local_date = _full_date
_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    # calendar-invalid dates (accepted by this parser)
    st.just("1979-02-30"),
    st.just("2023-13-45"),
    st.just("0000-00-00"),
    st.just("9999-99-99"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("1979-05-27T07:32:00.999999-07:00"),
    st.just("07:32:00"),
    st.just("07:32:00.999999"),
)

# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

_comment_char = st.one_of(
    st.characters(blacklist_characters="\n\r"),
    _SAFE_NON_ASCII,
    st.sampled_from(["\x01", "\x02", "\x07", "\x0b", "\x0c", "\x1f"]),
)

_comment = st.lists(_comment_char, max_size=20).map(
    lambda cs: "#" + "".join(cs)
)

_comment_opt = st.one_of(st.none(), _comment)

# ---------------------------------------------------------------------------
# Recursive value strategy: arrays and inline tables
# ---------------------------------------------------------------------------

# Leaf (non-recursive) values
_leaf_value = st.one_of(
    _string,
    _integer,
    _float,
    _bool,
    _date_time,
)

# We build recursive values with st.recursive.
# Base: leaf values.  Extension: arrays and inline tables.

def _array_from_elems(elems):
    """Build array text from a list of already-rendered value strings."""
    if not elems:
        return "[]"
    # multiline arrays with comments and trailing commas
    return "[" + ", ".join(elems) + "]"

def _array_with_ws(elems):
    """Array with whitespace/newlines/comments interspersed."""
    if not elems:
        return "[\n]"
    inner = ",\n".join(elems)
    return "[\n" + inner + ",\n]"

def _inline_table_from_pairs(pairs):
    if not pairs:
        return "{}"
    return "{" + ", ".join(pairs) + "}"

def _inline_table_trailing_comma(pairs):
    if not pairs:
        return "{}"
    return "{" + ", ".join(pairs) + ",}"

def _make_recursive(leaf, key_strategy, depth_band=(1500, 2048)):
    """Build the recursive value strategy."""

    def extend(children):
        child = st.one_of(children) if isinstance(children, (list, tuple)) else children

        # Array variants
        arr_simple = st.lists(child, max_size=5).map(_array_from_elems)
        arr_ws = st.lists(child, max_size=5).map(_array_with_ws)
        # Deeply nested arrays: nest a single child many times (depth band)
        deep_depth = st.integers(min_value=depth_band[0], max_value=depth_band[1])
        deep_array = deep_depth.map(lambda d: "[" * d + "]" * d)
        # Near-valid: missing closing bracket
        arr_unclosed = st.lists(child, min_size=1, max_size=3).map(
            lambda es: "[" + ", ".join(es)
        )
        # Double delimiter
        arr_doubled = st.lists(child, min_size=1, max_size=3).map(
            lambda es: "[[" + ", ".join(es) + "]]"
        )

        # Inline table variants
        def _pair(c):
            return st.tuples(key_strategy, c).map(lambda t: t[0] + " = " + t[1])

        pairs = st.lists(st.builds(lambda c: _pair(c), child), max_size=4)
        it_simple = pairs.map(_inline_table_from_pairs)
        it_trailing = pairs.map(_inline_table_trailing_comma)
        # Near-valid: missing closing brace
        it_unclosed = st.lists(
            st.builds(lambda c: _pair(c), child), min_size=1, max_size=3
        ).map(lambda ps: "{" + ", ".join(ps))
        # Near-valid: newline inside inline table (parser rejects)
        it_newline = st.lists(
            st.builds(lambda c: _pair(c), child), min_size=1, max_size=3
        ).map(lambda ps: "{" + ",\n".join(ps) + "}")

        return st.one_of(
            arr_simple,
            arr_ws,
            deep_array,
            arr_unclosed,
            arr_doubled,
            it_simple,
            it_trailing,
            it_unclosed,
            it_newline,
        )

    return st.recursive(leaf, extend, max_leaves=20)

_value = _make_recursive(_leaf_value, _key, depth_band=(1500, 2048))

# ---------------------------------------------------------------------------
# Key-value lines
# ---------------------------------------------------------------------------

def _key_value():
    return st.tuples(_key, _value).map(lambda t: t[0] + " = " + t[1])

_key_value_line = st.one_of(
    _key_value(),
    # near-valid: missing equals
    st.tuples(_key, _value).map(lambda t: t[0] + " " + t[1]),
    # near-valid: doubled equals
    st.tuples(_key, _value).map(lambda t: t[0] + " == " + t[1]),
    # near-valid: value on next line
    st.tuples(_key, _value).map(lambda t: t[0] + " =\n" + t[1]),
    # near-valid: stray token
    st.tuples(_key, _value).map(lambda t: t[0] + " = " + t[1] + " extra"),
)

# ---------------------------------------------------------------------------
# Tables and arrays of tables
# ---------------------------------------------------------------------------

_standard_table = _key.map(lambda k: "[" + k + "]")

_array_table = _key.map(lambda k: "[[" + k + "]]")

# Near-valid table variants
_malformed_table = st.one_of(
    _key.map(lambda k: "[" + k),
    _key.map(lambda k: k + "]"),
    _key.map(lambda k: "[[" + k + "]"),
    _key.map(lambda k: "[" + k + "]]"),
    st.just("[]"),
    st.just("[[]]"),
    st.just("[.]"),
)

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

# A line in the document is either a key-value, a table header, a comment, or blank
_doc_line = st.one_of(
    _key_value_line,
    _standard_table,
    _array_table,
    _malformed_table,
    _comment,
    st.just(""),
)

# Dotted-key duplicate-ish lines to trigger duplicate key rejection
_duplicate_key_line = st.one_of(
    st.just("a = 1"),
    st.just("a = 2"),
    st.just("[t]"),
    st.just("[t]"),
    st.just("[[a]]"),
    st.just("[[a]]"),
)

# Assemble a complete document
def _assemble(lines):
    """Join lines with newlines.  Sometimes omit trailing newline."""
    return "\n".join(lines)

_document_lines = st.lists(
    st.one_of(_doc_line, _duplicate_key_line),
    min_size=0,
    max_size=15,
)

_document = _document_lines.map(_assemble)

# Also allow documents with CRLF, tab indentation, no trailing newline
_crlf_document = _document_lines.map(lambda ls: "\r\n".join(ls))

_tab_indented_document = _document_lines.map(
    lambda ls: "\n".join("\t" + l if l else l for l in ls)
)

# Empty / comment-only documents
_empty_doc = st.just("")
_comment_only = st.lists(_comment, min_size=1, max_size=5).map(
    lambda cs: "\n".join(cs)
)

# Very long key (10000 chars)
_long_key = st.text(alphabet=_BARE_KEY_CHARS, min_size=10000, max_size=10000)
_long_key_doc = _long_key.map(lambda k: k + " = 1")

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _crlf_document,
    _tab_indented_document,
    _empty_doc,
    _comment_only,
    _long_key_doc,
    # A few hand-crafted edge cases
    st.sampled_from(
        [
            "a = 007\n",
            "a = 1.\n",
            "a = .5\n",
            'a = "x\x01y"\n',
            "# comment with \x01 control\n",
            "a = {b = 1,}\n",
            "a = 1979-02-30\n",
            "a = []\n",
            "a = {}\n",
            "a = [[[[1]]]]\n",
            '"" = 1\n',
            "a = 1e309\n",
            "a = inf\n",
            "a = -nan\n",
            "a = 0xdead_beef\n",
            "a = 0o777\n",
            "a = 0b1010\n",
            "a = 1_000_000\n",
            "a = 1979-05-27T07:32:00Z\n",
            "a = 1979-05-27 07:32:00Z\n",
            "a = 07:32:00\n",
            "a = 1979-05-27\n",
            'a = """multi\nline"""\n',
            "a = '''multi\nline'''\n",
            'a = "\\u0041"\n',
            'a = "\\U0001F600"\n',
            "a = true\n",
            "a = false\n",
            "[t]\n",
            "[[a]]\n",
            "a.b.c = 1\n",
            '"a b" = 1\n',
            "'a b' = 1\n",
            "a = 1_000.000_1\n",
            "a = 6.626e-34\n",
            "a = 1E+10\n",
            "a = -0.0\n",
            "a = +inf\n",
            "a = 2023-13-45\n",
            "a = 0000-00-00\n",
            "a = 9999-99-99\n",
        ]
    ),
)

# Ensure no raw NUL byte sneaks in (harness skips NUL-terminated input)
strategy = strategy.filter(lambda s: "\x00" not in s)