```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _safe_cp():
    # SAFECODEPOINT: ~ ["\\\u0000-\u001F]
    return st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='\\"',
    ).filter(lambda c: ord(c) > 0x1F)

def _esc():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    hexd = st.sampled_from("0123456789abcdefABCDEF")
    unicode_esc = st.tuples(
        st.just("\\u"), hexd, hexd, hexd, hexd
    ).map("".join)
    # surrogates and weird code units
    surrogate = st.tuples(
        st.just("\\u"),
        st.sampled_from("dD"),
        st.sampled_from("89abAB"),
        hexd,
        hexd,
    ).map("".join)
    return st.one_of(simple, unicode_esc, surrogate)

def _string_body():
    return st.one_of(_safe_cp(), _esc())

def _raw_control():
    # embedded NUL / control bytes (allowed by harness)
    return st.integers(min_value=0, max_value=0x1F).map(chr)

def _string_inner():
    return st.one_of(_string_body(), _raw_control())

def _string():
    return st.lists(_string_inner(), max_size=12).map(lambda cs: '"' + "".join(cs) + '"')

def _unterminated_string():
    return st.lists(_string_inner(), min_size=0, max_size=8).map(lambda cs: '"' + "".join(cs))

# ---------- numbers ----------

def _int_part():
    zero = st.just("0")
    nonzero = st.tuples(
        st.integers(min_value=1, max_value=9).map(str),
        st.lists(st.integers(min_value=0, max_value=9).map(str), max_size=6).map("".join),
    ).map("".join)
    return st.one_of(zero, nonzero)

def _frac():
    return st.tuples(
        st.just("."),
        st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=6).map("".join),
    ).map("".join)

def _exp():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=4).map("".join),
    ).map("".join)

def _number():
    sign = st.sampled_from(["", "-"])
    body = st.one_of(
        _int_part(),
        st.tuples(_int_part(), _frac()).map("".join),
        st.tuples(_int_part(), _frac(), _exp()).map("".join),
        st.tuples(_int_part(), _exp()).map("".join),
        # extreme magnitudes
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-309"),
        st.just("1e1000"),
        st.just("9" * 20),
        st.just("0." + "0" * 30 + "1"),
        st.just("1e" + "9" * 10),
        st.just("-0"),
        st.just("0e0"),
        st.just("0E+00"),
        # lone minus (parser accepts)
        st.just("-"),
    )
    return st.tuples(sign, body).map("".join)

def _bad_number():
    return st.sampled_from([
        "+1", ".5", "1.", "01", "007", "-01", "0x1F", "0x0",
        "1e", "1e+", "1e-", "1.", "-.", "+", "1..2", "1.2.3",
        "1e309abc", "--1", "1-", "1+2",
    ])

# ---------- recursive values ----------

_value = st.deferred(lambda: _value_strategy)

def _value_atom():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _bad_number(),
        _unterminated_string(),
    )

def _obj():
    # bias toward objects with members
    empty = st.just("{}")
    key = st.one_of(_string(), _unterminated_string())
    pair = st.tuples(key, st.just(":"), _value).map("".join)
    pairs = st.lists(pair, min_size=1, max_size=5)
    body = pairs.map(lambda ps: "{" + ",".join(ps) + "}")
    # duplicate keys
    dup_key = _string()
    dup_pair = st.tuples(dup_key, st.just(":"), _value).map("".join)
    dup_body = st.tuples(dup_pair, dup_pair).map(lambda t: "{" + t[0] + "," + t[1] + "}")
    # single trailing comma
    trailing = pairs.map(lambda ps: "{" + ",".join(ps) + ",}")
    return st.one_of(empty, body, dup_body, trailing)

def _arr():
    empty = st.just("[]")
    vals = st.lists(_value, min_size=1, max_size=5)
    body = vals.map(lambda vs: "[" + ",".join(vs) + "]")
    trailing = vals.map(lambda vs: "[" + ",".join(vs) + ",")
    return st.one_of(empty, body, trailing)

def _value_strategy():
    return st.one_of(_value_atom(), _obj(), _arr())

# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        st.sampled_from([
            "[,]", "[,1]", "[1,,2]", "[1,2,,]", "{,}", "{,}", '{"a":1,,"b":2}',
            '{"a" 1}', '{"a":}', '{:1}', '{"a":1', '[1,2', '{"a":1}}', '[[1]',
            '{"a":1,"a":2,"a":3}', '[1,2,]', '{"a":1,}', '{"":1}',
            '[1 2]', '{"a":1 "b":2}', 'tru', 'fals', 'nul', 'True', 'NULL',
            '1abc', '[]xyz', '1 garbage', 'true false', '{} {}', '[] []',
            '{"a":1}{"b":2}', '//x', '/* */1', "'x'", '{a:1}',
        ]),
        st.tuples(_value, st.text(alphabet="abcxyz ", max_size=4)).map(lambda t: t[0] + t[1]),
    )

# ---------- deep nesting ----------

def _deep(depth):
    # deeply nested objects (stresses first-pass memory measurement)
    inner = st.just("1")
    def wrap(n):
        acc = inner
        for _ in range(n):
            acc = st.tuples(st.just('{"a":'), acc, st.just("}")).map("".join)
        return acc
    return wrap(depth)

def _deep_arr(depth):
    inner = st.just("1")
    def wrap(n):
        acc = inner
        for _ in range(n):
            acc = st.tuples(st.just("["), acc, st.just("]")).map("".join)
        return acc
    return wrap(depth)

# ---------- near-crash intensification ----------
# The divergence/crash cluster centers on lone-surrogate escapes like "\uD800"
# (and related unpaired surrogate code units). Mutate structurally around it:
# vary the hex digits, embed it inside strings/objects/arrays, pad with
# surrounding text, and mix high/low surrogate pairs, escapes, and raw bytes.

def _surrogate_esc():
    hexd = st.sampled_from("0123456789abcdefABCDEF")
    hi = st.sampled_from("dD")
    lo = st.sampled_from("89abAB")
    return st.tuples(st.just("\\u"), hi, lo, hexd, hexd).map("".join)

def _low_surrogate_esc():
    hexd = st.sampled_from("0123456789abcdefABCDEF")
    hi = st.sampled_from("dD")
    lo = st.sampled_from("cdefCDEF")
    return st.tuples(st.just("\\u"), hi, lo, hexd, hexd).map("".join)

def _crash_core():
    # the exact crashing atom plus structural variants around it
    base = st.sampled_from([
        '"\\uD800"',
        '"\\uD800"',
        '"\\uD800"',
        '"\\ud800"',
        '"\\uDBFF"',
        '"\\uDC00"',
        '"\\uDFFF"',
        '"\\uD800\\uD800"',
        '"\\uDC00\\uD800"',
        '"\\uD800\\uDC00"',
        '"\\uD834\\uDD1E"',
        '"\\uD800x"',
        '"x\\uD800"',
        '"\\uD800\\n"',
        '"\\uD800\\u"',
        '"\\uD8"',
        '"\\uD800\\uD800\\uD800"',
        '"\\uD800\\uDFFF"',
        '"\\uDBFF\\uDFFF"',
        '"\\uDC00"',
    ])
    return st.one_of(
        base,
        _surrogate_esc().map(lambda e: '"' + e + '"'),
        _low_surrogate_esc().map(lambda e: '"' + e + '"'),
        st.tuples(
            st.just('"'),
            st.lists(
                st.one_of(
                    _surrogate_esc(),
                    _low_surrogate_esc(),
                    st.sampled_from(["x", " ", "\\n", "\\t", "\\\"", "a", "0"]),
                ),
                min_size=1, max_size=6,
            ).map("".join),
            st.just('"'),
        ).map("".join),
    )

def _near_crash():
    core = _crash_core()
    # embed the crash core in structural surroundings
    in_obj_key = core.map(lambda s: "{" + s + ":1}")
    in_obj_val = core.map(lambda s: '{"a":' + s + "}")
    in_arr = core.map(lambda s: "[" + s + "]")
    in_arr_multi = st.tuples(
        core, core
    ).map(lambda t: "[" + t[0] + "," + t[1] + "]")
    in_obj_multi = st.tuples(
        core, core
    ).map(lambda t: "{" + t[0] + ":1," + t[1] + ":2}")
    padded = st.tuples(
        st.text(alphabet=" \t\n\r", max_size=3),
        core,
        st.text(alphabet=" \t\n\r", max_size=3),
    ).map(lambda t: t[0] + t[1] + t[2])
    adjacent = st.tuples(
        core, st.just(","), core
    ).map(lambda t: t[0] + t[1] + t[2])
    trailing_garbage = st.tuples(
        core, st.text(alphabet="abcxyz{}[]:,", max_size=4)
    ).map(lambda t: t[0] + t[1])
    return st.one_of(
        core,
        in_obj_key,
        in_obj_val,
        in_arr,
        in_arr_multi,
        in_obj_multi,
        padded,
        adjacent,
        trailing_garbage,
        # raw (unescaped) surrogate-ish bytes and NULs near the crash
        st.sampled_from([
            "\xed\xa0\x80",
            "\xed\xbf\xbf",
            "\xed\xb0\x80",
            '"' + "\xed\xa0\x80" + '"',
            '"\x00"',
            "\x00",
            '"\x00\x01"',
        ]),
    )

# ---------- assembly ----------

_recursive = st.recursive(
    _value_atom(),
    lambda children: st.one_of(
        # objects with members (stressed path)
        st.lists(
            st.tuples(st.one_of(_string(), _unterminated_string()), st.just(":"), children).map("".join),
            min_size=1, max_size=4,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        # arrays
        st.lists(children, min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
    ),
    max_leaves=30,
)

# rebuild deferred _value to point at the recursive strategy
_value = _recursive

def _all():
    return st.one_of(
        _recursive,
        _malformed(),
        _deep(5),
        _deep(20),
        _deep_arr(20),
        _deep_arr(100),
        st.sampled_from([
            "{}", "[]", "null", "true", "false", "-", "1e309", '{"a":1,"a":2}',
            '[1,2,]', '{"a":1,}', "\x00", '"\\u0000"', '"\\uD800"', '"\\uDFFF"',
            '"\\uD834\\uDD1E"', '"\x00\x01\x02"', '{"\\u0000":1}',
        ]),
        st.tuples(_value, st.just(" ")).map("".join),
        st.text(alphabet="{}[],:\"\\ \t\n\r0123456789.eE+-truefalsn", min_size=0, max_size=40),
        _near_crash(),
    )

strategy = _all()
```