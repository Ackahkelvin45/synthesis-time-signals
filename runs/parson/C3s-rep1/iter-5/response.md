```python
from hypothesis import strategies as st
import json

# ---------- leaf / scalar strategies ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.text(alphabet=_hex, min_size=4, max_size=4)

def _escape():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    uni = st.builds(lambda h: "\\u" + h, _hex4())
    return st.one_of(simple, uni)

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
                         '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

def _string_body():
    return st.one_of(
        st.text(alphabet=_safe_char, max_size=12),
        st.lists(st.one_of(_escape(), st.text(alphabet=_safe_char, max_size=4)),
                 max_size=6).map("".join),
    )

_string = _string_body().map(lambda s: '"' + s + '"')

# strings that stress surrogate / unicode escapes and control escapes
_surrogate_string = st.one_of(
    st.just('"\\uD800"'),
    st.just('"\\uDFFF"'),
    st.just('"\\uD834\\uDD1E"'),
    st.just('"\\u0000"'),
    st.just('"\\u001f"'),
    st.just('"\\uFFFF"'),
    st.builds(lambda a, b: '"' + "\\u" + a + "\\u" + b + '"', _hex4(), _hex4()),
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        st.builds(lambda d, r: d + r, st.sampled_from("123456789"),
                  st.text(alphabet="0123456789", max_size=6)),
    )

def _number():
    sign = st.sampled_from(["", "-"])
    frac = st.one_of(st.just(""), st.builds(lambda d: "." + d, _digits))
    exp = st.one_of(
        st.just(""),
        st.builds(lambda e, s, d: e + s + d,
                  st.sampled_from("eE"),
                  st.sampled_from(["", "+", "-"]),
                  _digits),
    )
    normal = st.builds(lambda sg, ip, fr, ex: sg + ip + fr + ex, sign, _int_part(), frac, exp)

    extremes = st.sampled_from([
        "0", "-0", "0.0", "-0.0",
        "1e309", "-1e309", "1e308", "1e-308", "1e-400", "1e400",
        "1E+309", "9" * 20, "0." + "0" * 20 + "1",
        "1e000000000000000000001", "123456789012345678901234567890",
        "1.7976931348623157e308", "2.2250738585072014e-308",
    ])

    malformed = st.sampled_from([
        "01", "-01", "+1", ".5", "-.5", "1.", "-", "-.", "1e", "1e+",
        "0x1f", "Infinity", "-Infinity", "NaN", "--1", "1..2", "1e1.5",
        "00", "007", "1_000", "1,5",
    ])

    return st.one_of(normal, extremes, malformed)

# ---------- near-valid malformed fragments ----------

_malformed = st.sampled_from([
    "", ",", ",,", ":", "::", "{", "}", "[", "]", "{}extra", "[]x",
    '{"a":}', '{"a"}', '{"a":1,}', '{"a":1,,"b":2}', '[,]', '[1,]', '[1,,2]',
    '{"a" 1}', "{'a':1}", '{"a":1', '"unterminated', '"\\', '"\\u12"',
    '"\\x41"', "tru", "fals", "nul", "truex", "nullx", "1 2", "1abc",
    "[1 2]", "{,}", "[,]", "{\"a\":1}}", "[[[", "]]]", "1 garbage",
    "[]xyz", "truefalse", "  ", "\t\n", "/* c */ 1", "// c\n1",
])

# ---------- recursive structure ----------

def _key():
    return st.one_of(_string, _surrogate_string)

def _pair(value):
    return st.builds(lambda k, v: (k, v), _key(), value)

def _obj(value):
    return st.one_of(
        st.just("{}"),
        st.builds(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}",
                  st.lists(_pair(value), min_size=1, max_size=4)),
        # duplicate keys
        st.builds(lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
                  _key(), value, value),
    )

def _arr(value):
    return st.one_of(
        st.just("[]"),
        st.builds(lambda vs: "[" + ",".join(vs) + "]",
                  st.lists(value, min_size=1, max_size=4)),
    )

def _value_str():
    return st.one_of(
        _string,
        _surrogate_string,
        _number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _malformed,
    )

_value = st.deferred(lambda: st.one_of(
    _value_str(),
    _obj(_value),
    _arr(_value),
))

_json_doc = _value

# trailing content variants
_with_trailing = st.builds(
    lambda v, t: v + t,
    _value,
    st.sampled_from(["", " ", "\n", "garbage", "xyz", "1", "[]", "{}", "null", "true"]),
)

# ---------- depth-controlled structures near the 2048 cap ----------

def _deep(depth):
    return st.one_of(
        st.builds(lambda n: "[" * n + "]" * n, depth),
        st.builds(lambda n: "[" * n + "0" + "]" * n, depth),
        st.builds(lambda n: '{"a":' * n + "0" + "}" * n, depth),
    )

_depth_near_cap = st.one_of(
    st.integers(min_value=2000, max_value=2048),
    st.integers(min_value=1, max_value=64),
    st.integers(min_value=2049, max_value=2060),
    st.sampled_from([0, 1, 2, 3, 100, 1024, 2047, 2048, 2049, 4096]),
)

_deep_doc = _depth_near_cap.flatmap(lambda n: _deep(st.just(n)))

# unbalanced deep variants
_deep_unbalanced = st.builds(
    lambda n, m: "[" * n + "]" * m,
    st.integers(min_value=0, max_value=2050),
    st.integers(min_value=0, max_value=2050),
)

# ---------- whitespace-decorated valid docs ----------

_ws = st.text(alphabet=" \t\n\r", max_size=4)

def _ws_wrap(s):
    return st.builds(lambda a, b, c: a + b + c, _ws, st.just(s), _ws)

_ws_doc = st.one_of(
    st.builds(lambda a, b, c: a + b + c, _ws, _value, _ws),
)

# ---------- combine ----------

strategy = st.one_of(
    _value,
    _ws_doc,
    _with_trailing,
    _deep_doc,
    _deep_unbalanced,
    _malformed,
    st.just(""),
    st.just("{}"),
    st.just("[]"),
    st.just('{"k":0,"k":1}'),
    st.just('{"a":{"b":{"c":[1,2,3]}}}'),
    st.just('[{"a":1},{"b":[true,false,null]}]'),
    st.just('"\\u0000"'),
    st.just('"\\uD800\\uDC00"'),
    st.just("1e309"),
    st.just("-"),
    st.just("-.5"),
    st.just("01"),
    # --- added: exercise rarely-hit parser branches ---
    st.builds(lambda a, b: a + b, _ws, _value),   # leading whitespace only
    st.builds(lambda a, b: a + b, _value, _ws),   # trailing whitespace only
    st.builds(lambda a, b, c: a + b + c, _ws, _value, _ws),  # both sides
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("\r\n"),
    st.just(" \t\r\n"),
    st.just("[] "),
    st.just(" []"),
    st.just("{} "),
    st.just(" {}"),
    # --- added: nested whitespace, comments-like, and BOM/edge byte branches ---
    st.builds(lambda a, b, c, d, e: a + b + c + d + e,
              _ws, st.just("["), _ws, st.just("]"), _ws),
    st.builds(lambda a, b, c, d, e: a + b + c + d + e,
              _ws, st.just("{"), _ws, st.just("}"), _ws),
    st.builds(lambda a, b, c, d, e, f, g: a + b + c + d + e + f + g,
              _ws, st.just("["), _ws, _value, _ws, st.just("]"), _ws),
    st.builds(lambda a, b, c, d, e, f, g, h, i: a + b + c + d + e + f + g + h + i,
              _ws, st.just("{"), _ws, _string, _ws, st.just(":"), _ws, _value, _ws),
    st.just("\ufeff{}"),
    st.just("\ufeff[]"),
    st.just("\ufeff1"),
    st.just("\ufeff"),
    st.just("{} \n\t"),
    st.just("\n\t {}"),
    st.just("[\n\t]"),
    st.just("{\n\t}"),
    st.just("[\r\n1\r\n]"),
    st.just("{\r\n\"a\"\r\n:\r\n1\r\n}"),
    # --- added: target structural error branches the parser likely never hits ---
    st.builds(lambda n: "{" * n, st.integers(min_value=1, max_value=8)),
    st.builds(lambda n: "[" * n, st.integers(min_value=1, max_value=8)),
    st.builds(lambda n: "}" * n, st.integers(min_value=1, max_value=8)),
    st.builds(lambda n: "]" * n, st.integers(min_value=1, max_value=8)),
    st.builds(lambda a, b: a + b, st.just("["), st.just(":")),
    st.builds(lambda a, b: a + b, st.just("{"), st.just(":")),
    st.builds(lambda a, b: a + b, st.just("{"), st.just(",")),
    st.builds(lambda a, b: a + b, st.just("["), st.just(",")),
    st.builds(lambda a, b: a + b, st.just("{"), st.just("]")),
    st.builds(lambda a, b: a + b, st.just("["), st.just("}")),
    st.builds(lambda a, b: a + b, st.just("["), st.just('"')),
    st.builds(lambda a, b: a + b, st.just("{"), st.just('"')),
    st.builds(lambda a, b: a + b, st.just("["), st.just("-")),
    st.builds(lambda a, b: a + b, st.just("{"), st.just("true")),
    st.builds(lambda a, b: a + b, st.just("true"), st.just(":")),
    st.just('{"a":1,"a":}'),
    st.just('{"a":,"b":2}'),
    st.just('{"a"::1}'),
    st.just('{"a":1:2}'),
    st.just('["a" "b"]'),
    st.just('{"a" "b"}'),
    st.just('[1 2]'),
    st.just('[1:2]'),
    st.just('["\\uD800"]'),
    st.just('["\\uD800\\uD800"]'),
    st.just('{"\\uD800":1}'),
    st.just('{"a":"\\uDC00"}'),
    st.just('"\\uD800\\uDC00\\uD800"'),
    st.just('"\\uDC00\\uD800"'),
    st.just('"\\uD800x"'),
    st.just('"x\\uD800"'),
    st.just('"\\uD800\\u0041"'),
    st.just('"\\u0041\\uD800"'),
    st.just('1e+'),
    st.just('1e-'),
    st.just('1E'),
    st.just('1.e5'),
    st.just('.1e5'),
    st.just('-0e'),
    st.just('0e'),
    st.just('0e+'),
    st.just('0e-'),
    st.just('0.0e'),
    st.just('00.0'),
    st.just('-0.0e-0'),
    st.just('1.2.3'),
    st.just('1e1e1'),
    st.just('+'),
    st.just('+.'),
    st.just('e5'),
    st.just('E5'),
    st.just('.\x00'),
    st.just('\x00'),
    st.just('"a\x00b"'),
    st.just('[\x00]'),
    st.just('{\x00}'),
    st.just('\x00{}'),
    st.just('{}\x00'),
    st.just('null\x00'),
    st.just('"\\/\\/\\/"'),
    st.just('"\\b\\f\\n\\r\\t"'),
    st.just('"\\\\\\""'),
    st.just('{"":""}'),
    st.just('{"":1}'),
    st.just('[""]'),
    st.just('{"a":""}'),
    st.just('{"a":[]}'),
    st.just('{"a":{}}'),
    st.just('[[[]]]'),
    st.just('{"a":{"b":{}}}'),
    st.just('[[]]'),
    st.just('{"a":1,"b":2,"c":3,"d":4,"e":5}'),
    st.just('[1,2,3,4,5,6,7,8,9,10]'),
    # --- added: reach deeper string-escape and number-parsing branches ---
    st.builds(lambda h: '"\\u' + h + '"', _hex4()),
    st.builds(lambda h: '"\\u' + h + 'x"', _hex4()),
    st.builds(lambda h: '"x\\u' + h + '"', _hex4()),
    st.builds(lambda a, b, c: '"\\u' + a + '\\u' + b + 'x\\u' + c + '"',
              _hex4(), _hex4(), _hex4()),
    st.builds(lambda s: '{"' + s + '":' + s + '}',
              st.text(alphabet="abc", max_size=3)),
    st.builds(lambda a, b, c: "[" + a + "," + b + "," + c + "]",
              _value, _value, _value),
    st.builds(lambda a, b, c, d: "{" + a + ":" + b + "," + c + ":" + d + "}",
              _string, _value, _string, _value),
    st.builds(lambda s: s + s, _number()),
    st.builds(lambda s: s + s, _string),
    st.builds(lambda a, b: a + b, _number(), _number()),
    st.builds(lambda a, b: a + b, _string, _string),
    st.builds(lambda a, b: a + b, _value_str(), _value_str()),
    st.builds(lambda n, s: "[" * n + s + "]" * n,
              st.integers(min_value=1, max_value=30),
              _value_str()),
    st.builds(lambda n, s: '{"a":' * n + s + "}" * n,
              st.integers(min_value=1, max_value=30),
              _value_str()),
    st.builds(lambda a, b, c: a + b + c,
              st.sampled_from([" ", "\t", "\n", "\r", ""]),
              _value,
              st.sampled_from([" ", "\t", "\n", "\r", ""])),
    st.builds(lambda a, b: a + b,
              st.sampled_from(['"\\', '"\\u', '"\\uD', '"\\uD8', '"\\uD80']),
              st.sampled_from(["", "0", "00", '"', "x"])),
    st.builds(lambda a, b: a + b,
              st.sampled_from(["-", "1", "0", "1.", "1e", "1e+", "1e-"]),
              st.sampled_from(["", "e", "e+", "e-", ".", "0", "9", "x"])),
    st.builds(lambda a, b: a + b,
              st.sampled_from(["tru", "fals", "nul"]),
              st.sampled_from(["", "e", "l", "x", "0"])),
    st.builds(lambda a, b: a + b,
              st.sampled_from(["[", "{", "]", "}", ","]),
              st.sampled_from(["[", "{", "]", "}", ",", ":"])),
)
```