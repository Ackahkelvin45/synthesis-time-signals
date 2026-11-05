```python
from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4().map(lambda h: "\\u" + h),
    # surrogate escapes (some lone -> rejected, some paired -> ok)
    _hex4().map(lambda h: "\\u" + h),  # includes D800-DFFF range via hex
    st.sampled_from(["\\ud800", "\\udfff", "\\uD834", "\\uDD1E", "\\u0000"]),
)

# safe codepoints: printable ASCII minus " and backslash
_safe = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
).map(lambda c: c)

# raw control bytes / NUL allowed inside strings by this parser
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

# unicode printable non-ascii
_unicode_char = st.characters(min_codepoint=0x80, max_codepoint=0x2FFF)

_str_piece = st.one_of(_safe, _escapes, _raw_control, _unicode_char)

# a well-formed-ish string body (may include raw controls / escapes)
_string_body = st.lists(_str_piece, min_size=0, max_size=8).map(lambda xs: "".join(xs))

def _quoted(body):
    return '"' + body + '"'

_valid_string = _string_body.map(_quoted)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.just("00"),
    st.just("01"),
    st.just("007"),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
    st.just("."),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=10**4).map(str),
    ).map(lambda t: "".join(t)),
    st.sampled_from(["e309", "E309", "e-309", "e999", "e308", "e+00", "e01"]),
)

_sign = st.one_of(st.just(""), st.just("-"))

_valid_number = st.tuples(_sign, _int_part, _frac, _exp).map(lambda t: "".join(t))

# malformed numbers the parser rejects
_bad_number = st.sampled_from([
    "-", "+1", ".5", "-.5", "+", "1.2.3", "--1", "1e", "1e+", "0x", "1..2",
])

_number = st.one_of(_valid_number, _bad_number)

# ---------- literals ----------

_literal = st.one_of(
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------- whitespace ----------

_ws = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", "\x00"]),
).map(str)

# ---------- recursive structure ----------

_json_string = st.one_of(_valid_string, _literal, _number)

def _make_obj(pairs):
    # pairs: list of (key, val) strings
    if not pairs:
        return "{}"
    inner = ",".join(k + ":" + v for (k, v) in pairs)
    return "{" + inner + "}"

def _make_arr(items):
    if not items:
        return "[]"
    return "[" + ",".join(items) + "]"

# composite for objects: key string + value
_pair = st.tuples(_valid_string, _json_string).map(lambda t: (t[0], t[1]))

_obj = st.lists(_pair, min_size=0, max_size=6).map(_make_obj)

_arr = st.lists(_json_string, min_size=0, max_size=6).map(_make_arr)

# malformed object/array variants
_bad_obj = st.one_of(
    st.just("{"),
    st.just("}"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{"a":1,}'),
    st.just('{"a":1,,}'),
    st.just('{a:1}'),
    st.just("{'a':1}"),
    st.just('{"a":1'),
    st.just('{"a" : 1 , }'),
)

_bad_arr = st.one_of(
    st.just("["),
    st.just("]"),
    st.just("[1,]"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just("[1"),
    st.just("[1 2]"),
)

# ---------- deep nesting near the ~1000 limit ----------

def _deep(depth, kind):
    if kind == "arr":
        return "[" * depth + "]" * depth
    else:
        return '{"a":' * depth + "1" + "}" * depth

_deep_nesting = st.one_of(
    st.integers(min_value=990, max_value=1002).map(lambda d: _deep(d, "arr")),
    st.integers(min_value=990, max_value=1002).map(lambda d: _deep(d, "obj")),
    st.integers(min_value=0, max_value=1000).map(lambda d: _deep(d, "arr")),
)

# ---------- top level ----------

# recursive JSON value
_json_value = st.recursive(
    _json_string,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=6).map(_make_arr),
        st.lists(
            st.tuples(_valid_string, children), min_size=0, max_size=6
        ).map(_make_obj),
    ),
    max_leaves=20,
)

# malformed top-level fragments
_bad_toplevel = st.one_of(
    _bad_number,
    _bad_obj,
    _bad_arr,
    st.just(""),
    st.just("   "),
    st.just('"unterminated'),
    st.just("'single'"),
    st.just("tru"),
    st.just("nul"),
    st.just("fals"),
    st.just('"\\x41"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just("\x00"),
    st.just("\ufeff"),
    st.just("[]extra"),
    st.just("1abc"),
)

# BOM prefix
_bom = st.one_of(st.just(""), st.just("\ufeff"))

# trailing content (accepted, ignored)
_trailer = st.one_of(
    st.just(""),
    st.just(" \n\t "),
    st.just(" garbage"),
    st.just("\x00"),
    st.just("1 2"),
    st.just("abc"),
)

def _wrap(v):
    return _bom + v + _trailer

_toplevel_valid = st.tuples(_bom, _json_value, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_deep = st.tuples(_bom, _deep_nesting, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_bad = st.tuples(_bom, _bad_toplevel, _trailer).map(lambda t: t[0] + t[1] + t[2])

# also a few raw string-only candidates (top-level strings)
_toplevel_string = st.tuples(_bom, _valid_string, _trailer).map(lambda t: "".join(t))

# ---------- improved: structured mutations of valid documents ----------

def _mutate(s):
    # apply a small random-ish deterministic mutation to a valid JSON text
    n = len(s)
    if n == 0:
        return s
    ops = [
        lambda x: x[:-1],                              # truncate
        lambda x: x[: len(x) // 2],                    # cut in half
        lambda x: x + x[:1],                           # duplicate first char
        lambda x: x.replace(",", ",,", 1),             # dup comma
        lambda x: x.replace(":", "::", 1),             # dup colon
        lambda x: x.replace('"', "", 1),               # drop a quote
        lambda x: x.replace("]", "", 1),               # drop a bracket
        lambda x: x.replace("{", "", 1),               # drop a brace
        lambda x: " " + x,                             # leading space
        lambda x: x + " ",                             # trailing space
    ]
    # pick op based on a hash of content (stable, no randomness import)
    idx = sum(ord(c) for c in s) % len(ops)
    return ops[idx](s)

_toplevel_mutated = st.tuples(_bom, _json_value, _trailer).map(
    lambda t: t[0] + _mutate(t[1]) + t[2]
)

# concatenations of two valid values (top-level trailing garbage that parses)
_toplevel_concat = st.tuples(_bom, _json_value, _json_value).map(
    lambda t: t[0] + t[1] + " " + t[2]
)

# ---------- improved: multi-mutation fuzzing of valid documents ----------

def _apply_mutations(s, count):
    ops = [
        lambda x: x[:-1],
        lambda x: x[: len(x) // 2],
        lambda x: x + x[:1],
        lambda x: x.replace(",", ",,", 1),
        lambda x: x.replace(":", "::", 1),
        lambda x: x.replace('"', "", 1),
        lambda x: x.replace("]", "", 1),
        lambda x: x.replace("{", "", 1),
        lambda x: x.replace("[", "", 1),
        lambda x: x.replace("}", "", 1),
        lambda x: x.replace(" ", "", 1),
        lambda x: x + " ",
        lambda x: " " + x,
        lambda x: x.replace("e", "E", 1),
        lambda x: x.replace("E", "e", 1),
        lambda x: x.replace("0", "00", 1),
        lambda x: x.replace("-", "--", 1),
        lambda x: x.replace("\\", "\\\\", 1),
        lambda x: x.replace("t", "T", 1),
        lambda x: x.replace("n", "N", 1),
    ]
    for i in range(count):
        if not s:
            break
        # deterministic but varied selection
        idx = (sum(ord(c) for c in s) + i * 7) % len(ops)
        s = ops[idx](s)
    return s

_toplevel_multi_mutated = st.tuples(
    _bom,
    _json_value,
    st.integers(min_value=1, max_value=5),
    _trailer,
).map(lambda t: t[0] + _apply_mutations(t[1], t[2]) + t[3])

# ---------- improved: whitespace-injection around structural tokens ----------

_ws_opt = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", "\x00", "\x0b", "\x0c"]),
)

def _wsify(tokens):
    # tokens: list of literal pieces; interleave optional whitespace between them
    if not tokens:
        return ""
    return tokens[0] + "".join(tokens[i] for i in range(1, len(tokens)))

def _make_obj_ws(pairs):
    if not pairs:
        return "{" + " " + "}"
    parts = []
    for (k, v) in pairs:
        parts.append(k + ":" + v)
    return "{" + ",".join(parts) + "}"

def _make_arr_ws(items):
    if not items:
        return "[" + " " + "]"
    return "[" + ",".join(items) + "]"

# whitespace-heavy recursive value
_json_value_ws = st.recursive(
    _json_string,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=6).map(_make_arr_ws),
        st.lists(
            st.tuples(_valid_string, children), min_size=0, max_size=6
        ).map(_make_obj_ws),
    ),
    max_leaves=15,
)

_toplevel_ws = st.tuples(
    _bom,
    _ws_opt,
    _json_value_ws,
    _ws_opt,
    _trailer,
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

# ---------- improved: escape-heavy and unicode-heavy strings at top level ----------

_escape_heavy_body = st.lists(
    st.one_of(
        _escapes,
        st.sampled_from(["\\u0000", "\\u001f", "\\uffff", "\\uD800\\uDC00", "\\ud800\\udc00"]),
        _safe,
    ),
    min_size=0,
    max_size=16,
).map(lambda xs: "".join(xs))

_toplevel_escape_heavy = st.tuples(
    _bom,
    _escape_heavy_body.map(_quoted),
    _trailer,
).map(lambda t: t[0] + t[1] + t[2])

# ---------- improved: number edge cases at top level ----------

_num_edge = st.sampled_from([
    "0", "-0", "0.0", "-0.0", "1e308", "1e309", "-1e309",
    "1.7976931348623157e308", "2.2250738585072014e-308",
    "123456789012345678901234567890", "1e-999", "1E+999",
    "-1.0e-0", "0e0", "0e-0", "1e0000", "1.0E+00",
])

_toplevel_num_edge = st.tuples(_bom, _num_edge, _trailer).map(
    lambda t: t[0] + t[1] + t[2]
)

# ---------- improved: byte-level random fuzzing of valid docs ----------

def _byte_flip(s, pos, ch):
    if not s:
        return ch
    p = pos % len(s)
    return s[:p] + ch + s[p + 1:]

_interesting_chars = st.sampled_from(
    ['"', "\\", "{", "}", "[", "]", ",", ":", " ", "\x00", "\n", "\t", "-", "e", "E", ".", "0", "1", "t", "f", "n"]
)

_toplevel_byteflip = st.tuples(
    _bom,
    _json_value,
    st.integers(min_value=0, max_value=10**6),
    _interesting_chars,
    _trailer,
).map(lambda t: t[0] + _byte_flip(t[1], t[2], t[3]) + t[4])

strategy = st.one_of(
    _toplevel_valid,
    _toplevel_deep,
    _toplevel_bad,
    _toplevel_string,
    _toplevel_mutated,
    _toplevel_concat,
    _toplevel_multi_mutated,
    _toplevel_ws,
    _toplevel_escape_heavy,
    _toplevel_num_edge,
    _toplevel_byteflip,
)
```