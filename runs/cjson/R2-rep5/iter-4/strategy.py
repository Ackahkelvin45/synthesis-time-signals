from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helper building blocks
# ---------------------------------------------------------------------------

def _join(parts):
    return lambda t: "".join(t)

# A safe, ordinary string body (no need to be JSON-escaped since we build raw)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in raw text
    blacklist_characters='"\\',
)

def _raw_string_body():
    # Raw (unescaped) content, including control chars and NUL.
    return st.text(
        alphabet=st.one_of(
            _safe_chars,
            st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
        ),
        max_size=12,
    )

def _escape_seq():
    simple = st.sampled_from(
        ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
    )
    hexdigits = "0123456789abcdefABCDEF"
    unicode_esc = st.tuples(
        st.just("\\u"),
        st.text(alphabet=hexdigits, min_size=4, max_size=4),
    ).map("".join)
    # Deliberately include surrogate escapes (\ud800-\udfff)
    surrogate_esc = st.tuples(
        st.just("\\u"),
        st.sampled_from(["d", "D"]),
        st.text(alphabet="89abAB", min_size=1, max_size=1),
        st.text(alphabet=hexdigits, min_size=2, max_size=2),
    ).map("".join)
    return st.one_of(simple, unicode_esc, surrogate_esc)

def _json_string():
    body = st.one_of(
        _raw_string_body(),
        st.lists(st.one_of(_raw_string_body(), _escape_seq()), max_size=6).map(
            lambda parts: "".join(parts)
        ),
    )
    return st.tuples(st.just('"'), body, st.just('"')).map("".join)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _number():
    digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
    int_part = st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), digits).map("".join),
        # leading-zero deviation (accepted by parser)
        st.tuples(st.just("0"), digits).map("".join),
        # hex deviation (accepted by parser)
        st.tuples(st.just("0x"), st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=4)).map("".join),
    )
    sign = st.one_of(st.just(""), st.just("-"))
    frac = st.one_of(
        st.just(""),
        st.tuples(st.just("."), digits).map("".join),
        # trailing dot deviation
        st.just("."),
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.one_of(st.just(""), st.just("+"), st.just("-")),
            digits,
        ).map("".join),
    )
    # extreme magnitudes / overflow
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e999", "1e-999", "9" * 30, "-" + "9" * 30,
        "0e0", "1E+400", "1e-400",
    ])
    composed = st.tuples(sign, int_part, frac, exp).map("".join)
    return st.one_of(composed, extreme)

# ---------------------------------------------------------------------------
# Malformed fragments (near-valid but broken)
# ---------------------------------------------------------------------------

def _malformed():
    return st.sampled_from([
        "",            # empty input
        ",", "[,]", "{,}", "[1,,2]", '{"a":1,,"b":2}',
        "[1,2,]", '{"a":1,}', '{"a" 1}', '{"a":}', '{:1}',
        '"unterminated', "'single'", "{a:1}", "{'a':1}",
        "-", "+1", ".5", "NaN", "Infinity", "-Infinity",
        '["\\ud800"]', '["\\udfff"]',
        "tru", "fals", "nul", "truex", "01", "1.", "0x10",
        "[", "]", "{", "}", ":", "\\",
        '"\\q"', '"\\u12"', '"\\uZZZZ"',
    ])

# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

def _leaf():
    return st.one_of(
        _json_string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _ws():
    return st.text(alphabet=" \t\n\r", max_size=2)

def _value(draw_strategy):
    # draw_strategy is a SearchStrategy for nested values
    leaf = _leaf()

    def make_array(t):
        items = t
        return "[" + ",".join(items) + "]"

    def make_object(pairs):
        return "{" + ",".join(pairs) + "}"

    arr = st.lists(
        st.tuples(_ws(), draw_strategy, _ws()).map(lambda p: p[1]),
        max_size=4,
    ).map(make_array)

    def make_pair(kv):
        k, v = kv
        return k + ":" + v

    obj = st.lists(
        st.tuples(_json_string(), st.just(":"), draw_strategy).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        max_size=4,
    ).map(make_object)

    special = st.sampled_from(["{}", "[]"])

    return st.one_of(leaf, arr, obj, special)

# Depth-controlled recursive generation concentrating near the ~1000 limit.
def _nested(depth):
    # Build a value nested exactly `depth` levels deep using arrays.
    return st.just("[" * depth + "0" + "]" * depth)

def _deep_values():
    # Concentrate interesting depths near the limit.
    return st.one_of(
        st.integers(min_value=0, max_value=50).map(lambda d: "[" * d + "]" * d),
        st.integers(min_value=990, max_value=1010).map(
            lambda d: "[" * d + "0" + "]" * d
        ),
        st.integers(min_value=990, max_value=1010).map(
            lambda d: '{"a":' * d + "0" + "}" * d
        ),
        st.sampled_from([999, 1000, 1001]).map(
            lambda d: "[" * d + "]" * d
        ),
    )

# ---------------------------------------------------------------------------
# Whitespace / structural edge cases (targets lexer/parser branches)
# ---------------------------------------------------------------------------

def _ws_heavy():
    ws = st.text(alphabet=" \t\n\r", max_size=8)
    inner = _leaf()
    return st.tuples(
        ws,
        st.one_of(
            st.tuples(st.just("["), ws, inner, ws, st.just("]")).map("".join),
            st.tuples(
                st.just("{"),
                ws,
                _json_string(),
                ws,
                st.just(":"),
                ws,
                inner,
                ws,
                st.just("}"),
            ).map("".join),
            st.tuples(st.just("["), ws, inner, ws, st.just(","), ws, inner, ws, st.just("]")).map("".join),
        ),
        ws,
    ).map("".join)

def _lexer_edges():
    # Pieces that exercise string / number / literal lexing edge branches.
    return st.sampled_from([
        '""', '"\\u0000"', '"\\uFFFF"', '"\\uD800\\uDC00"',
        '"\\uD800x"', '"\\uDBFF"', '"\\uDFFF"',
        '"a\\u00e9b"', '"\\/"', '"\\\\"',
        "0", "-0", "0.0", "-0.0", "0e0", "0E-0",
        "1e0", "1e+0", "1e-0", "123456789012345678901234567890",
        "true", "false", "null",
        "  true  ", "\ttrue\n", "\r\nnull\r\n",
        "[ ]", "{ }", "[ 1 ]", '{ "a" : 1 }',
        "[\n1,\n2\n]", "{\n\"a\":\n1\n}",
        "[\"a\",\"b\",\"c\"]", '{"a":1,"b":2,"c":3}',
        '[[[[[]]]]]', '{"a":{"b":{"c":{}}}}',
    ])

# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

_base = st.recursive(
    _leaf(),
    _value,
    max_leaves=20,
)

_bom = st.one_of(st.just(""), st.just("\ufeff"))

_trailing = st.one_of(
    st.just(""),
    st.sampled_from(["abc", " 2", "\x00", " xyz", "1 2", "\n"]),
)

_valid = st.tuples(_bom, _base, _trailing).map("".join)

_malformed_top = st.tuples(_bom, _malformed()).map("".join)

# ---------------------------------------------------------------------------
# IMPROVEMENT: structural mutations of valid documents to hit parser error
# recovery / recovery branches that hand-written malformed cases miss.
# ---------------------------------------------------------------------------

def _mutate(s):
    """Apply a single random structural mutation to a valid JSON-ish string."""
    if not s:
        return s
    i = len(s) // 2
    return s[:i] + s[i + 1:]

_mutation_ops = st.sampled_from([
    lambda s: s[:-1] if s else s,                       # truncate
    lambda s: s[1:] if s else s,                        # drop first char
    lambda s: s.replace(",", "", 1),                    # drop a comma
    lambda s: s.replace(":", "", 1),                    # drop a colon
    lambda s: s.replace("[", "{", 1),                   # mismatched brackets
    lambda s: s.replace("]", "}", 1),
    lambda s: s + "]",                                  # extra closer
    lambda s: "[" + s,                                  # extra opener
    lambda s: s + ",",                                  # trailing comma
    lambda s: s.replace('"', "", 1),                    # drop a quote
    _mutate,
])

_structural_mutation = st.tuples(_base, _mutation_ops).map(
    lambda t: t[1](t[0])
)

# ---------------------------------------------------------------------------
# IMPROVEMENT: inject malformed fragments INSIDE otherwise-valid containers
# so the parser's per-element error handling / recovery code paths execute
# (previously malformed inputs were only ever top-level, which misses the
# recovery branches inside array/object element loops).
# ---------------------------------------------------------------------------

def _corrupt_inner():
    """Build a container whose elements are a mix of valid and broken parts."""
    bad = _malformed()
    good = _leaf()

    # Array with a broken element somewhere among valid ones.
    arr = st.lists(
        st.one_of(good, bad),
        min_size=1,
        max_size=4,
    ).map(lambda items: "[" + ",".join(items) + "]")

    # Object with a broken key or value.
    def make_obj(pairs):
        return "{" + ",".join(pairs) + "}"

    key = st.one_of(_json_string(), bad)
    val = st.one_of(good, bad)
    obj = st.lists(
        st.tuples(key, st.just(":"), val).map(lambda t: t[0] + t[1] + t[2]),
        min_size=1,
        max_size=4,
    ).map(make_obj)

    # Nest the corrupt container inside another (so recovery must unwind).
    wrapped_arr = arr.map(lambda s: "[" + s + "]")
    wrapped_obj = obj.map(lambda s: '{"k":' + s + "}")

    return st.one_of(arr, obj, wrapped_arr, wrapped_obj)

strategy = st.one_of(
    _valid,
    _malformed_top,
    _deep_values(),
    _ws_heavy(),
    _lexer_edges(),
    _structural_mutation,
    _corrupt_inner(),
)