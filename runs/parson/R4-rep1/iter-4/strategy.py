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

# ---------- improve_strategy additions ----------

# Strings that exercise json_serialize_string's switch: every control char,
# quote, backslash, slash, and a mix. Parsed then re-serialized by the harness.
_SERIALIZE_CHARS = [chr(c) for c in range(0x00, 0x20)] + ['"', '\\', '/', 'a', ' ']

def _serialize_string():
    # Build a JSON string literal whose *decoded* value contains every
    # interesting char. Use \uXXXX escapes for control chars and quote/backslash.
    def enc(c):
        if c == '"':
            return '\\"'
        if c == '\\':
            return '\\\\'
        if c == '/':
            return '/'
        if 0x00 <= ord(c) < 0x20:
            return '\\u%04x' % ord(c)
        return c
    def build(chars):
        return '"' + "".join(enc(c) for c in chars) + '"'
    all_chars = st.just(_SERIALIZE_CHARS)
    subset = st.lists(st.sampled_from(_SERIALIZE_CHARS), min_size=1, max_size=8)
    return st.one_of(all_chars, subset).map(build)

def _serialize_value():
    # Wrap serialize-test strings in containers so both top-level and nested
    # serialization paths (json_serialize_to_buffer_r) are exercised.
    s = _serialize_string()
    return st.one_of(
        s,
        st.builds(lambda a, b: "[" + a + "," + b + "]", s, s),
        st.builds(lambda k, v: '{"' + k + '":' + v + '}', s, s),
        st.builds(lambda a, b, c: '{"k":[' + a + ',"x":' + b + "," + c + "]}", s, s, s),
    )

def _copy_equals_pairs():
    # Two structurally-equal values (for json_value_equals / deep_copy).
    v = _value_tree()
    return st.tuples(v, v).map(lambda t: t[0] + " " + t[1])

def _valid_documents():
    # Pure valid JSON documents to drive json_validate / serialize / copy.
    return _value_tree()

# ---------- NEW: targeted coverage of serialize / copy / equals / validate ----------

# A single valid JSON string literal whose decoded value spans the full
# control-char + special-char range, so json_serialize_string hits every
# switch case (including the '/' branch under both escape settings).
def _full_switch_string():
    chars = list(_SERIALIZE_CHARS)
    def enc(c):
        if c == '"':
            return '\\"'
        if c == '\\':
            return '\\\\'
        if c == '/':
            return '/'
        if 0x00 <= ord(c) < 0x20:
            return '\\u%04x' % ord(c)
        return c
    return st.just('"' + "".join(enc(c) for c in chars) + '"')

def _valid_string_values():
    # Valid JSON string values (quoted) with varied decoded content.
    return st.one_of(
        _full_switch_string(),
        _serialize_string(),
        _string(),
        st.just('""'),
        st.just('"\\u0000"'),
        st.just('"\\/"'),
        st.just('"/"'),
        st.just('"\\\\"'),
        st.just('"\\""'),
    )

def _valid_scalar():
    return st.one_of(
        _valid_string_values(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _valid_value():
    # Fully valid JSON value tree (no malformed leaves) for validate/copy/equals.
    def _vobj(children):
        key = _valid_string_values()
        pair = st.tuples(key, children).map(lambda t: t[0] + ":" + t[1])
        empty = st.just("{}")
        nonempty = st.lists(pair, min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}")
        return st.one_of(empty, nonempty)
    def _varr(children):
        empty = st.just("[]")
        nonempty = st.lists(children, min_size=1, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]")
        return st.one_of(empty, nonempty)
    return st.recursive(
        _valid_scalar(),
        lambda children: st.one_of(_vobj(children), _varr(children)),
        max_leaves=10,
    )

def _valid_documents_v2():
    # Documents that must validate successfully -> drives json_validate,
    # json_serialize_to_buffer_r, json_value_deep_copy, json_value_equals.
    return _valid_value()

def _deep_valid_docs():
    # Deeply nested but valid documents to stress recursive serialize/copy.
    depth = st.one_of(
        st.integers(min_value=1, max_value=16),
        st.integers(min_value=100, max_value=600),
        st.integers(min_value=2000, max_value=2047),
    )
    kind = st.sampled_from(["[", "{"])
    inner = st.one_of(
        st.just("0"),
        st.just("null"),
        st.just('"x"'),
        st.just("[]"),
        st.just("{}"),
        _full_switch_string(),
    )
    def build(d, k, inn):
        if k == "[":
            return "[" * d + inn + "]" * d
        return '{"k":' * d + inn + "}" * d
    return st.tuples(depth, kind, inner).map(lambda t: build(*t))

def _copy_equals_valid_pairs():
    # Two *valid* structurally-equal values: exercises json_value_equals
    # (equal path) and json_value_deep_copy on real trees.
    v = _valid_value()
    return st.tuples(v, v).map(lambda t: t[0] + "\n" + t[1])

def _equals_unequal_pairs():
    # Two valid but generally distinct values: exercises the unequal path.
    return st.tuples(_valid_value(), _valid_value()).map(lambda t: t[0] + "\n" + t[1])

def _serialize_containers():
    # Valid containers whose string members span the full switch, to reach
    # json_serialize_to_buffer_r for arrays/objects and nested strings.
    s = _valid_string_values()
    n = _number()
    sc = _valid_scalar()
    return st.one_of(
        st.builds(lambda a, b: "[" + a + "," + b + "]", s, s),
        st.builds(lambda a, b, c: "[" + a + "," + b + "," + c + "]", s, n, sc),
        st.builds(lambda k, v: '{"' + k + '":' + v + '}', s, s),
        st.builds(lambda k, v: '{"' + k + '":' + v + '}', s, n),
        st.builds(lambda a, b, c: '{"k":[' + a + ',"x":' + b + "," + c + "]}", s, s, sc),
        st.builds(lambda a, b: '{"a":' + a + ',"b":' + b + '}', s, s),
    )

# ---------- NEW (improve_strategy): single-char string literal per switch case ----------
# Each case of json_serialize_string's switch is reached only when the decoded
# string contains that exact byte. Emit one literal per special char so every
# branch (including '/' under both escape settings and each control char) is
# guaranteed to be exercised when json_serialize_string runs.
_SWITCH_CHARS = ['"', '\\', '\b', '\f', '\n', '\r', '\t', '/'] + \
                [chr(c) for c in range(0x00, 0x20) if chr(c) not in '\b\f\n\r\t']

def _switch_single_char_strings():
    def enc(c):
        if c == '"':
            return '\\"'
        if c == '\\':
            return '\\\\'
        if c == '/':
            return '/'
        if 0x00 <= ord(c) < 0x20:
            return '\\u%04x' % ord(c)
        return c
    return st.sampled_from(['"' + enc(c) + '"' for c in _SWITCH_CHARS])

def _switch_char_documents():
    # Wrap each single-char string in the container shapes that drive
    # json_serialize_to_buffer_r (top-level, array, object, nested).
    s = _switch_single_char_strings()
    return st.one_of(
        s,
        st.builds(lambda a, b: "[" + a + "," + b + "]", s, s),
        st.builds(lambda k, v: '{"' + k + '":' + v + '}', s, s),
        st.builds(lambda a, b, c: "[" + a + ",[" + b + "]," + c + "]", s, s, s),
        st.builds(lambda a, b: '{"a":' + a + ',"b":[' + b + "]}", s, s),
    )

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
    _serialize_value(),
    _copy_equals_pairs(),
    _valid_documents(),
    # targeted additions
    _valid_documents_v2(),
    _full_switch_string(),
    _deep_valid_docs(),
    _copy_equals_valid_pairs(),
    _equals_unequal_pairs(),
    _serialize_containers(),
    # improve_strategy: guaranteed per-case switch coverage
    _switch_single_char_strings(),
    _switch_char_documents(),
)