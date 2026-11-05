```python
from hypothesis import strategies as st
import json

# ---------- building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = _hex4().map(lambda h: "\\u" + h)

# surrogate pairs and lone surrogates: parser rejects lone, accepts pairs
_surrogate_esc = st.sampled_from(
    [
        "\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDFFF",
        "\\ud83d\\ude00", "\\uD83D\\uDE00", "\\ud800\\udc00", "\\udbff\\udfff",
        "\\ud83d", "\\ude00",
    ]
)

# raw control / NUL bytes inside strings (parser accepts)
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

# safe code points (no quote, backslash, control)
_safechar = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_string_piece = st.one_of(
    _safechar,
    _simple_esc,
    _unicode_esc,
    _surrogate_esc,
    _raw_control,
)

def _make_string():
    return st.lists(_string_piece, max_size=12).map(lambda parts: '"' + "".join(parts) + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
    _digits,  # leading zeros (accepted by parser)
    st.just(""),  # for malformed like ".5" or "-"
)

_frac_part = st.one_of(
    st.just(""),
    _digits.map(lambda d: "." + d),
    st.just("."),  # trailing dot (accepted)
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_sign = st.one_of(st.just(""), st.just("-"), st.just("+"))

def _make_number():
    return st.tuples(_sign, _int_part, _frac_part, _exp_part).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

# extreme magnitudes
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-400", "-1e-400",
    "1e999999999", "0." + "0" * 20 + "1",
    "9" * 40, "-" + "9" * 40,
    "123456789012345678901234567890",
    "1e308", "1.7976931348623157e308",
    "0x10", "0xDEADBEEF", "0x", "0xg",
])

_number = st.one_of(_make_number(), _extreme_number)

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null", "NaN", "Infinity", "-Infinity"])

# ---------- recursive values ----------

_key = _make_string()

def _make_pair():
    return st.tuples(_key, st.just(":"), st.deferred(lambda: _value)).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _make_obj():
    return st.tuples(
        st.just("{"),
        st.lists(_make_pair(), max_size=4).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + t[2])

def _make_arr():
    return st.tuples(
        st.just("["),
        st.lists(st.deferred(lambda: _value), max_size=4).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + t[2])

_value = st.deferred(lambda: _value_strategy)

_value_strategy = st.recursive(
    st.one_of(_make_string(), _number, _literal),
    lambda children: st.one_of(_make_obj(), _make_arr()),
    max_leaves=20,
)

# ---------- deep nesting near the 1000 limit ----------

_depth = st.one_of(
    st.just(0),
    st.just(1),
    st.just(2),
    st.integers(min_value=990, max_value=1001),
    st.integers(min_value=0, max_value=50),
)

def _deep_array():
    return _depth.map(lambda d: "[" * d + "]" * d)

def _deep_object():
    return _depth.map(lambda d: '{"a":' * d + "0" + "}" * d)

# ---------- malformed near-valid ----------

_malformed = st.sampled_from([
    "",
    "{",
    "[",
    "}",
    "]",
    ",",
    ":",
    "{},",
    "[,]",
    "[1,]",
    '{"a":1,}',
    '{"a" 1}',
    '{"a":}',
    '{:1}',
    '{"a":1 "b":2}',
    '"unterminated',
    '"\\',
    '"\\u12"',
    '"\\u"',
    '"\\x41"',
    "'single'",
    "{a:1}",
    "{'a':1}",
    "-",
    "+",
    "+1",
    ".5",
    "-.5",
    "1.",
    "01",
    "00",
    "-01",
    "1e",
    "1e+",
    "1e-",
    "1.2.3",
    "1 2",
    "1abc",
    "truefalse",
    "nulll",
    "tru",
    "fals",
    "NaN",
    "Infinity",
    "-Infinity",
    "\\u0000",
    "\x00",
    "\xef\xbb\xbf1",
    "\ufeff1",
    "1\x00",
    '{"a":1}\x00',
    "[1,2,3]extra",
    '{"a":1}{"b":2}',
    "1,2",
])

# ---------- combine ----------

def _join(t):
    return "".join(t)

# structured mutation of a valid value: truncate, splice, or corrupt
def _mutate(v):
    return st.tuples(
        st.just(v),
        st.integers(min_value=0, max_value=3),
        st.sampled_from(["", ",", ":", "\x00", " ", "]", "}", '"', "x", "1"]),
    ).map(lambda t: _apply_mutation(t[0], t[1], t[2]))

def _apply_mutation(v, kind, ins):
    if not v:
        return ins
    if kind == 0:
        # truncate
        n = max(0, len(v) // 2)
        return v[:n]
    if kind == 1:
        # insert junk at random-ish position
        pos = len(v) // 2
        return v[:pos] + ins + v[pos:]
    if kind == 2:
        # drop a char
        pos = len(v) // 2
        return v[:pos] + v[pos + 1:]
    # append junk
    return v + ins

_mutated_value = st.tuples(_value_strategy, st.integers(min_value=0, max_value=3),
                           st.sampled_from(["", ",", ":", "\x00", " ", "]", "}", '"', "x", "1"])).map(
    lambda t: _apply_mutation(t[0], t[1], t[2])
)

# ---------- structural edge cases for branch coverage ----------

# whitespace variations around tokens (tests WS-skipping branches)
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

def _ws_wrap(tok):
    return st.tuples(_ws, st.just(tok), _ws).map(lambda t: t[0] + t[1] + t[2])

_ws_value = st.tuples(_ws, _value_strategy, _ws).map(lambda t: t[0] + t[1] + t[2])

# empty containers and edge shapes
_edge_container = st.sampled_from([
    "[]", "{}", "[[]]", "[{}]", "{{}}", "[0]", '{"":0}', '{"a":[]}',
    '{"a":{}}', "[[[[]]]]", "[[],[]]", "[1,[2,[3]]]",
])

# numbers exercising each branch of the number parser
_number_branches = st.sampled_from([
    "0", "-0", "0.0", "-0.0", "0e0", "0E0", "0e+0", "0e-0",
    "1", "-1", "1.0", "1e1", "1E1", "1e+1", "1e-1",
    "0.5", "-0.5", "123", "-123", "1.5e10", "-1.5E-10",
    "0.0001", "1e000", "1E000",
])

# string escapes exercising each branch of the string parser
_string_branches = st.sampled_from([
    '""', '"a"', '"\\""', '"\\\\"', '"\\/"', '"\\b"', '"\\f"',
    '"\\n"', '"\\r"', '"\\t"', '"\\u0000"', '"\\uFFFF"',
    '"\\uD83D\\uDE00"', '"\\u00e9"', '"\\u00E9"',
    '"a\\nb"', '"\\u0041\\u0042"',
])

# keys exercising string parsing in object context
_key_branches = st.sampled_from([
    '""', '"a"', '"\\n"', '"\\u0041"', '"\\uD83D\\uDE00"', '"key with spaces"',
])

def _obj_key_branch():
    return st.tuples(
        st.just("{"),
        _key_branches,
        st.just(":"),
        _number_branches,
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

# arrays/objects with a variety of separators and whitespace
_sep_variants = st.sampled_from([",", " ,", ", ", " , ", ",\n", ",\t"])

def _arr_multi():
    return st.tuples(
        st.just("["),
        st.lists(_number_branches, min_size=2, max_size=5),
        _sep_variants,
        st.just("]"),
    ).map(lambda t: t[0] + t[2].join(t[1]) + t[3])

def _obj_multi():
    return st.tuples(
        st.just("{"),
        st.lists(
            st.tuples(_key_branches, st.just(":"), _number_branches).map(
                lambda t: t[0] + t[1] + t[2]
            ),
            min_size=2, max_size=4,
        ),
        _sep_variants,
        st.just("}"),
    ).map(lambda t: t[0] + t[2].join(t[1]) + t[3])

# numbers with whitespace around (exercises sign/exp branches with WS)
_number_ws = st.tuples(_ws, _number_branches, _ws).map(lambda t: t[0] + t[1] + t[2])

# literals with whitespace
_literal_ws = st.tuples(_ws, _literal, _ws).map(lambda t: t[0] + t[1] + t[2])

_top = st.one_of(
    _value_strategy,
    _deep_array(),
    _deep_object(),
    _malformed,
    _mutated_value,
    st.tuples(_value_strategy, st.sampled_from(["", "\x00", " ", "x", "1"])).map(_join),
    st.tuples(st.sampled_from(["", "\ufeff", "\xef\xbb\xbf", " ", "\n"]), _value_strategy).map(_join),
    # ---- new branch-targeted generators ----
    _edge_container,
    _number_branches,
    _string_branches,
    _number_ws,
    _literal_ws,
    _ws_value,
    _obj_key_branch(),
    _arr_multi(),
    _obj_multi(),
)

# ---------- improve_strategy: target uncovered branches ----------

# Non-string values inside arrays/objects to exercise value-dispatch branches
# (numbers, literals, nested containers as elements/values).
_dispatch_value = st.sampled_from([
    "0", "-1", "1.5", "1e3", "true", "false", "null",
    "[]", "{}", "[0]", '{"a":0}', "[[]]", "[[0]]",
    '"x"', '""', '"\\n"', '"\\u0041"',
])

def _arr_dispatch():
    return st.tuples(
        st.just("["),
        st.lists(_dispatch_value, min_size=1, max_size=5),
        _sep_variants,
        st.just("]"),
    ).map(lambda t: t[0] + t[2].join(t[1]) + t[3])

def _obj_dispatch():
    return st.tuples(
        st.just("{"),
        st.lists(
            st.tuples(_key_branches, st.just(":"), _dispatch_value).map(
                lambda t: t[0] + t[1] + t[2]
            ),
            min_size=1, max_size=4,
        ),
        _sep_variants,
        st.just("}"),
    ).map(lambda t: t[0] + t[2].join(t[1]) + t[3])

# Numbers with every sign/exp combination to hit +/- and e/E branches
_number_exhaustive = st.tuples(
    st.sampled_from(["", "-", "+"]),
    st.sampled_from(["0", "1", "12", "007"]),
    st.sampled_from(["", ".0", ".5", "."]),
    st.sampled_from(["", "e0", "E0", "e+1", "E+1", "e-1", "E-1", "e10"]),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# String escapes exhaustively: all simple escapes, all u-hex shapes, mixed
_escape_exhaustive = st.tuples(
    st.just('"'),
    st.lists(
        st.one_of(
            _simple_esc,
            _unicode_esc,
            _surrogate_esc,
            st.sampled_from(["a", "Z", " ", "\u00e9", "\u4e2d"]),
        ),
        min_size=0, max_size=6,
    ),
    st.just('"'),
).map(lambda t: t[0] + "".join(t[1]) + t[2])

# Whitespace-heavy documents to exercise WS skipping in every state
_ws_heavy = st.tuples(
    st.lists(_ws, min_size=0, max_size=3),
    st.one_of(_number_branches, _literal, _string_branches, _edge_container),
    st.lists(_ws, min_size=0, max_size=3),
).map(lambda t: "".join(t[0]) + t[1] + "".join(t[2]))

# Trailing-garbage variants to exercise post-value error branches
_trailing = st.tuples(
    st.one_of(_number_branches, _literal, _string_branches, _edge_container),
    st.sampled_from(["", " ", "x", "\x00", ",", "]", "}", "1", "true", '"', ":", "\n", "\t"]),
).map(lambda t: t[0] + t[1])

# Leading-garbage variants to exercise pre-value error branches
_leading = st.tuples(
    st.sampled_from(["", " ", "x", "\x00", ",", "]", "}", "1", "true", '"', ":", "\n", "\t", "\ufeff"]),
    st.one_of(_number_branches, _literal, _string_branches, _edge_container),
).map(lambda t: t[0] + t[1])

_improved = st.one_of(
    _arr_dispatch(),
    _obj_dispatch(),
    _number_exhaustive,
    _escape_exhaustive,
    _ws_heavy,
    _trailing,
    _leading,
)

strategy = st.one_of(_top, _improved)
```