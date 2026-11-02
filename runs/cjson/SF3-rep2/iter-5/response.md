```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _unicode_escape():
    return st.one_of(
        _hex4().map(lambda h: "\\u" + h),
        # surrogate pair (valid)
        st.tuples(
            st.integers(min_value=0xD800, max_value=0xDBFF),
            st.integers(min_value=0xDC00, max_value=0xDFFF),
        ).map(lambda t: "\\u%04x\\u%04x" % t),
        # lone surrogate (rejected by parser)
        st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda c: "\\u%04x" % c),
    )

def _escape():
    return st.one_of(
        st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
        _unicode_escape(),
    )

def _safe_char():
    # printable-ish code points safe to embed
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                      blacklist_categories=("Cs",)),
        st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF,
                      blacklist_categories=("Cs",)),
        # raw control bytes / NUL (accepted by parser)
        st.integers(min_value=0, max_value=0x1F).map(chr),
    )

def _string_body():
    return st.one_of(
        st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                                       blacklist_characters='"\\'),
                max_size=12),
        st.lists(st.one_of(_escape(), _safe_char()), max_size=10).map("".join),
    )

def _string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=10, max_value=10**18).map(str),
        # leading zeros (accepted)
        st.tuples(st.just("0"), st.integers(min_value=0, max_value=999)).map(
            lambda t: t[0] + str(t[1])),
    )

def _frac_part():
    return st.one_of(
        st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
        st.just("."),  # trailing dot (accepted)
    )

def _exp_part():
    return st.one_of(
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.one_of(st.just(""), st.just("+"), st.just("-")),
            st.integers(min_value=0, max_value=9999).map(str),
        ).map("".join),
        # extreme exponents
        st.sampled_from(["e309", "e-309", "e999", "E+308", "e400", "e-400"]),
    )

def _number():
    sign = st.one_of(st.just(""), st.just("-"))
    core = st.one_of(
        _int_part(),
        st.tuples(_int_part(), _frac_part()).map("".join),
        st.tuples(_int_part(), _frac_part(), _exp_part()).map("".join),
        st.tuples(_int_part(), _exp_part()).map("".join),
    )
    valid = st.tuples(sign, core).map("".join)
    # hex numbers (accepted)
    hexnum = st.tuples(
        sign,
        st.just("0x"),
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8),
    ).map("".join)
    return st.one_of(valid, hexnum)

# ---------- malformed near-valid fragments ----------

def _malformed():
    return st.sampled_from([
        "", "-", "+1", ".5", "-.5", "01", "1.", "1..", "1e", "1e+",
        "NaN", "Infinity", "-Infinity", "nan", "inf",
        "truee", "falsee", "nulll", "tru", "fals", "nul",
        "{,}", "[,]", "[1,,2]", "{\"a\":,}", "{\"a\" 1}",
        "{a:1}", "{'a':1}", "'x'", "[1 2]", "{\"a\":1,}",
        "\"unterminated", "\"a\\", "\"\\u12\"", "\"\\x41\"",
        "{\"a\":1", "[1,2", "{", "[", "}", "]", ",", ":",
        "1 2 3", "1abc", "truex", "[]]", "{}extra",
    ])

# ---------- recursive value/obj/arr (bounded depth) ----------

_MAX_DEPTH = 4

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed(),
    )

def _value(depth=0):
    if depth >= _MAX_DEPTH:
        return _leaf()
    return st.one_of(_leaf(), _obj(depth), _arr(depth))

def _pair(depth):
    return st.tuples(_string(), st.just(":"), _value(depth)).map("".join)

def _obj(depth):
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(depth + 1), min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"),
        # duplicate keys (accepted)
        st.tuples(_string(), st.just(":"), _leaf(),
                  st.just(","), _string(), st.just(":"), _leaf()
                  ).map("".join).map(lambda s: "{" + s + "}"),
    )

def _arr(depth):
    return st.one_of(
        st.just("[]"),
        st.lists(_value(depth + 1), min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"),
    )

# ---------- deep nesting near the 1000 limit ----------

def _deep():
    depth = st.integers(min_value=990, max_value=1005)
    return st.tuples(
        depth,
        st.sampled_from(["[", "{"]),
        st.sampled_from(["]", "}"]),
    ).map(lambda t: t[1] * t[0] + "0" + t[2] * t[0])

def _deep_alt():
    depth = st.integers(min_value=990, max_value=1005)
    return depth.map(lambda d: "[" * d + "]" * d)

# ---------- top-level ----------

def _ws():
    return st.text(alphabet=" \t\n\r", max_size=3)

def _top():
    return st.one_of(
        _value(0),
        _malformed(),
        _deep(),
        _deep_alt(),
        # BOM prefix (accepted)
        st.tuples(st.just("\ufeff"), _value(0)).map("".join),
        # trailing content after complete value (accepted)
        st.tuples(_value(0), st.sampled_from(["abc", " 1 2", "\x00", "junk"])).map("".join),
        # NUL after value
        st.tuples(_value(0), st.just("\x00")).map("".join),
        # whitespace padding
        st.tuples(_ws(), _value(0), _ws()).map("".join),
        # raw NUL inside string
        st.just('"a\x00b"'),
        st.just('"tab\there"'),
        st.just('"nl\nhere"'),
        # exercise print paths: round-trip a parsed value through cJSON_Print
        # by generating compact and formatted variants of the same value
        _value(0).flatmap(lambda v: st.one_of(
            st.just(v),
            st.just(v + "\n"),
            st.just(" " + v + " "),
        )),
        # exercise print paths (print_value/print_string_ptr/print_number/
        # print_object) with objects containing special strings and numbers,
        # plus whitespace/formatting variants to hit pretty-printing branches
        st.tuples(
            _string_body(),
            _number(),
            _number(),
        ).flatmap(lambda t: st.one_of(
            st.just('{"s":' + json.dumps(t[0]) + ',"n":' + t[1] + ',"m":' + t[2] + '}'),
            st.just('{"s":' + json.dumps(t[0]) + '}'),
            st.just('{\n  "s": ' + json.dumps(t[0]) + ',\n  "n": ' + t[1] + '\n}'),
            st.just('{"n":' + t[1] + ',"m":' + t[2] + ',"o":{"x":' + t[2] + '}}'),
        )),
        # exercise cJSON_Compare branches: two structurally similar values
        st.tuples(_value(0), _value(0)).map(lambda t: t[0] + "\x00" + t[1]),
        # exercise cJSON_Compare via round-trip: parse a value, print it, then
        # emit two copies so the harness can compare identical structures
        _value(0).flatmap(lambda v: st.one_of(
            st.just(v + "\x00" + v),
            st.just("[" + v + "," + v + "]"),
            st.just('{"a":' + v + ',"b":' + v + '}'),
        )),
        # exercise print_string_ptr on strings requiring escaping and
        # print_number on floats/negatives/large values
        st.tuples(
            st.lists(st.one_of(_escape(), _safe_char()), max_size=8).map("".join),
            st.one_of(_number(), st.just("1.5"), st.just("-0.0"), st.just("1e300")),
        ).map(lambda t: '{"esc":"' + t[0] + '","num":' + t[1] + '}'),
        # exercise print_object / print_array with nested structures and
        # mixed content to hit all formatting branches
        st.tuples(_value(0), _value(0), _value(0)).map(
            lambda t: '{"a":' + t[0] + ',"b":[' + t[1] + ',' + t[2] + ']}'),
    )

strategy = _top()
```