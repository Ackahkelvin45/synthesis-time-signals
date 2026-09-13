```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

HEX = "0123456789abcdefABCDEF"

def _hex4():
    return st.text(alphabet=HEX, min_size=4, max_size=4)

def _escape():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    uni = st.builds(lambda h: "\\u" + h, _hex4())
    return st.one_of(simple, uni)

def _safe_char():
    # printable-ish ASCII, no quote, no backslash, no control, no NUL
    return st.characters(
        blacklist_categories=("Cs", "Cc"),
        blacklist_characters='\\"\x00',
    )

def _string_body():
    return st.one_of(
        st.text(alphabet=st.characters(
            blacklist_categories=("Cs", "Cc"),
            blacklist_characters='\\"\x00',
        ), max_size=12),
        st.lists(st.one_of(_escape(), _safe_char()), max_size=8).map("".join),
    )

def _string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _digits():
    return st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        st.builds(lambda d, rest: d + rest,
                  st.sampled_from("123456789"),
                  st.text(alphabet="0123456789", max_size=8)),
    )

def _frac():
    return st.builds(lambda d: "." + d, _digits())

def _exp():
    return st.builds(
        lambda e, s, d: e + s + d,
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits(),
    )

def _number():
    normal = st.builds(
        lambda sign, ip, fr, ex: sign + ip + fr + ex,
        st.sampled_from(["", "-"]),
        _int_part(),
        st.one_of(st.just(""), _frac()),
        st.one_of(st.just(""), _exp()),
    )
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e999999", "-1e999999",
        "1e308", "1e-308", "123456789012345678901234567890",
        "-0", "0", "0.0", "0e0", "0E+0",
        "1e01", "1E01", "1e+00", "1e-00",
        "-1e-9999", "9" * 40, "-" + "9" * 40,
    ])
    malformed = st.sampled_from([
        "+1", ".5", "1.", "01", "-01", "00", "1e", "1e+", "1e-",
        "--1", "1..2", "1.2.3", "-", "-.", "+", ".", "1e++1",
    ])
    return st.one_of(normal, extreme, malformed)

# ---------- recursive structure ----------

def _key():
    return _string()

def _pair(depth):
    return st.builds(
        lambda k, v: k + ":" + v,
        _key(),
        _value(depth),
    )

def _obj(depth):
    if depth <= 0:
        return st.just("{}")
    inner = st.lists(_pair(depth - 1), max_size=3).map(lambda xs: ",".join(xs))
    return inner.map(lambda s: "{" + s + "}")

def _arr(depth):
    if depth <= 0:
        return st.just("[]")
    inner = st.lists(_value(depth - 1), max_size=3).map(lambda xs: ",".join(xs))
    return inner.map(lambda s: "[" + s + "]")

def _value(depth):
    if depth <= 0:
        return st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null"]),
            st.just("{}"),
            st.just("[]"),
        )
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _obj(depth),
        _arr(depth),
    )

# ---------- depth targeting near 2048 ----------

def _deep_nesting():
    # concentrate interesting depth near the 2048 cap
    depth = st.integers(min_value=1500, max_value=2048)
    opener = st.sampled_from(["[", "{"])
    closer = st.sampled_from(["]", "}"])
    return st.builds(
        lambda d, o, c: o * d + c * d,
        depth, opener, closer,
    )

def _near_cap_structured():
    # a well-formed value wrapped in many arrays, near the cap
    depth = st.integers(min_value=1500, max_value=2048)
    return st.builds(
        lambda d, v: "[" * d + v + "]" * d,
        depth,
        st.one_of(_string(), _number(), st.sampled_from(["true", "false", "null", "{}", "[]"])),
    )

# ---------- malformed / near-valid ----------

def _malformed():
    return st.sampled_from([
        # double commas
        "[1,,2]", "[,]", "{,}", "[1,2,]", "{\"a\":1,,\"b\":2}",
        # missing colons
        "{\"a\" 1}", "{\"a\"}", "{:1}", "{\"a\":}",
        # unterminated strings
        '"abc', '"', '"abc\\', '{"a":"b}',
        # trailing commas
        "[1,2,]", "{\"a\":1,}",
        # leading +/.5/01
        "+1", ".5", "1.", "01", "-01", "00", "1e", "1e+",
        # lone sign
        "-", "-.",
        # unbalanced
        "[", "]", "{", "}", "[[", "]]", "{{", "}}",
        "[1", "{1", "{\"a\":", "{\"a\"", "\"a\":1",
        # trailing content after complete value
        "1abc", "1 garbage", "[]xyz", "{}extra", "nullnull", "truefalse",
        "123 456", "[1][2]", "{\"a\":1}{\"b\":2}",
        # duplicate keys
        '{"k":0,"k":1}', '{"a":1,"a":2,"b":3}',
        '{"x":{"y":1},"x":2}',
        # non-finite
        "1e309", "-1e309", "1e999999",
        # control chars in strings (escaped, not raw NUL)
        '"\\u0000"', '"\\u001f"', '"\\uD800"', '"\\uDC00"',
        '"\\uD800\\uDC00"', '"\\uD83D\\uDE00"',
        # bad escapes
        '"\\x41"', '"\\u12"', '"\\uZZZZ"', '"\\"',
        # whitespace variants
        "  ", "\t\n\r", " \t1 \n",
        # weird but complete
        '{"":""}', '[""]', '[{}]', '[[]]', '{"a":[]}',
    ])

# ---------- broadened structural diversity ----------

def _ws():
    return st.text(alphabet=" \t\n\r", max_size=3)

def _loose_value(depth):
    # whitespace-padded values to exercise lexer/parser whitespace handling
    if depth <= 0:
        core = st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null", "{}", "[]"]),
        )
    else:
        core = st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null"]),
            _loose_obj(depth),
            _loose_arr(depth),
        )
    return st.builds(lambda a, c, b: a + c + b, _ws(), core, _ws())

def _loose_pair(depth):
    return st.builds(
        lambda k, c1, v: k + c1 + v,
        _string(),
        st.one_of(st.just(":"), _ws().map(lambda w: w + ":")),
        _loose_value(depth),
    )

def _loose_obj(depth):
    inner = st.lists(_loose_pair(depth - 1), max_size=4).map(lambda xs: ",".join(xs))
    return st.builds(lambda a, i, b: "{" + a + i + b + "}", _ws(), inner, _ws())

def _loose_arr(depth):
    inner = st.lists(_loose_value(depth - 1), max_size=4).map(lambda xs: ",".join(xs))
    return st.builds(lambda a, i, b: "[" + a + i + b + "]", _ws(), inner, _ws())

def _wide_structure():
    # many sibling elements, flat but large
    n = st.integers(min_value=0, max_value=60)
    elem = st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"]))
    arr = st.builds(lambda k, e: "[" + ",".join([e] * k) + "]", n, elem)
    obj = st.builds(
        lambda k: "{" + ",".join('"k%d":%d' % (i, i) for i in range(k)) + "}",
        st.integers(min_value=0, max_value=40),
    )
    mixed = st.builds(
        lambda k: "[" + ",".join('{"i":%d,"v":[%d]}' % (i, i) for i in range(k)) + "]",
        st.integers(min_value=0, max_value=25),
    )
    return st.one_of(arr, obj, mixed)

def _mixed_nesting():
    # interleaved { and [ at varied depths
    depth = st.integers(min_value=1, max_value=40)
    return st.builds(
        lambda d: "".join("[" if i % 2 == 0 else "{" for i in range(d))
        + "0"
        + "".join("]" if i % 2 == 0 else "}" for i in reversed(range(d))),
        depth,
    )

def _string_diversity():
    # strings with varied lengths, unicode escapes, punctuation
    punct = st.text(alphabet=" !#$%&'()*+,-./:;<=>?@^_`|~", max_size=10)
    long_str = st.text(
        alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters='\\"\x00'),
        min_size=20, max_size=200,
    )
    unicode_esc = st.lists(_escape(), min_size=1, max_size=10).map("".join)
    return st.one_of(
        punct.map(lambda s: '"' + s + '"'),
        long_str.map(lambda s: '"' + s + '"'),
        unicode_esc.map(lambda s: '"' + s + '"'),
    )

def _key_variety():
    # objects with many distinct keys, nested keys, empty keys
    keys = st.lists(_string(), min_size=0, max_size=12, unique=True)
    return st.builds(
        lambda ks: "{" + ",".join(k + ":" + str(i) for i, k in enumerate(ks)) + "}",
        keys,
    )

def _scalar_diversity():
    return st.one_of(
        st.sampled_from(["true", "false", "null"]),
        _number(),
        _string(),
        st.sampled_from([
            "0", "-0", "0.0", "1e0", "1E0",
            '"\\u0041"', '"\\n"', '"\\t"', '"\\/"', '"\\\\"',
            '"a"', '""', '" "',
        ]),
    )

def _broadened():
    return st.one_of(
        _loose_value(4),
        _loose_obj(3),
        _loose_arr(3),
        _wide_structure(),
        _mixed_nesting(),
        _string_diversity(),
        _key_variety(),
        _scalar_diversity(),
    )

# ---------- top-level strategy ----------

def _valid_value():
    # depth budget chosen so recursive constructions stay well under the cap
    return _value(6)

def _top():
    return st.one_of(
        _valid_value(),
        _broadened(),
        _deep_nesting(),
        _near_cap_structured(),
        _malformed(),
        st.just(""),
        st.just("{}"),
        st.just("[]"),
        st.just("null"),
        st.just("true"),
        st.just("false"),
        st.just("0"),
        st.just("-"),
    )

strategy = _top()
```