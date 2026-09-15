```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex_chars(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

# Raw bytes that are legal-ish inside strings, including NUL and controls.
_RAW_STRING_BYTES = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),  # no lone surrogates
            blacklist_characters='"\\',
        ),
        max_size=8,
    ),
    # embedded NUL / control bytes
    st.text(
        alphabet=st.sampled_from(
            ["\x00", "\x01", "\x08", "\t", "\n", "\r", "\x1f", "\x7f"]
        ),
        min_size=1,
        max_size=4,
    ),
    # valid escapes
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    # \uXXXX escapes, including surrogate ranges
    st.builds(lambda h: "\\u" + h, _hex_chars(4)),
    st.sampled_from(["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\u0000", "\\uFFFF"]),
    # invalid escapes (parser rejects these when they terminate the string)
    st.sampled_from(["\\x", "\\q", "\\u12", "\\uZZZZ", "\\"]),
)

_string_body = st.lists(_RAW_STRING_BYTES, max_size=6).map("".join)


def _quoted(body):
    return '"' + body + '"'


# A string that is usually valid but sometimes deliberately unterminated/malformed.
_STRING_STRATEGY = st.one_of(
    _string_body.map(_quoted),
    _string_body.map(lambda b: '"' + b),            # unterminated
    st.just('"'),
    st.just("'single-quoted'"),
    st.just(""),
)

# ---------- numbers ----------

_INT_PART = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.just("01"),                    # leading zero (accepted by parser)
    st.just("007"),
    st.just("0x10"),                  # hex (accepted)
    st.just("0XFF"),
    st.just(""),                      # will join with '-' to make lone "-"
)

_FRAC_PART = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    st.just("."),                     # trailing dot (accepted)
    st.just(".5"),                    # bare frac (rejected when leading)
    st.just(".0"),
)

_EXP_PART = st.one_of(
    st.just(""),
    st.sampled_from(["e0", "e1", "e01", "E+2", "e-3"]),
    st.integers(min_value=100, max_value=400).map(lambda n: "e" + str(n)),
    st.just("e309"),
    st.just("e-309"),
    st.just("e9999"),
    st.just("E+000"),
)

_NUMBER_STRATEGY = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), _INT_PART, _FRAC_PART, _EXP_PART).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    ),
    st.sampled_from(["-", "+1", "NaN", "Infinity", "-Infinity", "."]),
    st.just("1e309"),
    st.just("-1e309"),
)

# ---------- recursive structure ----------

_WS = st.sampled_from(["", " ", "\t", "\n", "\r", "  "])

_ATOM = st.one_of(
    _STRING_STRATEGY,
    _NUMBER_STRATEGY,
    st.sampled_from(["true", "false", "null", "True", "NULL"]),
)

# depth control: concentrate near the parser's 1000-level limit.
_DEPTH = st.one_of(
    st.integers(min_value=0, max_value=5),
    st.sampled_from([998, 999, 1000, 1001, 1002, 1005, 1010]),
)


def _wrap(depth, inner, open_ch, close_ch):
    return open_ch * depth + inner + close_ch * depth


def _build_value(elem):
    """elem() returns a strategy for a value."""
    return st.one_of(
        _ATOM,
        st.builds(lambda d, e: _wrap(d, e, "[", "]"), _DEPTH, elem()),
        st.builds(lambda d, e: _wrap(d, e, "{", "}"), _DEPTH, elem()),
    )


_value = st.recursive(
    _ATOM,
    lambda children: st.one_of(
        # arrays
        st.one_of(
            st.just("[]"),
            st.builds(
                lambda d, xs: "[" * d + ",".join(xs) + "]" * d,
                _DEPTH,
                st.lists(children, min_size=1, max_size=4),
            ),
            st.builds(
                lambda xs: "[" + ",".join(xs) + "]",
                st.lists(children, min_size=1, max_size=4),
            ),
            # malformed array variants
            st.builds(lambda xs: "[" + ",".join(xs) + ",]", st.lists(children, min_size=0, max_size=3)),
            st.builds(lambda xs: "[" + " ".join(xs) + "]", st.lists(children, min_size=1, max_size=3)),
            st.just("["),
            st.just("[,"),
        ),
        # objects
        st.one_of(
            st.just("{}"),
            st.builds(
                lambda d, ps: "{" * d + ",".join(ps) + "}" * d,
                _DEPTH,
                st.lists(_pair(), min_size=1, max_size=4),
            ),
            st.builds(
                lambda ps: "{" + ",".join(ps) + "}",
                st.lists(_pair(), min_size=1, max_size=4),
            ),
            # duplicate keys
            st.builds(
                lambda v: '{"k":' + v + ',"k":' + v + "}",
                children,
            ),
            # malformed object variants
            st.builds(lambda ps: "{" + ",".join(ps) + ",}", st.lists(_pair(), min_size=0, max_size=3)),
            st.builds(lambda ps: "{" + " ".join(ps) + "}", st.lists(_pair(), min_size=1, max_size=3)),
            st.just("{"),
            st.just("{,"),
            st.just('{"a" 1}'),
            st.just('{"a":}'),
        ),
    ),
    max_leaves=12,
)


def _pair():
    key = st.one_of(
        _string_body.map(_quoted),
        st.sampled_from(['"a"', '"k"', '"\\u0000"', '"\\ud800"', '"dup"']),
    )
    return st.builds(
        lambda k, v: k + ":" + v,
        key,
        _value,
    )


# ---------- top-level ----------

_TOP = st.one_of(
    _value,
    # trailing content after a complete value (accepted; parser stops early)
    st.builds(lambda v, t: v + t, _value, st.sampled_from(["", " ", "abc", " 1 2", "\x00", "\x00junk", "//x"])),
    # BOM prefix (accepted)
    st.builds(lambda v: "\ufeff" + v, _value),
    # empty / near-empty malformed inputs
    st.sampled_from(["", " ", "\ufeff", ",", ":", "]"]),
)

strategy = _TOP
```