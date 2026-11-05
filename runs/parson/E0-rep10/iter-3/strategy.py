from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = "0123456789abcdefABCDEF"

def _u_escape():
    # \uXXXX including surrogates and NUL escape (as text, never a raw NUL)
    return st.tuples(
        st.just("\\u"),
        st.lists(st.sampled_from(_hex), min_size=4, max_size=4).map("".join),
    ).map(lambda t: t[0] + t[1])

def _simple_escape():
    return st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _safe_char():
    # printable-ish safe code points, no quote/backslash/control, no raw NUL
    return st.characters(
        blacklist_categories=("Cs", "Cc"),
        blacklist_characters='"\\',
    )

def _string_body():
    return st.lists(
        st.one_of(_safe_char(), _simple_escape(), _u_escape()),
        max_size=12,
    ).map("".join)

def _json_string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(
            st.sampled_from("123456789"),
            st.lists(st.sampled_from("0123456789"), max_size=20).map("".join),
        ).map(lambda t: t[0] + t[1]),
    )

def _frac_part():
    return st.tuples(
        st.just("."),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=20).map("".join),
    ).map(lambda t: t[0] + t[1])

def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=5).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2])

def _number():
    return st.tuples(
        st.sampled_from(["", "-"]),
        _int_part(),
        st.one_of(st.none(), _frac_part()),
        st.one_of(st.none(), _exp_part()),
    ).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or ""))

def _extreme_number():
    return st.one_of(
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e999999"),
        st.just("1e-999999"),
        st.just("1" + "0" * 300),
        st.just("-" + "9" * 300 + "e-400"),
        st.just("0e0"),
        st.just("-0"),
        st.just("1E+308"),
        st.just("1.7976931348623157e309"),
    )

# ---------- malformed fragments ----------

def _malformed_scalar():
    return st.sampled_from([
        "-", "-.", "+", "+1", ".", ".5", "-.5", "01", "00", "1.", "1e",
        "1e+", "0x10", "truex", "nul", "tru", "fals", "NaN", "Infinity",
        "-Infinity", "1.2.3", "--1", "1e++2", "'x'", "True", "NULL",
    ])

def _unterminated_string():
    return st.one_of(
        st.just('"'),
        st.just('"abc'),
        st.tuples(
            st.just('"'),
            st.lists(st.sampled_from("abc\\n\\u0041 "), max_size=8).map("".join),
        ).map(lambda t: t[0] + t[1]),
    )

# ---------- recursive structure ----------

def _key():
    return _json_string()

def _obj_fragments(pair_strategy):
    # returns a strategy producing an object string given a pair-producing strategy
    return st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            st.lists(pair_strategy, min_size=1, max_size=6).map(",".join),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # trailing comma malformed
        st.tuples(
            st.just("{"),
            st.lists(pair_strategy, min_size=1, max_size=4).map(",".join),
            st.just(",}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # missing colon malformed
        st.tuples(
            st.just("{"),
            _key(),
            st.just(" "),
            st.just("0"),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
        # leading comma malformed
        st.tuples(
            st.just("{,"),
            st.lists(pair_strategy, min_size=1, max_size=3).map(",".join),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # double comma malformed
        st.tuples(
            st.just("{"),
            pair_strategy,
            st.just(",,"),
            pair_strategy,
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
    )

def _arr_fragments(value_strategy):
    return st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            st.lists(value_strategy, min_size=1, max_size=6).map(",".join),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # trailing comma
        st.tuples(
            st.just("["),
            st.lists(value_strategy, min_size=1, max_size=4).map(",".join),
            st.just(",]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # double comma
        st.tuples(
            st.just("["),
            value_strategy,
            st.just(",,"),
            value_strategy,
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
        # leading comma
        st.tuples(
            st.just("[,"),
            st.lists(value_strategy, min_size=1, max_size=3).map(",".join),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

# ---------- deep nesting near the 2048 cap ----------

def _deep_nesting():
    # produce arrays/objects nested near the parser limit
    def depth_value():
        return st.integers(min_value=1, max_value=2048)

    def build(depth, open_ch, close_ch):
        return open_ch * depth + close_ch * depth

    return st.one_of(
        st.tuples(depth_value()).map(lambda t: build(t[0], "[", "]")),
        st.tuples(depth_value()).map(lambda t: build(t[0], '{"k":', "}")),
        st.tuples(depth_value()).map(
            lambda t: "[" * t[0] + "0" + "]" * t[0]
        ),
        st.tuples(st.integers(min_value=2040, max_value=2060)).map(
            lambda t: "[" * t[0] + "]" * t[0]
        ),
    )

# ---------- top-level value (recursive) ----------

def _scalar_value():
    return st.one_of(
        _json_string(),
        _number(),
        _extreme_number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed_scalar(),
        _unterminated_string(),
    )

value_strategy = st.recursive(
    _scalar_value(),
    lambda children: st.one_of(
        _obj_fragments(
            st.tuples(_key(), st.just(":"), children).map(
                lambda t: t[0] + t[1] + t[2]
            )
        ),
        _arr_fragments(children),
    ),
    max_leaves=40,
)

# ---------- top-level combinations ----------

def _with_trailing(value_strat):
    trailing = st.sampled_from(
        ["", " ", "abc", " garbage", "xyz", "}", "]", ",", "0", "null", "\n\t"]
    )
    return st.tuples(value_strat, trailing).map(lambda t: t[0] + t[1])

strategy = st.one_of(
    value_strategy,
    _with_trailing(value_strategy),
    _deep_nesting(),
    # duplicate keys (expect rejection)
    st.tuples(
        _key(),
        st.just(":"),
        value_strategy,
        st.just(","),
        _key(),
        st.just(":"),
        value_strategy,
    ).map(lambda t: "{" + t[0] + t[1] + t[2] + t[3] + t[4] + t[5] + t[6] + "}"),
    # whitespace-laden valid value
    st.tuples(
        st.just(" \t\n\r"),
        value_strategy,
        st.just(" \t\n\r"),
    ).map(lambda t: t[0] + t[1] + t[2]),
)