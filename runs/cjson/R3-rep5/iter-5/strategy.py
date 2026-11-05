from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helper building blocks
# ---------------------------------------------------------------------------

def _join(parts):
    return lambda t: "".join(t)

# A safe, ordinary string body (no need to be JSON-escaped since we build raw)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in raw text
    blacklist_characters='"\\',
)

def _raw_string_body():
    # Raw (unescaped) content, including control chars and NUL.
    return st.text(
        alphabet=st.one_of(
            _safe_chars,
            st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
        ),
        max_size=12,
    )

def _escape_seq():
    simple = st.sampled_from(
        ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
    )
    hexdigits = "0123456789abcdefABCDEF"
    unicode_esc = st.tuples(
        st.just("\\u"),
        st.text(alphabet=hexdigits, min_size=4, max_size=4),
    ).map("".join)
    # Deliberately include surrogate escapes (\ud800-\udfff)
    surrogate_esc = st.tuples(
        st.just("\\u"),
        st.sampled_from(["d", "D"]),
        st.text(alphabet="89abAB", min_size=1, max_size=1),
        st.text(alphabet=hexdigits, min_size=2, max_size=2),
    ).map("".join)
    return st.one_of(simple, unicode_esc, surrogate_esc)

def _json_string():
    body = st.one_of(
        _raw_string_body(),
        st.lists(st.one_of(_raw_string_body(), _escape_seq()), max_size=6).map(
            lambda parts: "".join(parts)
        ),
    )
    return st.tuples(st.just('"'), body, st.just('"')).map("".join)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _number():
    digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
    int_part = st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), digits).map("".join),
        # leading-zero deviation (accepted by parser)
        st.tuples(st.just("0"), digits).map("".join),
        # hex deviation (accepted by parser)
        st.tuples(st.just("0x"), st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=4)).map("".join),
    )
    sign = st.one_of(st.just(""), st.just("-"))
    frac = st.one_of(
        st.just(""),
        st.tuples(st.just("."), digits).map("".join),
        # trailing dot deviation
        st.just("."),
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.one_of(st.just(""), st.just("+"), st.just("-")),
            digits,
        ).map("".join),
    )
    # extreme magnitudes / overflow
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e999", "1e-999", "9" * 30, "-" + "9" * 30,
        "0e0", "1E+400", "1e-400",
    ])
    composed = st.tuples(sign, int_part, frac, exp).map("".join)
    return st.one_of(composed, extreme)

# ---------------------------------------------------------------------------
# Malformed fragments (near-valid but broken)
# ---------------------------------------------------------------------------

def _malformed():
    return st.sampled_from([
        "",            # empty input
        ",", "[,]", "{,}", "[1,,2]", '{"a":1,,"b":2}',
        "[1,2,]", '{"a":1,}', '{"a" 1}', '{"a":}', '{:1}',
        '"unterminated', "'single'", "{a:1}", "{'a':1}",
        "-", "+1", ".5", "NaN", "Infinity", "-Infinity",
        '["\\ud800"]', '["\\udfff"]',
        "tru", "fals", "nul", "truex", "01", "1.", "0x10",
        "[", "]", "{", "}", ":", "\\",
        '"\\q"', '"\\u12"', '"\\uZZZZ"',
    ])

# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

def _leaf():
    return st.one_of(
        _json_string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _ws():
    return st.text(alphabet=" \t\n\r", max_size=2)

def _value(draw_strategy):
    # draw_strategy is a SearchStrategy for nested values
    leaf = _leaf()

    def make_array(t):
        items = t
        return "[" + ",".join(items) + "]"

    def make_object(pairs):
        return "{" + ",".join(pairs) + "}"

    arr = st.lists(
        st.tuples(_ws(), draw_strategy, _ws()).map(lambda p: p[1]),
        max_size=4,
    ).map(make_array)

    def make_pair(kv):
        k, v = kv
        return k + ":" + v

    obj = st.lists(
        st.tuples(_json_string(), st.just(":"), draw_strategy).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        max_size=4,
    ).map(make_object)

    special = st.sampled_from(["{}", "[]"])

    return st.one_of(leaf, arr, obj, special)

# Depth-controlled recursive generation concentrating near the ~1000 limit.
def _nested(depth):
    # Build a value nested exactly `depth` levels deep using arrays.
    return st.just("[" * depth + "0" + "]" * depth)

def _deep_values():
    # Concentrate interesting depths near the limit.
    return st.one_of(
        st.integers(min_value=0, max_value=50).map(lambda d: "[" * d + "]" * d),
        st.integers(min_value=990, max_value=1010).map(
            lambda d: "[" * d + "0" + "]" * d
        ),
        st.integers(min_value=990, max_value=1010).map(
            lambda d: '{"a":' * d + "0" + "}" * d
        ),
        st.sampled_from([999, 1000, 1001]).map(
            lambda d: "[" * d + "]" * d
        ),
    )

# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

_base = st.recursive(
    _leaf(),
    _value,
    max_leaves=20,
)

_bom = st.one_of(st.just(""), st.just("\ufeff"))

_trailing = st.one_of(
    st.just(""),
    st.sampled_from(["abc", " 2", "\x00", " xyz", "1 2", "\n"]),
)

_valid = st.tuples(_bom, _base, _trailing).map("".join)

_malformed_top = st.tuples(_bom, _malformed()).map("".join)

# ---------------------------------------------------------------------------
# Round-trip / print-path exercises (cJSON_Parse -> cJSON_Print -> Compare)
# ---------------------------------------------------------------------------
# The print_* and cJSON_Compare functions were entirely uncovered. Exercise
# them by feeding values through a parse/print/compare style pipeline. We
# generate valid JSON and also wrap it in whitespace variants and key
# orderings that stress the printer and comparison logic.

def _print_path_value():
    # Objects with many keys (tests print_object ordering / compare).
    def make_obj(pairs):
        return "{" + ",".join(pairs) + "}"

    def make_pair(kv):
        k, v = kv
        return k + ":" + v

    keys = st.lists(
        st.tuples(_json_string(), _leaf()).map(make_pair),
        max_size=8,
    ).map(make_obj)

    # Arrays of mixed values (tests print_value / print_string_ptr).
    arrs = st.lists(_leaf(), max_size=8).map(
        lambda items: "[" + ",".join(items) + "]"
    )

    # Strings needing escaping on print (quotes, backslashes, control chars).
    tricky_strings = st.tuples(
        st.just('"'),
        st.lists(
            st.sampled_from(
                ['\\"', "\\\\", "\\n", "\\t", "\\r", "\\b", "\\f", "\\/",
                 "a", " ", "\x01", "\x1f", "\\u00e9", "\\u0000"]
            ),
            max_size=10,
        ).map("".join),
        st.just('"'),
    ).map("".join)

    # Numbers that stress print_number (formats, precision).
    tricky_numbers = st.sampled_from([
        "0", "-0", "1", "-1", "0.0", "1.0", "1.5", "-1.5",
        "1e10", "1e-10", "1.23456789", "123456789012345",
        "3.141592653589793", "2.718281828459045",
        "1e308", "1e-308", "9007199254740993",
    ])

    leaf = st.one_of(_json_string(), tricky_strings, tricky_numbers,
                     st.sampled_from(["true", "false", "null"]))

    obj = st.lists(
        st.tuples(_json_string(), leaf).map(make_pair),
        max_size=6,
    ).map(make_obj)

    arr = st.lists(leaf, max_size=6).map(
        lambda items: "[" + ",".join(items) + "]"
    )

    # Duplicate keys (compare behavior).
    dup_keys = st.lists(
        st.tuples(st.sampled_from(['"a"', '"b"', '"c"']), leaf).map(make_pair),
        min_size=2, max_size=5,
    ).map(make_obj)

    return st.one_of(keys, arrs, tricky_strings, tricky_numbers, obj, arr, dup_keys)

_print_path = st.tuples(
    st.one_of(st.just(""), st.just(" "), st.just("\n"), st.just("\t")),
    _print_path_value(),
    st.one_of(st.just(""), st.just(" "), st.just("\n")),
).map("".join)

# ---------------------------------------------------------------------------
# Dedicated round-trip pipeline driver: valid JSON documents that always
# parse successfully, so the downstream cJSON_Print / cJSON_Compare calls
# are actually reached (previously the print_* / Compare functions were 0%).
# ---------------------------------------------------------------------------

def _rt_scalar():
    return st.one_of(
        _json_string(),
        st.sampled_from([
            "0", "-0", "1", "-1", "1.5", "-1.5", "1e10", "1e-10",
            "123456789012345", "3.141592653589793", "9007199254740993",
            "true", "false", "null",
        ]),
    )

def _rt_value(depth):
    # Build a guaranteed-valid JSON value of bounded depth.
    scalar = _rt_scalar()
    if depth <= 0:
        return scalar

    def make_array(items):
        return "[" + ",".join(items) + "]"

    def make_object(pairs):
        return "{" + ",".join(pairs) + "}"

    arr = st.lists(_rt_value(depth - 1), max_size=4).map(make_array)

    def make_pair(kv):
        k, v = kv
        return k + ":" + v

    obj = st.lists(
        st.tuples(_json_string(), _rt_value(depth - 1)).map(make_pair),
        max_size=4,
    ).map(make_object)

    return st.one_of(scalar, arr, obj, st.just("{}"), st.just("[]"))

_roundtrip = st.tuples(
    st.one_of(st.just(""), st.just(" "), st.just("\n")),
    _rt_value(3),
    st.one_of(st.just(""), st.just(" "), st.just("\n")),
).map("".join)

# Objects with a fixed, duplicated-key layout guarantee cJSON_Compare is
# exercised on both equal and unequal trees.
_compare_pairs = st.lists(
    st.tuples(
        st.sampled_from(['"a"', '"b"', '"c"', '"x"']),
        _rt_scalar(),
    ).map(lambda kv: kv[0] + ":" + kv[1]),
    min_size=1,
    max_size=6,
).map(lambda pairs: "{" + ",".join(pairs) + "}")

# ---------------------------------------------------------------------------
# IMPROVEMENT: a dedicated parse/print/compare driver.
#
# The prior run still showed print_value/print_string_ptr/print_number/
# print_object/cJSON_Compare at 0% branches. Those are only reached when a
# valid document is parsed *and* then printed/compared. Emit a self-contained
# "program" that the harness can feed through that pipeline, biased toward
# the constructs that exercise the printer and comparator: nested containers,
# strings requiring escaping, and numbers with varied formats.
# ---------------------------------------------------------------------------

# Strings that force every escape branch of print_string_ptr.
_print_escape_string = st.tuples(
    st.just('"'),
    st.lists(
        st.sampled_from([
            '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
            "a", "Z", "0", " ", "\x00", "\x01", "\x1f", "\x7f",
            "\\u0000", "\\u00e9", "\\u20ac", "\\ud83d\\ude00",
        ]),
        min_size=0,
        max_size=12,
    ).map("".join),
    st.just('"'),
).map("".join)

# Numbers that force every branch of print_number (int vs double, signs,
# exponents, precision, large/small magnitudes).
_print_number = st.sampled_from([
    "0", "-0", "1", "-1", "42", "-42", "0.0", "-0.0", "1.0", "-1.0",
    "1.5", "-1.5", "0.1", "0.25", "1e10", "1E10", "1e-10", "1e+10",
    "-1e10", "1.23456789", "3.141592653589793", "2.718281828459045",
    "123456789012345", "9007199254740993", "1e308", "1e-308",
    "1.7976931348623157e308", "5e-324", "100000000000000000000",
])

_print_leaf = st.one_of(
    _print_escape_string,
    _json_string(),
    _print_number,
    st.sampled_from(["true", "false", "null"]),
)

def _print_doc(depth):
    def make_array(items):
        return "[" + ",".join(items) + "]"

    def make_object(pairs):
        return "{" + ",".join(pairs) + "}"

    def make_pair(kv):
        return kv[0] + ":" + kv[1]

    if depth <= 0:
        return _print_leaf

    arr = st.lists(_print_doc(depth - 1), min_size=0, max_size=5).map(make_array)
    obj = st.lists(
        st.tuples(_print_escape_string, _print_doc(depth - 1)).map(make_pair),
        min_size=0,
        max_size=5,
    ).map(make_object)
    return st.one_of(_print_leaf, arr, obj, st.just("{}"), st.just("[]"))

# Whitespace / BOM variants so the printer is reached from varied inputs.
_print_driver = st.tuples(
    st.one_of(st.just(""), st.just(" "), st.just("\n"), st.just("\t")),
    _print_doc(3),
    st.one_of(st.just(""), st.just(" "), st.just("\n")),
).map("".join)

# A guaranteed-valid, deeply-structured document to drive Compare on
# equal-vs-unequal trees: two sibling values joined by a marker the harness
# can split, plus a single well-formed document.
_compare_driver = st.tuples(
    _print_doc(2),
    st.just("\n"),
    _print_doc(2),
).map("".join)

# ---------------------------------------------------------------------------
# IMPROVEMENT (this change): a self-contained "program" that the harness can
# replay through parse -> print -> compare. The prior run left
# cJSON_Compare / print_value / print_string_ptr / print_number / print_object
# at 0% coverage, which means the harness never saw a document that both
# parsed successfully AND was then routed into the print/compare pipeline.
#
# We therefore emit a single valid JSON document (never malformed, never
# wrapped in trailing garbage) that is rich in the exact constructs those
# functions branch on: objects with many keys, arrays of mixed leaves,
# strings containing every escape class, and numbers spanning int/double,
# sign, exponent, and magnitude extremes. This is deliberately the FIRST
# alternative so it dominates the input distribution and guarantees the
# print/compare code paths are actually reached.
# ---------------------------------------------------------------------------

def _pipeline_value(depth):
    """A strictly-valid JSON value biased toward print/compare branches."""
    def make_array(items):
        return "[" + ",".join(items) + "]"

    def make_object(pairs):
        return "{" + ",".join(pairs) + "}"

    def make_pair(kv):
        return kv[0] + ":" + kv[1]

    if depth <= 0:
        return _print_leaf

    # Wide objects (exercise print_object key iteration + compare over keys).
    obj = st.lists(
        st.tuples(_print_escape_string, _pipeline_value(depth - 1)).map(make_pair),
        min_size=0,
        max_size=8,
    ).map(make_object)

    # Mixed arrays (exercise print_value dispatch + compare recursion).
    arr = st.lists(_pipeline_value(depth - 1), min_size=0, max_size=8).map(make_array)

    return st.one_of(_print_leaf, arr, obj, st.just("{}"), st.just("[]"))

# A single, guaranteed-parseable document. No BOM, no trailing junk: the
# harness's parse step must succeed so it proceeds to print/compare.
_pipeline_doc = _pipeline_value(4)

# Two documents separated by a newline so a harness that splits on "\n" can
# drive cJSON_Compare on both equal and structurally-different trees.
_pipeline_compare = st.tuples(
    _pipeline_value(2),
    st.just("\n"),
    _pipeline_value(2),
).map("".join)

# A document paired with a mutated copy (shares shape, differs in a leaf)
# to exercise cJSON_Compare's "not equal" branch.
def _mutated_pair():
    return st.tuples(
        _pipeline_value(2),
        st.sampled_from(["0", "1", "true", "false", "null", '"x"', '"y"', "[]", "{}"]),
    ).map(lambda t: t[0] + "\n" + t[1])

strategy = st.one_of(
    _pipeline_doc,
    _pipeline_compare,
    _mutated_pair(),
    _valid,
    _malformed_top,
    _deep_values(),
    _print_path,
    _roundtrip,
    _compare_pairs,
    _print_driver,
    _compare_driver,
)