```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Characters that are safe inside a JSON string per grammar (no " \ or control)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in str
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# Control characters including NUL, allowed inside strings via escapes
_escapes = st.sampled_from(
    ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
)

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map("".join)

_unicode_esc = st.tuples(st.just("\\u"), _hex4).map("".join)
# Surrogate escapes: high and low surrogates
_surrogate_esc = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD834\\uDD1E",  # valid surrogate pair (musical symbol)
    "\\uD800\\uD800",  # unpaired high surrogate
    "\\uDC00",         # lone low surrogate
])

# A raw control byte embedded literally (NUL etc.) — parser uses explicit length
_raw_control = st.sampled_from(
    ['\x00', '\x01', '\x1f', '\x0b', '\x0c', '\x1e', '\x7f']
)

_string_char = st.one_of(
    _safe_chars,
    _escapes,
    _unicode_esc,
    _surrogate_esc,
    _raw_control,
)

# JSON string literal (quoted). Keep lengths modest to favor validity.
json_string = st.lists(_string_char, min_size=0, max_size=8).map(
    lambda cs: '"' + "".join(cs) + '"'
)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text("123456789", min_size=1, max_size=1).flatmap(
    lambda first: st.tuples(st.just(first), st.text("0123456789", min_size=0, max_size=5)).map("".join)
)

_int_part = st.one_of(
    st.just("0"),
    _nonzero_digits,
    # extreme integer magnitudes
    st.sampled_from([
        "1", "9", "10", "100", "999999999999999999999999",
        "1" + "0" * 30,
        "9" * 40,
    ]),
)

_frac_part = st.tuples(
    st.just("."),
    st.text("0123456789", min_size=1, max_size=6),
).map("".join)

_exp_part = st.one_of(
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text("0123456789", min_size=1, max_size=4),
    ).map("".join),
    st.sampled_from([
        "e309", "e+309", "e-309", "E308", "e999", "e-999",
        "e0001", "E+01",
    ]),
)

_sign = st.sampled_from(["", "-"])

_valid_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.just(""), _frac_part),
    st.one_of(st.just(""), _exp_part),
).map("".join)

# Lenient/edge numbers the parser accepts or rejects interestingly
_edge_number = st.sampled_from([
    "-",            # lone minus accepted
    "1e309",        # overflow -> inf accepted
    "-1e309",
    "1e-400",       # underflow
    "0", "-0", "0.0", "-0.0",
    "1E10", "1e+10", "1e-10",
    "123456789012345678901234567890",
    "1.7976931348623157e308",
    "5e-324",
])

# Malformed numbers (should be rejected, good fuzzing)
_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-.5", "+.5",
    "1..2", "1e", "1e+", "1ee1", "--1", "1.2.3",
])

number = st.one_of(_valid_number, _edge_number)

# ---------- recursive values ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  "])

def _join(parts):
    return "".join(parts)

# We'll build values with a recursive strategy. To bias toward objects-with-members,
# weight the object branch heavily.

def _obj_strategy(value_st):
    # members: STRING ':' value
    pair = st.tuples(
        json_string,
        st.just(":"),
        _ws,
        value_st,
    ).map(_join)

    members = st.lists(pair, min_size=1, max_size=5)

    def build(members):
        inner = ("," + _ws.join([""])).join(members)  # join with ","
        # Simpler: join with ","
        inner = ",".join(members)
        return "{" + inner + "}"

    obj_with_members = members.map(build)
    empty_obj = st.just("{}")
    # single trailing comma variant
    trailing = members.map(lambda ms: "{" + ",".join(ms) + ",}")

    return st.one_of(obj_with_members, obj_with_members, obj_with_members,
                     empty_obj, trailing)


def _arr_strategy(value_st):
    elems = st.lists(value_st, min_size=1, max_size=5)
    arr = elems.map(lambda es: "[" + ",".join(es) + "]")
    empty = st.just("[]")
    trailing = elems.map(lambda es: "[" + ",".join(es) + ",]")
    return st.one_of(arr, arr, empty, trailing)


def _value_strategy(value_st):
    return st.one_of(
        json_string,
        number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _obj_strategy(value_st),
        _arr_strategy(value_st),
    )


json_value = st.recursive(
    st.one_of(
        json_string,
        number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        st.just("{}"),
        st.just("[]"),
    ),
    lambda children: st.one_of(
        _obj_strategy(children),
        _arr_strategy(children),
    ),
    max_leaves=20,
)

# ---------- deep nesting ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=60)
    # deep arrays
    deep_arr = depth.map(lambda d: "[" * d + "]" * d)
    # deep objects with members: {"a":{"a":{...}}}
    deep_obj = depth.map(lambda d: '{"a":' * d + "null" + "}" * d)
    # deep objects with empty innermost
    deep_obj_empty = depth.map(lambda d: '{"a":' * d + "{}" + "}" * d)
    return st.one_of(deep_arr, deep_obj, deep_obj_empty)


# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        st.sampled_from([
            "{,}", "[,]", "[1,,2]", "{,1}", "[1,2,,]",
            "{a:1}", "{'a':1}", '{"a" 1}', '{"a":}',
            '{"a"}', '{"a":1 "b":2}',
            '{"a":1,,"b":2}',
            '[1 2]', '[1;2]', '[1:2]',
            '"unterminated', "'single'", '"a\\"',
            '"\\u12"', '"\\uZZZZ"', '"\\x41"',
            'tru', 'fals', 'nul', 'True', 'NULL',
            '1abc', '[]xyz', 'true false', '1 garbage',
            '+1', '.5', '1.', '01', '0x1F',
            '//comment\n1', '/*c*/1',
            '', ' ', '\n', '\x00', '\x00\x01',
            '{"a":1,}', '[1,2,]',
        ]),
        # trailing comma with whitespace
        st.tuples(
            st.just('{"a":1'),
            _ws,
            st.just(',}'),
        ).map(_join),
        st.tuples(
            st.just('[1'),
            _ws,
            st.just(',]'),
        ).map(_join),
        # missing colon variants
        st.tuples(json_string, _ws, json_value).map(_join),
        # unterminated string with random content
        st.lists(_string_char, min_size=0, max_size=6).map(
            lambda cs: '"' + "".join(cs)
        ),
    )


# ---------- top-level document ----------

def _document():
    # Valid-ish documents (the bulk)
    valid = st.tuples(
        _ws,
        json_value,
        _ws,
    ).map(_join)

    # Objects with duplicate keys
    dup_keys = st.tuples(
        st.just("{"),
        json_string,
        st.just(":1,"),
        json_string,
        st.just(":2}"),
    ).map(_join)

    # Duplicate keys via same string
    dup_same = json_string.flatmap(
        lambda k: st.just("{" + k + ":1," + k + ":2}")
    )

    return st.one_of(
        valid, valid, valid, valid,  # weight toward valid
        _deep_nesting(),
        dup_keys,
        dup_same,
        _malformed(),
    )


strategy = _document()
```