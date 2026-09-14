from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _unicode_escape():
    return st.tuples(st.just("\\u"), _hex4()).map(lambda t: t[0] + t[1])

def _surrogate_escape():
    return st.sampled_from([
        "\\ud800", "\\udfff", "\\uD800", "\\uDFFF",
        "\\ud83d\\ude00", "\\uD83D\\uDE00",
    ])

def _simple_escape():
    return st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _safe_cp():
    # SAFECODEPOINT: ~ ["\\\u0000-\u001F]
    return st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='"\u0000\u0001\u0002\u0003\u0004\u0005\u0006\u0007'
        "\u0008\u0009\u000a\u000b\u000c\u000d\u000e\u000f\u0010\u0011\u0012"
        "\u0013\u0014\u0015\u0016\u0017\u0018\u0019\u001a\u001b\u001c\u001d"
        "\u001e\u001f\\",
    )

def _string_body_piece():
    return st.one_of(
        _safe_cp(),
        _simple_escape(),
        _unicode_escape(),
        _surrogate_escape(),
        st.sampled_from(["\u0000", "\u0001", "\u001f", "\u007f", "\u000b", "\u000c"]),
    )

def _string_body():
    return st.lists(_string_body_piece(), max_size=8).map("".join)

def _string():
    return st.tuples(st.just('"'), _string_body(), st.just('"')).map(lambda t: t[0] + t[1] + t[2])

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(
            st.integers(min_value=1, max_value=9),
            st.text(alphabet="0123456789", max_size=10),
        ).map(lambda t: str(t[0]) + t[1]),
        st.text(alphabet="0123456789", min_size=1, max_size=20),
    )

def _frac():
    return st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=8)).map(
        lambda t: t[0] + t[1]
    )

def _exp():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=6),
    ).map(lambda t: t[0] + t[1] + t[2])

def _number():
    sign = st.sampled_from(["", "-", "+"])
    body = st.tuples(
        _int_part(),
        st.one_of(st.just(""), _frac()),
        st.one_of(st.just(""), _exp()),
    ).map(lambda t: t[0] + t[1] + t[2])
    normal = st.tuples(sign, body).map(lambda t: t[0] + t[1])
    weird = st.sampled_from([
        "-", "1e309", "-1e309", "1e-309", "1E+999", "0e0", "0e00",
        ".5", "1.", "+1", "01", "0x1F", "1e", "1e+", "-.5", "00",
        "1e999999999999", "-0", "0.0", "-0.0", "1.0e0",
    ])
    return st.one_of(normal, weird)

# ---------- recursive values ----------

def _value(depth):
    leaf = st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )
    if depth <= 0:
        return leaf
    child = st.deferred(lambda: _value(depth - 1))
    obj = _obj(child)
    arr = _arr(child)
    return st.one_of(leaf, obj, arr)

def _pair(child):
    return st.tuples(_string(), st.just(":"), child).map(lambda t: t[0] + t[1] + t[2])

def _obj(child):
    return st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            st.lists(_pair(child), min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(
            st.just("{"),
            st.lists(_pair(child), min_size=1, max_size=3).map(lambda ps: ",".join(ps)),
            st.just(",}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

def _arr(child):
    return st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            st.lists(child, min_size=1, max_size=4).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(
            st.just("["),
            st.lists(child, min_size=1, max_size=3).map(lambda xs: ",".join(xs)),
            st.just(",]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

# ---------- deep nesting ----------

def _deep_nesting():
    def _mk(kind, n):
        return kind * n + (("{}" if kind == "{" else "[]") if kind == "{" else "[]")

    deep_obj = st.integers(min_value=1, max_value=200).map(
        lambda n: "{" + ",".join(['"k":' for _ in range(0)]) + "{}" if False else _deep_obj(n)
    )
    return st.integers(min_value=1, max_value=200).flatmap(
        lambda n: st.one_of(
            st.just("[" * n + "]" * n),
            st.just("{" + '"a":{' * n + "}" * n + "}"),
            st.just("[" * n + "0" + "]" * n),
        )
    )

def _deep_obj(n):
    return "{" + '"k":' * n + "null" + "}" * n

# ---------- malformed / near-valid ----------

def _malformed():
    return st.sampled_from([
        "[1,,2]", "[,]", "[,1]", "{,}", "{\"a\":1,,}", "{\"a\":1 \"b\":2}",
        "{a:1}", "{'a':1}", "{\"a\" 1}", "{\"a\":}", "{:1}",
        "[1 2]", "[1,2", "{\"a\":1", "\"unterminated", "\"a\\\"",
        "1abc", "[]xyz", "1 garbage", "true false", "nul", "tru", "fals",
        "+1", ".5", "1.", "01", "0x1F", "1e", "1e+", "--1", "-.",
        "//x", "/* */1", "'x'", "{\"a\":1,}", "[1,2,]",
        "\"\\uD800\"", "\"\\u\"", "\"\\uZZZZ\"", "\"\\q\"",
        "\u0000", "{\u0000}", "[\u0000]", "\"a\u0000b\"",
        "\"\\ud800\\udc00\"", "{\"a\":1}\u0000",
        "{}", "[]", "null", "", " ", "\n", "\t",
    ])

# ---------- top-level strategy ----------

def _top():
    deep = _deep_nesting()
    root = st.recursive(
        st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda child: st.one_of(_obj(child), _arr(child)),
        max_leaves=20,
    )
    return st.one_of(
        root,
        deep,
        _malformed(),
        st.tuples(
            st.one_of(_string(), _number()),
            st.sampled_from(["", " ", "\n", "\t"]),
        ).map(lambda t: t[0] + t[1]),
    )

strategy = st.one_of(
    _top(),
    _obj(_value(3)),
    _arr(_value(3)),
    _value(4),
).map(lambda s: s if isinstance(s, str) else json.dumps(s))