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

_string_body = st.one_of(
    st.lists(_safe_char, min_size=0, max_size=12).map("".join),
    st.lists(_raw_control, min_size=1, max_size=4).map("".join),
    st.lists(
        st.one_of(_safe_char, _simple_escape, _unicode_escape, _raw_control),
        min_size=0,
        max_size=10,
    ).map("".join),
    _lone_surrogate_escape,
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
)

# Leading BOM (accepted) and trailing content (accepted).
_trailing = st.one_of(
    st.just(""),
    st.sampled_from(["\x00", "abc", " 1 2", "\n", "junk"]),
)

# ---------- improved: structural mutation of valid values ----------

# Randomly delete, duplicate, or insert a delimiter into a generated value
# to produce near-valid inputs that stress the parser's error recovery.
_delims = st.sampled_from([",", ":", "[", "]", "{", "}", '"', " ", "\x00"])


def _mutate(s, op, pos, ch):
    if not s:
        return ch
    i = pos % (len(s) + 1)
    if op == 0:  # delete
        if i < len(s):
            return s[:i] + s[i + 1:]
        return s
    if op == 1:  # insert
        return s[:i] + ch + s[i:]
    # duplicate a slice
    j = (i + 1 + pos % 3) % (len(s) + 1)
    lo, hi = min(i, j), max(i, j)
    return s[:hi] + s[lo:hi] + s[hi:]


_mutated = st.builds(
    _mutate,
    _value,
    st.integers(min_value=0, max_value=2),
    st.integers(min_value=0, max_value=1000),
    _delims,
)

# Truncate a valid value at a random point (tests partial-input handling).
_truncated = st.builds(
    lambda s, k: s[: k % (len(s) + 1)] if s else s,
    _value,
    st.integers(min_value=0, max_value=1000),
)

# ---------- improved: multi-mutation chains ----------

# Apply several mutations in sequence to reach deeper, rarer error states.
_multi_mutated = st.builds(
    lambda s, ops, poss, chs: _apply_mutations(s, ops, poss, chs),
    _value,
    st.lists(st.integers(min_value=0, max_value=2), min_size=2, max_size=5),
    st.lists(st.integers(min_value=0, max_value=1000), min_size=2, max_size=5),
    st.lists(_delims, min_size=2, max_size=5),
)


def _apply_mutations(s, ops, poss, chs):
    n = min(len(ops), len(poss), len(chs))
    for k in range(n):
        s = _mutate(s, ops[k], poss[k], chs[k])
    return s


# ---------- improved: whitespace / separator fuzzing ----------

# JSON allows arbitrary whitespace between tokens; stress the lexer with
# unusual whitespace placement and amounts.
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\n", "\t\r\n"])


def _space_out(tokens, ws_choices):
    out = []
    for idx, tok in enumerate(tokens):
        out.append(tok)
        if idx < len(ws_choices):
            out.append(ws_choices[idx])
    return "".join(out)


_ws_value = st.builds(
    lambda v, w: _space_out(list(v), w),
    _value.map(lambda s: list(s)),
    st.lists(_ws, min_size=0, max_size=40),
)

# ---------- improved: boundary-length strings ----------

# Strings at parser-relevant size boundaries (empty, single char, long runs).
_long_safe = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ", min_size=0, max_size=200)
_boundary_string = st.builds(
    lambda body: '"' + body + '"',
    st.one_of(
        st.just(""),
        st.text(alphabet="a", min_size=1, max_size=1),
        _long_safe,
        st.text(alphabet="a", min_size=1000, max_size=1100),
    ),
)

# ---------- improved: surrogate-pair edge cases ----------

# Valid high+low surrogate pairs and near-misses (high-high, low-low).
_surrogate_pair = st.one_of(
    st.builds(
        lambda hi, lo: "\\u" + hi + "\\u" + lo,
        st.sampled_from(["d800", "d801", "dbff", "dabc"]),
        st.sampled_from(["dc00", "dc01", "dfff", "dabc"]),
    ),
    # invalid pairings
    st.builds(
        lambda a, b: "\\u" + a + "\\u" + b,
        st.sampled_from(["d800", "dbff"]),
        st.sampled_from(["d800", "dbff"]),
    ),
    st.builds(
        lambda a, b: "\\u" + a + "\\u" + b,
        st.sampled_from(["dc00", "dfff"]),
        st.sampled_from(["dc00", "dfff"]),
    ),
)

_surrogate_string = st.builds(lambda p: '"' + p + '"', _surrogate_pair)

strategy = st.one_of(
    _value,
    _deep_nesting,
    st.builds(lambda v, t: v + t, _value, _trailing),
    st.builds(lambda v: "\ufeff" + v, _value),
    st.builds(lambda v: v + "\x00", _value),
    st.builds(lambda v: v + "\x00" + v, _value),
    _mutated,
    _truncated,
    _multi_mutated,
    _ws_value,
    _boundary_string,
    _surrogate_string,
)
```