from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Safe characters that can appear unescaped inside a JSON string.
# Include control bytes and NUL explicitly (parser takes explicit length).
_safe_chars = st.one_of(
    st.characters(min_codepoint=0x00, max_codepoint=0x1F),  # control incl NUL
    st.characters(min_codepoint=0x20, max_codepoint=0x21),
    st.characters(min_codepoint=0x23, max_codepoint=0x5B),
    st.characters(min_codepoint=0x5D, max_codepoint=0x10FFFF).filter(
        lambda c: c not in ('"', '\\') and not (0xD800 <= ord(c) <= 0xDFFF)
    ),
)

# Escape sequences: \", \\, \/, \b \f \n \r \t, \uXXXX (incl surrogates)
_hex = st.sampled_from("0123456789abcdefABCDEF")
_unicode_esc = st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map("".join)
_simple_esc = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
# lone backslash-u followed by non-hex (malformed)
_bad_esc = st.tuples(st.just("\\u"), st.sampled_from("ghijklmnopqrstuvwxyzZ")).map("".join)
_bad_esc2 = st.just("\\")
_esc = st.one_of(_simple_esc, _unicode_esc)

_string_body = st.one_of(
    st.lists(st.one_of(_safe_chars, _esc), max_size=12).map("".join),
    # malformed escapes
    st.lists(st.one_of(_safe_chars, _esc, _bad_esc, _bad_esc2), max_size=8).map("".join),
)

# Well-formed JSON string (with quotes)
_string = st.tuples(st.just('"'), _string_body, st.just('"')).map("".join)

# Unterminated string (near-valid-malformed)
_unterminated_string = st.tuples(st.just('"'), _string_body).map("".join)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map("".join),
    # malformed leading zeros
    st.tuples(st.just("0"), _digits).map("".join),
)
_frac = st.tuples(st.just("."), _digits).map("".join)
_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    _digits,
).map("".join)

_number = st.one_of(
    # normal
    st.tuples(st.one_of(st.just(""), st.just("-")), _int_part,
              st.one_of(st.just(""), _frac),
              st.one_of(st.just(""), _exp)).map("".join),
    # lone minus (accepted by parser)
    st.just("-"),
    # leading +
    st.tuples(st.just("+"), _int_part).map("".join),
    # leading dot
    st.tuples(st.just("."), _digits).map("".join),
    # trailing dot
    st.tuples(_int_part, st.just(".")).map("".join),
    # extreme magnitudes
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-9999"),
    st.just("1E+308"),
    st.just("1e99999999999999999999"),
)

# ---------- recursive values ----------

# We use a lazy strategy to allow recursion.
_value = st.deferred(lambda: _value_strategy)

_whitespace = st.text(alphabet=" \t\n\r", max_size=3)

def _ws():
    return _whitespace

# Build the recursive structure with st.recursive.
def _build_recursive():
    # leaf values
    leaves = st.one_of(
        _string,
        _number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )
    # recursive wrapper for obj/arr
    def extend(children):
        # children is a strategy producing value strings
        # objects: bias toward objects with members
        pair = st.tuples(
            _string,
            st.one_of(st.just(":"), st.just(""), st.just("::")),
            _whitespace,
            children,
        ).map(lambda t: t[0] + t[1] + t[2] + t[3])

        obj_members = st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        )
        # trailing comma variant
        obj_trailing = st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        )
        # empty object
        obj_empty = st.just("{}")
        # malformed: double comma, missing colon
        obj_malformed = st.one_of(
            st.lists(pair, min_size=1, max_size=3).map(
                lambda ps: "{" + ",,".join(ps) + "}"
            ),
            st.lists(pair, min_size=1, max_size=3).map(
                lambda ps: "{" + " ".join(ps) + "}"
            ),
        )
        obj = st.one_of(obj_members, obj_trailing, obj_empty, obj_malformed)

        arr_elems = st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )
        arr_trailing = st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        )
        arr_empty = st.just("[]")
        arr_malformed = st.one_of(
            st.lists(children, min_size=1, max_size=3).map(
                lambda vs: "[" + ",,".join(vs) + "]"
            ),
            st.lists(children, min_size=1, max_size=3).map(
                lambda vs: "[" + " ".join(vs) + "]"
            ),
        )
        arr = st.one_of(arr_elems, arr_trailing, arr_empty, arr_malformed)

        return st.one_of(obj, arr)

    return st.recursive(leaves, extend, max_leaves=30)

_value_strategy = _build_recursive()

# ---------- top-level ----------

# Deep nesting stressor: many '[' or '{' around a simple value.
_deep_arr = st.integers(min_value=1, max_value=200).map(
    lambda n: "[" * n + "1" + "]" * n
)
_deep_obj = st.integers(min_value=1, max_value=200).map(
    lambda n: '{"a":' * n + "1" + "}" * n
)

# Near-valid malformed top-level fragments
_malformed_toplevel = st.one_of(
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just("[,1]"),
    st.just("{,}"),
    st.just('{"a":}'),
    st.just('{"a" 1}'),
    st.just('"unterminated'),
    st.just("1abc"),
    st.just("[]xyz"),
    st.just("true false"),
    st.just("01"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("0x1F"),
    st.just("//x"),
    st.just("/* */1"),
    st.just("'x'"),
    st.just("{a:1}"),
    # embedded NUL
    st.just("\x00"),
    st.just('{"a":\x00}'),
    st.just('"a\x00b"'),
)

# Duplicate keys
_dup_keys = st.lists(_string, min_size=2, max_size=5).map(
    lambda ks: "{" + ",".join(k + ":1" for k in ks) + "}"
)

# ---------- near-crash intensification ----------

# Structurally mutate around the crashing input: deep-unbalanced brackets,
# truncated containers, and boundary-length nesting. Intensified further:
# wider depth range, more interleavings, deeper targeted mutations, and
# repeated structural fragments re-entering the parser at deeper recursion
# levels.
_near_crash = st.one_of(
    # unbalanced deep nesting (only opens, or only closes)
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "{" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "}" * n),
    # deep nesting missing the innermost value
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + "]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + "}" * n),
    # deep nesting with mismatched closers
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + "}" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "{" * n + "]" * n),
    # truncated deep structures (opens without closes)
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + "1"),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + "1"),
    # boundary-length nesting around a value
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + "1" + "]" * (n - 1)),
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * (n - 1) + "1" + "]" * n),
    # deep nesting with trailing comma at innermost
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + ",]" + "]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + ',}' + "}" * n),
    # alternating open/close interleavings at depth (stress re-entrancy)
    st.integers(min_value=1, max_value=4096).map(lambda n: "[]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "{}" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + "]" * n + "1"),
    st.integers(min_value=1, max_value=4096).map(lambda n: "1" + "[" * n + "]" * n),
    # deeply nested key repetitions (object depth with repeated keys)
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + "[]" + "}" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + "{}" + "}" * n),
    # mixed bracket soup at depth
    st.integers(min_value=1, max_value=4096).map(lambda n: "[{" * n + "}]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "{[" * n + "]}" * n),
    # truncated at the innermost value boundary
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * (n - 1) + "1" + "]" * n),
    # trailing comma deep, truncated
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + ","),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + ","),
    # targeted mutations that re-enter the parser at deeper recursion levels:
    # inject a malformed fragment at an arbitrary depth within a deep structure
    st.tuples(
        st.integers(min_value=1, max_value=4096),
        st.integers(min_value=1, max_value=4096),
        st.sampled_from([",", ",,", ":", "::", "1", "true", "\x00", '"', "\\"]),
    ).map(lambda t: "[" * t[0] + t[2] + "]" * t[1]),
    st.tuples(
        st.integers(min_value=1, max_value=4096),
        st.integers(min_value=1, max_value=4096),
        st.sampled_from([",", ",,", ":", "::", "1", "null", "\x00", '"a"', "\\"]),
    ).map(lambda t: '{"a":' * t[0] + t[2] + "}" * t[1]),
    # two malformed fragments injected at independent depths
    st.tuples(
        st.integers(min_value=1, max_value=2048),
        st.integers(min_value=1, max_value=2048),
        st.sampled_from([",", ",,", ":", "::", "1", "\x00", '"', "\\"]),
        st.sampled_from([",", ",,", ":", "::", "1", "\x00", '"', "\\"]),
    ).map(lambda t: "[" * t[0] + t[2] + "1" + t[3] + "]" * t[1]),
    st.tuples(
        st.integers(min_value=1, max_value=2048),
        st.integers(min_value=1, max_value=2048),
        st.sampled_from([",", ",,", ":", "::", "1", "\x00", '"a"', "\\"]),
        st.sampled_from([",", ",,", ":", "::", "1", "\x00", '"a"', "\\"]),
    ).map(lambda t: '{"a":' * t[0] + t[2] + "1" + t[3] + "}" * t[1]),
    # deep nesting with a truncated string at the innermost level
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + '"'),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + '"'),
    # deep nesting with embedded NUL at the innermost level
    st.integers(min_value=1, max_value=4096).map(lambda n: "[" * n + "\x00" + "]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":' * n + "\x00" + "}" * n),
    # repeated structural fragments to stress re-entrancy paths
    st.integers(min_value=1, max_value=4096).map(lambda n: "[1]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a":1}' * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "[[]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "[]]" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "{{" * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: "}}" * n),
    # deeply nested with alternating fragment injections
    st.integers(min_value=1, max_value=4096).map(lambda n: "[," * n),
    st.integers(min_value=1, max_value=4096).map(lambda n: '{"a"::' * n),
)

strategy = st.one_of(
    _value,
    _deep_arr,
    _deep_obj,
    _malformed_toplevel,
    _dup_keys,
    _unterminated_string,
    _near_crash,
    st.just(""),
    st.just(" "),
    st.just("{}"),
    st.just("[]"),
)