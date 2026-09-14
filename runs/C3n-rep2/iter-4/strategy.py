from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

_hex = "0123456789abcdefABCDEF"

def _u_escape():
    return st.text(alphabet=_hex, min_size=4, max_size=4).map(lambda h: "\\u" + h)

def _simple_escape():
    return st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _string_char():
    return st.one_of(
        st.sampled_from(["\\u", "\\", '"', "/", "x", "y", "Z", "0", "9", " ", "\t"]),
        st.integers(min_value=0, max_value=0x10FFFF).map(chr),
        st.integers(min_value=0, max_value=0x1F).map(chr),
        st.just("\x00"),
    )

def _string_body():
    return st.one_of(
        st.text(
            alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters='"\x00'),
            min_size=0,
            max_size=12,
        ),
        st.lists(
            st.one_of(_simple_escape(), _u_escape(), _string_char()),
            min_size=0,
            max_size=8,
        ).map("".join),
    )

def _string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**6).map(str),
        st.integers(min_value=1, max_value=10**60).map(str),
    )

def _frac_part():
    return st.one_of(
        st.just(""),
        st.integers(min_value=0, max_value=10**30).map(lambda n: "." + str(n)),
    )

def _exp_part():
    return st.one_of(
        st.just(""),
        st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
        st.sampled_from(["e309", "E309", "e9999", "e-9999", "e+308", "E+01", "e01"]),
    )

def _number():
    sign = st.sampled_from(["", "-"])
    return st.tuples(sign, _int_part(), _frac_part(), _exp_part()).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

# ---------- malformed / near-valid fragments ----------

def _malformed_number():
    return st.sampled_from([
        "+1", "+0", ".5", "-.5", "1.", "01", "007", "0x1F", "0X1f",
        "1e", "1e+", "1.2.3", "--1", "1-2", "1 2", "0b101", "1_000",
    ])

def _malformed_string():
    return st.sampled_from([
        '"unterminated', '"', '\\', '"bad\\escape"', '"\\u12"', '"\\uZZZZ"',
        '"tab\there"', "'single'", '"newline\nhere"',
    ])

def _malformed_fragment():
    return st.sampled_from([
        ",", ",,", "[,]", "[,1]", "[1,,2]", "{,}", "{\"a\":1,,}",
        "{a:1}", "{'a':1}", "{1:2}", ":", "::", "{\"a\" 1}",
        "{\"a\":}", "{:1}", "tru", "fals", "nul", "True", "NULL",
        "//comment\n1", "/*c*/1", "1 garbage", "[]xyz", "true false",
        "1abc", "{}extra", "[1] [2]", "}", "]", "{{}}", "[[]",
    ])

# ---------- recursive JSON values ----------

def _value(depth):
    if depth <= 0:
        return st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null", "-"]),
            _malformed_number(),
            _malformed_string(),
            _malformed_fragment(),
        )
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null", "-"]),
        _malformed_number(),
        _malformed_string(),
        _malformed_fragment(),
        _obj(depth),
        _arr(depth),
    )

def _pair(depth):
    # duplicate keys are fine; sometimes emit malformed pairs
    return st.one_of(
        st.tuples(_string(), st.just(":"), _value(depth - 1)).map("".join),
        st.tuples(_string(), st.just(":"), _value(depth - 1)).map("".join),
        st.sampled_from([
            '"a":1', '"a" : 1', '"dup":1', '"dup":2',
            '"a" 1', '"a":', ':"v"', '"k"::1',
            '"\\u0000":1', '"\\uD800":1', '"\\uDC00":2',
        ]),
    )

def _obj(depth):
    empty = st.just("{}")
    one = st.tuples(st.just("{"), _pair(depth), st.just("}")).map("".join)
    many = st.tuples(
        st.just("{"),
        st.lists(_pair(depth), min_size=1, max_size=6).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map("".join)
    trailing = st.tuples(
        st.just("{"),
        st.lists(_pair(depth), min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
        st.just(",}"),
    ).map("".join)
    # unclosed object for malformed coverage
    unclosed = st.tuples(
        st.just("{"),
        st.lists(_pair(depth), min_size=1, max_size=3).map(lambda ps: ",".join(ps)),
    ).map("".join)
    return st.one_of(empty, one, many, trailing, unclosed)

def _arr(depth):
    empty = st.just("[]")
    one = st.tuples(st.just("["), _value(depth - 1), st.just("]")).map("".join)
    many = st.tuples(
        st.just("["),
        st.lists(_value(depth - 1), min_size=2, max_size=6).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map("".join)
    trailing = st.tuples(
        st.just("["),
        st.lists(_value(depth - 1), min_size=1, max_size=4).map(lambda vs: ",".join(vs)),
        st.just(",]"),
    ).map("".join)
    unclosed = st.tuples(
        st.just("["),
        st.lists(_value(depth - 1), min_size=1, max_size=3).map(lambda vs: ",".join(vs)),
    ).map("".join)
    return st.one_of(empty, one, many, trailing, unclosed)

# ---------- deep nesting ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=200)
    return depth.flatmap(lambda d: st.one_of(
        st.just("[" * d + "]" * d),
        st.just("[" * d + "0" + "]" * d),
        st.just("{\"a\":" * d + "1" + "}" * d),
        st.just("[" * d + "{\"k\":1}" + "]" * d),
        st.just("[" * d),  # unterminated deep
        st.just("{" * d),
    ))

# ---------- near-crash intensification ----------

# Structurally mutate around inputs that are known to stress the parser's
# recursion / allocation paths: deep nesting, huge exponents, lone surrogates,
# embedded NULs, and unterminated containers. These are the shapes most likely
# to drive json_parse / json_alloc / json_parse_ex branches.

_NEAR_CRASH_SEEDS = [
    "[" * 128 + "]" * 128,
    "[" * 128,
    "{" * 128,
    "{\"a\":" * 128 + "1" + "}" * 128,
    "[" * 64 + "{\"a\":" * 32 + "1" + "}" * 32 + "]" * 64,
    "1e309",
    "-1e309",
    "1e-309",
    "1e9999",
    "1e-9999",
    "\"\\uD800\"",
    "\"\\uDC00\"",
    "\"\\uD800\\uDC00\"",
    "\"\\u0000\"",
    "\"a\x00b\"",
    "[\x00]",
    "{\"a\":\x00}",
    "\x00",
    "{\"a\":1,\"a\":2,\"a\":3}",
    "[1,2,3,4,5,6,7,8,9,10]",
    "{\"a\":{\"b\":{\"c\":{\"d\":{\"e\":1}}}}}",
    "[[[[[[[[[[1]]]]]]]]]]",
    "[1,2,]",
    "{\"a\":1,}",
    "\"unterminated",
    "[,1]",
    "{,}",
]

def _mutate_seed(seed):
    # structural mutations that stay close to the crash shape
    def _truncate(s):
        n = max(0, len(s) - 1)
        return s[:n]
    def _extend(s):
        return s + s[-1:] if s else s
    def _dup(s):
        return s + s
    def _swap_brackets(s):
        return s.replace("[", "{").replace("]", "}")
    def _strip_close(s):
        return s.rstrip("]}") if s else s
    def _append_garbage(s):
        return s + "x"
    return st.one_of(
        st.just(seed),
        st.just(_truncate(seed)),
        st.just(_extend(seed)),
        st.just(_dup(seed)),
        st.just(_swap_brackets(seed)),
        st.just(_strip_close(seed)),
        st.just(_append_garbage(seed)),
    )

def _near_crash():
    return st.one_of(
        st.sampled_from(_NEAR_CRASH_SEEDS),
        st.sampled_from(_NEAR_CRASH_SEEDS).flatmap(_mutate_seed),
        _deep_nesting(),
    )

# ---------- top-level strategy ----------

def _top():
    return st.one_of(
        # objects with members strongly favored
        _obj(3),
        _obj(3),
        _obj(3),
        _arr(3),
        _value(3),
        # explicit edge classes
        st.just("{}"),
        st.just("[]"),
        st.just("{\"a\":1,\"a\":2}"),
        st.just("{\"a\":1,}"),
        st.just("[1,2,]"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-309"),
        st.just("1e9999"),
        st.just("-"),
        st.just("\"\\uD800\""),
        st.just("\"\\uDC00\""),
        st.just("\"\\uD800\\uDC00\""),
        st.just("\"\\u0000\""),
        st.just("\"a\x00b\""),
        st.just("[\x00]"),
        st.just("{\"a\":\x00}"),
        st.just("\x00"),
        st.just(""),
        st.just(" "),
        st.just("\n\t\r "),
        _deep_nesting(),
        _near_crash(),
        _malformed_fragment(),
        _malformed_number(),
        _malformed_string(),
    )

strategy = _top()