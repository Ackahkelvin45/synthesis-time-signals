Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- basic lexical pieces ----------

_hex = st.characters(whitelist_categories=("Nd",), min_codepoint=0x30, max_codepoint=0x39) | st.sampled_from("abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_esc_unicode = _hex4().map(lambda h: "\\u" + h)
_esc = _esc_simple | _esc_unicode

# surrogate escapes (lone and paired) — valuable edge cases
_surrogate = st.sampled_from(["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\ud800\\ud800", "\\udc00"])

# safe codepoints: anything except quote, backslash, and 0x00-0x1F
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\"\\',
).filter(lambda c: ord(c) > 0x1F)

# control bytes / NUL — explicitly allowed
_control_char = st.sampled_from(
    [chr(i) for i in range(0x00, 0x20)] + ['\x7f']
)

_string_body_char = _safe_char | _control_char | _esc | _surrogate

_string_body = st.lists(_string_body_char, max_size=12).map(lambda l: "".join(l))
_string = _string_body.map(lambda s: '"' + s + '"')

# malformed string: unterminated
_unterminated_string = _string_body.map(lambda s: '"' + s)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_digits_nz = st.text(alphabet="123456789", min_size=1, max_size=6).flatmap(
    lambda first: st.tuples(st.just(first), st.text(alphabet="0123456789", max_size=6)).map(lambda t: t[0] + t[1])
)

_int_part = st.just("0") | _digits_nz

_frac = _digits.map(lambda d: "." + d)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _digits,
).map(lambda t: t[0] + t[1] + t[2])

# extreme exponents / magnitudes
_extreme_exp = st.sampled_from([
    "e309", "e308", "e-309", "e-400", "e9999", "e-9999",
    "E+308", "E-324", "e+1000",
])
_extreme_mantissa = st.sampled_from([
    "1", "9", "123456789012345678901234567890",
    "0.1", "1.7976931348623157", "2.2250738585072014",
])

def _compose_num(sign, ip, fr, ex):
    return sign + ip + fr + ex

_sign = st.sampled_from(["", "-"])

_valid_number = st.builds(
    _compose_num,
    _sign,
    _int_part,
    _frac | st.just(""),
    _exp | st.just(""),
)

_extreme_number = st.tuples(
    _sign,
    _extreme_mantissa,
    st.just(""),
    _extreme_exp,
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# malformed numbers (leading +, leading dot, trailing dot, leading zeros, hex, lone -)
_malformed_number = st.sampled_from([
    "+1", "+0", ".5", "-.5", "1.", "01", "007", "00", "-01",
    "0x1F", "0X1f", "-", "--1", "1e", "1e+", "1E-", "1..2",
    "1.2.3", "1e1e1", "Infinity", "-Infinity", "NaN",
])

_number = _valid_number | _extreme_number | _malformed_number

# ---------- recursive JSON values ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

def _obj_members(pair_strategy, depth):
    # 1..4 members, with possible trailing comma (accepted) and possible malformed variants
    n = st.integers(min_value=1, max_value=4)
    members = st.lists(pair_strategy, min_size=1, max_size=4)
    trailing = st.booleans()

    def build(args):
        ms, tr = args
        body = ",".join(ms)
        if tr and ms:
            body += ","
        return "{" + body + "}"

    return st.tuples(members, trailing).map(build)

def _empty_obj():
    return st.just("{}")

def _malformed_obj(pair_strategy, value_strategy):
    return st.sampled_from([
        "{",
        "}",
        "{,}",
        "{,}",
        '{"a"1}',
        '{"a":}',
        '{"a":1,,"b":2}',
        '{a:1}',
        "{'a':1}",
        '{"a":1',
        '{"a" 1}',
        '{"a"::1}',
        '{"a":1,}',
        '{"a":1,,}',
        '{:1}',
        '{"a":1,"a":2}',  # duplicate keys (accepted)
    ])

def _arr_members(value_strategy):
    values = st.lists(value_strategy, min_size=1, max_size=4)
    trailing = st.booleans()

    def build(args):
        vs, tr = args
        body = ",".join(vs)
        if tr and vs:
            body += ","
        return "[" + body + "]"

    return st.tuples(values, trailing).map(build)

def _empty_arr():
    return st.just("[]")

def _malformed_arr(value_strategy):
    return st.sampled_from([
        "[",
        "]",
        "[,]",
        "[,1]",
        "[1,,2]",
        "[1 2]",
        "[1;2]",
        "[1,2",
        "[1,2,]",
        "[1,2,,]",
    ])

# ---------- pair ----------

def _pair(value_strategy):
    key = _string
    sep = st.sampled_from([":", ":", ":", " : "])
    return st.tuples(key, sep, value_strategy).map(lambda t: t[0] + t[1] + t[2])

# ---------- top-level recursive construction ----------

def _value_strategy():
    # Use recursive to build nested values; bias toward objects with members.
    return st.recursive(
        # leaves
        _string | _number | st.sampled_from(["true", "false", "null", "TRUE", "False", "nul", "undefined"]),
        # compound
        lambda children: (
            st.one_of(
                _empty_obj(),
                _empty_arr(),
                _obj_members(_pair(children), 0),
                _arr_members(children),
                _malformed_obj(_pair(children), children),
                _malformed_arr(children),
            )
        ),
        max_leaves=20,
    )

_value = _value_strategy()

# top-level json: value EOF. Add whitespace padding and near-valid trailing content.
_pad = st.lists(_ws, max_size=3).map(lambda l: "".join(l))

def _assemble(prefix, val, suffix):
    return prefix + val + suffix

_top = st.tuples(_pad, _value, _pad).map(lambda t: t[0] + t[1] + t[2])

# near-valid top-level variants with trailing garbage (rejected) and malformed roots
_trailing_garbage = st.sampled_from([
    "1abc", "[]xyz", "1 garbage", "true false", "{}x", "null!", "1 2", "{} {}",
    "[1] extra", '"a" "b"',
])

def _with_garbage(val):
    return st.tuples(st.just(val), _trailing_garbage).map(lambda t: t[0] + t[1])

_top_with_garbage = _value.flatmap(_with_garbage)

# deeply nested structures (no depth cap in parser)
def _deep(depth):
    open_c = st.sampled_from(["[", "{"])
    return st.integers(min_value=1, max_value=depth).flatmap(
        lambda n: st.tuples(
            st.just(n),
            st.lists(open_c, min_size=n, max_size=n),
        ).map(lambda t: "".join(t[1]))
    )

_deep_nest = st.integers(min_value=1, max_value=64).flatmap(
    lambda n: st.tuples(
        st.just("[" * n),
        st.just("0"),
        st.just("]" * n),
    ).map(lambda t: t[0] + t[1] + t[2])
)

_deep_obj_nest = st.integers(min_value=1, max_value=32).flatmap(
    lambda n: st.tuples(
        st.just('{"a":' * n),
        st.just("null"),
        st.just("}" * n),
    ).map(lambda t: t[0] + t[1] + t[2])
)

# raw NUL / control byte injections at top level
_raw_control = st.lists(_control_char, min_size=1, max_size=8).map(lambda l: "".join(l))

_top_level_specials = st.one_of(
    st.just(""),
    st.just("   "),
    st.just("\x00"),
    st.just("\x00\x00\x00"),
    st.just("{\x00}"),
    st.just('{"a\x00b":1}'),
    st.just('["\x00"]'),
    st.just("\x00null"),
    st.just("null\x00"),
    _raw_control,
    st.just("{}"),
    st.just("[]"),
    st.just("-"),
    st.just("1e309"),
    st.just("1e-400"),
    st.just('{"a":1,"a":2}'),
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
)

strategy = st.one_of(
    _top,
    _top_with_garbage,
    _deep_nest,
    _deep_obj_nest,
    _top_level_specials,
    _value,
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 45.99,
  "region_coverage_pct": 48.02,
  "least_covered_functions": [
    "hex_value (0% of branches)",
    "json_parse (0% of branches)",
    "json_alloc (33% of branches)",
    "json_parse_ex (45% of branches)",
    "new_value (82% of branches)"
  ]
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.