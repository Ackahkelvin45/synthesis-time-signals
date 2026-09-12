```python
from hypothesis import strategies as st


# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

def _unicode_escape():
    # \uXXXX, including surrogate halves and lone surrogates
    return st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet=_hex, min_size=4, max_size=4),
    )


_short_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])


def _string_char():
    return st.one_of(
        _short_escapes,
        _unicode_escape(),
        # safe code points, plus deliberately unsafe control bytes / NUL
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(
            lambda c: c not in ('"', "\\")
        ),
        st.sampled_from(["\x00", "\x01", "\x1f", "\x7f", "\x0b", "\x0c"]),
    )


def _json_string():
    return st.lists(_string_char(), max_size=12).map(lambda cs: '"' + "".join(cs) + '"')


# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        # malformed leading-zero forms (near-valid)
        st.integers(min_value=1, max_value=99).map(lambda n: "0" + str(n)),
    )


def _frac_part():
    return st.one_of(
        st.nothing(),
        st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
        st.just("."),  # trailing dot (malformed)
    )


def _exp_part():
    return st.one_of(
        st.nothing(),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.one_of(
                st.integers(min_value=0, max_value=10**3).map(str),
                st.sampled_from(["309", "308", "400", "999", "01", "007"]),
            ),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )


def _number():
    return st.one_of(
        # well-formed-ish
        st.tuples(
            st.sampled_from(["", "-"]),
            _int_part(),
            _frac_part(),
            _exp_part(),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        # lone minus (accepted by parser)
        st.just("-"),
        # leading plus (malformed)
        st.integers(min_value=0, max_value=10**6).map(lambda n: "+" + str(n)),
        # leading dot (malformed)
        st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
        # hex (malformed)
        st.integers(min_value=0, max_value=0xFFFF).map(lambda n: hex(n)),
        # extreme overflow magnitudes
        st.sampled_from(["1e309", "-1e309", "1e9999", "1e-9999", "1E+400"]),
    )


# ---------- recursive structure ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])


def _value(draw_depth):
    # base scalars
    scalars = st.one_of(
        _json_string(),
        _number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        # malformed scalars
        st.just("True"),
        st.just("NULL"),
        st.just("nul"),
        st.just("+"),
        st.just("."),
    )
    if draw_depth <= 0:
        return scalars

    obj = _obj(draw_depth - 1)
    arr = _arr(draw_depth - 1)
    return st.one_of(scalars, obj, arr)


def _pair(depth):
    key = st.one_of(
        _json_string(),
        # bare key (malformed)
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=6),
    )
    sep = st.one_of(st.just(":"), st.just(""), st.just("::"), st.just(" "))
    return st.tuples(key, sep, _value(depth)).map(lambda t: t[0] + t[1] + t[2])


def _obj(depth):
    return st.one_of(
        st.just("{}"),
        # object with members (stressed first-pass path)
        st.tuples(
            _pair(depth),
            st.lists(
                st.tuples(st.just(","), _pair(depth)).map(lambda t: t[0] + t[1]),
                max_size=4,
            ),
            st.sampled_from(["", ","]),  # optional single trailing comma
        ).map(lambda t: "{" + t[0] + "".join(t[1]) + t[2] + "}"),
        # malformed object variants
        st.tuples(
            st.just("{"),
            st.lists(_json_string(), min_size=0, max_size=3),
            st.just("}"),
        ).map(lambda t: t[0] + ",".join(t[1]) + t[2]),
        st.just("{,}"),
        st.just("{:1}"),
        st.just('{"a" 1}'),
        st.just('{"a":}'),
    )


def _arr(depth):
    return st.one_of(
        st.just("[]"),
        st.tuples(
            _value(depth),
            st.lists(
                st.tuples(st.just(","), _value(depth)).map(lambda t: t[0] + t[1]),
                max_size=4,
            ),
            st.sampled_from(["", ","]),  # optional single trailing comma
        ).map(lambda t: "[" + t[0] + "".join(t[1]) + t[2] + "]"),
        # malformed array variants
        st.just("[1,,2]"),
        st.just("[,]"),
        st.just("[,1]"),
        st.just("[1 2]"),
        st.just("["),
    )


# ---------- top-level ----------

def _top():
    return st.one_of(
        _value(3),
        # deep nesting (no depth cap in parser)
        st.integers(min_value=1, max_value=64).map(lambda n: "[" * n + "]" * n),
        st.integers(min_value=1, max_value=32).map(
            lambda n: "[" * n + '{"a":' * n + "1" + "}" * n + "]" * n
        ),
        # near-valid-but-malformed whole inputs
        st.just(""),
        st.just("   "),
        st.just("{"),
        st.just("["),
        st.just('"unterminated'),
        st.just("'single'"),
        st.just("{a:1}"),
        st.just("1abc"),
        st.just("[]xyz"),
        st.just("1 garbage"),
        st.just("true false"),
        st.just("\x00"),
        st.just("\x00\x01\x02"),
        st.just("\x00{}"),
        st.just("{}\x00"),
        st.just('{"\x00":1}'),
        st.just('["\x00"]'),
        st.just('{"a":1,"a":2}'),
        st.just('{"\\uD800":1}'),
        st.just('"\\uD800"'),
        st.just('"\\uDC00\\uD800"'),
        st.just('"\\uD83D\\uDE00"'),
        st.just("[1,2,]"),
        st.just('{"a":1,}'),
        st.just("1e309"),
        st.just("-"),
    )


strategy = st.recursive(
    _value(0),
    lambda children: st.one_of(
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_json_string(), st.just(":"), children).map(
                    lambda t: t[0] + t[1] + t[2]
                ),
                max_size=4,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(
            st.just("["),
            st.lists(children, max_size=4).map(lambda vs: ",".join(vs)),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    ),
    max_leaves=64,
)

# improve_strategy: interleave insignificant whitespace *between* structural
# tokens (JSON permits ws around every token), not just at the outer edges.
# This exercises the tokenizer's whitespace-skipping and state transitions
# throughout the document. Whitespace is injected at every nesting level:
# after '{', '[', ',', ':', and before '}', ']', and around scalars.
_ws_opt = st.one_of(st.just(""), _ws)


def _ws_value(depth):
    inner = _value(depth)
    return st.tuples(_ws_opt, inner, _ws_opt).map(lambda t: t[0] + t[1] + t[2])


def _ws_pair(depth):
    return st.tuples(
        _ws_opt,
        _json_string(),
        _ws_opt,
        st.sampled_from([":", " : ", ":", "::", ""]),
        _ws_opt,
        _ws_value(depth),
    ).map(lambda t: "".join(t))


def _ws_obj(depth):
    if depth <= 0:
        return st.just("{}")
    member = st.tuples(
        _ws_pair(depth - 1),
        st.lists(
            st.tuples(
                _ws_opt,
                st.just(","),
                _ws_opt,
                _ws_pair(depth - 1),
            ).map(lambda t: "".join(t)),
            max_size=3,
        ),
    ).map(lambda t: t[0] + "".join(t[1]))
    return st.tuples(
        st.just("{"),
        _ws_opt,
        st.one_of(
            st.tuples(member, _ws_opt, st.sampled_from(["", ","]), _ws_opt).map(
                lambda t: "".join(t)
            ),
            st.just(""),
        ),
        st.just("}"),
    ).map(lambda t: "".join(t))


def _ws_arr(depth):
    if depth <= 0:
        return st.just("[]")
    elem = st.tuples(
        _ws_value(depth - 1),
        st.lists(
            st.tuples(
                _ws_opt,
                st.just(","),
                _ws_opt,
                _ws_value(depth - 1),
            ).map(lambda t: "".join(t)),
            max_size=3,
        ),
    ).map(lambda t: t[0] + "".join(t[1]))
    return st.tuples(
        st.just("["),
        _ws_opt,
        st.one_of(
            st.tuples(elem, _ws_opt, st.sampled_from(["", ","]), _ws_opt).map(
                lambda t: "".join(t)
            ),
            st.just(""),
        ),
        st.just("]"),
    ).map(lambda t: "".join(t))


_ws_structural = st.recursive(
    _ws_value(0),
    lambda children: st.one_of(
        _ws_obj(2),
        _ws_arr(2),
    ),
    max_leaves=32,
)

# Outer whitespace wrap, plus whitespace-rich whole documents.
_ws_wrap = st.tuples(
    _ws_opt,
    st.one_of(strategy, _top()),
    _ws_opt,
).map(lambda t: t[0] + t[1] + t[2])

strategy = st.one_of(strategy, _top(), _ws_wrap, _ws_structural)
```