Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_ESCAPES = ["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

def _unicode_escape():
    return st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
    )

def _surrogate_escape():
    return st.sampled_from(
        ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD83D\\uDE00", "\\uD800\\uD800"]
    )

def _control_byte():
    return st.integers(min_value=0x00, max_value=0x1F).map(chr)

_SAFE = st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f')

def _string_body_piece():
    return st.one_of(
        _SAFE,
        _control_byte(),
        st.sampled_from(_ESCAPES),
        _unicode_escape(),
        _surrogate_escape(),
        st.just("\x00"),
    )

_string_body = st.lists(_string_body_piece(), max_size=8).map("".join)

def _quoted(s):
    return '"' + s + '"'

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=1, max_value=10**300).map(str),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**18).map(lambda n: "." + str(n)),
    st.just("." + "9" * 30),
)

_exp = st.one_of(
    st.just(""),
    st.builds(
        lambda e, s, d: e + s + d,
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.one_of(
            st.integers(min_value=0, max_value=99).map(str),
            st.integers(min_value=300, max_value=4000).map(str),
        ),
    ),
)

_number = st.builds(
    lambda sign, i, f, e: sign + i + f + e,
    st.sampled_from(["", "-"]),
    _int_part,
    _frac,
    _exp,
)

# near-valid / malformed numbers
_bad_number = st.sampled_from(
    [
        "+1", ".5", "1.", "01", "00", "-01", "0x1F", "-", "--1", "1e", "1e+",
        "1.2.3", "1..2", "+.5", "-.5", "1e309", "-1e309", "1e-9999", "1e99999",
        "0.", ".", "-.", "1e+", "0e", "1E", "1_000", "NaN", "Infinity", "-Infinity",
    ]
)

# ---------- raw / malformed fragments ----------

_raw_frag = st.one_of(
    st.just(","),
    st.just(",,"),
    st.just(":"),
    st.just("::"),
    st.just("{"),
    st.just("}"),
    st.just("["),
    st.just("]"),
    st.just('"'),
    st.just("'"),
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("\r"),
    st.just("\x00"),
    st.just("\\"),
    st.just("\\u"),
    st.just("\\u12"),
    st.just("\\x41"),
    st.just("tru"),
    st.just("fals"),
    st.just("nul"),
    st.just("truee"),
    st.just("nullx"),
    st.just("1abc"),
    st.just("[]xyz"),
)

# ---------- recursive value strategy ----------

def _value_strategy(depth):
    leaves = st.one_of(
        _string_body.map(_quoted),
        _number,
        _bad_number,
        st.sampled_from(["true", "false", "null", "TRUE", "False", "NULL"]),
        _raw_frag,
    )
    if depth <= 0:
        return leaves

    inner = st.deferred(lambda: _value_strategy(depth - 1))

    # pair: STRING ':' value  (bias toward objects with members)
    pair = st.builds(
        lambda k, v: k + ":" + v,
        _string_body.map(_quoted),
        inner,
    )

    obj_members = st.lists(pair, min_size=1, max_size=6)
    obj = st.one_of(
        st.just("{}"),
        obj_members.map(lambda ps: "{" + ",".join(ps) + "}"),
        # trailing comma variant (accepted by parser)
        obj_members.map(lambda ps: "{" + ",".join(ps) + ",}"),
        # duplicate keys
        st.builds(
            lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
            _string_body.map(_quoted),
            inner,
            inner,
        ),
        # malformed object
        st.builds(
            lambda a, b: "{" + a + "," + b + "}",
            _string_body.map(_quoted),
            inner,
        ),
        st.just("{,}"),
        st.just("{,}"),
        st.just("{a:1}"),
    )

    arr_items = st.lists(inner, min_size=0, max_size=6)
    arr = st.one_of(
        arr_items.map(lambda xs: "[" + ",".join(xs) + "]"),
        arr_items.map(lambda xs: "[" + ",".join(xs) + ",]"),
        st.just("[,]"),
        st.just("[,1]"),
        st.just("[1,,2]"),
        st.just("[1 2]"),
    )

    return st.one_of(leaves, obj, arr)

# deep nesting: vary freely, but keep generating tractable
_depth = st.integers(min_value=0, max_value=6)

_value = _depth.flatmap(_value_strategy)

# ---------- top-level document ----------

def _wrap(v):
    # sometimes pad with whitespace, sometimes append trailing garbage
    return v

_doc = st.one_of(
    _value,
    st.builds(lambda v: " " + v + " ", _value),
    st.builds(lambda v: v + "\n", _value),
    # trailing content (rejected by parser, good to test)
    st.builds(lambda v, g: v + g, _value, st.sampled_from(["x", " garbage", "true", "[]"])),
    # deep nesting burst
    st.integers(min_value=1, max_value=200).map(lambda n: "[" * n),
    st.integers(min_value=1, max_value=200).map(lambda n: "[" * n + "]" * n),
    st.integers(min_value=1, max_value=100).map(lambda n: "{" + '"a":' * n),
    st.just(""),
    st.just("   "),
    st.just("\x00"),
    st.just('"\x00"'),
    st.just('"\\u0000"'),
    st.just("1e309"),
    st.just("-"),
    st.just("{\"a\":1,\"a\":2}"),
    st.just("[1,2,]"),
    st.just("{\"a\":1,}"),
)

strategy = _doc
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.