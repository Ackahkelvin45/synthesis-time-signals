```python
from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.builds(
    lambda h: "\\u" + h,
    st.lists(_hex, min_size=4, max_size=4).map("".join),
)

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_esc = st.one_of(_simple_escapes, _unicode_escape)

# SAFECODEPOINT: anything except '"', '\\', and U+0000..U+001F
_safe_char = st.characters(
    blacklist_categories=(),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# Raw control bytes / NUL: allowed by the harness (length-delimited parser)
_raw_control = st.sampled_from(
    [chr(i) for i in range(0x00, 0x20)]
)

# A single string-body unit
_str_unit = st.one_of(_safe_char, _esc, _raw_control)

# Malformed pieces for near-valid strings
_str_unit_loose = st.one_of(
    _str_unit,
    st.just('"'),          # unescaped quote -> can terminate early
    st.just("\\"),         # dangling backslash
    st.just("\\u"),        # truncated unicode escape
    st.just("\\u12"),      # short hex
    st.just("\\x"),        # invalid escape
)

_string_body = st.lists(_str_unit_loose, min_size=0, max_size=12).map("".join)

# Full JSON string literal (usually well-formed)
_json_string = st.builds(lambda b: '"' + b + '"', _string_body)

# Sometimes deliberately unterminated
_unterminated_string = st.builds(lambda b: '"' + b, _string_body)

# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=18)

_plain_int = st.one_of(
    st.just("0"),
    st.builds(lambda d: d, st.text(alphabet="123456789", min_size=1, max_size=1)
              .flatmap(lambda first: st.text(alphabet="0123456789", min_size=0, max_size=17)
                       .map(lambda rest: first + rest))),
)

_frac = st.builds(lambda d: "." + d, _int_digits)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    _int_digits,
)

# Extreme exponents (overflow like 1e309)
_extreme_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.sampled_from(["309", "310", "400", "999", "1000", "9999", "2147483648", "99999999999999999999"]),
)

_sign = st.sampled_from(["", "-"])

_good_number = st.builds(
    lambda s, i, f, e: s + i + f + e,
    _sign,
    _plain_int,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp, _extreme_exp),
)

# Malformed / lenient numbers
_bad_number = st.one_of(
    st.just("-"),                 # lone '-' (accepted by parser)
    st.builds(lambda d: "+" + d, _int_digits),      # leading +
    st.builds(lambda d: "." + d, _int_digits),      # leading dot
    st.builds(lambda d: d + ".", _int_digits),      # trailing dot
    st.builds(lambda d: "0" + d, _int_digits),      # leading zero
    st.builds(lambda d: "0x" + d, _int_digits),     # hex
    st.just("1e309"),             # overflow -> inf
    st.just("1e-999"),            # underflow
    st.just("01"),
    st.just(".5"),
    st.just("1."),
    st.just("+1"),
)

_number = st.one_of(_good_number, _bad_number)

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null"])

# ---------- malformed fragments ----------

_malformed_fragment = st.sampled_from([
    ",", ",,", ":", "::", "}", "]", "{", "[",
    "true false", "1abc", "garbage", "'x'",
    "//comment", "/* comment */", "{a:1}", "nul\x00byte",
])

# ---------- recursive value/obj/arr ----------

def _make_value_strategy():
    return st.recursive(
        st.one_of(
            _json_string,
            _unterminated_string,
            _number,
            _literal,
            _malformed_fragment,
        ),
        lambda children: st.one_of(
            _obj(children),
            _arr(children),
        ),
        max_leaves=20,
    )


def _key_strategy():
    # Object keys: mostly well-formed strings, sometimes weird
    return st.one_of(
        _json_string,
        st.sampled_from(['"a"', '"a"', '"key"', '"k"', '""', '"\\u0000"', '"\\uD800"']),
        st.builds(lambda b: '"' + b + '"', _string_body),
    )


def _pair(children):
    return st.builds(
        lambda k, v: k + ":" + v,
        _key_strategy(),
        children,
    )


def _obj(children):
    # bias toward objects with members (stressed first-pass path)
    members = st.lists(
        _pair(children),
        min_size=0,
        max_size=6,
    )

    def render(pairs):
        body = ",".join(pairs)
        # occasionally add a single trailing comma (accepted by parser)
        if pairs:
            body = st.one_of(
                st.just(body),
                st.just(body + ","),
            ).example() if False else body
        return "{" + body + "}"

    # Build with optional trailing comma via strategy
    def build(pairs, trailing):
        body = ",".join(pairs)
        if pairs and trailing:
            body = body + ","
        return "{" + body + "}"

    return st.builds(
        build,
        members,
        st.booleans(),
    )


def _arr(children):
    def build(items, trailing):
        body = ",".join(items)
        if items and trailing:
            body = body + ","
        return "[" + body + "]"

    return st.builds(
        build,
        st.lists(children, min_size=0, max_size=6),
        st.booleans(),
    )


_value = _make_value_strategy()

# ---------- top-level document ----------

def _deep_nesting():
    # Deep object nesting to stress first-pass memory measurement.
    depth = st.integers(min_value=1, max_value=200)
    return st.builds(
        lambda d: '{"a":' * d + "0" + "}" * d,
        depth,
    )


def _deep_arr():
    depth = st.integers(min_value=1, max_value=500)
    return st.builds(
        lambda d: "[" * d + "]" * d,
        depth,
    )


_edge_doc = st.sampled_from([
    "{}",
    "[]",
    '{"a":1}',
    '{"a":1,"a":2}',        # duplicate keys (accepted)
    '{"a":1,}',             # trailing comma (accepted)
    "[1,2,]",
    "[1,,2]",               # double comma (rejected)
    "[,]",
    "[,1]",
    '{"a" 1}',              # missing colon
    '{"a":}',
    '{"a":1',
    '{"a":1}}',
    "1e309",                # overflow -> inf
    "-",                    # lone minus
    "1abc",                 # trailing content
    "[]xyz",
    "true false",
    '"\\uD800"',            # lone surrogate escape
    '"\\uDC00\\uD800"',     # reversed surrogate pair
    '"\\u0000"',            # escaped NUL
    '"\x00"',               # raw NUL in string
    '"\\uFFFF"',
    '"unterminated',
    '{"\\u0000":1}',
    "01",
    ".5",
    "1.",
    "+1",
    "0x1F",
    "'x'",
    "{a:1}",
    "//x",
    "/* */1",
])


# ---------- near-crash mutation around the crashing input ----------

_CRASH_SEED = '{"a":1e309,"b":[1,,2],"c":"\\uD800'

def _mutate_near_crash(s):
    # Structural mutations that keep the shape of the crashing input
    # but perturb tokens/boundaries to explore nearby parser branches.
    def flip_quote(x):
        # toggle the final quote-like boundary
        if x.endswith('"'):
            return x[:-1]
        return x + '"'

    def flip_bracket(x):
        if x.endswith("}"):
            return x[:-1] + "]"
        if x.endswith("]"):
            return x[:-1] + "}"
        return x + "}"

    def truncate(x):
        if len(x) <= 1:
            return x
        return x[:-1]

    def dup_tail(x):
        if not x:
            return x
        return x + x[-1]

    def swap_sep(x):
        return x.replace(",", ":", 1) if "," in x else x + ":"

    def inject_escape(x):
        i = x.find("\\u")
        if i >= 0:
            return x[:i] + "\\u" + x[i + 2:]
        return x + "\\u"

    def inject_nul(x):
        return x + "\x00"

    def inject_comma(x):
        return x + ","

    return st.one_of(
        st.just(s),
        st.builds(flip_quote, st.just(s)),
        st.builds(flip_bracket, st.just(s)),
        st.builds(truncate, st.just(s)),
        st.builds(dup_tail, st.just(s)),
        st.builds(swap_sep, st.just(s)),
        st.builds(inject_escape, st.just(s)),
        st.builds(inject_nul, st.just(s)),
        st.builds(inject_comma, st.just(s)),
        st.builds(lambda x: x + ",", st.just(s)),
        st.builds(lambda x: x + "}", st.just(s)),
        st.builds(lambda x: x + "]", st.just(s)),
        st.builds(lambda x: x + ":", st.just(s)),
        st.builds(lambda x: x + "\\", st.just(s)),
        st.builds(lambda x: x + '"', st.just(s)),
        st.builds(lambda x: x + "0", st.just(s)),
        st.builds(lambda x: x + "e309", st.just(s)),
        st.builds(lambda x: x[:-1] + "1" + x[-1:], st.just(s)),
        st.builds(lambda x: x[:1] + x, st.just(s)),
        st.builds(lambda x: x + x, st.just(s)),
    )


_near_crash = _mutate_near_crash(_CRASH_SEED)


strategy = st.one_of(
    _edge_doc,
    _deep_nesting(),
    _deep_arr(),
    # objects with members (heavily weighted)
    _obj(_value),
    _obj(_value),
    _obj(_value),
    _arr(_value),
    _value,
    # bare values with trailing junk
    st.builds(lambda v: v + "xyz", _value),
    st.builds(lambda v: v + " garbage", _value),
    # intensified fuzzing near the crashing input
    _near_crash,
    _near_crash,
    _near_crash,
)
```