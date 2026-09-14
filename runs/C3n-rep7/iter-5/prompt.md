Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

# Characters that are safe inside a JSON string per the grammar (excluding
# quote, backslash, and control chars which need escaping).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

# Raw control bytes / NUL that the parser handles faithfully via explicit length.
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x0d", "\x1f", "\x7f"]
)

# Escapes allowed by the grammar.
_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_unicode_esc = st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map("".join)

# Surrogate escapes (lone high/low and paired) — classic crash source.
_surrogate_esc = st.tuples(
    st.just("\\u"),
    st.sampled_from("dD"),
    st.sampled_from("89abAB"),
    _hex,
    _hex,
).map("".join)


@st.composite
def _string_body(draw, allow_raw_control=True):
    """Generate the inner content of a JSON string (no surrounding quotes)."""
    parts = []
    n = draw(st.integers(min_value=0, max_value=8))
    for _ in range(n):
        choice = draw(st.integers(min_value=0, max_value=5))
        if choice == 0:
            parts.append(draw(_safe_chars))
        elif choice == 1:
            parts.append(draw(_simple_esc))
        elif choice == 2:
            parts.append(draw(_unicode_esc))
        elif choice == 3:
            parts.append(draw(_surrogate_esc))
        elif choice == 4 and allow_raw_control:
            parts.append(draw(_raw_control))
        else:
            parts.append(draw(_safe_chars))
    return "".join(parts)


@st.composite
def _json_string(draw, allow_raw_control=True):
    body = draw(_string_body(allow_raw_control=allow_raw_control))
    return '"' + body + '"'


# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=0, max_value=10**18).map(str).filter(lambda s: not s.startswith("0") or s == "0"),
    st.integers(min_value=1, max_value=10**6).map(str),
)

_frac_part = st.tuples(st.just("."), st.integers(min_value=0, max_value=10**12).map(str)).map("".join)

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10**4).map(str),
).map("".join)

# Extreme exponent magnitudes including overflow like 1e309.
_extreme_exp = st.sampled_from(
    ["e309", "e308", "e-309", "e-324", "E400", "e+999", "e-999", "e0", "e01", "E+00"]
)


@st.composite
def _json_number(draw):
    sign = draw(st.sampled_from(["", "-"]))
    intp = draw(_int_part)
    has_frac = draw(st.booleans())
    has_exp = draw(st.booleans())
    use_extreme = draw(st.booleans())
    s = sign + intp
    if has_frac:
        s += draw(_frac_part)
    if use_extreme:
        s += draw(_extreme_exp)
    elif has_exp:
        s += draw(_exp_part)
    return s


# ---------- malformed number forms (still valuable edge inputs) ----------

_bad_number = st.sampled_from(
    [
        "+1", "+0", ".5", "1.", "01", "00", "007", "0x1F", "0X1f",
        "-", "--1", "1e", "1e+", "1E-", "1..2", "1.2.3", "1e1e1",
        "0b101", "Infinity", "-Infinity", "NaN", "1_000", "1,5",
        "1e309", "-1e309", "1e-999",
    ]
)


# ---------- malformed string forms ----------

_bad_string = st.sampled_from(
    [
        '"unterminated',
        '"unterminated\\"',
        '"bad\\x escape"',
        '"\\u12"',
        '"\\uZZZZ"',
        '"\\uD800"',
        '"\\uDC00"',
        '"\\uD800\\uD800"',
        "'single quoted'",
        '"trailing\\',
        '"\\"',
        '"\\u0000"',
        '"\\uD83D\\uDE00"',
    ]
)


# ---------- recursive value strategy ----------

_true = st.just("true")
_false = st.just("false")
_null = st.just("null")

# whitespace padding (grammar skips WS)
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n", "\t\r\n"])


@st.composite
def _pair(draw, value_strategy):
    key = draw(_json_string(allow_raw_control=True))
    ws1 = draw(_ws)
    ws2 = draw(_ws)
    val = draw(value_strategy)
    # Occasionally omit the colon (malformed) or use a bad key.
    if draw(st.integers(min_value=0, max_value=19)) == 0:
        return key + ws1 + ws2 + val  # missing colon
    return key + ws1 + ":" + ws2 + val


@st.composite
def _obj(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=6))
    if n == 0:
        # empty object, sometimes with whitespace
        return "{" + draw(_ws) + "}"
    pairs = [draw(_pair(value_strategy)) for _ in range(n)]
    sep = draw(st.sampled_from([",", ",", ", ", ",\n", ",\t"]))
    body = sep.join(pairs)
    # single trailing comma occasionally
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        body += ","
    # double comma occasionally (malformed)
    if draw(st.integers(min_value=0, max_value=19)) == 0:
        body = body.replace(",", ",,", 1)
    return "{" + draw(_ws) + body + draw(_ws) + "}"


@st.composite
def _arr(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=6))
    if n == 0:
        return "[" + draw(_ws) + "]"
    vals = [draw(value_strategy) for _ in range(n)]
    sep = draw(st.sampled_from([",", ",", ", ", ",\n", ",\t"]))
    body = sep.join(vals)
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        body += ","
    if draw(st.integers(min_value=0, max_value=19)) == 0:
        body = body.replace(",", ",,", 1)
    return "[" + draw(_ws) + body + draw(_ws) + "]"


_value = st.deferred(lambda: _value_impl)

_value_impl = st.one_of(
    _json_string(allow_raw_control=True),
    _json_number(),
    _bad_number,
    _bad_string,
    _true,
    _false,
    _null,
    _obj(_value),
    _arr(_value),
)

# Deep nesting: bias toward objects with members (stressed first-pass path).
_recursive_value = st.recursive(
    st.one_of(
        _json_string(allow_raw_control=True),
        _json_number(),
        _bad_number,
        _bad_string,
        _true,
        _false,
        _null,
    ),
    lambda children: st.one_of(
        _obj(children),
        _arr(children),
    ),
    max_leaves=40,
)


@st.composite
def _deep_nesting(draw):
    """Generate deliberately deep object/array nesting."""
    depth = draw(st.integers(min_value=1, max_value=64))
    kind = draw(st.sampled_from(["obj", "arr", "mixed"]))
    s = ""
    for i in range(depth):
        if kind == "obj":
            s += '{"a":'
        elif kind == "arr":
            s += "["
        else:
            s += '{"k":[' if i % 2 == 0 else '{"k":'
    s += draw(st.one_of(_json_string(), _json_number(), _true, _null))
    for i in range(depth):
        if kind == "obj":
            s += "}"
        elif kind == "arr":
            s += "]"
        else:
            s += "]}" if (depth - 1 - i) % 2 == 0 else "}"
    return s


# ---------- top-level malformed / near-valid inputs ----------

_malformed_top = st.sampled_from(
    [
        "",
        " ",
        "\x00",
        "\x00\x00",
        "{",
        "}",
        "[",
        "]",
        "{,}",
        "[,]",
        "[,,]",
        "[,1]",
        "[1,,2]",
        '{"a"}',
        '{"a":}',
        '{:1}',
        '{"a":1,,"b":2}',
        "1abc",
        "[]xyz",
        "1 garbage",
        "true false",
        "tru",
        "nul",
        "fals",
        "//comment\n1",
        "/* comment */1",
        "{a:1}",
        "'x'",
        "1 2",
        "{} {}",
        "[] []",
        "1,",
        ",1",
        "{\"a\":1}{\"b\":2}",
        "\xef\xbb\xbf{}",
        "{\"a\":\x00}",
        "[\x00]",
        "\"a\x00b\"",
    ]
)


@st.composite
def _duplicate_keys(draw):
    """Objects with duplicate keys (parser accepts these)."""
    n = draw(st.integers(min_value=2, max_value=5))
    key = draw(_json_string())
    pairs = [key + ":" + draw(st.one_of(_json_number(), _json_string(), _true, _null)) for _ in range(n)]
    return "{" + ",".join(pairs) + "}"


# ---------- near-crash mutation ----------

# Seeds representing structurally "crashy" shapes. The mutation below perturbs
# these around the exact structure that triggered a crash so the parser is
# driven through the same code path with slight variations.
_crash_seeds = st.sampled_from(
    [
        '{"a":',
        '{"a":[',
        '{"a":{"b":',
        '[',
        '[[',
        '{"k":[[',
        '{"a":1,"b":',
        '{"a":1,"a":',
        '{"":',
        '{"a":"',
        '{"a":"\\uD800',
        '{"a":"\\uD800\\uD800',
        '{"a":1e309',
        '{"a":-',
        '[{"a":',
        '{"a":[{"b":',
        '"\\uD800',
        '{"a":"\\',
        '{"a":\x00',
        '[1,\x00',
        '{"a":1e',
        '{"a":00',
        '{"a":1.',
        '{"a":.5',
    ]
)

# Structural fragments used to splice around a seed.
_open_frag = st.sampled_from(['{"a":', '{"k":', '{"":', '[', '[[', '{"a":[', '[{', '{"a":{"b":'])
_close_frag = st.sampled_from(["}", "]", "]}", "}]", "}}", "]]"])
_gap_frag = st.sampled_from(
    ["", " ", "\t", "\n", ",", ":", ",\x00", "\x00", ",", ",\n", ":", "  "]
)
_leaf_frag = st.sampled_from(
    [
        "",
        "1",
        "0",
        "-1",
        "1e309",
        "1e-999",
        "true",
        "false",
        "null",
        '"a"',
        '"\\uD800"',
        '"\\uDC00"',
        '"\\uD800\\uD800"',
        '"\\',
        "\x00",
        "01",
        "1.",
        ".5",
        "NaN",
        "Infinity",
    ]
)


@st.composite
def _near_crash(draw):
    """Mutate structurally around a crashing input.

    Take a crash-shaped seed and apply a larger number of structural mutations
    (splices, gaps, duplications, truncations) while repeatedly re-applying the
    most crash-relevant operations (dangling opens, NUL injection, lone
    surrogate escapes, unterminated strings). The goal is to keep the parser on
    the same near-crash code path while aggressively varying the surrounding
    structure.
    """
    seed = draw(_crash_seeds)
    s = seed

    n_mut = draw(st.integers(min_value=1, max_value=48))
    for _ in range(n_mut):
        op = draw(st.integers(min_value=0, max_value=15))
        if op == 0:
            # prepend an opening fragment
            s = draw(_open_frag) + s
        elif op == 1:
            # append a closing fragment
            s = s + draw(_close_frag)
        elif op == 2:
            # insert a gap/separator at a random position
            pos = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:pos] + draw(_gap_frag) + s[pos:]
        elif op == 3:
            # append a leaf value
            s = s + draw(_leaf_frag)
        elif op == 4:
            # prepend a leaf value
            s = draw(_leaf_frag) + s
        elif op == 5:
            # truncate at a random boundary
            if len(s) > 1:
                pos = draw(st.integers(min_value=1, max_value=len(s)))
                s = s[:pos]
        elif op == 6:
            # duplicate a contiguous slice
            if len(s) >= 2:
                a = draw(st.integers(min_value=0, max_value=len(s) - 1))
                b = draw(st.integers(min_value=a, max_value=len(s)))
                s = s[:b] + s[a:b] + s[b:]
        elif op == 7:
            # nest the whole thing inside a fresh container
            s = draw(_open_frag) + s + draw(_close_frag)
        elif op == 8:
            # inject a raw NUL byte at a random position (classic crash source)
            pos = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:pos] + "\x00" + s[pos:]
        elif op == 9:
            # append a dangling opening fragment to force unterminated parse
            s = s + draw(_open_frag)
        elif op == 10:
            # splice in a lone surrogate escape inside a string context
            s = s + draw(st.sampled_from(['"\\uD800', '"\\uDC00', '"\\uD800\\uD800', '"\\']))
        elif op == 11:
            # drop a closing bracket to leave structure unbalanced
            for _ in range(draw(st.integers(min_value=1, max_value=3))):
                idx = s.rfind("}")
                jdx = s.rfind("]")
                k = max(idx, jdx)
                if k >= 0:
                    s = s[:k] + s[k + 1:]
                else:
                    break
        elif op == 12:
            # wrap the current buffer in a dangling object key
            s = '{"a":' + s
        elif op == 13:
            # inject a dangling colon followed by an open container
            pos = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:pos] + draw(st.sampled_from([":", ":[", ":{", ":", ":["])) + s[pos:]
        elif op == 14:
            # inject an unterminated string opener
            pos = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:pos] + '"' + s[pos:]
        else:
            # inject a raw control byte / invalid escape sequence
            pos = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:pos] + draw(st.sampled_from(["\x01", "\x1f", "\\x", "\\u", "\\uD8", "\x7f"])) + s[pos:]

    # Frequently append a dangling opening fragment to force an unterminated
    # parse path (the classic crash shape).
    if draw(st.integers(min_value=0, max_value=1)) == 0:
        s = s + draw(_open_frag)

    # Frequently inject a NUL near the end to hit length-handling paths.
    if draw(st.integers(min_value=0, max_value=2)) == 0:
        s = s + "\x00"

    return s


@st.composite
def _top_value(draw):
    # Bias toward objects with members.
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice <= 3:
        return draw(_obj(_recursive_value))
    elif choice <= 5:
        return draw(_recursive_value)
    elif choice == 6:
        return draw(_deep_nesting())
    elif choice == 7:
        return draw(_duplicate_keys())
    elif choice == 8:
        return draw(_malformed_top)
    else:
        # raw bytes / control-heavy content
        return draw(_json_string(allow_raw_control=True))


strategy = st.one_of(_near_crash(), _top_value())
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 32.91,
  "region_coverage_pct": 33.71,
  "least_covered_functions": [
    "would_overflow (0% of branches)",
    "json_parse (0% of branches)",
    "json_parse_ex (29% of branches)",
    "json_alloc (33% of branches)",
    "new_value (46% of branches)"
  ]
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.