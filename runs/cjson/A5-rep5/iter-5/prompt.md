Here is the current Hypothesis strategy:

```python
import json
from hypothesis import strategies as st


# ---------- primitives ----------

def _safe_codepoint():
    # printable ASCII that is safe inside JSON strings
    return st.integers(min_value=0x20, max_value=0x7E)


def _hex_char():
    return st.sampled_from("0123456789abcdefABCDEF")


def _hex4():
    return st.tuples(_hex_char(), _hex_char(), _hex_char(), _hex_char()).map(
        lambda t: "".join(t)
    )


def _unicode_escape():
    # \uXXXX, including lone surrogates (rejected) and valid pairs
    return _hex4().map(lambda h: "\\u" + h)


def _escaped_char():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    return st.one_of(simple, _unicode_escape())


def _string_char():
    # normal safe chars, escapes, raw control bytes, raw NUL
    normal = _safe_codepoint().map(chr)
    raw_ctrl = st.integers(min_value=0, max_value=0x1F).map(chr)
    raw_del = st.just("\x7f")
    return st.one_of(normal, _escaped_char(), raw_ctrl, raw_del)


def _string_body():
    return st.lists(_string_char(), max_size=12).map(lambda cs: "".join(cs))


def _string():
    return st.tuples(st.just('"'), _string_body(), st.just('"')).map(
        lambda t: t[0] + t[1] + t[2]
    )


# ---------- numbers ----------

def _digits():
    return st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=6).map(
        lambda ds: "".join(str(d) for d in ds)
    )


def _int_part():
    zero = st.just("0")
    nonzero = st.tuples(
        st.integers(min_value=1, max_value=9).map(str),
        st.lists(st.integers(min_value=0, max_value=9), max_size=5).map(
            lambda ds: "".join(str(d) for d in ds)
        ),
    ).map(lambda t: t[0] + t[1])
    leading_zero = st.tuples(st.just("0"), _digits()).map(lambda t: t[0] + t[1])
    return st.one_of(zero, nonzero, leading_zero)


def _frac():
    return st.tuples(st.just("."), _digits()).map(lambda t: t[0] + t[1])


def _trailing_dot():
    return st.just(".")


def _exp():
    e = st.sampled_from("eE")
    sign = st.sampled_from(["", "+", "-"])
    digits = _digits()
    return st.tuples(e, sign, digits).map(lambda t: t[0] + t[1] + t[2])


def _extreme_exp():
    # extreme exponents including overflow like 1e309
    big = st.integers(min_value=300, max_value=9999).map(str)
    return st.tuples(st.sampled_from("eE"), st.sampled_from(["", "+", "-"]), big).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _number():
    sign = st.sampled_from(["", "-"])
    intp = _int_part()
    frac = st.one_of(st.none(), _frac(), _trailing_dot())
    exp = st.one_of(st.none(), _exp(), _extreme_exp())
    hexn = st.tuples(
        st.sampled_from(["0x", "0X"]), _digits()
    ).map(lambda t: t[0] + t[1])

    def build(t):
        s, i, f, e = t
        out = s + i
        if f is not None:
            out += f
        if e is not None:
            out += e
        return out

    return st.one_of(st.tuples(sign, intp, frac, exp).map(build), hexn)


# ---------- malformed fragments ----------

def _malformed():
    return st.sampled_from([
        "",
        "-",
        "+1",
        ".5",
        "NaN",
        "Infinity",
        "-Infinity",
        "01",
        "1.",
        "0x10",
        "1e",
        "1e+",
        "1e-",
        "1.",
        "[1,]",
        '{"a":1,}',
        '{"a" 1}',
        '{"a":}',
        '{"a"}',
        "{,}",
        "[,]",
        "[,1]",
        '"unterminated',
        "'single'",
        "{'a':1}",
        "{a:1}",
        "\\u",
        "\\ud800",
        "\\udc00",
        "\\x41",
        "tru",
        "fals",
        "nul",
        "truex",
        "falsex",
        "nullx",
        "\ufeff",
        "\x00",
        "\x01",
        "\t",
        "\n",
        " ",
        "  ",
        "1abc",
        "1 2",
        "{}extra",
        "[]extra",
        "[1] [2]",
        "{} {}",
        "1,",
        ",1",
        ":",
        "::",
        "{:}",
        "[]]",
        "{}}",
        "}{",
        "][",
        "1.2.3",
        "1e1e1",
        "--1",
        "-.5",
        "0.",
        "00",
        "00.1",
        "0e",
        "0e+",
        "0e-",
        "0e1e",
        "[1 2]",
        '{"a":1 "b":2}',
        '{"a":1,,"b":2}',
        '["a" "b"]',
        '["a",,]',
        '{"a":}',
        '{"a":,}',
        '{"a"::1}',
        '{"":}',
        "{:1}",
    ])


# ---------- recursive values ----------

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed(),
    )


def _key():
    return st.one_of(_string(), _malformed())


def _pair(key_strategy, value_strategy):
    return st.tuples(key_strategy, st.just(":"), value_strategy).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _obj(value_strategy):
    def build(pairs):
        return "{" + ",".join(pairs) + "}"

    empty = st.just("{}")
    nonempty = st.lists(
        _pair(_key(), value_strategy), min_size=1, max_size=6
    ).map(build)
    # duplicate keys
    dup = st.tuples(_key(), value_strategy).map(
        lambda t: '{"' + t[0].strip('"') + '":' + t[1] + ',"' + t[0].strip('"') + '":' + t[1] + "}"
    )
    return st.one_of(empty, nonempty, dup)


def _arr(value_strategy):
    def build(vals):
        return "[" + ",".join(vals) + "]"

    empty = st.just("[]")
    nonempty = st.lists(value_strategy, min_size=1, max_size=6).map(build)
    return st.one_of(empty, nonempty)


def _value():
    return st.recursive(
        _leaf(),
        lambda children: st.one_of(_obj(children), _arr(children)),
        max_leaves=8,
    )


# ---------- deep nesting near the 1000 limit ----------

def _deep_nesting():
    # depths near the parser limit of 1000
    depth = st.integers(min_value=1, max_value=1000)
    kind = st.sampled_from(["arr", "obj"])

    def build(t):
        d, k = t
        if k == "arr":
            return "[" * d + "]" * d
        else:
            return '{"a":' * d + "null" + "}" * d

    return st.tuples(depth, kind).map(build)


def _deep_nesting_over():
    depth = st.integers(min_value=1001, max_value=1200)

    def build(d):
        return "[" * d + "]" * d

    return depth.map(build)


# ---------- top-level ----------

def _top_level():
    return st.one_of(
        _value(),
        _malformed(),
        _deep_nesting(),
        _deep_nesting_over(),
        # trailing content after a complete value (accepted)
        st.tuples(_value(), _malformed()).map(lambda t: t[0] + t[1]),
        st.tuples(_value(), st.just(" "), _value()).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        # BOM prefix
        st.tuples(st.just("\ufeff"), _value()).map(lambda t: t[0] + t[1]),
        # raw NUL after a value
        st.tuples(_value(), st.just("\x00")).map(lambda t: t[0] + t[1]),
    )


strategy = _top_level()
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.