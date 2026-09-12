from hypothesis import strategies as st
import json

# ---------- primitive building blocks ----------

# Safe code points allowed unescaped inside strings (excluding " \ and controls)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

# Raw control / NUL bytes that the parser faithfully handles when embedded.
_control_bytes = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\x7f", "\t", "\n", "\r"]
)

_hex = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        # plain \uXXXX
        return "\\u" + "".join(draw(_hex) for _ in range(4))
    if kind == 1:
        # high surrogate
        return "\\u" + draw(st.sampled_from("dD")) + draw(st.sampled_from("89abAB")) + "".join(draw(_hex) for _ in range(2))
    if kind == 2:
        # low surrogate
        return "\\u" + draw(st.sampled_from("dD")) + draw(st.sampled_from("cdefCDEF")) + "".join(draw(_hex) for _ in range(2))
    # surrogate pair
    return (
        "\\u"
        + draw(st.sampled_from("dD"))
        + draw(st.sampled_from("89abAB"))
        + "".join(draw(_hex) for _ in range(2))
        + "\\u"
        + draw(st.sampled_from("dD"))
        + draw(st.sampled_from("cdefCDEF"))
        + "".join(draw(_hex) for _ in range(2))
    )


_simple_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# STRING content: mixture of safe chars, escapes, unicode escapes, controls, NUL
_string_piece = st.one_of(
    _safe_chars,
    _simple_escape,
    _unicode_escape(),
    _control_bytes,
)

_string_content = st.lists(_string_piece, min_size=0, max_size=12).map("".join)


@st.composite
def _string(draw):
    body = draw(_string_content)
    # Occasionally emit an unterminated string (near-valid-but-malformed).
    if draw(st.integers(min_value=0, max_value=19)) == 0:
        return '"' + body
    return '"' + body + '"'


# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_plain_int = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", min_size=0, max_size=6)).map("".join),
)

# extreme magnitudes / exponents
_extreme_int = st.sampled_from(
    [
        "1",
        "9" * 20,
        "1" + "0" * 100,
        "1" + "0" * 308,
        "1" + "0" * 309,
        "1" + "0" * 400,
        "9" * 500,
    ]
)

_fraction = st.tuples(
    st.just("."),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map("".join)

_exponent = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map("".join)

_extreme_exp = st.sampled_from(["e309", "E309", "e400", "E-400", "e+999", "e01", "E-0001"])


@st.composite
def _number(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        # lone minus (accepted by parser)
        return "-"
    if choice == 1:
        # overflow magnitude
        return draw(_extreme_int) + draw(st.one_of(st.just(""), _extreme_exp))
    if choice == 2:
        # leading-zero malformed
        return draw(st.tuples(st.just("0"), st.text(alphabet="0123456789", min_size=1, max_size=3)).map("".join))
    if choice == 3:
        # leading plus malformed
        return "+" + draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
    if choice == 4:
        # leading dot malformed
        return "." + draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
    if choice == 5:
        # trailing dot malformed
        return draw(_plain_int) + "."
    if choice == 6:
        # hex-ish malformed
        return "0x" + draw(st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=4))
    # well-formed number with optional sign, fraction, exponent
    sign = draw(st.sampled_from(["", "-"]))
    int_part = draw(_plain_int)
    frac = draw(st.one_of(st.just(""), _fraction))
    exp = draw(st.one_of(st.just(""), _exponent))
    return sign + int_part + frac + exp


# ---------- recursive value/obj/arr ----------

_json_value = st.deferred(lambda: _value())


@st.composite
def _pair(draw):
    key = draw(_string())
    sep = draw(st.sampled_from([":", ":", ":", ": ", ""]))  # occasionally missing colon
    val = draw(_json_value)
    return key + sep + val


@st.composite
def _obj(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    if n == 0:
        return "{}"
    pairs = [draw(_pair()) for _ in range(n)]
    body = ",".join(pairs)
    # occasionally a single trailing comma
    if draw(st.integers(min_value=0, max_value=4)) == 0:
        body = body + ","
    return "{" + body + "}"


@st.composite
def _arr(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    if n == 0:
        return "[]"
    items = [draw(_json_value) for _ in range(n)]
    body = ",".join(items)
    if draw(st.integers(min_value=0, max_value=4)) == 0:
        body = body + ","
    return "[" + body + "]"


@st.composite
def _value(draw):
    return draw(
        st.one_of(
            _string(),
            _number(),
            _obj(),
            _arr(),
            st.just("true"),
            st.just("false"),
            st.just("null"),
        )
    )


# ---------- malformed / near-valid shapes ----------

_malformed = st.one_of(
    # double commas
    st.just("[1,,2]"),
    st.just("{\"a\":1,,\"b\":2}"),
    st.just("[,]"),
    st.just("[,1]"),
    # missing colon / bare keys
    st.just("{\"a\" 1}"),
    st.just("{a:1}"),
    # unterminated string
    st.just("\"abc"),
    st.just("{\"a\":\"unterminated}"),
    # trailing garbage after complete value
    st.just("1abc"),
    st.just("[]xyz"),
    st.just("true false"),
    # single quotes / comments
    st.just("'x'"),
    st.just("//x\n1"),
    st.just("/* c */1"),
    # stray delimiters
    st.just("}"),
    st.just("]"),
    st.just("{"),
    st.just("["),
    st.just(":"),
    st.just(","),
    # embedded NUL / control
    st.just("\x00"),
    st.just("{\x00:1}"),
    st.just("[1,\x002]"),
    st.just("\"\x00\""),
    st.just("\"\x01\x02\x1f\""),
)


# ---------- top-level strategy ----------

_deep_nesting = st.integers(min_value=1, max_value=30)


@st.composite
def _deep(draw):
    depth = draw(_deep_nesting())
    opener = draw(st.sampled_from(["[", "{"]))
    closer = "]" if opener == "[" else "}"
    if opener == "[":
        inner = "1"
        return "[" * depth + inner + "]" * depth
    # deeply nested objects with a member at the core (stresses first pass)
    return "{" + "\"a\":{" * depth + "1" + "}" * depth + "}"


def _join(seq):
    return "".join(seq)


strategy = st.one_of(
    _value(),
    _deep(),
    _malformed,
    # objects with members are the stressed path: bias toward them
    _obj(),
    _obj(),
    _obj(),
    _arr(),
    st.lists(_value(), min_size=0, max_size=4).map(lambda xs: ",".join(xs)),
    st.text(alphabet=" \t\n\r", min_size=0, max_size=4),
).map(lambda s: s if isinstance(s, str) else str(s))