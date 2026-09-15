from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic building blocks
# ---------------------------------------------------------------------------

# Safe code points: anything except '"', '\\', and control chars 0x00-0x1F.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in the host string
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

# Raw control characters (including NUL) that the parser accepts inside strings.
_control_chars = st.integers(min_value=0, max_value=0x1F).map(chr)

# Escape sequences: standard short escapes plus \uXXXX.
_short_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.tuples(_hex_digit, _hex_digit, _hex_digit, _hex_digit).map(
    lambda t: "\\u" + "".join(t)
)

# Deliberately include lone surrogate escapes (rejected by the parser).
_surrogate_escape = st.tuples(
    st.sampled_from("dD"), _hex_digit, _hex_digit, _hex_digit
).map(lambda t: "\\u" + "".join(t))

_escape = st.one_of(_short_escapes, _unicode_escape, _surrogate_escape)

# A string body element: safe char, control char, or escape.
_string_piece = st.one_of(
    _safe_chars.map(str),
    _control_chars,
    _escape,
)

# A well-formed JSON string (quoted).
_json_string = st.lists(_string_piece, max_size=12).map(lambda parts: '"' + "".join(parts) + '"')

# Sometimes produce an unterminated string (missing closing quote).
_unterminated_string = st.lists(_string_piece, min_size=1, max_size=8).map(
    lambda parts: '"' + "".join(parts)
)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
    # leading-zero forms (accepted by this parser)
    st.tuples(st.just("0"), _digits).map(lambda t: t[0] + t[1]),
)

_optional_minus = st.booleans().map(lambda b: "-" if b else "")

_frac = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
    st.just("."),  # trailing dot, accepted by this parser
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map(lambda t: t[0] + t[1] + t[2]),
    # extreme exponents, including overflow like 1e309
    st.tuples(st.sampled_from("eE"), st.sampled_from(["", "+", "-"]), st.sampled_from(["309", "400", "999", "9999"]))
    .map(lambda t: t[0] + t[1] + t[2]),
)

_number = st.tuples(_optional_minus, _int_part, _frac, _exp).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)

# Malformed / near-valid numeric forms.
_bad_number = st.sampled_from([
    "-",
    "+1",
    ".5",
    "01",
    "007",
    "1.",
    "0x10",
    "1e",
    "1e+",
    "1e-",
    "--1",
    "1..2",
    "NaN",
    "Infinity",
    "-Infinity",
    "+Infinity",
    "1.2.3",
])


# ---------------------------------------------------------------------------
# Recursive value / object / array
# ---------------------------------------------------------------------------

# Depth concentration near the parser's 1000-level nesting limit.
_DEPTH_NEAR_LIMIT = st.integers(min_value=990, max_value=1005)

# We build the recursive structure with a bounded depth using st.recursive.
# The parser rejects nesting beyond 1000 levels; concentrate near that limit.

def _make_value_strategy():
    return st.recursive(
        # Leaves (non-recursive alternatives)
        st.one_of(
            _json_string,
            _number,
            _bad_number,
            _unterminated_string,
            st.sampled_from(["true", "false", "null"]),
        ),
        # Recursive alternatives: objects and arrays
        lambda children: st.one_of(_obj(children), _arr(children)),
        max_leaves=40,
    )


def _obj(children):
    # Duplicate keys are accepted by the parser, so we deliberately allow them.
    pair_key = st.one_of(_json_string, _unterminated_string)
    pair = st.tuples(pair_key, st.just(":"), children).map(
        lambda t: t[0] + t[1] + t[2]
    )
    # Sometimes omit the colon (malformed).
    bad_pair = st.tuples(pair_key, children).map(lambda t: t[0] + t[1])

    one_pair = st.one_of(pair, bad_pair)

    body = st.one_of(
        st.just(""),
        one_pair,
        st.lists(one_pair, min_size=2, max_size=5).map(lambda ps: ",".join(ps)),
        # double commas / trailing commas (malformed)
        st.lists(one_pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps) + ","),
        st.lists(one_pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps) + ",,"),
    )
    return st.tuples(st.just("{"), body, st.just("}")).map(lambda t: t[0] + t[1] + t[2])


def _arr(children):
    body = st.one_of(
        st.just(""),
        children,
        st.lists(children, min_size=2, max_size=5).map(lambda vs: ",".join(vs)),
        # trailing comma / double comma (malformed)
        st.lists(children, min_size=1, max_size=4).map(lambda vs: ",".join(vs) + ","),
        st.lists(children, min_size=1, max_size=4).map(lambda vs: ",".join(vs) + ",,"),
    )
    return st.tuples(st.just("["), body, st.just("]")).map(lambda t: t[0] + t[1] + t[2])


_value = _make_value_strategy()


# ---------------------------------------------------------------------------
# Deep nesting near the parser's 1000-level limit
# ---------------------------------------------------------------------------

def _deep_nesting(depth):
    """Build a deeply nested array or object of exactly `depth` levels."""
    # Base value at the innermost level.
    base = st.one_of(_number, _json_string, st.sampled_from(["true", "false", "null"]))

    # Build the nested structure iteratively using a single map to avoid
    # constructing a deeply nested chain of Hypothesis strategies (which would
    # blow Python's recursion limit during generation).
    def build(inner):
        # Decide for each level whether to wrap in an array or object.
        # We generate a list of booleans and apply the wrapping in a loop.
        choices = [bool(b) for b in inner[0]]
        value = inner[1]
        for is_arr in choices:
            if is_arr:
                value = "[" + value + "]"
            else:
                value = '{"k":' + value + "}"
        return value

    return st.tuples(
        st.lists(st.booleans(), min_size=depth, max_size=depth),
        base,
    ).map(build)


_deep_value = _DEPTH_NEAR_LIMIT.flatmap(_deep_nesting)


# ---------------------------------------------------------------------------
# Top-level strategy: valid, near-valid, and malformed JSON texts
# ---------------------------------------------------------------------------

# A value followed by trailing content (accepted: parser stops after first value).
_trailing_content = st.one_of(
    st.just(""),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("\x00"),
    st.just(" garbage"),
    st.sampled_from(["x", "}", "]", "123", "null"]),
)

_top_value = st.one_of(
    _value,
    _deep_value,
    # bare / malformed top-level fragments
    _bad_number,
    _unterminated_string,
    st.just(""),
    st.just(" "),
    st.just("{"),
    st.just("["),
    st.just("}"),
    st.just("]"),
    st.just(","),
    st.just(":"),
)

# Leading BOM (accepted by this parser).
_leading_bom = st.booleans().map(lambda b: "\ufeff" if b else "")

# Leading whitespace.
_leading_ws = st.text(alphabet=" \t\n\r", max_size=3)


strategy = st.tuples(
    _leading_bom,
    _leading_ws,
    _top_value,
    _trailing_content,
).map(lambda t: t[0] + t[1] + t[2] + t[3])