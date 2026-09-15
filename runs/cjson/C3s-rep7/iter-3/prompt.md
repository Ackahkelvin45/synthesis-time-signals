Here is the current Hypothesis strategy:

```python
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
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":1,"a":2}'),
        st.just('{"":""}'),
        st.just("[[]]"),
        st.just("[[[[[[[[[[0]]]]]]]]]]"),
        st.just('{"a":{"b":{"c":{"d":0}}}}'),
    )


strategy = _top_level()
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 75.28,
  "region_coverage_pct": 93.55
}

Make EXACTLY ONE change to the strategy: **increase_branch_coverage** — branch coverage is 75.3%; reach parser code the current inputs never execute.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.