from hypothesis import strategies as st
import json

# ---------- leaf generators ----------

# Safe printable characters (no quote, no backslash, no control).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _unicode_escape():
    return st.builds(
        lambda h: "\\u" + "".join(h),
        st.lists(_hex, min_size=4, max_size=4),
    )

def _surrogate_escape():
    return st.builds(
        lambda h: "\\u" + "".join(h),
        st.lists(st.sampled_from("dD"), min_size=1, max_size=1)
        .flatmap(lambda d: st.lists(
            st.one_of(
                st.sampled_from("89abAB"),
                _hex,
            ), min_size=3, max_size=3))
    )

# A string body piece: either a safe char, an escape, a unicode escape,
# a surrogate escape, or a raw control/NUL byte (allowed by the harness).
_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_control_byte = st.sampled_from(
    [chr(i) for i in range(0x00, 0x20)]
)

_string_piece = st.one_of(
    _safe_chars,
    _escape,
    _unicode_escape(),
    _surrogate_escape(),
    _control_byte,
)

def _quoted_string():
    return st.builds(
        lambda pieces: '"' + "".join(pieces) + '"',
        st.lists(_string_piece, min_size=0, max_size=8),
    )

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text(alphabet="123456789", min_size=1, max_size=1).flatmap(
    lambda first: st.builds(lambda rest: first + rest,
                            st.text(alphabet="0123456789", min_size=0, max_size=5))
)

_int_part = st.one_of(st.just("0"), _nonzero_digits)

_frac_part = st.builds(lambda d: "." + d, _digits)

_exp_part = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _digits,
)

def _number():
    return st.builds(
        lambda sign, ip, fp, ep: sign + ip + fp + ep,
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac_part),
        st.one_of(st.just(""), _exp_part),
    )

# Extreme magnitudes / overflow / special accepted-lenient forms.
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e9999", "-1e9999",
    "1E+308", "1e+308", "1e308", "1e-308",
    "0e0", "0E0", "0e+0", "0e-0",
    "-0", "-0.0", "-0e0",
    "1" + "0" * 300,
    "1." + "0" * 300,
    "1e" + "0" * 300,
    "9" * 17,
    "123456789012345678901234567890",
    "1.7976931348623157e308",
    "5e-324",
    "2.2250738585072014e-308",
    # lone minus is accepted by the parser
    "-",
])

# Malformed-ish number forms (near valid but rejected by strict grammar).
_malformed_number = st.sampled_from([
    "+1", ".5", "1.", "01", "0x1F", "1e", "1e+", "1e-", "--1",
    "1..2", "1.2.3", "+.5", "-.5", "007", "1_000",
])

_number_any = st.one_of(_number(), _extreme_number, _malformed_number)

# ---------- recursion for values ----------

_json_value = st.deferred(lambda: _value)

def _obj(depth):
    # Bias toward objects with members.
    empty = st.just("{}")
    members = st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(_pair(depth), min_size=1, max_size=6),
    )
    trailing = st.builds(
        lambda pairs: "{" + ",".join(pairs) + ",}",
        st.lists(_pair(depth), min_size=1, max_size=4),
    )
    return st.one_of(members, trailing, empty)

def _arr(depth):
    empty = st.just("[]")
    items = st.builds(
        lambda vals: "[" + ",".join(vals) + "]",
        st.lists(_value_at(depth), min_size=1, max_size=6),
    )
    trailing = st.builds(
        lambda vals: "[" + ",".join(vals) + ",]",
        st.lists(_value_at(depth), min_size=1, max_size=4),
    )
    return st.one_of(items, trailing, empty)

def _pair(depth):
    # Duplicate keys naturally arise from random strings; also force some.
    dup = st.builds(
        lambda k, v: '"' + k + '":' + v,
        st.sampled_from(["a", "a", "key", "key", "x", ""]),
        _value_at(depth),
    )
    normal = st.builds(
        lambda k, v: k + ":" + v,
        _quoted_string(),
        _value_at(depth),
    )
    return st.one_of(normal, dup)

def _value_at(depth):
    if depth <= 0:
        return st.one_of(_quoted_string(), _number_any,
                         st.sampled_from(["true", "false", "null"]))
    return st.one_of(
        _quoted_string(),
        _number_any,
        st.sampled_from(["true", "false", "null"]),
        _obj(depth - 1),
        _arr(depth - 1),
    )

_value = st.one_of(
    _quoted_string(),
    _number_any,
    st.sampled_from(["true", "false", "null"]),
    _obj(3),
    _arr(3),
)

# ---------- deep nesting (no recursion cap in parser) ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=64)
    # Deep object nesting with a member at each level (stresses first pass).
    deep_obj = depth.flatmap(
        lambda d: st.builds(
            lambda inner: "{" + '"k":' * d + inner + "}" * d,
            st.one_of(st.just("1"), st.just("null"), st.just('"x"')),
        )
    )
    deep_arr = depth.flatmap(
        lambda d: st.builds(
            lambda inner: "[" * d + inner + "]" * d,
            st.one_of(st.just("1"), st.just("null"), st.just('"x"')),
        )
    )
    return st.one_of(deep_obj, deep_arr)

# ---------- malformed / near-valid inputs ----------

_malformed = st.sampled_from([
    "[1,,2]", "[,]", "[,1]", "{,}", '{"a":1,,}',
    '{"a" 1}', '{"a":}', '{:1}', '{"a":1 "b":2}',
    '"unterminated', '{"a":"unterminated}',
    "[1,2", '{"a":1', "[1 2]", "{a:1}", "'x'",
    "1abc", "[]xyz", "1 garbage", "true false",
    "//x", "/* */1", "{}extra", "[][]",
    '{"a":1}{"b":2}', '"a" "b"',
    "[}", "{]", "[1,2}}", '{"a":1]]',
    "tru", "fals", "nul", "TRUE", "Null",
    '"\\x"', '"\\u12"', '"\\uZZZZ"', '"\\u"',
    "[", "]", "{", "}", ":", ",",
    "\x00", '"\x00"', '{"\x00":1}', "[\x00]",
])

# ---------- intensified near-crash mutations ----------

# Base crashing input: deeply nested objects with a member at each level.
# Structurally mutate around it: inject malformed tokens, truncate, splice
# siblings, and perturb the leaf so the parser walks near the crash path.
_NEAR_CRASH_BASE = "{" + '"k":' * 32 + "1" + "}" * 32

def _near_crash():
    depth = st.integers(min_value=1, max_value=64)
    leaf = st.sampled_from(["1", "null", '"x"', "", "1e309", "-"])
    # Build the deep skeleton, then structurally mutate around the crash point.
    skeleton = st.builds(
        lambda d, lf: "{" + '"k":' * d + lf + "}" * d,
        depth,
        leaf,
    )
    # Truncate: drop trailing closers (unbalanced deep nesting).
    truncated = skeleton.flatmap(
        lambda s: st.builds(
            lambda cut: s[:len(s) - cut] if cut < len(s) else s,
            st.integers(min_value=1, max_value=16),
        )
    )
    # Splice siblings at the deepest point (sibling key/value confusion).
    spliced = skeleton.flatmap(
        lambda s: st.builds(
            lambda inj: s[: len(s) // 2] + inj + s[len(s) // 2:],
            st.sampled_from([
                '"k":', '"k"', ":", ",", "{", "}", "[", "]",
                '"k":1,', ",", '"k":',
            ]),
        )
    )
    # Reorder: move a closer to the front to desync nesting counts.
    reordered = skeleton.flatmap(
        lambda s: st.builds(
            lambda n: s[n:] + s[:n] if n < len(s) else s,
            st.integers(min_value=1, max_value=8),
        )
    )
    # Duplicate the deep prefix to double the parse depth abruptly.
    doubled = skeleton.flatmap(
        lambda s: st.builds(
            lambda mid: s[: mid] + s + s[mid:] if mid < len(s) else s + s,
            st.integers(min_value=0, max_value=64),
        )
    )
    # Intensified structural mutation: many simultaneous edits around the
    # crash point. Interleave key/value token swaps, drop closers, inject
    # unmatched brackets, and reorder segments to maximize desync of the
    # parser's nesting counters near the deep prefix.
    def _intensify(s):
        n = len(s)
        return st.builds(
            lambda swaps, cuts, injs, rot, pre: _apply_mutations(
                s, swaps, cuts, injs, rot, pre
            ),
            st.lists(
                st.tuples(
                    st.integers(min_value=0, max_value=max(n, 1)),
                    st.sampled_from([
                        '"k":', '"k"', ":", ",", "1", "null", "", "{",
                        "}", "[", "]",
                    ]),
                ),
                min_size=1,
                max_size=8,
            ),
            st.lists(
                st.integers(min_value=1, max_value=8),
                min_size=0,
                max_size=6,
            ),
            st.lists(
                st.sampled_from([
                    '"k":', '"k"', ":", ",", "{", "}", "[", "]", "1",
                ]),
                min_size=0,
                max_size=6,
            ),
            st.integers(min_value=0, max_value=max(n, 1)),
            st.sampled_from([
                "", '"k":', '"k"', "{", "[", ",", "1",
            ]),
        )

    intensified = skeleton.flatmap(_intensify)

    # Direct mutations of the canonical crashing input.
    direct = st.sampled_from([
        _NEAR_CRASH_BASE,
        _NEAR_CRASH_BASE[:-1],
        _NEAR_CRASH_BASE + "}",
        _NEAR_CRASH_BASE + "{",
        _NEAR_CRASH_BASE + ",",
        _NEAR_CRASH_BASE.replace('"k":', '"k":', 1),
        _NEAR_CRASH_BASE[: len(_NEAR_CRASH_BASE) // 2],
        _NEAR_CRASH_BASE[: len(_NEAR_CRASH_BASE) // 2] + '"k":1',
        "{" + '"k":' * 64 + "1" + "}" * 63,
        "{" + '"k":' * 64 + "1" + "}" * 65,
        "[" * 32 + "1" + "]" * 32,
        "[" * 32 + "1" + "]" * 31,
        "[" * 64 + "1" + "]" * 64,
    ])
    return st.one_of(
        skeleton, truncated, spliced, reordered, doubled,
        intensified, direct,
    )

def _apply_mutations(s, swaps, cuts, injs, rot, pre):
    # Apply index-based token swaps (structural sibling/key confusion).
    out = s
    for idx, tok in swaps:
        i = idx % (len(out) + 1)
        out = out[:i] + tok + out[i:]
    # Truncate trailing characters (unbalanced closers).
    for cut in cuts:
        if cut < len(out):
            out = out[: len(out) - cut]
    # Inject unmatched brackets / tokens at the front.
    for tok in injs:
        out = tok + out
    # Rotate to desync nesting-count bookkeeping.
    if out and rot:
        r = rot % len(out)
        out = out[r:] + out[:r]
    # Prepend a prefix to shift the first-pass depth accounting.
    return pre + out

# ---------- top-level strategy ----------

def _top():
    return st.one_of(
        _value,
        _deep_nesting(),
        _near_crash(),
        _malformed,
        st.just(""),
        st.just(" "),
        st.just("\x00"),
        st.just('{"a":1,"a":2}'),
        st.just("[1,2,]"),
        st.just('{"a":1,}'),
        st.just("1e309"),
        st.just("-"),
    )

strategy = _top()