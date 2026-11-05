```python
import json
from hypothesis import strategies as st

# ---------- leaf pieces ----------

_hex = "0123456789abcdefABCDEF"

def _hex4(draw):
    return "".join(draw(st.sampled_from(_hex)) for _ in range(4))

_unicode_escape = st.builds(_hex4).map(lambda h: "\\u" + h)

# surrogate escapes and a few interesting unicode escapes
_special_unicode = st.sampled_from([
    "\\u0000",
    "\\uD800",
    "\\uDC00",
    "\\uD83D\\uDE00",
    "\\uFFFF",
    "\\u00e9",
    "\\u0041",
])

_short_escape = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# safe code points: avoid raw NUL and control chars; avoid quote/backslash handled by escapes
_safe_char = st.characters(
    whitelist_categories=("Lu", "Ll", "Lt", "Lm", "Lo", "Nd", "Nl", "No",
                          "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po", "Sm", "Sc", "Sk", "So"),
    blacklist_characters='"\u0000',
)

_string_body_piece = st.one_of(
    _safe_char,
    _short_escape,
    _unicode_escape,
    _special_unicode,
)

def _string(draw):
    n = draw(st.integers(min_value=0, max_value=12))
    body = "".join(draw(_string_body_piece) for _ in range(n))
    return '"' + body + '"'

_string_strategy = st.builds(lambda: None).flatmap(lambda _: st.builds(_string))

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=10, max_value=10**30).map(str),
    st.integers(min_value=1, max_value=10**300).map(str),
)

_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**20).map(lambda x: "." + str(x)),
)

_exp_part = st.one_of(
    st.just(""),
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(abs(e))),
    st.sampled_from(["e309", "e308", "e-309", "e9999", "e-9999", "e01", "E+0"]),
)

_sign = st.one_of(st.just(""), st.just("-"))

def _number(draw):
    return draw(_sign) + draw(_int_part) + draw(_frac_part) + draw(_exp_part)

_number_strategy = st.builds(_number)

# malformed / edge numbers
_malformed_number = st.sampled_from([
    "-", "-.", "+1", ".5", "01", "00", "1.", "-01", "1e", "1e+", "1e-",
    "0x10", "Infinity", "NaN", "-Infinity", "1.2.3", "--1",
])

# ---------- recursive value ----------

_ws = st.sampled_from(["", "", "", " ", "\t", "\n", "\r\n"])

_key = _string_strategy

def _pair(draw, value):
    k = draw(_key)
    ws1 = draw(_ws)
    ws2 = draw(_ws)
    v = draw(value)
    return k + ws1 + ":" + ws2 + v

def _obj(draw, value):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{}"
    sep = draw(st.sampled_from([",", ", ", " ,"]))
    parts = [_pair(draw, value) for _ in range(n)]
    return "{" + sep.join(parts) + "}"

def _arr(draw, value):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return "[]"
    sep = draw(st.sampled_from([",", ", ", " ,"]))
    parts = [draw(value) for _ in range(n)]
    return "[" + sep.join(parts) + "]"

def _make_value():
    return st.recursive(
        st.one_of(
            _string_strategy,
            _number_strategy,
            st.sampled_from(["true", "false", "null"]),
            _malformed_number,
        ),
        lambda children: st.one_of(
            st.builds(_obj, children),
            st.builds(_arr, children),
        ),
        max_leaves=40,
    )

_value = _make_value()

# ---------- deep nesting near the 2048 limit ----------

def _deep(draw):
    depth = draw(st.integers(min_value=2000, max_value=2048))
    opener, closer = draw(st.sampled_from([("[", "]"), ("{\"k\":", "}")]))
    # build nested structure
    if opener == "[":
        return "[" * depth + "]" * depth
    else:
        return "{\"k\":" * depth + "null" + "}" * depth

_deep_strategy = st.builds(_deep)

# ---------- malformed whole documents ----------

_malformed_doc = st.sampled_from([
    "[,]", "[1,,2]", "{\"a\":1,}", "{,}", "{\"a\" 1}", "{\"a\":}",
    "[1 2]", "{\"a\":1 \"b\":2}", "\"unterminated", "[1,2", "{\"a\":1",
    "tru", "fals", "nul", "[", "]", "{", "}", ":", ",",
    "{\"a\":1}garbage", "1abc", "[]xyz", "null trailing",
])

# ---------- top-level strategy ----------

def _document(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        return draw(_deep_strategy)
    if choice == 1:
        return draw(_malformed_doc)
    if choice == 2:
        # duplicate keys
        k = draw(_string_strategy)
        v1 = draw(_value)
        v2 = draw(_value)
        return "{" + k + ":" + v1 + "," + k + ":" + v2 + "}"
    if choice == 3:
        # extreme exponent
        return draw(st.sampled_from(["1e309", "-1e309", "1e400", "1e-400", "1e999999"]))
    if choice == 4:
        # empty containers
        return draw(st.sampled_from(["{}", "[]", "[{}]", "{\"a\":[]}", "[[[]]]"]))
    # normal value, optionally with trailing content
    v = draw(_value)
    if draw(st.booleans()):
        return v + draw(st.sampled_from(["", " ", "x", "garbage", "1"]))
    return v

strategy = st.builds(_document)
```