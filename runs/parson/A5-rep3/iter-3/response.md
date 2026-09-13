```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# SAFECODEPOINT excludes ", \, and control chars 0x00-0x1F.
# We must NEVER emit a raw NUL byte, so we exclude 0x00 from the safe set.
_SAFE_CHARS = [
    chr(c)
    for c in range(0x20, 0x7F)
    if c not in (ord('"'), ord('\\'))
]
_SAFE_CHARS_EXTRA = [
    "\u00e9", "\u00ff", "\u0100", "\u20ac", "\u4e2d", "\U0001F600",
]

# Escapes that are legal inside JSON strings.
_SIMPLE_ESCAPES = ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']


def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)


def _unicode_escape():
    # \uXXXX, including surrogates and lone surrogates.
    return st.one_of(
        _hex4().map(lambda h: "\\u" + h),
        st.sampled_from(["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
                         "\\uD83D\\uDE00", "\\u0000", "\\u001f", "\\uFFFF"]),
    )


def _string_body():
    pieces = [
        st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=8),
        st.sampled_from(_SAFE_CHARS_EXTRA),
        st.sampled_from(_SIMPLE_ESCAPES),
        _unicode_escape(),
    ]
    return st.lists(st.one_of(pieces), min_size=0, max_size=6).map("".join)


def _json_string():
    return _string_body().map(lambda s: '"' + s + '"')


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=10, max_value=10 ** 18).map(str),
    st.sampled_from(["1", "9", "10", "12345678901234567890",
                     "99999999999999999999999999"]),
)

_EXP = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=400).map(str),
            st.just("308"),
            st.just("309"),
            st.just("310"),
            st.just("999"),
            st.just("000"),
        ),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_FRAC = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10 ** 12).map(lambda n: "." + str(n)),
    st.sampled_from([".0", ".5", ".000", ".999999"]),
)


def _number():
    return st.tuples(
        st.sampled_from(["", "-"]),
        _INT,
        _FRAC,
        _EXP,
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])


# ---------------------------------------------------------------------------
# Recursive value/obj/arr
# ---------------------------------------------------------------------------

# Depth budget: concentrate near but not far beyond the parser cap (2048).
# We use a modest recursion depth for generation and separately emit
# deep-nesting probes near the cap.

_LEAF = st.one_of(
    _json_string(),
    _number(),
    st.sampled_from(["true", "false", "null"]),
)


def _pair(key_strategy):
    return st.tuples(
        key_strategy,
        st.just(":"),
        st.deferred(lambda: _value_impl),
    ).map(lambda t: t[0] + t[1] + t[2])


_value_impl = None  # filled in below


def _obj(key_strategy, value_strategy):
    pairs = st.lists(_pair(key_strategy), min_size=0, max_size=4)
    return st.tuples(
        st.just("{"),
        pairs.map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + t[2])


def _arr(value_strategy):
    vals = st.lists(value_strategy, min_size=0, max_size=4)
    return st.tuples(
        st.just("["),
        vals.map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + t[2])


# Key strategy: sometimes deliberately duplicate-prone (small alphabet).
_KEY_NORMAL = _json_string()
_KEY_DUPY = st.sampled_from(['"k"', '"a"', '"key"', '"dup"', '""'])


_value_impl = st.recursive(
    _LEAF,
    lambda children: st.one_of(
        _obj(_KEY_NORMAL, children),
        _arr(children),
        _obj(_KEY_DUPY, children),
    ),
    max_leaves=12,
)


# ---------------------------------------------------------------------------
# Deep nesting near the parser cap (2048)
# ---------------------------------------------------------------------------

_DEPTH_CHOICES = st.sampled_from([
    1, 2, 3, 10, 100, 1000, 2000, 2040, 2047, 2048, 2049, 2050, 2100, 3000,
])


def _deep_nesting():
    return st.tuples(
        _DEPTH_CHOICES,
        st.sampled_from(["[", "{"]),
        st.sampled_from(["", "0", "1", '"x"', "null", "true"]),
    ).map(lambda t: _build_deep(t[0], t[1], t[2]))


def _build_deep(depth, opener, filler):
    if depth <= 0:
        return filler
    if opener == "[":
        return "[" * depth + filler + "]" * depth
    # For objects, nest {"k": ... } depth times.
    return '{"k":' * depth + filler + "}" * depth


# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from([
    # double commas
    "[1,,2]", "{,}", '{"a":1,,"b":2}', "[,]", "[1,2,,]",
    # missing colons
    '{"a" 1}', '{"a"}', '{"a":}', '{"a" "b"}',
    # trailing commas
    "[1,2,]", '{"a":1,}', "[,]", "{,}",
    # unterminated strings
    '"abc', '"', '{"a":"b', '["x', '"\\', '"\\u12',
    # bad numbers / leading +, leading zeros, lone dot
    "01", "+1", ".5", "1.", "-", "-.", "+", "0x1", "1e", "1e+", "1e-",
    "00", "-01", "1..2", "1.2.3", "0.", ".", "1e309", "-1e309",
    "1e999999", "1234567890123456789012345678901234567890",
    # bad literals
    "tru", "truee", "nul", "falsee", "True", "NULL", "None",
    # stray punctuation / structure
    "}", "]", "{{", "[[", "]", "}", "{]", "[}", "}{",
    '{"a":1}}', "[1]]", '{"a":[1,2}',
    # trailing content (parser accepts!)
    "1abc", "1 garbage", "[]xyz", "{}trailing", '"s"more', "nullx",
    # whitespace-only / empty
    "", " ", "\t", "\n", "   \n\t ",
    # escapes
    '"\\u0000"', '"\\uD800"', '"\\uDC00"', '"\\uD83D\\uDE00"',
    '"\\q"', '"\\x41"', '"\\u12"', '"\\uZZZZ"',
    # duplicate keys (parser rejects)
    '{"k":0,"k":1}', '{"a":1,"a":2,"a":3}',
    # non-finite (parser rejects)
    "1e309", "-1e309", "1e400", "1E999",
    # control chars embedded (not NUL)
    '"\x01"', '"\x1f"', '"a\x07b"',
    # BOM / weird
    "\ufeff{}", "\xef\xbb\xbf{}",
    # lone sign accepted as 0
    "-", "-.",
])


# ---------------------------------------------------------------------------
# Structured mutation of valid values (near-miss perturbations)
# ---------------------------------------------------------------------------

# Take a valid value and apply a single structural mutation, producing
# near-valid inputs that are more likely to reach deep parser states than
# the fixed malformed corpus.

_MUTATIONS = st.sampled_from([
    # delete a random-ish char position via slicing
    lambda s: s[:-1] if s else s,
    lambda s: s[1:] if s else s,
    # duplicate a delimiter
    lambda s: s.replace(",", ",,", 1),
    lambda s: s.replace(":", "::", 1),
    # trailing comma before a closing bracket
    lambda s: s.replace(",]", ",]", 1),
    # insert a stray closing brace
    lambda s: s + "}",
    lambda s: s + "]",
    # insert a stray opening brace
    lambda s: "{" + s,
    lambda s: "[" + s,
    # drop a closing bracket (truncate structure)
    lambda s: s.replace("]", "", 1),
    lambda s: s.replace("}", "", 1),
    # append junk
    lambda s: s + "x",
    lambda s: s + " ",
    # remove quotes around a key/value
    lambda s: s.replace('"', "", 1),
    # swap a digit for a letter
    lambda s: s.replace("1", "l", 1),
    # turn a valid number into a leading-zero number
    lambda s: s.replace("0", "00", 1),
])


def _mutated_value():
    return st.tuples(_value_impl, _MUTATIONS).map(lambda t: t[1](t[0]))


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

# Weighted mix: bias towards structurally valid values (which exercise the
# recursive descent paths) while still hitting deep-nesting and malformed
# probes. We use `st.one_of` with repeated entries to weight probabilities,
# and `st.recursive`-generated values are sampled more often than the
# degenerate malformed corpus.
_WEIGHTED = st.one_of(
    # Valid-ish recursive values (most common).
    _value_impl,
    _value_impl,
    _value_impl,
    # Deep nesting probes near the parser cap.
    _deep_nesting(),
    # Malformed / boundary corpus.
    _MALFORMED,
    # Raw JSON-scalar leaves, useful for quick top-level parsing checks.
    _LEAF,
    _LEAF,
    # Near-miss mutations of valid values.
    _mutated_value(),
    _mutated_value(),
)


def _ensure_no_raw_nul(s: str) -> str:
    # Safety: never emit a raw NUL byte.
    if "\x00" in s:
        return s.replace("\x00", "\\u0000")
    return s


strategy = _WEIGHTED.map(_ensure_no_raw_nul)
```