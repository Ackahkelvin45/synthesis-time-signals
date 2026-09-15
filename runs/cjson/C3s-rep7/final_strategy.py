from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that are safe inside a JSON string per the grammar.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) >= 0x20)

# Raw control / NUL bytes are accepted by the parser inside strings.
_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)

# Simple escapes.
_simple_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex_digits = "0123456789abcdefABCDEF"


def _unicode_escape():
    return st.text(alphabet=_hex_digits, min_size=4, max_size=4).map(
        lambda h: "\\u" + h
    )


def _surrogate_escape():
    # High and low surrogates, valid and lone.
    return st.integers(min_value=0xD800, max_value=0xDFFF).map(
        lambda n: "\\u%04x" % n
    )


def _string_body_char():
    return st.one_of(
        _safe_chars.map(str),
        _raw_control.map(str),
        _simple_escapes,
        _unicode_escape(),
        _surrogate_escape(),
    )


def _string():
    return st.lists(_string_body_char(), max_size=12).map(
        lambda parts: '"' + "".join(parts) + '"'
    )


# ---------------------------------------------------------------------------
# Numbers: valid, edge, and near-valid-but-malformed
# ---------------------------------------------------------------------------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=1, max_value=10**18).map(str),
        # leading zeros: accepted by this parser
        st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
        # hex: accepted by this parser
        st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda n: "0x%x" % n),
    )


def _exp_part():
    return st.one_of(
        st.just(""),
        st.integers(min_value=-400, max_value=400).map(lambda n: "e%d" % n),
        st.integers(min_value=-400, max_value=400).map(lambda n: "E+%d" % n),
        st.just("e309"),
        st.just("E-309"),
        st.just("e9999"),
    )


def _frac_part():
    return st.one_of(
        st.just(""),
        st.integers(min_value=0, max_value=10**9).map(lambda n: ".%d" % n),
        st.just("."),  # trailing dot: accepted by this parser
    )


def _number():
    return st.builds(
        lambda sign, i, f, e: sign + i + f + e,
        st.sampled_from(["", "-"]),
        _int_part(),
        _frac_part(),
        _exp_part(),
    )


def _malformed_number():
    return st.sampled_from(
        ["-", "+1", ".5", "01", "1.", "0x", "1e", "1e+", "--1", "1..2", "0xZ"]
    )


# ---------------------------------------------------------------------------
# Recursive value strategy with controlled depth
# ---------------------------------------------------------------------------

_MAX_DEPTH = 1000


def _value_at_depth(depth):
    """Return a strategy for a JSON value, allowing nesting up to `depth`."""
    if depth <= 0:
        return st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null"]),
        )

    # Mix of leaves, shallow containers, and deep containers.
    leaf = st.one_of(
        _string(),
        _number(),
        _malformed_number(),
        st.sampled_from(["true", "false", "null", "NaN", "Infinity"]),
    )

    # A container whose children are at most depth-1.
    child = st.one_of(
        leaf,
        st.deferred(lambda: _value_at_depth(depth - 1)),
    )

    obj = st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(
            st.tuples(
                _string(),
                st.one_of(
                    leaf,
                    st.deferred(lambda: _value_at_depth(depth - 1)),
                ),
            ).map(lambda kv: kv[0] + ":" + kv[1]),
            max_size=4,
        ),
    )

    arr = st.builds(
        lambda items: "[" + ",".join(items) + "]",
        st.lists(child, max_size=4),
    )

    return st.one_of(leaf, obj, arr)


# ---------------------------------------------------------------------------
# Deep nesting near the 1000-level limit
# ---------------------------------------------------------------------------

def _deep_array():
    return st.integers(min_value=1, max_value=_MAX_DEPTH).map(
        lambda n: "[" * n + "0" + "]" * n
    )


def _deep_object():
    return st.integers(min_value=1, max_value=_MAX_DEPTH).map(
        lambda n: '{"a":' * n + "0" + "}" * n
    )


def _overdeep_array():
    return st.integers(min_value=_MAX_DEPTH + 1, max_value=_MAX_DEPTH + 50).map(
        lambda n: "[" * n + "0" + "]" * n
    )


def _overdeep_object():
    return st.integers(min_value=_MAX_DEPTH + 1, max_value=_MAX_DEPTH + 50).map(
        lambda n: '{"a":' * n + "0" + "}" * n
    )


# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

def _malformed():
    return st.sampled_from(
        [
            "",
            ",",
            "{",
            "}",
            "[",
            "]",
            "{,}",
            "[,]",
            "[1,,2]",
            '{"a":}',
            '{"a" 1}',
            '{"a":1,}',
            "[1,2,]",
            "'single'",
            "{a:1}",
            '"unterminated',
            '{"a":"unterminated}',
            "\\",
            '"\\x"',
            '"\\u12"',
            '"\\ud800"',
            '"\\udfff"',
            "tru",
            "fals",
            "nul",
            "True",
            "NULL",
            "-",
            "+1",
            ".5",
            "01",
            "NaN",
            "Infinity",
            "\x00",
            "\ufeff",
            "\xef\xbb\xbf1",
        ]
    )


def _bom_prefixed():
    return st.one_of(
        st.just("\ufeff1"),
        st.just("\ufeff{}"),
        st.just("\ufeff[]"),
        st.just("\ufeff\"x\""),
        st.just("\ufeff"),
    )


def _trailing_content():
    return st.one_of(
        st.just("1abc"),
        st.just("1 2"),
        st.just("{}garbage"),
        st.just("[]\x00"),
        st.just("nullnull"),
        st.just("truefalse"),
    )


def _whitespace():
    """Whitespace-only and whitespace-heavy inputs to hit lexer skip paths."""
    ws = " \t\n\r"
    return st.one_of(
        st.text(alphabet=ws, min_size=1, max_size=8),
        st.text(alphabet=ws, min_size=0, max_size=4).map(lambda w: w + "1" + w),
        st.text(alphabet=ws, min_size=0, max_size=4).map(
            lambda w: w + "{" + w + '"a"' + w + ":" + w + "1" + w + "}" + w
        ),
        st.text(alphabet=ws, min_size=0, max_size=4).map(
            lambda w: w + "[" + w + "1" + w + "," + w + "2" + w + "]" + w
        ),
        st.text(alphabet=ws, min_size=0, max_size=4).map(
            lambda w: w + "true" + w
        ),
        st.text(alphabet=ws, min_size=0, max_size=4).map(
            lambda w: w + "null" + w
        ),
        st.text(alphabet=ws, min_size=0, max_size=4).map(
            lambda w: w + "-" + w + "1" + w + "." + w + "5" + w + "e" + w + "2" + w
        ),
    )


# ---------------------------------------------------------------------------
# Branch-coverage boosters: exotic escapes / literals / structural edges
# ---------------------------------------------------------------------------

def _exotic_escapes():
    """Escape sequences and literal bytes that exercise rarely-taken branches."""
    return st.sampled_from(
        [
            '"\\u0000"',
            '"\\uFFFF"',
            '"\\uD800\\uDC00"',
            '"\\uDBFF\\uDFFF"',
            '"\\uD800x"',
            '"\\uDC00\\uD800"',
            '"\\uDBFF\\uD800"',
            '"\\uD800\\uD800"',
            '"\\uDC00\\uDC00"',
            '"\\uD800\\n"',
            '"\\uDC00\\t"',
            '"\\uD800\\uDBFF"',
            '"\\uU"',
            '"\\u12G4"',
            '"\\u123"',
            '"\\u12345"',
            '"\\u"',
            '"\\u0"',
            '"\\U0001F600"',
            '"\\x41"',
            '"\\0"',
            '"\\a"',
            '"\\v"',
            '"\\\'"',
            '"\\\n"',
            '"\\\r\n"',
            '"\\ "',
            '"\\\x00"',
            '"\\\x1f"',
            '"\\\x7f"',
            '"\\/\\/\\/"',
            '"\\\\\\""',
            '"\\uD83D\\uDE00"',
            '"\\uD83D\\uDE00x"',
            '"x\\uD83D\\uDE00"',
            '"\\uD83D\\u0041"',
            '"\\u0041\\uDE00"',
            '"\\uD83D\\uD83D"',
            '"\\uDE00\\uDE00"',
            '"\\uD83D"',
            '"\\uDE00"',
            '"\\uD83D\\uDE00\\uD83D\\uDE00"',
            '"\\uD83D\\u0041\\uDE00"',
            '"\\uDE00\\uD83D"',
            '"\\uD800\\u0041"',
            '"\\u0041\\uD800"',
            '"\\uD800\\uD800\\uDC00"',
            '"\\uDC00\\uD800\\uDC00"',
            '"\\uD800\\uDC00\\uD800\\uDC00"',
        ]
    )


def _exotic_literals():
    """Literal tokens whose prefixes share branches with valid keywords."""
    return st.sampled_from(
        [
            "t", "tr", "tru", "true", "truex", "true1",
            "f", "fa", "fal", "fals", "false", "falsex",
            "n", "nu", "nul", "null", "nullx",
            "tRue", "FALSE", "Null", "nULL",
            "truee", "falsee", "nulll",
            "true\x00", "null\x00", "false\x00",
        ]
    )


def _exotic_numbers():
    """Numeric shapes hitting sign / int / frac / exp transition branches."""
    return st.sampled_from(
        [
            "-0", "-0.0", "-0e0", "-0.0e0",
            "0e0", "0E0", "0e+0", "0e-0", "0E+0", "0E-0",
            "0.0", "0.0e0", "0.0E+0", "0.0E-0",
            "-1", "-1.5", "-1.5e-3", "-1.5E+3",
            "1e0", "1e+0", "1e-0", "1E0", "1E+0", "1E-0",
            "1.0e0", "1.0e+0", "1.0e-0",
            "1e00", "1e000", "1e+00", "1e-00",
            "1E+308", "1E-308", "1E+309", "1E-309",
            "1e308", "1e-308", "1e309", "1e-309",
            "0x0", "0x1", "0xabcdef", "0X1", "0XFF",
            "0x", "0X", "0xg", "0xG",
            "1e+", "1e-", "1E+", "1E-",
            "1.", ".1", "1.e0", "1.e+0",
            "-", "-.", "-e0", "--", "-+",
            "00", "000", "01", "0123",
            "1_000", "1,0", "1 0",
            "9007199254740993",
            "18446744073709551616",
            "1e400", "-1e400", "1e-400",
            "0.1e1", "0.1e-1",
        ]
    )


def _structural_edges():
    """Inputs hitting container-close, comma, colon, and EOF branches."""
    return st.sampled_from(
        [
            "[", "]", "{", "}", "[{", "[}", "{]", "{}",
            '{"a"', '{"a":', '{"a":1', '{"a":1,',
            '{"a":1,"b"', '{"a":1,"b":', '{"a":1,"b":2',
            "[1", "[1,", "[1,2", "[1,2,",
            "[[", "]]", "{{", "}}",
            "[}", "{]", "[{]", "{[}]",
            '{"a":[]}', '{"a":{}}', "[{}]", "[[]]",
            '{"a":[1,{"b":2}]}',
            "[1,[2,[3,[4,[5]]]]]",
            '{"a":{"b":{"c":{"d":{"e":1}}}}}',
            "[,]", "[,,]", "{,}", "{,,}",
            '{"":""}', '{"a":1,"a":2,"a":3}',
            "[1,2,3,4,5,6,7,8,9,10]",
            '{"a":1,"b":2,"c":3,"d":4}',
            "[null,true,false,0,\"\",[],{}]",
            '{"k":[null,true,false,0,"",[],{}]}',
            "[1 ]", "[ 1]", "{ }", "{  }",
            "[1, 2]", '{"a" : 1}',
            "[1,\n2]", '{"a":\n1}',
            "[\t1\t]", "{\t\"a\"\t:\t1\t}",
            "[1,]", '{"a":1,}',
            "[\n\n]", "{\n\n}",
        ]
    )


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

def _base_value():
    return _value_at_depth(6)


def _top_level():
    return st.one_of(
        _base_value(),
        _malformed(),
        _bom_prefixed(),
        _trailing_content(),
        _whitespace(),
        _deep_array(),
        _deep_object(),
        _overdeep_array(),
        _overdeep_object(),
        _exotic_escapes(),
        _exotic_literals(),
        _exotic_numbers(),
        _structural_edges(),
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":1,"a":2}'),
        st.just('{"":""}'),
        st.just("[[]]"),
        st.just("[[[[[[[[[[0]]]]]]]]]]"),
        st.just('{"a":{"b":{"c":{"d":0}}}}'),
        # NEW: whitespace/EOF and delimiter branch boosters.
        st.sampled_from(
            [
                # Trailing whitespace after a complete value (post-value EOF skip).
                "1 ", "1\t", "1\n", "1\r", "1 \t\n\r",
                "{} ", "[]\t", "null\n", "true\r", "false ",
                '"x" ', '"x"\t', '"x"\n', '"x"\r',
                # Leading whitespace before each token type (lexer skip branch).
                " 1", "\t1", "\n1", "\r1",
                " {}", "\t[]", "\nnull", "\rtrue",
                ' "x"', '\t"x"', '\n"x"', '\r"x"',
                # Whitespace around every structural delimiter.
                "[ 1 , 2 ]", '{ "a" : 1 }',
                "[1 ,2]", "[1, 2]", "[1 , 2]",
                '{"a" :1}', '{"a": 1}', '{"a" : 1}',
                "[\n1\n,\n2\n]", "{\n\"a\"\n:\n1\n}",
                "[\r1\r,\r2\r]", "{\r\"a\"\r:\r1\r}",
                "[\t1\t,\t2\t]", "{\t\"a\"\t:\t1\t}",
                # Whitespace inside empty containers.
                "[ ]", "[\t]", "[\n]", "[\r]",
                "{ }", "{\t}", "{\n}", "{\r}",
                # Whitespace between nested delimiters.
                "[ [ ] ]", "{ { } }", "[ { } ]", "{ [ ] }",
                "[ [ 1 ] ]", '{ "a" : { "b" : 1 } }',
                # Whitespace before EOF after unterminated containers.
                "[", "[ ", "[\t", "[\n", "[\r",
                "{", "{ ", "{\t", "{\n", "{\r",
                '{"a"', '{"a" ', '{"a":', '{"a": ',
                '{"a":1', '{"a":1 ', '{"a":1,', '{"a":1, ',
                "[1", "[1 ", "[1,", "[1, ",
                # Whitespace-only trailing after keywords / literals.
                "true ", "false ", "null ",
                " true", " false", " null",
                # Whitespace between tokens of a number.
                "- 1", "1 . 5", "1 e 2",
                # Whitespace after top-level scalar followed by EOF.
                "0 ", "-0 ", "0.0 ", "1e0 ",
            ]
        ),
        # NEW: string-scanning branches — unterminated strings, escapes at EOF,
        # truncated \u sequences, raw control bytes, and unterminated strings
        # embedded in containers.
        st.sampled_from(
            [
                '"',
                '"a',
                '"abc',
                '{"a":"',
                '{"a":"b',
                '["',
                '["a',
                '["a",',
                '"\\',
                '"\\u',
                '"\\u1',
                '"\\u12',
                '"\\u123',
                '"\\u1234',
                '"\\x',
                '"\\',
                '"\\\\',
                '"\\"',
                '"a\\',
                '"a\\u',
                '"a\\u12',
                '"a\\u1234',
                '"a\\"',
                '"a\\\\',
                '"a\nb"',
                '"a\tb"',
                '"a\rb"',
                '"a\x00b"',
                '"a\x1fb"',
                '"a\x7fb"',
                '{"a":"unterminated',
                '["unterminated',
                '{"a":"b","c":"unterminated',
                '["a","unterminated',
                '{"a":"\\u12',
                '["\\u12',
                '{"a":"\\',
                '["\\',
                '{"a":"\x00',
                '["\x00',
                '"\\uD800',
                '"\\uD800\\u',
                '"\\uD800\\uDC00',
                '"\\uD800\\uDC00x',
                '"\\uD800x',
                '"\\uD800x\\uDC00"',
            ]
        ),
    )


strategy = _top_level()