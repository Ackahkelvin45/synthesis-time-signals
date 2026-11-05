from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
    min_codepoint=0x20,
    max_codepoint=0x10FFFF,
)

_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_unicode_escapes = st.one_of(
    _hex4.map(lambda h: "\\u" + h),
    st.tuples(
        st.sampled_from("dD"), st.sampled_from("89abAB"), _hex, _hex
    ).map(lambda t: "\\u" + "".join(t)),
    st.tuples(
        st.sampled_from("dD"), st.sampled_from("cdefCDEF"), _hex, _hex
    ).map(lambda t: "\\u" + "".join(t)),
    st.just("\\u0000"),
    st.just("\\u001f"),
    st.just("\\u007f"),
    st.just("\\uffff"),
    st.just("\\ufffe"),
)

_string_piece = st.one_of(
    _safe_chars.map(str),
    _simple_escapes,
    _unicode_escapes,
)

def _mk_string(pieces):
    return '"' + "".join(pieces) + '"'

_json_string = st.lists(_string_piece, max_size=8).map(_mk_string)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.text("123456789", min_size=1, max_size=1).flatmap(
        lambda first: st.text("0123456789", min_size=0, max_size=6).map(
            lambda rest: first + rest
        )
    ),
)

_frac_part = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text("0123456789", min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.sampled_from(["308", "309", "310", "999", "1000", "400"]),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

def _mk_number(sign, ip, fp, ep):
    return sign + ip + fp + ep

_number = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part,
    _frac_part,
    _exp_part,
).map(lambda t: _mk_number(*t))

_extreme_numbers = st.sampled_from([
    "1e309", "-1e309", "1e400", "-1e400", "1e308", "1.7976931348623157e308",
    "1.7976931348623159e308", "5e-324", "1e-400", "0e999", "-0", "0.0",
    "123456789012345678901234567890", "1e1000000", "9" * 30,
])

_literal = st.sampled_from(["true", "false", "null"])

# ---------- recursive structure ----------

_malformed_tail = st.sampled_from([
    ",", ",,", ",]", ",}", ":", "::", '"', '""', "]", "}", " ",
    "1abc", "[]xyz", "{}garbage", "1 garbage", "-", "-.", ".5", "+1", "01",
    "tru", "nul", "fals", "\t", "\n", "\r",
])

_ws = st.sampled_from(["", " ", "\n", "\t", "\r", "  ", "\n\t"])

def _mk_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _mk_arr(items):
    return "[" + ",".join(items) + "]"

def _mk_pair(k, v):
    return k + ":" + v

value_strategy = st.deferred(lambda: _value)

def _make_value():
    leaf = st.one_of(
        _json_string,
        _number,
        _extreme_numbers,
        _literal,
    )

    pair = st.tuples(_json_string, value_strategy).map(lambda t: _mk_pair(*t))
    obj = st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=4).map(_mk_obj),
        st.tuples(_json_string, value_strategy, value_strategy).map(
            lambda t: _mk_pair(t[0], t[1]) + "," + _mk_pair(t[0], t[2])
        ).map(lambda s: "{" + s + "}"),
    )

    arr = st.one_of(
        st.just("[]"),
        st.lists(value_strategy, min_size=1, max_size=4).map(_mk_arr),
    )

    return st.one_of(leaf, obj, arr)

_value = _make_value()

# ---------- top-level assembly ----------

def _deep_nest(n, inner):
    return "[" * n + inner + "]" * n

_deep_depth = st.one_of(
    st.integers(min_value=2000, max_value=2048),
    st.integers(min_value=2045, max_value=2050),
    st.integers(min_value=1, max_value=20),
)

_deep = st.tuples(_deep_depth, value_strategy).map(
    lambda t: _deep_nest(t[0], t[1])
)

_deep_obj = st.tuples(
    st.integers(min_value=1900, max_value=2048),
    _json_string,
    value_strategy,
).map(lambda t: '{"k":' * t[0] + t[2] + "}" * t[0])

def _corrupt(v, tail):
    return v + tail

_malformed = st.tuples(value_strategy, _malformed_tail).map(
    lambda t: _corrupt(*t)
)

_unterminated = st.lists(_string_piece, max_size=6).map(
    lambda ps: '"' + "".join(ps)
)

_missing_colon = st.tuples(_json_string, value_strategy).map(
    lambda t: "{" + t[0] + t[1] + "}"
)
_double_comma = st.tuples(value_strategy, value_strategy).map(
    lambda t: "[" + t[0] + ",," + t[1] + "]"
)
_leading_plus = st.tuples(_int_part, _frac_part, _exp_part).map(
    lambda t: "+" + t[0] + t[1] + t[2]
)
_leading_dot = st.tuples(_digits, _exp_part).map(
    lambda t: "." + t[0] + t[1]
)
_leading_zero = st.tuples(st.text("0123456789", min_size=1, max_size=4)).map(
    lambda t: "0" + t[0]
)

_ws_wrapped = st.tuples(_ws, value_strategy, _ws).map(
    lambda t: t[0] + t[1] + t[2]
)

_trailing = st.tuples(value_strategy, _malformed_tail).map(
    lambda t: t[0] + t[1]
)

# ---------- serialization / round-trip oriented inputs ----------
# Exercise json_serialize_string by producing *valid* JSON whose decoded
# string content hits every switch branch (all control chars, quotes,
# backslashes, forward slash, high unicode).

# Cover every escaped control char explicitly plus the '/' branch and
# assorted printable/high unicode.
_ser_char = st.one_of(
    st.sampled_from(list('"\\/\b\f\n\r\t')),
    st.integers(min_value=0, max_value=0x1f).map(chr),
    st.sampled_from(["\x7f", "\x80", "\xff", "\u00e9", "\u2028", "\u2029"]),
    st.characters(min_codepoint=0x20, max_codepoint=0x7e,
                  blacklist_characters='"\\'),
    st.characters(min_codepoint=0xa0, max_codepoint=0x2fff,
                  blacklist_categories=("Cs",)),
)

_JSON_ESC = {
    '"': '\\"', '\\': '\\\\', '\b': '\\b', '\f': '\\f',
    '\n': '\\n', '\r': '\\r', '\t': '\\t',
}

def _encode_json_string(decoded):
    out = ['"']
    for c in decoded:
        if c in _JSON_ESC:
            out.append(_JSON_ESC[c])
        elif ord(c) < 0x20:
            out.append("\\u%04x" % ord(c))
        else:
            out.append(c)
    out.append('"')
    return "".join(out)

# A decoded string that is GUARANTEED to contain every serializer branch,
# then optionally padded with random extra chars.
def _forced_ser_content(extra):
    base = '"\\/\b\f\n\r\t' + "".join(chr(i) for i in range(0x20))
    return base + extra

_forced_ser_string = st.lists(_ser_char, max_size=6).map(
    lambda cs: _encode_json_string(_forced_ser_content("".join(cs)))
)

_ser_string_literal = st.one_of(
    _forced_ser_string,
    st.lists(_ser_char, max_size=10).map(
        lambda cs: _encode_json_string("".join(cs))
    ),
)

def _make_valid_value():
    leaf = st.one_of(
        _ser_string_literal,
        _number,
        _literal,
    )
    pair = st.tuples(_ser_string_literal, value_strategy).map(
        lambda t: _mk_pair(*t)
    )
    obj = st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=3).map(_mk_obj),
    )
    arr = st.one_of(
        st.just("[]"),
        st.lists(value_strategy, min_size=1, max_size=3).map(_mk_arr),
    )
    return st.one_of(leaf, obj, arr)

_valid_value = st.deferred(lambda: _make_valid_value())

_roundtrip = st.tuples(_ws, _valid_value, _ws).map(
    lambda t: t[0] + t[1] + t[2]
)

_ser_nested = st.tuples(
    st.integers(min_value=0, max_value=5),
    _ser_string_literal,
    st.integers(min_value=0, max_value=5),
).map(lambda t: "[" * t[0] + t[1] + "]" * t[2])

# A whole document that is valid and rich in serializer-stressing strings,
# so serialize / deep_copy / equals / validate get exercised on real data.
_ser_document = st.lists(
    st.tuples(_ser_string_literal, _valid_value), min_size=1, max_size=4
).map(lambda pairs: _mk_obj([_mk_pair(k, v) for k, v in pairs]))

# ---------- dedicated serializer / deep-copy / equals / validate drivers ----------
# These build *guaranteed-valid* JSON documents whose parsed tree is rich, so
# json_parse -> json_serialize_to_buffer_r / json_serialize_string /
# json_value_deep_copy / json_value_equals / json_validate all get exercised.

# A decoded string covering every single switch case in json_serialize_string,
# including all control chars 0x00..0x1f, '"', '\\', '/', and high unicode.
def _full_ser_content():
    return (
        '"\\/'
        + "".join(chr(i) for i in range(0x20))
        + "\x7f\x80\xff\u00e9\u2028\u2029"
        + "abcXYZ0123"
    )

_full_ser_literal = st.just(_encode_json_string(_full_ser_content()))

# Random valid strings that may include escapes and high unicode.
_random_ser_literal = st.lists(_ser_char, min_size=0, max_size=12).map(
    lambda cs: _encode_json_string("".join(cs))
)

_any_ser_literal = st.one_of(_full_ser_literal, _random_ser_literal)

# A leaf value that is guaranteed valid JSON.
_valid_leaf = st.one_of(
    _any_ser_literal,
    _number,
    _literal,
)

_valid_value2 = st.deferred(lambda: _make_valid_value2())

def _make_valid_value2():
    pair = st.tuples(_any_ser_literal, _valid_value2).map(
        lambda t: _mk_pair(*t)
    )
    obj = st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=4).map(_mk_obj),
    )
    arr = st.one_of(
        st.just("[]"),
        st.lists(_valid_value2, min_size=1, max_size=4).map(_mk_arr),
    )
    return st.one_of(_valid_leaf, obj, arr)

# A guaranteed-valid document containing the full serializer-stress string,
# so parse -> serialize -> deep_copy -> equals -> validate all run.
_ser_full_document = st.tuples(
    _any_ser_literal,
    _valid_value2,
).map(lambda t: _mk_obj([_mk_pair(t[0], t[1])]))

# A guaranteed-valid array of strings hitting every serializer branch,
# exercised both as a top-level value and nested.
_ser_full_array = st.tuples(
    _full_ser_literal,
    st.lists(_any_ser_literal, min_size=0, max_size=4),
).map(lambda t: _mk_arr([t[0]] + t[1]))

# Whitespace-padded valid document to exercise json_validate / parse ws paths.
_ser_ws_doc = st.tuples(_ws, _ser_full_document, _ws).map(
    lambda t: t[0] + t[1] + t[2]
)

# ---------- NEW: guaranteed-valid top-level drivers ----------
# The previous version's "valid" documents were mostly reached only through
# malformed wrappers or nested deep structures, so the parse-then-operate
# entry points (json_validate, json_value_deep_copy, json_value_equals,
# json_serialize_to_buffer_r) still showed 0% branch coverage. These drivers
# produce small, definitely-valid documents whose parsed tree hits each of
# those functions directly.

# A short valid document guaranteed to contain the full serializer string,
# so json_parse succeeds and downstream tree operations run.
_valid_full_short = st.tuples(
    _full_ser_literal,
    st.one_of(_full_ser_literal, _number, _literal),
).map(lambda t: _mk_obj([_mk_pair(t[0], t[1])]))

# A valid array whose elements are all full serializer-stress strings,
# exercising serialize on a homogeneous list and deep_copy/equals on it.
_valid_full_array_short = st.lists(
    _full_ser_literal, min_size=1, max_size=3
).map(_mk_arr)

# A valid document with nested objects/arrays so deep_copy and equals
# recurse through every node type (object, array, string, number, literal).
_valid_nested_short = st.tuples(
    _full_ser_literal,
    st.one_of(
        _number,
        _literal,
        _full_ser_literal,
        st.lists(_full_ser_literal, min_size=0, max_size=2).map(_mk_arr),
        st.tuples(_full_ser_literal, _number).map(
            lambda t: _mk_obj([_mk_pair(t[0], t[1])])
        ),
    ),
).map(lambda t: _mk_obj([_mk_pair(t[0], t[1])]))

_top = st.one_of(
    value_strategy,
    _deep,
    _deep_obj,
    _malformed,
    _unterminated,
    _missing_colon,
    _double_comma,
    _leading_plus,
    _leading_dot,
    _leading_zero,
    _ws_wrapped,
    _trailing,
    _roundtrip,
    _ser_nested,
    _ser_document,
    _ser_full_document,
    _ser_full_array,
    _ser_ws_doc,
    _valid_full_short,
    _valid_full_array_short,
    _valid_nested_short,
    st.just("{}"),
    st.just("[]"),
    st.just("-"),
    st.just(""),
)

def _no_nul(s):
    return "\x00" not in s

strategy = _top.filter(_no_nul)