```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"


@st.composite
def _unicode_escape(draw):
    kind = draw(st.integers(min_value=0, max_value=7))
    if kind == 0:
        # lone surrogate
        return "\\u" + draw(st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DFFF"]))
    if kind == 1:
        # surrogate pair
        hi = draw(st.sampled_from(["d800", "d801", "dbff", "D800", "DBFF"]))
        lo = draw(st.sampled_from(["dc00", "dc01", "dfff", "DC00", "DFFF"]))
        return "\\u" + hi + "\\u" + lo
    if kind == 2:
        # reversed / broken surrogate pair
        return "\\u" + draw(st.sampled_from(["dc00", "dfff"])) + "\\u" + draw(
            st.sampled_from(["d800", "dbff"])
        )
    if kind == 3:
        # \u0000 escape (six chars, fine)
        return "\\u0000"
    if kind == 4:
        # control-ish escapes
        return draw(st.sampled_from(["\\u001f", "\\u007f", "\\uFFFF", "\\u0001", "\\u00e9"]))
    if kind == 5:
        # uppercase / mixed-case hex variants
        return "\\u" + draw(st.sampled_from(["D800", "DbFf", "dBfF", "DFFF", "dC00"]))
    if kind == 6:
        # \U-style / non-4-digit hex escaping (invalid in JSON)
        return draw(
            st.sampled_from(
                [
                    "\\U0001F600",
                    "\\u{1F600}",
                    "\\u1",
                    "\\u12",
                    "\\u123",
                    "\\u12345",
                ]
            )
        )
    # random hex
    return "\\u" + "".join(draw(st.lists(st.sampled_from(_hex), min_size=4, max_size=4)))


@st.composite
def _string_char(draw):
    kind = draw(st.integers(min_value=0, max_value=5))
    if kind == 0:
        # simple ascii, avoid quote, backslash, raw control
        return draw(
            st.text(
                alphabet=st.characters(
                    min_codepoint=0x20,
                    max_codepoint=0x7E,
                    blacklist_characters='"\\',
                ),
                min_size=1,
                max_size=4,
            )
        )
    if kind == 1:
        return draw(st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]))
    if kind == 2:
        return draw(_unicode_escape())
    if kind == 3:
        # non-ascii safe codepoint (avoid raw control chars 0x00-0x1F)
        return draw(
            st.characters(
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
                blacklist_categories=("Cs",),
                blacklist_characters='"\\',
            )
        )
    if kind == 4:
        # raw control byte other than NUL (0x01-0x1F) — invalid JSON but no raw NUL
        return chr(draw(st.integers(min_value=0x01, max_value=0x1F)))
    # invalid single-char escape (unknown escape sequence)
    return draw(st.sampled_from(["\\x", "\\'", "\\ ", "\\a", "\\v", "\\0", "\\z"]))


@st.composite
def _json_string(draw):
    body = draw(st.lists(_string_char(), max_size=8))
    return '"' + "".join(body) + '"'


# ---------- numbers ----------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_FRAC = st.one_of(
    st.just(".0"),
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
)

_EXP = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(e)),
    st.just("e309"),
    st.just("E+309"),
    st.just("e-309"),
    st.just("e01"),
    st.just("E-00"),
)

_NUMBER = st.one_of(
    _INT,
    st.builds(lambda i, f: i + f, _INT, _FRAC),
    st.builds(lambda i, e: i + e, _INT, _EXP),
    st.builds(lambda i, f, e: i + f + e, _INT, _FRAC, _EXP),
    st.just("-0"),
    st.just("-0.0"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("0.0000000000000000000000001"),
    st.just("123456789012345678901234567890"),
    st.just("1e999999999"),
    st.just("1E+308"),
    st.just("-1E-308"),
)


# ---------- malformed numbers ----------

_MALFORMED_NUMBER = st.one_of(
    st.just("01"),
    st.just("00"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("-.5"),
    st.just("-"),
    st.just("-."),
    st.just("1e"),
    st.just("1e+"),
    st.just("0x1"),
    st.just("1_000"),
    st.just("--1"),
    st.just("1..2"),
    st.just("1e1e1"),
)


# ---------- malformed strings ----------

_MALFORMED_STRING = st.one_of(
    st.just('"unterminated'),
    st.just('"trailing\\'),
    st.just('"bad\\x"'),
    st.just('"bad\\u12"'),
    st.just('"bad\\uZZZZ"'),
    st.just('"\\"'),
    st.just("'\''"),
    st.just('"'),
    st.just('"\\u"'),
)


# ---------- whitespace ----------

_WS = st.text(alphabet=" \t\n\r", max_size=3)


# ---------- recursive values ----------

_literal = st.sampled_from(["true", "false", "null"])

_leaf_value = st.one_of(_json_string(), _NUMBER, _literal)


@st.composite
def _small_value(draw):
    """Small value with no nesting; used to seed the recursive strategy."""
    return draw(st.one_of(_leaf_value, _empty_obj(), _empty_arr(), _malformed_leaf()))


@st.composite
def _empty_obj(draw):
    ws = draw(_WS)
    return "{" + ws + "}"


@st.composite
def _empty_arr(draw):
    ws = draw(_WS)
    return "[" + ws + "]"


@st.composite
def _malformed_leaf(draw):
    return draw(st.one_of(_MALFORMED_NUMBER, _MALFORMED_STRING))


@st.composite
def _pair(draw):
    key = draw(_json_string())
    ws1 = draw(_WS)
    ws2 = draw(_WS)
    val = draw(_small_value())
    return key + ws1 + ":" + ws2 + val


@st.composite
def _obj(draw):
    ws1 = draw(_WS)
    ws2 = draw(_WS)
    ws3 = draw(_WS)
    pair = draw(_pair())
    # sometimes duplicate a key to exercise the parser's duplicate-key rejection
    if draw(st.booleans()):
        dup_key = draw(_json_string())
        dup_val = draw(_small_value())
        return "{" + ws1 + pair + ws2 + "," + ws3 + dup_key + ":" + dup_val + "}"
    return "{" + ws1 + pair + ws2 + "}"


@st.composite
def _arr(draw):
    ws1 = draw(_WS)
    ws2 = draw(_WS)
    val = draw(_small_value())
    return "[" + ws1 + val + ws2 + "]"


def _value_strategy():
    return st.recursive(
        _small_value(),
        lambda children: st.one_of(
            st.builds(
                lambda ws1, ws2, ws3, items: "{"
                + ws1
                + ",".join(items)
                + ws2
                + ws3
                + "}",
                _WS,
                _WS,
                _WS,
                st.lists(children, min_size=1, max_size=4),
            ),
            st.builds(
                lambda ws1, ws2, ws3, items: "["
                + ws1
                + ",".join(items)
                + ws2
                + ws3
                + "]",
                _WS,
                _WS,
                _WS,
                st.lists(children, min_size=1, max_size=4),
            ),
        ),
        max_leaves=12,
    )


# ---------- deep nesting near the 2048 cap ----------

@st.composite
def _deep_nesting(draw):
    depth = draw(
        st.one_of(
            st.integers(min_value=2000, max_value=2048),
            st.integers(min_value=1800, max_value=2100),
            st.just(2047),
            st.just(2048),
            st.just(2049),
            st.just(2050),
        )
    )
    open_c = draw(st.sampled_from(["[", "{"]))
    if open_c == "[":
        close_c = "]"
        inner = draw(st.one_of(st.just("0"), st.just('"x"'), st.just("null")))
    else:
        close_c = "}"
        inner = draw(st.one_of(st.just('"k":0'), st.just('"k":null')))
    return open_c * depth + inner + close_c * depth


# ---------- malformed structures ----------

@st.composite
def _malformed_structure(draw):
    kind = draw(st.integers(min_value=0, max_value=11))
    if kind == 0:
        return '{"a":1,}'
    if kind == 1:
        return "[1,2,]"
    if kind == 2:
        return '{,"a":1}'
    if kind == 3:
        return "[,1]"
    if kind == 4:
        return '{"a" 1}'
    if kind == 5:
        return '{:1}'
    if kind == 6:
        return '{"a":}'
    if kind == 7:
        return "[1 2]"
    if kind == 8:
        return '{"a":1 "b":2}'
    if kind == 9:
        return "{'a':1}"
    if kind == 10:
        return "[]]"
    return "[}"


# ---------- trailing content (accepted by the parser) ----------

_TRAILING = st.one_of(
    st.just("abc"),
    st.just(" garbage"),
    st.just("xyz"),
    st.just("0"),
    st.just("{}"),
    st.just("]"),
    st.just("}"),
    st.just("\x00"),  # placeholder replaced below
    st.just(" /* c */"),
    st.just(" // c"),
)


@st.composite
def _with_trailing(draw):
    base = draw(_value_strategy())
    tail = draw(_TRAILING)
    if tail == "\x00":
        tail = draw(st.sampled_from(["", " ", "x", "1"]))
    return base + tail


# ---------- top-level ----------

@st.composite
def _json_document(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        return draw(_value_strategy())
    if kind == 1:
        return draw(_deep_nesting())
    if kind == 2:
        return draw(_malformed_structure())
    if kind == 3:
        return draw(_with_trailing())
    if kind == 4:
        return draw(_empty_obj())
    if kind == 5:
        return draw(_empty_arr())
    if kind == 6:
        return draw(_malformed_leaf())
    if kind == 7:
        # duplicate keys explicitly
        return draw(
            st.one_of(
                st.just('{"k":0,"k":1}'),
                st.just('{"a":1,"b":2,"a":3}'),
                st.just('{"x":{"y":1},"x":2}'),
            )
        )
    if kind == 8:
        # extreme numbers directly
        return draw(_NUMBER)
    return draw(_json_string())


@st.composite
def _maybe_ws_wrapped(draw):
    s = draw(_json_document())
    pre = draw(_WS)
    post = draw(_WS)
    return pre + s + post


def _strip_raw_nul(s: str) -> str:
    # Safety net: the harness skips inputs containing a raw NUL.
    return s.replace("\x00", "")


strategy = _maybe_ws_wrapped().map(_strip_raw_nul)
```