```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Safe, ordinary string characters (no quote, no backslash, no control).
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

# Raw control / NUL bytes that the parser accepts inside strings.
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

# Escape sequences: simple escapes plus \uXXXX (including surrogate ranges).
_simple_escape = st.sampled_from([r"\"", r"\\", r"\/", r"\b", r"\f", r"\n", r"\r", r"\t"])
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escape = st.builds(lambda h: "\\u" + h, _hex4)

# Lone surrogates (rejected by the parser) and valid pairs.
_lone_surrogate_escape = st.sampled_from(
    ["\\ud800", "\\udc00", "\\udfff", "\\udabc", "\\udC00"]
)

# Valid surrogate pairs, which the parser should combine into one code point.
_valid_surrogate_pair = st.builds(
    lambda hi, lo: "\\u" + hi + "\\u" + lo,
    st.sampled_from(["d800", "d801", "d83d", "dbff"]),
    st.sampled_from(["dc00", "dc01", "de00", "dfff"]),
)

_string_body = st.one_of(
    st.lists(_safe_char, min_size=0, max_size=12).map("".join),
    st.lists(_raw_control, min_size=1, max_size=4).map("".join),
    st.lists(
        st.one_of(_safe_char, _simple_escape, _unicode_escape, _raw_control),
        min_size=0,
        max_size=10,
    ).map("".join),
    _lone_surrogate_escape,
    _valid_surrogate_pair,
)


def _quoted(body):
    return '"' + body + '"'


# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_leading_zero_int = st.builds(lambda d: "0" + d, _int_digits)
_big_int = st.text(alphabet="0123456789", min_size=1, max_size=30)

_exp = st.builds(
    lambda sign, digits: "e" + sign + digits,
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_frac = st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=6))

_number = st.one_of(
    # plain ints and negative ints
    st.builds(lambda s, d: s + d, st.sampled_from(["", "-"]), st.text(alphabet="123456789", min_size=1, max_size=6)),
    st.just("0"),
    # extreme magnitudes / overflow
    st.sampled_from(["1e309", "-1e309", "1e999", "1e-999", "9" * 40, "-" + "9" * 40]),
    # leading zero (accepted by parser)
    _leading_zero_int,
    # trailing dot (accepted by parser)
    st.builds(lambda d: d + ".", _big_int),
    # hex (accepted by parser)
    st.builds(lambda h: "0x" + h, st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8)),
    # normal floats with exponent
    st.builds(lambda i, f, e: i + f + e, _big_int, _frac, _exp),
    st.builds(lambda i, e: i + e, _big_int, _exp),
    # malformed-ish numbers
    st.sampled_from(["-", "+1", ".5", "-.5", "01", "00", "1.", "1e", "1e+", "1e-", "0x", "0xG"]),
)


# ---------- recursive structure ----------

# Keys: strings plus a few duplicate-key generators.
_key = st.one_of(
    _string_body.map(_quoted),
    st.sampled_from(['"a"', '"a"', '"key"', '""', '"\\u0000"']),
)

# Malformed fragments for near-valid-but-broken inputs.
_malformed = st.sampled_from(
    [
        "[1,,2]",
        "[,1]",
        "[1,]",
        '{"a":1,}',
        '{"a" 1}',
        '{"a":}',
        "{:1}",
        '{"a":1 "b":2}',
        "[1 2]",
        '"unterminated',
        "'single'",
        "{unquoted:1}",
        "[1,2",
        '{"a":1',
        "[}",
        "{]",
        "}",
        "]",
        ",",
        ":",
        "",
        "   ",
        "NaN",
        "Infinity",
        "-Infinity",
    ]
)


def _make_strategy():
    return st.recursive(
        st.one_of(
            _number,
            _string_body.map(_quoted),
            st.sampled_from(["true", "false", "null"]),
            _malformed,
        ),
        lambda children: st.one_of(
            # arrays
            st.lists(children, min_size=0, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]"),
            # objects
            st.lists(
                st.tuples(_key, children).map(lambda kv: kv[0] + ":" + kv[1]),
                min_size=0,
                max_size=5,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
            # duplicate keys explicitly
            st.builds(
                lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
                _key,
                children,
                children,
            ),
        ),
        max_leaves=30,
    )


_value = _make_strategy()


# Deep nesting near the ~1000 level limit (accepted at 1000, rejected at 1001).
def _deep(depth):
    return "[" * depth + "0" + "]" * depth


_deep_nesting = st.one_of(
    st.integers(min_value=990, max_value=1000).map(_deep),
    st.integers(min_value=1001, max_value=1010).map(_deep),
    st.integers(min_value=1, max_value=50).map(_deep),
    st.integers(min_value=990, max_value=1000).map(lambda d: "{" + '"a":' * d + "0" + "}" * d),
    # Mixed nesting around the limit boundary to stress depth accounting
    # (arrays inside objects and vice-versa at the exact cap).
    st.builds(
        lambda d, inner: "[" * d + inner + "]" * d,
        st.integers(min_value=490, max_value=500),
        st.sampled_from(["0", "{}", "[]", '{"a":0}', "[0]"]),
    ),
    st.builds(
        lambda d, inner: "{" + '"a":' * d + inner + "}" * d,
        st.integers(min_value=490, max_value=500),
        st.sampled_from(["0", "{}", "[]", '{"a":0}', "[0]"]),
    ),
)

# Leading BOM (accepted) and trailing content (accepted).
_trailing = st.one_of(
    st.just(""),
    st.sampled_from(["\x00", "abc", " 1 2", "\n", "junk"]),
)

# Whitespace injection around structural tokens (parser should tolerate).
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "\r\n", "  "])


# Interleave arbitrary whitespace between top-level structural characters
# of a valid value to exercise the tokenizer's whitespace handling.
def _inject_ws(s):
    out = []
    for ch in s:
        out.append(ch)
        if ch in "{}[],:":
            out.append(" ")
    return "".join(out)


_whitespace_wrapped = st.builds(
    lambda v, pre, post: pre + _inject_ws(v) + post,
    _value,
    _ws,
    _ws,
)

# Pair of values separated by whitespace (tests trailing-content handling).
_value_pair = st.builds(lambda a, b, w: a + w + b, _value, _value, _ws)


# ---------- token-boundary mutations ----------

# Insert a single structural / token-splitting character at a random position
# inside an otherwise valid value to probe the tokenizer & parser error paths.
_break_char = st.sampled_from(list('{}[],:"\\') + ["\x00", " ", "\n", "\t"])


def _insert_at(s, idx, ch):
    idx = min(max(idx, 0), len(s))
    return s[:idx] + ch + s[idx:]


_break_insertion = st.builds(
    _insert_at,
    _value,
    st.integers(min_value=0, max_value=64),
    _break_char,
)

# Truncate a valid value at an arbitrary point (unterminated structures).
_break_truncation = st.builds(
    lambda s, n: s[:n],
    _value,
    st.integers(min_value=0, max_value=64),
)

# Duplicate a slice of a valid value (tests repeated tokens / separators).
_break_duplication = st.builds(
    lambda s, i, j: s + s[i:j],
    _value,
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=0, max_value=8),
)

# Swap two characters to create near-miss structural errors.
def _swap(s, i, j):
    if not s:
        return s
    i = i % len(s)
    j = j % len(s)
    lst = list(s)
    lst[i], lst[j] = lst[j], lst[i]
    return "".join(lst)


_break_swap = st.builds(
    _swap,
    _value,
    st.integers(min_value=0, max_value=32),
    st.integers(min_value=0, max_value=32),
)


strategy = st.one_of(
    _value,
    _deep_nesting,
    st.builds(lambda v, t: v + t, _value, _trailing),
    st.builds(lambda v: "\ufeff" + v, _value),
    st.builds(lambda v: v + "\x00", _value),
    st.builds(lambda v: v + "\x00" + v, _value),
    _whitespace_wrapped,
    _value_pair,
    _break_insertion,
    _break_truncation,
    _break_duplication,
    _break_swap,
)
```