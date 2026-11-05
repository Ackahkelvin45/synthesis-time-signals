from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Safe-ish string characters (no raw NUL, no lone control chars unescaped).
_plain_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates as raw chars
    blacklist_characters="\x00",   # never a raw NUL
)

# Escapes that are valid inside a JSON string.
_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes (valid syntactically as \uXXXX escapes).
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


# A well-formed JSON string literal.
_wellformed_string = _string_body().map(lambda body: '"' + body + '"')

# Malformed string variants.
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


# Extreme / overflow numbers (non-finite -> rejected by parser).
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

# Near-valid-but-malformed numbers.
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

# Depth budget: concentrate near the parser cap (~2048).
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
    # children: strategy producing a value string
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
        # Build a nested structure of depth d around a leaf.
        inner = st.one_of(_leaf_value, st.just(""))
        # Iteratively wrap; do it via reduce over a fixed count.
        def wrap(acc, _i):
            return st.tuples(open_c, acc, close_c).map(
                lambda t: t[0] + t[1] + t[2]
            )

        # st.lists would draw a count, but we already have d; use a fold.
        result = inner
        for _ in range(d):
            result = wrap(result, None)
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

# Optional trailing content after a complete value (parser accepts it).
strategy = st.tuples(
    _document,
    st.one_of(st.just(""), _ws, st.sampled_from(["xyz", " garbage", "\n1"])),
).map(lambda t: t[0] + t[1])