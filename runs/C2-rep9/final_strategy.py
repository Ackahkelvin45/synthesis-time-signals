from hypothesis import strategies as st
import json

# ---------- leaf / scalar fragments ----------

# characters safe inside a JSON string (no raw control, no quote, no backslash)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\' + "".join(chr(c) for c in range(0x20)),
)

# raw control bytes / NUL that the parser handles faithfully
_control_char = st.sampled_from(
    [chr(c) for c in range(0x20)] + ["\x00", "\x7f"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    # surrogate escapes
    st.integers(min_value=0xD800, max_value=0xDBFF)
    .map(lambda n: "\\u%04x" % n),
    st.integers(min_value=0xDC00, max_value=0xDFFF)
    .map(lambda n: "\\u%04x" % n),
)

_string_body = st.one_of(
    _safe_char,
    _control_char,
    _escape,
)


@st.composite
def _json_string(draw):
    parts = draw(st.lists(_string_body, max_size=8))
    return '"' + "".join(parts) + '"'


# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_big_magnitude = st.sampled_from(
    ["1e309", "1e-309", "-1e309", "1e999", "-1e999", "1e308", "1e-308",
     "1e1000", "9e999", "1e+309", "0e999999", "123456789012345678901234567890"]
)


@st.composite
def _json_number(draw):
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind == 0:
        return draw(_big_magnitude)
    if kind == 1:
        # lone minus (accepted by parser)
        return "-"
    if kind == 2:
        # integer with optional sign
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        return sign + intpart
    if kind == 3:
        # decimal
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        frac = draw(st.text(alphabet="0123456789", min_size=1, max_size=6))
        return sign + intpart + "." + frac
    if kind == 4:
        # exponent
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        exp_sign = draw(st.sampled_from(["", "+", "-"]))
        exp_digits = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        return sign + intpart + draw(st.sampled_from(["e", "E"])) + exp_sign + exp_digits
    if kind == 5:
        # decimal + exponent
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        frac = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        exp_sign = draw(st.sampled_from(["", "+", "-"]))
        exp_digits = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        return (sign + intpart + "." + frac
                + draw(st.sampled_from(["e", "E"])) + exp_sign + exp_digits)
    # malformed-ish number forms (near-valid-but-malformed)
    return draw(st.sampled_from([
        "+1", ".5", "1.", "01", "00", "0x1F", "-.5", "+.5",
        "1e", "1e+", "1e-", "-", "--1", "1..2", "0.", ".0",
    ]))


# ---------- malformed string fragments ----------

_malformed_string = st.sampled_from([
    '"unterminated',
    '"unterminated\\',
    '"bad\\x"',
    '"\\u12"',
    '"\\uZZZZ"',
    '"\\u12G4"',
    '"trailing\\',
    "'single'",
    '"' + "\x00" + 'unterminated',
])


# ---------- recursive JSON value ----------

_json_value = st.deferred(lambda: _json_value_impl())


@st.composite
def _json_value_impl(draw):
    return draw(_json_value_strategy())


def _json_value_strategy():
    scalars = st.one_of(
        _json_string(),
        _json_number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed_string,
    )

    @st.composite
    def _obj(draw):
        # bias toward objects with members
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "{}"
        pairs = [draw(_json_pair()) for _ in range(n)]
        body = ",".join(pairs)
        # occasionally add a single trailing comma (accepted by parser)
        if draw(st.booleans()):
            body = body + ","
        return "{" + body + "}"

    @st.composite
    def _arr(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "[]"
        elems = [draw(_json_value) for _ in range(n)]
        body = ",".join(elems)
        if draw(st.booleans()):
            body = body + ","
        return "[" + body + "]"

    return st.one_of(
        scalars,
        _obj(),
        _arr(),
        _malformed_value(),
    )


@st.composite
def _json_pair(draw):
    key = draw(_json_string())
    # occasionally duplicate-ish key
    val = draw(_json_value)
    if draw(st.booleans()):
        # missing colon variant
        return key + draw(st.sampled_from([" ", ""])) + val
    return key + ":" + val


@st.composite
def _malformed_value(draw):
    return draw(st.sampled_from([
        "{,}", "[,]", "[,1]", "[1,,2]", "{,}",
        "{\"a\":1,,}",
        "{a:1}", "{'a':1}",
        "[1 2]", "{\"a\" 1}",
        "1abc", "[]xyz", "1 garbage", "true false",
        "//comment\n1", "/*c*/1",
        "[1,2",
        "{\"a\":1",
        "\x00", "\x00\x00", "[\x00]", "{\"a\":\x00}",
        "\x01\x02\x03",
    ]))


# ---------- near-crash mutation around crashing inputs ----------

# The parser crashed (ubsan: applying-non-zero-offset-to-null-pointer) on
# inputs like b'-' and b'1e309'. Intensify structure-preserving mutations
# around those crash seeds to explore the surrounding fault region.
_crash_seeds = ["-", "1e309"]

# small punctuation/structural tokens that can be inserted around a seed
_punct = st.sampled_from([
    "-", "+", ".", "e", "E", "0", "9", " ", "\t", "\n", "\r",
    "\x00", "[", "]", "{", "}", ",", ":", '"', "\\",
])

# numeric-ish alphabet for byte-level mutations of the seeds
_numish = st.sampled_from(list("0123456789eE+-."))

# full byte-ish alphabet for aggressive structural mutations
_anyish = st.sampled_from(
    list("0123456789eE+-. \t\n\r") + ["\x00", "[", "]", "{", "}", ",",
                                       ":", '"', "\\", "x", "a", "t", "f", "n"]
)

# extra structural corruption tokens used to intensify near-crash exploration
_corrupt = st.sampled_from([
    "", "-", "+", ".", "e", "E", "0", "1", "9", " ", "\t", "\n", "\r",
    "\x00", "[", "]", "{", "}", ",", ":", '"', "\\",
    "1e309", "-", "1e", "e309", "309", "1e30", "e30", ".309", "1e3",
    "[1e309]", "{\"a\":-}", "-1e309", "1e3091e309", "--", "1e309-",
])


@st.composite
def _near_crash(draw):
    seed = draw(st.sampled_from(_crash_seeds))
    style = draw(st.integers(min_value=0, max_value=19))

    if style == 0:
        # repeat the seed (e.g. '--', '1e3091e309')
        return seed * draw(st.integers(min_value=2, max_value=6))
    if style == 1:
        # prefix with punctuation
        return draw(_punct) + seed
    if style == 2:
        # suffix with punctuation
        return seed + draw(_punct)
    if style == 3:
        # wrap in brackets/braces
        return draw(st.sampled_from(["[" + seed + "]",
                                     "{" + seed + "}",
                                     '{"a":' + seed + "}",
                                     "[" + seed + "," + seed + "]",
                                     '"' + seed + '"']))
    if style == 4:
        # byte-level mutation: replace one char with a numeric-ish char
        if not seed:
            return seed
        i = draw(st.integers(min_value=0, max_value=len(seed) - 1))
        c = draw(_numish)
        return seed[:i] + c + seed[i + 1:]
    if style == 5:
        # insert a numeric-ish char somewhere
        i = draw(st.integers(min_value=0, max_value=len(seed)))
        return seed[:i] + draw(_numish) + seed[i:]
    if style == 6:
        # delete a char
        if len(seed) <= 1:
            return seed
        i = draw(st.integers(min_value=0, max_value=len(seed) - 1))
        return seed[:i] + seed[i + 1:]
    if style == 7:
        # concatenate two seeds/mutations
        return seed + draw(st.sampled_from(_crash_seeds))
    if style == 8:
        # exponent-focused variants around 1e309
        return draw(st.sampled_from([
            "1e309", "1e310", "1e-309", "-1e309", "1e309e309",
            "1e3091", "1e30", "1e3090", "1e309.", ".1e309",
            "1e309\x00", "1e309 ", " 1e309", "-1e309-",
        ]))
    if style == 9:
        # minus-focused variants around '-'
        return draw(st.sampled_from([
            "-", "--", "- ", " -", "-\n", "-\x00", "-[", "-{", "-,",
            "-:", "-.", "-e", "-1", "-0", "[-]", "{-}", '{"-":-}',
        ]))
    if style == 10:
        # multi-byte structural mutation: replace several chars with any-ish
        if not seed:
            return seed
        n = draw(st.integers(min_value=1, max_value=len(seed)))
        chars = list(seed)
        for _ in range(n):
            i = draw(st.integers(min_value=0, max_value=len(chars) - 1))
            chars[i] = draw(_anyish)
        return "".join(chars)
    if style == 11:
        # insert random structural tokens at multiple positions
        parts = list(seed)
        k = draw(st.integers(min_value=1, max_value=4))
        for _ in range(k):
            i = draw(st.integers(min_value=0, max_value=len(parts)))
            parts.insert(i, draw(_anyish))
        return "".join(parts)
    if style == 12:
        # wrap seed inside a chain of containers
        depth = draw(st.integers(min_value=1, max_value=4))
        s = seed
        for _ in range(depth):
            s = draw(st.sampled_from([
                "[" + s + "]",
                "{" + s + "}",
                '{"k":' + s + "}",
                "[" + s + "," + seed + "]",
            ]))
        return s
    if style == 13:
        # seed with surrounding whitespace / separators of varying length
        pad = draw(st.text(alphabet=" \t\n\r", min_size=0, max_size=4))
        sep = draw(st.sampled_from(["", ",", ":", " ", "\x00"]))
        return pad + seed + sep + draw(st.sampled_from(["", seed, "-", "1e309"])) + pad
    if style == 14:
        # prefix/suffix with other JSON-ish tokens to force deep parse paths
        return draw(st.sampled_from([
            "[" + seed, seed + "]", "{" + seed, seed + "}",
            '{"a":[' + seed + "]}", "[" + seed + "," + seed + "," + seed + "]",
            '{"a":' + seed + ',"b":' + seed + "}",
            "[" + seed + ",[" + seed + "]]",
        ]))
    if style == 15:
        # intensified: splice multiple corruption tokens around the seed
        k = draw(st.integers(min_value=1, max_value=6))
        out = seed
        for _ in range(k):
            pos = draw(st.integers(min_value=0, max_value=len(out)))
            out = out[:pos] + draw(_corrupt) + out[pos:]
        return out
    if style == 16:
        # intensified: alternating seed/corrupt interleave
        k = draw(st.integers(min_value=1, max_value=5))
        pieces = []
        for _ in range(k):
            pieces.append(seed)
            pieces.append(draw(_corrupt))
        if draw(st.booleans()):
            pieces.append(seed)
        return "".join(pieces)
    if style == 17:
        # intensified: nested container wrapping with corrupted inner seed
        inner = draw(_corrupt) + seed + draw(_corrupt)
        depth = draw(st.integers(min_value=1, max_value=5))
        s = inner
        for _ in range(depth):
            s = draw(st.sampled_from([
                "[" + s + "]",
                "{" + s + "}",
                '{"k":' + s + "}",
                "[" + s + "," + inner + "]",
                '{"k":' + s + ',"j":' + inner + "}",
            ]))
        return s
    if style == 18:
        # intensified: repeated byte-level rewrites of the seed
        s = seed
        rounds = draw(st.integers(min_value=1, max_value=8))
        for _ in range(rounds):
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + draw(_corrupt) + s[i:]
        return s
    # aggressive byte-level: build a string from a small alphabet around the seed
    n = draw(st.integers(min_value=1, max_value=8))
    frag = draw(st.lists(_anyish, min_size=0, max_size=n))
    pos = draw(st.integers(min_value=0, max_value=len(seed)))
    return seed[:pos] + "".join(frag) + seed[pos:]


# ---------- top-level strategy ----------

deep_value = st.recursive(
    _json_value_strategy(),
    lambda children: st.one_of(
        children.map(lambda v: "[" + v + "]"),
        children.map(lambda v: '{"k":' + v + "}"),
        st.lists(children, min_size=1, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]"),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "{" + ",".join('"k%d":%s' % (i, x) for i, x in enumerate(xs)) + "}"
        ),
    ),
    max_leaves=12,
)


@st.composite
def _strategy_impl(draw):
    style = draw(st.integers(min_value=0, max_value=10))
    if style == 0:
        # deep nesting
        return draw(deep_value)
    if style == 1:
        # raw NUL / control bytes
        return draw(st.sampled_from([
            "\x00", "[\x00]", "{\"a\":\x00}", "\x00\x00\x00",
            "[\x01,\x02,\x03]", "{\"k\":\"\x00\"}",
        ]))
    if style == 2:
        # extreme numbers
        return draw(_big_magnitude)
    if style == 3:
        # lone minus
        return "-"
    if style == 4:
        # duplicate keys
        return draw(st.sampled_from([
            '{"a":1,"a":2}', '{"a":1,"a":2,"a":3}',
            '{"x":{"x":{"x":1}}}',
        ]))
    if style == 5:
        # malformed
        return draw(_malformed_value())
    if style == 6:
        # leading whitespace variants
        inner = draw(_json_value)
        return draw(st.sampled_from([" ", "\t", "\n", "\r", "  "])) + inner
    if style == 7:
        # trailing content
        inner = draw(_json_value)
        return inner + draw(st.sampled_from(["x", " ", "garbage", "\x00"]))
    if style == 8:
        # near-crash mutation around crashing seeds
        return draw(_near_crash())
    # general value
    return draw(_json_value)


strategy = _strategy_impl()