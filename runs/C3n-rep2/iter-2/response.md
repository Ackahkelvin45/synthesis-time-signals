```python
from hypothesis import strategies as st
import json

# ---------- low-level building blocks ----------

HEX = "0123456789abcdefABCDEF"

def _hex4():
    return st.text(alphabet=HEX, min_size=4, max_size=4)

# Escape sequences valid inside a JSON string body (without surrounding quotes)
_esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_esc_unicode = st.builds(lambda h: "\\u" + h, _hex4())
_esc = st.one_of(_esc_simple, _esc_unicode)

# Surrogate escapes (lone / paired), explicitly encouraged
_surrogates = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD800\\uDC00", "\\uDBFF\\uDFFF", "\\uD800x",
])

# Raw characters allowed in the string body: SAFECODEPOINT plus NUL/control bytes.
# NUL (0x00) and other control chars are deliberately included per adaptation notes.
_safe = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates as raw chars
    blacklist_characters='\\"',
    min_codepoint=0x00,
    max_codepoint=0x10FFFF,
)
_control = st.integers(min_value=0, max_value=0x1F).map(chr)
_raw_char = st.one_of(_safe, _control)

_string_body = st.one_of(
    st.lists(st.one_of(_raw_char, _esc, _surrogates), max_size=12).map("".join),
    st.just(""),
)

# A well-formed JSON string literal
string_lit = st.builds(lambda b: '"' + b + '"', _string_body)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d: d[0:1].lstrip("0") or "0", st.text(alphabet="123456789", min_size=1, max_size=1) + _digits),
)

# Extreme magnitudes / exponents
_extreme_int = st.sampled_from([
    "0", "-0", "1", "-1", "9", "10", "123456789",
    "1" + "0" * 300, "9" * 300,
])
_exp = st.builds(
    lambda s, e: s + e,
    st.sampled_from(["e", "E"]),
    st.one_of(
        st.just("309"), st.just("-309"), st.just("308"), st.just("+308"),
        st.just("999"), st.just("-999"), st.just("0"),
        st.builds(lambda d: d, _digits),
        st.builds(lambda s, d: s + d, st.sampled_from(["+", "-"]), _digits),
    ),
)
_frac = st.builds(lambda d: "." + d, _digits)

number = st.one_of(
    _extreme_int,
    st.builds(lambda i, f: i + f, _int_part, _frac),
    st.builds(lambda i, e: i + e, _int_part, _exp),
    st.builds(lambda i, f, e: i + f + e, _int_part, _frac, _exp),
    # lone minus: accepted by parser per notes
    st.just("-"),
)

# ---------- malformed / near-valid fragments ----------

malformed = st.sampled_from([
    "", ",", ",,", "[,]", "[1,,2]", "{,}", "{\"a\":}", "{:1}",
    "{a:1}", "'x'", "//x", "/* */1", "1abc", "[]xyz", "true false",
    "+1", ".5", "1.", "01", "0x1F", "nul", "tru", "fals",
    "\"unterminated", "\"bad\\", "{\"a\" 1}", "[1 2]", "[1,2",
    "{\"a\":1", "]", "}", ":", "\\u12", "\\uZZZZ",
])

# ---------- recursive JSON values ----------

_json_value = st.deferred(lambda: _value_strategy)

def _make_obj():
    return st.one_of(
        st.just("{}"),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(_pair_strategy, min_size=1, max_size=6),
        ),
        # single trailing comma (accepted by parser)
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + ",}",
            st.lists(_pair_strategy, min_size=1, max_size=6),
        ),
    )

def _make_arr():
    return st.one_of(
        st.just("[]"),
        st.builds(
            lambda vals: "[" + ",".join(vals) + "]",
            st.lists(_json_value, min_size=1, max_size=6),
        ),
        st.builds(
            lambda vals: "[" + ",".join(vals) + ",]",
            st.lists(_json_value, min_size=1, max_size=6),
        ),
    )

_pair_strategy = st.builds(
    lambda k, v: k + ":" + v,
    string_lit,
    _json_value,
)

_value_strategy = st.one_of(
    string_lit,
    number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _make_obj(),
    _make_arr(),
)

# Use recursive to allow nesting; bias toward objects with members.
recursive_value = st.recursive(
    st.one_of(string_lit, number, st.just("true"), st.just("false"), st.just("null")),
    lambda children: st.one_of(
        # objects with members (stressed path) — heavier weight
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, string_lit, children),
                min_size=1, max_size=6,
            ),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + ",}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, string_lit, children),
                min_size=1, max_size=6,
            ),
        ),
        st.just("{}"),
        # arrays
        st.builds(
            lambda vals: "[" + ",".join(vals) + "]",
            st.lists(children, min_size=0, max_size=6),
        ),
        st.builds(
            lambda vals: "[" + ",".join(vals) + ",]",
            st.lists(children, min_size=1, max_size=6),
        ),
    ),
    max_leaves=40,
)

# ---------- deep nesting generators (no depth cap in parser) ----------

def _deep_obj(depth):
    # {"a":{"a":{...}}} of given depth
    return "{" + '"a":' * depth + "null" + "}" * depth

def _deep_arr(depth):
    return "[" * depth + "null" + "]" * depth

_deep = st.one_of(
    st.integers(min_value=1, max_value=200).map(_deep_obj),
    st.integers(min_value=1, max_value=200).map(_deep_arr),
    st.integers(min_value=1, max_value=2000).map(lambda d: "[" * d),
    st.integers(min_value=1, max_value=2000).map(lambda d: "{" * d),
)

# ---------- top-level strategy ----------

_whitespace = st.text(alphabet=" \t\n\r", max_size=4)

def _wrap(s):
    return s

strategy = st.one_of(
    # valid-ish documents
    recursive_value,
    _deep,
    # whitespace-wrapped
    st.builds(lambda a, v, b: a + v + b, _whitespace, recursive_value, _whitespace),
    # malformed / near-valid fragments (still useful edge inputs)
    malformed,
    # duplicate keys, explicitly
    st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        string_lit, _json_value, _json_value,
    ),
)

strategy = strategy.map(lambda s: s if isinstance(s, str) else str(s))
```