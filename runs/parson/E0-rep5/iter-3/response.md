EDIT: add_or_upweight_production

```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

def _hex_digits(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

# escapes that are valid inside a JSON string
_escapes = st.one_of(
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    st.builds(lambda h: "\\u" + h, _hex_digits(4)),
    # surrogate escapes (lone and paired)
    st.builds(lambda h: "\\u" + h, st.sampled_from(
        ["D800", "DBFF", "DC00", "DFFF", "d800", "dc00", "D834", "DD1E"])),
    st.builds(lambda a, b: "\\u" + a + "\\u" + b,
              _hex_digits(4), _hex_digits(4)),
    # embedded NUL escape (six chars, safe)
    st.just("\\u0000"),
)

# safe code points (no raw control chars, no raw NUL, no quote/backslash)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) >= 0x20 or c in "\t\n\r")

_string_body = st.lists(
    st.one_of(_escapes, _safe_char), max_size=12
).map("".join)

_json_string = _string_body.map(lambda b: '"' + b + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d, r: d + r,
              st.sampled_from("123456789"),
              st.text(alphabet="0123456789", max_size=6)),
)

_frac = st.builds(lambda d: "." + d, _digits)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + fr + ex,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

# extreme magnitudes / exponents
_extreme_number = st.one_of(
    st.just("1e309"), st.just("-1e309"), st.just("1e-309"),
    st.just("1e999999"), st.just("-1e999999"),
    st.just("1" + "0" * 400),
    st.just("0." + "0" * 300 + "1"),
    st.just("1e308"), st.just("1.7976931348623157e308"),
    st.just("-1.7976931348623157e308"), st.just("1e-400"),
    st.builds(lambda d: "1e" + d, st.text(alphabet="0123456789", min_size=1, max_size=10)),
    st.builds(lambda d: "-1e-" + d, st.text(alphabet="0123456789", min_size=1, max_size=10)),
)

# malformed numeric-ish tokens
_bad_number = st.one_of(
    st.just("+1"), st.just(".5"), st.just("1."), st.just("01"),
    st.just("-01"), st.just("00"), st.just("-"), st.just("-."),
    st.just("1e"), st.just("1e+"), st.just("--1"), st.just("1..2"),
    st.builds(lambda d: "0" + d, _digits),
)

# ---------- malformed fragments ----------

_unterminated_string = st.builds(
    lambda b: '"' + b,
    _string_body,
)

_malformed = st.one_of(
    _unterminated_string,
    st.just("{"),
    st.just("["),
    st.just("}"),
    st.just("]"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{"a":1,}'),
    st.just('[1,]'),
    st.just('[,]'),
    st.just('[1,,2]'),
    st.just('{,}'),
    st.just('{"a":1 "b":2}'),
    st.just('{"a" 1}'),
    st.just('{"a":1,,"b":2}'),
    st.just('"\\u12"'),
    st.just('"\\u"'),
    st.just('"\\q"'),
    st.just('tru'),
    st.just('nul'),
    st.just('fals'),
    st.just('True'),
)

# ---------- recursive values ----------

_leaf = st.one_of(
    _json_string,
    _number,
    _extreme_number,
    st.sampled_from(["true", "false", "null"]),
    _bad_number,
    _malformed,
)

_key = st.one_of(
    _json_string,
    st.just('""'),
    st.just('"k"'),
    st.just('"key"'),
    st.just('"\\u0000"'),
    st.just('"\\uD800"'),
)

def _pair(key, value):
    return key + ":" + value

def _obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _arr(items):
    return "[" + ",".join(items) + "]"

# value strategy (recursive)
_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.lists(st.tuples(_key, children), max_size=4)
        .map(lambda ps: _obj([_pair(k, v) for k, v in ps])),
        st.lists(children, max_size=5).map(_arr),
    ),
    max_leaves=40,
)

# ---------- deep nesting near the 2048 cap ----------

_deep_near_cap = st.builds(
    lambda depth, inner: "[" * depth + inner + "]" * depth,
    st.integers(min_value=2000, max_value=2060),
    st.one_of(st.just(""), st.just("0"), st.just('"x"')),
)

_deep_arr = st.builds(
    lambda depth, inner: "[" * depth + inner + "]" * depth,
    st.integers(min_value=0, max_value=2060),
    st.one_of(st.just(""), st.just("0"), st.just("null")),
)

_deep_obj = st.builds(
    lambda depth: '{"a":' * depth + "0" + "}" * depth,
    st.integers(min_value=0, max_value=2060),
)

_deep = st.one_of(_deep_arr, _deep_obj, _deep_near_cap)

# ---------- top-level: value, with optional trailing content ----------

_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("garbage"),
    st.just("abc"),
    st.just("[]xyz"),
    st.just(" /* c */"),
    st.just("//c"),
    st.just("\t\r\n"),
    st.just("1"),
)

# upweighted: whitespace-interleaved structures and empty containers,
# which JSON parsers commonly mishandle.
_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "])

_ws_value = st.builds(
    lambda l, items, r: l + "[" + ",".join(items) + "]" + r,
    _ws,
    st.lists(st.one_of(_leaf, _ws), max_size=4),
    _ws,
)

_ws_obj = st.builds(
    lambda l, pairs, r: l + "{" + ",".join(pairs) + "}" + r,
    _ws,
    st.lists(st.builds(lambda k, v: k + ":" + v, _key, _leaf), max_size=4),
    _ws,
)

_empty_containers = st.sampled_from(["[]", "{}", "[ ]", "{ }", "[\n]", "{\n}"])

_ws_production = st.one_of(_ws_value, _ws_obj, _empty_containers)

_top_value = st.one_of(
    _ws_production,
    _value,
    _deep,
    _leaf,
    _malformed,
)

strategy = st.builds(
    lambda v, t: v + t,
    _top_value,
    _trailing,
)
```