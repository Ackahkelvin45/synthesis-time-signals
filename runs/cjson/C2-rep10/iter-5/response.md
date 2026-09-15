```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

# SAFECODEPOINT: everything except " \ and control chars 0x00-0x1F
_safe_char = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in raw text
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# raw control / NUL bytes allowed by the parser inside strings (deviation)
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x0b", "\x0c", "\x7f"]
)

_escape_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# \uXXXX escapes: include lone surrogates (parser rejects) and paired surrogates
_u_escape = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet=_hex, min_size=4, max_size=4),
)

_high_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(
    lambda n: "\\u%04x" % n
)
_low_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)
_surrogate_pair = st.tuples(_high_surrogate, _low_surrogate).map(lambda t: t[0] + t[1])
_lone_surrogate = st.one_of(_high_surrogate, _low_surrogate)

_string_body = st.one_of(
    _safe_char,
    _raw_control,
    _escape_simple,
    _u_escape,
    _surrogate_pair,
    _lone_surrogate,
)

_string = st.lists(_string_body, max_size=12).map(lambda cs: '"' + "".join(cs) + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text(alphabet="123456789", min_size=1, max_size=1).flatmap(
    lambda first: st.tuples(
        st.just(first), st.text(alphabet="0123456789", min_size=0, max_size=6)
    ).map(lambda t: t[0] + t[1])
)

_int_part = st.one_of(
    st.just("0"),
    _nonzero_digits,
    # leading zeros: accepted by parser, rejected by strict
    st.text(alphabet="0123456789", min_size=2, max_size=5).filter(
        lambda s: s[0] == "0"
    ),
)

_frac = st.one_of(
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
    st.just("."),  # trailing dot, accepted by parser
)

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    _digits,
).map(lambda t: t[0] + t[1] + t[2])

# extreme exponents / magnitudes
_extreme_exp = st.sampled_from(
    [
        "e309", "E309", "e-309", "e999", "e-999", "e2147483647",
        "e-2147483648", "e308", "e400", "E+400", "e-400",
        "e0000000000000000001", "e999999999999999999999",
    ]
)

_hex_number = st.tuples(
    st.sampled_from(["0x", "0X", "-0x", "-0X"]),
    st.text(alphabet=_hex, min_size=1, max_size=8),
).map(lambda t: t[0] + t[1])

_sign = st.sampled_from(["", "-"])

_plain_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
).map(
    lambda t: t[0]
    + t[1]
    + (t[2] if t[2] is not None else "")
    + (t[3] if t[3] is not None else "")
)

_magnitude_number = st.tuples(
    st.one_of(st.just("1"), st.just("0"), _digits),
    _extreme_exp,
).map(lambda t: t[0] + t[1])

# malformed numbers the parser rejects
_malformed_number = st.sampled_from(
    ["-", "+1", ".5", "-.5", "01", "0x", "1e", "1e+", "--1", "1..2", "+", "."]
)

_number = st.one_of(
    _plain_number,
    _magnitude_number,
    _hex_number,
    _malformed_number,
)

# ---------- malformed string fragments ----------

_unterminated_string = st.lists(_string_body, max_size=8).map(
    lambda cs: '"' + "".join(cs)
)

_malformed_string = st.one_of(
    _unterminated_string,
    st.just("'single'"),
    st.just('"bad\\x"'),
    st.just('"\\u12"'),
    st.just('"unclosed'),
)

# ---------- malformed structural fragments ----------

_malformed_frag = st.sampled_from(
    [
        "{,}",
        "[,]",
        "{,}",
        "[1,]",
        '{"a":1,}',
        "[1 2]",
        '{"a" 1}',
        "{a:1}",
        "{'a':1}",
        "[",
        "]",
        "{",
        "}",
        '{"a":}',
        "[,]",
        "{:1}",
        "[1,,2]",
        '{"a":1 "b":2}',
    ]
)

# ---------- recursive value ----------

_json_value = st.deferred(lambda: _value)

# leaf values
_leaf = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# pair: STRING ':' value
_pair = st.tuples(_string, _json_value).map(lambda t: t[0] + ":" + t[1])

# broaden accepted structures: whitespace variants, nested empty containers,
# varied key shapes, and wider fan-out for arrays/objects.
_ws = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  "])

_key = st.one_of(
    _string,
    _string.map(lambda s: s),  # keep identity, but allow duplicates elsewhere
    st.sampled_from(['""', '"a"', '"key"', '"\\u0000"', '"\\n"', '" "']),
)

_ws_pair = st.tuples(_key, _ws, _ws, _json_value).map(
    lambda t: t[0] + t[1] + ":" + t[2] + t[3]
)

_obj = st.one_of(
    st.just("{}"),
    st.tuples(_ws, _ws).map(lambda t: "{" + t[0] + t[1] + "}"),
    st.lists(_ws_pair, min_size=1, max_size=8).map(
        lambda ps: "{" + ",".join(ps) + "}"
    ),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(_ws, _ws).map(lambda t: "[" + t[0] + t[1] + "]"),
    st.lists(_json_value, min_size=1, max_size=8).map(
        lambda vs: "[" + ",".join(vs) + "]"
    ),
    st.lists(_json_value, min_size=1, max_size=6).map(
        lambda vs: "[" + ", ".join(vs) + "]"
    ),
)

# base for recursion: leaves + malformed fragments (as "values")
_base_value = st.one_of(_leaf, _malformed_string, _malformed_frag, _malformed_number)

_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        st.lists(children, min_size=1, max_size=8).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(
            st.tuples(_key, children).map(lambda t: t[0] + ":" + t[1]),
            min_size=1,
            max_size=8,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        # nested empty containers as children (diversify structures)
        st.just("[]"),
        st.just("{}"),
    ),
)

# ---------- deep nesting near the 1000-level limit ----------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth


_depth_choice = st.integers(min_value=700, max_value=950)


@st.composite
def _deeply_nested(draw):
    depth = draw(_depth_choice)
    kind = draw(st.sampled_from(["arr", "obj", "mixed"]))
    inner = draw(st.one_of(_leaf, st.just("1"), st.just('"x"'), st.just("null")))
    if kind == "arr":
        return _deep(depth, "[", "]", inner)
    if kind == "obj":
        return _deep(depth, '{"k":', "}", inner)
    # mixed
    out = inner
    for i in range(depth):
        if i % 2 == 0:
            out = "[" + out + "]"
        else:
            out = '{"k":' + out + "}"
    return out


# ---------- duplicate keys ----------

@st.composite
def _dup_keys(draw):
    n = draw(st.integers(min_value=2, max_value=8))
    key = draw(_string)
    vals = draw(st.lists(_leaf, min_size=n, max_size=n))
    pairs = [key + ":" + v for v in vals]
    return "{" + ",".join(pairs) + "}"


# ---------- BOM, trailing content, NUL placement ----------

_bom = st.just("\ufeff")

_trailing = st.sampled_from(
    ["", "1abc", " \n\t", "\x00", " 1 2", "xyz", "]", "}", ",", "null"]
)


@st.composite
def _with_bom_and_trailing(draw):
    bom = draw(st.one_of(st.just(""), _bom))
    v = draw(_value)
    tr = draw(_trailing)
    return bom + v + tr


# ---------- broaden: whitespace-padded and structural variants ----------

@st.composite
def _padded_value(draw):
    lead = draw(_ws)
    v = draw(_value)
    trail = draw(_ws)
    return lead + v + trail


@st.composite
def _structure_diverse(draw):
    # build wider/deeper mixed structures with varied fan-out
    shape = draw(st.sampled_from(["wide_arr", "wide_obj", "mixed_deep", "empty_heavy"]))
    if shape == "wide_arr":
        n = draw(st.integers(min_value=3, max_value=12))
        items = draw(st.lists(_leaf, min_size=n, max_size=n))
        return "[" + ",".join(items) + "]"
    if shape == "wide_obj":
        n = draw(st.integers(min_value=3, max_value=12))
        keys = draw(st.lists(_key, min_size=n, max_size=n))
        vals = draw(st.lists(_leaf, min_size=n, max_size=n))
        return "{" + ",".join(k + ":" + v for k, v in zip(keys, vals)) + "}"
    if shape == "mixed_deep":
        depth = draw(st.integers(min_value=3, max_value=40))
        out = draw(_leaf)
        for i in range(depth):
            if i % 3 == 0:
                out = "[" + out + "]"
            elif i % 3 == 1:
                out = "{" + draw(_key) + ":" + out + "}"
            else:
                out = "[" + out + "," + draw(_leaf) + "]"
        return out
    # empty_heavy
    n = draw(st.integers(min_value=1, max_value=8))
    parts = draw(st.lists(st.sampled_from(["[]", "{}"]), min_size=n, max_size=n))
    return "[" + ",".join(parts) + "]"


# ---------- broaden exploration: diversify accepted structures ----------

@st.composite
def _structure_broaden(draw):
    shape = draw(
        st.sampled_from(
            [
                "arr_of_objs",
                "obj_of_arrs",
                "arr_of_arrs",
                "obj_of_objs",
                "mixed_matrix",
                "kw_heavy",
                "scalar_alternating",
                "ragged",
                "balanced_tree",
                "ws_matrix",
            ]
        )
    )

    _scalars = st.sampled_from(
        [
            "1", "0", "-1", "1.5", "1e10", "1e-10", "0x1f", "true",
            "false", "null", "NaN", "Infinity", "-Infinity", '""',
            '"a"', '"key"', '"\\n"', '"\\u0041"',
        ]
    )

    if shape == "arr_of_objs":
        n = draw(st.integers(min_value=1, max_value=6))
        objs = []
        for _ in range(n):
            m = draw(st.integers(min_value=0, max_value=4))
            pairs = []
            for _ in range(m):
                k = draw(_key)
                v = draw(st.one_of(_scalars, st.just("[]"), st.just("{}")))
                pairs.append(k + ":" + v)
            objs.append("{" + ",".join(pairs) + "}")
        return "[" + ",".join(objs) + "]"

    if shape == "obj_of_arrs":
        n = draw(st.integers(min_value=1, max_value=6))
        pairs = []
        for _ in range(n):
            k = draw(_key)
            m = draw(st.integers(min_value=0, max_value=4))
            items = draw(st.lists(_scalars, min_size=m, max_size=m))
            pairs.append(k + ":[" + ",".join(items) + "]")
        return "{" + ",".join(pairs) + "}"

    if shape == "arr_of_arrs":
        n = draw(st.integers(min_value=1, max_value=6))
        rows = []
        for _ in range(n):
            m = draw(st.integers(min_value=0, max_value=5))
            items = draw(st.lists(_scalars, min_size=m, max_size=m))
            rows.append("[" + ",".join(items) + "]")
        return "[" + ",".join(rows) + "]"

    if shape == "obj_of_objs":
        n = draw(st.integers(min_value=1, max_value=5))
        pairs = []
        for _ in range(n):
            k = draw(_key)
            m = draw(st.integers(min_value=0, max_value=4))
            inner = []
            for _ in range(m):
                ik = draw(_key)
                iv = draw(_scalars)
                inner.append(ik + ":" + iv)
            pairs.append(k + ":{" + ",".join(inner) + "}")
        return "{" + ",".join(pairs) + "}"

    if shape == "mixed_matrix":
        rows = draw(st.integers(min_value=1, max_value=5))
        cols = draw(st.integers(min_value=1, max_value=5))
        cells = draw(
            st.lists(
                st.one_of(_scalars, st.just("[]"), st.just("{}")),
                min_size=rows * cols,
                max_size=rows * cols,
            )
        )
        out_rows = []
        for i in range(rows):
            out_rows.append("[" + ",".join(cells[i * cols:(i + 1) * cols]) + "]")
        return "[" + ",".join(out_rows) + "]"

    if shape == "kw_heavy":
        n = draw(st.integers(min_value=2, max_value=8))
        pairs = []
        for _ in range(n):
            k = draw(st.sampled_from(['"a"', '"b"', '"c"', '"key"', '""', '"x y"']))
            v = draw(_scalars)
            pairs.append(k + ":" + v)
        return "{" + ",".join(pairs) + "}"

    if shape == "scalar_alternating":
        n = draw(st.integers(min_value=2, max_value=10))
        items = draw(st.lists(_scalars, min_size=n, max_size=n))
        return "[" + ",".join(items) + "]"

    if shape == "ragged":
        n = draw(st.integers(min_value=1, max_value=6))
        rows = []
        for _ in range(n):
            m = draw(st.integers(min_value=0, max_value=6))
            items = draw(st.lists(_scalars, min_size=m, max_size=m))
            rows.append("[" + ",".join(items) + "]")
        return "[" + ",".join(rows) + "]"

    if shape == "balanced_tree":
        depth = draw(st.integers(min_value=1, max_value=5))
        def build(d):
            if d == 0:
                return draw(_scalars)
            left = build(d - 1)
            right = build(d - 1)
            if draw(st.booleans()):
                return "[" + left + "," + right + "]"
            return '{"l":' + left + ',"r":' + right + "}"
        return build(depth)

    # ws_matrix
    rows = draw(st.integers(min_value=1, max_value=4))
    cols = draw(st.integers(min_value=1, max_value=4))
    cells = draw(
        st.lists(
            st.one_of(_scalars, st.just("[]"), st.just("{}")),
            min_size=rows * cols,
            max_size=rows * cols,
        )
    )
    out_rows = []
    for i in range(rows):
        out_rows.append(
            draw(_ws) + "[" + ("," + draw(_ws)).join(cells[i * cols:(i + 1) * cols]) + "]" + draw(_ws)
        )
    return draw(_ws) + "[" + ("," + draw(_ws)).join(out_rows) + "]" + draw(_ws)


# ---------- top-level strategy ----------

strategy = st.one_of(
    _value,
    _deeply_nested(),
    _dup_keys(),
    _with_bom_and_trailing(),
    _padded_value(),
    _structure_diverse(),
    _structure_broaden(),
    # ensure some pure edge cases appear
    st.sampled_from(
        [
            "{}",
            "[]",
            "1e309",
            "1e-309",
            "0x10",
            "01",
            "1.",
            "\ufeff{}",
            "\x00",
            '"\\ud800"',
            '"\\udc00"',
            '"\\ud83d\\ude00"',
            '"a\x00b"',
            '"a\tb"',
            "NaN",
            "Infinity",
            "-",
            "+1",
            ".5",
            "[1,]",
            '{"a":1,}',
            "[1 2]",
            '{"a" 1}',
        ]
    ),
)
```