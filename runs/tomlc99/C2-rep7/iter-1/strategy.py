from hypothesis import strategies as st
import json

# ---------- primitives ----------

_ws = st.sampled_from(["", " ", "  ", "\t", " \t "])
_comment_text = st.text(
    alphabet=st.characters(blacklist_characters="\n\r\x00"), max_size=20
)
_comment = st.one_of(
    st.just(""),
    _comment_text.map(lambda s: "#" + s),
)
_comment_nl = st.one_of(
    st.just(""),
    _comment.map(lambda c: c + "\n"),
    st.just("\n"),
    st.just("\r\n"),
)

# bare-key characters (ASCII only; non-ASCII bare keys are rejected)
_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_bare_key = st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)

# escape sequences
_esc = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\u%04X" % (n & 0xFFFF)
    ),
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08X" % n
    ),
)

_basic_char = st.one_of(
    st.characters(blacklist_characters='"\\\n\r\x00'),
    _esc,
)

_basic_string = st.lists(_basic_char, max_size=10).map(
    lambda cs: '"' + "".join(cs) + '"'
)

_literal_char = st.characters(blacklist_characters="'\n\r\x00")
_literal_string = st.lists(_literal_char, max_size=10).map(
    lambda cs: "'" + "".join(cs) + "'"
)

_ml_basic_string = st.lists(
    st.one_of(_basic_char, st.just("\n")), max_size=10
).map(lambda cs: '"""' + "".join(cs) + '"""')

_ml_literal_string = st.lists(
    st.characters(blacklist_characters="\x00"), max_size=10
).map(lambda cs: "'''" + "".join(cs) + "'''")

_string = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# numbers
_dec_int = st.one_of(
    st.integers().map(str),
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.just("007"),
    st.just("+0"),
    st.just("-0"),
    st.just("1_000"),
    st.just("1_2_3"),
    st.just("99999999999999999999999999999999"),
)
_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x%X" % n),
    st.just("0xDEAD_BEEF"),
    st.just("0x0"),
)
_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2**32).map(lambda n: "0o%o" % n),
    st.just("0o7_7"),
)
_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2**32).map(lambda n: "0b" + bin(n)[2:]),
    st.just("0b1_0_1"),
)
_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.just("1."),
    st.just(".5"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("3.14"),
    st.just("1_000.000_1"),
    st.just("6.626e-34"),
    st.just("0.0"),
    st.just("+1.0"),
    st.just("1E10"),
    st.just("5e+22"),
    st.just("1e06"),
    st.just("-2E-2"),
    st.just("224_617.445_991_228"),
)
_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
_floating = st.one_of(_float, _inf_nan)

_bool = st.sampled_from(["true", "false"])

_date = st.one_of(
    st.just("1979-05-27"),
    st.just("1979-02-30"),
    st.just("0000-00-00"),
    st.just("2024-13-45"),
)
_time = st.one_of(
    st.just("07:32:00"),
    st.just("00:32:00.999999"),
    st.just("23:59:60"),
)
_datetime = st.one_of(
    st.just("1979-05-27T07:32:00Z"),
    st.just("1979-05-27T00:32:00-07:00"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("1979-05-27t07:32:00.999999+13:00"),
    _date,
    _time,
    st.just("1979-05-27T07:32:00"),
)
_date_time = _datetime

# ---------- recursive structures ----------

_key_simple = st.one_of(_bare_key, _basic_string, _literal_string)

_dotted_key = st.lists(_key_simple, min_size=2, max_size=4).map(
    lambda ks: ".".join(ks)
)

_key = st.one_of(_key_simple, _dotted_key)

# value: recursive
def _value_strategy(draw):
    return draw(_value)

_value = st.deferred(lambda: _value_impl)

_array = st.deferred(lambda: _array_impl)
_inline_table = st.deferred(lambda: _inline_table_impl)

_scalar = st.one_of(
    _string,
    _integer,
    _floating,
    _bool,
    _date_time,
)

def _array_impl(draw):
    n = draw(st.integers(min_value=0, max_value=4))
    items = [draw(_value) for _ in range(n)]
    ws = draw(_ws)
    inner = ("," + ws).join(items)
    trailing = draw(st.sampled_from(["", ","]))
    return "[" + ws + inner + trailing + ws + "]"

def _inline_table_impl(draw):
    n = draw(st.integers(min_value=0, max_value=3))
    pairs = []
    for _ in range(n):
        k = draw(_key)
        v = draw(_value)
        pairs.append(k + " = " + v)
    ws = draw(_ws)
    inner = ("," + ws).join(pairs)
    trailing = draw(st.sampled_from(["", ","]))
    return "{" + ws + inner + trailing + ws + "}"

def _value_impl(draw):
    return draw(st.one_of(_scalar, _array, _inline_table))

# ---------- document ----------

def _key_value(draw):
    k = draw(_key)
    v = draw(_value)
    c = draw(_comment)
    ws = draw(_ws)
    line = k + ws + "=" + ws + v
    if c:
        line += " " + c
    return line

def _standard_table(draw):
    k = draw(_key)
    c = draw(_comment)
    line = "[" + k + "]"
    if c:
        line += " " + c
    return line

def _array_table(draw):
    k = draw(_key)
    c = draw(_comment)
    line = "[[" + k + "]]"
    if c:
        line += " " + c
    return line

def _expression(draw):
    return draw(st.one_of(
        _key_value,
        _standard_table,
        _array_table,
        _comment,
    ))

def _document(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    lines = [draw(_expression) for _ in range(n)]
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(lines)
    if draw(st.booleans()):
        doc += sep
    return doc

# ---------- edge-case / malformed overlays ----------

def _edge_document(draw):
    choice = draw(st.integers(min_value=0, max_value=11))
    if choice == 0:
        return ""
    if choice == 1:
        return "# just a comment"
    if choice == 2:
        return 'a = "unterminated'
    if choice == 3:
        return "a = [1, 2"
    if choice == 4:
        return "a = {b = 1"
    if choice == 5:
        return "a = 1\nb = 2\nb = 3"
    if choice == 6:
        return "[t]\n[t]\n"
    if choice == 7:
        return "a = [1,,2]"
    if choice == 8:
        return "a = {b = 1\nc = 2}"
    if choice == 9:
        return 'a = "x\x01y"'
    if choice == 10:
        return "a = 1e309\nb = 007\nc = 1.\nd = .5\n"
    return "key = " + draw(_value)

def _deep_array(draw):
    depth = draw(st.integers(min_value=1500, max_value=2048))
    return "a = " + "[" * depth + "]" * depth

def _deep_inline(draw):
    depth = draw(st.integers(min_value=1500, max_value=2048))
    return "a = " + "{b = " * depth + "1" + "}" * depth

def _big_key(draw):
    n = draw(st.integers(min_value=100, max_value=10000))
    return "".join(draw(st.sampled_from(_bare_key_chars)) for _ in range(n)) + " = 1"

def _complete_doc(draw):
    return draw(_document)

strategy = st.one_of(
    _complete_doc,
    _edge_document,
    _deep_array,
    _deep_inline,
    _big_key,
)