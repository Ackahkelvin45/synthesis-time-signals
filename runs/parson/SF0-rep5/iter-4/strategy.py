from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Scalars ---------------------------------------------------------------

_safe_codepoints = st.characters(
    blacklist_categories=("Cs",),  # no lone surrogates
    blacklist_characters="\x00\"\\",  # no raw NUL, no quote, no backslash
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_escapes = st.one_of(
    st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    # surrogate escapes (legal in the grammar's ESC/UNICODE production)
    st.sampled_from(
        [
            "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
            "\\uD83D\\uDE00",  # valid surrogate pair
            "\\uD800\\uD800",  # unpaired high
            "\\uDC00",         # lone low
        ]
    ),
    # embedded NUL / control bytes via escape (raw NUL is forbidden)
    st.sampled_from(["\\u0000", "\\u001F", "\\u0007", "\\u001b"]),
)

_string_body = st.one_of(
    _safe_codepoints,
    _escapes,
    st.text(alphabet="abcXYZ019 _-.,:;{}[]", min_size=0, max_size=6),
)

_json_string = st.lists(_string_body, min_size=0, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Numbers ---------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.integers(1, 9).map(str), st.text(alphabet="0123456789", min_size=0, max_size=18)).map(
        lambda t: t[0] + t[1]
    ),
)

_frac_part = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=18)).map(
    lambda t: t[0] + t[1]
)

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=5),
).map(lambda t: t[0] + t[1] + t[2])

_extreme_magnitudes = st.sampled_from(
    [
        "1e309", "-1e309", "1e-309", "1e308", "1e999999",
        "2.2250738585072014e-308", "1.7976931348623157e308",
        "1.7976931348623159e308", "-1e400", "9" * 30,
        "0." + "0" * 20 + "1",
        "1e" + "0" * 30,
    ]
)

_number = st.one_of(
    _extreme_magnitudes,
    st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac_part),
        st.one_of(st.just(""), _exp_part),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

# Malformed numbers (lenient-accept / near-valid) -----------------------

_malformed_number = st.sampled_from(
    [
        "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "00", "007",
        "1e", "1e+", "1e-", "0x1", "1_000", "--1", "1..2", "1.2.3",
        "1e309abc",
    ]
)

# ---------------------------------------------------------------------------
# Recursive value structure
# ---------------------------------------------------------------------------

_leaf = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
)

_value = st.deferred(lambda: _value_strategy)


def _join_obj(pairs):
    return "{" + ",".join(pairs) + "}"


def _join_arr(items):
    return "[" + ",".join(items) + "]"


_obj_strategy = st.one_of(
    st.just("{}"),
    st.lists(
        st.tuples(_json_string, st.just(":"), _value).map(lambda t: t[0] + t[1] + t[2]),
        min_size=1,
        max_size=6,
    ).map(_join_obj),
)

_arr_strategy = st.one_of(
    st.just("[]"),
    st.lists(_value, min_size=1, max_size=6).map(_join_arr),
)

_value_strategy = st.one_of(_leaf, _obj_strategy, _arr_strategy)

# ---------------------------------------------------------------------------
# Duplicate keys (expect rejection by the parser)
# ---------------------------------------------------------------------------

_dup_key_obj = st.tuples(
    _json_string,
    _value,
    _value,
).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}")

_dup_key_obj3 = st.tuples(
    _json_string,
    _value,
).map(lambda t: "{" + t[0] + ":0," + t[0] + ":1," + t[0] + ":" + t[1] + "}")

# ---------------------------------------------------------------------------
# Deep nesting near the 2048 cap
# ---------------------------------------------------------------------------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth


_near_cap_depth = st.one_of(
    st.integers(min_value=1, max_value=16),
    st.integers(min_value=2000, max_value=2055),
    st.integers(min_value=1024, max_value=1030),
    st.sampled_from([2047, 2048, 2049, 2050]),
)

_deep_array = st.tuples(_near_cap_depth, _leaf).map(
    lambda t: _deep(t[0], "[", "]", t[1])
)

# Correct deep object: {"k":{"k":{... value ...}}}
_deep_object = st.tuples(_near_cap_depth, _json_string, _leaf).map(
    lambda t: '{"k":' * t[0] + t[2] + "}" * t[0]
)

_deep_mixed = st.tuples(_near_cap_depth, _leaf).map(
    lambda t: "[{" * t[0] + t[1] + "}]" * t[0]
)

_deep_unterminated = st.tuples(_near_cap_depth).map(
    lambda t: "[" * t[0]
)

# ---------------------------------------------------------------------------
# Near-valid-but-malformed inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        # double commas / trailing commas
        "[1,,2]", "[1,2,]", "[,]", "[,1]", '{"a":1,,"b":2}', '{"a":1,}',
        '{"a":1,"b":2,}', "{,}", "{,}",
        # missing colons
        '{"a" 1}', '{"a"}', '{"a":}', '{:1}', '{"a":1 "b":2}',
        # unterminated strings
        '"abc', '{"a":"unterminated}', '["x', '"', '"\\', '"\\u12',
        # trailing content after a complete value (parser ACCEPTS)
        "1abc", "1 garbage", "[]xyz", "{}tail", "truefalse", "nullnull",
        "42 43", '{"a":1}{"b":2}', "[1] [2]",
        # leading +, lone ., leading zeros
        "+1", ".5", "1.", "01", "00", "-", "-.", "-.5",
        # stray tokens
        "]", "}", ",", ":", "tru", "nul", "falsey", "TRUE", "Null",
        # bad escapes
        '"\\x41"', '"\\uZZZZ"', '"\\u12"', '"\\"',
        # whitespace-only / empty
        "", " ", "\n", "\t\r ",
        # control char inside string (raw control, not NUL)
        '"\x01"', '"\x1f"',
        # nesting-ish malformed
        "[[[", "{{{", "[]]", "[}", "{]",
    ]
)

# ---------------------------------------------------------------------------
# Whitespace-padded valid values
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \t\n\r "])

_padded = st.tuples(_ws, _value, _ws).map(lambda t: t[0] + t[1] + t[2])

_padded_trailing = st.tuples(_value, st.text(alphabet="abcXYZ 0123[]{}", min_size=1, max_size=8)).map(
    lambda t: t[0] + t[1]
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

# A small set of structurally interesting but boundary-focused top-level
# generators that bias toward realistic document shapes (deeply nested
# objects/arrays with a variety of leaf values) to better exercise the
# recursive descent parser near its limits, while still keeping the
# malformed/degenerate cases.
_document = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=8).map(_join_arr),
        st.lists(
            st.tuples(_json_string, st.just(":"), children).map(
                lambda t: t[0] + t[1] + t[2]
            ),
            min_size=0,
            max_size=8,
        ).map(_join_obj),
    ),
    max_leaves=40,
)

# Interleaved whitespace between structural tokens: exercises the parser's
# whitespace-skipping in positions other than the outer edges (after
# commas, colons, brackets, and before closing tokens).
_ws_choice = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \t\n\r "])


# Build a generator that inserts random whitespace around structural
# punctuation in a JSON document.
def _jitter_doc(doc):
    out = []
    for ch in doc:
        if ch in "{}[],:":
            out.append(" ")
            out.append(ch)
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


_jittered = _document.map(_jitter_doc)

# Unterminated / truncated variants of otherwise-valid documents: take a
# document and chop off a random suffix length.  This targets the parser's
# error paths for truncated input (EOF mid-value).
def _truncate(doc, n):
    if n <= 0:
        return doc
    return doc[: max(0, len(doc) - n)]


_truncated = st.tuples(_document, st.integers(min_value=1, max_value=8)).map(
    lambda t: _truncate(t[0], t[1])
)

# Documents with a stray trailing byte appended (parser may accept or reject
# depending on trailing-content policy).
_trailing_byte = st.tuples(
    _document,
    st.sampled_from(["x", "0", "]", "}", ",", ":", '"', " ", "\n", "\x01"]),
).map(lambda t: t[0] + t[1])

# Documents with a leading stray byte prepended.
_leading_byte = st.tuples(
    st.sampled_from(["x", "0", "]", "}", ",", ":", '"', " ", "\n"]),
    _document,
).map(lambda t: t[0] + t[1])

# BOM prefix (some parsers reject, some accept).
_bom_prefixed = _document.map(lambda d: "\ufeff" + d)

# ---------------------------------------------------------------------------
# IMPROVEMENT: structured whitespace jitter that inserts *random* whitespace
# at structural boundaries (rather than a fixed single space), plus random
# whitespace *inside* strings is avoided.  This more thoroughly exercises the
# parser's tokenizer/skipper without changing the grammar of the document.
# ---------------------------------------------------------------------------

_ws_frag = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \t", "\n\r ", " \t\n\r "])

def _ws_jitter_doc(doc):
    # Split the document into a token stream we can re-emit with random
    # whitespace around structural punctuation.  We keep string contents
    # intact by tracking whether we are inside a string.
    out = []
    in_str = False
    esc = False
    pending_ws = None
    for ch in doc:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            if pending_ws is not None:
                out.append(pending_ws)
                pending_ws = None
            out.append(ch)
            in_str = True
            continue
        if ch in "{}[],:":
            if pending_ws is not None:
                out.append(pending_ws)
                pending_ws = None
            out.append(ch)
            pending_ws = _ws_frag.example() if False else None
            # We cannot call .example() here; instead emit a placeholder and
            # let Hypothesis fill it via a mapped strategy.  Use a sentinel.
            out.append("\x00WS\x00")
        else:
            out.append(ch)
    return "".join(out)


# Since we cannot sample inside a pure map, do the jitter with a strategy
# that pairs the document with a list of whitespace fragments (one per
# structural char) and substitutes them in.
def _count_structural(doc):
    n = 0
    in_str = False
    esc = False
    for ch in doc:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{}[],:":
            n += 1
    return n


def _apply_ws(doc, frags):
    out = []
    in_str = False
    esc = False
    i = 0
    for ch in doc:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            out.append(ch)
            in_str = True
            continue
        if ch in "{}[],:":
            if i < len(frags):
                out.append(frags[i])
                i += 1
            out.append(ch)
            if i < len(frags):
                out.append(frags[i])
                i += 1
        else:
            out.append(ch)
    return "".join(out)


def _ws_jittered(doc):
    n = _count_structural(doc)
    return st.tuples(
        st.just(doc),
        st.lists(_ws_frag, min_size=2 * n, max_size=2 * n),
    ).map(lambda t: _apply_ws(t[0], t[1]))


_ws_jittered_docs = _document.flatmap(_ws_jittered)

# ---------------------------------------------------------------------------
# IMPROVEMENT: "splice" mutation - take a valid document and inject a random
# structural token at a random position.  This produces many near-valid
# inputs that stress single-token error recovery paths.
# ---------------------------------------------------------------------------

_inject_tokens = st.sampled_from(
    ["{", "}", "[", "]", ",", ":", '"', "\\", "0", "-", "e", " ", "\n", "null", "true"]
)

def _splice(doc, pos, tok):
    pos = max(0, min(len(doc), pos))
    return doc[:pos] + tok + doc[pos:]


_spliced = st.tuples(
    _document,
    st.integers(min_value=0, max_value=64),
    _inject_tokens,
).map(lambda t: _splice(t[0], t[1], t[2]))

# ---------------------------------------------------------------------------
# IMPROVEMENT: byte-level mutation of a valid document - flip one character
# to another (from a JSON-relevant alphabet).  Catches off-by-one tokenizer
# bugs and error-recovery bugs.
# ---------------------------------------------------------------------------

_flip_alphabet = "{}[],:\"\\0123456789eE+-.truefalsn \t\n\r"


def _flip(doc, pos, ch):
    if not doc:
        return ch
    pos = pos % len(doc)
    return doc[:pos] + ch + doc[pos + 1:]


_flipped = st.tuples(
    _document,
    st.integers(min_value=0, max_value=256),
    st.sampled_from(list(_flip_alphabet)),
).map(lambda t: _flip(t[0], t[1], t[2]))

# ---------------------------------------------------------------------------
# IMPROVEMENT: empty / degenerate-but-valid documents with surrounding
# whitespace of arbitrary length, to stress the tokenizer at EOF.
# ---------------------------------------------------------------------------

_long_ws = st.text(alphabet=" \t\n\r", min_size=0, max_size=64)
_ws_only = _long_ws
_wrapped = st.tuples(_long_ws, _value, _long_ws).map(lambda t: t[0] + t[1] + t[2])

# ---------------------------------------------------------------------------
# IMPROVEMENT: string-focused fuzzing - strings with random escape sequences
# and raw bytes (excluding NUL, quote, backslash) to stress the string
# scanner and unicode-escape decoder.
# ---------------------------------------------------------------------------

_str_escape_heavy = st.lists(
    st.one_of(
        _safe_codepoints,
        st.sampled_from(
            [
                "\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
                "\\u0000", "\\uD800", "\\uDFFF", "\\uD83D\\uDE00",
                "\\uFFFF", "\\uFFFE", "\\uD800\\uD800", "\\uDC00\\uD800",
            ]
        ),
    ),
    min_size=0,
    max_size=20,
).map(lambda parts: '"' + "".join(parts) + '"')

# ---------------------------------------------------------------------------
# IMPROVEMENT: deep nesting variants that exceed the cap by a lot, and
# alternating bracket types, to ensure the depth counter is robust.
# ---------------------------------------------------------------------------

_deep_over_cap = st.sampled_from(
    [
        "[" * 2050 + "]" * 2050,
        "[" * 4096 + "]" * 4096,
        "[" * 10000 + "]" * 10000,
        "[" * 2048,
        "[" * 2049,
        '{"a":' * 2050 + "null" + "}" * 2050,
        '{"a":' * 2049 + "null" + "}" * 2049,
        "[{" * 1025 + "null" + "}]" * 1025,
        "[" * 2048 + "1" + "]" * 2048,
        "[" * 2048 + "1" + "]" * 2047,
    ]
)

# ---------------------------------------------------------------------------
# IMPROVEMENT: "balanced-but-wrong" documents - correct bracket counts but
# wrong ordering, to stress the parser's structural error detection.
# ---------------------------------------------------------------------------

_balanced_wrong = st.sampled_from(
    [
        "{[}]", "[{]}", "{[}]}", "{[}]", "[]{}", "{[]}", "[[[[]]]]",
        '{"a":[}]}', '[{"a":1]', '{"a":[1}]', '{"a":[1]}',
        '{"a":1,"b":2,"a":3}',  # duplicate key
        '{"a":{"a":{"a":1}}}',  # nested duplicate-ish
        "[1,2,3,4,5,6,7,8,9,0]",
        '{"":1}',  # empty key
        '{"a":1,"":2}',
    ]
)

# ---------------------------------------------------------------------------
# IMPROVEMENT: JSON-encoded strings via json.dumps to get guaranteed-valid
# JSON string literals (including unicode escapes) as a sanity baseline.
# ---------------------------------------------------------------------------

_python_str = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=20,
)
_json_dumped = _python_str.map(json.dumps)

strategy = st.one_of(
    _value,
    _document,
    _padded,
    _padded_trailing,
    _dup_key_obj,
    _dup_key_obj3,
    _deep_array,
    _deep_object,
    _deep_mixed,
    _deep_unterminated,
    _malformed,
    _malformed_number,
    _jittered,
    _truncated,
    _trailing_byte,
    _leading_byte,
    _bom_prefixed,
    _ws_jittered_docs,
    _spliced,
    _flipped,
    _ws_only,
    _wrapped,
    _str_escape_heavy,
    _deep_over_cap,
    _balanced_wrong,
    _json_dumped,
    st.sampled_from(
        [
            "{}", "[]", "null", "true", "false", "0", "-0", "0.0", "1e0",
            '"\\u0000"', '"\\uD800"', '"\\uDFFF"', '"\\uD83D\\uDE00"',
        ]
    ),
)