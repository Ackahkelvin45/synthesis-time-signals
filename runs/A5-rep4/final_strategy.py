from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

def _unicode_escape():
    return st.tuples(st.just("\\u"), _hex4()).map(lambda t: t[0] + t[1])

_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# surrogate escapes and other unicode-ish escapes
_weird_esc = st.one_of(
    _unicode_escape(),
    st.just("\\uD800"), st.just("\\uDBFF"), st.just("\\uDC00"),
    st.just("\\uDFFF"), st.just("\\u0000"), st.just("\\uFFFF"),
    st.just("\\u0001"), st.just("\\u001F"),
    # surrogate pairs
    st.tuples(st.just("\\uD800"), st.just("\\uDC00")).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("\\uDBFF"), st.just("\\uDFFF")).map(lambda t: t[0] + t[1]),
    # lone high surrogate followed by non-low
    st.tuples(st.just("\\uD800"), st.just("a")).map(lambda t: t[0] + t[1]),
)

# raw control bytes / NUL - allowed since parser takes explicit length
_ctrl_bytes = st.sampled_from(
    ["\x00", "\x01", "\x1f", "\x7f", "\x0b", "\x0c", "\x08", "\x0e"]
)

# a "safe" raw char (no quote, no backslash, no control)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f",
)

_str_body_piece = st.one_of(
    _safe_char.map(str),
    _simple_esc,
    _weird_esc,
    _ctrl_bytes,
)

def _make_string_body():
    return st.lists(_str_body_piece, max_size=12).map("".join)

# strings, including malformed / unterminated variants
_quoted_string = _make_string_body().map(lambda b: '"' + b + '"')

_unterminated_string = _make_string_body().map(lambda b: '"' + b)

_bad_escape_string = st.one_of(
    st.just('"\\x41"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('"\\'),
    st.just('"'),
    st.just('"\\u"'),
    st.just('"\\uD800"'),
    st.just('"\\uDC00"'),
    st.just('"\\uD800a"'),
    st.just('"\\uD800\\uD800"'),
)

_string = st.one_of(_quoted_string, _unterminated_string, _bad_escape_string)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"),
              st.lists(st.sampled_from("0123456789"), max_size=18).map("".join))
        .map(lambda t: t[0] + t[1]),
)

_frac = st.tuples(st.just("."),
                  st.lists(st.sampled_from("0123456789"), min_size=1, max_size=18).map("".join)
                  ).map(lambda t: t[0] + t[1])

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.sampled_from("0123456789"), min_size=1, max_size=5).map("".join),
).map(lambda t: t[0] + t[1] + t[2])

_number = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# extreme numbers / overflow / lenient forms
_extreme_number = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1e308"),
    st.just("1.7976931348623157e309"),
    st.just("1e999999999"),
    st.just("1e-999999999"),
    st.just("0e0"),
    st.just("-0"),
    st.just("-0.0e-0"),
    # lone minus accepted by parser
    st.just("-"),
    # malformed / rejected-by-spec number forms
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("-01"),
    st.just("0x1F"),
    st.just("1e"),
    st.just("1e+"),
    st.just("--1"),
    st.just("1.2.3"),
    st.just("1e+308"),
    st.just("1e-308"),
    st.just("2.2250738585072014e-308"),
    st.just("4.9406564584124654e-324"),
    st.just("1.7976931348623157e308"),
    st.just("0.0000000000000000000000000000000000000000000000000000000000000001"),
    st.just("-1e-999999999"),
    st.just("1E999"),
    st.just("1e00000000000000000000000000000001"),
)

_number_all = st.one_of(_number, _extreme_number)

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null", "True", "FALSE", "nul", "undefined"])

# ---------- recursive value / obj / arr ----------

json_strategy = st.recursive(
    st.one_of(_string, _number_all, _literal),
    lambda children: st.one_of(
        # arrays
        st.one_of(
            st.just("[]"),
            st.lists(children, min_size=1, max_size=6).map(lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(children, min_size=1, max_size=6).map(lambda xs: "[" + ",".join(xs) + ",]"),
            st.just("[1,,2]"),
            st.just("[,]"),
            st.just("[,1]"),
            st.just("[1 2]"),
            st.just("[1,2"),
            st.lists(children, min_size=1, max_size=6).map(lambda xs: "[" + " ".join(xs) + "]"),
            st.lists(children, min_size=1, max_size=6).map(lambda xs: "[" + ",".join(xs) + ",,]"),
        ),
        # objects - biased toward members (stressed path)
        st.one_of(
            st.just("{}"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map(lambda t: t[0] + t[1] + t[2]),
                min_size=1, max_size=6,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map(lambda t: t[0] + t[1] + t[2]),
                min_size=1, max_size=6,
            ).map(lambda ps: "{" + ",".join(ps) + ",}"),
            # duplicate keys
            st.tuples(_string, children).map(lambda t: '{"k":' + t[1] + ',"k":' + t[1] + "}"),
            # malformed objects
            st.just('{"a":1,,"b":2}'),
            st.just('{"a" 1}'),
            st.just('{"a":}'),
            st.just('{:1}'),
            st.just('{a:1}'),
            st.just('{"a":1'),
            st.just("{,}"),
            st.just('{"a":1 "b":2}'),
            st.lists(
                st.tuples(_string, st.just(":"), children).map(lambda t: t[0] + t[1] + t[2]),
                min_size=1, max_size=6,
            ).map(lambda ps: "{" + " ".join(ps) + "}"),
        ),
    ),
    max_leaves=40,
)

# ---------- deep nesting ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=2000)
    return depth.map(lambda d: "[" * d + "]" * d)

def _deep_obj_nesting():
    depth = st.integers(min_value=1, max_value=500)
    return depth.map(lambda d: '{"a":' * d + "null" + "}" * d)

_deep = st.one_of(_deep_nesting(), _deep_obj_nesting(),
                  st.just("[" * 100 + "1" + "]" * 100),
                  st.integers(min_value=1, max_value=2000).map(lambda d: "[" * d),
                  st.integers(min_value=1, max_value=500).map(lambda d: '{"a":' * d))

# ---------- near-valid-but-malformed whole inputs ----------

_malformed = st.sampled_from([
    "1abc",
    "[]xyz",
    "1 garbage",
    "true false",
    "//x\n1",
    "/* */1",
    "'x'",
    "{a:1}",
    "[1,2,]",
    '{"a":1,}',
    '{"a":1,"a":2}',
    "1e309",
    "-",
    "+1",
    ".5",
    "1.",
    "01",
    '"unterminated',
    '"\\u12"',
    "\x00",
    "{}\x00",
    "[1,\x00,2]",
    '{"a":\x001}',
    "\x00{}",
    "[\x00]",
    '{"":""}',
    '{"\\u0000":"\\u0000"}',
    '{"a":1,"a":2,"a":3}',
    "[1][2]",
    "{} {}",
    "nullnull",
    "tru",
    "nul",
    "[1,2,3,]",
    '{"x":1,"x":2,}',
    '{"a":1,"a":2,"a":3,"a":4,"a":5}',
    '{"\\uD800":1}',
    '{"\\uDC00":1}',
    '{"\\uD800\\uDC00":1}',
    '{"a":1e309}',
    '{"a":-0}',
    '{"a":1,"a":2,"a":3,"a":4,"a":5,"a":6}',
    '[1,2,3,4,5,6,7,8,9,10]',
    '{"a":{"b":{"c":{"d":1}}}}',
])

# ---------- top-level combination ----------

# Bias toward objects with members and the recursive tree.
# Also include a generic whitespace-padded wrapper to exercise the parser's
# leading/trailing whitespace handling, which is a common source of bugs.
_ws = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  \t\n "])

_padded = st.tuples(_ws, json_strategy, _ws).map(lambda t: t[0] + t[1] + t[2])

# A structural mutation operator: take a valid-ish value and inject a
# single corruption at a random position, which is much more likely to
# land near a parser decision point than generic trailing garbage.
_corrupt_byte = st.sampled_from(
    ["\x00", ",", ":", "{", "}", "[", "]", '"', "\\", " ", "\t", "\n", "e", "-", "1"]
)

def _mutate(s):
    # s is a string; splice a corruption at a random index.
    # Use a deterministic-but-varied index derived from content to avoid
    # needing an extra strategy layer.
    if not s:
        return s
    idx = (len(s) * 2654435761) % (len(s) + 1)
    return s[:idx] + "\x00" + s[idx:]

_mutated = json_strategy.map(_mutate)

# New: a mutation that replaces a random byte (rather than inserting) with a
# structural corruption, and one that truncates at a random point. These
# exercise different parser recovery paths than insertion alone.
def _replace(s):
    if not s:
        return s
    idx = (len(s) * 40503) % len(s)
    return s[:idx] + "]" + s[idx + 1:]

def _truncate(s):
    if not s:
        return s
    idx = (len(s) * 40503) % (len(s) + 1)
    return s[:idx]

_replace_mutated = json_strategy.map(_replace)
_truncated = json_strategy.map(_truncate)

strategy = st.one_of(
    json_strategy,
    json_strategy,
    json_strategy,
    _padded,
    _deep,
    _malformed,
    _mutated,
    _replace_mutated,
    _truncated,
    # wrap a value in trailing garbage sometimes
    st.tuples(json_strategy, st.sampled_from(["", " ", "x", "\x00", "1"])).map(
        lambda t: t[0] + t[1]
    ),
)