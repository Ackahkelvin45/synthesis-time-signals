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
        "tru", "fals", "nul", "True", "NULL", "truee", "falsee", "nulll",
        "TRUE", "FALSE", "NULL ", " true", "true ", "true\t", "false\n",
        "nulL", "tRue", "1e++5", "1e--5", "0e", "0.e1", "1.2.3",
        "-0.0", "+0", "0x", "0b1", "0o7", "1_000", "1,000",
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

# ---------- targeted divergence probes ----------

def _trailing_comma_probes():
    # Exercise trailing-comma handling at every container position,
    # including empty containers and nested combinations.
    return st.sampled_from([
        '{"": "",}',
        '{"": "", }',
        '{"a":1,}',
        '{"a":1, }',
        '{"a":1,"b":2,}',
        '{"a":{},}',
        '{"a":[],}',
        '{"a":{"b":1,},}',
        '{"a":[1,],}',
        '[1,]',
        '[1, ]',
        '[1,2,]',
        '[,]',
        '[, ]',
        '[[],]',
        '[[1,],]',
        '[{},]',
        '[{"a":1,},]',
        '["",]',
        '[null,]',
        '[true,]',
        '[1,,]',
        '{"a":1,,}',
        '{"a":1,,"b":2}',
    ])

# ---------- targeted probes for observed divergences ----------

def _number_tail_probes():
    # Numbers with trailing junk / near-miss tails that parsers often mishandle.
    return st.sampled_from([
        '1.', '1.e5', '1.e', '1.0.', '-1.', '.5', '-.5', '+1', '01',
        '0.', '0.e1', '1.2.3', '1e', '1e+', '1e-', '1e++5', '1e--5',
        '1.0e', '1.0e+', '1.0e-', '0x1', '0b1', '0o1', '1_0',
        '1.0e+5x', '1x', '1 ', '1\t', '1\n', '1]', '1}',
        '-', '--1', '+', '++1', '1.2e3.4',
        '1e999999', '1e-999999', '-0', '-0.0',
    ])

def _literal_tail_probes():
    # Keywords with trailing junk or case/whitespace mutations.
    return st.sampled_from([
        'truee', 'falsee', 'nulll', 'tru', 'fals', 'nul',
        'truex', 'falsex', 'nullx', 'true1', 'false1', 'null1',
        'true]', 'false}', 'null,', 'true false', 'null null',
        'True', 'False', 'Null', 'TRUE', 'FALSE', 'NULL',
        'true ', 'false ', 'null ', ' true', ' false', ' null',
        'true\t', 'false\n', 'null\r',
        'tRue', 'fAlse', 'nUll',
    ])

def _string_tail_probes():
    # Strings with trailing junk, bad escapes, or unterminated forms.
    return st.sampled_from([
        '"abc', '"abc\\', '"\\', '"\\u', '"\\u12', '"\\u123',
        '"\\uZZZZ"', '"\\x41"', '"\\q"', '"a\nb"', '"a\tb"',
        '"a"b', '"a" "b"', '"a""b"', '"', '""', '""""',
        '"\\uD800"', '"\\uDC00"', '"\\uD800\\uDC00"',
        '"\\uD834\\uDD1E"', '"\\u0000"', '"\\uFFFF"',
    ])

def _structure_tail_probes():
    # Structural near-misses that exercise error paths.
    return st.sampled_from([
        '{', '[', '}', ']', '{]', '[}', '{{}}', '[[]]',
        '{"a"}', '{"a":}', '{:1}', '{"a" 1}', '{"a":1 "b":2}',
        '{"a":1}{"b":2}', '[1][2]', '[1] [2]',
        '{"a":1}x', '[1]x', '{}x', '[]x',
        '{"a":1,,"b":2}', '[1,,2]', '[,1]', '[1,]', '{"a":1,}',
        '{"a":[1,2,]}', '[{"a":1,}]',
    ])

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
    _trailing_comma_probes(),
    _number_tail_probes(),
    _literal_tail_probes(),
    _string_tail_probes(),
    _structure_tail_probes(),
)