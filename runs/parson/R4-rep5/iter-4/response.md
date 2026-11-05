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
    # control-char escapes that exercise the serializer's \\u00XX cases
    st.builds(lambda h: "\\u00" + h, st.text(alphabet="0123456789abcdef", min_size=2, max_size=2)),
    # all single-byte \u00XX escapes to hit every serializer switch branch
    st.builds(lambda h: "\\u00" + h, st.sampled_from(
        ["%02x" % c for c in range(0x00, 0x20)]
    )),
    # every control escape in one string, to sweep the serializer switch
    st.just("".join("\\u%04x" % c for c in range(0x00, 0x20))),
)

# safe code points (no raw control chars, no raw NUL, no quote/backslash)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) >= 0x20 or c in "\t\n\r")

# raw control characters as literal bytes inside a string body are invalid
# JSON, but they exercise the serializer / validator's handling of them when
# they appear in decoded values; keep them rare and only via escapes above.

_string_body = st.lists(
    st.one_of(_escapes, _safe_char), max_size=12
).map("".join)

_json_string = _string_body.map(lambda b: '"' + b + '"')

# strings specifically crafted to hit every branch of json_serialize_string:
# quotes, backslashes, slashes, all \b\f\n\r\t, NUL, and each \x01..\x1f.
_serialize_probe_chars = "".join(chr(c) for c in range(0x00, 0x20))
_serialize_probe = st.one_of(
    st.just('"' + "".join(
        "\\u%04x" % c for c in range(0x00, 0x20)
    ) + '"'),
    st.just('"' + "".join(
        "\\u%04x" % c for c in range(0x20, 0x7f)
    ) + '"'),
    st.just('"\\"\\\\\\/\\b\\f\\n\\r\\t"'),
    st.just('"a/b/c"'),
    st.just('"\\/\\/\\/"'),
    st.just('"' + "".join("\\u%04x" % c for c in range(0x00, 0x20)) + 'x/y"'),
    # every control char in one string, to sweep json_serialize_string
    st.just('"' + "".join("\\u%04x" % c for c in range(0x00, 0x20)) + '"'),
    # mixed escapes and slashes
    st.just('"\\u0000\\u001f/\\"\\\\\\b\\f\\n\\r\\t"'),
)

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
    _serialize_probe,
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
    st.just('"a/b"'),
    st.just('"\\u0001\\u001f"'),
    # key that exercises every serializer branch
    st.just('"' + "".join("\\u%04x" % c for c in range(0x00, 0x20)) + '"'),
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

_deep_arr = st.builds(
    lambda depth, inner: "[" * depth + inner + "]" * depth,
    st.integers(min_value=0, max_value=2060),
    st.one_of(st.just(""), st.just("0"), st.just("null")),
)

_deep_obj = st.builds(
    lambda depth: '{"a":' * depth + "0" + "}" * depth,
    st.integers(min_value=0, max_value=2060),
)

_deep = st.one_of(_deep_arr, _deep_obj)

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

_top_value = st.one_of(_value, _deep, _leaf, _malformed, _serialize_probe)

# ---------- round-trip / serialize / validate probes ----------

# Valid documents that a parser will accept and then serialize/validate/
# deep-copy/equals. These are the inputs that actually drive the uncovered
# serializer, validate, deep-copy and equals functions.
_rt_string = st.one_of(
    st.just('""'),
    st.just('"a"'),
    st.just('"a/b"'),
    st.just('"\\u0000"'),
    st.just('"\\u0001\\u001f"'),
    st.just('"\\/\\/\\/"'),
    st.just('"\\"\\\\\\/\\b\\f\\n\\r\\t"'),
    st.just('"' + "".join("\\u%04x" % c for c in range(0x00, 0x20)) + '"'),
    st.just('"' + "".join("\\u%04x" % c for c in range(0x20, 0x7f)) + '"'),
    st.just('"' + "".join("\\u%04x" % c for c in range(0x00, 0x20)) + 'x/y"'),
    _json_string,
)

_rt_leaf = st.one_of(
    _rt_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
    st.just("0"),
    st.just("-0"),
    st.just("[]"),
    st.just("{}"),
    st.just('{"a":1}'),
    st.just('[1,2,3]'),
    st.just('{"a":[1,{"b":null}],"c":true}'),
)

_rt_value = st.recursive(
    _rt_leaf,
    lambda children: st.one_of(
        st.lists(st.tuples(_rt_string, children), max_size=4)
        .map(lambda ps: _obj([_pair(k, v) for k, v in ps])),
        st.lists(children, max_size=5).map(_arr),
    ),
    max_leaves=30,
)

# A document guaranteed to be valid JSON, so the parser reaches the
# serializer / validate / deep-copy / equals code paths.
_valid_doc = st.one_of(_rt_value, _rt_leaf)

strategy = st.one_of(
    st.builds(lambda v, t: v + t, _top_value, _trailing),
    _valid_doc,
)
```