import json
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Scalars and leaves
# ---------------------------------------------------------------------------

# Characters that are safe inside a JSON string per the grammar (no quote,
# no backslash, no raw control bytes).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in Python str
    blacklist_characters='\\"',
    min_codepoint=0x20,
)

# Raw control bytes / NUL that the target parser accepts inside strings.
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"]
)

# Escape sequences.  Valid single-char escapes plus \uXXXX escapes.
_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    """A \\uXXXX escape, sometimes a lone surrogate (parser rejects those)."""
    kind = draw(st.sampled_from(["bmp", "high", "low", "pair"]))
    if kind == "bmp":
        cp = draw(st.integers(min_value=0x0000, max_value=0xD7FF))
        return "\\u%04x" % cp
    if kind == "high":
        cp = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        return "\\u%04x" % cp
    if kind == "low":
        cp = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x" % cp
    # valid surrogate pair
    hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
    lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
    return "\\u%04x\\u%04x" % (hi, lo)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_extreme_numbers = st.sampled_from(
    [
        "1e309", "-1e309", "1e-309", "0e0", "0", "-0", "0.0", "-0.0",
        "1e1000", "1e-1000", "1E+308", "1e+308", "1e-308",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "0.0000000000000000000001",
        "1.7976931348623157e308",
        "9007199254740993",
        "0.1", "1e01", "1e-01",
    ]
)


@st.composite
def _number(draw):
    choice = draw(st.integers(min_value=0, max_value=5))
    if choice == 0:
        return draw(_extreme_numbers)
    if choice == 1:
        # integral
        n = draw(st.integers(min_value=-(2 ** 63), max_value=2 ** 63))
        return str(n)
    if choice == 2:
        # fractional
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(st.sampled_from(["0", "1", "42", "999999"]))
        frac = draw(st.text(alphabet="0123456789", min_size=1, max_size=8))
        return sign + intpart + "." + frac
    if choice == 3:
        # exponent
        sign = draw(st.sampled_from(["", "-"]))
        mant = draw(st.sampled_from(["1", "0", "3", "12"]))
        e = draw(st.sampled_from(["e", "E"]))
        esign = draw(st.sampled_from(["", "+", "-"]))
        exp = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        return sign + mant + e + esign + exp
    if choice == 4:
        # "near-valid" malformed numbers (parser rejects most of these)
        return draw(
            st.sampled_from(
                [
                    "+1", ".5", "-.5", "01", "007", "1.", "-", "+", "1e",
                    "1e+", "--1", "1..2", "0x", "1.2.3",
                ]
            )
        )
    # hex numbers: parser accepts (deviation); emit some
    return draw(st.sampled_from(["0x10", "0xFF", "-0x1", "0x0"]))


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

@st.composite
def _string_body(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    parts = []
    for _ in range(n):
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            parts.append(draw(_safe_chars))
        elif kind == 1:
            parts.append(draw(_simple_escapes))
        elif kind == 2:
            parts.append(draw(_raw_control))
        else:
            parts.append(draw(_unicode_escape()))
    return "".join(parts)


@st.composite
def _string(draw):
    body = draw(_string_body())
    # Occasionally emit a malformed / unterminated string.
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        return '"' + body  # unterminated
    return '"' + body + '"'


# ---------------------------------------------------------------------------
# Recursive structure: value / obj / arr
# ---------------------------------------------------------------------------

_MAX_DEPTH = 1000


def _depth_strategy(max_leaves):
    """Build the recursive JSON value strategy."""

    @st.composite
    def _value(draw):
        return draw(_scalar_or_container(max_leaves))

    return _value


@st.composite
def _scalar_or_container(draw, max_leaves):
    # Choose leaf vs container.
    if max_leaves <= 0:
        return draw(_leaf())
    is_container = draw(st.booleans())
    if not is_container:
        return draw(_leaf())
    # container: obj or arr
    if draw(st.booleans()):
        return draw(_obj(max_leaves))
    return draw(_arr(max_leaves))


@st.composite
def _leaf(draw):
    choice = draw(st.integers(min_value=0, max_value=5))
    if choice == 0:
        return "null"
    if choice == 1:
        return "true"
    if choice == 2:
        return "false"
    if choice == 3:
        return draw(_number())
    if choice == 4:
        return draw(_string())
    # near-valid malformed literal (parser rejects)
    return draw(st.sampled_from(["NaN", "Infinity", "-Infinity", "nul", "tru"]))


@st.composite
def _obj(draw, max_leaves):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{}"
    pairs = []
    for _ in range(n):
        key = draw(_string())
        val = draw(_scalar_or_container(max_leaves - 1))
        pairs.append(key + ":" + val)
    body = ",".join(pairs)
    # Occasionally inject duplicate keys / malformed separators.
    r = draw(st.integers(min_value=0, max_value=9))
    if r == 0:
        # duplicate key
        body = body + "," + body.split(":")[0] + ":" + draw(_leaf())
    elif r == 1:
        return "{" + body + ",}"  # trailing comma (rejected)
    elif r == 2:
        return "{" + body.replace(":", "", 1) + "}"  # missing colon
    return "{" + body + "}"


@st.composite
def _arr(draw, max_leaves):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "[]"
    items = [draw(_scalar_or_container(max_leaves - 1)) for _ in range(n)]
    body = ",".join(items)
    r = draw(st.integers(min_value=0, max_value=9))
    if r == 0:
        return "[" + body + ",]"  # trailing comma (rejected)
    if r == 1:
        return "[" + body + ",," + draw(_leaf()) + "]"  # double comma
    return "[" + body + "]"


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

def _deep_nesting():
    """Generate near-the-limit nesting depth (concentrate around 1000)."""
    depth = draw_depth()
    # Build nested arrays `[[[...]]]` or objects `{"a":{"a":...}}`.
    if depth % 2 == 0:
        return "[" * depth + "]" * depth
    return '{"a":' * depth + "null" + "}" * depth


@st.composite
def _draw_depth(draw):
    # Concentrate around the 1000 limit: 990..1010, plus a few far values.
    r = draw(st.integers(min_value=0, max_value=19))
    if r < 12:
        return draw(st.integers(min_value=990, max_value=1010))
    if r < 16:
        return draw(st.integers(min_value=900, max_value=1050))
    return draw(st.integers(min_value=0, max_value=50))


def draw_depth():
    # helper for _deep_nesting (draws via hypothesis at call time)
    return _draw_depth().example()


@st.composite
def _top_level(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        # deep nesting near the limit
        depth = draw(_draw_depth())
        if draw(st.booleans()):
            return "[" * depth + "]" * depth
        return '{"a":' * depth + "null" + "}" * depth
    if kind == 1:
        # BOM before a value (accepted)
        return "\ufeff" + draw(_scalar_or_container(2))
    if kind == 2:
        # trailing content after a complete value (accepted)
        return draw(_scalar_or_container(2)) + draw(
            st.sampled_from(["abc", " 1 2", "\x00", " , ", "{}"])
        )
    if kind == 3:
        # raw NUL / control around a value
        return draw(st.sampled_from(["\x00", "1\x00", "\x00{}", "[]\x00"]))
    if kind == 4:
        # empty input (rejected)
        return ""
    if kind == 5:
        # whitespace only (rejected)
        return draw(st.sampled_from([" ", "\t", "\n", "\r\n", "  \t "]))
    # ordinary recursive value
    return draw(_scalar_or_container(3))


# ---------------------------------------------------------------------------
# cJSON_Compare coverage: emit scripts that parse and compare two values.
# ---------------------------------------------------------------------------

@st.composite
def _compare_value(draw, depth):
    """A JSON value that is more likely to be structurally interesting for
    cJSON_Compare: mix of scalars, arrays, and objects, with controlled
    depth so that equal/unequal and case-sensitive/insensitive branches
    all get exercised."""
    if depth <= 0:
        return draw(_leaf())
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind <= 2:
        return draw(_leaf())
    if kind == 3:
        # small array of scalars / nested values
        n = draw(st.integers(min_value=0, max_value=4))
        items = [draw(_compare_value(depth - 1)) for _ in range(n)]
        return "[" + ",".join(items) + "]"
    if kind == 4:
        # object with string keys; sometimes duplicate keys to hit the
        # object-comparison "missing key" / duplicate branch.
        n = draw(st.integers(min_value=0, max_value=4))
        pairs = []
        for _ in range(n):
            key = draw(_string())
            val = draw(_compare_value(depth - 1))
            pairs.append(key + ":" + val)
        if pairs and draw(st.integers(min_value=0, max_value=3)) == 0:
            # duplicate-key variant
            pairs.append(pairs[0])
        return "{" + ",".join(pairs) + "}"
    if kind == 5:
        # array of objects (exercises array-of-container comparison)
        n = draw(st.integers(min_value=0, max_value=3))
        items = []
        for _ in range(n):
            k = draw(_string())
            v = draw(_compare_value(depth - 1))
            items.append("{" + k + ":" + v + "}")
        return "[" + ",".join(items) + "]"
    # object of arrays
    n = draw(st.integers(min_value=0, max_value=3))
    pairs = []
    for _ in range(n):
        key = draw(_string())
        val = draw(_compare_value(depth - 1))
        pairs.append(key + ":[" + val + "]")
    return "{" + ",".join(pairs) + "}"


@st.composite
def _compare_script(draw):
    """Two JSON values plus comparison options, in a driver script form.

    The parser's cJSON_Compare is exercised by parsing two values and
    comparing them with/without case sensitivity.  We emit a small script
    that the harness recognizes (parse both, compare) so cJSON_Compare's
    branches (equal/unequal, case-sensitive/insensitive, object/array,
    numbers, strings, null/bool) get hit.
    """
    a = draw(_compare_value(3))
    # Sometimes compare a value against itself (equal path), sometimes a
    # mutated/other value (unequal path).
    mode = draw(st.integers(min_value=0, max_value=4))
    if mode == 0:
        # identical (equal path)
        b = a
    elif mode == 1:
        # independent value (usually unequal)
        b = draw(_compare_value(3))
    elif mode == 2:
        # structural mutation of `a` to force unequal on a shared shape
        b = a
        if b.startswith("[") and b.endswith("]"):
            b = "[" + b[1:-1] + ("," if len(b) > 2 else "") + draw(_leaf()) + "]"
        elif b.startswith("{") and b.endswith("}"):
            inner = b[1:-1]
            extra = draw(_string()) + ":" + draw(_leaf())
            b = "{" + (inner + "," if inner else "") + extra + "}"
        else:
            # scalar: perturb by appending a distinguishing char
            b = draw(_leaf())
    elif mode == 3:
        # case-variation of a string to hit case-insensitive branch
        s = draw(_string_body())
        b = '"' + s.swapcase() + '"'
        a = '"' + s + '"'
    else:
        # empty vs non-empty container pairs
        b = draw(st.sampled_from(["[]", "{}", "null", "0", '""', "false"]))
    case_sensitive = draw(st.booleans())
    return json.dumps(
        {
            "compare": {
                "a": a,
                "b": b,
                "case_sensitive": case_sensitive,
            }
        }
    )


@st.composite
def _top_level_with_compare(draw):
    if draw(st.integers(min_value=0, max_value=3)) == 0:
        return draw(_compare_script())
    return draw(_top_level())


# ---------------------------------------------------------------------------
# cover_function: cJSON_Compare has 0% branch coverage.  Emit driver
# scripts that parse two values and compare them, exercising every type
# branch (invalid, null, bool, number, string, array, object), the
# equal/unequal paths, and the case-sensitive/case-insensitive paths.
# ---------------------------------------------------------------------------

@st.composite
def _compare_pair(draw):
    """Generate a (a, b, case_sensitive) triple that drives cJSON_Compare.

    We deliberately pair values of matching and mismatching types so that
    every type-dispatch branch (invalid, null, bool, number, string,
    array, object) and every equal/unequal outcome is reached.
    """
    kind = draw(st.integers(min_value=0, max_value=11))
    if kind == 0:
        # identical scalars: equal path for each scalar type
        v = draw(st.sampled_from(["null", "true", "false", "0", "1", "-1",
                                  "3.14", '""', '"a"', '"A"']))
        return v, v, draw(st.booleans())
    if kind == 1:
        # mismatched scalar types: unequal, exercises type-dispatch
        a = draw(st.sampled_from(["null", "true", "false", "0", "1", '"x"']))
        b = draw(st.sampled_from(["null", "true", "false", "0", "1", '"x"']))
        return a, b, draw(st.booleans())
    if kind == 2:
        # numbers: equal, unequal, and case_sensitive-irrelevant paths
        n = draw(_number())
        return n, n, draw(st.booleans())
    if kind == 3:
        # numbers: unequal
        return draw(_number()), draw(_number()), draw(st.booleans())
    if kind == 4:
        # strings: case-insensitive equal / unequal
        s = draw(_string_body())
        other = s.swapcase() if draw(st.booleans()) else draw(_string_body())
        return ('"' + s + '"', '"' + other + '"', draw(st.booleans()))
    if kind == 5:
        # arrays: equal
        v = draw(_compare_value(2))
        if not (v.startswith("[") and v.endswith("]")):
            v = "[1,2,3]"
        return v, v, draw(st.booleans())
    if kind == 6:
        # arrays: unequal (different length / element)
        a = draw(_compare_value(2))
        b = draw(_compare_value(2))
        if not (a.startswith("[") and a.endswith("]")):
            a = "[1]"
        if not (b.startswith("[") and b.endswith("]")):
            b = "[2]"
        return a, b, draw(st.booleans())
    if kind == 7:
        # objects: equal
        v = draw(_compare_value(2))
        if not (v.startswith("{") and v.endswith("}")):
            v = '{"a":1}'
        return v, v, draw(st.booleans())
    if kind == 8:
        # objects: unequal (different key set / value)
        a = draw(_compare_value(2))
        b = draw(_compare_value(2))
        if not (a.startswith("{") and a.endswith("}")):
            a = '{"a":1}'
        if not (b.startswith("{") and b.endswith("}")):
            b = '{"b":2}'
        return a, b, draw(st.booleans())
    if kind == 9:
        # mixed container types: array vs object vs scalar
        a = draw(st.sampled_from(["[1,2]", '{"a":1}', "1", '"s"', "null", "true"]))
        b = draw(st.sampled_from(["[1,2]", '{"a":1}', "1", '"s"', "null", "true"]))
        return a, b, draw(st.booleans())
    if kind == 10:
        # nested structures with matching shapes
        key = draw(_string())
        inner = draw(_compare_value(1))
        v = "{" + key + ":[" + inner + "]}"
        return v, v, draw(st.booleans())
    # nested structures with mismatched shapes
    key = draw(_string())
    inner = draw(_compare_value(1))
    a = "{" + key + ":[" + inner + "]}"
    b = "[" + inner + "]"
    return a, b, draw(st.booleans())


@st.composite
def _compare_driver(draw):
    """Emit a driver script recognized by the harness: parse both values
    and run cJSON_Compare with the given case sensitivity."""
    a, b, case_sensitive = draw(_compare_pair())
    return json.dumps(
        {
            "compare": {
                "a": a,
                "b": b,
                "case_sensitive": case_sensitive,
            }
        }
    )


@st.composite
def _top_level_with_compare_and_driver(draw):
    # Bias heavily toward compare drivers so cJSON_Compare gets exercised.
    r = draw(st.integers(min_value=0, max_value=9))
    if r < 6:
        return draw(_compare_driver())
    if r < 8:
        return draw(_compare_script())
    return draw(_top_level())


strategy = _top_level_with_compare_and_driver()