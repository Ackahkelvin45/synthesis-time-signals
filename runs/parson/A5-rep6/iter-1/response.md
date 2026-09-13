```python
from hypothesis import strategies as st
import json

# ---- Leaf strategies -------------------------------------------------------

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _unicode_escape():
    return st.builds(lambda h: "\\u" + h, _hex4())

def _surrogate_escape():
    # lone surrogates and paired surrogates
    lo = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda n: "\\u%04x" % n)
    hi = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda n: "\\u%04x" % n)
    paired = st.builds(lambda a, b: a + b, lo, hi)
    return st.one_of(lo, hi, paired)

def _simple_escape():
    return st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _safe_char():
    # printable ASCII excluding " and \
    return st.text(
        alphabet=st.characters(
            blacklist_categories=["Cs"],
            blacklist_characters='"\\\x00',
            min_codepoint=0x20,
            max_codepoint=0x7E,
        ),
        min_size=1,
        max_size=1,
    )

def _control_escape():
    # \uXXXX form of control chars (allowed, unlike raw control bytes)
    return st.integers(min_value=0x00, max_value=0x1F).map(lambda n: "\\u%04x" % n)

def _string_body_piece():
    return st.one_of(
        _safe_char(),
        _simple_escape(),
        _unicode_escape(),
        _surrogate_escape(),
        _control_escape(),
        st.just("\\u0000"),
    )

def _string():
    body = st.lists(_string_body_piece(), min_size=0, max_size=12).map("".join)
    return st.builds(lambda b: '"' + b + '"', body)

def _unterminated_string():
    body = st.lists(_string_body_piece(), min_size=0, max_size=8).map("".join)
    return st.builds(lambda b: '"' + b, body)

# ---- Number strategies -----------------------------------------------------

def _int_part():
    zero = st.just("0")
    nonzero = st.builds(
        lambda d, rest: d + rest,
        st.integers(min_value=1, max_value=9).map(str),
        st.text(alphabet="0123456789", min_size=0, max_size=12),
    )
    return st.one_of(zero, nonzero)

def _frac_part():
    return st.builds(
        lambda ds: "." + ds,
        st.text(alphabet="0123456789", min_size=1, max_size=12),
    )

def _exp_part():
    return st.builds(
        lambda sign, ds: "e" + sign + ds,
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    )

def _extreme_exp():
    # extreme / overflow exponents like 1e309, 1e-400, 1e99999
    return st.one_of(
        st.integers(min_value=300, max_value=400).map(lambda n: "e%d" % n),
        st.integers(min_value=300, max_value=400).map(lambda n: "e-%d" % n),
        st.integers(min_value=100000, max_value=999999).map(lambda n: "e%d" % n),
        st.integers(min_value=1, max_value=400).map(lambda n: "e+%d" % n),
    )

def _number():
    sign = st.sampled_from(["", "-"])
    base = _int_part()
    frac = st.one_of(st.none(), _frac_part())
    exp = st.one_of(st.none(), _exp_part(), _extreme_exp())
    return st.builds(
        lambda s, i, f, e: s + i + (f or "") + (e or ""),
        sign, base, frac, exp,
    )

def _malformed_number():
    # leading +, leading zeros, lone dot, trailing dot, lone sign
    return st.one_of(
        st.builds(lambda ds: "+" + ds, _int_part()),
        st.builds(
            lambda z, rest: "0" + rest,
            st.just("0"),
            st.text(alphabet="0123456789", min_size=1, max_size=6),
        ),
        st.builds(lambda ds: "." + ds, st.text(alphabet="0123456789", min_size=1, max_size=6)),
        st.builds(lambda i: i + ".", _int_part()),
        st.just("-"),
        st.just("-."),
        st.just("+"),
    )

# ---- Recursive structure ---------------------------------------------------

def _pair(key_strategy, value_strategy):
    return st.builds(
        lambda k, v: k + ":" + v,
        key_strategy,
        value_strategy,
    )

def _obj(key_strategy, value_strategy):
    empty = st.just("{}")
    pair = _pair(key_strategy, value_strategy)
    single = st.builds(lambda p: "{" + p + "}", pair)
    multi = st.builds(
        lambda ps: "{" + ",".join(ps) + "}",
        st.lists(pair, min_size=2, max_size=5),
    )
    # duplicate keys deliberately
    dup = st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        key_strategy,
        value_strategy,
        value_strategy,
    )
    return st.one_of(empty, single, multi, dup)

def _arr(value_strategy):
    empty = st.just("[]")
    single = st.builds(lambda v: "[" + v + "]", value_strategy)
    multi = st.builds(
        lambda vs: "[" + ",".join(vs) + "]",
        st.lists(value_strategy, min_size=2, max_size=6),
    )
    return st.one_of(empty, single, multi)

def _malformed_value():
    return st.one_of(
        _unterminated_string(),
        st.just("{"),
        st.just("["),
        st.just("}"),
        st.just("]"),
        st.just(","),
        st.just(":"),
        st.just("{" + '"a"' + "}"),
        st.just("{" + '"a"' + ":" + "}"),
        st.just("[" + "," + "]"),
        st.just("[" + "1" + "," + "," + "2" + "]"),
        st.just('{"a":1,}'),
        st.just("[1,2,]"),
        st.just('{"a" 1}'),
        st.just('{a:1}'),
        st.just("tru"),
        st.just("nul"),
        st.just("fals"),
        st.just("truex"),
    )

# ---- Build recursive value strategy ---------------------------------------

def _make_value():
    leaf = st.one_of(
        _string(),
        _number(),
        _malformed_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _malformed_value(),
    )
    return st.recursive(
        leaf,
        lambda children: st.one_of(
            _obj(_string(), children),
            _arr(children),
        ),
        max_leaves=40,
    )

_value = _make_value()

# ---- Depth near the 2048 limit --------------------------------------------

def _deep_nesting():
    # concentrate near the cap: brackets nested to depth close to 2048
    def build(depth, opener, closer):
        return opener * depth + closer * depth

    depths = st.one_of(
        st.integers(min_value=2000, max_value=2060),
        st.integers(min_value=1024, max_value=2048),
        st.integers(min_value=2048, max_value=2100),
    )
    return st.builds(
        lambda d, pair: build(d, pair[0], pair[1]),
        depths,
        st.sampled_from([("[", "]"), ("{", "}")]),
    )

def _deep_with_value():
    def build(depth, val):
        return "[" * depth + val + "]" * depth

    return st.builds(
        build,
        st.integers(min_value=1000, max_value=2048),
        st.one_of(st.just("1"), st.just('"x"'), st.just("null")),
    )

# ---- Trailing content (accepted by this parser) ---------------------------

def _trailing():
    return st.builds(
        lambda v, t: v + t,
        _value,
        st.one_of(
            st.just("abc"),
            st.just(" garbage"),
            st.just("xyz"),
            st.just(" 123"),
            st.just("//comment"),
            st.just("/* c */"),
            st.text(alphabet="abcxyz \t\n", min_size=1, max_size=8),
        ),
    )

# ---- Top-level strategy ----------------------------------------------------

def _top():
    return st.one_of(
        _value,
        _deep_nesting(),
        _deep_with_value(),
        _trailing(),
        _malformed_value(),
        _malformed_number(),
        _unterminated_string(),
    )

strategy = _top()
```