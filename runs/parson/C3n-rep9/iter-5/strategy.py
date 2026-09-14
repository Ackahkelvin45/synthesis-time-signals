from hypothesis import strategies as st
import json

# ---------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------

# Characters safe to embed raw in a JSON string (no ", \, or control chars).
_SAFE_CHARS = [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)]
# A few interesting non-ASCII code points (encode as \uXXXX escapes).
_UNICODE_ESCAPE_CODEPOINTS = [
    0x0000, 0x0001, 0x001F, 0x0020, 0x007F, 0x0080, 0x00FF, 0x07FF,
    0x0800, 0xFFFD, 0xFFFF, 0xD800, 0xDBFF, 0xDC00, 0xDFFF, 0xE000,
]

_SIMPLE_ESCAPES = ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']


@st.composite
def _unicode_escape(draw):
    cp = draw(st.sampled_from(_UNICODE_ESCAPE_CODEPOINTS))
    return "\\u%04x" % cp


@st.composite
def _string_fragment(draw):
    """A single piece of string content: raw char or escape sequence."""
    return draw(st.one_of(
        st.sampled_from(_SAFE_CHARS),
        st.sampled_from(_SIMPLE_ESCAPES),
        _unicode_escape(),
    ))


@st.composite
def json_string(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    body = "".join(draw(_string_fragment()) for _ in range(n))
    return '"' + body + '"'


# ---------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------

_INT_DIGITS = st.text(alphabet="0123456789", min_size=1, max_size=6)

_EXTREME_LITERALS = [
    "0", "-0", "1", "-1", "0.0", "-0.0",
    "1e0", "1E0", "1e+0", "1e-0",
    "1e308", "-1e308", "1e309", "-1e309",  # overflow to inf -> rejected
    "1e-308", "1e-309", "1e-400", "1e400",
    "1.7976931348623157e308",
    "2.2250738585072014e-308",
    "5e-324", "1e-324",
    "123456789012345678901234567890",
    "0.0000000000000000000000001",
    "1" + "0" * 20,
    "1e" + "9" * 10,
    "1e-" + "9" * 10,
]


@st.composite
def json_number(draw):
    return draw(st.one_of(
        st.sampled_from(_EXTREME_LITERALS),
        st.builds(lambda d: d, _INT_DIGITS),
        st.builds(
            lambda a, b: a + "." + b,
            st.sampled_from(["0", "-0", "1", "-1", "12", "-12"]),
            st.text(alphabet="0123456789", min_size=1, max_size=6),
        ),
        st.builds(
            lambda i, e, s, d: i + e + s + d,
            _INT_DIGITS,
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.text(alphabet="0123456789", min_size=1, max_size=4),
        ),
    ))


# ---------------------------------------------------------------
# Malformed near-JSON fragments (to exercise reject paths)
# ---------------------------------------------------------------

_MALFORMED_FRAGMENTS = [
    # leading + / lone .5 / leading zeros
    "+1", "+1.5", ".5", "-.5", "1.", "01", "00", "-01", "-00", "0.5.5",
    # lone signs
    "-", "-.", "+", ".", "e5", "1e", "1e+", "1e-",
    # stray punctuation
    ",", ":", "{}", "[]", "tru", "fals", "nul", "True", "FALSE", "NULL",
    # unterminated strings
    '"', '"abc', '"abc\\', '"\\u12', '"\\uZZZZ"',
    # double commas / missing colons
    "[1,,2]", '{"a" 1}', '{"a":1,}', "[,1]", "[1,]", "{,}", '{:}',
    '{"a":}', '{"a":1,,"b":2}', '[1 2]', '{1:2}', '{"a"::1}',
    # unbalanced
    "[", "]", "{", "}", "[1,2", '{"a":1', "[[[]]", "{{}}",
    # trailing content after a complete value (accepted by target)
    "1abc", "1 garbage", "[]xyz", "{}trailing", "truefalse", "nullnull",
    # whitespace-only
    " ", "\t", "\n", "\r\n", "   ",
]


@st.composite
def _malformed(draw):
    return draw(st.sampled_from(_MALFORMED_FRAGMENTS))


# ---------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------

# Depth budget: concentrate near the parser limit (~2048).
# We use a modest structural depth for the recursive strategy, and
# separately emit explicit deep-nesting strings near the cap.
_STRUCTURAL_DEPTH = 8


@st.composite
def _pair(draw, value_strategy, key):
    return key + ":" + draw(value_strategy)


@st.composite
def _obj(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{}"
    keys = draw(st.lists(json_string(), min_size=n, max_size=n))
    # Occasionally force a duplicate key (target rejects these).
    if draw(st.booleans()):
        keys = keys + [keys[0]]
    pairs = [k + ":" + draw(value_strategy) for k in keys]
    return "{" + ",".join(pairs) + "}"


@st.composite
def _arr(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "[]"
    items = [draw(value_strategy) for _ in range(n)]
    return "[" + ",".join(items) + "]"


@st.composite
def _value(draw):
    return draw(st.one_of(
        json_string(),
        json_number(),
        st.sampled_from(["true", "false", "null"]),
    ))


def _make_value_strategy():
    return st.recursive(
        st.one_of(
            json_string(),
            json_number(),
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda children: st.one_of(
            _obj(children),
            _arr(children),
        ),
        max_leaves=20,
    )


_value_strategy = _make_value_strategy()


# ---------------------------------------------------------------
# Deep nesting near the parser cap
# ---------------------------------------------------------------

@st.composite
def _deep_nesting(draw):
    # Concentrate around 2048: sample near the limit.
    depth = draw(st.one_of(
        st.integers(min_value=1, max_value=16),
        st.integers(min_value=2000, max_value=2060),
        st.sampled_from([1024, 2047, 2048, 2049, 2050, 4096]),
    ))
    opener, closer = draw(st.sampled_from([("[", "]"), ("{", "}")]))
    if opener == "{":
        # build nested objects with a leaf value
        inner = "0"
        body = opener * depth + '"k":' + inner + closer * depth
        # wrap: {"k":{"k":...0...}}
        # simpler: produce nested arrays for objects with one key each
        s = ""
        for _ in range(depth):
            s += '{"k":'
        s += "0"
        s += "}" * depth
        return s
    else:
        return opener * depth + "0" + closer * depth


# ---------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------

@st.composite
def _json_text(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind <= 4:
        # Well-formed-ish value (possibly with duplicate keys / extremes).
        return draw(_value_strategy)
    if kind == 5:
        # Explicit empty containers and tiny structures.
        return draw(st.sampled_from([
            "{}", "[]", "[[],{}]", "{}", "[]",
            '{"a":{}}', '[[]]', '[{},{}]', '{"":0}',
        ]))
    if kind == 6:
        # Deep nesting near the cap.
        return draw(_deep_nesting())
    if kind == 7:
        # Malformed near-JSON fragment.
        return draw(_malformed())
    if kind == 8:
        # Well-formed value with trailing content (accepted by target).
        base = draw(_value_strategy)
        tail = draw(st.sampled_from([
            "", " ", "garbage", "xyz", "1", "true", "\nnull",
            " /* c */", "// c", "[]", "{}",
        ]))
        return base + tail
    # kind == 9: whitespace-padded value
    base = draw(_value_strategy)
    lead = draw(st.sampled_from(["", " ", "\t", "\n", "  \r\n"]))
    trail = draw(st.sampled_from(["", " ", "\t", "\n"]))
    return lead + base + trail


# ---------------------------------------------------------------
# Serialize-focused strategy (json_serialize_string coverage)
# ---------------------------------------------------------------

# Every character that json_serialize_string must handle specially:
# the quote, the backslash, and every C0 control character.  Also
# include the full 0x00-0x1F range plus DEL, and high bytes.
_SERIALIZE_SPECIAL_CHARS = (
    ['"', '\\']
    + [chr(c) for c in range(0x00, 0x20)]
    + [chr(0x7F)]
    + [chr(c) for c in range(0x80, 0x100)]
)


@st.composite
def _serialize_raw_string(draw):
    """A raw (unescaped) Python string whose characters stress the
    serializer's escaping logic: quotes, backslashes, control chars,
    and non-ASCII bytes."""
    n = draw(st.integers(min_value=0, max_value=64))
    frags = []
    for _ in range(n):
        frags.append(draw(st.one_of(
            st.sampled_from(_SAFE_CHARS),
            # Force the special escape branches to fire directly.
            st.sampled_from(_SERIALIZE_SPECIAL_CHARS),
            st.sampled_from([chr(c) for c in range(0x00, 0x20)]),
            st.sampled_from([chr(c) for c in range(0x7F, 0x100)]),
            st.sampled_from(["\u2028", "\u2029", "\uffff", "\ufffd",
                             "\u0085", "\u00a0", "\u2603"]),
        )))
    # Guarantee at least one of each critical escaping case often enough.
    if draw(st.booleans()):
        frags.append('"')
    if draw(st.booleans()):
        frags.append('\\')
    if draw(st.booleans()):
        frags.append(draw(st.sampled_from([chr(c) for c in range(0x00, 0x20)])))
    return "".join(frags)


def _embed_json_string(raw):
    """Encode a raw Python string as a valid JSON string literal so the
    parser accepts it and the serializer is invoked on the decoded value."""
    out = ['"']
    for ch in raw:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif o < 0x20:
            out.append("\\u%04x" % o)
        elif o < 0x7F:
            out.append(ch)
        else:
            out.append("\\u%04x" % o)
    out.append('"')
    return "".join(out)


@st.composite
def _serialize_string_input(draw):
    """Strings that exercise json_serialize_string: control chars,
    quotes, backslashes, non-ASCII, and long runs, embedded in valid
    JSON documents so the parser accepts them and reaches serialization."""
    raw = draw(_serialize_raw_string())
    literal = _embed_json_string(raw)
    # wrap in a few shapes so serialization is invoked on strings
    shape = draw(st.integers(min_value=0, max_value=3))
    if shape == 0:
        return literal
    if shape == 1:
        return "[" + literal + "]"
    if shape == 2:
        return '{"k":' + literal + "}"
    return '{"k":' + literal + ',"k2":' + literal + "}"


@st.composite
def _serialize_doc(draw):
    """Valid docs forcing full serialize paths (json_serialize_to_buffer_r)."""
    n = draw(st.integers(min_value=1, max_value=6))
    items = [draw(_serialize_string_input()) for _ in range(n)]
    return "[" + ",".join(items) + "]"


# ---------------------------------------------------------------
# json_serialize_string coverage: keys, long strings, all escapes
# ---------------------------------------------------------------

# A raw string covering every branch json_serialize_string must take:
# quote, backslash, every C0 control (with the \b \f \n \r \t short
# forms plus \u00XX for the rest), DEL, and non-ASCII.
_ALL_CONTROL_CHARS = "".join(chr(c) for c in range(0x00, 0x20))


@st.composite
def _serialize_string_direct(draw):
    """A raw Python string guaranteed to hit every escaping branch in
    json_serialize_string: '"', '\\', each short escape (\\b \\f \\n
    \\r \\t), the generic \\u00XX control path, DEL, and non-ASCII."""
    # Guarantee all short-escape and generic-escape branches fire.
    guaranteed = ['"', '\\', '\b', '\f', '\n', '\r', '\t']
    guaranteed += [chr(c) for c in range(0x00, 0x20)
                   if c not in (0x08, 0x0C, 0x0A, 0x0D, 0x09)]
    guaranteed.append(chr(0x7F))

    n = draw(st.integers(min_value=0, max_value=48))
    frags = []
    for _ in range(n):
        frags.append(draw(st.one_of(
            st.sampled_from(_SAFE_CHARS),
            st.sampled_from(_SERIALIZE_SPECIAL_CHARS),
            st.sampled_from([chr(c) for c in range(0x00, 0x20)]),
            st.sampled_from([chr(c) for c in range(0x7F, 0x100)]),
            st.sampled_from(["\u2028", "\u2029", "\uffff", "\ufffd",
                             "\u0085", "\u00a0", "\u2603"]),
        )))
    # Inject the guaranteed branch-covering chars at a random position.
    body = guaranteed + frags
    return "".join(body)


@st.composite
def _serialize_string_as_key(draw):
    """Put the stressing raw string in an object KEY position, so the
    serializer's key-escaping path is also exercised."""
    raw = draw(_serialize_string_direct())
    literal = _embed_json_string(raw)
    return "{" + literal + ":0}"


@st.composite
def _serialize_string_long(draw):
    """A long raw string to exercise the serializer's incremental
    buffer-write loop and any chunking branches."""
    n = draw(st.integers(min_value=0, max_value=256))
    frags = []
    for _ in range(n):
        frags.append(draw(st.one_of(
            st.sampled_from(_SAFE_CHARS),
            st.sampled_from(_SERIALIZE_SPECIAL_CHARS),
            st.sampled_from([chr(c) for c in range(0x00, 0x20)]),
        )))
    return "".join(frags)


@st.composite
def _serialize_string_input_v2(draw):
    """Valid JSON documents whose string values exercise
    json_serialize_string across every escaping branch, in value and
    key positions, plus long runs."""
    shape = draw(st.integers(min_value=0, max_value=5))
    if shape == 0:
        raw = draw(_serialize_string_direct())
        return _embed_json_string(raw)
    if shape == 1:
        raw = draw(_serialize_string_direct())
        return "[" + _embed_json_string(raw) + "]"
    if shape == 2:
        return draw(_serialize_string_as_key())
    if shape == 3:
        raw = draw(_serialize_string_long())
        return "[" + _embed_json_string(raw) + "]"
    if shape == 4:
        # Mix direct-branch string and long string in one doc.
        a = _embed_json_string(draw(_serialize_string_direct()))
        b = _embed_json_string(draw(_serialize_string_long()))
        return '{"k":' + a + ',"k2":' + b + "}"
    # shape == 5: string in both key and value position
    raw = draw(_serialize_string_direct())
    literal = _embed_json_string(raw)
    return "{" + literal + ":" + literal + "}"


# ---------------------------------------------------------------
# Direct json_serialize_string coverage (target the function itself)
# ---------------------------------------------------------------

# All C0 control characters, DEL, quote, and backslash, as a single
# guaranteed corpus.  Every one of these must take a distinct branch
# inside json_serialize_string.
_SERIALIZE_BRANCH_CORPUS = (
    '"' + '\\'
    + "\b" + "\f" + "\n" + "\r" + "\t"
    + "".join(chr(c) for c in range(0x00, 0x20)
              if c not in (0x08, 0x0C, 0x0A, 0x0D, 0x09))
    + chr(0x7F)
    + "\u0080" + "\u00ff" + "\uffff"
)


@st.composite
def _serialize_string_branch_doc(draw):
    """Documents engineered so json_serialize_string is invoked on a
    string that contains every character requiring a distinct escape
    branch.  The corpus is shuffled and padded so the serializer walks
    through each branch in varying orders, and placed both as a value
    and as a key."""
    # Shuffle the guaranteed corpus so branch order varies.
    chars = list(_SERIALIZE_BRANCH_CORPUS)
    # Random permutation via sorting on a drawn key.
    keys = draw(st.lists(
        st.integers(min_value=0, max_value=1 << 30),
        min_size=len(chars), max_size=len(chars),
    ))
    shuffled = [c for _, c in sorted(zip(keys, chars))]
    body = "".join(shuffled)

    # Optionally pad with random safe/control content to vary lengths.
    pad_n = draw(st.integers(min_value=0, max_value=32))
    pad = []
    for _ in range(pad_n):
        pad.append(draw(st.one_of(
            st.sampled_from(_SAFE_CHARS),
            st.sampled_from(_SERIALIZE_SPECIAL_CHARS),
            st.sampled_from([chr(c) for c in range(0x00, 0x20)]),
            st.sampled_from([chr(c) for c in range(0x7F, 0x100)]),
        )))
    raw = body + "".join(pad)

    literal = _embed_json_string(raw)
    shape = draw(st.integers(min_value=0, max_value=3))
    if shape == 0:
        return literal
    if shape == 1:
        return "[" + literal + "]"
    if shape == 2:
        return "{" + literal + ":0}"
    return '{"k":' + literal + "}"


@st.composite
def _serialize_string_all_codepoints(draw):
    """A raw string built from every byte value 0x00-0xFF (plus a few
    multibyte code points) so json_serialize_string's per-character
    dispatch is exercised exhaustively.  Embedded as a valid JSON
    string literal so the parser accepts it and serialization runs."""
    # Full 0x00-0xFF sweep, in a drawn rotation order.
    base = [chr(c) for c in range(0x00, 0x100)]
    rot = draw(st.integers(min_value=0, max_value=255))
    base = base[rot:] + base[:rot]
    extra = draw(st.lists(
        st.sampled_from(["\u2028", "\u2029", "\uffff", "\ufffd",
                         "\u0085", "\u00a0", "\u2603", "\U0001F600"]),
        min_size=0, max_size=8,
    ))
    raw = "".join(base) + "".join(extra)
    literal = _embed_json_string(raw)
    shape = draw(st.integers(min_value=0, max_value=2))
    if shape == 0:
        return literal
    if shape == 1:
        return "[" + literal + "]"
    return "{" + literal + ":0}"


@st.composite
def _serialize_string_nested(draw):
    """Nested containers holding branch-covering strings, so
    json_serialize_string is invoked repeatedly during a single
    serialization walk (json_serialize_to_buffer_r -> string)."""
    depth = draw(st.integers(min_value=1, max_value=6))
    raw = draw(_serialize_string_direct())
    literal = _embed_json_string(raw)
    # Build nested arrays with the string at the leaf.
    return "[" * depth + literal + "]" * depth


@st.composite
def _json_text_full(draw):
    kind = draw(st.integers(min_value=0, max_value=15))
    if kind == 10:
        return draw(_serialize_string_input())
    if kind == 11:
        return draw(_serialize_doc())
    if kind == 12:
        return draw(_serialize_string_input_v2())
    if kind == 13:
        # Dedicated json_serialize_string branch coverage.
        return draw(_serialize_string_input_v2())
    if kind == 14:
        # Direct branch-targeting documents for json_serialize_string.
        return draw(_serialize_string_branch_doc())
    if kind == 15:
        # Exhaustive per-codepoint sweep and nested invocation paths.
        return draw(st.one_of(
            _serialize_string_all_codepoints(),
            _serialize_string_nested(),
        ))
    return draw(_json_text())


strategy = _json_text_full()