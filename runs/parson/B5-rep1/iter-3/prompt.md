Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

def _wrap(open_ch, inner, close_ch):
    return open_ch + inner + close_ch

# ---------- scalar pieces ----------

# Safe code points: printable ASCII minus quote, backslash, and control chars.
_SAFE = [chr(c) for c in range(0x20, 0x7f) if chr(c) not in '"\\']

def _escapes():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    hexdig = st.sampled_from('0123456789abcdefABCDEF')
    uni = st.tuples(st.just('\\u'), *[hexdig] * 4).map(_join)
    # surrogate escapes and NUL escape
    surrogate = st.sampled_from([
        '\\u0000', '\\uD800', '\\uDBFF', '\\uDC00', '\\uDFFF',
        '\\uD834\\uDD1E', '\\uFFFF', '\\u001F', '\\u007F',
    ])
    return st.one_of(simple, uni, surrogate)

def _string_body():
    safe = st.text(alphabet=_SAFE, min_size=0, max_size=12)
    esc = _escapes()
    return st.lists(st.one_of(safe, esc), min_size=0, max_size=6).map(_join)

def _string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.integers(min_value=-(10**18), max_value=-1).map(str),
    )

def _number():
    intp = _int_part()
    frac = st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n))
    exp = st.builds(
        lambda e, sign, digits: e + sign + digits,
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=10**4).map(str),
    )
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e400", "1e999999", "-1e999999",
        "1e-999999", "0e0", "-0", "1.7976931348623157e308",
        "1e308", "1e-308", "123456789012345678901234567890",
    ])
    core = st.builds(
        lambda i, f, e: i + f + e,
        intp,
        st.one_of(st.just(""), frac),
        st.one_of(st.just(""), exp),
    )
    return st.one_of(core, extreme)

# ---------- malformed fragments ----------

def _malformed_scalar():
    return st.sampled_from([
        "01", "-01", "+1", ".5", "-.5", "1.", "1.e5", ".", "-", "+",
        "1e", "1e+", "1e-", "--1", "0x10", "Infinity", "NaN", "-Infinity",
        "tru", "fals", "nul", "True", "NULL", "truee",
    ])

def _unterminated_string():
    return st.builds(
        lambda body: '"' + body,
        _string_body(),
    )

# ---------- recursive structure ----------

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed_scalar(),
        _unterminated_string(),
    )

def _pair(value_st):
    key = _string()
    sep = st.one_of(st.just(":"), st.just(""), st.just("::"), st.just(" : "))
    return st.tuples(key, sep, value_st).map(lambda t: t[0] + t[1] + t[2])

def _obj(value_st):
    empty = st.just("{}")
    pair = _pair(value_st)
    sep = st.one_of(st.just(","), st.just(",,"), st.just(" , "), st.just(""))
    body = st.tuples(pair, st.lists(st.tuples(sep, pair), max_size=4)).map(
        lambda t: t[0] + "".join(s + p for s, p in t[1])
    )
    nonempty = body.map(lambda b: "{" + b + "}")
    # trailing comma variant
    trailing = body.map(lambda b: "{" + b + ",}")
    return st.one_of(empty, nonempty, trailing)

def _arr(value_st):
    empty = st.just("[]")
    sep = st.one_of(st.just(","), st.just(",,"), st.just(" , "), st.just(""))
    elems = st.lists(value_st, min_size=1, max_size=4)
    body = elems.map(lambda xs: ",".join(xs))
    nonempty = body.map(lambda b: "[" + b + "]")
    trailing = body.map(lambda b: "[" + b + ",]")
    return st.one_of(empty, nonempty, trailing)

def _value_tree():
    return st.recursive(
        _leaf(),
        lambda children: st.one_of(_obj(children), _arr(children)),
        max_leaves=12,
    )

# ---------- deep nesting near the 2048 cap ----------

def _deep_nesting():
    # Concentrate depth near the parser's MAX_NESTING = 2048.
    depth = st.one_of(
        st.integers(min_value=1, max_value=16),
        st.integers(min_value=2040, max_value=2055),
        st.integers(min_value=2000, max_value=2100),
    )
    kind = st.sampled_from(["[", "{"])
    inner = st.one_of(st.just("0"), st.just("null"), st.just('"x"'), st.just("[]"))
    def build(d, k, inn):
        if k == "[":
            return "[" * d + inn + "]" * d
        return '{"k":' * d + inn + "}" * d
    return st.tuples(depth, kind, inner).map(lambda t: build(*t))

# ---------- top-level assembly ----------

def _top_value():
    return st.one_of(_value_tree(), _deep_nesting())

def _with_trailing():
    val = _top_value()
    trail = st.one_of(
        st.just(""),
        st.just(" "),
        st.just("garbage"),
        st.just("xyz"),
        st.just("\n\t"),
        st.just("]"),
        st.just("}"),
    )
    return st.tuples(val, trail).map(lambda t: t[0] + t[1])

def _duplicate_keys():
    return st.builds(
        lambda k, v1, v2: '{"' + k + '":' + v1 + ',"' + k + '":' + v2 + "}",
        st.text(alphabet="abc", min_size=0, max_size=3),
        _leaf(),
        _leaf(),
    )

# ---------- improved: whitespace-fuzzed valid documents ----------

def _ws():
    return st.sampled_from(["", " ", "\t", "\n", "\r\n", "  ", "\n\n"])

def _ws_fuzz(obj):
    # Insert arbitrary JSON whitespace between structural tokens.
    return st.builds(
        lambda a, b, c, d, e, f, g, h, i: a + b + c + d + e + f + g + h + i,
        _ws(), obj, _ws(), st.just(""), _ws(), st.just(""), _ws(), st.just(""), _ws(),
    )

def _ws_document():
    # Wrap a valid value tree with random leading/trailing whitespace and
    # occasionally interleave whitespace inside compact containers.
    val = _value_tree()
    lead = _ws()
    trail = _ws()
    return st.tuples(lead, val, trail).map(lambda t: t[0] + t[1] + t[2])

strategy = st.one_of(
    _value_tree(),
    _with_trailing(),
    _deep_nesting(),
    _duplicate_keys(),
    _leaf(),
    _malformed_scalar(),
    _unterminated_string(),
    _string(),
    _number(),
    _ws_document(),
)
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.