```python
from hypothesis import strategies as st

# ---------- scalar / leaf generators ----------

def _hex(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)


def _unicode_escape():
    # \uXXXX, including surrogate ranges and lone surrogates
    return st.one_of(
        st.builds(lambda h: "\\u" + h, _hex(4)),
        st.just("\\uD800"),
        st.just("\\uDC00"),
        st.just("\\uDFFF"),
        st.just("\\ud800\\udc00"),
    )


def _escape():
    return st.one_of(
        st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
        _unicode_escape(),
    )


def _safe_codepoint():
    # printable-ish plus control bytes and NUL, excluding " and \
    return st.one_of(
        st.characters(min_codepoint=0x00, max_codepoint=0x1F),
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(
            lambda c: c not in '"\\'
        ),
        st.just("\x00"),
        st.just("\x01"),
        st.just("\x7f"),
    )


def _string_body():
    return st.one_of(
        st.lists(_safe_codepoint(), min_size=0, max_size=8).map("".join),
        st.lists(_escape(), min_size=1, max_size=4).map("".join),
        st.lists(
            st.one_of(_safe_codepoint(), _escape()), min_size=0, max_size=8
        ).map("".join),
    )


def _string():
    return _string_body().map(lambda b: '"' + b + '"')


def _unterminated_string():
    return _string_body().map(lambda b: '"' + b)


def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.text(alphabet="0123456789", min_size=1, max_size=20),
    )


def _number():
    def build(sign, ip, frac, exp):
        s = sign + ip
        if frac is not None:
            s += "." + frac
        if exp is not None:
            s += exp
        return s

    sign = st.sampled_from(["", "-"])
    ip = _int_part()
    frac = st.one_of(
        st.none(),
        st.text(alphabet="0123456789", min_size=1, max_size=8),
    )
    exp = st.one_of(
        st.none(),
        st.builds(
            lambda e, s, d: e + s + d,
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.text(alphabet="0123456789", min_size=1, max_size=4),
        ),
        st.just("e309"),
        st.just("E+309"),
        st.just("e-309"),
        st.just("e99999999999999999999"),
    )
    return st.builds(build, sign, ip, frac, exp)


def _bad_number():
    return st.one_of(
        st.just("+1"),
        st.just(".5"),
        st.just("1."),
        st.just("01"),
        st.just("00"),
        st.just("0x1F"),
        st.just("-"),
        st.just("+"),
        st.just("-."),
        st.just("1e"),
        st.just("1e+"),
        st.just("--1"),
        st.just("1..2"),
        st.just("NaN"),
        st.just("Infinity"),
        st.just("-Infinity"),
    )


# ---------- recursive value ----------

def _scalar_value():
    return st.one_of(
        _string(),
        _number(),
        _bad_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )


def _pair(key, value):
    return key + ":" + value


def _obj(inner):
    def build(members, trailing, empty):
        if empty:
            return "{}"
        body = ",".join(members)
        if trailing:
            body += ","
        return "{" + body + "}"

    member = st.builds(
        _pair,
        _string(),
        inner,
    )
    return st.builds(
        build,
        st.lists(member, min_size=0, max_size=5),
        st.booleans(),
        st.booleans(),
    )


def _arr(inner):
    def build(elems, trailing, empty):
        if empty:
            return "[]"
        body = ",".join(elems)
        if trailing:
            body += ","
        return "[" + body + "]"

    return st.builds(
        build,
        st.lists(inner, min_size=0, max_size=5),
        st.booleans(),
        st.booleans(),
    )


def _dup_key_obj(inner):
    def build(key, v1, v2):
        return "{" + key + ":" + v1 + "," + key + ":" + v2 + "}"

    return st.builds(build, _string(), inner, inner)


_value = st.recursive(
    _scalar_value(),
    lambda children: st.one_of(
        _obj(children),
        _arr(children),
        _dup_key_obj(children),
    ),
    max_leaves=30,
)


# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        st.just("{"),
        st.just("}"),
        st.just("["),
        st.just("]"),
        st.just("[1,,2]"),
        st.just("[,]"),
        st.just("[,1]"),
        st.just("{,}"),
        st.just('{"a"}'),
        st.just('{"a":}'),
        st.just('{:1}'),
        st.just("{a:1}"),
        st.just("{'a':1}"),
        st.just('{"a":1'),
        st.just("[1,2"),
        st.just("1abc"),
        st.just("[]xyz"),
        st.just("true false"),
        st.just("1 garbage"),
        st.just("//comment\n1"),
        st.just("/*c*/1"),
        _unterminated_string(),
        st.just('"\\'),
        st.just('"\\u12'),
        st.just('"\\uZZZZ"'),
        st.just(""),
        st.just(" "),
        st.just("\x00"),
        st.just("{\x00:1}"),
        st.just('{"\x00":1}'),
        st.just('{"a":1,"a":2}'),
        st.just("[1,2,]"),
        st.just('{"a":1,}'),
    )


def _deep_nesting():
    return st.integers(min_value=0, max_value=200).flatmap(
        lambda n: st.one_of(
            st.just("[" * n + "]" * n),
            st.just('{"a":' * n + "0" + "}" * n),
            st.just("[" * n + "0" + "," * 0 + "]" * n),
        )
    )


def _control_bytes():
    return st.lists(
        st.integers(min_value=0, max_value=0x1F), min_size=1, max_size=8
    ).map(lambda bs: '"' + "".join(chr(b) for b in bs) + '"')


# ---------- near-crash intensification ----------

_CRASH_SEEDS = [
    '{"a":',
    '[1,',
    '{"a":1,"a":',
    '[[[',
    '{"a":{"b":',
    '[{"a":',
    '{"a":[1,',
    '"\\u',
    '"\\',
    '{"a":1e',
    '{"a":-',
    '{"":',
    '{"a":1,"b":',
    '[1,[2,',
    '{"a":"',
    '{"a":null,',
    '{"a":true,"b":',
    '{"a":{},"b":',
    '{"a":[],"b":',
]


def _near_crash():
    seed = st.sampled_from(_CRASH_SEEDS)
    suffix = st.one_of(
        st.just(""),
        st.just("}"),
        st.just("]"),
        st.just("}]"),
        st.just("}}"),
        st.just("]]"),
        st.just("]}"),
        st.just("1}"),
        st.just("1]"),
        st.just('"a"}'),
        st.just('"a"]'),
        st.just("0}"),
        st.just("null}"),
        st.just("true}"),
        st.just("false]"),
        st.just("\x00}"),
        st.just("1,2}"),
        st.just("1,2]"),
        st.just('"\\u12'),
        st.just('"\\uD800'),
        st.just('"\\uDC00'),
        st.just("e309}"),
        st.just("e-309]"),
        st.just("1e99999999999999999999}"),
    )

    # structural mutations around the crashing input: splice, wrap, nest,
    # truncate, duplicate keys/elems, and inject terminators at random offsets
    def _mutate(s):
        return st.one_of(
            # wrap the seed in additional container depth
            st.builds(
                lambda s, pre, post: pre + s + post,
                st.just(s),
                st.sampled_from(["", "{", "[", '{"a":', "[0,", '{"x":[']),
                st.sampled_from(["", "}", "]", "}", "]}", "}]"]),
            ),
            # splice the seed with a random structural fragment
            st.builds(
                lambda s, mid, tail: s + mid + tail,
                st.just(s),
                st.sampled_from(
                    [",", ":", '"a":', "[", "{", ",\"a\":", ",[", ",{"]
                ),
                st.sampled_from(
                    ["", "}", "]", "0}", '0]', '"a"}', '"a"]', "null}", "true]"]
                ),
            ),
            # truncate the seed at a random position
            st.builds(
                lambda s, n: s[:n],
                st.just(s),
                st.integers(min_value=0, max_value=max(len(s), 1)),
            ),
            # duplicate the seed body (deepens structural nesting)
            st.builds(lambda s: s + s, st.just(s)),
            # append a closing-bracket run
            st.builds(
                lambda s, n: s + "]" * n,
                st.just(s),
                st.integers(min_value=1, max_value=8),
            ),
            st.builds(
                lambda s, n: s + "}" * n,
                st.just(s),
                st.integers(min_value=1, max_value=8),
            ),
            # inject a terminator/separator at a random offset inside the seed
            st.builds(
                lambda s, n, tok: s[:n] + tok + s[n:],
                st.just(s),
                st.integers(min_value=0, max_value=max(len(s), 1)),
                st.sampled_from(
                    [",", ":", "]", "}", '"', "\\", "\x00", "e", "-", "[", "{"]
                ),
            ),
            # interleave the seed with a structural fragment at random offset
            st.builds(
                lambda s, n, frag: s[:n] + frag + s[n:],
                st.just(s),
                st.integers(min_value=0, max_value=max(len(s), 1)),
                st.sampled_from(
                    [
                        '{"a":',
                        "[1,",
                        ",[",
                        ",{",
                        ',"a":',
                        "null,",
                        "true,",
                        '""',
                        "0",
                        "1e309",
                        '"\\u',
                    ]
                ),
            ),
            # delete a random slice of the seed
            st.builds(
                lambda s, a, b: s[:a] + s[b:],
                st.just(s),
                st.integers(min_value=0, max_value=max(len(s), 1)),
                st.integers(min_value=0, max_value=max(len(s), 1)),
            ),
            # duplicate a random slice of the seed
            st.builds(
                lambda s, a, b: s[:a] + s[b:] + s[a:b],
                st.just(s),
                st.integers(min_value=0, max_value=max(len(s), 1)),
                st.integers(min_value=0, max_value=max(len(s), 1)),
            ),
        )

    mutated = seed.flatmap(_mutate)
    return st.one_of(
        st.builds(lambda s, suf: s + suf, seed, suffix),
        mutated,
    )


strategy = st.one_of(
    _value,
    _malformed(),
    _deep_nesting(),
    _control_bytes(),
    _near_crash(),
    st.builds(lambda v: v, _value),
)
```