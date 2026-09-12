```python
from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

# Safe string characters (no quote, no backslash, no control) plus some unicode
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# A raw string body that may include escapes, control bytes, NUL, surrogates
_escape_seqs = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
    '\\u0000', '\\u001F', '\\uD800', '\\uDC00', '\\uDFFF', '\\uFFFF',
    '\\u00e9', '\\u0041', '\\u0001', '\\u0007',
])

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_esc = _hex4.map(lambda h: "\\u" + h)

_esc_or_char = st.one_of(
    _escape_seqs,
    _unicode_esc,
    _safe_chars.map(str),
    st.sampled_from(['\x00', '\x01', '\x07', '\x1f', '\x7f']),
)

# A JSON string literal (well-formed)
_string_literal = st.lists(_esc_or_char, max_size=8).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Malformed string: unterminated, stray quote, etc.
_bad_string = st.one_of(
    st.lists(_esc_or_char, max_size=6).map(lambda p: '"' + "".join(p)),
    st.just('"'),
    st.just('"""'),
    st.text(alphabet='abc"\\\x00\x1f', min_size=1, max_size=8).map(lambda s: '"' + s),
)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=0, max_value=10**18).map(str),
)

def _num():
    return st.one_of(
        _int_part,
        st.builds(lambda a, b: "-" + a if b else a, _int_part, st.booleans()),
        st.builds(lambda i, f: i + "." + f,
                  _int_part,
                  st.integers(min_value=0, max_value=10**6).map(str)),
        st.builds(lambda i, e: i + e,
                  _int_part,
                  st.one_of(
                      st.just("e309"), st.just("E309"), st.just("e-309"),
                      st.just("e999999"), st.just("e+308"), st.just("e01"),
                      st.integers(min_value=-400, max_value=400).map(lambda n: "e%d" % n),
                  )),
        # lone minus (accepted by parser)
        st.just("-"),
        # extreme magnitudes
        st.sampled_from(["1e309", "-1e309", "1e-400", "0e0", "1E+308", "9" * 20,
                         "1." + "0" * 5, "-0", "0.0", "1e999999999"]),
        # malformed numbers
        st.sampled_from(["+1", ".5", "1.", "01", "00", "0x1F", "1_000",
                         "-.5", "+.5", "1e", "1e+", "--1", "1..2", "Infinity",
                         "NaN", "1e1e1"]),
    )

_number = _num()

# ---------- recursive value ----------

# We build recursive values via st.recursive with a deferred obj/arr.
# To bias toward objects with members, we weight the object branch heavily.

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\x00"])

def _pair(key_strat):
    return st.builds(
        lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
        key_strat,
        _ws,
        _ws,
        st.deferred(lambda: _value),
    )

# keys: mostly normal strings, sometimes duplicates handled at object level
_key = st.one_of(_string_literal, _bad_string, st.just('"a"'), st.just('""'))

# forward declaration
_value = None  # assigned below

_member = st.builds(
    lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
    _key,
    _ws,
    _ws,
    st.deferred(lambda: _value),
)

# object: {pairs} with optional single trailing comma, sometimes duplicate keys
def _object(member):
    return st.one_of(
        st.just("{}"),
        st.just("{ }"),
        st.lists(member, min_size=1, max_size=6).map(
            lambda ms: "{" + ",".join(ms) + "}"
        ),
        st.lists(member, min_size=1, max_size=6).map(
            lambda ms: "{" + ",".join(ms) + ",}"
        ),
        # duplicate keys explicitly
        st.builds(lambda m: "{" + m + "," + m + "}", member),
        # malformed: missing colon / double comma
        st.lists(_key, min_size=1, max_size=4).map(
            lambda ks: "{" + ",".join(ks) + "}"
        ),
        st.lists(member, min_size=2, max_size=5).map(
            lambda ms: "{" + ",,".join(ms) + "}"
        ),
        st.just("{,}"),
        st.just("{a:1}"),
        st.just('{"a" 1}'),
    )

def _array(value):
    return st.one_of(
        st.just("[]"),
        st.just("[ ]"),
        st.lists(value, min_size=1, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(value, min_size=1, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
        st.lists(value, min_size=2, max_size=5).map(
            lambda vs: "[" + ",,".join(vs) + "]"
        ),
        st.just("[,]"),
        st.just("[,1]"),
        st.just("[1,,2]"),
        st.just("["),
        st.just("]"),
    )

_literal = st.sampled_from(["true", "false", "null", "True", "NULL", "tru", "nul"])

_scalar = st.one_of(_string_literal, _bad_string, _number, _literal)

# Use st.recursive: base = scalars, extend = obj/arr
_value = st.recursive(
    _scalar,
    lambda children: st.one_of(
        # bias toward objects with members
        _object(st.builds(
            lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
            _key, _ws, _ws, children,
        )),
        _array(children),
    ),
    max_leaves=40,
)

# ---------- deep nesting ----------

_deep_obj = st.integers(min_value=1, max_value=200).map(
    lambda n: '{"a":' * n + "1" + "}" * n
)
_deep_arr = st.integers(min_value=1, max_value=200).map(
    lambda n: "[" * n + "1" + "]" * n
)
_deep_empty_arr = st.integers(min_value=1, max_value=200).map(
    lambda n: "[" * n + "]" * n
)

# ---------- top-level composition ----------

_top = st.one_of(
    _value,
    _deep_obj,
    _deep_arr,
    _deep_empty_arr,
    # trailing content after complete value (should be rejected)
    st.builds(lambda v, t: v + t, _value, st.sampled_from(
        [" garbage", "xyz", " true", "abc", "\x00", "[]", "}"])),
    # leading garbage
    st.builds(lambda t, v: t + v, st.sampled_from(
        ["//x\n", "/* */", "'x'", "x", "\x00", " "]), _value),
    # raw NUL / control at top
    st.just("\x00"),
    st.just(""),
    st.just("   "),
    st.just("\x00\x00\x00"),
    st.just("null\x00"),
    st.just("\xef\xbb\xbf{}"),  # BOM
)

# Wrap with optional surrounding whitespace
strategy = st.one_of(
    _top,
    st.builds(lambda a, b: a + b, st.sampled_from(["", " ", "\n", "\t"]), _top),
    st.builds(lambda a, b: a + b, _top, st.sampled_from(["", " ", "\n", "\t"])),
)
```