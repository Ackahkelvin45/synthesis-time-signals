from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = st.characters(min_codepoint=0x30, max_codepoint=0x39).map(str) | \
       st.characters(min_codepoint=0x61, max_codepoint=0x66).map(str) | \
       st.characters(min_codepoint=0x41, max_codepoint=0x46).map(str)

_hex4 = st.lists(_hex, min_size=4, max_size=4).map("".join)

_escapes = st.one_of(
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    _hex4.map(lambda h: "\\u" + h),
    # lone surrogates and other 4-hex escapes
    st.sampled_from(["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\u0000",
                     "\\u0001", "\\u001f", "\\uFFFF", "\\u00e9"]),
)

# characters allowed inside a JSON string body (no raw quote, no raw backslash,
# no raw control chars per grammar; but we deliberately include raw control/NUL
# in the "malformed" family below).
_safe_char = st.characters(
    blacklist_categories=["Cs"],
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
                        '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

_string_body = st.lists(
    st.one_of(_safe_char, _escapes), min_size=0, max_size=12
).map("".join)

_json_string = _string_body.map(lambda b: '"' + b + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=8)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.integers(min_value=1, max_value=9).map(str), _digits)
      .map(lambda t: t[0] + t[1]),
    _digits,
)

_frac = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=5),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # extreme exponents
    st.sampled_from(["e309", "E309", "e-309", "e9999", "E+308", "e308"]),
)

_sign = st.one_of(st.just(""), st.just("-"))

_number = st.tuples(_sign, _int_part, _frac, _exp).map(lambda t: "".join(t))

# malformed / edge number forms (the parser may accept some, e.g. lone "-")
_bad_number = st.sampled_from([
    "-", "+", "+1", ".5", "1.", "01", "00", "0x1F", "1e", "1e+", "1e-",
    "--1", "1..2", "1.2.3", ".", "-.", "-.5", "1e309", "1e-999",
    "1e999999999", "0.0e0", "-0", "1_000",
])

# ---------- malformed fragments ----------

_malformed = st.sampled_from([
    "{,}", "[,]", "[1,,2]", "{,}", "{\"a\":}", "{\"a\" 1}", "{a:1}",
    "{'a':1}", "[1 2]", "[1,2,,]", "{,}", "[", "]", "{", "}", "[1",
    "{\"a\":1", "\"unterminated", "\"", "'x'", "//x", "/* */1",
    "1abc", "[]xyz", "true false", "nul", "tru", "fals", "{}extra",
    "[1,2]junk", "\x00", "\x01\x02", "{}\x00", "[\x00]",
])

# ---------- recursive JSON ----------

def _make_value():
    return st.recursive(
        # leaves
        st.one_of(
            _json_string,
            _number,
            st.sampled_from(["true", "false", "null"]),
            _bad_number,
        ),
        # recursive combinators: obj and arr
        lambda children: st.one_of(
            _make_obj(children),
            _make_arr(children),
        ),
        max_leaves=40,
    )


def _make_pair(value_st):
    key = st.one_of(
        _json_string,
        # duplicate-key bias: a small fixed pool of keys
        st.sampled_from(['"a"', '"b"', '"key"', '"dup"', '""']),
    )
    return st.tuples(key, value_st).map(lambda t: t[0] + ":" + t[1])


def _make_obj(value_st):
    def build(pairs):
        body = ",".join(pairs)
        # bias toward non-empty objects
        if pairs and st.randoms is not None:
            pass
        return "{" + body + "}"

    pair = _make_pair(value_st)

    # non-empty objects (stressed path) plus occasionally empty
    nonempty = st.lists(pair, min_size=1, max_size=6).map(build)
    empty = st.just("{}")
    trailing = st.lists(pair, min_size=1, max_size=4).map(
        lambda ps: "{" + ",".join(ps) + ",}"
    )
    return st.one_of(nonempty, empty, trailing)


def _make_arr(value_st):
    def build(items):
        return "[" + ",".join(items) + "]"

    nonempty = st.lists(value_st, min_size=1, max_size=6).map(build)
    empty = st.just("[]")
    trailing = st.lists(value_st, min_size=1, max_size=4).map(
        lambda xs: "[" + ",".join(xs) + ",]"
    )
    return st.one_of(nonempty, empty, trailing)


_value = _make_value()

# ---------- top-level strategy ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  "])

# ---------- near-crash mutation family ----------
# The crashing inputs share the shape: a well-formed JSON value followed by a
# stray NUL byte ("\"\"\x00", "[]\x00"). Intensify structurally around this
# by generating many variants: any value (or value-ish fragment) with NUL/control
# bytes at varying positions, plus nested/trailing NUL combinations.

_nul = st.sampled_from(["\x00", "\x01", "\x00\x00", "\x01\x02", "\x1f"])

_near_crash_base = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
    st.just("[]"),
    st.just("{}"),
    st.just("[1,2]"),
    st.just('{"a":1}'),
    st.just('""'),
    st.just("0"),
)

# value + trailing NUL/control byte(s)
_near_crash_trailing = st.tuples(_near_crash_base, _nul).map(
    lambda t: t[0] + t[1]
)

# NUL/control byte(s) + value
_near_crash_leading = st.tuples(_nul, _near_crash_base).map(
    lambda t: t[0] + t[1]
)

# NUL embedded between two values / fragments
_near_crash_middle = st.tuples(
    _near_crash_base, _nul, _near_crash_base
).map(lambda t: t[0] + t[1] + t[2])

# NUL inside containers (array / object) at various positions
_near_crash_in_arr = st.one_of(
    st.tuples(st.just("["), _nul, st.just("]")).map(lambda t: "".join(t)),
    st.tuples(st.just("["), _nul, _near_crash_base, st.just("]")).map(
        lambda t: "".join(t)
    ),
    st.tuples(st.just("["), _near_crash_base, _nul, st.just("]")).map(
        lambda t: "".join(t)
    ),
    st.tuples(st.just("["), _near_crash_base, st.just(","), _nul,
              _near_crash_base, st.just("]")).map(lambda t: "".join(t)),
)

_near_crash_in_obj = st.one_of(
    st.tuples(st.just('{"a":'), _nul, st.just("}")).map(lambda t: "".join(t)),
    st.tuples(st.just('{"a":'), _near_crash_base, st.just(","), _nul,
              st.just('"b":1}')).map(lambda t: "".join(t)),
    st.tuples(st.just("{"), _nul, st.just('"a":1}')).map(lambda t: "".join(t)),
)

# repeated NUL padding around a value
_near_crash_padded = st.tuples(
    st.lists(_nul, min_size=0, max_size=4).map("".join),
    _near_crash_base,
    st.lists(_nul, min_size=0, max_size=4).map("".join),
).map(lambda t: t[0] + t[1] + t[2])

# nested containers with trailing NUL (deep-ish, stresses cleanup on error)
_near_crash_nested = st.tuples(
    st.integers(min_value=0, max_value=30),
    _nul,
).map(lambda t: "[" * t[0] + "1" + "]" * t[0] + t[1])

_near_crash_nested_obj = st.tuples(
    st.integers(min_value=1, max_value=30),
    _nul,
).map(lambda t: "{" + '"a":' * t[0] + "1" + "}" * t[0] + t[1])

# NUL-only and NUL with surrounding whitespace
_near_crash_ws = st.tuples(
    _ws, _nul, _ws
).map(lambda t: t[0] + t[1] + t[2])

_near_crash = st.one_of(
    _near_crash_trailing,
    _near_crash_leading,
    _near_crash_middle,
    _near_crash_in_arr,
    _near_crash_in_obj,
    _near_crash_padded,
    _near_crash_nested,
    _near_crash_nested_obj,
    _near_crash_ws,
)

_top = st.one_of(
    # near-crash structural mutations (heavily emphasized)
    _near_crash,
    _near_crash,
    _near_crash,
    # valid-ish documents
    _value,
    # malformed fragments
    _malformed,
    # documents with surrounding whitespace
    st.tuples(_ws, _value, _ws).map(lambda t: t[0] + t[1] + t[2]),
    # deep nesting stress (objects with members)
    st.integers(min_value=1, max_value=200).map(
        lambda n: "{" + '"a":' * n + "1" + "}" * n
    ),
    st.integers(min_value=1, max_value=200).map(
        lambda n: "[" * n + "1" + "]" * n
    ),
    # embedded NUL / control bytes around a value
    st.tuples(st.just("\x00"), _value).map(lambda t: t[0] + t[1]),
    st.tuples(_value, st.just("\x00")).map(lambda t: t[0] + t[1]),
    st.just("\x00"),
    st.just(""),
)

strategy = _top