from hypothesis import strategies as st
import json


# ---------------------------------------------------------------------------
# Basic character classes
# ---------------------------------------------------------------------------

# Characters safe for bare keys (ASCII alnum, '-', '_')
_bare_key_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)

# Non-ASCII characters for strings
_non_ascii = st.sampled_from(
    "\u00e9\u00fc\u00f1\u4e2d\u6587\u05d0\u0641\u3042\U0001F600\U0001F4A9"
)

# Control characters (raw, allowed inside strings/comments by the parser)
_control_char = st.sampled_from(
    "\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0b\x0c\x0d\x0e\x0f"
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"
)

# Escape sequences for basic strings
_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t", "\\u0041", "\\U0001F600"]
)

# Characters allowed raw inside basic strings (no quote, no backslash, no newline)
_basic_string_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\n\r'),
    _non_ascii,
    _control_char,
    _escape,
)

# Characters allowed inside literal strings (no quote, no newline)
_literal_string_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters="'\n\r"),
    _non_ascii,
    _control_char,
)

# Multiline basic string char (allows newlines)
_ml_basic_char = st.one_of(
    _basic_string_char,
    st.just("\n"),
    st.just("\r\n"),
)

# Multiline literal string char (allows newlines)
_ml_literal_char = st.one_of(
    _literal_string_char,
    st.just("\n"),
    st.just("\r\n"),
)


# ---------------------------------------------------------------------------
# Strings (all four quoting forms)
# ---------------------------------------------------------------------------

basic_string = st.lists(_basic_string_char, max_size=12).map("".join).map(
    lambda s: '"' + s + '"'
)

literal_string = st.lists(_literal_string_char, max_size=12).map("".join).map(
    lambda s: "'" + s + "'"
)

ml_basic_string = st.lists(_ml_basic_char, max_size=12).map("".join).map(
    lambda s: '"""' + s + '"""'
)

ml_literal_string = st.lists(_ml_literal_char, max_size=12).map("".join).map(
    lambda s: "'''" + s + "'''"
)

_string = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_digits = st.text("0123456789", min_size=1, max_size=20)
_dec_int = st.one_of(
    _dec_digits,
    _dec_digits.map(lambda s: "+" + s),
    _dec_digits.map(lambda s: "-" + s),
    # leading zeros (parser accepts)
    st.just("007"),
    st.just("0000"),
    # underscores
    st.just("1_000_000"),
    # extreme magnitudes
    st.just("99999999999999999999999999999999999999"),
    st.just("-99999999999999999999999999999999999999"),
    st.just("18446744073709551616"),
)

_hex_digits = st.text("0123456789abcdefABCDEF", min_size=1, max_size=16)
_hex_int = _hex_digits.map(lambda s: "0x" + s)
_oct_int = st.text("01234567", min_size=1, max_size=16).map(lambda s: "0o" + s)
_bin_int = st.text("01", min_size=1, max_size=16).map(lambda s: "0b" + s)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.just("1.0"),
    st.just("-1.0"),
    st.just("+1.0"),
    st.just("3.14159"),
    st.just("1e10"),
    st.just("1E10"),
    st.just("1e+10"),
    st.just("1e-10"),
    st.just("6.626e-34"),
    st.just("1_000.000_1"),
    # parser accepts these deviations
    st.just("1."),
    st.just(".5"),
    st.just("1.e10"),
    # extreme exponents
    st.just("1e309"),
    st.just("1e-309"),
    st.just("1e999999"),
    st.just("-1e999999"),
    st.just("0.0"),
    st.just("-0.0"),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_floating_point = st.one_of(_float, _inf_nan)


# ---------------------------------------------------------------------------
# Booleans
# ---------------------------------------------------------------------------

_boolean = st.sampled_from(["true", "false"])


# ---------------------------------------------------------------------------
# Date-times (all four forms)
# ---------------------------------------------------------------------------

_date_time = st.one_of(
    # offset date-time
    st.just("1979-05-27T07:32:00Z"),
    st.just("1979-05-27T00:32:00-07:00"),
    st.just("1979-05-27T00:32:00.999999-07:00"),
    st.just("1979-05-27 07:32:00Z"),
    # local date-time
    st.just("1979-05-27T07:32:00"),
    st.just("1979-05-27T00:32:00.999999"),
    # local date
    st.just("1979-05-27"),
    # local time
    st.just("07:32:00"),
    st.just("00:32:00.999999"),
    # calendar-invalid (parser accepts)
    st.just("1979-02-30"),
    st.just("2023-13-45"),
    st.just("0000-00-00"),
)


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.lists(_bare_key_char, min_size=1, max_size=10).map("".join)

_quoted_key = st.one_of(basic_string, literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(".".join)

_key = st.one_of(_simple_key, _dotted_key)


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# We use st.recursive to build nested arrays and inline tables.
# Depth band 1500-2048 is interesting but building that via recursive
# naturally is expensive; we add explicit deep-nesting strategies separately.

_scalar_value = st.one_of(
    _string,
    _integer,
    _floating_point,
    _boolean,
    _date_time,
)

# Comment text (raw control chars allowed by parser)
_comment_text = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",), blacklist_characters="\n\r"
        ),
        max_size=30,
    ),
    _control_char,
)

_comment = _comment_text.map(lambda s: "#" + s)

# Whitespace / newlines inside arrays
_ws = st.sampled_from(["", " ", "  ", "\t"])
_nl = st.sampled_from(["\n", "\r\n"])


def _array_from_values(values):
    """Build an array string from a list of already-rendered value strings."""
    if not values:
        return "[]"
    # Occasionally produce multiline arrays with comments and trailing comma
    sep = st.sampled_from([", ", ",\n", ", # c\n", " , "])
    # We can't use st inside a map easily; just do a simple join here.
    return "[" + ", ".join(values) + "]"


def _inline_table_from_pairs(pairs):
    """Build an inline table from a list of (key, value) rendered strings."""
    if not pairs:
        return "{}"
    body = ", ".join("{} = {}".format(k, v) for k, v in pairs)
    return "{" + body + "}"


# Recursive value strategy
_value = st.recursive(
    _scalar_value,
    lambda children: st.one_of(
        # arrays
        st.lists(children, max_size=5).map(_array_from_values),
        # inline tables
        st.lists(
            st.tuples(_key, children), max_size=4
        ).map(_inline_table_from_pairs),
    ),
    max_leaves=30,
)


# ---------------------------------------------------------------------------
# Deep nesting (band 1500-2048)
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_inline_table(depth):
    # {a = {a = {a = ... 1 ...}}}
    return "{" * depth + "a = 1" + "}" * depth


_deep_nesting = st.integers(min_value=1500, max_value=2048).flatmap(
    lambda d: st.one_of(
        st.just(_deep_array(d)),
        st.just(_deep_inline_table(d)),
    )
)

# Additional deep-nesting variants that mix arrays and inline tables, and
# place nested structures inside a key-value assignment, to push the parser
# toward the depth cap from multiple syntactic entry points.
def _deep_mixed(depth):
    """Alternate array and inline-table nesting to depth `depth`."""
    parts = []
    for i in range(depth):
        if i % 2 == 0:
            parts.append("[")
        else:
            parts.append("{a = ")
    inner = "1"
    closers = []
    for i in range(depth):
        if i % 2 == 0:
            closers.append("]")
        else:
            closers.append("}")
    return "".join(parts) + inner + "".join(reversed(closers))


_deep_nesting_cap = st.integers(min_value=1500, max_value=2048).flatmap(
    lambda d: st.one_of(
        st.just(_deep_array(d)),
        st.just(_deep_inline_table(d)),
        st.just(_deep_mixed(d)),
        st.just("a = " + _deep_array(d)),
        st.just("a = " + _deep_inline_table(d)),
        st.just("a = " + _deep_mixed(d)),
        st.just("[t]\na = " + _deep_array(d)),
        st.just("[[t]]\na = " + _deep_inline_table(d)),
    )
)


# ---------------------------------------------------------------------------
# Key-value lines
# ---------------------------------------------------------------------------

_key_value = st.tuples(_key, _value).map(
    lambda kv: "{} = {}".format(kv[0], kv[1])
)

# key-value with comment
_key_value_comment = st.tuples(_key, _value, _comment).map(
    lambda kvc: "{} = {} {}".format(kvc[0], kvc[1], kvc[2])
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

_standard_table = _key.map(lambda k: "[{}]".format(k))

_array_table = _key.map(lambda k: "[[{}]]".format(k))

# Empty table
_empty_table = st.just("[]")

# Table with comment
_table_comment = st.tuples(_standard_table, _comment).map(
    lambda tc: "{} {}".format(tc[0], tc[1])
)


# ---------------------------------------------------------------------------
# Edge cases: malformed / near-valid
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    # missing closing bracket
    st.just("[table"),
    # doubled delimiter
    st.just("[[table]]]"),
    st.just("[table]]"),
    # unterminated string
    st.just('a = "unterminated'),
    st.just("a = 'unterminated"),
    st.just('a = """unterminated'),
    st.just("a = '''unterminated"),
    # stray token
    st.just("a = = 1"),
    st.just("a = 1 2"),
    st.just("= 1"),
    st.just("a ="),
    # newline inside inline table (rejected)
    st.just("a = {b = 1,\nc = 2}"),
    # invalid escape
    st.just('a = "\\q"'),
    # value on next line
    st.just("a =\n1"),
    # bare non-ASCII key
    st.just("caf\u00e9 = 1"),
    # duplicate keys
    st.just("a = 1\na = 2"),
    # duplicate tables
    st.just("[t]\n[t]"),
    st.just("[[a]]\n[[a]]"),
    # table and array of tables same name
    st.just("[t]\n[[t]]"),
)


# ---------------------------------------------------------------------------
# Complete documents
# ---------------------------------------------------------------------------

# A line is either a key-value, a table header, a comment, or blank
_line = st.one_of(
    _key_value,
    _key_value_comment,
    _standard_table,
    _array_table,
    _table_comment,
    _comment,
    st.just(""),
)

# Multiline document: several lines
_document = st.lists(_line, min_size=0, max_size=8).map("\n".join)

# Document with trailing newline sometimes
_document_with_nl = st.one_of(
    _document,
    _document.map(lambda s: s + "\n"),
    _document.map(lambda s: s + "\r\n"),
)

# Empty document
_empty_doc = st.just("")

# Comment-only document
_comment_only = _comment.map(lambda c: c + "\n")

# Document with deep nesting
_deep_doc = _deep_nesting.map(lambda v: "a = " + v)

# Document with extreme values
_extreme_doc = st.one_of(
    st.just("a = 1e309"),
    st.just("a = -1e309"),
    st.just("a = 99999999999999999999999999999999999999"),
    st.just("a = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"),
    st.just("a = 0o777777777777777777777777777777777777"),
    st.just("a = 0b1111111111111111111111111111111111111111111111111111111111111111"),
    st.just("a = inf"),
    st.just("a = -inf"),
    st.just("a = nan"),
)

# Document with escapes and non-ASCII
_unicode_doc = st.one_of(
    st.just('a = "\\u00e9"'),
    st.just('a = "\\U0001F600"'),
    st.just('a = "caf\u00e9"'),
    st.just('a = "\u4e2d\u6587"'),
    st.just("a = '\u05d0\u0641'"),
    st.just('a = """\n\u00e9\n"""'),
    st.just("a = '''\n\u4e2d\u6587\n'''"),
)

# Document with control bytes
_control_doc = st.one_of(
    st.just('a = "x\x01y"'),
    st.just('a = "x\x7fy"'),
    st.just("a = 'x\x01y'"),
    st.just("# comment \x01\x02\n"),
)

# Document with empty containers
_empty_containers = st.one_of(
    st.just("a = []"),
    st.just("a = {}"),
    st.just("[t]"),
    st.just("[[a]]"),
    st.just('"" = 1'),
    st.just("a = {b = [], c = {}}"),
)

# Deep nesting document
_deep_doc2 = _deep_nesting.map(lambda v: "a = " + v)

# Boolean-focused documents (upweight boolean production)
_bool_doc = st.one_of(
    _boolean.map(lambda b: "a = " + b),
    st.tuples(_key, _boolean).map(lambda kb: "{} = {}".format(kb[0], kb[1])),
    st.lists(st.tuples(_key, _boolean), min_size=1, max_size=4).map(
        lambda pairs: "\n".join("{} = {}".format(k, v) for k, v in pairs)
    ),
    st.tuples(_key, _boolean, _boolean).map(
        lambda kbb: "{} = [{}, {}]".format(kbb[0], kbb[1], kbb[2])
    ),
    st.tuples(_key, _boolean).map(
        lambda kb: "{} = {{b = {}}}".format(kb[0], kb[1])
    ),
)

# Date-time-focused documents (upweight date_time production)
_date_time_doc = st.one_of(
    _date_time.map(lambda dt: "a = " + dt),
    st.tuples(_key, _date_time).map(lambda kd: "{} = {}".format(kd[0], kd[1])),
    st.lists(st.tuples(_key, _date_time), min_size=1, max_size=4).map(
        lambda pairs: "\n".join("{} = {}".format(k, v) for k, v in pairs)
    ),
    st.tuples(_key, _date_time, _date_time).map(
        lambda kdd: "{} = [{}, {}]".format(kdd[0], kdd[1], kdd[2])
    ),
    st.tuples(_key, _date_time).map(
        lambda kd: "{} = {{b = {}}}".format(kd[0], kd[1])
    ),
)


# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document_with_nl,
    _empty_doc,
    _comment_only,
    _deep_doc,
    _extreme_doc,
    _unicode_doc,
    _control_doc,
    _empty_containers,
    _malformed,
    _deep_nesting_cap,
    _bool_doc,
    _date_time_doc,
)