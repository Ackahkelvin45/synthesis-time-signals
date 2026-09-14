from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

# Safe string body characters (no quote, no backslash, no raw control).
_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

# Raw control / NUL bytes that are allowed to appear (parser uses explicit length).
_raw_ctrl = st.sampled_from(
    ["\x00", "\x01", "\x1f", "\x0b", "\x0c", "\x7f"]
)

_hex = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "u" + "".join(t))
_surrogate_escape = st.tuples(
    st.just("d"), st.sampled_from("89abAB"), _hex, _hex
).map(lambda t: "u" + "".join(t))

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _unicode_escape,
    _surrogate_escape,
    st.just("\\u0000"),
    st.just("\\uD800"),
    st.just("\\uDBFF"),
    st.just("\\uDC00"),
    st.just("\\uDFFF"),
)

_str_body = st.one_of(
    _safe,
    _raw_ctrl,
    _escapes,
)

# A string literal (well-formed).
_string = st.lists(_str_body, max_size=12).map(lambda cs: '"' + "".join(cs) + '"')

# Unterminated string (malformed).
_unterminated_string = st.lists(_str_body, min_size=1, max_size=8).map(
    lambda cs: '"' + "".join(cs)
)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=400).map(str),
    ).map(lambda t: "".join(t)),
)

_sign = st.sampled_from(["", "-"])

_number = st.tuples(_sign, _int_part, _frac, _exp).map(lambda t: "".join(t))

# Extreme / special numeric forms (some accepted by this parser, some malformed).
_extreme_number = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-400"),
    st.just("1E308"),
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("0x1F"),
    st.just("1e"),
    st.just("1e+"),
    st.just("--1"),
    st.just("1e999999"),
)

_number_all = st.one_of(_number, _extreme_number)

# ---------- malformed fragments ----------

_malformed = st.one_of(
    _unterminated_string,
    st.just(","),
    st.just(":"),
    st.just("{"),
    st.just("}"),
    st.just("["),
    st.just("]"),
    st.just("'x'"),
    st.just("//x"),
    st.just("/* */1"),
    st.just("true false"),
    st.just("1abc"),
    st.just("[]xyz"),
)

# ---------- recursive value ----------

_value = st.deferred(lambda: _value_strategy)

_key = st.one_of(_string, _unterminated_string)

# pair: STRING ':' value
_pair = st.tuples(_key, st.just(":"), _value).map(lambda t: "".join(t))

# obj with members (biased) and empty obj
_obj_members = st.lists(_pair, min_size=1, max_size=6).map(
    lambda ps: "{" + ",".join(ps) + "}"
)
_obj_empty = st.just("{}")
# trailing comma variant
_obj_trailing = st.lists(_pair, min_size=1, max_size=4).map(
    lambda ps: "{" + ",".join(ps) + ",}"
)
# malformed: double comma / missing colon
_obj_malformed = st.one_of(
    st.lists(_pair, min_size=1, max_size=3).map(
        lambda ps: "{" + ",,".join(ps) + "}"
    ),
    st.tuples(_string, _value).map(lambda t: "{" + t[0] + t[1] + "}"),
    st.just("{,}"),
    st.just("{,1}"),
)

_obj = st.one_of(_obj_empty, _obj_members, _obj_trailing, _obj_malformed)

# arr
_arr_members = st.lists(_value, min_size=1, max_size=6).map(
    lambda vs: "[" + ",".join(vs) + "]"
)
_arr_empty = st.just("[]")
_arr_trailing = st.lists(_value, min_size=1, max_size=4).map(
    lambda vs: "[" + ",".join(vs) + ",]"
)
_arr_malformed = st.one_of(
    st.lists(_value, min_size=1, max_size=3).map(
        lambda vs: "[" + ",,".join(vs) + "]"
    ),
    st.just("[,]"),
    st.just("[,1]"),
)

_arr = st.one_of(_arr_empty, _arr_members, _arr_trailing, _arr_malformed)

_literal = st.sampled_from(["true", "false", "null"])

_value_strategy = st.one_of(
    _string,
    _unterminated_string,
    _number_all,
    _literal,
    _obj,
    _arr,
    _malformed,
)

# ---------- deep nesting ----------

_deep = st.integers(min_value=1, max_value=200)


def _deep_obj(n):
    return "{" + '"a":' * n + "1" + "}" * n


def _deep_arr(n):
    return "[" * n + "1" + "]" * n


_deep_nested = st.one_of(
    _deep.map(_deep_obj),
    _deep.map(_deep_arr),
)

# ---------- near-crash structural mutations ----------
# Take the known crashing input and mutate structurally around it: truncate,
# duplicate, splice, and perturb delimiters / escapes to reach the deep
# parser paths (json_parse, json_parse_ex, new_value, hex_value) that the
# current strategy misses.

_crash_seed = '{"a":' * 200 + "1" + "}" * 200

_truncations = st.integers(min_value=1, max_value=len(_crash_seed)).map(
    lambda n: _crash_seed[:n]
)

_duplications = st.integers(min_value=1, max_value=4).map(
    lambda n: _crash_seed * n
)

_splices = st.integers(min_value=0, max_value=len(_crash_seed)).map(
    lambda n: _crash_seed[:n] + _crash_seed[n:]
)

_delim_perturb = st.tuples(
    st.integers(min_value=0, max_value=len(_crash_seed) - 1),
    st.sampled_from(['"', "\\", "{", "}", "[", "]", ",", ":", "\x00", "u"]),
).map(lambda t: _crash_seed[: t[0]] + t[1] + _crash_seed[t[0] + 1 :])

_deletions = st.integers(min_value=0, max_value=len(_crash_seed) - 1).map(
    lambda n: _crash_seed[:n] + _crash_seed[n + 1 :]
)

_hex_mutation = st.tuples(
    st.integers(min_value=0, max_value=len(_crash_seed) - 1),
    _hex,
).map(lambda t: _crash_seed[: t[0]] + t[1] + _crash_seed[t[0] + 1 :])

_near_crash = st.one_of(
    st.just(_crash_seed),
    _truncations,
    _duplications,
    _splices,
    _delim_perturb,
    _deletions,
    _hex_mutation,
    st.tuples(
        _truncations,
        st.sampled_from(['"', "\\", "\\u", "\x00", "{", "[", ",", ":"]),
    ).map(lambda t: t[0] + t[1]),
)

# ---------- top level ----------

# whitespace padding occasionally
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", " \t\n\r"])

_top = st.one_of(
    _value_strategy,
    _deep_nested,
)

strategy = st.one_of(
    _top,
    st.tuples(_ws, _top, _ws).map(lambda t: "".join(t)),
    _near_crash,
)