from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters allowed inside a JSON string (no raw NUL, no unescaped control).
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),  # no lone surrogates
    blacklist_characters="\x00",   # parser is NUL-terminated
).filter(lambda c: ord(c) > 0x1F and c not in '"\\')

# Escape sequences that are always valid.
_SIMPLE_ESCAPES = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

# \uXXXX escapes, including surrogate ranges (lone surrogates are still
# syntactically valid per the grammar).
_UNICODE_ESCAPE = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
)

# Deliberately include surrogate escapes and the NUL escape (as text).
_SPECIAL_ESCAPES = st.sampled_from([
    "\\u0000", "\\uD800", "\\uDFFF", "\\uDBFF", "\\uDC00", "\\uFFFF",
    "\\u0041", "\\u00e9", "\\u10FFFF"[:6],
])

_ESCAPE = st.one_of(_SIMPLE_ESCAPES, _UNICODE_ESCAPE, _SPECIAL_ESCAPES)

# Raw control-ish bytes are forbidden by grammar; keep them out of valid strings.
_STRING_CHAR = st.one_of(_SAFE_CHARS, _ESCAPE)


def _quoted(chars_strategy, min_size=0, max_size=32):
    return st.lists(chars_strategy, min_size=min_size, max_size=max_size).map(
        lambda cs: '"' + "".join(cs) + '"'
    )


# Valid string literal.
_valid_string = _quoted(_STRING_CHAR)

# Malformed string variants.
_unterminated_string = st.lists(_STRING_CHAR, min_size=0, max_size=16).map(
    lambda cs: '"' + "".join(cs)
)
_bad_escape_string = st.lists(
    st.one_of(_STRING_CHAR, st.sampled_from(["\\x", "\\u12", "\\uZZZZ", "\\ "])),
    min_size=0,
    max_size=16,
).map(lambda cs: '"' + "".join(cs) + '"')

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_DIGITS = st.text(alphabet="0123456789", min_size=1, max_size=18)
_NZDIGITS = st.text(alphabet="0123456789", min_size=1, max_size=18).filter(
    lambda s: s[0] != "0"
)

_INT_PART = st.one_of(st.just("0"), _NZDIGITS)

_EXP_PART = st.one_of(
    st.builds(lambda e, s, d: e + s + d,
              st.sampled_from(["e", "E"]),
              st.sampled_from(["", "+", "-"]),
              _DIGITS),
    st.sampled_from(["e309", "E309", "e-309", "e9999", "e-9999", "e308", "e-324"]),
)

_FRAC_PART = st.builds(lambda d: "." + d, _DIGITS)

_valid_number = st.builds(
    lambda sign, ip, frac, exp: sign + ip + frac + exp,
    st.sampled_from(["", "-"]),
    _INT_PART,
    st.one_of(st.just(""), _FRAC_PART),
    st.one_of(st.just(""), _EXP_PART),
)

# Extreme / boundary numbers.
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e400", "1e-400",
    "9" * 30, "-" + "9" * 30, "0." + "0" * 20 + "1",
    "1.7976931348623157e308", "1.7976931348623159e308",
    "1e308", "1e-308", "0e0", "-0", "0.0", "1E+10", "1e01",
])

# Near-valid / malformed numbers.
_bad_number = st.sampled_from([
    "01", "007", "-01", "+1", ".5", "-.5", "1.", "1.e5", "-", "-.",
    "1..2", "1e", "1e+", "1e-", "--1", "1.2.3", "0x1F", "Infinity",
    "NaN", "-Infinity", "1_000", "1,5",
])

# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser cap (~2048).
_DEPTH_NEAR_CAP = st.one_of(
    st.integers(min_value=1, max_value=8),
    st.integers(min_value=2000, max_value=2060),
    st.just(2048),
)


@st.composite
def _deep_wrapper(draw):
    """Produce deep nesting near the 2048 cap using repeated brackets."""
    depth = draw(_DEPTH_NEAR_CAP)
    kind = draw(st.sampled_from(["arr", "obj"]))
    if kind == "arr":
        return "[" * depth + "]" * depth
    return '{"a":' * depth + "null" + "}" * depth


def _json_value(draw):
    """Non-recursive primitives."""
    return draw(
        st.one_of(
            _valid_string,
            _valid_number,
            _extreme_number,
            st.sampled_from(["true", "false", "null"]),
        )
    )


# Composite recursive strategy for value/obj/arr.
@st.composite
def _value(draw):
    return draw(
        st.recursive(
            st.one_of(_valid_string, _valid_number, _extreme_number,
                      st.sampled_from(["true", "false", "null"])),
            lambda children: st.one_of(
                # array
                st.lists(children, min_size=0, max_size=6).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                # object with distinct-ish keys (duplicates sometimes on purpose)
                st.lists(
                    st.tuples(_valid_string, children),
                    min_size=0,
                    max_size=6,
                ).map(
                    lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"
                ),
            ),
            max_leaves=40,
        )
    )


# ---------------------------------------------------------------------------
# Edge-case / malformed top-level inputs
# ---------------------------------------------------------------------------

_empty_containers = st.sampled_from(["{}", "[]", " { } ", "[ ]", "\t{}\n", "[{}]", "{\"a\":[]}"])

_duplicate_keys = st.builds(
    lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
    _valid_string,
    _valid_string,
    _valid_string,
)

_trailing_content = st.builds(
    lambda v, t: v + t,
    st.one_of(_valid_string, _valid_number, st.sampled_from(["[]", "{}", "null", "true"])),
    st.sampled_from(["abc", " garbage", "xyz", "[]", "{}", "1", "  \t\n", "/*c*/", "//c\n"]),
)

_malformed = st.one_of(
    # double commas
    st.sampled_from([
        "[1,,2]", "{,}", "[,]", "[1,]", "{\"a\":1,}", "[1 2]",
        "{\"a\":1 \"b\":2}", "{\"a\" 1}", "{\"a\":}", "{:1}",
        "[}", "{]", "[[", "]]", "{{", "}}", "[1,2", "{\"a\":1",
        "tru", "fals", "nul", "TRUE", "Null", "None",
    ]),
    # unterminated / bad strings
    _unterminated_string,
    _bad_escape_string,
    # malformed numbers
    _bad_number,
    # near-valid with trailing comma / missing colon
    st.builds(lambda k: "{" + k + ":", _valid_string),
    st.builds(lambda k: "{" + k + ":}", _valid_string),
)

_deep = _deep_wrapper()

# ---------------------------------------------------------------------------
# Serialize-focused inputs (exercise json_serialize_string / _to_buffer_r)
# ---------------------------------------------------------------------------

# Strings that force every escape branch in json_serialize_string: quotes,
# backslashes, forward slashes, and all C control escapes plus other controls.
_SERIALIZE_STRINGS = st.sampled_from([
    '"',
    '\\',
    '/',
    '\b', '\f', '\n', '\r', '\t',
    '"\\/\b\f\n\r\t',
    'a"b\\c/d',
    'quote:" backslash:\\ slash:/',
    'ctrl:\x01\x02\x03\x1f',
    'mix:"\\\b\f\n\r\t/\x00\x1f',
    'unicode:\u00e9\u4e2d\U0001F600',
    'surrogate-pair:\U0001F600\U0001F4A9',
    'long:' + 'a' * 200,
    'escapes:' + '\\' * 20 + '"' * 20,
    'tabs:\t\t\tnewlines:\n\n\n',
    'nul-adjacent:\x01\x7f',
])

# Objects/arrays containing serialize-heavy strings, forcing the serializer to
# walk nested containers and stringify each member.
_serialize_object = st.builds(
    lambda k, v: "{" + k + ":" + v + "}",
    _valid_string,
    st.one_of(_valid_string, _SERIALIZE_STRINGS.map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')),
)

_serialize_nested = st.builds(
    lambda s1, s2: '{"k1":' + s1 + ',"k2":[' + s2 + ']}',
    _SERIALIZE_STRINGS.map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"'),
    _SERIALIZE_STRINGS.map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"'),
)

_serialize_inputs = st.one_of(
    _SERIALIZE_STRINGS.map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"'),
    _serialize_object,
    _serialize_nested,
    st.lists(
        _SERIALIZE_STRINGS.map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"'),
        min_size=1,
        max_size=6,
    ).map(lambda vs: "[" + ",".join(vs) + "]"),
)

# ---------------------------------------------------------------------------
# Direct json_serialize_string coverage: raw strings containing every escape
# branch. These are emitted as JSON string literals with the raw control
# characters preserved (escaped where needed for valid JSON), so the parser
# produces strings that exercise all serializer branches (quote, backslash,
# slash, \b \f \n \r \t, and other control chars via unicode escapes).
# ---------------------------------------------------------------------------

_SERIALIZE_BRANCH_CHARS = st.sampled_from([
    '"', '\\', '/', '\b', '\f', '\n', '\r', '\t',
    '\x00', '\x01', '\x02', '\x1f', '\x7f',
    'a', 'Z', '0', ' ', '\u00e9', '\u4e2d', '\U0001F600',
])


def _escape_for_json_literal(s):
    out = []
    for c in s:
        o = ord(c)
        if c == '"':
            out.append('\\"')
        elif c == '\\':
            out.append('\\\\')
        elif c == '\b':
            out.append('\\b')
        elif c == '\f':
            out.append('\\f')
        elif c == '\n':
            out.append('\\n')
        elif c == '\r':
            out.append('\\r')
        elif c == '\t':
            out.append('\\t')
        elif o < 0x20:
            out.append('\\u%04x' % o)
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


_serialize_branch_string = st.lists(
    _SERIALIZE_BRANCH_CHARS, min_size=1, max_size=40
).map(lambda cs: _escape_for_json_literal("".join(cs)))

_serialize_branch_inputs = st.one_of(
    _serialize_branch_string,
    st.lists(_serialize_branch_string, min_size=1, max_size=6).map(
        lambda vs: "[" + ",".join(vs) + "]"
    ),
    st.lists(
        st.tuples(_serialize_branch_string, _serialize_branch_string),
        min_size=1,
        max_size=6,
    ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
)

# ---------------------------------------------------------------------------
# Function-targeted coverage: json_serialize_string
# ---------------------------------------------------------------------------

# Characters whose serialization takes every distinct branch inside
# json_serialize_string: the quote branch, backslash branch, forward-slash
# branch, the \b \f \n \r \t named escapes, and the generic control-character
# unicode-escape branch (ord < 0x20), plus plain pass-through characters.
_SERIALIZE_STRING_BRANCH_CHARS = st.sampled_from([
    '"', '\\', '/',
    '\b', '\f', '\n', '\r', '\t',
    '\x01', '\x02', '\x03', '\x07', '\x0b', '\x0e', '\x1f',
    '\x00', '\x7f',
    'a', 'z', 'A', 'Z', '0', '9', ' ', '~',
    '\u00e9', '\u4e2d', '\U0001F600',
])


def _json_string_literal_from_raw(raw):
    """Emit a JSON string literal that parses back to `raw` exactly, so the
    parser hands `raw` to json_serialize_string and every branch is reached."""
    out = []
    for c in raw:
        o = ord(c)
        if c == '"':
            out.append('\\"')
        elif c == '\\':
            out.append('\\\\')
        elif c == '/':
            out.append('/')
        elif c == '\b':
            out.append('\\b')
        elif c == '\f':
            out.append('\\f')
        elif c == '\n':
            out.append('\\n')
        elif c == '\r':
            out.append('\\r')
        elif c == '\t':
            out.append('\\t')
        elif o < 0x20:
            out.append('\\u%04x' % o)
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


_serialize_string_raw = st.lists(
    _SERIALIZE_STRING_BRANCH_CHARS, min_size=1, max_size=48
).map(lambda cs: "".join(cs))

# Top-level literal that is a single string, forcing json_serialize_string.
_serialize_string_literal = _serialize_string_raw.map(_json_string_literal_from_raw)

# Ensure each branch char appears (guaranteed branch hits) as a literal.
_serialize_string_all_branches = _SERIALIZE_STRING_BRANCH_CHARS.map(
    lambda c: _json_string_literal_from_raw(c)
)

# Same strings embedded in containers so the serializer recurses into them.
_serialize_string_in_array = st.lists(
    _serialize_string_raw.map(_json_string_literal_from_raw),
    min_size=1,
    max_size=8,
).map(lambda vs: "[" + ",".join(vs) + "]")

_serialize_string_in_object = st.lists(
    st.tuples(
        _serialize_string_raw.map(_json_string_literal_from_raw),
        _serialize_string_raw.map(_json_string_literal_from_raw),
    ),
    min_size=1,
    max_size=8,
).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}")

_serialize_string_inputs = st.one_of(
    _serialize_string_literal,
    _serialize_string_all_branches,
    _serialize_string_in_array,
    _serialize_string_in_object,
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value(),
    _deep,
    _empty_containers,
    _duplicate_keys,
    _trailing_content,
    _malformed,
    # whitespace-padded valid values
    st.builds(lambda v: "  " + v + "  \n", _value()),
    # serialize-focused inputs
    _serialize_inputs,
    # direct json_serialize_string branch coverage
    _serialize_branch_inputs,
    # function-targeted coverage for json_serialize_string
    _serialize_string_inputs,
)