```python
from hypothesis import strategies as st
import json

# ---------- building blocks ----------

_hex = "0123456789abcdefABCDEF"

def _plain_string():
    # SAFECODEPOINT-ish chars, plus some raw control/NUL bytes the parser tolerates
    chars = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),  # avoid lone surrogates in source text
            blacklist_characters='"\\',
        ),
        max_size=8,
    )
    raw_ctrl = st.sampled_from(["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"])
    pieces = st.one_of(
        st.lists(st.one_of(chars, raw_ctrl), max_size=6).map("".join),
    )
    return pieces.map(lambda s: '"' + s + '"')

def _escape_string():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    uni = st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "\\u" + "".join(t))
    # lone surrogate escapes (parser rejects, but we want to emit them)
    surrogate = st.tuples(
        st.sampled_from("dD"), st.sampled_from("89abAB"),
        st.sampled_from(_hex), st.sampled_from(_hex),
    ).map(lambda t: "\\u" + "".join(t))
    piece = st.one_of(simple, uni, surrogate)
    body = st.lists(piece, min_size=1, max_size=4).map("".join)
    return body.map(lambda s: '"' + s + '"')

def _string():
    return st.one_of(_plain_string(), _escape_string())

def _number():
    int_part = st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.just("01"),          # leading zero (accepted)
        st.just("0x10"),        # hex (accepted)
    )
    sign = st.one_of(st.just(""), st.just("-"))
    frac = st.one_of(
        st.just(""),
        st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
        st.just("."),           # trailing dot (accepted)
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from("eE"),
            st.one_of(st.just(""), st.just("+"), st.just("-")),
            st.integers(min_value=0, max_value=400).map(str),
        ).map(lambda t: "".join(t)),
    )
    # extreme magnitudes / overflow
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e999999", "9" * 40, "-" + "9" * 40,
        "1e-999999", "0e0", "1E+308",
    ])
    normal = st.tuples(sign, int_part, frac, exp).map(lambda t: "".join(t))
    return st.one_of(normal, extreme)

def _literal():
    return st.sampled_from(["true", "false", "null"])

# ---------- malformed fragments (near-valid) ----------

def _malformed():
    return st.sampled_from([
        "", "-", "+1", ".5", "-.5", "NaN", "Infinity", "-Infinity",
        "[,]", "[1,,2]", '{"a":1,}', '{"a" 1}', '{"a":}', "{:1}",
        '"unterminated', "'single'", "{a:1}", "[1 2]", '{"a":1 "b":2}',
        "[", "]", "{", "}", '"\\u12"', '"\\ud800"', '"\\x41"',
        "tru", "nul", "fals", "1 2", "1abc", "\xef\xbb\xbf1",
    ])

# ---------- recursive structure ----------

def _leaf():
    return st.one_of(_string(), _number(), _literal(), _malformed())

def _value():
    return st.recursive(
        _leaf(),
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(
                st.tuples(_string(), children).map(lambda t: t[0] + ":" + t[1]),
                max_size=4,
            ).map(lambda xs: "{" + ",".join(xs) + "}"),
        ),
        max_leaves=20,
    )

def _deep(depth):
    # build nested arrays/objects to a given depth
    return st.just(depth).map(
        lambda d: "[" * d + "0" + "]" * d
    )

def _deep_obj(depth):
    return st.just(depth).map(
        lambda d: '{"a":' * d + "0" + "}" * d
    )

def _depth_value():
    return st.one_of(
        st.integers(min_value=0, max_value=1000).flatmap(_deep),
        st.integers(min_value=0, max_value=1000).flatmap(_deep_obj),
        st.integers(min_value=999, max_value=1003).flatmap(_deep),
        st.integers(min_value=999, max_value=1003).flatmap(_deep_obj),
    )

# ---------- top-level strategy ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", " \t\n"])

def _maybe_ws(s):
    s_strategy = st.just(s) if isinstance(s, str) else s
    return st.tuples(_ws, s_strategy, _ws).map(lambda t: t[0] + t[1] + t[2])

def _valid_doc():
    # small, definitely-valid documents to drive print_value/print_object/print_string/print_number
    return st.recursive(
        st.one_of(_number(), _string(), _literal()),
        lambda children: st.one_of(
            st.lists(children, max_size=3).map(lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(
                st.tuples(_string(), children).map(lambda t: t[0] + ":" + t[1]),
                max_size=3,
            ).map(lambda xs: "{" + ",".join(xs) + "}"),
        ),
        max_leaves=12,
    )

def _compare_pair():
    # drive cJSON_Compare: pairs of valid docs sharing a common prefix to encourage
    # matching structure so the comparison walks deeply before diverging.
    def build(prefix):
        tail = st.one_of(_number(), _string(), _literal())
        return st.tuples(tail, tail).map(
            lambda tt: prefix + "[" + tt[0] + "," + tt[1] + "]"
        )
    common = st.one_of(
        st.just("["),
        st.just('{"a":['),
        st.just('{"k":'),
    )
    return st.tuples(common, st.one_of(_number(), _string(), _literal())).map(
        lambda t: t[0] + t[1] + "]" * (t[0].count("[") - t[0].count("]"))
    )

# ---------- print / compare drivers (added to reach print_* and cJSON_Compare) ----------

def _print_doc():
    # Documents designed to exercise print_object / print_string_ptr / print_number /
    # print_value. Include empty containers, nested containers, strings needing
    # escaping, Unicode escapes, and a wide variety of number formats.
    def key():
        return st.one_of(
            st.just('"a"'),
            st.just('"key with space"'),
            st.just('"tab\\there"'),
            st.just('"quote\\"inside"'),
            st.just('"back\\\\slash"'),
            st.just('"uni\\u00e9"'),
            st.just('"newline\\n"'),
            st.just('"\\u0000nul"'),
            st.just('"\\uD834\\uDD1E"'),  # surrogate pair
            st.just('""'),
        )

    def num():
        return st.one_of(
            st.just("0"), st.just("-0"), st.just("0.0"),
            st.just("123"), st.just("-123"),
            st.just("1.5"), st.just("-1.5e10"),
            st.just("1e-5"), st.just("1E+10"),
            st.integers(min_value=-(10**12), max_value=10**12).map(str),
            st.integers(min_value=0, max_value=10**6).map(lambda n: str(n) + "." + str(n)),
        )

    def leaf():
        return st.one_of(
            num(),
            _string(),
            st.just("true"), st.just("false"), st.just("null"),
        )

    def value(depth):
        if depth <= 0:
            return leaf()
        return st.one_of(
            leaf(),
            st.lists(leaf(), max_size=3).map(lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(
                st.tuples(key(), leaf()).map(lambda t: t[0] + ":" + t[1]),
                max_size=3,
            ).map(lambda xs: "{" + ",".join(xs) + "}"),
            st.lists(
                st.tuples(key(), value(depth - 1)).map(lambda t: t[0] + ":" + t[1]),
                max_size=3,
            ).map(lambda xs: "{" + ",".join(xs) + "}"),
            st.lists(value(depth - 1), max_size=3).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.just("{}"),
            st.just("[]"),
        )

    return st.one_of(
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":{}}'),
        st.just('[[]]'),
        st.just('{"a":[],"b":{},"c":[{}]}'),
        value(3),
    )

def _compare_doc_pair():
    # Produce pairs of documents that are structurally identical, or differ in
    # exactly one leaf, to exercise cJSON_Compare's deep recursion and matching
    # paths. We build a shared skeleton and vary one leaf.
    def skeleton(depth):
        if depth <= 0:
            return st.one_of(
                st.just("0"), st.just("1"), st.just("true"),
                st.just("null"), st.just('"x"'), st.just("[]"), st.just("{}"),
            )
        return st.one_of(
            st.lists(skeleton(depth - 1), min_size=1, max_size=3).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(
                    st.sampled_from(['"a"', '"b"', '"c"']),
                    skeleton(depth - 1),
                ).map(lambda t: t[0] + ":" + t[1]),
                min_size=1, max_size=3,
            ).map(lambda xs: "{" + ",".join(xs) + "}"),
            skeleton(depth - 1),
        )

    def variant(doc):
        # Slightly perturb a document's text so compare walks it then diverges.
        swaps = st.sampled_from([
            ("0", "1"), ("1", "0"), ("true", "false"), ("null", "true"),
            ('"x"', '"y"'), ("[]", "[0]"), ("{}", '{"a":0}'),
        ])
        return swaps.map(lambda sw: doc.replace(sw[0], sw[1], 1))

    skel = skeleton(st.integers(min_value=1, max_value=3).flatmap(
        lambda d: st.just(d)
    ) if False else 2)

    return st.one_of(
        # identical pair
        skel.map(lambda s: (s, s)),
        # differ in one spot
        skel.flatmap(lambda s: variant(s).map(lambda v: (s, v))),
        # type mismatch at top-level
        st.tuples(
            st.sampled_from(["1", "true", "null", '"s"', "[]", "{}"]),
            st.sampled_from(["1", "true", "null", '"s"', "[]", "{}"]),
        ),
    )

# ---------- top-level strategy ----------

strategy = st.one_of(
    _value(),
    _depth_value(),
    _maybe_ws(st.one_of(_value(), _number(), _string(), _literal())),
    st.one_of(_malformed(), st.just("\x00"), st.just("{}"), st.just("[]")),
    _maybe_ws(_valid_doc()),
    _maybe_ws(_valid_doc()),
    _compare_pair(),
    _maybe_ws(_print_doc()),
    _maybe_ws(_print_doc()),
    _compare_doc_pair().map(lambda p: p[0]),
    _compare_doc_pair().map(lambda p: p[1]),
).map(lambda s: s if isinstance(s, str) else str(s))
```