```python
from hypothesis import strategies as st
import json

# Helper constants (no other imports allowed)
_SAFE_UNQUOTED = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " +-*/.:,;_@#%&()[]{}<>?`~^$|="  # a variety of printable safe chars
)
# ensure we never emit a raw NUL character '\x00' in generated strings
_SAFE_UNQUOTED = _SAFE_UNQUOTED.replace("\x00", "")

# Basic components

# Valid string contents pieces: either a safe unescaped character or an escape sequence.
_unescaped_char = st.sampled_from(list(_SAFE_UNQUOTED))
_simple_escape = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_hex4 = st.text('0123456789abcdef', min_size=4, max_size=4)
_unicode_escape = st.builds(lambda hx: '\\u' + hx, hx=_hex4)
# Surrogate-range escape (D800..DFFF)
_surrogate_escape = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda v: '\\u' + format(v, '04X'))

_string_piece = st.one_of(_unescaped_char, _simple_escape, _unicode_escape, _surrogate_escape)

# Valid quoted STRING token (may include escaped \u0000 but never actual NUL)
valid_string_token = st.lists(_string_piece, min_size=0, max_size=12).map(lambda pieces: '"' + ''.join(pieces) + '"')

# Unterminated or near-valid-but-malformed string variants
unterminated_string_token = st.one_of(
    # missing closing quote
    valid_string_token.map(lambda s: s[:-1]),
    # missing opening quote
    valid_string_token.map(lambda s: s[1:]),
    # random truncation
    valid_string_token.map(lambda s: s[: max(0, len(s) // 2)]),
)

# Combine string token strategies (mostly valid, sometimes malformed)
STRING_TOKEN = st.one_of(
    valid_string_token,
    unterminated_string_token,
)

# NUMBER token strategy: valid and near-valid/malformed examples
# Valid integers (no leading zeros unless '0'), decimals and exponents
_valid_int = st.one_of(
    st.just("0"),
    st.builds(lambda s: s, s=st.text('123456789', min_size=1, max_size=1).flatmap(
        lambda first: st.text('0123456789', min_size=0, max_size=6).map(lambda rest: first + rest)
    ))
)

_valid_frac = st.one_of(
    st.just(""),
    st.builds(lambda frac: "." + frac, frac=st.text('0123456789', min_size=1, max_size=6))
)

_valid_exp = st.one_of(
    st.just(""),
    st.builds(lambda e: "e" + e, e=st.builds(
        lambda sign, digits: sign + digits,
        sign=st.one_of(st.just(""), st.just("+"), st.just("-")),
        digits=st.text('0123456789', min_size=1, max_size=6)
    ))
)

valid_number = st.builds(
    lambda sign, integer, frac, exp: (sign + integer + frac + exp),
    sign=st.one_of(st.just(""), st.just("-")),
    integer=_valid_int,
    frac=_valid_frac,
    exp=_valid_exp,
)

# Malformed and edge numeric forms to include deliberately:
# leading plus, lone dot leading (.5), trailing dot (1.), leading zeroes (01), huge exponents (1e309)
malformed_numbers = st.sampled_from([
    "+1", "+0", "+123",
    ".5", "-.5", "1.", "123.",
    "01", "-01",
    "-", "-.",  # parser accepts lone '-' as 0 per notes
    "1e309", "-1e309", "1e10000", "9e9999", "1e-10000",
    "1E+309", "1e+309",
])

NUMBER_TOKEN = st.one_of(valid_number, malformed_numbers)

# Base (non-recursive) value tokens
BASE_VALUE = st.one_of(
    STRING_TOKEN,
    NUMBER_TOKEN,
    st.text('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_', min_size=1, max_size=8),
    st.sampled_from(["true", "false", "null", "-"]),  # include lone '-' which parser accepts
)

# Extensions for arrays/objects that use recursive children strategy.
def _make_array_from_children(children):
    # children: strategy producing strings (value tokens)
    # Normal arrays: [], [v,...]
    normal = st.lists(children, min_size=0, max_size=6).map(lambda vs: "[" + ",".join(vs) + "]")

    # Malformed/edge arrays: double commas, trailing commas, missing commas
    double_commas = st.lists(children, min_size=2, max_size=6).map(
        lambda vs: "[" + ",".join(vs[:1]) + ",," + ",".join(vs[1:]) + "]"
    )
    trailing_comma = st.lists(children, min_size=1, max_size=6).map(lambda vs: "[" + ",".join(vs) + ",]")
    missing_commas = st.lists(children, min_size=2, max_size=4).map(lambda vs: "[" + " ".join(vs) + "]")
    # Tiny arrays with whitespace/newline variety
    spaced = st.lists(children, min_size=0, max_size=4).map(lambda vs: "[" + ", ".join(vs) + "]")
    return st.one_of(normal, double_commas, trailing_comma, missing_commas, spaced)

def _make_object_from_children(children):
    # key must be a string token (prefer valid key tokens for keys, but allow malformed)
    key_token = st.one_of(valid_string_token, unterminated_string_token)
    # list of (key, value) pairs
    def pairs_strategy(n):
        return st.lists(st.tuples(key_token, children), min_size=n, max_size=n)

    # normal object
    normal = st.lists(st.tuples(key_token, children), min_size=0, max_size=6).map(
        lambda kvs: "{" + ",".join(k + ":" + v for k, v in kvs) + "}"
    )

    # empty object
    empty = st.just("{}")

    # duplicate keys: intentionally create duplicates in the key list
    def dup_builder(kvs):
        if not kvs:
            return "{}"
        # make first key duplicate of second if available, else duplicate first
        if len(kvs) >= 2:
            kvs.insert(1, kvs[0])
        else:
            kvs.append(kvs[0])
        return "{" + ",".join(k + ":" + v for k, v in kvs) + "}"

    duplicate_keys = st.lists(st.tuples(key_token, children), min_size=1, max_size=4).map(dup_builder)

    # malformed: missing colon, double commas, trailing commas
    missing_colon = st.lists(st.tuples(key_token, children), min_size=1, max_size=4).map(
        lambda kvs: "{" + ",".join(k + v for k, v in kvs) + "}"
    )
    double_commas = st.lists(st.tuples(key_token, children), min_size=2, max_size=5).map(
        lambda kvs: "{" + ",".join(k + ":" + v for k, v in kvs[:1]) + ",," + ",".join(k + ":" + v for k, v in kvs[1:]) + "}"
    )
    trailing_comma = st.lists(st.tuples(key_token, children), min_size=1, max_size=5).map(
        lambda kvs: "{" + ",".join(k + ":" + v for k, v in kvs) + ",}"
    )

    return st.one_of(normal, empty, duplicate_keys, missing_colon, double_commas, trailing_comma)

# Build recursive value strategy for ordinary recursion (small-to-moderate depth)
RECURSIVE_VALUE = st.recursive(
    BASE_VALUE,
    lambda children: st.one_of(
        _make_array_from_children(children),
        _make_object_from_children(children),
    ),
    max_leaves=200,
)

# Composite strategies for deep-but-legal (and near-limit) nesting using @st.composite
@st.composite
def deep_nesting(draw):
    # Choose whether to build arrays or objects
    is_array = draw(st.booleans())
    # Depth distribution: usually small, but sometimes near the parser cap (~2048)
    bias = draw(st.integers(min_value=0, max_value=99))
    if bias == 0:
        # very rare: pick a depth near the parser limit (allow slightly below/above)
        depth = draw(st.integers(min_value=2000, max_value=2050))
    elif bias < 5:
        # occasional deep-ish
        depth = draw(st.integers(min_value=100, max_value=600))
    else:
        depth = draw(st.integers(min_value=1, max_value=12))

    # Base innermost value
    inner = draw(st.one_of(st.just("0"), st.just("null"), st.just("true"), st.just("false"), valid_string_token))
    if is_array:
        # Build nested arrays: [[[inner]]]
        s = inner
        for _ in range(depth):
            s = "[" + s + "]"
        return s
    else:
        # Build nested objects: {"k0": {"k1": ...}}
        # Use short keys; intentionally allowed to create duplicate keys occasionally
        s = inner
        for i in range(depth):
            # occasionally repeat the same key to provoke duplicate-key rejection
            if i % 10 == 0:
                key = '"k"'  # repeated key every 10 levels
            else:
                key = '"k{}"'.format(i)
            s = "{" + key + ":" + s + "}"
        return s

# Top-level strategy occasionally appends trailing content (parser accepts trailing bytes)
_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("   "),
    st.just("\nabc"),
    st.text(min_size=1, max_size=8),
)

# Also allow generating stand-alone near-valid fragments (like leading +, .5, 01) as top-level
TOP_FRAGMENT = st.one_of(
    NUMBER_TOKEN,
    STRING_TOKEN,
    st.sampled_from(["{", "[", "", "}", "]", ",", ":-", "::"]),
)

# Compose final top-level strategy: mostly recursive values, sometimes deep nesting or fragments,
# and optionally append trailing content.
_top = st.one_of(
    RECURSIVE_VALUE,
    deep_nesting(),
    TOP_FRAGMENT,
)

# Ensure the final produced type is str; append trailing garbage occasionally
strategy = st.builds(lambda base, tail: base + tail, base=_top, tail=_trailing)
```