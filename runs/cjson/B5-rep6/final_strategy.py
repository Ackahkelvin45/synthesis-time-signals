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
    # Broken / partial escape sequences that exercise error paths
    broken_esc = st.sampled_from([
        "\\", "\\\\\\", "\\u", "\\u1", "\\u12", "\\u123", "\\uZZZZ",
        "\\x41", "\\U0001F600", "\\'", "\\q", "\\0",
    ])
    return st.one_of(simple, unicode_esc, surrogate_esc, broken_esc)

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
    # Concentrate interesting depths near the limit, and mix array/object
    # nesting plus whitespace and trailing garbage to exercise the parser's
    # depth handling at boundaries.
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
        # mixed nesting (alternating array/object) near the limit
        st.integers(min_value=990, max_value=1010).map(
            lambda d: "".join(
                ("[" if i % 2 == 0 else '{"a":') for i in range(d)
            )
            + "0"
            + "".join(
                ("]" if i % 2 == 0 else "}") for i in reversed(range(d))
            )
        ),
        # depth with surrounding whitespace / trailing junk
        st.tuples(
            st.integers(min_value=995, max_value=1005),
            st.sampled_from(["", " ", "\n", "\x00", "x"]),
        ).map(lambda t: "[" * t[0] + "0" + "]" * t[0] + t[1]),
    )

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
    # trailing junk after a valid value is a common parser edge case
    st.text(alphabet=" \t\n\r{}[],:\"0123456789abcx\\", max_size=4),
)

_leading = st.one_of(
    st.just(""),
    st.text(alphabet=" \t\n\r", max_size=3),
)

_valid = st.tuples(_leading, _bom, _base, _trailing).map("".join)

_malformed_top = st.tuples(_bom, _malformed()).map("".join)

# Structured mutation of valid values to produce near-valid broken inputs
# (truncation, single-char corruption, duplicate/inserted delimiters).
_corrupt_chars = st.sampled_from(list('{}[],:"\\ \t\n\r0123456789abcx'))

def _mutate(s):
    n = len(s)
    if n == 0:
        return st.just(s)
    trunc = st.integers(min_value=0, max_value=n).map(lambda i: s[:i])
    replace = st.tuples(
        st.integers(min_value=0, max_value=n - 1),
        _corrupt_chars,
    ).map(lambda t: s[:t[0]] + t[1] + s[t[0] + 1:])
    insert = st.tuples(
        st.integers(min_value=0, max_value=n),
        _corrupt_chars,
    ).map(lambda t: s[:t[0]] + t[1] + s[t[0]:])
    delete = st.integers(min_value=0, max_value=n - 1).map(
        lambda i: s[:i] + s[i + 1:]
    )
    return st.one_of(trunc, replace, insert, delete)

_mutated = _valid.flatmap(_mutate)

# Apply two independent mutations to valid values to reach deeper parser
# error paths (e.g. truncated escapes inside corrupted structure).
_double_mutated = _mutated.flatmap(_mutate)

# A byte-oriented fuzzer for the raw input layer: arbitrary bytes decoded
# with surrogateescape so the parser sees exactly what was generated,
# covering non-UTF-8 input, embedded NULs, and invalid/overlong sequences.
_raw_bytes = st.binary(max_size=64).map(
    lambda b: b.decode("utf-8", "surrogateescape")
)

# Valid JSON re-serialized with varied separators to stress whitespace
# handling and compact/pretty layouts.
_reserialized = _base.map(
    lambda s: json.dumps(s, ensure_ascii=False, separators=(",", ":"))
)

strategy = st.one_of(
    _valid,
    _malformed_top,
    _deep_values(),
    _mutated,
    _double_mutated,
    _raw_bytes,
    _reserialized,
)