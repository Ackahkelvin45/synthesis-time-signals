```python
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

# ---------- compose ----------

# Exercise serialize / deep-copy / equals / validate paths by generating
# structured documents that round-trip through these routines, plus
# whitespace-insensitive variants of deeply nested values.
_roundtrip_value = st.one_of(
    _value,
    _obj_pairs(),
    _arr_vals(),
    _duplicate_keys,
)

def _is_valid(v):
    try:
        json.loads(v)
        return True
    except Exception:
        return False

_serialize_doc = _roundtrip_value.map(lambda v: json.dumps(json.loads(v)) if _is_valid(v) else v)

# whitespace-laden variants to stress json_serialize / validate whitespace handling
_ws_wrapped = st.tuples(
    _ws, _roundtrip_value, _ws
).map("".join)

# nested arrays/objects with whitespace around structural tokens
_ws_structural = _roundtrip_value.map(
    lambda v: v.replace(",", " , ").replace(":", " : ")
)

# ---------- targeted valid documents for serialize / deep_copy / equals / validate ----------

# Plain valid scalar documents.
_valid_scalar = st.one_of(
    _json_str,
    _json_num,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

# Valid documents guaranteed to parse (so serialize/deep_copy/equals/validate
# paths in the parser are actually exercised, not just parse failures).
_valid_doc = st.recursive(
    _valid_scalar,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=5).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(st.tuples(_json_str, children), min_size=0, max_size=5).map(
            lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}"
        ),
    ),
    max_leaves=15,
)

# Valid documents with whitespace sprinkled between tokens; these still parse
# and so drive json_validate / json_serialize whitespace handling.
def _sprinkle_ws(v):
    return (
        v.replace("{", "{ ").replace("}", " }")
         .replace("[", "[ ").replace("]", " ]")
         .replace(",", " , ").replace(":", " : ")
    )

_valid_ws_doc = _valid_doc.map(_sprinkle_ws)

# Valid documents with escaped strings and unicode to exercise
# json_serialize_string (string escaping / copying).
_escapable_string = st.one_of(
    _string(),
    st.lists(
        st.one_of(
            st.sampled_from(list('"\\/\b\f\n\r\t')),
            st.characters(min_codepoint=0x20, max_codepoint=0x7e),
            st.characters(min_codepoint=0xa0, max_codepoint=0x2fff),
            _unicode_escapes,
        ),
        min_size=0, max_size=10,
    ).map(lambda xs: '"' + "".join(xs) + '"'),
)

_string_heavy_doc = st.one_of(
    _escapable_string,
    st.tuples(_escapable_string, _escapable_string).map(lambda kv: "[" + kv[0] + "," + kv[1] + "]"),
    st.lists(st.tuples(_escapable_string, _escapable_string), min_size=0, max_size=4).map(
        lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}"
    ),
)

# Valid deep documents to exercise deep_copy / equals recursion.
_valid_deep = st.one_of(
    _depth_choices.flatmap(lambda d: _valid_scalar.map(lambda v: "[" * d + v + "]" * d)),
    _depth_choices.flatmap(lambda d: _valid_scalar.map(lambda v: '{"k":' * d + v + "}" * d)),
)

# Valid documents with duplicate keys to drive equals / deep_copy semantics.
_valid_dup_keys = st.lists(
    st.tuples(_json_str, _valid_scalar), min_size=2, max_size=5
).map(lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}")

# ---------- targeted documents to reach serialize/deep_copy/equals/validate ----------

# Documents that are guaranteed valid JSON and exercise string escaping,
# whitespace, deep nesting, duplicate keys, and round-trip serialization.
# These are the paths that showed 0% branch coverage, so bias heavily toward them.
_valid_targeted = st.one_of(
    _valid_doc,
    _valid_ws_doc,
    _string_heavy_doc,
    _valid_deep,
    _valid_dup_keys,
    _serialize_doc,
    # Valid documents with strings containing escapes at various depths.
    st.recursive(
        _escapable_string,
        lambda children: st.one_of(
            st.lists(children, min_size=1, max_size=4).map(
                lambda vs: "[" + ",".join(vs) + "]"
            ),
            st.lists(st.tuples(_escapable_string, children), min_size=1, max_size=4).map(
                lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}"
            ),
        ),
        max_leaves=10,
    ),
    # Valid documents with unicode escapes in strings.
    st.lists(_unicode_escapes, min_size=1, max_size=6).map(
        lambda xs: '"' + "".join(xs) + '"'
    ),
    st.tuples(_json_str, _json_str).map(lambda kv: "[" + kv[0] + "," + kv[1] + "]"),
    st.lists(st.tuples(_json_str, _valid_scalar), min_size=0, max_size=4).map(
        lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}"
    ),
)

# ---------- valid-only documents to drive serialize/deep_copy/equals/validate ----------

# These serialize/deep_copy/equals/validate paths showed 0% coverage, which
# means the parser is only being reached on inputs that fail to parse. Build
# documents that are guaranteed to be valid JSON (verified via json.loads) so
# the post-parse routines actually run. We also exercise whitespace variants
# and string-escaping variants, since serialize_string was uncovered too.
def _valid_or_fallback(v):
    return v if _is_valid(v) else "null"

_valid_serialize = _valid_targeted.map(_valid_or_fallback)

# Round-trip through json.dumps to guarantee canonical valid JSON with
# normalized strings/escapes; drives serialize_string and validate.
_canonical = _valid_targeted.flatmap(
    lambda v: st.just(json.dumps(json.loads(v))) if _is_valid(v) else st.just("null")
)

# Valid documents wrapped in surrounding whitespace, guaranteed to parse.
_valid_ws_around = st.tuples(_ws, _valid_serialize, _ws).map("".join)

_document = st.one_of(
    _valid_serialize,
    _canonical,
    _valid_ws_around,
    _malformed_doc,
    _malformed_num,
    st.just("{}"),
    st.just("[]"),
    _value,
    _duplicate_keys,
    _obj_pairs(),
    _arr_vals(),
    _ws_wrapped,
    _ws_structural,
    _valid_targeted,
)

strategy = _document
```