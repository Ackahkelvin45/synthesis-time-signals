from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic leaf strategies
# ---------------------------------------------------------------------------

# Control characters and NUL are allowed and encouraged (parser takes length).
_CONTROL_CHARS = [
    "\x00", "\x01", "\x02", "\x07", "\x08", "\x09", "\x0a",
    "\x0b", "\x0c", "\x0d", "\x1b", "\x1f",
]

# Escapes permitted by the grammar's ESC production.
_SIMPLE_ESCAPES = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

_HEX = "0123456789abcdefABCDEF"


def _unicode_escape():
    """Return a strategy producing \\uXXXX escapes, including lone surrogates."""
    return st.text(alphabet=_HEX, min_size=4, max_size=4).map(lambda h: "\\u" + h)


def _string_body_char():
    """A single char allowed inside a JSON string (escaped or safe or control)."""
    return st.one_of(
        # safe code points
        st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08'
            "\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17"
            "\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
        ),
        # escapes
        st.sampled_from(_SIMPLE_ESCAPES),
        _unicode_escape(),
        # raw control / NUL bytes (parser accepts them faithfully)
        st.sampled_from(_CONTROL_CHARS),
    )


def _string_body():
    return st.lists(_string_body_char(), min_size=0, max_size=12).map("".join)


# A well-formed quoted string.
string_value = _string_body().map(lambda b: '"' + b + '"')


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT_NO_ZERO = st.integers(min_value=1, max_value=10 ** 18).map(str)
_INT = st.one_of(st.just("0"), _INT_NO_ZERO)

_FRAC = st.tuples(st.just("."), st.integers(min_value=0, max_value=10 ** 12).map(str)) \
    .map(lambda t: t[0] + t[1])
_EXP = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10 ** 4).map(str),
).map(lambda t: t[0] + t[1] + t[2])

# Extreme magnitudes / exponents, including overflow like 1e309.
_EXTREME_NUM = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1e308"),
    st.just("-1e308"),
    st.just("1e999999"),
    st.just("0e0"),
    st.just("-0"),
    st.just("-"),
    st.tuples(
        st.sampled_from(["", "-"]),
        st.just("1"),
        st.just("e"),
        st.integers(min_value=300, max_value=400).map(str),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

number_value = st.one_of(
    _INT,
    st.tuples(st.sampled_from(["", "-"]), _INT).map(lambda t: t[0] + t[1]),
    st.tuples(st.sampled_from(["", "-"]), _INT, _FRAC).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.sampled_from(["", "-"]), _INT, _FRAC, _EXP).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    ),
    st.tuples(st.sampled_from(["", "-"]), _INT, _EXP).map(lambda t: t[0] + t[1] + t[2]),
    _EXTREME_NUM,
)


# ---------------------------------------------------------------------------
# Near-valid-but-malformed number forms (should be rejected, but good fuzz).
# ---------------------------------------------------------------------------

bad_number = st.one_of(
    st.just("+1"),
    st.just("+0"),
    st.just(".5"),
    st.just("-.5"),
    st.just("1."),
    st.just("-1."),
    st.just("01"),
    st.just("-01"),
    st.just("00"),
    st.just("0x1F"),
    st.just("1e"),
    st.just("1e+"),
    st.just("1e-"),
    st.just("1.2.3"),
    st.just("--1"),
    st.just("1-2"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just("NaN"),
    st.just("1_000"),
)


# ---------------------------------------------------------------------------
# Malformed string fragments
# ---------------------------------------------------------------------------

bad_string = st.one_of(
    st.just('"unterminated'),
    st.just('"esc\\'),
    st.just('"bad \\x escape"'),
    st.just('"\\u12"'),          # short unicode escape
    st.just('"\\uZZZZ"'),        # invalid hex
    st.just('"trailing\\'),      # unterminated after escape
    st.just('"'),                # lone quote
    st.just('"a"b"'),            # stray content
    st.just("'single quoted'"),  # single quotes rejected
)


# ---------------------------------------------------------------------------
# Recursive value/object/array construction
# ---------------------------------------------------------------------------

_WS = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

_key = string_value


def _pair(key, value):
    return st.tuples(
        key, _WS, st.just(":"), _WS, value
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])


def _obj_members(pair_strategy):
    """Produce the interior of an object (possibly empty, possibly trailing comma)."""
    base = st.lists(pair_strategy, min_size=0, max_size=6)
    return st.tuples(
        base,
        st.booleans(),  # whether to add a single trailing comma
    ).map(
        lambda t: (
            ",".join(t[0]) + ("," if (t[1] and t[0]) else "")
        )
    )


def _arr_members(value_strategy):
    base = st.lists(value_strategy, min_size=0, max_size=6)
    return st.tuples(
        base,
        st.booleans(),
    ).map(
        lambda t: ",".join(t[0]) + ("," if (t[1] and t[0]) else "")
    )


def _wrap_obj(inner):
    return st.tuples(_WS, st.just("{"), inner, st.just("}"), _WS).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )


def _wrap_arr(inner):
    return st.tuples(_WS, st.just("["), inner, st.just("]"), _WS).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )


# Malformed structural fragments to inject near the leaves.
_malformed_obj = st.one_of(
    st.just("{"),
    st.just("}"),
    st.just("{}"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{"a":1,}'),
    st.just('{"a":1,,}'),
    st.just('{,"a":1}'),
    st.just('{"a":1 "b":2}'),
    st.just('{"a":1,"a":2}'),          # duplicate keys
    st.just('{"a":1,"a":2,"a":3}'),
    st.just("{a:1}"),                   # bare key
    st.just("{'a':1}"),                 # single-quoted key
    st.just('{"a" 1}'),                 # missing colon
)

_malformed_arr = st.one_of(
    st.just("["),
    st.just("]"),
    st.just("[]"),
    st.just("[1,]"),
    st.just("[,]"),
    st.just("[,1]"),
    st.just("[1,,2]"),
    st.just("[1 2]"),
    st.just("[1;2]"),
    st.just("[[[["),
    st.just("]]]]"),
)


def _make_value(base_value):
    """Build the recursive value strategy."""
    return st.recursive(
        base_value,
        lambda children: st.one_of(
            _wrap_obj(_obj_members(_pair(_key, children))),
            _wrap_arr(_arr_members(children)),
        ),
        max_leaves=40,
    )


# ---------------------------------------------------------------------------
# Leaf values (non-recursive)
# ---------------------------------------------------------------------------

_leaf_literals = st.sampled_from(["true", "false", "null"])

_leaf = st.one_of(
    string_value,
    number_value,
    _leaf_literals,
)

# A value strategy that also injects malformed leaves.
_leaf_with_bad = st.one_of(
    _leaf,
    bad_string,
    bad_number,
    _malformed_obj,
    _malformed_arr,
)

value_strategy = _make_value(_leaf_with_bad)


# ---------------------------------------------------------------------------
# Deep nesting: bias toward objects with members (the stressed path).
# ---------------------------------------------------------------------------

def _deep_obj(depth):
    """Build a deeply nested object with a member at each level."""
    if depth <= 0:
        return st.one_of(string_value, number_value, _leaf_literals)
    inner = _deep_obj(depth - 1)
    pair = _pair(string_value, inner)
    return st.tuples(st.just('{"k":'), pair, st.just("}")).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _deep_arr(depth):
    if depth <= 0:
        return st.one_of(string_value, number_value, _leaf_literals)
    inner = _deep_arr(depth - 1)
    return st.tuples(st.just("["), inner, st.just("]")).map(
        lambda t: t[0] + t[1] + t[2]
    )


_deep_obj_strategy = st.integers(min_value=1, max_value=200).flatmap(_deep_obj)
_deep_arr_strategy = st.integers(min_value=1, max_value=200).flatmap(_deep_arr)


# ---------------------------------------------------------------------------
# Near-crash structural mutations around the crashing input
#   b'"bad \\x escape"'
# The crash signature is a ubsan null-pointer-offset in the parse function,
# so we generate many small structural variants around this string: changing
# the escape introducer, the trailing content, surrounding container context,
# truncations, and byte-level perturbations.
#
# INTENSIFIED: heavier weighting of near-crash mutations, multi-byte
# mutations, structured escape-payload permutations, container nesting,
# and byte-level perturbations that keep the parser on the crash path.
# ---------------------------------------------------------------------------

_CRASH_SEED = '"bad \\x escape"'

# Perturb the escape introducer / escape payload.
_escape_variants = st.sampled_from([
    '\\x', '\\X', '\\', '\\\\', '\\u', '\\U', '\\0', '\\1', '\\9',
    '\\a', '\\v', '\\e', '\\z', '\\ ', '\\\t', '\\\n', '\\\r', '\\/',
    '\\b', '\\f', '\\n', '\\r', '\\t', '\\"', "\\'",
])

# Surrounding prefix/suffix context to vary the parse path.
_prefix_variants = st.sampled_from([
    "", " ", "\t", "\n", "\r", "\x00", "[", "{", '{"a":', '["', "  ",
])

_suffix_variants = st.sampled_from([
    "", " ", "\t", "\n", "\r", "\x00", "]", "}", '"}', '"]', ",", ":",
    "\\", '"', "x", "0", "1",
])


def _near_crash_string():
    """Build strings structurally close to the crashing input."""
    # Byte-level mutations of the seed: substitute, insert, delete, duplicate.
    _seed_bytes = list(_CRASH_SEED)

    def _substitute_byte():
        return st.tuples(
            st.integers(min_value=0, max_value=len(_seed_bytes) - 1),
            st.sampled_from(list('\\xX"bad esca0\x00\x01\x1b')),
        ).map(lambda t: "".join(
            _seed_bytes[:t[0]] + [t[1]] + _seed_bytes[t[0] + 1:]
        ))

    def _insert_byte():
        return st.tuples(
            st.integers(min_value=0, max_value=len(_seed_bytes)),
            st.sampled_from(list('\\xX"{}[],: \x00\x01\x1b')),
        ).map(lambda t: "".join(
            _seed_bytes[:t[0]] + [t[1]] + _seed_bytes[t[0]:]
        ))

    def _delete_byte():
        return st.integers(min_value=0, max_value=len(_seed_bytes) - 1).map(
            lambda i: "".join(_seed_bytes[:i] + _seed_bytes[i + 1:])
        )

    def _duplicate_byte():
        return st.integers(min_value=0, max_value=len(_seed_bytes) - 1).map(
            lambda i: "".join(_seed_bytes[:i] + [_seed_bytes[i]] + _seed_bytes[i:])
        )

    _byte_mutations = st.one_of(
        _substitute_byte(),
        _insert_byte(),
        _delete_byte(),
        _duplicate_byte(),
    )

    # Stack multiple byte mutations to reach deeper structural variants.
    _multi_byte_mutations = st.one_of(
        st.lists(_byte_mutations, min_size=2, max_size=6).map(
            lambda xs: xs[0]
        ),
        st.lists(_byte_mutations, min_size=2, max_size=6).map(
            lambda xs: "".join(xs)
        ),
    )

    # Repetition of the escape introducer with varying counts.
    _escape_repeat = st.tuples(
        st.sampled_from(['\\x', '\\', '\\u', '\\X', '\\\\']),
        st.integers(min_value=1, max_value=12),
    ).map(lambda t: t[0] * t[1])

    # Structured escape payloads: introducer + payload bytes.
    _escape_payload = st.tuples(
        _escape_variants,
        st.lists(
            st.sampled_from(list('xX0123456789abcdefABCDEFuU{}[]",: \t\n\r\x00\x01\x1b')),
            min_size=0, max_size=10,
        ),
    ).map(lambda t: t[0] + "".join(t[1]))

    # The seed body with the escape region replaced by a payload.
    _payload_in_seed = st.tuples(
        st.just('"bad '), _escape_payload, st.just(" escape\"")
    ).map(lambda t: t[0] + t[1] + t[2])

    # Container wrappers around the seed.
    _open_wraps = st.lists(
        st.sampled_from(["[", "{", '{"k":', '["', '{"k":[']),
        min_size=1, max_size=5,
    )
    _close_wraps = st.lists(
        st.sampled_from(["]", "}", '"}', '"]', "]}" ]),
        min_size=1, max_size=5,
    )

    return st.one_of(
        # exact seed
        st.just(_CRASH_SEED),
        # seed with escape introducer swapped
        st.tuples(
            st.just('"bad '), _escape_variants, st.just(" escape\"")
        ).map(lambda t: t[0] + t[1] + t[2]),
        # seed with prefix/suffix context
        st.tuples(
            _prefix_variants, st.just(_CRASH_SEED), _suffix_variants
        ).map(lambda t: t[0] + t[1] + t[2]),
        # truncations of the seed (parser may read past end)
        st.sampled_from([
            _CRASH_SEED[:i] for i in range(len(_CRASH_SEED) + 1)
        ]),
        # seed with the closing quote removed / duplicated
        st.just('"bad \\x escape'),
        st.just('"bad \\x escape""'),
        st.just('"bad \\x escape"\\'),
        st.just('"bad \\x escape\\"'),
        # seed with embedded NUL / control bytes
        st.tuples(
            st.just('"bad '), _escape_variants,
            st.sampled_from(["\x00", "\x01", "\x1b", "\x7f"]),
            st.just(" escape\""),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        # seed wrapped in containers (exercises the obj/arr parse path)
        st.tuples(
            st.sampled_from(["[", "{" + '"k":', '{"k":[']),
            st.just(_CRASH_SEED),
            st.sampled_from(["]", "}", "]}" ]),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # repeated escape sequences near the crash
        st.lists(
            st.sampled_from(['\\x', '\\', '\\u', 'x', ' ']),
            min_size=1, max_size=8,
        ).map(lambda xs: '"' + "".join(xs) + ' escape"'),
        # byte-level mutations of the exact seed
        _byte_mutations,
        # stacked byte-level mutations
        _multi_byte_mutations,
        # repeated escape introducers embedded in the seed body
        st.tuples(
            st.just('"bad '), _escape_repeat, st.just(" escape\"")
        ).map(lambda t: t[0] + t[1] + t[2]),
        # structured escape payloads inside the seed body
        _payload_in_seed,
        # seed with prefix/suffix and byte mutation combined
        st.tuples(
            _prefix_variants, _byte_mutations, _suffix_variants
        ).map(lambda t: t[0] + t[1] + t[2]),
        # stacked mutations with prefix/suffix
        st.tuples(
            _prefix_variants, _multi_byte_mutations, _suffix_variants
        ).map(lambda t: t[0] + t[1] + t[2]),
        # truncations with appended context
        st.tuples(
            st.sampled_from([
                _CRASH_SEED[:i] for i in range(len(_CRASH_SEED) + 1)
            ]),
            _suffix_variants,
        ).map(lambda t: t[0] + t[1]),
        # seed nested inside multiple containers
        st.tuples(
            _open_wraps,
            st.just(_CRASH_SEED),
            _close_wraps,
        ).map(lambda t: "".join(t[0]) + t[1] + "".join(t[2])),
        # mutated seed nested inside multiple containers
        st.tuples(
            _open_wraps,
            _byte_mutations,
            _close_wraps,
        ).map(lambda t: "".join(t[0]) + t[1] + "".join(t[2])),
        # escape payload nested inside containers
        st.tuples(
            _open_wraps,
            _payload_in_seed,
            _close_wraps,
        ).map(lambda t: "".join(t[0]) + t[1] + "".join(t[2])),
        # repeated truncations concatenated (parser reads past end repeatedly)
        st.lists(
            st.sampled_from([
                _CRASH_SEED[:i] for i in range(len(_CRASH_SEED) + 1)
            ]),
            min_size=2, max_size=5,
        ).map(lambda xs: "".join(xs)),
        # seed with escape introducer repeated and containers
        st.tuples(
            _open_wraps,
            st.just('"bad '), _escape_repeat, st.just(" escape\""),
            _close_wraps,
        ).map(lambda t: "".join(t[0]) + t[1] + t[2] + t[3] + "".join(t[4])),
    )


_near_crash = _near_crash_string()


# ---------------------------------------------------------------------------
# Whole-document strategy
# ---------------------------------------------------------------------------

# Bias toward objects with members (the stressed first-pass path).
_document_core = st.one_of(
    # objects with members, weighted heavily
    st.lists(
        st.one_of(
            _wrap_obj(_obj_members(_pair(_key, value_strategy))),
            _wrap_obj(_obj_members(_pair(_key, _leaf))),
            _wrap_obj(_obj_members(_pair(_key, value_strategy))),
        ),
        min_size=1,
        max_size=3,
    ).map(lambda xs: xs[0]),
    # arrays
    _wrap_arr(_arr_members(value_strategy)),
    _wrap_arr(_arr_members(_leaf)),
    # bare values
    value_strategy,
    # deep nesting (objects biased)
    _deep_obj_strategy,
    _deep_arr_strategy,
    # empty containers
    st.just("{}"),
    st.just("[]"),
    st.just(""),
    # malformed whole documents
    _malformed_obj,
    _malformed_arr,
    bad_string,
    bad_number,
    # trailing content after a complete value (should be rejected)
    st.tuples(
        st.one_of(st.just("1"), st.just("[]"), st.just("true"), st.just('"x"')),
        st.sampled_from(["abc", " xyz", " false", "\x00", "garbage"]),
    ).map(lambda t: t[0] + t[1]),
    # comments (rejected with default settings)
    st.just("// comment\n1"),
    st.just("/* comment */ 1"),
    st.just("1 // trailing"),
    # NUL-heavy
    st.just("\x00"),
    st.just('{"a":\x00}'),
    st.just('["\x00"]'),
    # near-crash structural mutations (heavily weighted via duplication)
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
    _near_crash,
)


strategy = _document_core