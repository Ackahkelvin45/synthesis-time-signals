```python
import json

from hypothesis import strategies as st


# ---------- leaf / atom strategies ----------

# Valid JSON strings (with escapes, unicode, surrogate escapes, control bytes).
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) < 0x20 or ord(c) >= 0x20)

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex = st.sampled_from("0123456789abcdefABCDEF")
_unicode_escape = st.tuples(
    st.just("\\u"), _hex, _hex, _hex, _hex
).map(lambda t: "".join(t))

# Lone surrogate escapes (high and low) - valid escapes, dubious semantics.
_surrogate_escape = st.tuples(
    st.just("\\u"),
    st.sampled_from("dD"),
    st.sampled_from("89abAB"),
    _hex,
    _hex,
).map(lambda t: "".join(t))

_string_body_piece = st.one_of(
    _safe_char.map(str),
    _escapes,
    _unicode_escape,
    _surrogate_escape,
)

_json_string = st.lists(
    _string_body_piece, min_size=0, max_size=8
).map(lambda parts: '"' + "".join(parts) + '"')


# ---------- number strategies ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(
        st.sampled_from("123456789"),
        st.lists(st.sampled_from("0123456789"), min_size=0, max_size=8),
    ).map(lambda t: t[0] + "".join(t[1])),
)

_frac_part = st.tuples(
    st.just("."),
    st.lists(st.sampled_from("0123456789"), min_size=1, max_size=8),
).map(lambda t: t[0] + "".join(t[1]))

_exp_part = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.lists(st.sampled_from("0123456789"), min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + "".join(t[2]))

_opt_frac = st.one_of(st.just(""), _frac_part)
_opt_exp = st.one_of(st.just(""), _exp_part)

# Extreme exponents to force overflow / non-finite.
_extreme_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.sampled_from(["309", "310", "400", "999", "10000", "308", "307"]),
).map(lambda t: t[0] + t[1] + t[2])

_valid_number = st.tuples(
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    _opt_frac,
    st.one_of(_opt_exp, _extreme_exp),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Parser-accepted oddities.
_lenient_number = st.sampled_from([
    "-",
    "1e309",
    "-1e309",
    "1E999",
    "0e0",
    "1e01",
    "-0",
    "0.0",
    "1.5e+308",
])

# Malformed / near-valid number forms (should be rejected, good fuzz).
_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "00", "0x1F", "-.5", "1..2", "1e", "1e+",
    "--1", "1-2", "1.2.3",
])

_number = st.one_of(_valid_number, _lenient_number, _bad_number)


# ---------- malformed string fragments ----------

_bad_string = st.sampled_from([
    '"unterminated',
    '"bad\\xescape"',
    '"\\u12"',
    '"\\uZZZZ"',
    '"\\"',
    '"',
    'abc',
    "'single'",
    '"\\u"',
])


# ---------- recursive structure ----------

def _make_value(value_st):
    scalars = st.one_of(
        _json_string,
        _number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _bad_string,
    )
    return st.one_of(scalars, value_st)


# Control bytes / NUL for embedded-in-string and raw emission.
_control_bytes = st.builds(
    lambda n: chr(n), st.integers(min_value=0, max_value=0x1F)
)


# A "pair" is a STRING ':' value.
def _pair(value_st):
    return st.tuples(
        _json_string,
        st.just(":"),
        value_st,
    ).map(lambda t: t[0] + t[1] + t[2])


# A member is STRING ':' value (used inside objects).
def _obj_members(value_st):
    return st.tuples(
        _json_string,
        st.just(":"),
        value_st,
    ).map(lambda t: t[0] + t[1] + t[2])


def _make_obj(value_st):
    members = _obj_members(value_st)
    member_list = st.lists(members, min_size=1, max_size=6)
    # bias toward objects with members (stressed first-pass path)
    return st.one_of(
        st.just("{}"),
        member_list.map(lambda ms: "{" + ",".join(ms) + "}"),
        # trailing comma leniency
        member_list.map(lambda ms: "{" + ",".join(ms) + ",}"),
        # duplicate keys
        member_list.map(
            lambda ms: "{" + ",".join(ms + ms[:1]) + "}"
        ),
        # missing colon / malformed
        member_list.map(
            lambda ms: "{" + ",".join(ms) + ",,}"
        ),
    )


def _make_arr(value_st):
    value_list = st.lists(value_st, min_size=0, max_size=6)
    return st.one_of(
        st.just("[]"),
        value_list.map(lambda vs: "[" + ",".join(vs) + "]"),
        # trailing comma leniency
        value_list.filter(lambda vs: len(vs) > 0).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
        # double comma malformed
        value_list.filter(lambda vs: len(vs) > 0).map(
            lambda vs: "[" + ",".join(vs) + ",,]"
        ),
    )


def _build_value():
    # Recursive value: leaves + obj/arr referencing value.
    return st.recursive(
        _make_value(st.nothing()),
        lambda children: st.one_of(
            _make_obj(children),
            _make_arr(children),
        ),
        max_leaves=12,
    )


_value = _build_value()


# ---------- top-level json: value EOF, plus whitespace and raw control ----------

_ws = st.lists(
    st.sampled_from([" ", "\t", "\n", "\r"]), min_size=0, max_size=3
).map(lambda xs: "".join(xs))


def _wrap(v):
    return v


_top = st.tuples(
    _ws,
    _value,
    _ws,
).map(lambda t: t[0] + t[1] + t[2])


# Occasionally inject a raw NUL / control byte into the whole document.
_nul_injected = st.tuples(
    _top,
    _control_bytes,
    st.integers(min_value=0, max_value=1),
).map(lambda t: t[0] + t[1] if t[2] else t[1] + t[0])


# A few hand-crafted deep nestings.
_deep = st.integers(min_value=1, max_value=200).flatmap(
    lambda n: st.just("[" * n + "]" * n)
)

_deep_obj = st.integers(min_value=1, max_value=60).flatmap(
    lambda n: st.just(
        "{" + '{"a":' * n + "1" + "}" * n + "}"
    )
)


strategy = st.one_of(
    _top,
    _nul_injected,
    _deep,
    _deep_obj,
)
```