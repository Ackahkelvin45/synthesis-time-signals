```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _unicode_escape():
    return st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map("".join)

def _simple_escape():
    return st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _escape():
    return st.one_of(_simple_escape(), _unicode_escape())

# control / NUL bytes and other raw codepoints allowed inside strings
def _raw_char():
    return st.one_of(
        st.characters(min_codepoint=0, max_codepoint=0x1F),  # control + NUL
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(
            lambda c: c not in '"\\'
        ),
    )

def _string_body_piece():
    return st.one_of(_escape(), _raw_char())

def _string_body():
    return st.lists(_string_body_piece(), max_size=8).map("".join)

def json_string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.integers(min_value=1, max_value=9).map(str),
    )

def _frac_part():
    return st.tuples(st.just("."), st.integers(min_value=0, max_value=10**9).map(str)).map("".join)

def _exp_part():
    return st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=10**5).map(str),
    ).map("".join)

def json_number():
    sign = st.sampled_from(["", "-"])
    base = st.tuples(sign, _int_part()).map("".join)
    frac = st.one_of(st.just(""), _frac_part())
    exp = st.one_of(st.just(""), _exp_part())
    normal = st.tuples(base, frac, exp).map("".join)

    # extremes / overflow / non-finite
    extreme = st.sampled_from(
        [
            "1e309", "-1e309", "1e308", "-1e308", "1e999999", "-1e999999",
            "1E309", "1e+309", "1e-309", "1e-999999",
            "0e0", "-0", "-0.0", "0.0", "1e0", "1E0",
            "123456789012345678901234567890",
            "1.7976931348623157e308", "1.7976931348623159e308",
            "5e-324", "2.2250738585072014e-308",
            "9" * 40, "1" + "0" * 30 + "e" + "9" * 10,
        ]
    )
    # parser-accepted lone '-'
    lone = st.just("-")
    return st.one_of(normal, extreme, lone)

json_number_strategy = json_number()

# ---------- malformed near-valid fragments ----------

malformed_number = st.sampled_from(
    ["+1", ".5", "1.", "01", "0x1F", "1e", "1e+", "--1", "+", ".", "1..2", "1e1.2"]
)

unterminated_string = st.sampled_from(
    ['"abc', '"', '"\\', '"\\u12', '"\\uZZZZ', '"abc\\"', '"line\nbreak']
)

# ---------- recursive structure ----------

json_value = st.deferred(lambda: _value)

def _value():
    return st.one_of(
        json_string(),
        json_number_strategy,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        json_obj(),
        json_arr(),
        # malformed near-valid leaves
        malformed_number,
        unterminated_string,
    )

def _pair():
    return st.tuples(json_string(), st.just(":"), json_value).map("".join)

# malformed pairs (missing colon, double colon, etc.)
def _bad_pair():
    return st.one_of(
        st.tuples(json_string(), json_value).map("".join),          # missing colon
        st.tuples(json_string(), st.just("::"), json_value).map("".join),
        st.tuples(json_string(), st.just(":"), st.just(","), json_value).map("".join),
        st.tuples(json_string(), st.just(":"), json_value, json_value).map("".join),
    )

def _obj_members():
    return st.lists(
        st.one_of(_pair(), _bad_pair()),
        min_size=1,
        max_size=6,
    )

def _obj_body():
    members = _obj_members()
    # build: "{" + ",".join(members) + optional trailing comma + "}"
    def build(ms):
        inner = ",".join(ms)
        trailing = st.booleans()
        return inner, trailing
    return st.tuples(members, st.booleans()).map(
        lambda mt: "{" + ",".join(mt[0]) + ("," if mt[1] else "") + "}"
    )

def _arr_values():
    return st.lists(json_value, min_size=1, max_size=6)

def _arr_body():
    return st.tuples(_arr_values(), st.booleans()).map(
        lambda vt: "[" + ",".join(vt[0]) + ("," if vt[1] else "") + "]"
    )

def json_obj():
    return st.one_of(
        st.just("{}"),
        st.just("{,}"),
        st.just("{:}"),
        st.just('{"a"}'),
        st.just('{"a":}'),
        _obj_body(),
    )

def json_arr():
    return st.one_of(
        st.just("[]"),
        st.just("[,]"),
        st.just("[1,,2]"),
        st.just("[,1]"),
        _arr_body(),
    )

# ---------- deep nesting ----------

def _deep_obj_chain():
    # nested objects to stress first-pass memory measurement
    return st.integers(min_value=1, max_value=2000).map(
        lambda n: "{" + '"k":' * n + "0" + "}" * n
    )

def _deep_arr_chain():
    return st.integers(min_value=1, max_value=5000).map(
        lambda n: "[" * n + "0" + "]" * n
    )

def _deep_mixed_chain():
    def build(n):
        parts = []
        for i in range(n):
            parts.append("{" + '"a":' if i % 2 == 0 else "[")
        parts.append("null")
        for i in reversed(range(n)):
            parts.append("}" if i % 2 == 0 else "]")
        return "".join(parts)
    return st.integers(min_value=1, max_value=1000).map(build)

deep_nesting = st.one_of(_deep_obj_chain(), _deep_arr_chain(), _deep_mixed_chain())

# ---------- top-level value with optional trailing garbage / whitespace ----------

def _ws():
    return st.lists(st.sampled_from([" ", "\t", "\n", "\r"]), max_size=4).map("".join)

trailing_garbage = st.sampled_from(
    ["1abc", "[]xyz", "1 garbage", "true false", "nullnull", "{} {}", "]\x00", "1\x00"]
)

# ---------- recursive strategy assembly ----------

# Use st.recursive for obj/arr/value so the structure is genuinely recursive.
# Base cases: primitives + malformed leaves. Recursive: obj/arr built from value.
base = st.one_of(
    json_string(),
    json_number_strategy,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    malformed_number,
    unterminated_string,
    st.just("{}"),
    st.just("[]"),
    st.just("{,}"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    deep_nesting,
    trailing_garbage,
)

def _extend(children):
    # children is a strategy producing json value strings
    def make_obj(v):
        # object with members (biased)
        def build(ms):
            return "{" + ",".join(ms) + "}"
        return st.lists(
            st.tuples(json_string(), st.just(":"), v).map("".join),
            min_size=1,
            max_size=5,
        ).map(build)

    def make_arr(v):
        return st.lists(v, min_size=1, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]")

    return st.one_of(make_obj(children), make_arr(children))

recursive_value = st.recursive(base, _extend, max_leaves=30)

# ---------- bias toward valid JSON ----------

def _valid_value():
    return st.one_of(
        json_string(),
        json_number_strategy,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _valid_obj(),
        _valid_arr(),
    )

def _valid_obj():
    return st.lists(
        st.tuples(json_string(), st.just(":"), _valid_value()).map("".join),
        min_size=0,
        max_size=6,
    ).map(lambda ms: "{" + ",".join(ms) + "}")

def _valid_arr():
    return st.lists(
        _valid_value(),
        min_size=0,
        max_size=6,
    ).map(lambda xs: "[" + ",".join(xs) + "]")

valid_value = st.recursive(
    st.one_of(
        json_string(),
        json_number_strategy,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ),
    lambda children: st.one_of(
        st.lists(
            st.tuples(json_string(), st.just(":"), children).map("".join),
            min_size=0,
            max_size=5,
        ).map(lambda ms: "{" + ",".join(ms) + "}"),
        st.lists(children, min_size=0, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]"),
    ),
    max_leaves=30,
)

# ---------- near-crash intensification ----------
# Crash signature: ubsan:applying-non-zero-offset-to-null-pointer in the parse
# function. This typically fires when an offset is added to a NULL base pointer,
# which happens when the parser walks a container (obj/arr) whose inner value
# pointer is NULL. Mutate structurally around such shapes: empty/missing inner
# values, NULL-offset-inducing offsets (leading commas, empty members), and
# deeply nested containers with empty innermost content.

def _near_crash_mutations():
    # empty / missing inner value inside containers -> NULL inner pointer
    empty_inner = st.sampled_from(
        [
            '{"a":}', '{"a"::}', '{"a" : }', '{"a":,}', '{"a":,"b":1}',
            '{:"a"}', '{,"a":1}', '{:"a",}', '{"a"::"b"}',
            '[,]', '[,1]', '[1,]', '[,]', '[,1,]', '[,,]', '[,,1]',
            '[1,,]', '[[,]]', '{"a":[,]}', '[{"a":}]', '{"a":[]}',
            '{"a":{}}', '[{}]', '[[]]', '{"a":[[]]}', '[[{}]]',
            '{"a":[{"b":}]}', '[{"a":[{}]}]',
        ]
    )
    # leading-comma / offset-heavy shapes (offset applied to NULL base)
    offset_shapes = st.integers(min_value=1, max_value=64).map(
        lambda n: "[" * n + "," + "]" * n
    )
    offset_shapes_obj = st.integers(min_value=1, max_value=64).map(
        lambda n: "{" + '"a":' * n + "," + "}" * n
    )
    # deep nesting ending in an empty value -> inner NULL after deep walk
    deep_empty = st.integers(min_value=1, max_value=2048).map(
        lambda n: "[" * n + "," + "]" * n
    )
    deep_empty_obj = st.integers(min_value=1, max_value=2048).map(
        lambda n: "{" + '"k":' * n + "," + "}" * n
    )
    # NUL / control bytes near structural boundaries
    nul_boundary = st.sampled_from(
        [
            '{"a":\x00}', '[\x00]', '[,]\x00', '{"a":}\x00', '\x00{}',
            '{"a":\x00:1}', '[1,\x00]', '{\x00:"a"}', '["\x00"]',
            '{"\x00":1}', '[\x00,]', '{,}\x00', '[,]\x00',
        ]
    )
    # whitespace-padded empty containers (offset arithmetic on empty)
    ws_empty = st.sampled_from(
        [
            '{"a": }', '[ ]', '{ }', '{"a":\t}', '[\n]', '{\r}',
            '{"a" : }', '{"a":, }', '[ , ]', '{ , }',
        ]
    )
    # trailing-garbage right after empty inner value
    trailing_after_empty = st.sampled_from(
        [
            '{"a":}x', '[,]x', '{"a":}[', '[,]{', '{"a":}]', '[,]}',
            '{"a":}\x00', '[,]\x00', '{"a":}1', '[,]1',
        ]
    )
    # Intensification directly on the observed crashing shape —
    # offset applied to a NULL inner value pointer. Combine the empty-inner
    # container with varying amounts of leading offset (leading commas, empty
    # members, empty array values) so the parser's offset arithmetic lands on
    # a NULL base. Also mix in lone '-' (the second divergence example) inside
    # the empty slot, and pad with whitespace/NUL to shift offsets.
    lone_minus_inner = st.sampled_from(
        [
            '{"a":-}', '{"a":- ,}', '[ - ]', '[-]', '{"a":[-]}', '[-,"a"]',
            '[-,]', '[, -]', '{"a":-,}', '{"-":-}', '[-]', '{"a":[-]}',
            '[[-]]', '{"a":[-]}', '[-,,]', '[,-]', '{"a":-,"b":-}',
        ]
    )
    def _offset_empty(n):
        # n leading commas before an empty slot, then closing bracket(s)
        return "[" * n + "," * n + "]" * n
    offset_empty_lead = st.integers(min_value=1, max_value=128).map(_offset_empty)
    def _offset_empty_obj(n):
        return "{" + ('"a":,' * n) + "}" * n
    offset_empty_obj_lead = st.integers(min_value=1, max_value=128).map(_offset_empty_obj)
    # empty container with leading offset then a lone '-' value (NULL + offset)
    def _offset_lone_minus(n):
        return "[" * n + "," * n + "-" + "]" * n
    offset_lone_minus = st.integers(min_value=1, max_value=128).map(_offset_lone_minus)
    # whitespace / NUL padding around empty inner to perturb offset arithmetic
    padded_empty = st.sampled_from(
        [
            '{"a": }', '{"a":\t}', '{"a":\n}', '{"a":\r}', '{"a":\x00}',
            '[ ]', '[\t]', '[\n]', '[\r]', '[\x00]',
            '{"a": , }', '{"a":\x00,}', '[\x00,]', '[,\x00]',
            '{"a":\x00,\x00}', '[\x00,\x00]',
        ]
    )
    # combine empty-inner container with leading offset both inside and out
    def _nested_offset_empty(n):
        return "[" * n + "{" + '"a":' * n + "," + "}" * n + "]" * n
    nested_offset_empty = st.integers(min_value=1, max_value=64).map(_nested_offset_empty)

    # NEW intensification: combined offset + empty-inner + lone '-' + NUL/ws,
    # plus mixed obj/arr offset chains and inner-NULL containers wrapped with
    # offset prefixes and suffixes, and trailing offset after empty inner.
    def _offset_lone_minus_obj(n):
        return "{" + ('"a":,' * n) + "-" + "}" * n
    offset_lone_minus_obj = st.integers(min_value=1, max_value=128).map(_offset_lone_minus_obj)

    def _mixed_offset_empty(n):
        # alternating [ { with commas, empty innermost, then closers
        opens = []
        for i in range(n):
            opens.append("[" if i % 2 == 0 else "{")
        inner = "," * n
        closes = []
        for i in reversed(range(n)):
            closes.append("]" if i % 2 == 0 else "}")
        return "".join(opens) + inner + "".join(closes)
    mixed_offset_empty = st.integers(min_value=1, max_value=96).map(_mixed_offset_empty)

    def _offset_empty_trailing(n):
        # empty inner slot followed by n trailing commas before close
        return "[" + "," * n + "]" + "," * n
    offset_empty_trailing = st.integers(min_value=1, max_value=128).map(_offset_empty_trailing)

    def _offset_empty_obj_trailing(n):
        return "{" + ('"a":,' * n) + "}" + "," * n
    offset_empty_obj_trailing = st.integers(min_value=1, max_value=128).map(_offset_empty_obj_trailing)

    combined_offset_empty = st.sampled_from(
        [
            '[-,]', '[,-]', '[,,]', '[,,,]', '[,1,]', '[1,,]',
            '{"a":,}', '{"a":,,}', '{"a":-,"b":,}', '{"a":,"b":-}',
            '{"a":\x00}', '{"a":\x00,}', '[,\x00,]', '[\x00,,]',
            '{"a": }', '{"a":- }', '[ -]', '[- ]', '[ , ]', '{ , }',
            '[{"a":,}]', '{"a":[,]}', '[[,],]', '[,[,]]',
            '{"a":-,"b":1}', '{"a":1,"b":-}', '[-,,]', '[,-,]',
            '{"a":[-,]}', '{"a":[,,-]}', '[[-],]', '[,[-]]',
            '{"a":\x00-}', '[-\x00]', '[\x00-]', '{"a":-\x00}',
            '[-,]\x00', '\x00[-,]', '{"a":,}\x00', '\x00{"a":,}',
        ]
    )
    def _offset_lone_minus_ws(n):
        return "[" * n + (" ," * n) + "-" + "]" * n
    offset_lone_minus_ws = st.integers(min_value=1, max_value=64).map(_offset_lone_minus_ws)
    def _offset_empty_ws(n):
        return "[" * n + (" ," * n) + "]" * n
    offset_empty_ws = st.integers(min_value=1, max_value=64).map(_offset_empty_ws)
    def _offset_empty_nul(n):
        return "[" * n + (",\x00" * n) + "]" * n
    offset_empty_nul = st.integers(min_value=1, max_value=64).map(_offset_empty_nul)

    return st.one_of(
        empty_inner,
        offset_shapes,
        offset_shapes_obj,
        deep_empty,
        deep_empty_obj,
        nul_boundary,
        ws_empty,
        trailing_after_empty,
        lone_minus_inner,
        offset_empty_lead,
        offset_empty_obj_lead,
        offset_lone_minus,
        padded_empty,
        nested_offset_empty,
        offset_lone_minus_obj,
        mixed_offset_empty,
        offset_empty_trailing,
        offset_empty_obj_trailing,
        combined_offset_empty,
        offset_lone_minus_ws,
        offset_empty_ws,
        offset_empty_nul,
    )

near_crash = _near_crash_mutations()

def _top_level(v):
    return st.one_of(
        # mostly valid JSON
        valid_value,
        st.tuples(_ws(), valid_value, _ws()).map("".join),
        # occasional malformed / edge cases
        v,
        st.lists(
            st.tuples(json_string(), st.just(":"), v).map("".join),
            min_size=1,
            max_size=6,
        ).map(lambda ms: "{" + ",".join(ms) + "}"),
        st.tuples(v, trailing_garbage).map("".join),
        # intensified structural mutations around the crashing input
        near_crash,
    )

strategy = _top_level(recursive_value)
```