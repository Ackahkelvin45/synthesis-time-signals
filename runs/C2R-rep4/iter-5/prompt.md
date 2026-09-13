Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _safe_char():
    # printable ASCII excluding quote and backslash, plus some unicode
    return st.one_of(
        st.integers(min_value=0x20, max_value=0x7E).filter(
            lambda c: c not in (0x22, 0x5C)
        ).map(chr),
        st.sampled_from(["é", "ü", "€", "😀", "中", "ß"]),
    )

def _esc_char():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    hexs = "0123456789abcdefABCDEF"
    unicode_esc = st.text(alphabet=hexs, min_size=4, max_size=4).map(lambda h: "\\u" + h)
    surrogate = st.sampled_from(["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD834\\uDD1E"])
    return st.one_of(simple, unicode_esc, surrogate)

def _string_body():
    return st.one_of(
        st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
            lambda c: c not in ('"', '\\')), max_size=8),
        st.lists(st.one_of(_safe_char(), _esc_char()), max_size=8).map("".join),
    )

def _json_string():
    return _string_body().map(lambda s: '"' + s + '"')

def _unterminated_string():
    return _string_body().map(lambda s: '"' + s)

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**9).map(str),
        st.integers(min_value=1, max_value=10**18).map(str),
    )

def _number():
    sign = st.sampled_from(["", "-"])
    intp = _int_part()
    frac = st.one_of(
        st.just(""),
        st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    )
    exp = st.one_of(
        st.just(""),
        st.sampled_from(["e", "E"]).flatmap(
            lambda e: st.one_of(
                st.integers(min_value=-400, max_value=400).map(lambda x: e + str(x)),
                st.sampled_from(["+0", "-0", "01", "+309", "308", "-308"]).map(lambda x: e + x),
            )
        ),
    )
    return st.tuples(sign, intp, frac, exp).map(lambda t: "".join(t))

def _extreme_number():
    return st.sampled_from([
        "1e309", "-1e309", "1e-400", "1e400", "-1e999",
        "1.7976931348623157e309", "2.2250738585072014e-308",
        "1e000000000000000000000009", "0e0", "-0", "0.0", "-0.0",
        "123456789012345678901234567890",
        "1.0000000000000000000000000001e308",
        "9" * 40,
        "-" + "9" * 40,
    ])

# ---------- malformed number forms ----------

def _bad_number():
    return st.sampled_from([
        "+1", ".5", "1.", "01", "007", "0x1F", "-", "--1", "1e", "1e+",
        "1.2.3", "1..2", "e5", ".", "+", "-.", "1e999999999999999999999",
        "0b101", "0o17", "Infinity", "-Infinity", "NaN",
        "1_000", "1,5", "1 2", "٣", "１２３",
    ])

# ---------- malformed / near-valid fragments ----------

def _malformed_fragments():
    return st.sampled_from([
        ",", ",,", "[,]", "[,1]", "[1,,2]", "{,}", "{,}", "{\"a\":,}",
        "{:1}", "{\"a\" 1}", "{\"a\":1 \"b\":2}", "{\"a\"::1}",
        "[1 2]", "[1;2]", "{'a':1}", "{a:1}", "['a']",
        "tru", "fals", "nul", "True", "FALSE", "None",
        "//comment", "/*c*/", "//", "/*",
        "\"unterminated", "'single'", "\"bad\\escape\"",
        "\"\\u12\"", "\"\\uZZZZ\"", "\"\\x41\"",
        "]", "}", "[", "{", "[}", "{]",
        "1abc", "[]xyz", "1 garbage", "true false",
        "{\"a\":1,}", "[1,2,]", "{\"a\":1,,\"b\":2}",
        "{\"a\":1,}", "[1,2,]",
        "\x00", "\x01", "\x1f", "\x7f",
        "{\"a\":\x00}", "[1,\x00]",
        "{\"a\":\"\x00\"}",
        "{\"a\":\"\x01\x02\x03\"}",
        "\"a\x00b\"",
        "{\"a\":\"\\uD800\"}",
        "{ \"a\" : 1 , \"a\" : 2 }",
    ])

# ---------- whitespace ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t ", "\r\n"])

# ---------- recursive JSON structure ----------

def _json_value(depth):
    if depth <= 0:
        return st.one_of(
            _json_string(),
            _number(),
            _extreme_number(),
            st.sampled_from(["true", "false", "null"]),
        )
    return st.one_of(
        _json_string(),
        _number(),
        _extreme_number(),
        st.sampled_from(["true", "false", "null"]),
        _json_array(depth),
        _json_object(depth),
    )

def _json_array(depth):
    inner = st.lists(_json_value(depth - 1), min_size=0, max_size=4)
    def build(items):
        if not items:
            return "[]"
        return "[" + ",".join(items) + "]"
    return inner.map(build)

def _json_object(depth):
    pair = st.tuples(_json_string(), _ws, st.just(":"), _ws, _json_value(depth - 1)).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )
    pairs = st.lists(pair, min_size=0, max_size=4)
    def build(ps):
        if not ps:
            return "{}"
        return "{" + ",".join(ps) + "}"
    return pairs.map(build)

# ---------- deep nesting ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=200)
    opener = st.sampled_from(["[", "{"])
    closer = st.sampled_from(["]", "}"])
    def build(d):
        if d == 0:
            return "null"
        return opener.example() * d + closer.example() * d
    return depth.flatmap(lambda d: st.builds(
        lambda o, c: o * d + "null" + c * d,
        opener, closer,
    ))

# ---------- near-crash structural mutations ----------
# Bias toward the crashing shapes: lone "-", and lone-surrogate strings.
# Intensified: mutate structurally around the crashing inputs by wrapping
# crash seeds in deeper container stacks, mixing whitespace/separators,
# and combining the two crash families.

def _near_crash_mutations():
    # lone-minus seeds and structural mutations around them
    lone_minus = st.sampled_from([
        "-", "[-]", "[-,-]", "{-}", '{"-":-}', '{"a":-}',
        "[-,1]", "[1,-]", "[-]", "[- ]", "[ -]", "[-,-,-]",
        "[[-]]", '{"a":[-]}', '{"a":-,"b":-}', "[--1]", "[-0]",
        "[-e]", "[-.]", "[- ]", "-\n", "-\t", " - ", "\n-\n",
    ])

    # lone-surrogate / surrogate-pair seeds and structural mutations
    surrogate_seeds = st.sampled_from([
        '"\\uD800"', '"\\uDC00"', '"\\uDBFF"', '"\\uDFFF"',
        '"\\uD800\\uD800"', '"\\uDC00\\uDC00"',
        '"\\uD800\\uDC00"', '"\\uDBFF\\uDFFF"',
        '"\\uD834\\uDD1E"',
        '{"a":"\\uD800"}', '["\\uD800"]',
        '{"\\uD800":1}', '["\\uDC00"]',
        '{"a":"\\uD800\\uD800"}',
        '"\\uD800a"', '"a\\uD800"',
        '["\\uD800","\\uDC00"]',
        '{"a":"\\uDBFF","b":"\\uDFFF"}',
        '["\\uD800",1]', '[1,"\\uD800"]',
        '{"a":"\\uD800","b":1}',
        '"\\uD800\\uDC00\\uD800"',
    ])

    # bracket/brace framing around a lone minus
    def _framed_minus():
        prefix = st.sampled_from(["", "[", "{", "[[", "{{", '{"a":', '["'])
        suffix = st.sampled_from(["", "]", "}", "]]", "}}", '}', '"]'])
        return st.tuples(prefix, suffix).map(lambda t: t[0] + "-" + t[1])

    # bracket/brace framing around a lone surrogate escape
    def _framed_surrogate():
        prefix = st.sampled_from(["", "[", "{", "[[", "{{", '{"a":', '["'])
        suffix = st.sampled_from(["", "]", "}", "]]", "}}", '}', '"]'])
        esc = st.sampled_from([
            "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF",
            "\\uD834\\uDD1E", "\\uD800\\uD800",
        ])
        return st.tuples(prefix, esc, suffix).map(
            lambda t: t[0] + '"' + t[1] + '"' + t[2]
        )

    # intensified: wrap crash seeds inside deeper container stacks and
    # sprinkle whitespace / separators around them so the parser is
    # driven onto the same null-offset path via more structural shapes.
    def _deep_wrapped_minus():
        depth = st.integers(min_value=0, max_value=6)
        opener = st.sampled_from(["[", "{"])
        closer = st.sampled_from(["]", "}"])
        sep = st.sampled_from(["", ",", " ", ":", ',"a":', ",-"])
        return st.tuples(depth, opener, closer, sep).map(
            lambda t: t[1] * t[0] + t[3] + "-" + t[3] + t[2] * t[0]
        )

    def _minus_with_neighbors():
        left = st.sampled_from(["", "[", "{", "[1,", '{"a":', "[", "[[", '{"a":['])
        right = st.sampled_from(["", "]", "}", ",1]", ',"b":2}', "]", "]]", "]}"])
        mid = st.sampled_from([
            "-", "- ", " -", "-\n", "-\t", "-0", "-1", "-e", "-.",
            "-", "-", "-",  # weight toward bare minus
        ])
        return st.tuples(left, mid, right).map(lambda t: t[0] + t[1] + t[2])

    def _surrogate_with_neighbors():
        left = st.sampled_from(["", "[", "{", "[1,", '{"a":', "[", "[[", '{"a":['])
        right = st.sampled_from(["", "]", "}", ",1]", ',"b":2}', "]", "]]", "]}"])
        esc = st.sampled_from([
            "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF",
            "\\uD800\\uD800", "\\uD834\\uDD1E",
        ])
        return st.tuples(left, esc, right).map(
            lambda t: t[0] + '"' + t[1] + '"' + t[2]
        )

    def _minus_in_array_or_object():
        # build small containers whose sole member is a lone minus,
        # possibly with trailing commas / extra separators
        tail = st.sampled_from(["", ",", ",,", ", ", " ,"])
        return st.tuples(tail).map(lambda t: "[-" + t[0] + "]") | st.tuples(tail).map(
            lambda t: '{"a":-' + t[0] + "}"
        )

    # --- intensified structural mutation around crash seeds ---

    def _deep_wrapped_surrogate():
        depth = st.integers(min_value=0, max_value=6)
        opener = st.sampled_from(["[", "{"])
        closer = st.sampled_from(["]", "}"])
        sep = st.sampled_from(["", ",", " ", ":", ',"a":'])
        esc = st.sampled_from([
            "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF",
            "\\uD800\\uD800", "\\uD834\\uDD1E",
        ])
        return st.tuples(depth, opener, closer, sep, esc).map(
            lambda t: t[1] * t[0] + t[3] + '"' + t[4] + '"' + t[3] + t[2] * t[0]
        )

    def _combined_crash_seeds():
        # combine a lone minus and a lone surrogate in one document,
        # with assorted framing and separators
        left = st.sampled_from(["", "[", "{", "[1,", '{"a":', "[", "[[", '{"a":['])
        mid = st.sampled_from(["", ",", ", ", ":", ',"a":', "-", " ", "\n"])
        right = st.sampled_from(["", "]", "}", ",1]", ',"b":2}', "]", "]]", "]}"])
        esc = st.sampled_from([
            "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF",
            "\\uD800\\uD800", "\\uD834\\uDD1E",
        ])
        def build(t):
            l, m, e, r = t
            return l + "-" + m + '"' + e + '"' + r
        return st.tuples(left, mid, esc, right).map(build)

    def _nested_minus_stack():
        # stack of containers each containing a lone minus, with
        # separators between levels
        depth = st.integers(min_value=1, max_value=5)
        opener = st.sampled_from(["[", "{"])
        closer = st.sampled_from(["]", "}"])
        sep = st.sampled_from(["", ",", " ", ":", ',"a":'])
        def build(t):
            d, o, c, s = t
            parts = []
            for _ in range(d):
                parts.append(o)
            parts.append(s)
            parts.append("-")
            parts.append(s)
            for _ in range(d):
                parts.append(c)
            return "".join(parts)
        return st.tuples(depth, opener, closer, sep).map(build)

    def _minus_with_prefix_suffix():
        # arbitrary short prefix/suffix text around a lone minus
        pre = st.sampled_from([
            "", "[", "{", "[ ", "{ ", '{"a":', '["', "[1,", '{"a":[',
            "\n", "\t", " ", "[[", "{{", '{"a":{"b":',
        ])
        post = st.sampled_from([
            "", "]", "}", " ]", " }", '}', '"]', ",1]", ']}', "]]",
            "\n", "\t", " ", "]]", "}}", '}}}',
        ])
        return st.tuples(pre, post).map(lambda t: t[0] + "-" + t[1])

    def _surrogate_with_prefix_suffix():
        pre = st.sampled_from([
            "", "[", "{", "[ ", "{ ", '{"a":', '["', "[1,", '{"a":[',
            "\n", "\t", " ", "[[", "{{", '{"a":{"b":',
        ])
        post = st.sampled_from([
            "", "]", "}", " ]", " }", '}', '"]', ",1]", ']}', "]]",
            "\n", "\t", " ", "]]", "}}", '}}}',
        ])
        esc = st.sampled_from([
            "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF",
            "\\uD800\\uD800", "\\uD834\\uDD1E",
        ])
        return st.tuples(pre, esc, post).map(
            lambda t: t[0] + '"' + t[1] + '"' + t[2]
        )

    def _minus_in_object_value():
        # lone minus as object value with varying keys and tails
        key = st.sampled_from(['"a"', '"b"', '"x"', '""', '"\\uD800"'])
        tail = st.sampled_from(["", ",", ",,", ", ", " ,", ',"b":1'])
        return st.tuples(key, tail).map(lambda t: "{" + t[0] + ":-" + t[1] + "}")

    def _surrogate_in_object_key():
        key = st.sampled_from([
            "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF",
            "\\uD800\\uD800", "\\uD834\\uDD1E",
        ])
        tail = st.sampled_from(["", ",", ",,", ", ", " ,", ',"b":1'])
        return st.tuples(key, tail).map(lambda t: '{"' + t[0] + '":1' + t[1] + "}")

    def _minus_arrays_with_tails():
        tail = st.sampled_from(["", ",", ",,", ", ", " ,", ",1", ",-"])
        head = st.sampled_from(["", "1,", "-", "null,", '"a",'])
        return st.tuples(head, tail).map(lambda t: "[" + t[0] + "-" + t[1] + "]")

    def _surrogate_arrays_with_tails():
        head = st.sampled_from(["", "1,", "-", "null,", '"a",'])
        tail = st.sampled_from(["", ",", ",,", ", ", " ,", ",1", ",-"])
        esc = st.sampled_from([
            "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF",
            "\\uD800\\uD800", "\\uD834\\uDD1E",
        ])
        return st.tuples(head, esc, tail).map(
            lambda t: "[" + t[0] + '"' + t[1] + '"' + t[2] + "]"
        )

    return st.one_of(
        lone_minus,
        surrogate_seeds,
        _framed_minus(),
        _framed_surrogate(),
        _deep_wrapped_minus(),
        _minus_with_neighbors(),
        _surrogate_with_neighbors(),
        _minus_in_array_or_object(),
        _deep_wrapped_surrogate(),
        _combined_crash_seeds(),
        _nested_minus_stack(),
        _minus_with_prefix_suffix(),
        _surrogate_with_prefix_suffix(),
        _minus_in_object_value(),
        _surrogate_in_object_key(),
        _minus_arrays_with_tails(),
        _surrogate_arrays_with_tails(),
    )

# ---------- top-level strategy ----------

def _top_level():
    return st.one_of(
        # intensified near-crash mutations (primary focus)
        _near_crash_mutations(),
        # valid JSON values with whitespace
        st.tuples(_ws, _json_value(5), _ws).map(lambda t: t[0] + t[1] + t[2]),
        # bias toward objects with members
        st.tuples(_ws, _json_object(4), _ws).map(lambda t: t[0] + t[1] + t[2]),
        # empty containers
        st.sampled_from(["{}", "[]", " { } ", " [ ] ", "{}", "[]"]),
        # deep nesting
        _deep_nesting(),
        # extreme numbers
        st.tuples(_ws, _extreme_number(), _ws).map(lambda t: t[0] + t[1] + t[2]),
        # malformed numbers
        st.tuples(_ws, _bad_number(), _ws).map(lambda t: t[0] + t[1] + t[2]),
        # malformed fragments
        _malformed_fragments(),
        # duplicate keys
        st.sampled_from([
            '{"a":1,"a":2}',
            '{"a":1,"a":2,"a":3}',
            '{"x":{"a":1},"x":{"a":2}}',
            '{"a":1,"b":2,"a":3,"b":4}',
        ]),
        # trailing commas
        st.sampled_from([
            "[1,2,]", "[1,]", '{"a":1,}', '{"a":1,"b":2,}',
            "[1,2,3,]", '{"a":1,}',
        ]),
        # non-finite / overflow
        st.sampled_from([
            "1e309", "-1e309", "1e308", "1e-308",
            '{"a":1e309}', "[1e309]",
            "1e999999999999999999999",
        ]),
        # lone dash
        st.sampled_from(["-", "[-]", '{"a":-}', "[-,-]"]),
        # unicode escapes
        st.sampled_from([
            '"\\u0041"', '"\\uD834\\uDD1E"', '"\\uD800"', '"\\uDC00"',
            '"\\u0000"', '"\\uFFFF"', '"\\uD800\\uD800"',
            '{"\\u0041":1}', '["\\uD834\\uDD1E"]',
        ]),
        # embedded NUL and control bytes
        st.sampled_from([
            "\x00", "{\x00}", "[\x00]", '"a\x00b"', '{"a":1}\x00',
            "\x00{}", "{\"a\":\x00}", "[\x00,1]",
            "\x01\x02\x03", "{\"a\":\"\x01\"}",
        ]),
        # near-valid malformed
        st.sampled_from([
            "{\"a\":1,,}", "[1,,2]", "[,]", "[,1]",
            "{\"a\":}", "{:1}", "{\"a\" 1}",
            "\"unterminated", "'single'", "tru", "nul",
            "+1", ".5", "01", "1.", "--1",
            "[]extra", "1abc", "true false",
            "{\"a\":1}extra",
        ]),
    )

strategy = _top_level()
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 11,
    "reject": 4,
    "crash": 8
  },
  "acceptance_rate": 0.478,
  "max_nesting_depth": 4,
  "productions_accepted": [
    "NUMBER",
    "arr",
    "json",
    "null",
    "obj",
    "value"
  ],
  "productions_gap": [
    "pair",
    "STRING",
    "true",
    "false"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 4,
  "divergences": 7,
  "divergence_examples": [
    "b'-'",
    "b'1e309'",
    "b'1e999999999999999999999'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.