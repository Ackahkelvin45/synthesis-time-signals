```python
from hypothesis import strategies as st
import json

# ---------- leaf generators ----------

# Safe string characters (no quote/backslash/control)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) >= 0x20)

# Raw NUL and control bytes we want to emit inside strings (allowed by harness)
_control_chars = st.sampled_from(["\x00", "\x01", "\x1f", "\x0b", "\x0c", "\x7f"])

# Escape sequences
_simple_escapes = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escapes = _hex4.map(lambda h: "\\u" + h)
# Lone surrogates & paired surrogates
_surrogate_escapes = st.sampled_from([
    "\\ud800", "\\udfff", "\\udc00", "\\ud83d\\ude00", "\\ud800\\ud800",
])

_escape = st.one_of(_simple_escapes, _unicode_escapes, _surrogate_escapes)

# Body pieces of a string
_string_piece = st.one_of(
    _safe_chars.map(str),
    _control_chars,
    _escape,
)

# A valid-ish JSON string literal (with quotes)
_json_string = st.lists(_string_piece, max_size=8).map(lambda parts: '"' + "".join(parts) + '"')

# Unterminated strings (missing closing quote)
_unterminated_string = st.lists(_string_piece, min_size=0, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)

# ---------- number generators ----------

_int_no_leading_zero = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
)
_optional_minus = st.booleans().map(lambda b: "-" if b else "")
_frac = st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n))
_exp = st.builds(
    lambda e, sign, digits: e + sign + digits,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10**9).map(str),
)

_valid_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + (fr or "") + (ex or ""),
    _optional_minus,
    _int_no_leading_zero,
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
)

# Extreme magnitudes / overflow
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e400", "-1e400",
    "1e999999", "9" * 40, "-" + "9" * 40,
    "0e0", "0E+0", "-0", "-0.0", "0.0e-0",
    "1" + "0" * 300,
    "1." + "0" * 50 + "e" + "9" * 10,
    "123456789012345678901234567890",
])

# Malformed numbers (rejected by parser but valuable)
_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-", "--1", "1e", "1e+",
    "1.2.3", "1..2", "1e1.5", "- 1", "0b101", "Infinity", "NaN",
    "1_000", "١٢٣",
])

_number = st.one_of(_valid_number, _extreme_number, _bad_number)

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null", "True", "FALSE", "NULL", "nul", "tru"])

# ---------- recursive structure ----------

# Forward declaration via st.recursive
_value = st.deferred(lambda: _value_strategy)

# Key for object pairs: prefer strings, sometimes malformed (bare keys)
_key = st.one_of(_json_string, _unterminated_string)

# A pair: key + colon + value, sometimes missing colon (malformed)
_pair = st.one_of(
    st.builds(lambda k, v: k + ":" + v, _key, _value),
    st.builds(lambda k, v: k + v, _key, _value),  # missing colon
)

# Object: prefer with members (stressed path)
_obj_with_members = st.builds(
    lambda pairs: "{" + ",".join(pairs) + "}",
    st.lists(_pair, min_size=1, max_size=5),
)
_obj_empty = st.just("{}")
_obj_trailing_comma = st.builds(
    lambda pairs: "{" + ",".join(pairs) + ",}",
    st.lists(_pair, min_size=1, max_size=4),
)
_obj_double_comma = st.builds(
    lambda pairs: "{" + ",".join(pairs) + ",,}",
    st.lists(_pair, min_size=1, max_size=3),
)
_obj = st.one_of(_obj_with_members, _obj_with_members, _obj_with_members, _obj_empty, _obj_trailing_comma, _obj_double_comma)

_arr_with_members = st.builds(
    lambda vs: "[" + ",".join(vs) + "]",
    st.lists(_value, min_size=1, max_size=5),
)
_arr_empty = st.just("[]")
_arr_trailing_comma = st.builds(
    lambda vs: "[" + ",".join(vs) + ",]",
    st.lists(_value, min_size=1, max_size=4),
)
_arr_double_comma = st.builds(
    lambda vs: "[" + ",".join(vs) + ",,]",
    st.lists(_value, min_size=1, max_size=3),
)
_arr_leading_comma = st.builds(
    lambda vs: "[," + ",".join(vs) + "]",
    st.lists(_value, min_size=1, max_size=3),
)
_arr = st.one_of(_arr_with_members, _arr_with_members, _arr_with_members, _arr_empty, _arr_trailing_comma, _arr_double_comma, _arr_leading_comma)

# Base (non-recursive) values
_base_value = st.one_of(
    _json_string,
    _unterminated_string,
    _number,
    _literal,
)

_value_strategy = st.recursive(
    _base_value,
    lambda children: st.one_of(_obj.map(lambda o: o), _arr.map(lambda a: a)),
    max_leaves=20,
)

# ---------- deep nesting (bias toward object depth for the stressed first-pass) ----------

def _deep_obj(depth):
    inner = _pair
    # build nested objects: {"k": {"k": {...}}}
    return st.builds(
        lambda d, p: "{" * d + p + "}" * d,
        st.just(depth),
        _pair,
    )

def _deep_arr(depth):
    return st.builds(
        lambda d, v: "[" * d + v + "]" * d,
        st.just(depth),
        _value,
    )

_deep = st.one_of(
    _deep_obj(50),
    _deep_obj(200),
    _deep_obj(1000),
    _deep_arr(50),
    _deep_arr(200),
    _deep_arr(1000),
    _deep_arr(5000),
)

# ---------- top-level wrappers ----------

# Trailing content after a complete value (rejected by parser)
_trailing_content = st.builds(
    lambda v, t: v + t,
    _value,
    st.sampled_from(["abc", " xyz", "1", "true false", "[]", "}", "]"]),
)

# Leading BOM or garbage
_leading_garbage = st.builds(
    lambda g, v: g + v,
    st.sampled_from(["\ufeff", "\x00", " ", "\t", "\n", "\r", "//x\n", "/* */"]),
    _value,
)

# Whitespace-padded
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  \n\t "])
_padded = st.builds(
    lambda a, v, b: a + v + b,
    _ws, _value, _ws,
)

# Bare tokens / malformed top-level
_bare = st.sampled_from([
    "", " ", "\x00", "{", "}", "[", "]", ",", ":", '"',
    "{\"a\"}", "{\"a\":}", "{:1}", "[1 2]", "{\"a\":1 \"b\":2}",
    "tru", "nul", "'x'", "{a:1}", "//x", "/* */",
])

# ---------- near-crash mutation (intensified) ----------

# The crashing input region: deeply nested structures near the depth limit.
# Intensify by mutating structurally around it: perturb depth by ±1..few,
# add/remove/duplicate delimiters, splice malformed tokens at the boundary.
_crash_seed = st.sampled_from([
    "[" * 5000 + "]" * 5000,
    "{" * 1000 + "}" * 1000,
    "[" * 1000 + "]" * 1000,
    "[" * 200 + "]" * 200,
    "{" * 200 + "}" * 200,
])

# Structural mutations around the crash seed: depth perturbation.
def _perturb_depth(seed):
    return st.builds(
        lambda s, delta: s + ("[" * delta if delta > 0 else "]" * (-delta)),
        st.just(seed),
        st.integers(min_value=-5, max_value=5),
    )

# Delimiter insertions/deletions at the boundary.
def _mutate_boundary(seed):
    return st.builds(
        lambda s, pre, post: pre + s + post,
        st.just(seed),
        st.sampled_from(["", "[", "{", "]", "}", ",", ":", '"', "\x00"]),
        st.sampled_from(["", "[", "{", "]", "}", ",", ":", '"', "\x00"]),
    )

# Splice a malformed token into the seed near the boundary.
def _splice_token(seed):
    return st.builds(
        lambda s, mid, tok: s[:len(s)//2] + tok + s[len(s)//2:],
        st.just(seed),
        st.sampled_from(["", " ", ","]),
        st.sampled_from([
            "", "x", "1", "true", "null", ":", ",", "[", "]", "{", "}",
            '"', "\x00", "\x01", "\\", "\\u", "e", "-",
        ]),
    )

# Truncate the seed at a boundary (near-crash: cut off closing delimiters).
def _truncate(seed):
    return st.builds(
        lambda s, n: s[:n],
        st.just(seed),
        st.integers(min_value=0, max_value=len(seed)),
    )

# Duplicate a chunk of the seed (intensify nesting pressure).
def _duplicate(seed):
    return st.builds(
        lambda s, a, b: s[:a] + s[a:b] + s[a:],
        st.just(seed),
        st.integers(min_value=0, max_value=len(seed)),
        st.integers(min_value=0, max_value=len(seed)),
    )

# Intensified structural mutation around the crash boundary: multi-step
# mutations (perturb + boundary + splice + truncate + duplicate composed)
# and depth sweeps across a range of nesting limits.
def _intensify_depth_sweep(seed):
    return st.builds(
        lambda s, delta: s + ("[" * delta if delta > 0 else "]" * (-delta)),
        st.just(seed),
        st.integers(min_value=-20, max_value=20),
    )

def _intensify_multi_mutate(seed):
    def _apply(s, pre, post, mid, tok, cut, dup_a, dup_b):
        out = pre + s + post
        out = out[:len(out)//2] + mid + tok + out[len(out)//2:]
        n = cut % (len(out) + 1)
        out = out[:n]
        if dup_a <= dup_b:
            out = out[:dup_a] + out[dup_a:dup_b] + out[dup_a:]
        return out
    return st.builds(
        _apply,
        st.just(seed),
        st.sampled_from(["", "[", "{", "]", "}", ",", ":", '"', "\x00"]),
        st.sampled_from(["", "[", "{", "]", "}", ",", ":", '"', "\x00"]),
        st.sampled_from(["", " ", ","]),
        st.sampled_from([
            "", "x", "1", "true", "null", ":", ",", "[", "]", "{", "}",
            '"', "\x00", "\x01", "\\", "\\u", "e", "-",
        ]),
        st.integers(min_value=0, max_value=20000),
        st.integers(min_value=0, max_value=20000),
        st.integers(min_value=0, max_value=20000),
    )

def _intensify_delimiter_swap(seed):
    return st.builds(
        lambda s, old, new: s.replace(old, new, 1),
        st.just(seed),
        st.sampled_from(["[", "]", "{", "}"]),
        st.sampled_from(["[", "]", "{", "}", ",", ":", '"', "\x00"]),
    )

def _intensify_balance_split(seed):
    # Split a balanced seed into its open/close halves and recombine unequally.
    return st.builds(
        lambda s, extra_open, extra_close: (
            s[:len(s)//2] + ("[" * extra_open) + s[len(s)//2:] + ("]" * extra_close)
        ),
        st.just(seed),
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=0, max_value=10),
    )

_near_crash = st.one_of(
    _crash_seed,
    _crash_seed.flatmap(_perturb_depth),
    _crash_seed.flatmap(_mutate_boundary),
    _crash_seed.flatmap(_splice_token),
    _crash_seed.flatmap(_truncate),
    _crash_seed.flatmap(_duplicate),
    # intensified structural mutations
    _crash_seed.flatmap(_intensify_depth_sweep),
    _crash_seed.flatmap(_intensify_multi_mutate),
    _crash_seed.flatmap(_intensify_delimiter_swap),
    _crash_seed.flatmap(_intensify_balance_split),
)

strategy = st.one_of(
    _value,
    _padded,
    _deep,
    _trailing_content,
    _leading_garbage,
    _bare,
    _near_crash,
    # Raw NUL/control heavy strings
    st.lists(_control_chars, min_size=1, max_size=10).map("".join),
    st.lists(st.one_of(_control_chars, _safe_chars.map(str)), min_size=1, max_size=20).map(
        lambda parts: '"' + "".join(parts) + '"'
    ),
)
```