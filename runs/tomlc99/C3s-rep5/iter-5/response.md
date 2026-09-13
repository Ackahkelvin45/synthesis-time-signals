```python
from hypothesis import strategies as st
import json

# ---------- basic character classes ----------
# Non-NUL control bytes (raw control chars are accepted inside strings/comments)
CTRL = st.integers(min_value=1, max_value=0x1F).map(chr)
DEL = st.just("\x7f")

# Text that is safe inside strings (no raw NUL)
SAFE_TEXT_CHARS = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF),
    CTRL,
    DEL,
    st.sampled_from(list("\\\"'[]{}#=.,\t")),
)

# ---------- escapes ----------
HEX4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
HEX8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)
SHORT_ESC = st.sampled_from(list("\"\\/bfnrt"))
UNICODE_ESC = HEX4.map(lambda h: "\\u" + h)
EX_UNICODE_ESC = HEX8.map(lambda h: "\\U" + h)
ESC = st.one_of(SHORT_ESC, UNICODE_ESC, EX_UNICODE_ESC)
# a multiline escape: backslash + optional CR + newline
ML_LINE_ESC = st.one_of(
    st.just("\\\n"),
    st.just("\\\r\n"),
    ESC,
)

# ---------- keys ----------
UNQUOTED_KEY_CHARS = st.text(
    alphabet=st.sampled_from(list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")),
    min_size=1,
    max_size=8,
)
UNQUOTED_KEY = UNQUOTED_KEY_CHARS

def _basic_string_body(chars, esc):
    return st.lists(
        st.one_of(chars, esc),
        min_size=0,
        max_size=6,
    ).map("".join)

BASIC_STRING = _basic_string_body(
    st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF),
        CTRL,
        DEL,
        st.sampled_from(list("'[]{}=.,#\t")),
    ),
    ESC,
).map(lambda s: '"' + s + '"')

LITERAL_STRING = st.lists(
    st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF),
        CTRL,
        DEL,
        st.sampled_from(list("\"[]{}=.,#\t")),
    ),
    min_size=0,
    max_size=6,
).map(lambda cs: "'" + "".join(cs) + "'")

ML_BASIC_STRING = _basic_string_body(
    st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF),
        CTRL,
        DEL,
        st.sampled_from(list("'[]{}=.,#\t")),
        st.just("\n"),
        st.just("\r\n"),
    ),
    ML_LINE_ESC,
).map(lambda s: '"""' + s + '"""')

ML_LITERAL_STRING = st.lists(
    st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF),
        CTRL,
        DEL,
        st.sampled_from(list("\"[]{}=.,#\t")),
        st.just("\n"),
        st.just("\r\n"),
    ),
    min_size=0,
    max_size=6,
).map(lambda cs: "'''" + "".join(cs) + "'''")

STRING = st.one_of(BASIC_STRING, LITERAL_STRING, ML_BASIC_STRING, ML_LITERAL_STRING)

QUOTED_KEY = st.one_of(BASIC_STRING, LITERAL_STRING)
SIMPLE_KEY = st.one_of(UNQUOTED_KEY, QUOTED_KEY)
DOTTED_KEY = st.lists(SIMPLE_KEY, min_size=2, max_size=3).map(".".join)
KEY = st.one_of(SIMPLE_KEY, DOTTED_KEY)

# ---------- numbers ----------
DEC_DIGITS = st.text(alphabet="0123456789", min_size=1, max_size=6)
UNDERSCORE_INT = st.lists(
    st.text(alphabet="0123456789", min_size=1, max_size=2),
    min_size=1,
    max_size=4,
).map("_".join)

DEC_INT = st.one_of(
    st.just("0"),
    st.just("007"),
    st.just("000"),
    st.just("123456789012345678901234567890"),
    st.from_regex(r"[+-]?[0-9]{1,20}", fullmatch=True),
    st.from_regex(r"[+-]?[1-9][0-9]{0,3}(_[0-9]{2,3})*", fullmatch=True),
    st.integers(min_value=-2**70, max_value=2**70).map(str),
)

HEX_INT = st.one_of(
    st.from_regex(r"0x[0-9A-Fa-f]{1,16}", fullmatch=True),
    st.from_regex(r"0x[0-9A-Fa-f]{1,4}(_[0-9A-Fa-f]{2,3})*", fullmatch=True),
)
OCT_INT = st.one_of(
    st.from_regex(r"0o[0-7]{1,16}", fullmatch=True),
    st.from_regex(r"0o[0-7]{1,4}(_[0-7]{2,3})*", fullmatch=True),
)
BIN_INT = st.one_of(
    st.from_regex(r"0b[01]{1,16}", fullmatch=True),
    st.from_regex(r"0b[01]{1,4}(_[01]{2,3})*", fullmatch=True),
)
INTEGER = st.one_of(DEC_INT, HEX_INT, OCT_INT, BIN_INT)

FLOAT = st.one_of(
    st.just("1."),
    st.just(".5"),
    st.just("+1."),
    st.just("-0.0"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("0.0e0"),
    st.just("1_000.000_1"),
    st.from_regex(r"[+-]?[0-9]{1,3}\.[0-9]{1,6}([eE][+-]?[0-9]{1,3})?", fullmatch=True),
    st.from_regex(r"[+-]?[0-9]{1,3}[eE][+-]?[0-9]{1,3}", fullmatch=True),
    st.from_regex(r"[+-]?[0-9]_[0-9]{2,3}\.[0-9]{1,4}", fullmatch=True),
)
INF = st.sampled_from(["+inf", "-inf", "inf"])
NAN = st.sampled_from(["+nan", "-nan", "nan"])
FLOATING_POINT = st.one_of(FLOAT, INF, NAN)

BOOLEAN = st.sampled_from(["true", "false"])

# ---------- date-times ----------
D2 = st.text(alphabet="0123456789", min_size=2, max_size=2)
D4 = st.text(alphabet="0123456789", min_size=4, max_size=4)
YEAR = st.one_of(D4, st.just("0000"), st.just("9999"))
MONTH = st.one_of(D2, st.just("13"), st.just("00"))
DAY = st.one_of(D2, st.just("32"), st.just("30"))
HOUR = st.one_of(D2, st.just("24"))
MIN = st.one_of(D2, st.just("60"))
SEC = st.one_of(D2, st.just("60"))
SECFRAC = st.one_of(st.just(""), st.text(alphabet="0123456789", min_size=1, max_size=6).map(lambda s: "." + s))
DELIM = st.sampled_from(["T", "t", " "])
OFFSET = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(st.sampled_from(["+", "-"]), D2, st.just(":"), D2).map("".join),
)
PARTIAL_TIME = st.tuples(HOUR, st.just(":"), MIN, st.just(":"), SEC, SECFRAC).map("".join)
FULL_DATE = st.tuples(YEAR, st.just("-"), MONTH, st.just("-"), DAY).map("".join)
FULL_TIME = st.tuples(PARTIAL_TIME, OFFSET).map("".join)
OFFSET_DATE_TIME = st.tuples(FULL_DATE, DELIM, FULL_TIME).map("".join)
LOCAL_DATE_TIME = st.tuples(FULL_DATE, DELIM, PARTIAL_TIME).map("".join)
LOCAL_DATE = FULL_DATE
LOCAL_TIME = PARTIAL_TIME
DATE_TIME = st.one_of(OFFSET_DATE_TIME, LOCAL_DATE_TIME, LOCAL_DATE, LOCAL_TIME)

# ---------- recursive values ----------
def _array_of(value):
    # arrays can contain comments and newlines
    inner = st.one_of(
        st.lists(value, min_size=0, max_size=4).map(lambda vs: ", ".join(vs)),
        st.lists(value, min_size=1, max_size=4).map(lambda vs: ", ".join(vs) + ","),
        st.just(""),
        st.lists(value, min_size=1, max_size=3).map(
            lambda vs: "\n  " + ",\n  ".join(vs) + ",\n"
        ),
        st.lists(value, min_size=1, max_size=3).map(
            lambda vs: "# c\n" + ",\n".join(vs) + "\n# c\n"
        ),
    )
    return inner.map(lambda s: "[" + s + "]")

def _inline_table_of(value):
    pairs = st.lists(
        st.tuples(KEY, st.just(" = "), value).map("".join),
        min_size=0,
        max_size=4,
    )
    def build(ps):
        if not ps:
            return "{}"
        if len(ps) == 1:
            return "{" + ps[0] + "}"
        return "{" + ", ".join(ps) + "}"
    return pairs.map(build)

VALUE = st.recursive(
    st.one_of(STRING, INTEGER, FLOATING_POINT, BOOLEAN, DATE_TIME),
    lambda children: st.one_of(
        _array_of(children),
        _inline_table_of(children),
    ),
    max_leaves=40,
)

# ---------- near-valid-but-malformed fragments ----------
MALFORMED_VALUE = st.one_of(
    # unterminated strings
    st.just('"unterminated'),
    st.just("'unterminated"),
    st.just('"""unterminated'),
    st.just("'''unterminated"),
    # invalid escape
    st.just('"bad\\q"'),
    st.just('"bad\\x41"'),
    # stray tokens
    st.just("="),
    st.just(","),
    st.just("]"),
    st.just("}"),
    st.just("."),
    st.just(":"),
    # doubled delimiters
    st.just("[["),
    st.just("]]"),
    st.just("{{"),
    st.just("}}"),
    st.just("=="),
    st.just(",,"),
    # one missing delimiter
    st.just("[1, 2"),
    st.just("{a = 1"),
    st.just('"abc'),
    st.just("a = "),
)

# ---------- documents ----------
def _kv(key, value):
    return st.tuples(key, st.just(" = "), value).map("".join)

def _comment():
    return st.one_of(
        st.just("#"),
        st.lists(
            st.one_of(
                st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF),
                CTRL,
                DEL,
                st.sampled_from(list("\t")),
            ),
            min_size=0,
            max_size=20,
        ).map(lambda cs: "#" + "".join(cs)),
    )

KV_LINE = st.one_of(
    st.tuples(KEY, st.just(" = "), VALUE).map("".join),
    st.tuples(KEY, st.just("="), VALUE).map("".join),
)

TABLE_LINE = st.one_of(
    st.tuples(st.just("["), KEY, st.just("]")).map("".join),
    st.tuples(st.just("[["), KEY, st.just("]]")).map("".join),
)

MALFORMED_LINE = st.one_of(
    st.tuples(KEY, st.just(" = "), MALFORMED_VALUE).map("".join),
    MALFORMED_VALUE,
    st.just("[bad"),
    st.just("[[bad]"),
    st.just("bad = "),
    st.just("= 1"),
    st.just("[]"),
    st.just("[[]]"),
)

LINE = st.one_of(KV_LINE, TABLE_LINE, _comment(), MALFORMED_LINE)

def _join_lines(lines):
    if not lines:
        return ""
    # sometimes use CRLF, sometimes no trailing newline
    return "\n".join(lines)

DOCUMENT = st.one_of(
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("# c\n"),
    st.lists(LINE, min_size=1, max_size=8).map(_join_lines),
    st.lists(LINE, min_size=1, max_size=6).map(lambda ls: "\n".join(ls) + "\n"),
    st.lists(LINE, min_size=1, max_size=6).map(lambda ls: "\r\n".join(ls)),
    st.lists(LINE, min_size=1, max_size=6).map(lambda ls: "\n".join(ls) + "\n# done"),
)

# ---------- deep nesting band (1500-2048) ----------
DEEP_DEPTH = st.integers(min_value=1500, max_value=2048)

DEEP_ARRAY = DEEP_DEPTH.map(lambda n: "[" * n + "]" * n)
DEEP_INLINE = DEEP_DEPTH.map(lambda n: "{a = " * n + "1" + "}" * n)
DEEP_MIXED = DEEP_DEPTH.map(lambda n: "[{a = " * (n // 2) + "1" + "}]" * (n // 2))

DEEP_DOC = st.one_of(
    DEEP_ARRAY.map(lambda s: "deep = " + s),
    DEEP_INLINE.map(lambda s: "deep = " + s),
    DEEP_MIXED.map(lambda s: "deep = " + s),
)

# ---------- big key ----------
BIG_KEY = st.just("k" * 10000)

# ---------- additional malformed / edge fragments to reach uncovered branches ----------
EXTRA_MALFORMED = st.one_of(
    # bare CR and CRLF handling in comments/whitespace
    st.just("a = 1\r\nb = 2"),
    st.just("a = 1\rb = 2"),
    st.just("\r\n\r\n"),
    st.just("\r"),
    # tab / vertical whitespace around key and value
    st.just("\ta = 1"),
    st.just("a\t=\t1"),
    st.just("a = 1\t"),
    st.just("\v\f"),
    # empty / whitespace-only keys and weird key separators
    st.just(" = 1"),
    st.just("\t= 1"),
    st.just("a b = 1"),
    st.just(". = 1"),
    st.just("a. = 1"),
    st.just(".a = 1"),
    st.just("a..b = 1"),
    st.just("a. b = 1"),
    # table header variants
    st.just("[a.b.c]"),
    st.just("[ a . b ]"),
    st.just("[a.b]"),
    st.just("[[a.b]]"),
    st.just("[[[a]]]"),
    st.just("[a]]"),
    st.just("[[a]"),
    st.just("[.]"),
    st.just("[]"),
    st.just("[ ]"),
    st.just("[a.]"),
    st.just("[.a]"),
    # duplicate keys / redefinition
    st.just("a = 1\na = 2"),
    st.just("[t]\na = 1\n[t]\na = 2"),
    st.just("a = 1\n[a]\nb = 2"),
    # inline table edge cases
    st.just("a = {}"),
    st.just("a = { }"),
    st.just("a = {b = 1,}"),
    st.just("a = {,}"),
    st.just("a = {b = 1 c = 2}"),
    st.just("a = {b = }"),
    st.just("a = {= 1}"),
    # array edge cases
    st.just("a = []"),
    st.just("a = [ ]"),
    st.just("a = [,]"),
    st.just("a = [1 2]"),
    st.just("a = [1,,2]"),
    st.just("a = [1,2,]"),
    st.just("a = [1,2"),
    st.just("a = 1,2]"),
    # number edge cases
    st.just("a = 0x"),
    st.just("a = 0o"),
    st.just("a = 0b"),
    st.just("a = 0x_1"),
    st.just("a = 0x1_"),
    st.just("a = 1__2"),
    st.just("a = _1"),
    st.just("a = 1_"),
    st.just("a = 1."),
    st.just("a = ."),
    st.just("a = 1.e"),
    st.just("a = 1e"),
    st.just("a = 1e+"),
    st.just("a = +"),
    st.just("a = -"),
    st.just("a = ++1"),
    st.just("a = 0_0"),
    # datetime edge cases
    st.just("a = 2021-01-01T"),
    st.just("a = 2021-01-01T00"),
    st.just("a = 2021-01-01T00:"),
    st.just("a = 2021-01-01T00:00"),
    st.just("a = 2021-01-01T00:00:"),
    st.just("a = 2021-01-01T00:00:00."),
    st.just("a = 2021-01-01T00:00:00+"),
    st.just("a = 2021-01-01T00:00:00+0"),
    st.just("a = 2021-01-01T00:00:00+00:"),
    st.just("a = 2021-13-32T24:60:60Z"),
    st.just("a = 2021-01-01"),
    st.just("a = 00:00:00"),
    st.just("a = 2021-01-01 00:00:00"),
    st.just("a = 2021-01-01t00:00:00z"),
    st.just("a = 2021-01-01T00:00:00-00:00"),
    # string edge cases
    st.just('a = "\\u"'),
    st.just('a = "\\u12"'),
    st.just('a = "\\U0000"'),
    st.just('a = "\\U0000000"'),
    st.just('a = "\\U00110000"'),
    st.just('a = "\\uD800"'),
    st.just('a = ""'),
    st.just("a = ''"),
    st.just('a = """"""'),
    st.just("a = ''''''"),
    st.just('a = """x""'),
    st.just("a = '''x''"),
    st.just('a = "line\\\ncont"'),
    st.just('a = "line\\\r\ncont"'),
    st.just('a = """line\\\ncont"""'),
    st.just("a = 'has \" quote'"),
    st.just('a = "has \' quote"'),
    # comment edge cases
    st.just("#"),
    st.just("#\n"),
    st.just("# comment\r\n"),
    st.just("# comment\r"),
    st.just("a = 1 # trailing"),
    st.just("a = 1# trailing"),
    st.just("a = 1 # trailing\r\nb = 2"),
    # bare tokens / garbage
    st.just("garbage"),
    st.just("1"),
    st.just("true"),
    st.just("@"),
    st.just("$"),
    st.just("\\"),
    st.just("a = @"),
    st.just("a = '"),
    st.just('a = "'),
    st.just("a = ["),
    st.just("a = {"),
    st.just("a = ]"),
    st.just("a = }"),
    st.just("a = #"),
)

DOCUMENT_WITH_EXTREMES = st.one_of(
    DOCUMENT,
    DEEP_DOC,
    st.tuples(BIG_KEY, st.just(" = 1")).map("".join),
    st.tuples(st.just("x = "), VALUE).map("".join),
    EXTRA_MALFORMED,
)

strategy = DOCUMENT_WITH_EXTREMES
```