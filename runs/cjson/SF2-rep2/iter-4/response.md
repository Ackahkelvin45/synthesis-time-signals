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
        # --- improve_strategy: deepen coverage of structural edge cases ---
        # mixed-depth nesting (near limit) to hit depth-tracking branches
        st.integers(min_value=1, max_value=1000).flatmap(
            lambda d: st.tuples(
                st.just("[" * d),
                _value(0),
                st.just("]" * d),
            ).map("".join)),
        # object with many keys (exercise key iteration / duplicate handling)
        st.lists(
            st.tuples(_string(), st.just(":"), _leaf()),
            min_size=0, max_size=32,
        ).map(lambda ps: "{" + ",".join("".join(p) for p in ps) + "}"),
        # array with many elements (exercise element iteration)
        st.lists(_value(1), min_size=0, max_size=32).map(
            lambda vs: "[" + ",".join(vs) + "]"),
        # whitespace-heavy variants around structural tokens
        st.tuples(
            st.just("["),
            st.lists(_ws(), min_size=1, max_size=4).map("".join),
            _value(1),
            st.lists(_ws(), min_size=1, max_size=4).map("".join),
            st.just("]"),
        ).map("".join),
        # truncated deep structures (unbalanced) to hit error paths
        st.integers(min_value=1, max_value=1000).map(lambda d: "[" * d),
        st.integers(min_value=1, max_value=1000).map(lambda d: "]" * d),
        # empty-ish whitespace-only inputs
        st.lists(_ws(), min_size=0, max_size=6).map("".join),
        # numbers at boundary magnitudes (overflow / underflow branches)
        st.sampled_from([
            "1e308", "1e309", "-1e309", "1e-323", "1e-324", "1e-400",
            "1.7976931348623157e308", "2.2250738585072014e-308",
            "0.0", "-0.0", "0e0", "-0e-0", "1E+000", "1E-000",
        ]),
        # --- improve_strategy: target remaining branch gaps ---
        # mismatched bracket types at depth (hits bracket-type validation)
        st.integers(min_value=1, max_value=1000).flatmap(
            lambda d: st.tuples(
                st.just("[" * d),
                st.just("}"),
            ).map("".join)),
        st.integers(min_value=1, max_value=1000).flatmap(
            lambda d: st.tuples(
                st.just("{" * d),
                st.just("]"),
            ).map("".join)),
        # deep object with a key:value leaf (exercises object descent)
        st.integers(min_value=1, max_value=1000).flatmap(
            lambda d: st.tuples(
                st.just('{"a":' * d),
                _leaf(),
                st.just("}" * d),
            ).map("".join)),
        # string escape edge cases: empty escape, truncated unicode, bad hex
        st.sampled_from([
            '"\\"', '"\\u"', '"\\u0"', '"\\u00"', '"\\u000"',
            '"\\u000g"', '"\\uD800"', '"\\uDC00"', '"\\uD800\\uD800"',
            '"\\uDC00\\uD800"', '"\\uD800\\u0041"', '"\\u0000"',
            '"\\uFFFF"', '"\\uFFFE"', '"\\uDBFF\\uDFFF"',
            '"\\uD800\\uDC00"', '"\\ud83d\\ude00"', '"\\U0001F600"',
            '"\\/"', '"\\a"', '"\\v"', '"\\0"', '"\\\'"',
        ]),
        # number edge: leading zero variants, sign-only, exp-only
        st.sampled_from([
            "00", "000", "-00", "0.0e0", "0e", "0e+", "0e-", "-0",
            "1e+0", "1e-0", "1E0", "1.0E+0", "0.0000000000001",
            "123456789012345678901234567890", "1e000000000000000000",
        ]),
        # object/array with trailing commas and whitespace at various spots
        st.sampled_from([
            "[1,]", "[1 , ]", "[ 1 ]", "{ }", "{,}", "{\"a\":1,}",
            "{\"a\" : 1}", "{\"a\": 1 , }", "[,1]", "[1,,]",
            "{\"a\":1,\"a\":2}", "{\"a\":1,\"b\":2,\"a\":3}",
        ]),
        # top-level scalars followed by whitespace/newlines
        st.tuples(
            _leaf(),
            st.text(alphabet=" \t\n\r", min_size=1, max_size=8),
        ).map("".join),
        # control chars / invalid bytes at top level
        st.sampled_from([
            "\x00", "\x01", "\x1f", "\x7f", "\x80", "\xff",
            "true\x00", "null\x00", "1\x002",
        ]),
        # --- improve_strategy: close remaining branch gaps ---
        # whitespace inside object around key, colon, value, and commas
        st.tuples(
            st.just("{"),
            st.lists(_ws(), min_size=0, max_size=2).map("".join),
            _string(),
            st.lists(_ws(), min_size=0, max_size=2).map("".join),
            st.just(":"),
            st.lists(_ws(), min_size=0, max_size=2).map("".join),
            _value(1),
            st.lists(_ws(), min_size=0, max_size=2).map("".join),
            st.just("}"),
        ).map("".join),
        # array with leading/trailing whitespace and multiple elements
        st.lists(_value(1), min_size=1, max_size=6).map(
            lambda vs: "[" + " , ".join(vs) + "]"),
        # object missing colon / value (hits error branches)
        st.sampled_from([
            "{\"a\"}", "{\"a\"}", "{\"a\":}", "{:\"a\"}", "{\"a\"::1}",
            "{\"a\":1 \"b\":2}", "{\"a\":1,,}", "{\"a\":}", "{\"a\":1,}",
            "{\"a\" 1}", "{1:2}", "{[1]:2}", "{{}:2}", "{\"a\":{\"b\":}}",
        ]),
        # array element errors
        st.sampled_from([
            "[1 2]", "[1,,2]", "[,]", "[,1]", "[1,]", "[[1]", "[1]]",
            "[{]", "[{}", "[[[]]", "[]]", "[[1,2],[3,4]]",
        ]),
        # literal case / truncation variants
        st.sampled_from([
            "True", "TRUE", "False", "FALSE", "Null", "NULL",
            "tRue", "fAlse", "nUll", "tr", "fa", "nu", "t", "f", "n",
            "tru e", "nul l", "fals e",
        ]),
        # number continuation errors (letters after digits, double signs)
        st.sampled_from([
            "1-2", "1+2", "--1", "++1", "+-1", "-+1", "1.2.3",
            "1e1e1", "1ee1", "1e+-1", "0x", "0xG", "-0x1", "0x1g",
            "1.2e", "1.2e+", ".", "-.", "+", "-", "1.", "-1.",
        ]),
        # string content errors: control chars, unterminated, bad escapes
        st.sampled_from([
            '"a\x01b"', '"a\x1fb"', '"a\x7fb"', '"\\x"', '"\\uZZZZ"',
            '"\\u12"', '"\\u123"', '"\\u12345"', '"abc', '"abc\\',
            '"\\', '"', '"a"b"', '"a""b"',
        ]),
        # nesting depth boundary probes (exact 999/1000/1001)
        st.sampled_from([999, 1000, 1001]).flatmap(
            lambda d: st.one_of(
                st.just("[" * d + "]" * d),
                st.just("[" * d + "0" + "]" * d),
                st.just("[" * d),
                st.just("{" * d + "}" * d),
                st.just("[" * d + "}"),
            )),
        # top-level garbage prefixes before a valid value
        st.tuples(
            st.sampled_from(["x", "\x00", "]", "}", ",", ":", "1", "true"]),
            _value(1),
        ).map("".join),
    )

strategy = _top()
```