Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

# Safe string characters (no raw NUL, no unescaped control chars, no quote/backslash)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in the source text
    blacklist_characters='"\x00\\',
    min_codepoint=0x20,
    max_codepoint=0x10FFFF,
)

# Escapes that are valid inside a JSON string
_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

# Correctly-formed unicode escapes: a BMP non-surrogate, or a proper
# high-surrogate + low-surrogate pair. Lone/mismatched surrogates are NOT
# emitted here because they are not valid JSON string escapes.
_unicode_escapes = st.one_of(
    # BMP scalar values that are not surrogate code points
    st.tuples(_hex, _hex, _hex, _hex)
    .filter(lambda t: not (t[0] in "dD" and t[1] in "89abABCDEFabcdef"))
    .map(lambda t: "\\u" + "".join(t)),
    # well-formed surrogate pair: high D800-DBFF then low DC00-DFFF
    st.tuples(
        st.sampled_from("dD"), st.sampled_from("89abAB"), _hex, _hex,
        st.sampled_from("dD"), st.sampled_from("cdefCDEF"), _hex, _hex,
    ).map(lambda t: "\\u" + "".join(t[:4]) + "\\u" + "".join(t[4:])),
    st.just("\\u0000"),
    st.just("\\u001f"),
    st.just("\\u007f"),
    st.just("\\uffff"),
    st.just("\\ufffe"),
)

_string_piece = st.one_of(
    _safe_chars.map(str),
    _simple_escapes,
    _unicode_escapes,
)

def _mk_string(pieces):
    return '"' + "".join(pieces) + '"'

_json_string = st.lists(_string_piece, max_size=8).map(_mk_string)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text("0123456789", min_size=1, max_size=6).filter(
    lambda s: not s.startswith("0") or len(s) == 1
)

_int_part = st.one_of(
    st.just("0"),
    st.text("123456789", min_size=1, max_size=1).flatmap(
        lambda first: st.text("0123456789", min_size=0, max_size=6).map(
            lambda rest: first + rest
        )
    ),
)

_frac_part = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text("0123456789", min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # extreme exponents
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.sampled_from(["308", "309", "310", "999", "1000", "400"]),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

def _mk_number(sign, ip, fp, ep):
    return sign + ip + fp + ep

_number = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part,
    _frac_part,
    _exp_part,
).map(lambda t: _mk_number(*t))

# Extreme magnitude literals
_extreme_numbers = st.sampled_from([
    "1e309", "-1e309", "1e400", "-1e400", "1e308", "1.7976931348623157e308",
    "1.7976931348623159e308", "5e-324", "1e-400", "0e999", "-0", "0.0",
    "123456789012345678901234567890", "1e1000000", "9" * 30,
])

_literal = st.sampled_from(["true", "false", "null"])

# ---------- recursive structure ----------

# Malformed fragments for near-valid-but-malformed inputs
_malformed_tail = st.sampled_from([
    ",", ",,", ",]", ",}", ":", "::", '"', '""', "]", "}", " ",
    "1abc", "[]xyz", "{}garbage", "1 garbage", "-", "-.", ".5", "+1", "01",
    "tru", "nul", "fals", "\t", "\n", "\r",
])

_ws = st.sampled_from(["", " ", "\n", "\t", "\r", "  ", "\n\t"])

def _join(parts):
    return "".join(parts)

def _mk_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _mk_arr(items):
    return "[" + ",".join(items) + "]"

def _mk_pair(k, v):
    return k + ":" + v

# We build the strategy recursively. Leaves are strings/numbers/literals.
# The recursion is bounded by Hypothesis' recursion machinery.

value_strategy = st.deferred(lambda: _value)

def _make_value():
    # A leaf or a (recursive) container.
    leaf = st.one_of(
        _json_string,
        _number,
        _extreme_numbers,
        _literal,
    )

    pair = st.tuples(_json_string, value_strategy).map(lambda t: _mk_pair(*t))
    obj = st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=4).map(_mk_obj),
        # duplicate keys deliberately
        st.tuples(_json_string, value_strategy, value_strategy).map(
            lambda t: _mk_pair(t[0], t[1]) + "," + _mk_pair(t[0], t[2])
        ).map(lambda s: "{" + s + "}"),
    )

    arr = st.one_of(
        st.just("[]"),
        st.lists(value_strategy, min_size=1, max_size=4).map(_mk_arr),
    )

    return st.one_of(leaf, obj, arr)

_value = _make_value()

# ---------- top-level assembly ----------

# Deep nesting near the 2048 limit: build a chain of '[' * n + value + ']' * n
def _deep_nest(n, inner):
    return "[" * n + inner + "]" * n

_deep_depth = st.one_of(
    st.integers(min_value=2000, max_value=2048),
    st.integers(min_value=2045, max_value=2050),
    st.integers(min_value=1, max_value=20),
)

_deep = st.tuples(_deep_depth, value_strategy).map(
    lambda t: _deep_nest(t[0], t[1])
)

# Objects nested deeply too
_deep_obj = st.tuples(
    st.integers(min_value=1900, max_value=2048),
    _json_string,
    value_strategy,
).map(lambda t: '{"k":' * t[0] + t[2] + "}" * t[0])

# Near-valid-but-malformed: take a valid value and corrupt it
def _corrupt(v, tail):
    return v + tail

_malformed = st.tuples(value_strategy, _malformed_tail).map(
    lambda t: _corrupt(*t)
)

# Unterminated string
_unterminated = st.lists(_string_piece, max_size=6).map(
    lambda ps: '"' + "".join(ps)
)

# Missing colon / double comma forms
_missing_colon = st.tuples(_json_string, value_strategy).map(
    lambda t: "{" + t[0] + t[1] + "}"
)
_double_comma = st.tuples(value_strategy, value_strategy).map(
    lambda t: "[" + t[0] + ",," + t[1] + "]"
)
_leading_plus = st.tuples(_int_part, _frac_part, _exp_part).map(
    lambda t: "+" + t[0] + t[1] + t[2]
)
_leading_dot = st.tuples(_digits, _exp_part).map(
    lambda t: "." + t[0] + t[1]
)
_leading_zero = st.tuples(st.text("0123456789", min_size=1, max_size=4)).map(
    lambda t: "0" + t[0]
)

# Whitespace-wrapped valid values (WS is skipped by grammar)
_ws_wrapped = st.tuples(_ws, value_strategy, _ws).map(
    lambda t: t[0] + t[1] + t[2]
)

# Trailing content after a complete value (parser accepts)
_trailing = st.tuples(value_strategy, _malformed_tail).map(
    lambda t: t[0] + t[1]
)

_top = st.one_of(
    value_strategy,
    _deep,
    _deep_obj,
    _malformed,
    _unterminated,
    _missing_colon,
    _double_comma,
    _leading_plus,
    _leading_dot,
    _leading_zero,
    _ws_wrapped,
    _trailing,
    st.just("{}"),
    st.just("[]"),
    st.just("-"),
    st.just(""),
)

# Filter out any raw NUL bytes (harness skips those)
def _no_nul(s):
    return "\x00" not in s

strategy = _top.filter(_no_nul)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 171,
    "reject": 179
  },
  "acceptance_rate": 0.489,
  "max_nesting_depth": 2055,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "false",
    "json",
    "null",
    "obj",
    "pair",
    "true",
    "value"
  ],
  "productions_gap": [],
  "cap_distance_mass": 0.181,
  "novelty": 30,
  "divergences": 91,
  "divergence_examples": [
    "b'\"\",'",
    "b'{}:'",
    "b'-'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **one edit of your choice from this list** — add_or_upweight_production (add or upweight a grammar production the inputs under-use); generate_nesting_toward_cap (generate nesting close to the parser's depth limit); fix_feature_encoding (fix how one feature of the format is encoded); broaden_exploration (diversify the structures the inputs take). Use the run feedback above where it is given, and write the name of the edit you chose on the first line as EDIT: <name>.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.