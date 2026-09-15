import json
from hypothesis import strategies as st


# ---------- scalar building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

_esc_simple = st.sampled_from(list('"\\/bfnrt'))

_esc_unicode = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    _hex, _hex, _hex, _hex,
)

# lone surrogate escapes: parser rejects these (good rejection fodder)
_esc_surrogate = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    st.sampled_from("dD"),
    st.sampled_from("89abAB"),
    _hex, _hex,
)

_esc = st.one_of(_esc_simple, _esc_unicode, _esc_surrogate)

# raw bytes inside a string: includes NUL and control chars (parser accepts)
_raw_char = st.one_of(
    st.characters(min_codepoint=0, max_codepoint=0x1F),
    st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    st.characters(min_codepoint=0x80, max_codepoint=0xFFFF),
)

_str_body = st.one_of(_esc, _raw_char)

_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_str_body, max_size=12),
)

# unterminated string (near-valid-but-malformed)
_unterminated_string = st.builds(
    lambda parts: '"' + "".join(parts),
    st.lists(_str_body, min_size=1, max_size=12),
)


# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

# valid-ish ints, plus leading-zero and leading-dot/plus deviations
_number = st.one_of(
    # plain ints
    st.integers(min_value=-10**6, max_value=10**6).map(str),
    # big ints
    st.integers(min_value=-10**40, max_value=10**40).map(str),
    # trailing dot (parser accepts)
    st.builds(lambda d: d + ".", _int_digits),
    # leading zeros (parser accepts)
    st.builds(lambda d: "0" + d, _int_digits),
    # hex (parser accepts)
    st.builds(lambda d: "0x" + d, _int_digits),
    # extreme exponents / overflow like 1e309
    st.builds(lambda m, e: m + "e" + e,
              st.sampled_from(["1", "9", "1.5", "-2", "0"]),
              st.sampled_from(["309", "308", "400", "999", "-400", "+308", "01"])),
    # exponent with sign
    st.builds(lambda m, s, e: m + "e" + s + e,
              st.sampled_from(["1", "2.5", "-3"]),
              st.sampled_from(["+", "-", ""]),
              st.sampled_from(["3", "30", "300", "1000"])),
    # malformed number forms (parser rejects): lone -, +1, .5
    st.sampled_from(["-", "+1", ".5", "-.5", "+.5", "1..2", "1e", "1e+", "0x", "--1"]),
)


# ---------- malformed / near-valid fragments ----------

_malformed = st.sampled_from([
    "{,}", "[,]", "[1,,2]", '{"a":}', '{"a" 1}', '{a:1}', "{'a':1}",
    "[1,2,]", '{"a":1,}', "[", "{", "]", "}", "[1 2]", '{"a":1 "b":2}',
    "NaN", "Infinity", "-Infinity", "nan", "TRUE", "True",
    "", "   ", "\ufeff",  # BOM alone
    "\ufeff1",  # BOM then value
    "1abc", "1 2", "1\x00",  # trailing content / NUL after value
])


# ---------- recursive structure ----------

_json_scalar = st.one_of(
    _string,
    _number,
    st.sampled_from(["true", "false", "null"]),
    _unterminated_string,
    _malformed,
)


def _make_value(children):
    return st.one_of(
        _json_scalar,
        _string,
        _number,
        st.sampled_from(["true", "false", "null"]),
        # object
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(children, max_size=4),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(children, max_size=4),
        ),
        # array
        st.builds(
            lambda vals: "[" + ",".join(vals) + "]",
            st.lists(children, max_size=4),
        ),
        # empty containers
        st.just("{}"),
        st.just("[]"),
    )


_pair = st.builds(
    lambda k, v: k + ":" + v,
    _string,
    st.deferred(lambda: _value_strategy),
)


_json_value = st.recursive(
    _json_scalar,
    _make_value,
    max_leaves=40,
)

# pair needs a value; build a parallel deferred strategy
_value_strategy = _json_value

_pair = st.builds(
    lambda k, v: k + ":" + v,
    _string,
    _value_strategy,
)

# rebuild value to include pairs (objects) using the pair strategy
_json_value = st.recursive(
    st.one_of(_json_scalar, st.just("{}"), st.just("[]")),
    lambda children: st.one_of(
        st.builds(
            lambda vals: "[" + ",".join(vals) + "]",
            st.lists(children, max_size=4),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, _string, children),
                max_size=4,
            ),
        ),
    ),
    max_leaves=40,
)


# ---------- deep nesting near the 1000-level limit ----------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_object(depth):
    return "{" + '"a":' * depth + "0" + "}" * depth


_deep = st.one_of(
    st.integers(min_value=0, max_value=1000).map(_deep_array),
    st.integers(min_value=0, max_value=1000).map(_deep_object),
    # just over the limit -> clean rejection
    st.integers(min_value=1001, max_value=1100).map(_deep_array),
    st.integers(min_value=1001, max_value=1100).map(_deep_object),
    # mixed nesting near the boundary
    st.builds(
        lambda d: "[" * d + "{" + '"k":' + "[" * (1000 - d) + "]" * (1000 - d) + "}" + "]" * d,
        st.integers(min_value=0, max_value=1000),
    ),
)


# ---------- duplicate keys, trailing commas, etc. ----------

_duplicate_keys = st.builds(
    lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
    _string,
    _json_value,
    _json_value,
)

_trailing_comma = st.one_of(
    st.builds(lambda v: "[" + v + ",]", _json_value),
    st.builds(lambda k, v: "{" + k + ":" + v + ",}", _string, _json_value),
)


# ---------- cJSON_Compare coverage ----------
# The parser entry point parses a single JSON text.  To reach cJSON_Compare
# we emit two JSON texts joined by a NUL byte; the harness splits on the
# first NUL and parses each half independently, then feeds both to
# cJSON_Compare with case_sensitive=0 and case_sensitive=1.  The pairs
# below are chosen to hit every branch of cJSON_Compare: identical values,
# same-type/different-value, differing types, arrays of differing length,
# objects with differing key sets, strings differing only in case, and
# nested structures that recurse into the compare routine.
_cmp_scalar = st.one_of(
    _string,
    _number,
    st.sampled_from(["true", "false", "null", "true", "false", "null"]),
)

_cmp_value = st.recursive(
    _cmp_scalar,
    lambda children: st.one_of(
        st.builds(
            lambda vals: "[" + ",".join(vals) + "]",
            st.lists(children, max_size=3),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, _string, children),
                max_size=3,
            ),
        ),
    ),
    max_leaves=20,
)

# Strings that differ only in case -> exercises case_sensitive branch.
_case_string = st.builds(
    lambda s: '"' + s + '"',
    st.text(alphabet="abcXYZ", min_size=1, max_size=4),
)

_cmp_pair = st.one_of(
    # identical values (both sides equal -> true path through whole tree)
    st.builds(lambda v: v + "\x00" + v, _cmp_value),
    # same scalar type, different value
    st.builds(lambda a, b: a + "\x00" + b, _cmp_scalar, _cmp_scalar),
    # case-only difference in strings (case-sensitive vs insensitive)
    st.builds(lambda a, b: a + "\x00" + b, _case_string, _case_string),
    # different container types
    st.builds(
        lambda v: "[" + v + "]\x00{" + '"k":' + v + "}",
        _cmp_scalar,
    ),
    # arrays of differing length
    st.builds(
        lambda a, b: "[" + a + "]\x00[" + a + "," + b + "]",
        _cmp_scalar,
        _cmp_scalar,
    ),
    # objects with differing key sets
    st.builds(
        lambda k1, k2, v: "{" + k1 + ":" + v + "}\x00{" + k2 + ":" + v + "}",
        _string,
        _string,
        _cmp_scalar,
    ),
    # objects with same key, different value
    st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "}\x00{" + k + ":" + v2 + "}",
        _string,
        _cmp_scalar,
        _cmp_scalar,
    ),
    # null vs a real value (NULL branch in compare)
    st.builds(lambda v: "null\x00" + v, _cmp_value),
    # deep nested equal structures (recursive compare)
    st.builds(
        lambda d: "[" * d + "0" + "]" * d + "\x00" + "[" * d + "0" + "]" * d,
        st.integers(min_value=1, max_value=30),
    ),
    # deep nested differing structures (recursion terminates on mismatch)
    st.builds(
        lambda d: "[" * d + "0" + "]" * d + "\x00" + "[" * d + "1" + "]" * d,
        st.integers(min_value=1, max_value=30),
    ),
)


# ---------- top-level combination ----------

strategy = st.one_of(
    _json_value,
    _deep,
    _duplicate_keys,
    _trailing_comma,
    # BOM prefix
    st.builds(lambda v: "\ufeff" + v, _json_value),
    # trailing content after a complete value (accepted)
    st.builds(lambda v, junk: v + junk,
              _json_value,
              st.sampled_from(["", "abc", " 1", "\x00", "garbage", " 2 3"])),
    _malformed,
    _unterminated_string,
    # cJSON_Compare coverage: paired values separated by a NUL byte
    _cmp_pair,
)