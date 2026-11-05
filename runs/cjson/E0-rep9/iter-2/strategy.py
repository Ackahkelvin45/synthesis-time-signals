from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_CHARS = (
    [chr(c) for c in range(0x20, 0x7F) if chr(c) not in '"\\']
    + [" ", "\t", "\n", "\r"]
    + ["\u00e9", "\u00fc", "\u4e2d", "\U0001F600", "\u00a0", "\u2028"]
)

_ESC = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
_HEX = "0123456789abcdefABCDEF"


def _unicode_escape():
    return st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet=_HEX, min_size=4, max_size=4),
    )


def _string_body():
    pieces = [
        st.sampled_from(_SAFE_CHARS),
        st.sampled_from(_ESC),
        _unicode_escape(),
        st.text(alphabet="\x00\x01\x07\x0b\x0c\x1f", min_size=0, max_size=3),
    ]
    return st.lists(st.one_of(*pieces), min_size=0, max_size=8).map("".join)


def _json_string():
    return _string_body().map(lambda body: '"' + body + '"')


# numbers --------------------------------------------------------------------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=1, max_value=10 ** 6).map(str),
        st.integers(min_value=10 ** 17, max_value=10 ** 19).map(str),
        st.just("01"),          # leading zero (parser accepts)
        st.just("00"),
    )


def _frac_part():
    return st.one_of(
        st.integers(min_value=0, max_value=10 ** 6).map(lambda n: "." + str(n)),
        st.just("."),
        st.just(".0"),
        st.just(".0000001"),
    )


def _exp_part():
    return st.one_of(
        st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
        st.integers(min_value=-400, max_value=400).map(lambda n: "E+" + str(abs(n))),
        st.just("e309"),
        st.just("e-309"),
        st.just("e999999"),
        st.just("E-999999"),
        st.just("e01"),
    )


def _number():
    sign = st.one_of(st.just(""), st.just("-"))
    return st.builds(
        lambda s, i, f, e: s + i + f + e,
        sign,
        _int_part(),
        st.one_of(st.just(""), _frac_part()),
        st.one_of(st.just(""), _exp_part()),
    )


# malformed numeric-ish tokens ----------------------------------------------

def _bad_number():
    return st.sampled_from([
        "-", "+1", ".5", "-.5", "1.", "-1.", "0x10", "0X1f", "0x",
        "NaN", "Infinity", "-Infinity", "1e", "1e+", "1.e5", "--1",
        "1.2.3", ".", "+", "0b101", "1_000",
    ])


# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

_LEAF = st.one_of(
    _json_string(),
    _number(),
    st.sampled_from(["true", "false", "null"]),
)

_LEAF_OR_BAD = st.one_of(_LEAF, _bad_number())


def _pair_leaf():
    return st.builds(
        lambda k, v: k + ":" + v,
        _json_string(),
        _LEAF_OR_BAD,
    )


def _arr_leaf():
    return _LEAF_OR_BAD


def _obj_from_pairs(pairs):
    return "{" + ",".join(pairs) + "}"


def _arr_from_vals(vals):
    return "[" + ",".join(vals) + "]"


def _value(depth):
    return st.recursive(
        _LEAF_OR_BAD,
        lambda children: st.one_of(
            st.lists(_pair_leaf(), min_size=0, max_size=4).map(_obj_from_pairs),
            st.lists(children, min_size=0, max_size=4).map(_arr_from_vals),
        ),
        max_leaves=depth,
    )


# ---------------------------------------------------------------------------
# Malformed structural fragments
# ---------------------------------------------------------------------------

def _malformed():
    return st.sampled_from([
        '{"a":1,}',
        '{"a":1,,}',
        '[1,2,]',
        '[1,,2]',
        '[,]',
        '{,}',
        '{"a" 1}',
        '{"a":}',
        '{:1}',
        '{"a":1',
        '[1,2',
        '"unterminated',
        '"unterminated\\',
        "'single'",
        '{a:1}',
        '{"a":1 "b":2}',
        '[]]',
        '{}}',
        'tru',
        'fals',
        'nul',
        'True',
        'NULL',
        '',
        '   ',
        '\xef\xbb\xbf',
        '\xef\xbb\xbf1',
        '1abc',
        '1 2',
        '\x00',
        '"\x00"',
        '"\\ud800"',
        '"\\ud800\\ud800"',
        '"\\udc00"',
        '"\\u"',
        '"\\u12"',
        '"\\uZZZZ"',
        '"\\x41"',
        '"\\q"',
    ])


# ---------------------------------------------------------------------------
# Deep nesting near the 1000-level limit
# ---------------------------------------------------------------------------

def _deep_nesting():
    depths = st.one_of(
        st.integers(min_value=990, max_value=1001),
        st.sampled_from([999, 1000, 1001, 1002]),
        st.integers(min_value=0, max_value=1001),
    )
    return st.builds(
        lambda d, kind, inner: (
            (kind[0] * d) + inner + (kind[1] * d)
        ),
        depths,
        st.sampled_from([("[", "]"), ("{\"a\":", "}")]),
        _LEAF,
    )


def _deep_arrays():
    return st.builds(
        lambda d: "[" * d + "]" * d,
        st.integers(min_value=999, max_value=1001),
    )


def _deep_objects():
    return st.builds(
        lambda d: '{"a":' * d + "1" + "}" * d,
        st.integers(min_value=999, max_value=1001),
    )


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value(6),
    _pair_leaf().map(lambda p: "{" + p + "}"),
    _malformed(),
    _deep_nesting(),
    _deep_arrays(),
    _deep_objects(),
    st.lists(_LEAF_OR_BAD, min_size=0, max_size=4).map(_arr_from_vals),
    st.lists(_pair_leaf(), min_size=0, max_size=4).map(_obj_from_pairs),
)