from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

# Safe string bodies (no quotes/backslash/control) for keys
_key_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

_keys = st.one_of(
    st.just(""),
    st.text(_key_chars, min_size=1, max_size=12),
    # duplicate-key bait: small alphabet
    st.text(alphabet="ab", min_size=1, max_size=4),
)

# String content pieces, including escapes, unicode escapes, surrogates,
# control bytes and NUL, all wrapped so they form valid JSON strings.
_escape_pieces = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u0001", "\\u001f", "\\u007f", "\\u00e9", "\\u20ac",
    "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF", "\\uD83D\\uDE00",
    "\\uFFFF", "\\uFFFE", "\\u0000\\u0000",
])

_control_pieces = st.sampled_from([
    "\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\x7f",
])

_safe_pieces = st.text(_key_chars, min_size=0, max_size=8)

_string_piece = st.one_of(_safe_pieces, _escape_pieces, _control_pieces)


@st.composite
def _json_string(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    body = "".join(draw(_string_piece) for _ in range(n))
    return '"' + body + '"'


# ---------- number strategies ----------

_int_part = st.one_of(
    st.just("0"),
    st.from_regex(r"[1-9][0-9]{0,18}", fullmatch=True),
)

_frac_part = st.one_of(
    st.just(""),
    st.from_regex(r"\.[0-9]{1,18}", fullmatch=True),
)

_exp_part = st.one_of(
    st.just(""),
    st.from_regex(r"[eE][+-]?[0-9]{1,4}", fullmatch=True),
    # extreme exponents / overflow
    st.sampled_from(["e309", "e-309", "E308", "e999999", "e-999999",
                     "e+308", "e+309", "E-400"]),
)

_number = st.builds(
    lambda sign, ip, fp, ep: sign + ip + fp + ep,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    _frac_part,
    _exp_part,
)

# non-finite / extreme magnitudes
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "-1e308", "1e-309", "1e-324", "1e400",
    "0e0", "-0", "-0.0", "0.0", "1234567890123456789",
    "-123456789012345678901234567890", "1e+999999", "1e-999999",
    "9" * 40, "0." + "0" * 30 + "1",
])

# malformed number forms (parser rejects, but valuable)
_bad_number = st.sampled_from([
    "+1", "+0", ".5", "-.5", "1.", "01", "007", "-01", "0x1F",
    "1_000", "1e", "1e+", "1e-", "--1", "1..2", "1e1.5",
    "-",  # lone minus: accepted by parser, still edge
    "00", "0e", "Infinity", "NaN", "-Infinity",
])

_number_all = st.one_of(_number, _extreme_number, _bad_number)


# ---------- recursive value ----------

_json_value = st.recursive(
    st.one_of(
        _json_string(),
        _number_all,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        # arrays
        st.builds(
            lambda items: "[" + ",".join(items) + "]",
            st.lists(children, min_size=0, max_size=6),
        ),
        # trailing comma array
        st.builds(
            lambda items: "[" + ",".join(items) + ",]" if items else "[,]",
            st.lists(children, min_size=0, max_size=5),
        ),
        # objects (biased: usually non-empty)
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _json_string(),
                    children,
                ),
                min_size=1,
                max_size=6,
            ),
        ),
        # empty object
        st.just("{}"),
        # trailing comma object
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + ",}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _json_string(),
                    children,
                ),
                min_size=1,
                max_size=5,
            ),
        ),
    ),
    max_leaves=40,
)


# ---------- deep nesting ----------

@st.composite
def _deep_nesting(draw):
    depth = draw(st.integers(min_value=1, max_value=200))
    kind = draw(st.sampled_from(["arr", "obj", "mixed"]))
    if kind == "arr":
        return "[" * depth + "]" * depth
    if kind == "obj":
        return '{"a":' * depth + "null" + "}" * depth
    # mixed: alternate
    out = []
    for i in range(depth):
        if i % 2 == 0:
            out.append('{"a":')
        else:
            out.append("[")
    close = []
    for i in reversed(range(depth)):
        if i % 2 == 0:
            close.append("}")
        else:
            close.append("]")
    return "".join(out) + "null" + "".join(close)


# ---------- malformed near-valid ----------

_malformed = st.sampled_from([
    # double commas
    "[1,,2]", "[,]", "[,1]", "[1,]", "[1,2,,]",
    # missing colons
    '{"a" 1}', '{"a"}', '{"a":}', '{:1}', '{"a":1 "b":2}',
    # unterminated strings
    '"abc', '{"a":"abc}', '["abc]', '"\\', '"\\u12', '"\\uZZZZ"',
    # trailing content
    "1abc", "[]xyz", "1 garbage", "true false", "{} {}", "nullx",
    # bad structure
    "}", "]", "{", "[", '{"a":1', "[1,2", "{{}}", "[[[]",
    # stray tokens
    ",", ":", "::", "{{", "]]", "}{", "][",
    # comments (disabled)
    "//x", "/* */1", "1 //c", "/* unterminated",
    # single quotes / bare keys
    "'x'", "{a:1}", "{'a':1}", "['a']",
    # whitespace-only / empty
    "", " ", "\t\n\r", "\x00",
    # NUL and control bytes embedded
    '"\x00"', "[\x00]", "{\x00:1}", "1\x00", "\x00{}",
    # duplicate keys
    '{"a":1,"a":2}', '{"a":1,"a":2,"a":3}',
    # lone minus / nonfinite
    "-", "1e309", "-1e309",
    # trailing comma variants
    "[1,2,]", '{"a":1,}', "[,]", "{,}",
    # unicode surrogates
    '"\\uD800"', '"\\uDC00"', '"\\uD800\\uD800"', '"\\uD800x"',
])


# ---------- near-crash structural mutations ----------

# Base seeds that resemble typical parser-crash inputs: deep nesting,
# truncated structures, boundary-length strings/buffers, huge tokens.
_crash_seeds = st.sampled_from([
    "[" * 64 + "]" * 64,
    "[" * 128 + "]" * 128,
    "[" * 255 + "]" * 255,
    "[" * 256 + "]" * 256,
    "[" * 512 + "]" * 512,
    '{"a":' * 64 + "null" + "}" * 64,
    '{"a":' * 128 + "null" + "}" * 128,
    '{"a":' * 255 + "null" + "}" * 255,
    '"' + "a" * 255 + '"',
    '"' + "a" * 256 + '"',
    '"' + "a" * 1024 + '"',
    '"' + "\\u0041" * 256 + '"',
    '"' + "\\n" * 512 + '"',
    "[" + ",".join(["1"] * 256) + "]",
    "[" + ",".join(["1"] * 1024) + "]",
    "{" + ",".join(['"k%d":1' % i for i in range(256)]) + "}",
    "9" * 256,
    "9" * 1024,
    "-" + "9" * 1024,
    "1e" + "9" * 256,
    '{"a":"' + "b" * 4096 + '"}',
    "[" * 200 + "1" + "]" * 199,
    "{" * 200 + "}" * 200,
    '{"a":{"b":{"c":' + "[" * 100 + "]" * 100 + "}}}",
    "[" + "[" * 128 + "]" * 128 + "]",
    '["' + "\\uD800" * 128 + '"]',
    '"' + "\x00" * 512 + '"',
    "[" + ",".join(['"\\uD800"'] * 128) + "]",
    "[" + ",".join(["-0"] * 512) + "]",
    "[" + ",".join(["1e309"] * 256) + "]",
])

# Structural mutation operators applied to a seed string.
@st.composite
def _mutate_seed(draw):
    s = draw(_crash_seeds)
    n_ops = draw(st.integers(min_value=1, max_value=4))
    for _ in range(n_ops):
        op = draw(st.sampled_from([
            "truncate", "dup_prefix", "dup_suffix", "swap_bracket",
            "insert_close", "insert_open", "insert_comma", "insert_colon",
            "insert_quote", "insert_backslash", "insert_nul", "insert_ctrl",
            "drop_char", "replace_char", "wrap_arr", "wrap_obj",
            "extend_run", "dup_token", "balance_break", "prefix_junk",
            "suffix_junk", "repeat_inner",
        ]))
        if not s and op not in ("insert_open", "insert_close", "insert_quote",
                                "insert_comma", "insert_colon", "prefix_junk"):
            s = draw(_crash_seeds)
        if op == "truncate":
            k = draw(st.integers(min_value=1, max_value=max(1, len(s))))
            s = s[:len(s) - k]
        elif op == "dup_prefix":
            k = draw(st.integers(min_value=1, max_value=max(1, len(s))))
            s = s[:k] + s
        elif op == "dup_suffix":
            k = draw(st.integers(min_value=1, max_value=max(1, len(s))))
            s = s + s[len(s) - k:]
        elif op == "swap_bracket":
            i = draw(st.integers(min_value=0, max_value=max(0, len(s) - 1)))
            if i < len(s):
                c = s[i]
                m = {"[": "]", "]": "[", "{": "}", "}": "{"}.get(c)
                if m:
                    s = s[:i] + m + s[i + 1:]
        elif op == "insert_close":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + draw(st.sampled_from(["}", "]", "]", "}"])) + s[i:]
        elif op == "insert_open":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + draw(st.sampled_from(["{", "[", '{"a":', "["])) + s[i:]
        elif op == "insert_comma":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + "," + s[i:]
        elif op == "insert_colon":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + ":" + s[i:]
        elif op == "insert_quote":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + '"' + s[i:]
        elif op == "insert_backslash":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + "\\" + s[i:]
        elif op == "insert_nul":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + "\x00" + s[i:]
        elif op == "insert_ctrl":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + draw(st.sampled_from(
                ["\x01", "\x07", "\x0b", "\x1f", "\x7f"])) + s[i:]
        elif op == "drop_char" and s:
            i = draw(st.integers(min_value=0, max_value=len(s) - 1))
            s = s[:i] + s[i + 1:]
        elif op == "replace_char" and s:
            i = draw(st.integers(min_value=0, max_value=len(s) - 1))
            s = s[:i] + draw(st.sampled_from(
                ["[", "]", "{", "}", ",", ":", '"', "\\", "0", "9",
                 "e", "-", "+", ".", "t", "f", "n", " ", "\x00"])) + s[i + 1:]
        elif op == "wrap_arr":
            s = "[" + s + "]"
        elif op == "wrap_obj":
            s = '{"a":' + s + "}"
        elif op == "extend_run":
            run = draw(st.sampled_from(["[", "]", "{", "}", "9", "a",
                                        "\\uD800", ",", ":"]))
            k = draw(st.integers(min_value=1, max_value=64))
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + run * k + s[i:]
        elif op == "dup_token":
            toks = ["true", "false", "null", "1e309", "-0", '"a"',
                    "\\uD800", "[]", "{}"]
            t = draw(st.sampled_from(toks))
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + t + s[i:]
        elif op == "balance_break":
            opens = s.count("[") + s.count("{")
            closes = s.count("]") + s.count("}")
            if opens > closes:
                s = s + draw(st.sampled_from(["}", "]"])) * (
                    opens - closes + draw(st.integers(min_value=1, max_value=4)))
            else:
                s = draw(st.sampled_from(["[", "{"])) * (
                    closes - opens + draw(st.integers(min_value=1, max_value=4))) + s
        elif op == "prefix_junk":
            s = draw(st.sampled_from(
                ["x", "\x00", "//", "/*", "'", "Infinity", "NaN", "+",
                 ".", "-.", "01", "0x"])) + s
        elif op == "suffix_junk":
            s = s + draw(st.sampled_from(
                ["x", "\x00", "//", "/*", "'", "garbage", ",", ":",
                 "}", "]"]))
        elif op == "repeat_inner":
            if len(s) > 2:
                i = draw(st.integers(min_value=0, max_value=len(s) - 2))
                j = draw(st.integers(min_value=i + 1, max_value=len(s)))
                k = draw(st.integers(min_value=1, max_value=8))
                s = s[:j] + s[i:j] * k + s[j:]
    return s


# ---------- intensified near-crash mutation ----------

# The known crashing input; we mutate structurally around it to explore the
# neighborhood of the crash site.
_known_crash = "[" * 256 + "]" * 256

@st.composite
def _intensify_near_crash(draw):
    s = _known_crash
    n_ops = draw(st.integers(min_value=1, max_value=6))
    for _ in range(n_ops):
        op = draw(st.sampled_from([
            "truncate", "dup_prefix", "dup_suffix", "swap_bracket",
            "insert_close", "insert_open", "insert_comma", "insert_colon",
            "insert_quote", "insert_backslash", "insert_nul", "insert_ctrl",
            "drop_char", "replace_char", "wrap_arr", "wrap_obj",
            "extend_run", "dup_token", "balance_break", "prefix_junk",
            "suffix_junk", "repeat_inner", "resize_depth", "off_by_one_depth",
        ]))
        if not s and op not in ("insert_open", "insert_close", "insert_quote",
                                "insert_comma", "insert_colon", "prefix_junk"):
            s = _known_crash
        if op == "truncate":
            k = draw(st.integers(min_value=1, max_value=max(1, len(s))))
            s = s[:len(s) - k]
        elif op == "dup_prefix":
            k = draw(st.integers(min_value=1, max_value=max(1, len(s))))
            s = s[:k] + s
        elif op == "dup_suffix":
            k = draw(st.integers(min_value=1, max_value=max(1, len(s))))
            s = s + s[len(s) - k:]
        elif op == "swap_bracket":
            i = draw(st.integers(min_value=0, max_value=max(0, len(s) - 1)))
            if i < len(s):
                c = s[i]
                m = {"[": "]", "]": "[", "{": "}", "}": "{"}.get(c)
                if m:
                    s = s[:i] + m + s[i + 1:]
        elif op == "insert_close":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + draw(st.sampled_from(["}", "]", "]", "}"])) + s[i:]
        elif op == "insert_open":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + draw(st.sampled_from(["{", "[", '{"a":', "["])) + s[i:]
        elif op == "insert_comma":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + "," + s[i:]
        elif op == "insert_colon":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + ":" + s[i:]
        elif op == "insert_quote":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + '"' + s[i:]
        elif op == "insert_backslash":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + "\\" + s[i:]
        elif op == "insert_nul":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + "\x00" + s[i:]
        elif op == "insert_ctrl":
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + draw(st.sampled_from(
                ["\x01", "\x07", "\x0b", "\x1f", "\x7f"])) + s[i:]
        elif op == "drop_char" and s:
            i = draw(st.integers(min_value=0, max_value=len(s) - 1))
            s = s[:i] + s[i + 1:]
        elif op == "replace_char" and s:
            i = draw(st.integers(min_value=0, max_value=len(s) - 1))
            s = s[:i] + draw(st.sampled_from(
                ["[", "]", "{", "}", ",", ":", '"', "\\", "0", "9",
                 "e", "-", "+", ".", "t", "f", "n", " ", "\x00"])) + s[i + 1:]
        elif op == "wrap_arr":
            s = "[" + s + "]"
        elif op == "wrap_obj":
            s = '{"a":' + s + "}"
        elif op == "extend_run":
            run = draw(st.sampled_from(["[", "]", "{", "}", "9", "a",
                                        "\\uD800", ",", ":"]))
            k = draw(st.integers(min_value=1, max_value=64))
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + run * k + s[i:]
        elif op == "dup_token":
            toks = ["true", "false", "null", "1e309", "-0", '"a"',
                    "\\uD800", "[]", "{}"]
            t = draw(st.sampled_from(toks))
            i = draw(st.integers(min_value=0, max_value=len(s)))
            s = s[:i] + t + s[i:]
        elif op == "balance_break":
            opens = s.count("[") + s.count("{")
            closes = s.count("]") + s.count("}")
            if opens > closes:
                s = s + draw(st.sampled_from(["}", "]"])) * (
                    opens - closes + draw(st.integers(min_value=1, max_value=4)))
            else:
                s = draw(st.sampled_from(["[", "{"])) * (
                    closes - opens + draw(st.integers(min_value=1, max_value=4))) + s
        elif op == "prefix_junk":
            s = draw(st.sampled_from(
                ["x", "\x00", "//", "/*", "'", "Infinity", "NaN", "+",
                 ".", "-.", "01", "0x"])) + s
        elif op == "suffix_junk":
            s = s + draw(st.sampled_from(
                ["x", "\x00", "//", "/*", "'", "garbage", ",", ":",
                 "}", "]"]))
        elif op == "repeat_inner":
            if len(s) > 2:
                i = draw(st.integers(min_value=0, max_value=len(s) - 2))
                j = draw(st.integers(min_value=i + 1, max_value=len(s)))
                k = draw(st.integers(min_value=1, max_value=8))
                s = s[:j] + s[i:j] * k + s[j:]
        elif op == "resize_depth":
            depth = draw(st.integers(min_value=1, max_value=600))
            s = "[" * depth + "]" * depth
        elif op == "off_by_one_depth":
            depth = draw(st.integers(min_value=1, max_value=600))
            delta = draw(st.sampled_from([-1, 1]))
            if delta < 0:
                s = "[" * depth + "]" * max(0, depth - 1)
            else:
                s = "[" * depth + "]" * (depth + 1)
    return s


# ---------- valid JSON via json.dumps ----------

@st.composite
def _valid_json(draw):
    value = draw(_json_value)
    try:
        parsed = json.loads(value)
    except Exception:
        return draw(_valid_json())
    return json.dumps(parsed)


# ---------- top-level strategy ----------

strategy = st.one_of(
    # heavily weighted toward valid JSON
    _valid_json(),
    st.one_of(
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _json_string(),
                    _json_value,
                ),
                min_size=1,
                max_size=8,
            ),
        ),
        _json_value,
        _deep_nesting(),
    ),
    # small fraction of adversarial inputs
    st.one_of(
        _malformed,
        _mutate_seed(),
        _intensify_near_crash(),
    ),
)