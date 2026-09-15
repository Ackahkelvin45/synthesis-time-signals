from hypothesis import strategies as st
import json

# ---------- leaf fragments ----------

_hex = "0123456789abcdefABCDEF"
_esc_simple = list('"\\/bfnrt')

def _u_escape():
    # valid \uXXXX, sometimes a surrogate pair, sometimes lone surrogate
    return st.one_of(
        st.tuples(st.sampled_from(_hex), st.sampled_from(_hex),
                  st.sampled_from(_hex), st.sampled_from(_hex)).map(
            lambda t: "\\u" + "".join(t)),
        st.tuples(
            st.sampled_from(["d800", "dbff", "dc00", "dfff", "d83d"]),
            st.sampled_from(["dc00", "dfff", "de00", "d800"])
        ).map(lambda t: "\\u" + t[0] + "\\u" + t[1]),
        st.sampled_from(["\\ud800", "\\udfff", "\\udc00", "\\ud83d"]),
    )

def _string_body_char():
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
            lambda c: c not in '"\\'),
        st.sampled_from(["\x00", "\x01", "\x1f", "\t", "\n", "\r", "\x7f"]),
        st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF).filter(
            lambda c: not (0xD800 <= ord(c) <= 0xDFFF)),
        st.sampled_from(_esc_simple).map(lambda c: "\\" + c),
        _u_escape(),
        st.just("\\"),
        st.just('"'),
    )

_string_inner = st.lists(_string_body_char(), max_size=12).map("".join)

def _string():
    return st.builds(lambda b: '"' + b + '"', _string_inner)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text("0123456789", min_size=1, max_size=6).map(
    lambda s: s.lstrip("0") or "0")

def _int_part():
    return st.one_of(
        st.just("0"),
        _digits,                      # may include leading zeros (accepted)
        st.just("0") + _digits,       # explicit leading zero
        _nonzero_digits,
    )

def _frac_part():
    return st.one_of(
        st.just(".") + _digits,
        st.just("."),                 # trailing dot (accepted)
        st.just(".0"),
    )

def _exp_part():
    return st.one_of(
        st.sampled_from(["e", "E"]) + st.sampled_from(["", "+", "-"]) + _digits,
        st.sampled_from(["e", "E"]) + st.sampled_from(["", "+", "-"]) + _digits,
    )

def _number():
    body = st.one_of(
        _int_part(),
        _int_part() + _frac_part(),
        _int_part() + _exp_part(),
        _int_part() + _frac_part() + _exp_part(),
        st.just("0x10"),
        st.just("0XFF"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-309"),
        st.just("-"),
        st.just("+1"),
        st.just(".5"),
        st.just("01"),
        st.just("1."),
        st.just("NaN"),
        st.just("Infinity"),
        st.just("1e999999999999999999999"),
    )
    return st.one_of(
        body,
        st.builds(lambda s: "-" + s, body.filter(lambda s: not s.startswith("-"))),
    )

# ---------- recursive structure ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  "])

def _key():
    return _string()

def _pair():
    return st.builds(
        lambda k, c1, v, c2: k + c1 + ":" + c2 + v,
        _key(), _ws(), st.deferred(lambda: _value()), _ws(),
    )

def _obj():
    pairs = st.lists(_pair(), max_size=4)
    return st.one_of(
        st.just("{}"),
        st.builds(lambda ps: "{" + ",".join(ps) + "}", pairs),
        st.builds(lambda ps: "{" + ", ".join(ps) + "}", pairs),
        st.builds(lambda ps: "{" + ",".join(ps) + ",}", pairs),  # trailing comma
        st.builds(lambda ps: "{" + ",".join(ps) + "", pairs),    # unterminated
        st.builds(lambda ps: "{" + ",,".join(ps) + "}", pairs),  # double comma
        st.builds(lambda ps: "{" + " ".join(ps) + "}", pairs),   # no commas
        st.builds(lambda k: "{" + k + "}", _key()),              # missing colon
    )

def _arr():
    vals = st.lists(st.deferred(lambda: _value()), max_size=4)
    return st.one_of(
        st.just("[]"),
        st.builds(lambda vs: "[" + ",".join(vs) + "]", vals),
        st.builds(lambda vs: "[" + ", ".join(vs) + "]", vals),
        st.builds(lambda vs: "[" + ",".join(vs) + ",]", vals),  # trailing comma
        st.builds(lambda vs: "[" + ",".join(vs) + "", vals),    # unterminated
        st.builds(lambda vs: "[" + ",,".join(vs) + "]", vals),
        st.builds(lambda vs: "[" + " ".join(vs) + "]", vals),
    )

def _value():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _obj(),
        _arr(),
    )

# ---------- deep nesting near the 1000-level limit ----------

def _deep(depth, opener, closer):
    return st.builds(
        lambda d: opener * d + closer * d,
        st.integers(min_value=0, max_value=1000),
    )

_deep_arr = st.integers(min_value=990, max_value=1005).map(
    lambda d: "[" * d + "]" * d)
_deep_obj = st.integers(min_value=990, max_value=1005).map(
    lambda d: '{"a":' * d + "null" + "}" * d)
_deep_mixed = st.integers(min_value=990, max_value=1005).map(
    lambda d: "[" * d + "0" + "]" * d)
_just_over = st.integers(min_value=1001, max_value=1200).map(
    lambda d: "[" * d + "]" * d)

# ---------- malformed / near-valid top-level fragments ----------

_malformed = st.sampled_from([
    "", " ", "\n", "\t",
    ",", ":", "{}", "[]",
    "{,}", "[,]", "{:}", "[1,]", '{"a":}', '{"a" 1}',
    "{'a':1}", "{a:1}", '"unterminated', "'single'",
    "tru", "fals", "nul", "True", "False", "None",
    "01", "1.", ".5", "+1", "-", "0x", "0xG",
    "1e", "1e+", "1e-", "--1", "1..2", "1.2.3",
    "\ufeff1", "1\ufeff", "\ufeff{}", "\ufeffnull",
    "\x00", "1\x00", '"\x00"', '{"a":"\x00"}',
    '"\ud800"', '"\\ud800"', '"\\uD800"', '"\\uDC00"',
    '"\\u"', '"\\u12"', '"\\uZZZZ"', '"\\x41"', '"\\q"',
    "[]]", "[[]", "{{}}", "{{}", "}{",
    "1 2", "1abc", "truefalse", "nullnull",
    "\x00\x00", "[\x00]", '{"\x00":\x00}',
    "1e309", "-1e309", "1e-99999",
])

def _top():
    return st.one_of(
        _value(),
        _deep_arr,
        _deep_obj,
        _deep_mixed,
        _just_over,
        _malformed,
        # trailing content after a valid value (accepted by parser)
        st.builds(lambda v, t: v + t, _value(),
                  st.sampled_from(["", " ", "abc", "\x00", " 1 2", "xyz"])),
        # BOM prefix
        st.builds(lambda v: "\ufeff" + v, _value()),
    )

strategy = _top()