```python
from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

def _escaped_string():
    # safe codepoints: exclude " \ and control chars
    safe = st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
        '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
    )
    escapes = st.sampled_from(
        ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
    )
    unicode_esc = st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
    )
    # lone surrogates (rejected) and valid pairs
    lone_surrogate = st.sampled_from(
        ["\\ud800", "\\udfff", "\\udabc", "\\udc00"]
    )
    surrogate_pair = st.builds(
        lambda hi, lo: "\\u" + hi + "\\u" + lo,
        st.sampled_from(["d800", "dbff", "d801"]),
        st.sampled_from(["dc00", "dfff", "dc01"]),
    )
    # raw control / NUL bytes inside a string (accepted by parser)
    raw_ctrl = st.sampled_from(
        ["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]
    )
    # invalid / near-miss escapes to exercise error paths
    bad_escape = st.sampled_from(
        ["\\x41", "\\u12", "\\u", "\\uZZZZ", "\\", "\\a", "\\'", "\\U0041"]
    )
    inner = st.one_of(
        safe,
        escapes,
        unicode_esc,
        lone_surrogate,
        surrogate_pair,
        raw_ctrl,
        bad_escape,
    )
    return st.lists(inner, max_size=8).map("".join).map(lambda s: '"' + s + '"')


def _number():
    digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
    int_part = st.one_of(
        st.just("0"),
        st.builds(lambda d: d, st.text(alphabet="123456789", min_size=1, max_size=1)),
        st.builds(
            lambda a, b: a + b,
            st.text(alphabet="123456789", min_size=1, max_size=1),
            st.text(alphabet="0123456789", min_size=0, max_size=5),
        ),
    )
    # leading zeros (accepted by parser)
    leading_zero = st.builds(
        lambda z, d: "0" + z + d,
        st.text(alphabet="0123456789", min_size=1, max_size=3),
        st.text(alphabet="0123456789", min_size=1, max_size=3),
    )
    frac = st.builds(
        lambda d: "." + d,
        st.text(alphabet="0123456789", min_size=1, max_size=6),
    )
    # trailing dot (accepted)
    trailing_dot = st.just(".")
    exp = st.builds(
        lambda e, s, d: e + s + d,
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    )
    # extreme exponents
    extreme_exp = st.sampled_from(
        ["e309", "e999", "e-999", "e+308", "E400", "e00000000000000000000001"]
    )
    hex_num = st.builds(
        lambda h: "0x" + h,
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8),
    )
    sign = st.sampled_from(["", "-"])
    base = st.one_of(int_part, leading_zero)
    body = st.tuples(
        base,
        st.one_of(st.none(), frac, trailing_dot),
        st.one_of(st.none(), exp, extreme_exp),
    ).map(lambda t: t[0] + (t[1] or "") + (t[2] or ""))
    num = st.tuples(sign, body).map(lambda t: t[0] + t[1])
    return st.one_of(num, hex_num)


# ---------- recursive structure ----------

# depth budget: concentrate near the 1000 limit
_depth_choices = st.one_of(
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=990, max_value=1005),
    st.integers(min_value=100, max_value=900),
)


def _leaf():
    return st.one_of(
        _escaped_string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )


def _ws():
    return st.text(alphabet=" \t\n\r", max_size=3)


value = st.recursive(
    _leaf(),
    lambda children: st.one_of(
        # array
        st.tuples(
            _ws(),
            st.lists(children, max_size=4),
            _ws(),
        ).map(lambda t: "[" + t[0] + ",".join(t[1]) + t[2] + "]"),
        # object with possible duplicate keys
        st.tuples(
            _ws(),
            st.lists(
                st.tuples(_escaped_string(), st.just(":"), children).map(
                    lambda t: t[0] + t[1] + t[2]
                ),
                max_size=4,
            ),
            _ws(),
        ).map(lambda t: "{" + t[0] + ",".join(t[1]) + t[2] + "}"),
    ),
    max_leaves=40,
)


def _deep(depth):
    # build a deeply nested array at exactly `depth` levels
    return st.just("[" * depth + "0" + "]" * depth)


def _deep_obj(depth):
    return st.just('{"a":' * depth + "0" + "}" * depth)


deep_value = _depth_choices.flatmap(
    lambda d: st.one_of(_deep(d), _deep_obj(d))
)


# ---------- malformed / near-valid inputs ----------

def _malformed():
    return st.sampled_from(
        [
            "",
            " ",
            ",",
            "[,]",
            "{,}",
            "[1,]",
            '{"a":1,}',
            '{"a" 1}',
            '{"a":}',
            "{:1}",
            "[1 2]",
            '"unterminated',
            "'single'",
            "{unquoted:1}",
            "+1",
            ".5",
            "-",
            "-.",
            "NaN",
            "Infinity",
            "-Infinity",
            "01",
            "1.",
            "0x10",
            "1e",
            "1e+",
            "1e-",
            "tru",
            "fals",
            "nul",
            "True",
            "NULL",
            '"\\x41"',
            '"\\u12"',
            '"\\ud800"',
            '"\\udfff"',
            "\xef\xbb\xbf",  # BOM alone (no value)
            "\x00",
            "1\x00",
            "\x00{}",
        ]
    )


# trailing content after a valid value is ACCEPTED
trailing = st.tuples(
    value,
    st.one_of(
        st.just(""),
        st.sampled_from(["abc", " 1 2", "\x00", "\n", "[]", "junk", "\x00\x00"]),
    ),
).map(lambda t: t[0] + t[1])


# leading BOM then value (accepted)
bom_value = value.map(lambda v: "\xef\xbb\xbf" + v)


# ---------- near-valid mutation of valid values ----------

def _mutate(s):
    # single-byte / structural mutations applied to a valid JSON string
    if not s:
        return s
    i = len(s) // 2
    return s[:i] + s[i + 1:]


def _mutated():
    return value.map(_mutate).filter(lambda s: len(s) > 0)


# ---------- truncated valid values (exercise EOF handling) ----------

def _truncated():
    return value.flatmap(
        lambda s: st.one_of(
            st.just(s[: max(0, len(s) - 1)]),
            st.just(s[: max(0, len(s) // 2)]),
            st.just(s[:1]),
        )
    )


# ---------- deeper structural mutation of valid values ----------

def _mutate_multi(s):
    # apply several random-ish single-byte deletions/insertions to exercise
    # parser state after partially-consumed tokens
    if len(s) < 2:
        return s
    out = list(s)
    # delete a byte near the middle
    i = len(out) // 2
    del out[i]
    # insert a stray structural byte
    j = len(out) // 3
    out.insert(j, "[")
    # duplicate a token boundary
    k = min(len(out) - 1, (2 * len(out)) // 3)
    out.insert(k, ",")
    return "".join(out)


def _mutated_multi():
    return value.map(_mutate_multi)


# ---------- deeply nested with trailing garbage ----------

def _deep_with_trailing():
    return st.tuples(
        deep_value,
        st.sampled_from(["", "x", "]", "}", ",", "\x00", " null"]),
    ).map(lambda t: t[0] + t[1])


strategy = st.one_of(
    value,
    deep_value,
    _malformed(),
    trailing,
    bom_value,
    _mutated(),
    _truncated(),
    _mutated_multi(),
    _deep_with_trailing(),
)
```