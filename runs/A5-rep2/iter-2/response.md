```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Safe string chars (no quote, no backslash, no control)
_safe_chars = st.characters(
    blacklist_categories=("Cs", "Cc"),
    blacklist_characters='"\\',
)

# Escapes: \" \\ \/ \b \f \n \r \t
_simple_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# \uXXXX
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes (lone and paired) — legal chars in escape form
_surrogate_escape = st.sampled_from([
    "\\ud800", "\\udfff", "\\ud83d", "\\ude00",
    "\\ud83d\\ude00",  # valid pair
    "\\udc00\\ud800",  # reversed pair
    "\\u0000", "\\u001f", "\\u007f",
])

# Raw control / NUL bytes (allowed per notes)
_raw_control = st.sampled_from(["\x00", "\x01", "\x1f", "\x7f", "\t", "\n", "\r"])

# Body of a JSON string (contents between quotes)
_string_body = st.one_of(
    st.text(alphabet=_safe_chars, max_size=8),
    _simple_escape,
    _unicode_escape,
    _surrogate_escape,
    _raw_control,
)

# A well-formed JSON string literal
_string_literal = st.lists(_string_body, max_size=6).map(lambda parts: '"' + "".join(parts) + '"')

# Unterminated / malformed strings
_unterminated_string = st.lists(_string_body, min_size=1, max_size=4).map(
    lambda parts: '"' + "".join(parts)
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_int_part = st.one_of(
    st.just("0"),
    st.text(alphabet="123456789", min_size=1, max_size=1).flatmap(
        lambda first: st.text(alphabet="0123456789", max_size=6).map(lambda rest: first + rest)
    ),
)
_frac = st.text(alphabet="0123456789", min_size=1, max_size=6).map(lambda d: "." + d)
_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

_number = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or ""))

# Extreme magnitudes / overflow
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e308", "1e-308",
    "1e999", "1e-999", "0e0", "0e999",
    "-0", "-0.0", "0.0",
    "1" + "0" * 30, "1" + "0" * 300,
    "9" * 20, "9" * 300,
    "-" + "9" * 300,
    "1e" + "0" * 50,
])

# Malformed number forms
_malformed_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-", "-.5", "+", "1e", "1e+", "1E-",
    "--1", "1..2", "1e1e1", "0.0.0", "-01",
])

_number_all = st.one_of(_number, _extreme_number, _malformed_number)

# ---------- whitespace ----------

_ws = st.text(alphabet=" \t\n\r", max_size=3)
_ws_opt = st.text(alphabet=" \t\n\r", max_size=2)

# ---------- recursive JSON ----------

json_strategy = st.recursive(
    # Leaves
    st.one_of(
        _string_literal,
        _unterminated_string,
        _number_all,
        st.sampled_from(["true", "false", "null", "tru", "nul"]),
    ),
    # Recursive extensions
    lambda children: st.one_of(
        # Arrays
        st.lists(children, max_size=4).map(
            lambda items: "[" + ",".join(items) + "]"
        ),
        # Arrays with a single trailing comma
        st.lists(children, min_size=1, max_size=4).map(
            lambda items: "[" + ",".join(items) + ",]"
        ),
        # Empty array
        st.just("[]"),
        # Objects with members (stressed path)
        st.lists(
            st.tuples(_string_literal, children),
            min_size=1,
            max_size=4,
        ).map(
            lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
        ),
        # Object with single trailing comma
        st.lists(
            st.tuples(_string_literal, children),
            min_size=1,
            max_size=4,
        ).map(
            lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + ",}"
        ),
        # Empty object
        st.just("{}"),
    ),
    max_leaves=20,
)

# ---------- malformed / near-valid wrappers ----------

_malformed = st.one_of(
    # Double commas
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just("[,1]"),
    st.just('{"a":1,,"b":2}'),
    # Missing colon
    st.just('{"a" 1}'),
    st.just('{"a"}'),
    # Unterminated containers
    st.just("["),
    st.just("{"),
    st.just("[1,2"),
    st.just('{"a":1'),
    # Trailing content after value
    st.just("1abc"),
    st.just("[]xyz"),
    st.just("1 garbage"),
    st.just("true false"),
    # Bare keys / single quotes / comments
    st.just("{a:1}"),
    st.just("'x'"),
    st.just("//x"),
    st.just("/* */1"),
    # Empty
    st.just(""),
    st.just("   "),
)

# Duplicate keys explicitly
_duplicate_keys = st.lists(
    st.tuples(
        st.sampled_from(['"a"', '"b"', '"a"', '"key"']),
        st.one_of(_number_all, _string_literal, st.sampled_from(["true", "false", "null"])),
    ),
    min_size=2,
    max_size=5,
).map(lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}")

# Deep nesting
_deep_nesting = st.integers(min_value=1, max_value=200).flatmap(
    lambda depth: st.one_of(
        st.just("[" * depth + "]" * depth),
        st.just("[" * depth + "0" + "]" * depth),
        st.just("{" + '"a":' * depth + "0" + "}" * depth),
        st.just("[" * depth),
    )
)

# Whitespace-padded JSON
_padded = st.tuples(_ws, json_strategy, _ws).map(lambda t: t[0] + t[1] + t[2])

# ---------- top-level strategy ----------

strategy = st.one_of(
    json_strategy,
    _padded,
    _malformed,
    _duplicate_keys,
    _deep_nesting,
    _unterminated_string,
    _extreme_number,
    _malformed_number,
)
```