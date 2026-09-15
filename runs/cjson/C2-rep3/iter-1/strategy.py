from hypothesis import strategies as st
import json


# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*[st.sampled_from(_hex)] * 4).map("".join)


def _unicode_escape():
    return st.one_of(
        _hex4(),
        # surrogate range escapes (lone surrogates are rejected by parser)
        st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DC00"]),
        # valid surrogate pairs
        st.tuples(
            st.sampled_from(["d800", "d801", "d83d", "dbff"]),
            st.sampled_from(["dc00", "dc01", "de00", "dfff"]),
        ).map(lambda p: p[0] + p[1]),
        st.just("0000"),
        st.just("001f"),
        st.just("007f"),
        st.just("ffff"),
    )


def _simple_escape():
    return st.sampled_from(['"', "\\", "/", "b", "f", "n", "r", "t"])


def _escape():
    return st.one_of(
        _simple_escape(),
        st.tuples(st.just("u"), _unicode_escape()).map(lambda p: p[0] + p[1]),
    )


# raw bytes allowed inside strings. Include control chars and NUL.
# SAFECODEPOINT in the grammar excludes " \ and 0x00-0x1F, but the parser
# accepts raw control/NUL inside strings, so we deliberately emit them.
_raw_string_char = st.one_of(
    st.characters(
        blacklist_categories=("Cs",),  # avoid lone surrogates from python side
        blacklist_characters='"\\',
    ),
    st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
)


def _string_body():
    return st.one_of(
        st.lists(_raw_string_char, min_size=0, max_size=12).map("".join),
        st.lists(
            st.tuples(st.just("\\"), _escape()).map(lambda p: p[0] + p[1]),
            min_size=0,
            max_size=6,
        ).map("".join),
        st.lists(
            st.one_of(
                _raw_string_char,
                st.tuples(st.just("\\"), _escape()).map(lambda p: p[0] + p[1]),
            ),
            min_size=0,
            max_size=10,
        ).map("".join),
    )


def _string():
    return _string_body().map(lambda b: '"' + b + '"')


# ---------- numbers ----------

_digit = st.integers(min_value=0, max_value=9).map(str)
_nonzero = st.integers(min_value=1, max_value=9).map(str)


def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(_nonzero, st.lists(_digit, max_size=10).map("".join)).map(
            lambda p: p[0] + p[1]
        ),
        # leading zeros (parser accepts, grammar forbids)
        st.lists(_digit, min_size=2, max_size=6).map("".join),
    )


def _frac_part():
    return st.one_of(
        st.lists(_digit, min_size=1, max_size=10).map(lambda ds: "." + "".join(ds)),
        st.just("."),  # trailing dot, parser accepts
    )


def _exp_part():
    return st.one_of(
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.lists(_digit, min_size=1, max_size=4).map("".join),
        ).map(lambda p: p[0] + p[1] + p[2]),
        # extreme magnitudes
        st.sampled_from(
            ["e309", "e308", "e400", "e-400", "E+9999", "e999999999", "e0", "e01"]
        ),
    )


def _number():
    sign = st.sampled_from(["", "-"])
    body = st.one_of(
        _int_part(),
        st.tuples(_int_part(), _frac_part()).map(lambda p: p[0] + p[1]),
        st.tuples(_int_part(), _exp_part()).map(lambda p: p[0] + p[1]),
        st.tuples(_int_part(), _frac_part(), _exp_part()).map(
            lambda p: p[0] + p[1] + p[2]
        ),
        # hex (parser accepts)
        st.tuples(
            st.just("0"),
            st.sampled_from(["x", "X"]),
            st.lists(st.sampled_from(_hex), min_size=1, max_size=8).map("".join),
        ).map(lambda p: p[0] + p[1] + p[2]),
        # extremes
        st.sampled_from(
            [
                "0",
                "-0",
                "1e309",
                "-1e309",
                "1e-309",
                "1E400",
                "123456789012345678901234567890",
                "1.7976931348623157e308",
                "5e-324",
            ]
        ),
    )
    return st.tuples(sign, body).map(lambda p: p[0] + p[1])


# ---------- recursive value ----------

_leaf = st.one_of(
    _string(),
    _number(),
    st.sampled_from(["true", "false", "null"]),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])


def _pair():
    return st.tuples(_string(), st.just(":"), _leaf).map(lambda p: "".join(p))


def _obj_body():
    return st.one_of(
        st.just(""),
        st.lists(_pair(), min_size=1, max_size=4).map(
            lambda ps: ",".join(ps)
        ),
        # duplicate keys
        st.tuples(_string(), st.just(":"), _leaf, st.just(","), _string(), st.just(":"), _leaf).map(
            lambda p: "".join(p)
        ),
    )


def _arr_body():
    return st.one_of(
        st.just(""),
        st.lists(_leaf, min_size=1, max_size=5).map(lambda xs: ",".join(xs)),
    )


# We use st.recursive so nesting is genuine, not a flattened blob.
_json_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.tuples(
            st.just("{"), _ws, _obj_body_with(children), _ws, st.just("}")
        ).map(lambda p: "".join(p)),
        st.tuples(
            st.just("["), _ws, _arr_body_with(children), _ws, st.just("]")
        ).map(lambda p: "".join(p)),
    ),
    max_leaves=20,
)


def _obj_body_with(value_strategy):
    pair = st.tuples(
        _string(), _ws, st.just(":"), _ws, value_strategy
    ).map(lambda p: "".join(p))
    return st.one_of(
        st.just(""),
        st.lists(pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
        st.tuples(
            pair,
            st.just(","),
            pair,
        ).map(lambda p: "".join(p)),
    )


def _arr_body_with(value_strategy):
    return st.one_of(
        st.just(""),
        st.lists(value_strategy, min_size=1, max_size=5).map(lambda xs: ",".join(xs)),
    )


# ---------- deep nesting near the 1000 limit ----------

def _deep_nesting():
    # depths around the parser's 1000-level limit.
    depth = st.one_of(
        st.integers(min_value=1, max_value=20),
        st.sampled_from([99, 100, 500, 990, 998, 999, 1000, 1001, 1002, 1010, 1100]),
    )
    kind = st.sampled_from(["[", "{"])
    return st.tuples(kind, depth).map(_build_nested)


def _build_nested(kd):
    kind, depth = kd
    if kind == "[":
        return "[" * depth + "]" * depth
    # objects: {"a":{"a":...null...}}
    return '{"a":' * depth + "null" + "}" * depth


# ---------- malformed / near-valid ----------

_malformed = st.sampled_from(
    [
        "",
        "{",
        "}",
        "[",
        "]",
        "[,]",
        "[1,]",
        "{,}",
        '{"a":1,}',
        '{"a" 1}',
        '{"a":}',
        "{:1}",
        '"unterminated',
        "'single'",
        "{a:1}",
        "{'a':1}",
        "[1 2]",
        '{"a":1 "b":2}',
        "01",
        "007",
        "1.",
        "-",
        "+1",
        ".5",
        "-.5",
        "1e",
        "1e+",
        "1e-",
        "NaN",
        "Infinity",
        "-Infinity",
        "0x",
        "0xG",
        '"\\ud800"',
        '"\\udfff"',
        '"\\x41"',
        '"\\u12"',
        '"\\u"',
        "[1,,2]",
        '{"a":1,,"b":2}',
        "[",
        "[[[[",
        "]]]]",
        "\x00",
        "\x00\x00",
        '"a\x00b"',
        '"a\nb"',
        '"a\tb"',
        "\ufeff1",
        "\ufeff",
        "tru",
        "fals",
        "nul",
        "TRUE",
        "Null",
        "00",
        "-01",
        "1..2",
        "1.2.3",
        "1e1e1",
        "[1,2",
        '{"a":1',
    ]
)


# ---------- trailing content (accepted by parser) ----------

def _trailing():
    return st.tuples(
        _json_value,
        st.sampled_from(
            [
                "abc",
                " 1 2",
                "\x00",
                "\x00junk",
                "garbage",
                "}",
                "]",
                "1e309",
                "\ufeff",
            ]
        ),
    ).map(lambda p: p[0] + p[1])


# ---------- BOM ----------

def _bom():
    return st.tuples(st.just("\ufeff"), _json_value).map(lambda p: p[0] + p[1])


# ---------- top-level strategy ----------

strategy = st.one_of(
    _json_value,
    _deep_nesting(),
    _malformed,
    _trailing(),
    _bom(),
    st.tuples(_json_value, _ws).map(lambda p: p[0] + p[1]),
)