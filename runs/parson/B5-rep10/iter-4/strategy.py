from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that are legal raw inside a JSON string (SAFECODEPOINT):
# anything except " \ and control chars 0x00-0x1F.  We must never emit a raw
# NUL, so the control range is excluded entirely.
_safe_char = st.characters(
    blacklist_categories=("Cs",),  # surrogates can't be encoded raw
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

# Escape sequences that are valid inside a JSON string.
_simple_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_unicode_esc = _hex4().map(lambda h: "\\u" + h)

# Surrogate escapes (high/low surrogates, and mismatched ones).
_surrogate_esc = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD834\\uDD1E",   # valid surrogate pair (G clef)
    "\\uD800\\uD800",   # two highs
    "\\uDC00\\uDC00",   # two lows
    "\\uD800",          # lone high
    "\\uDC00",          # lone low
])

_esc = st.one_of(_simple_esc, _unicode_esc, _surrogate_esc)

# A string body piece: either a safe char or an escape.
_str_piece = st.one_of(_safe_char, _esc)

# A valid JSON string literal (well-formed), with variable length.
_string_literal = st.lists(_str_piece, min_size=0, max_size=8).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_lead = st.builds(
    lambda d, rest: d + rest,
    st.sampled_from("123456789"),
    st.text("0123456789", min_size=0, max_size=6),
)
_int_part = st.one_of(st.just("0"), _nonzero_lead, _int_digits)

_frac = st.tuples(st.just("."), st.text("0123456789", min_size=1, max_size=6)).map(
    lambda t: t[0] + t[1]
)
_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text("0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

# Extreme magnitudes / exponents, including overflow (1e309).
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "1E400", "1e-400", "-1e-400",
    "1.7976931348623157e308", "1.7976931348623159e308",
    "4.9e-324", "2.2250738585072014e-308",
    "0e0", "-0", "-0.0", "0.0", "1" + "0" * 400,
    "123456789012345678901234567890",
    "1e999999999", "1e-999999999",
])

_valid_number = st.one_of(
    st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac),
        st.one_of(st.just(""), _exp),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    _extreme_number,
)

# Lenient / malformed numeric forms the parser may accept or reject.
_malformed_number = st.sampled_from([
    "-", "-.", "+1", "+0.5", ".5", "-.5", "1.", "01", "00", "-01",
    "1e", "1e+", "1e-", "1.2.3", "--1", "0x10", "1_000", "Infinity",
    "NaN", "-Infinity", "1e309x",
])

_number = st.one_of(_valid_number, _malformed_number)

# ---------------------------------------------------------------------------
# Malformed string fragments (unterminated, stray escapes, raw controls)
# ---------------------------------------------------------------------------

_malformed_string = st.sampled_from([
    '"',                    # unterminated
    '"abc',                 # unterminated
    '"abc\\',               # unterminated trailing backslash
    '"abc\\"',              # escaped quote then unterminated
    '"\\u12"',              # short unicode escape
    '"\\uZZZZ"',            # bad hex
    '"\\x41"',              # invalid escape
    '"a\nb"',               # raw newline inside string
    '"a\tb"',               # raw tab inside string
    '"a\x01b"',             # raw control byte
    '"\x7f"',               # DEL
    '"\\u0000"',            # escaped NUL (legal text)
    '"ok"',                 # valid but here for mixing
])

# ---------------------------------------------------------------------------
# Recursive value / object / array generation
# ---------------------------------------------------------------------------
# We build with st.recursive.  The "leaf" strings are JSON scalars; the
# recursive branch produces objects and arrays.  Depth is controlled by the
# recursive strategy's expansion, and we additionally craft explicit
# near-limit deep structures.

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n "])

def _join(parts):
    return "".join(parts)

# A JSON key: a string literal (valid) or occasionally a malformed one.
_key = st.one_of(_string_literal, _malformed_string)

# Leaf scalar values as text.
_scalar_text = st.one_of(
    _string_literal,
    _number,
    st.sampled_from(["true", "false", "null"]),
    _malformed_string,
)

# We need a recursive strategy producing *text*.  Use st.recursive with a
# base of scalars and an extend function that builds obj/arr strings.
def _extend(children):
    # children: strategy producing JSON text for sub-values.
    child = children

    # A pair: key ':' value
    pair = st.tuples(_key, _ws, st.just(":"), _ws, child).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

    # Object: '{' pair (',' pair)* '}' or '{}'
    obj = st.one_of(
        st.just("{}"),
        st.just("{ }"),
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        # duplicate keys (parser rejects, but exercise it)
        st.tuples(_string_literal, child).map(
            lambda t: '{"k":' + t[1] + ',"k":' + t[1] + "}"
        ),
        # trailing comma / missing colon malformed objects
        st.tuples(_string_literal, child).map(
            lambda t: "{" + t[0] + ":" + t[1] + ",}"
        ),
        st.tuples(_string_literal, child).map(
            lambda t: "{" + t[0] + " " + t[1] + "}"
        ),
    )

    # Array: '[' value (',' value)* ']' or '[]'
    arr = st.one_of(
        st.just("[]"),
        st.just("[ ]"),
        st.lists(child, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(child, min_size=1, max_size=3).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
        st.lists(child, min_size=2, max_size=3).map(
            lambda vs: "[" + ",,".join(vs) + "]"
        ),
    )

    return st.one_of(obj, arr)

_recursive_value = st.recursive(
    _scalar_text,
    _extend,
    max_leaves=12,
)

# ---------------------------------------------------------------------------
# Deep nesting near the 2048 limit
# ---------------------------------------------------------------------------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

_deep_nesting = st.one_of(
    # near-limit arrays
    st.integers(min_value=2000, max_value=2050).map(
        lambda d: _deep(d, "[", "]", "1")
    ),
    # near-limit objects
    st.integers(min_value=2000, max_value=2050).map(
        lambda d: _deep(d, '{"a":', "}", "1")
    ),
    # just over the limit (expect clean rejection)
    st.integers(min_value=2049, max_value=2100).map(
        lambda d: _deep(d, "[", "]", "0")
    ),
    # mixed nesting near limit
    st.integers(min_value=1000, max_value=1025).map(
        lambda d: _deep(d, '[{"a":', "}]", "1")
    ),
    # deep empty arrays
    st.integers(min_value=2040, max_value=2050).map(
        lambda d: "[" * d + "]" * d
    ),
)

# ---------------------------------------------------------------------------
# Trailing content / lenient forms
# ---------------------------------------------------------------------------

_trailing = st.one_of(
    _recursive_value,
    st.tuples(_recursive_value, st.sampled_from(["x", " garbage", " []xyz",
                                                 "1abc", "null", "{", "]"]))
    .map(lambda t: t[0] + t[1]),
)

_lenient_number = st.sampled_from(["-", "-.", "+", ".5", "1.", "01", "00"])

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

_wellformed_or_edge = st.one_of(
    _recursive_value,
    _deep_nesting,
    _trailing,
    _lenient_number,
    _malformed_string,
    _malformed_number,
    st.just(""),
    st.just(" "),
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
)

# Bias generation toward structurally interesting whole documents: wrap
# arbitrary value text in surrounding whitespace, and combine two independent
# values with a separator to probe stream/concatenation handling.
_wrapped = st.tuples(_ws, _wellformed_or_edge, _ws).map(
    lambda t: t[0] + t[1] + t[2]
)

_concatenated = st.tuples(
    _recursive_value,
    st.sampled_from(["", " ", "\n", "\x00", ",", ":", "]", "}"]),
    _recursive_value,
).map(lambda t: t[0] + t[1] + t[2])

# ---------------------------------------------------------------------------
# Fuzz amplifier: derive additional inputs from a generated document by
# truncating it at random byte offsets and by injecting stray bytes.  This
# exercises the parser's error paths (unexpected EOF, partial tokens) far
# more densely than hand-written malformations alone.
# ---------------------------------------------------------------------------

_base_doc = st.one_of(_wellformed_or_edge, _wrapped, _concatenated)

_amplified = st.tuples(
    _base_doc,
    st.integers(min_value=0, max_value=1000),
    st.sampled_from(["truncate", "inject", "dup", "none"]),
    st.sampled_from(["", " ", "\x00", "\xff", "\\", '"', "{", "}", "[", "]",
                     ",", ":", "e", "-", ".", "u", "0"]),
).map(
    lambda t: (
        t[0]
        if t[2] == "none"
        else (
            t[0][: t[1] % (len(t[0]) + 1)]
            if t[2] == "truncate"
            else (
                t[0][: t[1] % (len(t[0]) + 1)]
                + t[3]
                + t[0][t[1] % (len(t[0]) + 1):]
                if t[2] == "inject"
                else t[0] + t[0]
            )
        )
    )
)

strategy = st.one_of(_base_doc, _amplified)