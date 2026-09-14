from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic scalar productions
# ---------------------------------------------------------------------------

SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\",
)

# Escapes that appear inside JSON strings (the six-char \u0000 form is fine).
_escapes = st.sampled_from(
    [
        '\\"',
        "\\\\",
        "\\/",
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
        "\\u0000",
        "\\u001f",
        "\\u007f",
        "\\u00e9",
        "\\u20ac",
        "\\ud800",
        "\\udfff",
        "\\ud83d\\ude00",
        "\\uD834\\uDD1E",
        "\\uFFFF",
        "\\u000a",
        "\\u000d",
    ]
)

_string_body = st.one_of(
    st.text(alphabet=SAFE_CHARS, min_size=0, max_size=12),
    st.lists(st.one_of(st.text(alphabet=SAFE_CHARS, max_size=6), _escapes), max_size=6).map(
        "".join
    ),
)

_json_string = _string_body.map(lambda s: '"' + s + '"')

# ---------------------------------------------------------------------------
# Numbers: normal, extreme, and malformed-ish (still grammar-shaped)
# ---------------------------------------------------------------------------

_plain_int = st.integers(min_value=0, max_value=10**18).map(str)

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.sampled_from(
        [
            "1",
            "9",
            "10",
            "12345678901234567890",
            "999999999999999999999999999999",
        ]
    ),
)

_frac = st.one_of(
    st.nothing(),
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n).zfill(1)),
    st.sampled_from([".0", ".5", ".000", ".999999999", "." + "9" * 40]),
)

_exp = st.one_of(
    st.nothing(),
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.sampled_from(
        [
            "e0",
            "E0",
            "e+0",
            "e-0",
            "e01",
            "e+308",
            "e-308",
            "e309",
            "e310",
            "e-400",
            "e+999",
            "E+99999999999999999999",
            "e-99999999999999999999",
        ]
    ),
)

_sign = st.one_of(st.nothing(), st.just("-"))

_json_number = st.builds(
    lambda s, i, f, e: s + i + f + e,
    _sign,
    _int_part,
    _frac,
    _exp,
)

# A few "lenient but grammar-adjacent" numeric forms the parser is known/expected
# to be permissive about. These are deliberately outside strict JSON NUMBER.
_weird_number = st.sampled_from(
    [
        "-",
        "-.",
        "-.0",
        ".5",
        "1.",
        "+1",
        "+0",
        "01",
        "00",
        "1e",
        "1e+",
        "1e-",
        "1.e5",
        "-01",
        "0x10",
        "Infinity",
        "-Infinity",
        "NaN",
    ]
)

number_value = st.one_of(_json_number, _weird_number)

# ---------------------------------------------------------------------------
# Recursive structure: obj / arr / value
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser's MAX_NESTING = 2048.
# st.recursive keeps things bounded; we also add explicit deep-nesting cases.
_base_value = st.one_of(
    _json_string,
    number_value,
    st.sampled_from(["true", "false", "null"]),
)

# Object keys: mix of ordinary, empty, duplicate-prone, and escape-laden keys.
_key = st.one_of(
    _json_string,
    st.sampled_from(
        [
            '""',
            '"k"',
            '"a"',
            '"\\u0000"',
            '"\\ud800"',
            '"\\n"',
            '"\\""',
            '"\\\\"',
        ]
    ),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n\t "])

_pair = st.builds(
    lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
    _key,
    _ws,
    _ws,
    _base_value,
)

# Malformed pair fragments: missing colon, empty key, bare tokens.
_bad_pair = st.sampled_from(
    [
        '"a" 1',
        '"a":',
        ':1',
        '""',
        '"a" "b"',
        '"a":,',
        '"a"::1',
        '1:2',
    ]
)


def _join(parts):
    return "".join(parts)


def _obj(inner):
    """Object built from inner value strategy."""
    pair = st.builds(
        lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
        _key,
        _ws,
        _ws,
        inner,
    )
    member = st.one_of(pair, _bad_pair)
    members = st.lists(member, min_size=0, max_size=5).map(lambda xs: (",".join(xs)))
    return st.builds(
        lambda w1, body, w2: "{" + w1 + body + w2 + "}",
        _ws,
        members,
        _ws,
    )


def _arr(inner):
    elems = st.lists(inner, min_size=0, max_size=5).map(lambda xs: ",".join(xs))
    return st.builds(
        lambda w1, body, w2: "[" + w1 + body + w2 + "]",
        _ws,
        elems,
        _ws,
    )


# ---------------------------------------------------------------------------
# Deep nesting near the cap (2048). Builders that produce exactly-N-depth input.
# ---------------------------------------------------------------------------

def _deep_array(depth, leaf):
    return "[" * depth + leaf + "]" * depth


def _deep_object(depth, leaf):
    return '{"a":' * depth + leaf + "}" * depth


def _deep_mixed(depth, leaf):
    # Alternate array/object nesting.
    openers = []
    closers = []
    for i in range(depth):
        if i % 2 == 0:
            openers.append("[")
            closers.append("]")
        else:
            openers.append('{"a":')
            closers.append("}")
    return "".join(openers) + leaf + "".join(reversed(closers))


_depth = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=2000, max_value=2052),
    st.sampled_from([1, 2, 100, 1024, 2046, 2047, 2048, 2049, 2050, 4096, 100000]),
)

_deep_leaf = st.one_of(
    st.sampled_from(["0", "1", "null", "true", "false", '"x"', ""]),
)

deep_value = st.one_of(
    st.builds(_deep_array, _depth, _deep_leaf),
    st.builds(_deep_object, _depth, _deep_leaf),
    st.builds(_deep_mixed, _depth, _deep_leaf),
)

# ---------------------------------------------------------------------------
# Recursive value via st.recursive
# ---------------------------------------------------------------------------

_recursive_value = st.recursive(
    _base_value,
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=20,
)

value = st.one_of(_recursive_value, deep_value)

# ---------------------------------------------------------------------------
# Malformed / near-valid top-level inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "",
        " ",
        "{",
        "}",
        "[",
        "]",
        "[,]",
        "[1,]",
        "[,1]",
        "[1,,2]",
        "{,}",
        '{"a":1,}',
        '{"a":1,,"b":2}',
        '{"a" 1}',
        '{"a":}',
        '{"a":1 "b":2}',
        '{"a":1,}',
        '"unterminated',
        '"unterminated\\',
        '"\\u12"',
        '"\\uZZZZ"',
        '"\\x41"',
        "'single'",
        "tru",
        "truE",
        "NULL",
        "nul",
        "undefined",
        "1abc",
        "[]xyz",
        "{}trailing",
        '{"a":1}garbage',
        "[1,2,3] extra",
        "/* comment */ 1",
        "// line\n1",
        "\x01",
        "\x1f",
        "\x7f",
        "\u00e9",
        "\u2028",
        "\ufeff{}",
        "{\"a\":1,\"a\":2}",
        '{"a":1,"a":1}',
        '{"a":1,"b":2,"a":3}',
        "1e309",
        "-1e309",
        "1e999999999",
        "[1e309]",
        '{"x":1e309}',
        "9007199254740993",
        "123456789012345678901234567890",
        "-",
        "-.",
        "+1",
        ".5",
        "01",
        "1.",
    ]
)

# ---------------------------------------------------------------------------
# Top-level strategy: complete values (with optional trailing junk / ws),
# deep nesting, and malformed inputs.
# ---------------------------------------------------------------------------

_trailing = st.one_of(
    st.nothing(),
    st.sampled_from(["", " ", "\n", "garbage", "abc", "]", "}", ",", "1", "null"]),
)

complete = st.builds(
    lambda w1, v, w2, t: w1 + v + w2 + t,
    _ws,
    value,
    _ws,
    _trailing,
)

# ---------------------------------------------------------------------------
# NEW: targeted inputs to reach parser branches not covered before.
# These exercise error-recovery paths, unusual escapes, control chars in
# strings, BOM/whitespace handling, and edge numeric/structural forms.
# ---------------------------------------------------------------------------

_branch_targeted = st.sampled_from(
    [
        # Strings containing raw control characters (parser must reject/handle).
        '"\x01"',
        '"\x1f"',
        '"\x7f"',
        '"a\x00b"',
        '"a\tb"',
        '"a\nb"',
        '"a\rb"',
        # Unicode escape edge cases: surrogate handling, lone low surrogate.
        '"\\udc00"',
        '"\\ud83d"',
        '"\\uD83D\\uDE00"',
        '"\\u0000\\u0000"',
        '"\\uD800\\uD800"',
        '"\\uDBFF\\uDFFF"',
        '"\\u"',
        '"\\u0"',
        '"\\u00"',
        '"\\u000"',
        '"\\uD83Dx"',
        # Invalid / partial escapes.
        '"\\"',
        '"\\q"',
        '"\\/"',
        '"\\b\\f\\n\\r\\t"',
        # BOM and unusual whitespace at top level and inside structures.
        "\ufeff1",
        "\ufeff{}",
        "\u00a0 1",
        "\u20281",
        "\u20291",
        "[\u00a01]",
        '{"a"\u00a0:1}',
        "{\u2028\"a\":1}",
        # Whitespace-only variants covering more WS code points.
        "\u000b",
        "\u000c",
        "\u0085",
        # Numbers: leading zeros, plus signs, exponents without digits.
        "00.1",
        "0.0e",
        "0e",
        "0e+",
        "0e-",
        "-0",
        "-0.0",
        "1E10",
        "1E+10",
        "1E-10",
        "1e00000000000000000000000000000000000000000",
        "1E-00000000000000000000000000000000000000000",
        # Deeply nested but unbalanced closers/openers to hit depth-limit branches.
        "[" * 2049 + "]" * 2048,
        "[" * 2048 + "]" * 2049,
        "{" * 2049 + "}" * 2048,
        '{"a":' * 2049 + "0" + "}" * 2048,
        # Mixed bracket mismatches.
        "[}",
        "{]",
        "[{)",
        "([)]",
        "[[]",
        "[]]",
        "{{}}",
        "}{",
        # Trailing content after valid value in nested contexts.
        "[1,2,3",
        '{"a":1',
        '[1 2]',
        '{"a":1 "b":2}',
        # Empty and whitespace-only containers with varied whitespace.
        "[ ]",
        "{ }",
        "[ \t\n\r ]",
        "{ \t\n\r }",
        # Multiple top-level values.
        "1 2",
        "true false",
        "null null",
        "{} {}",
        "[] []",
        # Comments in various positions.
        "[/* c */1]",
        '{"a"/* c */:1}',
        '{"a":/* c */1}',
        '{"a":1/* c */}',
        "// c\n[1]",
        "/* c */[]",
        # Strings with high-bit bytes / non-ASCII.
        '"\u00ff"',
        '"\u0100"',
        '"\U0001f600"',
        '"\uffff"',
        # Nested structures with trailing commas and empty members.
        "[,]",
        "[1,]",
        "[,]",
        "{,}",
        '{"a":,}',
        '{"a":1,,"b":2}',
        # Null/true/false partials and case variants.
        "t",
        "tr",
        "tru",
        "f",
        "fa",
        "fal",
        "fals",
        "n",
        "nu",
        "nul",
        "TRUE",
        "False",
        "NULL",
        # Number followed by junk.
        "1x",
        "1.2.3",
        "1e1e1",
        "-+1",
        "--1",
        "++1",
        # Object with non-string key.
        "{1:2}",
        "{true:1}",
        "{null:1}",
        "{[1]:2}",
        "{{}:1}",
        # Array with weird separators.
        "[1;2]",
        "[1:2]",
        "[1|2]",
        # Very long string (stress buffer growth).
        '"' + "a" * 5000 + '"',
        '"' + "\\n" * 1000 + '"',
        # Long key.
        '{"' + "k" * 5000 + '":1}',
        # Lone backslash at end of input.
        "\\",
        '"\\',
        # Single quote inside string.
        "\"it's\"",
        # Tab/newline inside string (raw).
        '"a\tb"',
        '"a\nb"',
        '"a\rb"',
    ]
)

# ---------------------------------------------------------------------------
# NEW: additional branch-targeted inputs to lift branch coverage.
# Focus on parser paths not yet exercised: whitespace between every token,
# deeply-nested-but-not-at-cap structures, nested error-recovery, escaped
# surrogate pairs split across buffers, exponent boundary digits, and
# incremental-parser boundary conditions.
# ---------------------------------------------------------------------------

_branch_targeted2 = st.sampled_from(
    [
        # Whitespace interleaved between all structural tokens.
        "[ 1 , 2 , 3 ]",
        "{ \"a\" : 1 , \"b\" : 2 }",
        "[\n1\n,\n2\n]",
        "{\r\n\"a\"\r\n:\r\n1\r\n}",
        "[\t1\t,\t2\t]",
        # Whitespace before closing bracket after trailing comma.
        "[1, ]",
        '{"a":1, }',
        "[1 ,]",
        '{"a":1 ,}',
        # Nested containers with inner malformed content.
        "[{,}]",
        "[{\"a\":}]",
        "[[[]",
        "{{{{",
        "]]]]",
        "}}}}",
        # Deeply nested valid structures just below the cap.
        "[" * 2046 + "]" * 2046,
        '{"a":' * 2046 + "0" + "}" * 2046,
        # Deeply nested with malformed leaf.
        "[" * 2048 + "x" + "]" * 2048,
        '{"a":' * 2048 + "x" + "}" * 2048,
        # Surrogate pair split forms.
        '"\\ud83d\\ude00"',
        '"\\ud83d\\ude01"',
        '"\\udbff\\udfff"',
        '"\\ud800\\udc00"',
        # Escape at very end of string.
        '"abc\\n"',
        '"abc\\u0041"',
        '"abc\\\\"',
        # Strings with embedded null via escape and raw.
        '"\\u0000abc"',
        '"abc\\u0000"',
        # Number boundary: just at int/float exponent limits.
        "1e308",
        "1e-308",
        "1e309",
        "-1e308",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "5e-324",
        "1.7976931348623159e308",
        # Leading zero variants.
        "0.1",
        "0e1",
        "0E1",
        "0.0e0",
        "-0e0",
        "-0.0e-0",
        # Plus sign in exponent variants.
        "1e+1",
        "1e-1",
        "1E+1",
        "1E-1",
        # Empty object/array with whitespace variants.
        "{\t}",
        "[\t]",
        "{\n}",
        "[\n]",
        "{\r}",
        "[\r]",
        # Multiple trailing commas.
        "[1,,]",
        "[,,]",
        '{"a":1,,}',
        # Colon-only / comma-only fragments.
        ":",
        ",",
        ":::",
        ",,,",
        # Bracket-only fragments.
        "[]",
        "{}",
        "[{}]",
        "{[ ]}",
        "[[]]",
        "{{}}",
        # Whitespace + bracket fragments.
        " [ ] ",
        " { } ",
        "\t[\n]\r",
        # Partial keywords at various truncation points.
        "tru",
        "fals",
        "nul",
        "truex",
        "falsey",
        "nullz",
        # Numbers with trailing whitespace inside containers.
        "[1 ]",
        "[ 1]",
        "{ \"a\" : 1 }",
        # Nested arrays with mixed valid/invalid.
        "[[1],[2]]",
        "[[1],2]",
        "[1,[2]]",
        "[{},[]]",
        # Objects with nested values.
        '{"a":{}}',
        '{"a":[]}',
        '{"a":{"b":{}}}',
        '{"a":[{"b":1}]}',
    ]
)

# ---------------------------------------------------------------------------
# NEW (branch coverage): token-boundary and state-machine-edge inputs.
# The previous strategy exercised mostly whole-value shapes; these target
# the lexer/parser state transitions: whitespace/EOF right after each token
# class, every keyword truncated at each prefix length, numbers ending in
# every possible trailing char, strings ending at every escape prefix, and
# structural tokens at exact cap boundaries with mismatched closers.
# ---------------------------------------------------------------------------

_keyword_prefixes = [
    p
    for kw in ("true", "false", "null")
    for p in (kw[:i] for i in range(len(kw) + 1))
]

_number_tails = st.sampled_from(
    [
        "0a", "0.", "0e", "0E", "0e+", "0e-", "0x", "0b", "0o",
        "1a", "1.", "1e", "1E", "1e+", "1e-", "1_", "1$", "1%",
        "-0a", "-0.", "-1e", "-1e+", "-1e-",
        "1e+1a", "1e-1a", "1.0.0", "1..2", "1.2e", "1.2e+", "1.2e-",
        "0.", "00.", "000", "0.0.0",
        "1e999999999999999999999999999999999999",
        "-1e-999999999999999999999999999999999999",
    ]
)

_string_tails = st.sampled_from(
    [
        '"\\', '"\\u', '"\\u0', '"\\u00', '"\\u000',
        '"\\uD', '"\\uD8', '"\\uD80', '"\\uD800',
        '"\\uDC', '"\\uDC0', '"\\uDC00',
        '"\\', '"\\x', '"\\U', '"\\N',
        '"a\\', '"ab\\', '"abc\\',
        '"', '"\x00', '"\x01', '"\x1f', '"\x7f',
    ]
)

_state_edge = st.sampled_from(
    [
        # Every keyword prefix as a top-level token.
        *[" " + p for p in _keyword_prefixes],
        # Keyword prefix immediately followed by structural chars.
        *[p + "]" for p in _keyword_prefixes],
        *[p + "}" for p in _keyword_prefixes],
        *[p + "," for p in _keyword_prefixes],
        *[p + ":" for p in _keyword_prefixes],
        # Keyword prefix inside a container.
        *["[" + p + "]" for p in _keyword_prefixes],
        *['{"a":' + p + "}" for p in _keyword_prefixes],
        # Whitespace/EOF right after opening/closing tokens.
        "[ ", "[\t", "[\n", "[\r", "[\r\n",
        "{ ", "{\t", "{\n", "{\r", "{\r\n",
        "[1", "[1 ", "[1\t", "[1\n", "[1\r",
        '{"a":1', '{"a":1 ', '{"a":1\t', '{"a":1\n', '{"a":1\r',
        '{"a"', '{"a" ', '{"a"\t', '{"a"\n', '{"a"\r',
        '{"a":', '{"a": ', '{"a":\t', '{"a":\n', '{"a":\r',
        # Comma/colon with trailing whitespace/EOF.
        "[1,", "[1, ", "[1,\t", "[1,\n", "[1,\r",
        '{"a":1,', '{"a":1, ', '{"a":1,\t', '{"a":1,\n', '{"a":1,\r',
        '{"a":,', '{"a":, ', '{"a":,\t',
        # Nested closers with mismatched opening at exact depths.
        "[" * 2047 + "}" * 2047,
        "{" * 2047 + "]" * 2047,
        "[" * 2048 + "}" * 2048,
        "{" * 2048 + "]" * 2048,
        "[" * 2049 + "}" * 2049,
        "{" * 2049 + "]" * 2049,
        # Depth cap: exactly at cap with each closer type.
        "[" * 2048 + "]" * 2047,
        "[" * 2047 + "]" * 2048,
        '{"a":' * 2048 + "}" * 2047,
        '{"a":' * 2047 + "}" * 2048,
        # Depth cap exceeded by one with valid closure.
        "[" * 2049 + "]" * 2049,
        '{"a":' * 2049 + "0" + "}" * 2049,
        # Mixed nesting at cap boundary.
        "[" * 1024 + '{"a":' * 1024 + "0" + "}" * 1024 + "]" * 1024,
        "[" * 1025 + '{"a":' * 1024 + "0" + "}" * 1024 + "]" * 1024,
        # Empty key/value at token boundaries.
        '{"":1}', '{"":"",}', '{""}', '{"":}', '{"":,}',
        # Whitespace-only between every pair of structural tokens.
        "[  1  ]", "[  1  ,  2  ]", '{  "a"  :  1  }',
        # Tab/newline/CR combinations around tokens.
        "[\t1\t,\t2\t]", "{\n\"a\"\n:\n1\n}", "{\r\"a\"\r:\r1\r}",
        # Bare colon/comma after value.
        "[1:2]", "[1,2:", '{"a":1:2}', '{"a":1,,2}',
        # Mismatched container closers mid-stream.
        "[{]", "[}]", "{[]", "{]}", "[[}]", "{{]}",
        # Numbers with each possible tail char.
        *["1" + t for t in ("a", "b", "z", "$", "%", "&", "*", "(", ")", "=", "?", "@")],
        # Empty input variants with each whitespace char.
        "", " ", "\t", "\n", "\r", "\v", "\f",
        " \t\n\r\v\f",
    ]
)

strategy = st.one_of(
    complete,
    deep_value,
    _malformed,
    _branch_targeted,
    _branch_targeted2,
    _state_edge,
    # Number/string token-boundary tails to hit lexer fallthrough branches.
    st.builds(lambda pre, tail: pre + tail, st.sampled_from(["", "-", "0", "1", "12", "1.", "1.5", "1e", "1e1"]), _number_tails),
    st.builds(lambda pre, tail: pre + tail, st.sampled_from(['"', '"a', '"ab', '"abc', '"\\', '"\\u', '"\\u0']), _string_tails),
    # Pure whitespace / empty-ish inputs.
    st.text(alphabet=" \t\n\r", max_size=8),
    # A couple of raw JSON dumps of Python objects for realistic seeds.
    st.one_of(
        st.integers(min_value=-10**6, max_value=10**6),
        st.floats(allow_nan=False, allow_infinity=False, width=64),
        st.booleans(),
        st.none(),
        st.text(alphabet=SAFE_CHARS, max_size=8),
        st.lists(st.integers(min_value=-100, max_value=100), max_size=5),
    ).map(lambda o: json.dumps(o, ensure_ascii=True)),
)