from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
)
_SAFE_NOCTRL = _SAFE.filter(lambda c: ord(c) >= 0x20)

_ESCAPES = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_HEX = st.sampled_from("0123456789abcdefABCDEF")
_UNICODE_ESC = st.tuples(_HEX, _HEX, _HEX, _HEX).map(lambda t: "\\u" + "".join(t))

_SURROGATE_ESC = st.tuples(
    st.sampled_from("dD"), st.sampled_from("89abAB"),
    _HEX, _HEX,
).map(lambda t: "\\u" + t[0] + t[1] + t[2] + t[3])

_STR_BODY = st.one_of(
    _SAFE_NOCTRL,
    _ESCAPES,
    _UNICODE_ESC,
    _SURROGATE_ESC,
    st.just("\x00"),
    st.just("\x01"),
    st.just("\x1f"),
    st.just("\x7f"),
)

_STR_CONTENT = st.lists(_STR_BODY, max_size=12).map("".join)

_STRING = _STR_CONTENT.map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=1, max_value=10**40).map(str),
    st.integers(min_value=10**300, max_value=10**320).map(str),
)

_FRAC = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    st.integers(min_value=10**300, max_value=10**320).map(lambda n: "." + str(n)),
)

_EXP = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.one_of(st.just(""), st.just("+"), st.just("-")),
        st.integers(min_value=0, max_value=400).map(str),
    ).map(lambda t: t[0] + t[1] + t[2]),
    st.just("e309"),
    st.just("E309"),
    st.just("e-309"),
    st.just("e999999999"),
)

_SIGN = st.one_of(st.just(""), st.just("-"))

_NUMBER = st.tuples(_SIGN, _INT, _FRAC, _EXP).map(lambda t: "".join(t))

# ---------- malformed number forms (still useful) ----------

_BAD_NUMBER = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-", "-.5", "+.5",
    "1e", "1e+", "1e-", "1.2.3", "1e309", "-1e309", "1E309",
    "--1", "1e+309", "0.", "00", "-01", "1..2",
])

# ---------- malformed strings ----------

_BAD_STRING = st.one_of(
    st.just('"unterminated'),
    st.just('"'),
    st.just('"\\'),
    st.just('"\\u"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('"\\x41"'),
    st.just("'single'"),
    st.just("bare"),
)

# ---------- malformed structural fragments ----------

_BAD_FRAGMENT = st.sampled_from([
    "[1,,2]", "[,]", "[,1]", "{,}", "{,1}", '{"a":1,,"b":2}',
    '{"a" 1}', '{"a":}', '{:1}', '{"a":1 "b":2}', '{a:1}',
    '[1 2]', '[1,2', '{"a":1', '}', ']', '[', '{',
    '{"a":1}}', '[1,2]]', '1abc', '[]xyz', '1 garbage', 'true false',
    '//x', '/* */1',
    '[}', '{]', '{"a":[}', '[{"a":1]',
])

_WS = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("\r"),
    st.just("\x00"),
    st.just("\x0b"),
    st.just("\x0c"),
)

# ---------- recursive value ----------

_value = st.deferred(lambda: _value_strategy)

_key = _STRING

_pair = st.tuples(_key, _WS, st.just(":"), _WS, _value).map(lambda t: "".join(t))

_obj_members = st.tuples(
    _pair,
    st.lists(st.tuples(st.just(","), _pair).map(lambda t: t[0] + t[1]), max_size=6),
).map(lambda t: t[0] + "".join(t[1]))

_obj = st.one_of(
    st.just("{}"),
    _obj_members.map(lambda s: "{" + s + "}"),
    _obj_members.map(lambda s: "{" + s + ",}"),
    st.just("{" + "\x00" + "}"),
    st.just('{"a":1,"a":2}'),
    st.just('{"a":1,"a":2,"a":3}'),
)

_arr = st.one_of(
    st.just("[]"),
    st.lists(_value, min_size=1, max_size=8).map(lambda xs: "[" + ",".join(xs) + "]"),
    st.lists(_value, min_size=1, max_size=8).map(lambda xs: "[" + ",".join(xs) + ",]"),
)

_leaf_value = st.one_of(
    _STRING,
    _NUMBER,
    _BAD_NUMBER,
    _BAD_STRING,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("TRUE"),
    st.just("None"),
)

_value_strategy = st.one_of(
    _leaf_value,
    _obj,
    _arr,
    _BAD_FRAGMENT,
)

_deep = st.integers(min_value=0, max_value=200).flatmap(
    lambda n: st.just("[" * n + "1" + "]" * n)
)

_deep_obj = st.integers(min_value=0, max_value=60).flatmap(
    lambda n: st.just('{"a":' * n + "1" + "}" * n)
)

# ---------- near-crash structural mutations ----------

_NEAR_CRASH_SEEDS = [
    '"\\x41"',
    '"\\x00"',
    '"\\x"',
    '"\\x4"',
    '"\\xZZ"',
    '"\\\\x41"',
    '"\\u0041"',
    '"\\u"',
    '"\\u0"',
    '"\\uD800"',
    '"\\uD800\\uDC00"',
    '"\\uDC00"',
    '"\\x41\\x42"',
    '"\\x41"\\x42',
    '["\\x41"]',
    '{"a":"\\x41"}',
    '{"a":["\\x41"]}',
]

_NEAR_CRASH_MUTATION = st.one_of(
    st.sampled_from(_NEAR_CRASH_SEEDS),
    st.tuples(
        st.sampled_from(_NEAR_CRASH_SEEDS),
        st.lists(
            st.sampled_from([
                '"', '\\', 'x', 'u', '0', '4', '1', 'D', '8', 'C',
                'A', 'F', 'Z', '[', ']', '{', '}', ':', ',', ' ',
                '\x00', '\x01', '\x7f',
            ]),
            min_size=1, max_size=6,
        ),
    ).map(lambda t: t[0][:-1] + "".join(t[1]) + t[0][-1]),
    st.tuples(
        st.sampled_from(_NEAR_CRASH_SEEDS),
        st.integers(min_value=0, max_value=8),
    ).map(lambda t: t[0][:t[1]] + t[0][t[1] + 1:] if t[1] < len(t[0]) else t[0]),
    st.tuples(
        st.sampled_from(_NEAR_CRASH_SEEDS),
        st.sampled_from(['"', '\\', 'x', 'u', '\x00', 'A', 'F']),
        st.integers(min_value=0, max_value=10),
    ).map(lambda t: t[0][:t[2]] + t[1] + t[0][t[2]:]),
    st.tuples(
        st.sampled_from(_NEAR_CRASH_SEEDS),
        st.sampled_from(['"', '\\', 'x', 'u', '\x00', 'A', 'F']),
        st.integers(min_value=0, max_value=10),
    ).map(lambda t: t[0][:t[2]] + t[1] + t[0][t[2] + 1:] if t[2] < len(t[0]) else t[0] + t[1]),
)

# ---------- intensified structural mutations around the crashing input ----------
# The observed crash signature is a UBSan null-pointer-offset in the parse
# function, hit by the near-crash string seeds (e.g. '"\\x41"'). Intensify by
# structurally wrapping / splicing / nesting those seeds instead of only
# mutating them in place.

_CRASH_CORE = st.sampled_from([
    '"\\x41"',
    '"\\x00"',
    '"\\x"',
    '"\\x4"',
    '"\\xZZ"',
    '"\\u0041"',
    '"\\uD800"',
    '"\\uDC00"',
    '"\\x41\\x42"',
])

_STRUCT_WRAP_PREFIX = st.sampled_from([
    "[", "{", '{"a":', '["', '{"a":["', "[{", '{"a":[{"b":',
])
_STRUCT_WRAP_SUFFIX = st.sampled_from([
    "]", "}", "]}", '"]}', '"]}]}', "}]}", "]}]}",
])
_STRUCT_SEP = st.sampled_from([",", ":", ",,", " ", ", ", ": ", "\x00", ","])

_STRUCTURAL_MUTATION = st.one_of(
    # wrap the crashing core inside nested containers
    st.tuples(_STRUCT_WRAP_PREFIX, _CRASH_CORE, _STRUCT_WRAP_SUFFIX).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # splice two crash cores together with a structural separator
    st.tuples(_CRASH_CORE, _STRUCT_SEP, _CRASH_CORE).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # nested array/object of crash cores
    st.tuples(
        st.lists(_CRASH_CORE, min_size=1, max_size=4),
        st.sampled_from(["[", "{"]),
        st.sampled_from(["]", "}"]),
    ).map(lambda t: t[1] + ",".join(t[0]) + t[2]),
    # object with crash-core key and value
    st.tuples(_CRASH_CORE, _CRASH_CORE).map(lambda t: "{" + t[0] + ":" + t[1] + "}"),
    # deep nesting around the crash core
    st.tuples(
        st.integers(min_value=1, max_value=40),
        _CRASH_CORE,
        st.sampled_from(["[]", "{}"]),
    ).map(lambda t: t[2][0] * t[0] + t[1] + t[2][1] * t[0]),
    # crash core with trailing structural garbage
    st.tuples(
        _CRASH_CORE,
        st.lists(
            st.sampled_from([
                "[", "]", "{", "}", ":", ",", '"', "\\", "x", "u",
                "\x00", " ", "1", "a",
            ]),
            min_size=1, max_size=8,
        ),
    ).map(lambda t: t[0] + "".join(t[1])),
    # structural fragments with crash core embedded
    st.tuples(
        st.sampled_from([
            '{"a":', '["', '{"a":[', '[{',
        ]),
        _CRASH_CORE,
        st.sampled_from([
            "}", "]", "]}", '"]}', "}]}",
        ]),
        st.lists(
            st.sampled_from(["[", "]", "{", "}", ",", ":", '"', "\x00"]),
            min_size=0, max_size=4,
        ),
    ).map(lambda t: t[0] + t[1] + t[2] + "".join(t[3])),
)

# ---------- intensified near-crash structural mutation (intensify_near_crash) ----------
# Push harder on the crashing input by combining multiple structural mutations
# in sequence: wrap, then splice, then nest, then append garbage, and finally
# apply character-level mutation to the whole structure. This targets the
# UBSan null-pointer-offset in the parse function.

_GARBAGE_CHARS = st.sampled_from([
    "[", "]", "{", "}", ":", ",", '"', "\\", "x", "u", "0", "4",
    "D", "8", "C", "A", "F", "Z", "\x00", "\x01", "\x7f", " ",
])

_GARBAGE = st.lists(_GARBAGE_CHARS, min_size=0, max_size=12).map("".join)

_WRAP = st.tuples(
    st.sampled_from([
        "[", "{", '{"a":', '["', '{"a":["', "[{", '{"a":[{"b":',
        '{"a":[{"b":["', '[[', '{{',
    ]),
    _CRASH_CORE,
    st.sampled_from([
        "]", "}", "]}", '"]}', '"]}]}', "}]}", "]}]}", "]]", "}}",
    ]),
).map(lambda t: t[0] + t[1] + t[2])

_SPLICE = st.tuples(
    _CRASH_CORE,
    st.sampled_from([",", ":", ",,", " ", ", ", ": ", "\x00", ",", "][", "}{"]),
    _CRASH_CORE,
).map(lambda t: t[0] + t[1] + t[2])

_NEST = st.tuples(
    st.integers(min_value=1, max_value=60),
    st.one_of(_CRASH_CORE, _WRAP, _SPLICE),
    st.sampled_from(["[]", "{}", "[{}]", "{\"a\":[]}"]),
).map(lambda t: t[2][0] * t[0] + t[1] + t[2][-1] * t[0])

_EMBED = st.tuples(
    st.sampled_from([
        '{"a":', '["', '{"a":[', '[{', '{"a":{"b":', '[[',
    ]),
    st.one_of(_CRASH_CORE, _WRAP, _SPLICE),
    st.sampled_from([
        "}", "]", "]}", '"]}', "}]}", "]]", "}}", "}]}]}",
    ]),
    _GARBAGE,
).map(lambda t: t[0] + t[1] + t[2] + t[3])

_CHAR_MUTATE = st.tuples(
    st.one_of(_CRASH_CORE, _WRAP, _SPLICE, _EMBED),
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=40),
            _GARBAGE_CHARS,
        ),
        min_size=1, max_size=6,
    ),
).map(lambda t: "".join(
    t[0][:pos] + ch + t[0][pos + 1:]
    if pos < len(t[0]) else t[0] + ch
    for pos, ch in sorted(t[1], key=lambda p: p[0])
))

_CHAIN = st.one_of(_WRAP, _SPLICE, _NEST, _EMBED, _CHAR_MUTATE)

_INTENSIFIED_NEAR_CRASH = st.one_of(
    _CHAIN,
    # double-wrap: wrap a wrap
    st.tuples(
        st.sampled_from(["[", "{", '{"a":', '["']),
        _WRAP,
        st.sampled_from(["]", "}", "]}", '"]}']),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # wrap then append garbage
    st.tuples(_WRAP, _GARBAGE).map(lambda t: t[0] + t[1]),
    # splice then wrap
    st.tuples(
        st.sampled_from(["[", "{", '{"a":', '["']),
        _SPLICE,
        st.sampled_from(["]", "}", "]}", '"]}']),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # nest then splice with another core
    st.tuples(_NEST, _STRUCT_SEP, _CRASH_CORE).map(lambda t: t[0] + t[1] + t[2]),
    # embed then char-mutate
    st.tuples(_EMBED, _GARBAGE).map(lambda t: t[0] + t[1]),
    # multiple cores in nested containers with garbage
    st.tuples(
        st.lists(st.one_of(_CRASH_CORE, _WRAP), min_size=1, max_size=5),
        st.sampled_from(["[", "{"]),
        st.sampled_from(["]", "}"]),
        _GARBAGE,
    ).map(lambda t: t[1] + ",".join(t[0]) + t[2] + t[3]),
)

# ---------- top-level ----------

_top = st.one_of(
    _value,
    _deep,
    _deep_obj,
    st.tuples(_WS, _value, _WS).map(lambda t: t[0] + t[1] + t[2]),
    st.just(""),
    st.just("\x00"),
    st.just(" "),
    st.just("null\x00"),
    st.just("\x00null"),
    _NEAR_CRASH_MUTATION,
    _STRUCTURAL_MUTATION,
    _INTENSIFIED_NEAR_CRASH,
)

strategy = _top