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

# ---------- recursive value/obj/arr ----------

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed(),
    )

def _pair():
    return st.tuples(_string(), st.just(":"), st.deferred(lambda: _value())).map("".join)

def _obj():
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(), min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}"),
        # duplicate keys (accepted)
        st.tuples(_string(), st.just(":"), _leaf(),
                  st.just(","), _string(), st.just(":"), _leaf()
                  ).map("".join).map(lambda s: "{" + s + "}"),
    )

def _arr():
    return st.one_of(
        st.just("[]"),
        st.lists(st.deferred(lambda: _value()), min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"),
    )

def _value():
    return st.one_of(_leaf(), _obj(), _arr())

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
        _value(),
        _malformed(),
        _deep(),
        _deep_alt(),
        # BOM prefix (accepted)
        st.tuples(st.just("\ufeff"), _value()).map("".join),
        # trailing content after complete value (accepted)
        st.tuples(_value(), st.sampled_from(["abc", " 1 2", "\x00", "junk"])).map("".join),
        # NUL after value
        st.tuples(_value(), st.just("\x00")).map("".join),
        # whitespace padding
        st.tuples(_ws(), _value(), _ws()).map("".join),
        # raw NUL inside string
        st.just('"a\x00b"'),
        st.just('"tab\there"'),
        st.just('"nl\nhere"'),
    )

strategy = _top()