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

# ---------- exercises for uncovered API functions ----------
# The parser's serialize/copy/equals/validate paths are only reached by
# well-formed documents. Generate many valid trees to drive those branches.

def _valid_value_tree():
    def leaf():
        return st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null"]),
        )
    def obj(children):
        key = _string()
        pair = st.tuples(key, st.just(":"), children).map(lambda t: t[0] + t[1] + t[2])
        body = st.lists(pair, max_size=4).map(lambda xs: ",".join(xs))
        return st.one_of(st.just("{}"), body.map(lambda b: "{" + b + "}"))
    def arr(children):
        body = st.lists(children, max_size=4).map(lambda xs: ",".join(xs))
        return st.one_of(st.just("[]"), body.map(lambda b: "[" + b + "]"))
    return st.recursive(leaf(), lambda ch: st.one_of(obj(ch), arr(ch)), max_leaves=10)

def _valid_document():
    return _valid_value_tree()

def _roundtrip_pair():
    # Produce a valid doc, then optionally a second valid doc; both are
    # serialized/copied/compared by the parser API.
    return st.tuples(_valid_document(), _valid_document()).map(
        lambda t: t[0] + "\n" + t[1]
    )

# ---------- API-driving documents ----------
# These wrap valid documents so the top-level value is always a single
# well-formed document that reaches serialize/copy/equals/validate.

def _api_document():
    # A single valid document is what serialize/copy/equals/validate need.
    return _valid_document()

def _api_document_with_string_emphasis():
    # String-heavy valid docs to exercise json_serialize_string escaping.
    def s():
        return st.one_of(
            _string(),
            st.sampled_from(['"\\u0000"', '"\\n\\t\\r"', '"\\"quoted\\""',
                             '"\\\\backslash"', '"\\uD834\\uDD1E"']),
        )
    def leaf():
        return st.one_of(s(), _number(), st.sampled_from(["true", "false", "null"]))
    def obj(children):
        key = s()
        pair = st.tuples(key, st.just(":"), children).map(lambda t: t[0] + t[1] + t[2])
        body = st.lists(pair, max_size=4).map(lambda xs: ",".join(xs))
        return st.one_of(st.just("{}"), body.map(lambda b: "{" + b + "}"))
    def arr(children):
        body = st.lists(children, max_size=4).map(lambda xs: ",".join(xs))
        return st.one_of(st.just("[]"), body.map(lambda b: "[" + b + "]"))
    return st.recursive(leaf(), lambda ch: st.one_of(obj(ch), arr(ch)), max_leaves=10)

def _api_document_large():
    # Larger valid docs to exercise buffer growth in serialize_to_buffer_r.
    def leaf():
        return st.one_of(_string(), _number(), st.sampled_from(["true", "false", "null"]))
    def obj(children):
        key = _string()
        pair = st.tuples(key, st.just(":"), children).map(lambda t: t[0] + t[1] + t[2])
        body = st.lists(pair, min_size=1, max_size=8).map(lambda xs: ",".join(xs))
        return body.map(lambda b: "{" + b + "}")
    def arr(children):
        body = st.lists(children, min_size=1, max_size=8).map(lambda xs: ",".join(xs))
        return body.map(lambda b: "[" + b + "]")
    return st.recursive(leaf(), lambda ch: st.one_of(obj(ch), arr(ch)), max_leaves=40)

def _api_equals_pair():
    # Same document twice (must compare equal) and a mutated variant.
    base = _valid_document()
    return st.tuples(base, base).map(lambda t: t[0] + "\n" + t[1])

# ---------- improved API-driving documents ----------
# The previous run showed 0% coverage on the serialize/copy/equals/validate
# functions. These are only reached by a single top-level well-formed document.
# We make those documents dominant and include a broad mix of scalar/string
# shapes so json_serialize_string, json_serialize_to_buffer_r, json_value_equals,
# json_value_deep_copy and json_validate all get exercised.

def _api_scalar():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _api_string_heavy():
    # Strings that force the serializer's escaping path (control chars, escapes,
    # quotes, backslashes, unicode escapes including surrogates).
    return st.one_of(
        _string(),
        st.sampled_from([
            '""',
            '"\\u0000"',
            '"\\u001F"',
            '"\\u007F"',
            '"\\n\\t\\r\\b\\f"',
            '"\\"quoted\\""',
            '"\\\\backslash"',
            '"\\/"',
            '"\\uD834\\uDD1E"',
            '"\\uD800"',
            '"\\uDFFF"',
            '"plain"',
            '"mixed \\u0041 \\n \\" end"',
        ]),
    )

def _api_object():
    # A single well-formed object whose value is a valid document.
    val = _api_document()
    key = _api_string_heavy()
    return st.tuples(key, val).map(lambda t: "{" + t[0] + ":" + t[1] + "}")

def _api_array():
    # A single well-formed array with one or more valid documents.
    elems = st.lists(_api_document(), min_size=1, max_size=6)
    return elems.map(lambda xs: "[" + ",".join(xs) + "]")

def _api_root_document():
    # Always a single well-formed JSON document (never trailing junk), so the
    # parse succeeds and the serialize/copy/equals/validate paths execute.
    return st.one_of(
        _api_scalar(),
        _api_string_heavy(),
        _api_object(),
        _api_array(),
        _api_document(),
        _api_document_with_string_emphasis(),
        _api_document_large(),
    )

def _api_root_string():
    # A bare JSON string document — maximally exercises json_serialize_string.
    return _api_string_heavy()

def _api_root_container_of_strings():
    # Containers full of strings to exercise both value-copy and serialize-string.
    def s():
        return _api_string_heavy()
    def obj(children):
        key = s()
        pair = st.tuples(key, st.just(":"), children).map(lambda t: t[0] + t[1] + t[2])
        body = st.lists(pair, min_size=1, max_size=6).map(lambda xs: ",".join(xs))
        return body.map(lambda b: "{" + b + "}")
    def arr(children):
        body = st.lists(children, min_size=1, max_size=6).map(lambda xs: ",".join(xs))
        return body.map(lambda b: "[" + b + "]")
    return st.recursive(s(), lambda ch: st.one_of(obj(ch), arr(ch)), max_leaves=20)

strategy = st.one_of(
    # Dominant weight toward well-formed single documents so the API paths
    # (serialize/copy/equals/validate) are reliably reached.
    _api_root_document(),
    _api_root_string(),
    _api_root_container_of_strings(),
    _api_document(),
    _api_document_with_string_emphasis(),
    _api_document_large(),
    _api_equals_pair(),
    _roundtrip_pair(),
    # Keep the malformed / structural fuzzers for parser robustness.
    _value_tree(),
    _with_trailing(),
    _deep_nesting(),
    _duplicate_keys(),
    _leaf(),
    _malformed_scalar(),
    _unterminated_string(),
    _string(),
    _number(),
)
```