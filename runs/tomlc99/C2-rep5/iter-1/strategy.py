from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Control chars that are NOT NUL.  NUL must never appear raw in the output.
_CTRL_NO_NUL = [chr(i) for i in range(0x01, 0x20)] + [chr(0x7F)]
_CTRL_NO_NUL_STR = "".join(_CTRL_NO_NUL)

# Characters allowed raw inside a basic string (no '"', '\\', raw newline).
_BASIC_RAW = "".join(
    chr(c)
    for c in range(0x20, 0x7F)
    if chr(c) not in '"\\'
) + _CTRL_NO_NUL_STR + "".join(
    chr(c) for c in range(0x80, 0x2000) if c != 0x7F
)

# Characters allowed raw inside a literal string (no "'", no newline).
_LITERAL_RAW = "".join(
    chr(c)
    for c in range(0x20, 0x7F)
    if chr(c) != "'"
) + _CTRL_NO_NUL_STR + "".join(
    chr(c) for c in range(0x80, 0x2000) if c != 0x7F
)

# Multiline basic: raw newlines are allowed; raw '"' is allowed except runs of 3.
_ML_BASIC_RAW = _BASIC_RAW + "\n\r" + '""' + '"'

# Multiline literal: raw "'" allowed except runs of 3.
_ML_LITERAL_RAW = _LITERAL_RAW + "\n\r" + "''" + "'"

_UNQUOTED_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

# ---------------------------------------------------------------------------
# Escapes
# ---------------------------------------------------------------------------

_SIMPLE_ESCAPES = ["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]

def _unicode_escape():
    return st.integers(min_value=0, max_value=0xFFFF).map(
        lambda n: "\\u%04x" % n
    )

def _ex_unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08x" % n
    )

_ESCAPE = st.one_of(
    st.sampled_from(_SIMPLE_ESCAPES),
    _unicode_escape(),
    _ex_unicode_escape(),
    # near-valid malformed escape (parser rejects \q)
    st.just("\\q"),
    st.just("\\"),
)

# ---------------------------------------------------------------------------
# Strings (all four quoting forms)
# ---------------------------------------------------------------------------

def _basic_string():
    return st.one_of(
        st.just('""'),
        st.lists(
            st.one_of(
                st.text(alphabet=_BASIC_RAW, max_size=8),
                _ESCAPE,
            ),
            min_size=1,
            max_size=6,
        ).map(lambda parts: '"' + "".join(parts) + '"'),
    )

def _literal_string():
    return st.one_of(
        st.just("''"),
        st.text(alphabet=_LITERAL_RAW, min_size=1, max_size=20).map(
            lambda s: "'" + s + "'"
        ),
    )

def _ml_basic_string():
    return st.one_of(
        st.just('""""""'),
        st.lists(
            st.one_of(
                st.text(alphabet=_ML_BASIC_RAW, max_size=10),
                _ESCAPE,
                st.just('\\\n'),
                st.just('\\\r\n'),
            ),
            min_size=1,
            max_size=5,
        ).map(lambda parts: '"""' + "".join(parts) + '"""'),
    )

def _ml_literal_string():
    return st.one_of(
        st.just("''''''"),
        st.text(alphabet=_ML_LITERAL_RAW, min_size=1, max_size=25).map(
            lambda s: "'''" + s + "'''"
        ),
    )

def _string():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    )

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_DEC_DIGITS = "0123456789"

def _dec_int():
    return st.one_of(
        st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
        st.just("0"),
        st.just("-0"),
        st.just("+0"),
        # leading zeros (accepted)
        st.integers(min_value=0, max_value=999999).map(lambda n: "0" + str(n)),
        # underscores
        st.integers(min_value=10 ** 6, max_value=10 ** 12).map(
            lambda n: "{:,}".format(n).replace(",", "_")
        ),
        st.just("9" * 40),
        st.just("-" + "9" * 40),
    )

def _hex_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0x%x" % n),
        st.just("0x0"),
        st.just("0xDEAD_BEEF"),
        st.just("0x" + "F" * 32),
    )

def _oct_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2 ** 32).map(lambda n: "0o%o" % n),
        st.just("0o0"),
        st.just("0o7_7_7"),
    )

def _bin_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2 ** 32).map(lambda n: "0b" + bin(n)[2:]),
        st.just("0b0"),
        st.just("0b1_0_1"),
    )

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    return st.one_of(
        st.just("1."),
        st.just(".5"),
        st.just("0.0"),
        st.just("-0.0"),
        st.just("+1.0"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-309"),
        st.just("6.626e-34"),
        st.just("1_000.000_1"),
        st.just("3."),
        st.just(".0"),
        st.just("1e0"),
        st.just("1E+2"),
        st.just("1e-2"),
        st.just("9" * 30 + "." + "9" * 30 + "e" + "9" * 10),
        st.just("inf"),
        st.just("+inf"),
        st.just("-inf"),
        st.just("nan"),
        st.just("+nan"),
        st.just("-nan"),
    )

# ---------------------------------------------------------------------------
# Dates / times
# ---------------------------------------------------------------------------

def _date():
    return st.one_of(
        st.just("1979-05-27"),
        st.just("0000-00-00"),
        st.just("1979-02-30"),  # calendar-invalid, accepted
        st.just("9999-12-31"),
        st.tuples(
            st.integers(min_value=0, max_value=9999),
            st.integers(min_value=0, max_value=99),
            st.integers(min_value=0, max_value=99),
        ).map(lambda t: "%04d-%02d-%02d" % t),
    )

def _time_partial():
    return st.tuples(
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.one_of(st.just(""), st.integers(min_value=0, max_value=999999).map(lambda n: ".%d" % n)),
    ).map(lambda t: "%02d:%02d:%02d%s" % t)

def _offset():
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(
            st.sampled_from(["+", "-"]),
            st.integers(min_value=0, max_value=99),
            st.integers(min_value=0, max_value=99),
        ).map(lambda t: "%s%02d:%02d" % t),
    )

def _datetime():
    sep = st.sampled_from(["T", "t", " "])
    return st.one_of(
        st.tuples(_date(), sep, _time_partial(), _offset()).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        ),
        st.tuples(_date(), sep, _time_partial()).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        _date(),
        _time_partial(),
    )

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _unquoted_key():
    return st.one_of(
        st.text(alphabet=_UNQUOTED_KEY_CHARS, min_size=1, max_size=12),
        st.just("a"),
        st.just("0"),
        st.just("-"),
        st.just("_"),
        st.just("k" * 1000),
    )

def _quoted_key():
    return st.one_of(
        st.just('""'),
        st.just("''"),
        _basic_string(),
        _literal_string(),
    )

def _simple_key():
    return st.one_of(_unquoted_key(), _quoted_key())

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(
        lambda ks: ".".join(ks)
    )

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------------------------------------------------------------------------
# Values (recursive)
# ---------------------------------------------------------------------------

def _bool():
    return st.sampled_from(["true", "false"])

def _leaf_value():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _bool(),
        _datetime(),
    )

def _value(value_strategy):
    return st.one_of(
        _leaf_value(),
        _array(value_strategy),
        _inline_table(value_strategy),
    )

def _array(value_strategy):
    elem = _value(value_strategy)

    def build(elems):
        if not elems:
            return "[]"
        # sometimes multiline, sometimes with trailing comma, sometimes comments
        return "[" + ", ".join(elems) + "]"

    def build_trailing(elems):
        if not elems:
            return "[]"
        return "[" + ", ".join(elems) + ",]"

    def build_multiline(elems):
        if not elems:
            return "[\n]"
        body = ",\n".join("  " + e for e in elems)
        return "[\n" + body + ",\n]"

    def build_with_comments(elems):
        if not elems:
            return "[\n# empty\n]"
        body = ",\n".join(
            ("  " + e + " # c" + str(i)) for i, e in enumerate(elems)
        )
        return "[\n" + body + ",\n]"

    return st.one_of(
        st.lists(elem, min_size=0, max_size=4).map(build),
        st.lists(elem, min_size=1, max_size=4).map(build_trailing),
        st.lists(elem, min_size=0, max_size=4).map(build_multiline),
        st.lists(elem, min_size=0, max_size=4).map(build_with_comments),
    )

def _inline_table(value_strategy):
    def build(pairs):
        if not pairs:
            return "{}"
        return "{" + ", ".join(pairs) + "}"

    def build_trailing(pairs):
        if not pairs:
            return "{}"
        return "{" + ", ".join(pairs) + ",}"

    pair = st.tuples(_key(), _value(value_strategy)).map(
        lambda t: t[0] + " = " + t[1]
    )
    return st.one_of(
        st.lists(pair, min_size=0, max_size=3).map(build),
        st.lists(pair, min_size=1, max_size=3).map(build_trailing),
    )

# ---------------------------------------------------------------------------
# Depth control for the recursive value strategy
# ---------------------------------------------------------------------------

def _value_strategy():
    # Recursive with explicit depth band 1500-2048 for deep-nesting cases,
    # but Hypothesis's recursive needs a depth limit; we use max_leaves and
    # let the strategy itself build moderate depth, plus a dedicated deep
    # array generator.
    return st.recursive(
        _leaf_value(),
        lambda children: st.one_of(
            _array(children),
            _inline_table(children),
        ),
        max_leaves=8,
    )

_VALUE = _value_strategy()

# ---------------------------------------------------------------------------
# Deep nesting (arrays and inline tables) - dedicated band 1500-2048
# ---------------------------------------------------------------------------

def _deep_array(depth):
    # depth >= 1
    inner = "[]"
    return "[" * depth + "]" * depth

def _deep_inline_table(depth):
    # nested inline tables: {a = {a = {a = 1}}}
    if depth <= 0:
        return "1"
    return "{a = " + _deep_inline_table(depth - 1) + "}"

_DEEP_DEPTH = st.integers(min_value=1500, max_value=2048)

def _deep_value():
    return st.one_of(
        _DEEP_DEPTH.map(_deep_array),
        _DEEP_DEPTH.map(_deep_inline_table),
    )

# ---------------------------------------------------------------------------
# Key/value lines, tables, array-of-tables
# ---------------------------------------------------------------------------

def _comment():
    # comments may contain raw control chars (parser accepts) but no newline
    return st.one_of(
        st.just(""),
        st.text(
            alphabet="".join(
                chr(c) for c in range(0x20, 0x7F)
            ) + _CTRL_NO_NUL_STR + "".join(chr(c) for c in range(0x80, 0x2000)),
            max_size=20,
        ).map(lambda s: "# " + s),
    )

def _key_value_line():
    return st.tuples(_key(), _VALUE, _comment()).map(
        lambda t: t[0] + " = " + t[1] + ((" " + t[2]) if t[2] else "")
    )

def _standard_table():
    return st.tuples(_key(), _comment()).map(
        lambda t: "[" + t[0] + "]" + ((" " + t[1]) if t[1] else "")
    )

def _array_table():
    return st.tuples(_key(), _comment()).map(
        lambda t: "[[" + t[0] + "]]" + ((" " + t[1]) if t[1] else "")
    )

def _line():
    return st.one_of(
        _key_value_line(),
        _standard_table(),
        _array_table(),
        _comment(),
    )

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

def _malformed():
    return st.one_of(
        # missing delimiter
        st.just('a = "unterminated'),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        st.just("a = '''unterminated"),
        st.just("a = [1, 2"),
        st.just("a = {b = 1"),
        st.just("a = 1"),
        st.just("[table"),
        st.just("[[array]"),
        # doubled delimiter
        st.just("a = [[1, 2]]"),
        st.just("a = {{b = 1}}"),
        st.just("a = 1]"),
        st.just("a = 1}"),
        st.just("a = = 1"),
        st.just("[t]]"),
        # stray token
        st.just("a = 1 b = 2"),
        st.just("a = 1 2"),
        st.just("a = @"),
        st.just("a = $"),
        st.just("a = \\"),
        st.just("a = 1.2.3"),
        st.just("a = 0x"),
        st.just("a = 0b2"),
        st.just("a = 0o8"),
        # newline inside inline table (rejected)
        st.just("a = {b = 1,\nc = 2}"),
        # duplicate keys (rejected)
        st.just("a = 1\na = 2"),
        st.just("[t]\n[t]"),
        st.just("[[a]]\n[a]"),
        # bare key outside allowed set (rejected)
        st.just("a = 1\n\u00e9 = 2"),
        # invalid escape (rejected)
        st.just('a = "\\q"'),
        # value on the line after =
        st.just("a =\n1"),
        # empty document variants
        st.just(""),
        st.just("\n"),
        st.just("# only comment"),
        st.just("\n\n\n"),
        st.just("   \t  "),
    )

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _document():
    # A document is a sequence of expressions separated by newlines.
    # We join lines with "\n" and sometimes CRLF / tabs / no trailing newline.
    sep = st.sampled_from(["\n", "\r\n", "\n\n", "\n# sep\n"])
    trailing = st.sampled_from(["", "\n", "\r\n", "\n\n"])

    def build(parts):
        lines = [p for p in parts if p is not None]
        if not lines:
            return ""
        return sep.example() if False else "\n".join(lines)

    return st.tuples(
        st.lists(_line(), min_size=0, max_size=8),
        trailing,
    ).map(lambda t: "\n".join(t[0]) + t[1])

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

_DOC = _document()

strategy = st.one_of(
    _DOC,
    _malformed(),
    _deep_value(),
    # comment-only / empty
    st.just(""),
    st.just("# comment only"),
    st.just("\n# comment\n"),
    # single key/value with every value kind
    st.tuples(_key(), _VALUE).map(lambda t: t[0] + " = " + t[1]),
    st.tuples(_key(), _VALUE).map(lambda t: t[0] + " = " + t[1] + "\n"),
    # empty containers
    st.just("a = []\nb = {}\n[t]\n[[arr]]"),
    # duplicate keys / tables (rejected by parser)
    st.just("a = 1\na = 2"),
    st.just("[t]\n[t]"),
    st.just("[[a]]\n[a]"),
    # non-ASCII bare key (rejected)
    st.just("\u00e9 = 1"),
    # embedded control chars (no NUL)
    st.just('a = "x' + "\x01" + 'y"'),
    st.just("a = 1 # comment with \x02 control"),
    # NUL escape inside string is fine (raw NUL never emitted)
    st.just('a = "\\u0000"'),
    st.just('a = "\\U00000000"'),
    # CRLF and tab indentation
    st.just("a = 1\r\nb = 2\r\n"),
    st.just("\ta = 1\n\tb = 2\n"),
    # super-table after sub-table
    st.just("[a.b]\nc = 1\n[a]\nd = 2\n"),
    # long key
    st.just("k" * 10000 + " = 1"),
    # no trailing newline
    st.just("a = 1"),
    # empty quoted key
    st.just('"" = 1'),
    # multiline arrays with comments
    st.just("a = [\n  1, # one\n  2, # two\n]\n"),
    # mixed-type array
    st.just('a = [1, "two", 3.0, true, 1979-05-27, [1], {b = 2}]'),
    # inline table trailing comma (accepted)
    st.just("a = {b = 1,}"),
    # calendar-invalid date (accepted)
    st.just("a = 1979-02-30"),
    # leading zero integer (accepted)
    st.just("a = 007"),
    # float forms (accepted)
    st.just("a = 1."),
    st.just("a = .5"),
    # raw control char in string (accepted)
    st.just('a = "x' + "\x01" + 'y"'),
    # deep nesting in band
    _DEEP_DEPTH.map(_deep_array),
    _DEEP_DEPTH.map(_deep_inline_table),
)