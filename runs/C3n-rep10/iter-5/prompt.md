Here is the current Hypothesis strategy:

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

# Structural mutation primitives applied to a seed string.
_QUOTES = ['"', "'", "\\", ""]
_BRACKETS = ["}", "]", ")", "{", "[", "("]
_SEPS = [",", ":", ";", " ", "", "\t", "\n"]
_HEXISH = ["0", "1", "9", "a", "f", "F", "e", "E", "u", "x", "\\", "."]
_TAILS = ["", ",", "}", "]", ":", "\\", '"', "0", "e309", "e-999", "\x00", " ", "null", "true"]


def _mutate_near_crash(s):
    # Structural mutations that keep the shape of the crashing input
    # but perturb tokens/boundaries to explore nearby parser branches.

    def flip_quote(x):
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

    # --- new intensified structural mutators ---

    def splice_at(x, i, tok):
        i = max(0, min(i, len(x)))
        return x[:i] + tok + x[i:]

    def del_at(x, i):
        if not x:
            return x
        i = max(0, min(i, len(x) - 1))
        return x[:i] + x[i + 1:]

    def replace_at(x, i, tok):
        if not x:
            return tok
        i = max(0, min(i, len(x) - 1))
        return x[:i] + tok + x[i + 1:]

    def swap_at(x, i, j):
        if len(x) < 2:
            return x
        i %= len(x)
        j %= len(x)
        lst = list(x)
        lst[i], lst[j] = lst[j], lst[i]
        return "".join(lst)

    def dup_slice(x, i):
        if not x:
            return x
        i = max(0, min(i, len(x)))
        return x[:i] + x[i:i + 1] + x[i:]

    def cut_span(x, a, b):
        if not x:
            return x
        a %= len(x)
        b %= len(x)
        if a > b:
            a, b = b, a
        return x[:a] + x[b:]

    def wrap(x, pre, post):
        return pre + x + post

    def inject_token(x, tok, i):
        return splice_at(x, i, tok)

    def json_structural_perturb(x):
        # Insert a structural token at a quote/bracket/colon boundary.
        for ch in ('"', "{", "}", "[", "]", ":", ","):
            k = x.find(ch)
            if k >= 0:
                return x[:k] + ch + x[k:]
        return x + "{}"

    def nest_deeper(x):
        return "[" + x + "]"

    def nest_object(x):
        return '{"k":' + x + "}"

    def unbalanced_open(x):
        return x + "{" * 1

    def unbalanced_close(x):
        return "}" * 1 + x

    def inject_number_junk(x):
        return x + "1e309"

    def inject_unicode_pair(x):
        return x + '"\\uD800\\uDC00"'

    def inject_lone_surrogate(x):
        return x + '"\\uD800"'

    def inject_bad_escape(x):
        return x + '"\\uZZZZ"'

    def inject_control(x):
        return x + chr(0x01)

    def inject_high_cp(x):
        return x + "\U0010FFFF"

    def split_escape(x):
        i = x.find("\\u")
        if i >= 0 and len(x) > i + 2:
            return x[:i + 2] + " " + x[i + 2:]
        return x

    def double_backslash(x):
        return x.replace("\\", "\\\\", 1)

    def make_hex_overflow(x):
        i = x.find("\\u")
        if i >= 0:
            return x[:i] + "\\uFFFF" + x[i + 6:]
        return x + "\\uFFFF"

    def swap_braces(x):
        return x.replace("{", "\x00").replace("}", "{").replace("\x00", "}")

    def swap_brackets(x):
        return x.replace("[", "\x00").replace("]", "[").replace("\x00", "]")

    def rotate(x):
        if len(x) < 2:
            return x
        return x[1:] + x[:1]

    def reverse(x):
        return x[::-1]

    def repeat_prefix(x):
        if not x:
            return x
        return x[:1] * 2 + x

    def repeat_suffix(x):
        if not x:
            return x
        return x + x[-1:] * 2

    def close_all(x):
        opens = x.count("{") + x.count("[")
        closes = x.count("}") + x.count("]")
        return x + "}" * max(0, opens - closes)

    def open_all(x):
        opens = x.count("{") + x.count("[")
        closes = x.count("}") + x.count("]")
        return "{" * max(0, closes - opens) + x

    def inject_key_no_value(x):
        return x + '{"k"'

    def inject_value_no_key(x):
        return x + ':"v"'

    def inject_double_colon(x):
        return x + "::"

    def inject_double_comma(x):
        return x + ",,"

    def inject_missing_colon(x):
        return x + '{"a" 1}'

    def inject_trailing_content(x):
        return x + "xyz"

    def inject_leading_junk(x):
        return "xyz" + x

    def inject_whitespace(x):
        return x + " \t\n\r"

    def inject_bom(x):
        return "\ufeff" + x

    def inject_long_number(x):
        return x + "9" * 30

    def inject_negative_zero(x):
        return x + "-0"

    def inject_plus_number(x):
        return x + "+1"

    def inject_leading_zero(x):
        return x + "01"

    def inject_hex_number(x):
        return x + "0x1F"

    def inject_dot_number(x):
        return x + ".5"

    def inject_trailing_dot(x):
        return x + "1."

    def inject_lone_minus(x):
        return x + "-"

    def inject_nan_like(x):
        return x + "NaN"

    def inject_inf_like(x):
        return x + "Infinity"

    def inject_comment(x):
        return x + "/*x*/"

    def inject_line_comment(x):
        return x + "//x\n"

    def inject_single_quote(x):
        return x + "'x'"

    def inject_dollar(x):
        return x + "$"

    def inject_at(x):
        return x + "@"

    def inject_percent(x):
        return x + "%"

    def inject_amp(x):
        return x + "&"

    def inject_pipe(x):
        return x + "|"

    def inject_caret(x):
        return x + "^"

    def inject_tilde(x):
        return x + "~"

    def inject_backtick(x):
        return x + "`"

    def inject_semicolon(x):
        return x + ";"

    def inject_equals(x):
        return x + "="

    def inject_question(x):
        return x + "?"

    def inject_hash(x):
        return x + "#"

    def inject_slash(x):
        return x + "/"

    def inject_star(x):
        return x + "*"

    def inject_dash(x):
        return x + "-"

    def inject_underscore(x):
        return x + "_"

    def inject_paren(x):
        return x + "()"

    return st.one_of(
        # original mutations
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
        # intensified structural mutations
        st.builds(lambda x: truncate(x), st.just(s)),
        st.builds(lambda x: truncate(truncate(x)), st.just(s)),
        st.builds(lambda x: x[: len(x) // 2], st.just(s)),
        st.builds(lambda x: x[len(x) // 2:], st.just(s)),
        st.builds(lambda x: rotate(x), st.just(s)),
        st.builds(lambda x: reverse(x), st.just(s)),
        st.builds(lambda x: repeat_prefix(x), st.just(s)),
        st.builds(lambda x: repeat_suffix(x), st.just(s)),
        st.builds(lambda x: swap_braces(x), st.just(s)),
        st.builds(lambda x: swap_brackets(x), st.just(s)),
        st.builds(lambda x: close_all(x), st.just(s)),
        st.builds(lambda x: open_all(x), st.just(s)),
        st.builds(lambda x: nest_deeper(x), st.just(s)),
        st.builds(lambda x: nest_object(x), st.just(s)),
        st.builds(lambda x: unbalanced_open(x), st.just(s)),
        st.builds(lambda x: unbalanced_close(x), st.just(s)),
        st.builds(lambda x: wrap(x, "[", "]"), st.just(s)),
        st.builds(lambda x: wrap(x, "{", "}"), st.just(s)),
        st.builds(lambda x: wrap(x, '"', '"'), st.just(s)),
        st.builds(lambda x: wrap(x, "", ","), st.just(s)),
        st.builds(lambda x: wrap(x, ",", ""), st.just(s)),
        st.builds(lambda x: json_structural_perturb(x), st.just(s)),
        st.builds(lambda x: inject_number_junk(x), st.just(s)),
        st.builds(lambda x: inject_unicode_pair(x), st.just(s)),
        st.builds(lambda x: inject_lone_surrogate(x), st.just(s)),
        st.builds(lambda x: inject_bad_escape(x), st.just(s)),
        st.builds(lambda x: inject_control(x), st.just(s)),
        st.builds(lambda x: inject_high_cp(x), st.just(s)),
        st.builds(lambda x: split_escape(x), st.just(s)),
        st.builds(lambda x: double_backslash(x), st.just(s)),
        st.builds(lambda x: make_hex_overflow(x), st.just(s)),
        st.builds(lambda x: inject_key_no_value(x), st.just(s)),
        st.builds(lambda x: inject_value_no_key(x), st.just(s)),
        st.builds(lambda x: inject_double_colon(x), st.just(s)),
        st.builds(lambda x: inject_double_comma(x), st.just(s)),
        st.builds(lambda x: inject_missing_colon(x), st.just(s)),
        st.builds(lambda x: inject_trailing_content(x), st.just(s)),
        st.builds(lambda x: inject_leading_junk(x), st.just(s)),
        st.builds(lambda x: inject_whitespace(x), st.just(s)),
        st.builds(lambda x: inject_bom(x), st.just(s)),
        st.builds(lambda x: inject_long_number(x), st.just(s)),
        st.builds(lambda x: inject_negative_zero(x), st.just(s)),
        st.builds(lambda x: inject_plus_number(x), st.just(s)),
        st.builds(lambda x: inject_leading_zero(x), st.just(s)),
        st.builds(lambda x: inject_hex_number(x), st.just(s)),
        st.builds(lambda x: inject_dot_number(x), st.just(s)),
        st.builds(lambda x: inject_trailing_dot(x), st.just(s)),
        st.builds(lambda x: inject_lone_minus(x), st.just(s)),
        st.builds(lambda x: inject_nan_like(x), st.just(s)),
        st.builds(lambda x: inject_inf_like(x), st.just(s)),
        st.builds(lambda x: inject_comment(x), st.just(s)),
        st.builds(lambda x: inject_line_comment(x), st.just(s)),
        st.builds(lambda x: inject_single_quote(x), st.just(s)),
        st.builds(lambda x: inject_dollar(x), st.just(s)),
        st.builds(lambda x: inject_at(x), st.just(s)),
        st.builds(lambda x: inject_percent(x), st.just(s)),
        st.builds(lambda x: inject_amp(x), st.just(s)),
        st.builds(lambda x: inject_pipe(x), st.just(s)),
        st.builds(lambda x: inject_caret(x), st.just(s)),
        st.builds(lambda x: inject_tilde(x), st.just(s)),
        st.builds(lambda x: inject_backtick(x), st.just(s)),
        st.builds(lambda x: inject_semicolon(x), st.just(s)),
        st.builds(lambda x: inject_equals(x), st.just(s)),
        st.builds(lambda x: inject_question(x), st.just(s)),
        st.builds(lambda x: inject_hash(x), st.just(s)),
        st.builds(lambda x: inject_slash(x), st.just(s)),
        st.builds(lambda x: inject_star(x), st.just(s)),
        st.builds(lambda x: inject_dash(x), st.just(s)),
        st.builds(lambda x: inject_underscore(x), st.just(s)),
        st.builds(lambda x: inject_paren(x), st.just(s)),
        # positional splice/delete/replace over a range
        st.builds(
            lambda x, i, tok: splice_at(x, i, tok),
            st.just(s),
            st.integers(min_value=0, max_value=len(s)),
            st.sampled_from(_SEPS + _HEXISH + _BRACKETS + _QUOTES),
        ),
        st.builds(
            lambda x, i: del_at(x, i),
            st.just(s),
            st.integers(min_value=0, max_value=max(0, len(s) - 1)),
        ),
        st.builds(
            lambda x, i, tok: replace_at(x, i, tok),
            st.just(s),
            st.integers(min_value=0, max_value=max(0, len(s) - 1)),
            st.sampled_from(_SEPS + _HEXISH + _BRACKETS + _QUOTES),
        ),
        st.builds(
            lambda x, i, j: swap_at(x, i, j),
            st.just(s),
            st.integers(min_value=0, max_value=max(0, len(s) - 1)),
            st.integers(min_value=0, max_value=max(0, len(s) - 1)),
        ),
        st.builds(
            lambda x, i: dup_slice(x, i),
            st.just(s),
            st.integers(min_value=0, max_value=len(s)),
        ),
        st.builds(
            lambda x, a, b: cut_span(x, a, b),
            st.just(s),
            st.integers(min_value=0, max_value=max(0, len(s) - 1)),
            st.integers(min_value=0, max_value=max(0, len(s) - 1)),
        ),
        st.builds(
            lambda x, tok, i: inject_token(x, tok, i),
            st.just(s),
            st.sampled_from(_TAILS + _BRACKETS + _SEPS),
            st.integers(min_value=0, max_value=len(s)),
        ),
        # composite multi-step mutations
        st.builds(lambda x: nest_object(nest_deeper(x)), st.just(s)),
        st.builds(lambda x: nest_deeper(nest_object(x)), st.just(s)),
        st.builds(lambda x: close_all(nest_deeper(x)), st.just(s)),
        st.builds(lambda x: open_all(nest_object(x)), st.just(s)),
        st.builds(lambda x: inject_comma(truncate(x)), st.just(s)),
        st.builds(lambda x: inject_nul(truncate(x)), st.just(s)),
        st.builds(lambda x: inject_escape(truncate(x)), st.just(s)),
        st.builds(lambda x: flip_bracket(truncate(x)), st.just(s)),
        st.builds(lambda x: flip_quote(truncate(x)), st.just(s)),
        st.builds(lambda x: double_backslash(truncate(x)), st.just(s)),
        st.builds(lambda x: swap_sep(truncate(x)), st.just(s)),
        st.builds(lambda x: dup_tail(truncate(x)), st.just(s)),
        st.builds(lambda x: rotate(truncate(x)), st.just(s)),
        st.builds(lambda x: reverse(truncate(x)), st.just(s)),
        st.builds(lambda x: inject_number_junk(truncate(x)), st.just(s)),
        st.builds(lambda x: inject_lone_surrogate(truncate(x)), st.just(s)),
        st.builds(lambda x: inject_bad_escape(truncate(x)), st.just(s)),
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
    _near_crash,
    _near_crash,
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 40.3,
  "region_coverage_pct": 43.63,
  "least_covered_functions": [
    "hex_value (0% of branches)",
    "json_parse (0% of branches)",
    "json_alloc (33% of branches)",
    "json_parse_ex (38% of branches)",
    "new_value (79% of branches)"
  ]
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.