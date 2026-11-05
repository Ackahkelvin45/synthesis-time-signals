from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

_plain_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_unicode_escape = _hex4.map(lambda h: "\\u" + h)

_surrogate_escape = st.integers(min_value=0xD800, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)

_escapes = st.one_of(_simple_escapes, _unicode_escape, _surrogate_escape)


def _string_body():
    return st.recursive(
        st.one_of(_plain_chars, _escapes),
        lambda children: st.one_of(
            children,
            st.tuples(children, children).map(lambda t: t[0] + t[1]),
        ),
        max_leaves=12,
    )


_wellformed_string = _string_body().map(lambda body: '"' + body + '"')

_unterminated_string = _string_body().map(lambda body: '"' + body)
_bad_escape_string = st.sampled_from(['"\\x"', '"\\u12"', '"\\uZZZZ"', '"a\\"', '"\\u"'])


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=1, max_value=10**30).map(str),
)

_frac_part = st.one_of(
    st.nothing(),
    st.tuples(st.just("."), st.integers(min_value=0, max_value=10**9).map(str)).map(
        lambda t: t[0] + t[1]
    ),
)

_exp_part = st.one_of(
    st.nothing(),
    st.tuples(
        st.sampled_from("eE"),
        st.one_of(st.just(""), st.just("+"), st.just("-")),
        st.integers(min_value=0, max_value=9999).map(str),
    ).map(lambda t: t[0] + t[1] + t[2]),
)


def _number():
    sign = st.one_of(st.just(""), st.just("-"))
    return st.tuples(sign, _int_part, _frac_part, _exp_part).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )


_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e999",
        "1e-999",
        "1E+308",
        "123456789012345678901234567890",
        "0.0000000000000000000001",
        "1e308",
        "2e308",
        "-0",
        "0e0",
        "1e01",
    ]
)

_malformed_number = st.sampled_from(
    [
        "+1",
        ".5",
        "-.5",
        "1.",
        "01",
        "-01",
        "00",
        "1e",
        "1e+",
        "1e-",
        "--1",
        "1..2",
        "1e309e1",
    ]
)


# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

_ws_opt = st.one_of(st.just(""), _ws)


# ---------------------------------------------------------------------------
# Recursive values (obj / arr)
# ---------------------------------------------------------------------------

def _depth_budget():
    return st.one_of(
        st.integers(min_value=0, max_value=5),
        st.integers(min_value=2000, max_value=2048),
        st.integers(min_value=2049, max_value=2060),
    )


_leaf_value = st.one_of(
    _wellformed_string,
    _number(),
    _extreme_number,
    _malformed_number,
    _unterminated_string,
    _bad_escape_string,
    st.sampled_from(["true", "false", "null"]),
)


def _obj_strategy(children):
    pair = st.tuples(
        _wellformed_string,
        _ws_opt,
        st.just(":"),
        _ws_opt,
        children,
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

    pairs = st.lists(pair, min_size=0, max_size=4).map(lambda xs: ",".join(xs))

    return st.tuples(st.just("{"), _ws_opt, pairs, _ws_opt, st.just("}")).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )


def _arr_strategy(children):
    elems = st.lists(children, min_size=0, max_size=4).map(lambda xs: ",".join(xs))
    return st.tuples(st.just("["), _ws_opt, elems, _ws_opt, st.just("]")).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )


_value = st.recursive(
    _leaf_value,
    lambda children: st.one_of(_obj_strategy(children), _arr_strategy(children)),
    max_leaves=20,
)


# ---------------------------------------------------------------------------
# Deep nesting near the cap
# ---------------------------------------------------------------------------

def _deep_nesting():
    depth = _depth_budget()
    open_c = st.sampled_from(["[", "{"])
    close_c = st.sampled_from(["]", "}"])

    def build(d):
        inner = st.one_of(_leaf_value, st.just(""))

        def wrap(acc, _i):
            return st.tuples(open_c, acc, close_c).map(
                lambda t: t[0] + t[1] + t[2]
            )

        result = inner
        for _ in range(min(d, 64)):
            result = wrap(result, None)
        extra = max(0, d - 64)
        if extra:
            extra_open = st.sampled_from(["[", "{"]).map(lambda c: c * extra)
            extra_close = st.sampled_from(["]", "}"]).map(lambda c: c * extra)
            result = st.tuples(extra_open, result, extra_close).map(
                lambda t: t[0] + t[1] + t[2]
            )
        return result

    return depth.flatmap(build)


# ---------------------------------------------------------------------------
# Malformed / near-valid whole documents
# ---------------------------------------------------------------------------

_malformed_doc = st.sampled_from(
    [
        '{"a":1,}',
        "[1,2,]",
        '{"a" 1}',
        '{"a":}',
        "[,]",
        "[1,,2]",
        '{"a":1 "b":2}',
        "{,}",
        '{"a":1,,"b":2}',
        "[]xyz",
        "1 garbage",
        "1abc",
        "{}",
        "[]",
        "-",
        "-.",
        "truefalse",
        "nul",
        '"unterminated',
        '{"a":"\\u0000"}',
        '{"a":1}{"b":2}',
        "[[[[",
        "]]]]",
        '{"a":1,"a":2}',
        '{"k":0,"k":1}',
    ]
)


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

_document = st.one_of(
    _value,
    _deep_nesting(),
    _malformed_doc,
    _extreme_number,
    _malformed_number,
    _wellformed_string,
    _unterminated_string,
    _bad_escape_string,
)

# ---------------------------------------------------------------------------
# Round-trip / serialize / validate / deep-copy / equals coverage
# ---------------------------------------------------------------------------

# Small, semantically-rich JSON values that exercise the serializer,
# deep-copy, equals, and validate paths.
_small_json_value = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(10**9), max_value=10**9),
        st.floats(allow_nan=False, allow_infinity=False),
        _string_body().map(lambda b: b),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(
            _string_body().map(lambda b: b),
            children,
            max_size=4,
        ),
    ),
    max_leaves=10,
)


def _encode(v):
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return "null"


# A document that is guaranteed to be valid JSON, so that downstream
# operations (validate, deep_copy, equals, serialize) get exercised.
_valid_document = _small_json_value.map(_encode)

# Documents with surrounding whitespace / trailing content to also hit
# the validate path on near-valid inputs.
_valid_with_ws = st.tuples(_valid_document, _ws_opt).map(lambda t: t[1] + t[0] + t[1])

# Valid documents with strings containing characters that force the
# serializer's escaping path (control chars, quotes, backslashes, unicode).
_serialize_rich_string = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
    min_size=0,
    max_size=12,
).filter(lambda s: any(c in s for c in '"\\\n\r\t\b\f\u2028\u2029') or any(ord(c) < 0x20 for c in s))

_serialize_rich_value = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(10**9), max_value=10**9),
        st.floats(allow_nan=False, allow_infinity=False),
        _serialize_rich_string,
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(_serialize_rich_string, children, max_size=3),
    ),
    max_leaves=8,
)


def _encode_rich(v):
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return "null"


_serialize_rich_document = _serialize_rich_value.map(_encode_rich)

# Larger valid documents to exercise deep_copy / equals on nontrivial trees.
_large_valid_value = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(10**12), max_value=10**12),
        st.floats(allow_nan=False, allow_infinity=False),
        _string_body().map(lambda b: b),
    ),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=8),
        st.dictionaries(_string_body().map(lambda b: b), children, min_size=0, max_size=8),
    ),
    max_leaves=40,
)


def _encode_large(v):
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return "null"


_large_valid_document = _large_valid_value.map(_encode_large)

# Valid documents with surrounding whitespace to hit validate's success path.
_valid_ws_wrapped = st.tuples(
    st.one_of(_valid_document, _serialize_rich_document, _large_valid_document),
    _ws_opt,
).map(lambda t: t[1] + t[0] + t[1])

strategy = st.one_of(
    st.tuples(
        _document,
        st.one_of(st.just(""), _ws, st.sampled_from(["xyz", " garbage", "\n1"])),
    ).map(lambda t: t[0] + t[1]),
    _valid_document,
    _valid_with_ws,
    _serialize_rich_document,
    _large_valid_document,
    _valid_ws_wrapped,
)