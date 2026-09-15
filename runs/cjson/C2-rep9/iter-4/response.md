```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _num_strategy():
    # integers, including leading zeros / hex / big magnitudes
    ints = st.one_of(
        st.integers(min_value=-10**18, max_value=10**18).map(str),
        st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n) if n else "0"),
        st.integers(min_value=0, max_value=0xFFFFFF).map(lambda n: "0x" + format(n, "x")),
        st.just("0"),
        st.just("-0"),
    )
    fracs = st.builds(
        lambda i, f: f"{i}.{f}",
        st.one_of(st.integers(min_value=-10**6, max_value=10**6).map(str), st.just("0")),
        st.integers(min_value=0, max_value=10**6).map(str),
    )
    trailing_dot = st.builds(
        lambda i: f"{i}.",
        st.integers(min_value=-10**9, max_value=10**9).map(str),
    )
    exps = st.builds(
        lambda m, e, s: f"{m}e{s}{e}",
        st.one_of(st.integers(min_value=0, max_value=10**6).map(str), st.just("1")),
        st.integers(min_value=0, max_value=400),
        st.sampled_from(["", "+", "-"]),
    )
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e-309", "1E+308", "1e308", "0e0",
        "1e999999", "-1e999999", "1.7976931348623157e308",
        "1e-999999", "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.0e10", "1e01", "1e00", "0.0000001",
    ])
    return st.one_of(ints, fracs, trailing_dot, exps, extreme)


def _string_strategy():
    safe = st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='\\"',
        min_codepoint=0x20,
    )
    # raw control bytes / NUL inside strings (parser accepts)
    raw_ctrl = st.sampled_from(["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"])
    escapes = st.sampled_from([
        '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
        "\\u0000", "\\u0001", "\\u001f", "\\u0041", "\\uffff",
        "\\uD83D\\uDE00",  # valid surrogate pair
        "\\ud83d\\ude00",
        "\\u00e9", "\\u20ac",
    ])
    # lone surrogates (parser rejects)
    bad_surrogates = st.sampled_from([
        "\\ud800", "\\udc00", "\\udfff", "\\uD800", "\\uDFFF",
        "\\ud800x", "\\ud800\\ud800",
    ])
    inner = st.one_of(
        st.lists(st.one_of(safe, raw_ctrl, escapes), max_size=8).map("".join),
        st.just(""),
    )
    good = inner.map(lambda s: '"' + s + '"')
    bad = bad_surrogates.map(lambda s: '"' + s + '"')
    unterminated = inner.map(lambda s: '"' + s)
    return st.one_of(good, bad, unterminated)


def _ws():
    return st.text(alphabet=" \t\n\r", max_size=3)


# ---------- recursive value ----------

def _leaf_strategies():
    return st.one_of(
        _string_strategy(),
        _num_strategy(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )


def _obj_from_pairs(pairs):
    if not pairs:
        return "{}"
    return "{" + ",".join(pairs) + "}"


def _arr_from_items(items):
    if not items:
        return "[]"
    return "[" + ",".join(items) + "]"


def _obj_strategy(value_st):
    return st.one_of(
        st.just("{}"),
        st.builds(
            _obj_from_pairs,
            st.lists(
                st.tuples(_string_strategy(), value_st).map(lambda kv: kv[0] + ":" + kv[1]),
                max_size=4,
            ),
        ),
        # duplicate keys
        st.builds(
            lambda v: '{"a":' + v + ',"a":' + v + '}',
            value_st,
        ),
        # whitespace-heavy object
        st.builds(
            lambda k, v: "{ " + k + " : " + v + " }",
            _string_strategy(),
            value_st,
        ),
    )


def _arr_strategy(value_st):
    return st.one_of(
        st.just("[]"),
        st.builds(
            _arr_from_items,
            st.lists(value_st, max_size=4),
        ),
        # whitespace-heavy array
        st.builds(
            lambda v: "[ " + v + " , " + v + " ]",
            value_st,
        ),
        # nested array of arrays
        st.builds(
            lambda v: "[[" + v + "],[" + v + "," + v + "]]",
            value_st,
        ),
    )


def _value_strategy():
    return st.recursive(
        _leaf_strategies(),
        lambda children: st.one_of(
            _obj_strategy(children),
            _arr_strategy(children),
        ),
        max_leaves=15,
    )


# ---------- depth-focused strategies ----------

def _deep_array(depth):
    return "[" * depth + "1" + "]" * depth


def _deep_object(depth):
    return '{"a":' * depth + "1" + "}" * depth


def _depth_strategy():
    # concentrate near the 1000-level limit, targeting depth 700-950
    return st.one_of(
        st.integers(min_value=700, max_value=950).map(_deep_array),
        st.integers(min_value=700, max_value=950).map(_deep_object),
        st.sampled_from([
            _deep_array(700), _deep_array(750), _deep_array(800),
            _deep_array(850), _deep_array(900), _deep_array(950),
            _deep_object(700), _deep_object(750), _deep_object(800),
            _deep_object(850), _deep_object(900), _deep_object(950),
        ]),
    )


# ---------- malformed / near-valid ----------

def _malformed_strategy():
    return st.sampled_from([
        "",
        "{",
        "}",
        "[",
        "]",
        "[1,]",
        "[1,2,]",
        '{"a":1,}',
        '{"a":1,,"b":2}',
        '{"a" 1}',
        '{"a":}',
        '{:1}',
        "{a:1}",
        "{'a':1}",
        "[1 2]",
        "[,1]",
        "[1,,2]",
        "'single'",
        "nul",
        "tru",
        "fals",
        "TRUE",
        "None",
        "NaN",
        "Infinity",
        "-Infinity",
        "+1",
        "-",
        ".5",
        "1.",
        "01",
        "1e",
        "1e+",
        "1.2.3",
        "0x",
        "0xG",
        "\\",
        "\\u",
        "\\u12",
        "\\uZZZZ",
        '"unterminated',
        '"\\',
        '"\\u12"',
        '"\\x41"',
        "1abc",
        "1 2",
        "\ufeff1",
        "\x001",
        "1\x00",
        "   ",
        "\t\n\r",
    ])


# ---------- broaden exploration ----------

def _broadened_value_strategy():
    # wider structural diversity: deeper nesting, more siblings, mixed keys
    return st.recursive(
        _leaf_strategies(),
        lambda children: st.one_of(
            _obj_strategy(children),
            _arr_strategy(children),
            # long arrays of heterogeneous values
            st.builds(
                _arr_from_items,
                st.lists(children, min_size=5, max_size=12),
            ),
            # long objects with varied keys
            st.builds(
                _obj_from_pairs,
                st.lists(
                    st.tuples(_string_strategy(), children).map(lambda kv: kv[0] + ":" + kv[1]),
                    min_size=5,
                    max_size=12,
                ),
            ),
            # mixed nesting array-of-objects
            st.builds(
                lambda a, b, c: "[" + a + ",{" + '"k":' + b + "}," + c + "]",
                children, children, children,
            ),
            # object-of-arrays
            st.builds(
                lambda a, b: '{"x":[' + a + '],"y":[' + b + "]}",
                children, children,
            ),
        ),
        max_leaves=40,
    )


# ---------- composition ----------

@st.composite
def _json_text(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice <= 3:
        v = draw(_value_strategy())
    elif choice == 4:
        v = draw(_depth_strategy())
    elif choice == 5:
        v = draw(_malformed_strategy())
    elif choice == 6:
        # value with trailing content
        v = draw(_value_strategy()) + draw(st.sampled_from(["abc", " 1", "\x00", " xyz", "]"]))
    elif choice == 7:
        # BOM prefix
        v = "\ufeff" + draw(_value_strategy())
    elif choice == 8:
        # leading/trailing whitespace
        v = draw(_ws()) + draw(_value_strategy()) + draw(_ws())
    else:
        # broadened structural exploration
        v = draw(_broadened_value_strategy())
    return v


strategy = _json_text()
```