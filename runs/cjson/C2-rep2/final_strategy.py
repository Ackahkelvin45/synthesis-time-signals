from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _join(parts):
    return "".join(parts)


# Characters allowed unescaped inside strings by the grammar, plus extras the
# parser tolerates (raw control chars, NUL).
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: c != "\x00" or True)  # NUL allowed, handled below

# We build string bodies from a mix of safe chars and explicit escapes.
_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Lone surrogates: parser rejects these, but include to exercise the decoder.
_lone_surrogate_escape = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff"]
)

# Raw control bytes and NUL, accepted by the parser inside strings.
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f"]
)

_string_body_atom = st.one_of(
    _SAFE_CHARS,
    _escapes,
    _unicode_escape,
    _lone_surrogate_escape,
    _raw_control,
)

_string_body = st.lists(_string_body_atom, max_size=12).map(_join)

# A properly quoted string.
_string = _string_body.map(lambda b: '"' + b + '"')

# Unterminated string: opening quote, no closing quote.
_unterminated_string = _string_body.map(lambda b: '"' + b)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

# Normal integers.
_int = st.one_of(
    st.just("0"),
    _int_digits.filter(lambda d: d[0] != "0" or len(d) == 1),
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
)

# Extreme magnitudes / exponents, including overflow like 1e309.
_extreme_number = st.one_of(
    st.sampled_from(
        [
            "1e309", "-1e309", "1e-309", "1e999", "-1e999",
            "1e308", "1.7976931348623157e308",
            "0e0", "0e999", "-0", "-0.0",
            "1e+308", "1e-308",
        ]
    ),
    st.integers(min_value=0, max_value=10**6).map(lambda n: f"{n}e{n}"),
    st.integers(min_value=0, max_value=10**6).map(lambda n: f"-{n}e-{n}"),
)

# Near-valid-but-malformed numeric forms.
_malformed_number = st.sampled_from(
    [
        "01", "007", "00", "1.", "-", "+1", ".5", "-.5", "+.5",
        "0x10", "0X1f", "0x", "1e", "1e+", "1e-", "1.e5",
        "--1", "1..2", ".", "1.2.3",
    ]
)

_number = st.one_of(_int, _extreme_number, _malformed_number)


# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the 1000-level nesting limit.
def _depth_strategy():
    return st.integers(min_value=0, max_value=1005)


# Leaf values. Upweight the "true"/"null" literals so the parser's literal
# productions get exercised more often (they were previously under-covered).
# "false" is upweighted here to close the productions_gap.
_leaf = st.one_of(
    _string,
    _number,
    st.sampled_from(
        [
            "true", "false", "null", "NaN", "Infinity", "-Infinity",
            "true", "false", "null", "true", "false", "null", "true", "null",
            "false", "false", "false", "false",
            "false", "false", "false", "false", "false", "false",
            "false", "false", "false", "false", "false", "false",
        ]
    ),
)

# Building blocks for structured values.
_key = _string

# Duplicate-key objects.
_duplicate_key_pair = st.sampled_from(
    ['"a":1', '"a":2', '"a":1,"a":2', '"k":null,"k":true']
)

# Malformed fragments.
_malformed_fragment = st.sampled_from(
    [
        ",", ",,", ":", "::", "{", "}", "[", "]", '{"a"}', '{"a":}',
        '{"a":1,}', "[1,]", "[,1]", "[1,,2]", "{,}", "{\"a\":1,}",
        "[", "{", '"', "'a'", "{a:1}", "{'a':1}", "[1 2]",
        '{"a" 1}', '{"a":1 "b":2}',
    ]
)


@st.composite
def _value_strategy(draw, max_depth=1005):
    depth = draw(st.integers(min_value=0, max_value=max_depth))

    def build(d):
        if d <= 0:
            return draw(_leaf)
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 3:
            return draw(_leaf)
        if choice == 4:
            # Object with pairs, possibly duplicate keys.
            n = draw(st.integers(min_value=0, max_value=4))
            if n == 0:
                return "{}"
            pairs = []
            for _ in range(n):
                if draw(st.booleans()):
                    pairs.append(draw(_duplicate_key_pair))
                else:
                    k = draw(_key)
                    v = build(d - 1)
                    pairs.append(k + ":" + v)
            return "{" + ",".join(pairs) + "}"
        if choice == 5:
            # Array.
            n = draw(st.integers(min_value=0, max_value=4))
            if n == 0:
                return "[]"
            items = [build(d - 1) for _ in range(n)]
            return "[" + ",".join(items) + "]"
        if choice == 6:
            # Deep nesting: chain of arrays/objects near the limit.
            kind = draw(st.integers(min_value=0, max_value=1))
            levels = draw(st.integers(min_value=1, max_value=min(d, 1005)))
            inner = build(max(0, d - levels))
            if kind == 0:
                return "[" * levels + inner + "]" * levels
            else:
                return '{"a":' * levels + inner + "}" * levels
        if choice == 7:
            # Malformed fragment.
            return draw(_malformed_fragment)
        if choice == 8:
            # Unterminated string.
            return draw(_unterminated_string)
        # Trailing content after a complete value.
        first = build(max(0, d - 1))
        tail = draw(
            st.one_of(
                st.just(""),
                st.just("abc"),
                st.just(" 1 2"),
                st.just("\x00"),
                st.just("garbage"),
            )
        )
        return first + tail

    return build(depth)


_value = st.deferred(lambda: _value_strategy())

# Top-level strategy: a value, optionally with a BOM or trailing bytes.
_top = st.one_of(
    _value,
    _value.map(lambda v: "\ufeff" + v),
    _value.map(lambda v: v + "\x00"),
)


def _finalize(v):
    # Ensure plain str (no surrogates that would break encoding downstream is
    # fine here; the harness works on bytes/str with explicit length).
    return str(v)


strategy = _top.map(_finalize)