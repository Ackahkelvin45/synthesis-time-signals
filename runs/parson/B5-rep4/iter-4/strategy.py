from hypothesis import strategies as st
import json

# ---------- basic leaf strategies ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.lists(st.sampled_from(_hex), min_size=4, max_size=4).map("".join)

_escapes_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_unicode_escapes = st.one_of(
    _hex4().map(lambda h: "\\u" + h),
    st.sampled_from(["\\u0000", "\\u001f", "\\u007f", "\\u0080", "\\u00ff",
                     "\\u07ff", "\\u0800", "\\uffff", "\\uD800", "\\uDBFF",
                     "\\uDC00", "\\uDFFF", "\\uD83D\\uDE00", "\\uD800\\uD800"]),
)

# safe code points: printable-ish, avoid raw NUL and control chars
_safe_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7e),
    st.characters(min_codepoint=0xa0, max_codepoint=0x2fff),
    st.sampled_from([" ", "\t", "\n", "\r"]),
)

_string_body = st.one_of(
    _safe_chars,
    _escapes_simple,
    _unicode_escapes,
)

def _string():
    return st.lists(_string_body, min_size=0, max_size=12).map(lambda xs: '"' + "".join(xs) + '"')

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=10**18, max_value=10**400).map(str),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**20).map(lambda n: "." + str(n)),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(st.sampled_from(["e", "E"]),
              st.sampled_from(["", "+", "-"]),
              st.integers(min_value=0, max_value=400).map(str)).map("".join),
    st.sampled_from(["e309", "E309", "e-309", "e400", "e-400", "e9999", "e-9999",
                     "e308", "e-308", "e000", "e+000"]),
)

def _number():
    return st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        _frac,
        _exp,
    ).map("".join)

# ---------- malformed number-ish fragments ----------

_malformed_num = st.sampled_from([
    "-", "-.", "+1", "+", ".5", "-.5", "01", "00", "1.", "1.e5", "1e", "1e+",
    "--1", "1..2", "1e1e1", "0x10", "Infinity", "-Infinity", "NaN", "1_000",
])

# ---------- recursive structure ----------

_json_str = _string()
_json_num = _number()

_leaf = st.one_of(
    _json_str,
    _json_num,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

def _obj(items):
    # items: list of (key_str, value_str) already rendered
    def render(pairs):
        if not pairs:
            return "{}"
        inner = ",".join(k + ":" + v for (k, v) in pairs)
        return "{" + inner + "}"
    return items.map(render)

def _arr(items):
    def render(vals):
        if not vals:
            return "[]"
        return "[" + ",".join(vals) + "]"
    return items.map(render)

# depth control: concentrate near 2048
_depth_choices = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=8, max_value=64),
    st.integers(min_value=64, max_value=512),
    st.integers(min_value=1800, max_value=2050),
)

def _deep_array(depth):
    # build nested arrays with a leaf at the center
    leaf = _leaf
    return leaf.map(lambda v: "[" * depth + v + "]" * depth)

def _deep_object(depth):
    leaf = _leaf
    return leaf.map(lambda v: '{"k":' * depth + v + "}" * depth)

_deep = st.one_of(
    _depth_choices.flatmap(_deep_array),
    _depth_choices.flatmap(_deep_object),
)

_base_value = st.one_of(_leaf, _deep)

def _pair():
    return st.tuples(_json_str, _base_value).map(lambda kv: kv[0] + ":" + kv[1])

def _obj_pairs():
    return st.lists(_pair(), min_size=0, max_size=6).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )

def _arr_vals():
    return st.lists(_base_value, min_size=0, max_size=6).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )

_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        children.map(lambda v: "{" + '"k":' + v + "}"),
        children.map(lambda v: "[" + v + "]"),
        st.lists(children, min_size=0, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(st.tuples(_json_str, children), min_size=0, max_size=6).map(
            lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}"
        ),
    ),
    max_leaves=20,
)

# ---------- edge-case / malformed whole documents ----------

_duplicate_keys = st.lists(
    st.tuples(_json_str, _base_value), min_size=2, max_size=5
).map(lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}")

_malformed_doc = st.one_of(
    # double commas
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just('{"a":1,,"b":2}'),
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
    # missing colons
    st.just('{"a" 1}'),
    st.just('{"a"}'),
    st.just('{a:1}'),
    # unterminated strings
    st.just('"abc'),
    st.just('{"a":"b'),
    st.just('["x'),
    # leading +/.5/01
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("-"),
    st.just("-."),
    st.just("1."),
    # stray brackets
    st.just("]"),
    st.just("}"),
    st.just("[}"),
    st.just("{]"),
    # trailing content after a value
    st.just("1abc"),
    st.just("[]xyz"),
    st.just('{"a":1} trailing'),
    st.just("null null"),
    st.just("truefalse"),
    # empty / whitespace
    st.just(""),
    st.just("   "),
    st.just("\t\n\r "),
    # unicode / control escapes inside strings
    st.just('"\\u0000"'),
    st.just('"\\uD800"'),
    st.just('"\\uD800\\uDC00"'),
    st.just('"a\\u0000b"'),
    st.just('"\\u001f\\u007f"'),
    # extreme numbers
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-9999"),
    st.just("1" + "0" * 400),
    st.just("0." + "0" * 400 + "1"),
    # lone sign
    st.just("-"),
    st.just("+"),
    st.just("."),
)

# ---------- structured mutation of well-formed docs ----------

def _mutate(doc, op, pos):
    """Apply one of several byte-level mutations to a well-formed doc."""
    n = len(doc)
    if n == 0:
        return doc
    p = pos % (n + 1)
    if op == 0:
        # truncate at position p
        return doc[:p]
    elif op == 1:
        # delete one char at p (if possible)
        if p < n:
            return doc[:p] + doc[p + 1:]
        return doc
    elif op == 2:
        # duplicate a char at p
        if p < n:
            return doc[:p] + doc[p] + doc[p:]
        return doc
    elif op == 3:
        # insert a random structural punctuation char at p
        punct = "{}[],:\"\\ \t\n0123456789eE.-+tfnul"
        c = punct[(pos * 7 + p) % len(punct)]
        return doc[:p] + c + doc[p:]
    elif op == 4:
        # swap two adjacent chars
        if p < n - 1:
            return doc[:p] + doc[p + 1] + doc[p] + doc[p + 2:]
        return doc
    else:
        # append trailing garbage
        return doc + ["x", "]", "}", ",", " ", "1", "\"", "\x00"][pos % 8]

_structural_mutation = st.tuples(
    _value, st.integers(min_value=0, max_value=5), st.integers(min_value=0, max_value=64)
).map(lambda t: _mutate(t[0], t[1], t[2]))

# ---------- compose ----------

_document = st.one_of(
    _value,
    _malformed_doc,
    _malformed_num,
    _duplicate_keys,
    _obj_pairs(),
    _arr_vals(),
    _structural_mutation,
    st.just("{}"),
    st.just("[]"),
    st.tuples(_ws, _value, _ws).map("".join),
)

strategy = _document