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

# exercise print_* functions: round-trip valid docs through print/unformatted/compare paths
_printed = st.one_of(_value(), _number(), _string(), _literal()).map(
    lambda s: json.dumps(json.loads(s)) if _is_valid_json(s) else s
) if False else st.nothing()

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

strategy = st.one_of(
    _value(),
    _depth_value(),
    _maybe_ws(st.one_of(_value(), _number(), _string(), _literal())),
    st.one_of(_malformed(), st.just("\x00"), st.just("{}"), st.just("[]")),
    _maybe_ws(_valid_doc()),
).map(lambda s: s if isinstance(s, str) else str(s))
```