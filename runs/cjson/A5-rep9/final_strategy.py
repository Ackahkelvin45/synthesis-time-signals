from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf-level strategies
# ---------------------------------------------------------------------------

_number_ints = st.one_of(
    st.integers(min_value=0, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    # leading zeros (accepted by parser)
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
    # hex (accepted by parser)
    st.integers(min_value=0, max_value=2**32).map(lambda n: hex(n)),
    st.just("0"),
    st.just("-0"),
)

_number_fracs = st.one_of(
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot, accepted by parser
    st.tuples(
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=0, max_value=10**6),
    ).map(lambda t: "." + str(t[0]) + "0" * (t[1] % 5)),
)

_number_exps = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(abs(e))),
    st.integers(min_value=0, max_value=400).map(lambda e: "e-" + str(e)),
    # huge magnitudes -> inf when parsed
    st.sampled_from(["e309", "e1000", "e999999999", "E+308", "e-9999"]),
)

_numbers = st.one_of(
    _number_ints,
    st.tuples(_number_ints, _number_fracs).map(lambda t: t[0] + t[1]),
    st.tuples(_number_ints, _number_fracs, _number_exps).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(_number_ints, _number_exps).map(lambda t: t[0] + t[1]),
)

# Strings: valid escapes, \uXXXX, surrogate escapes, raw control/NUL bytes.
_hex4 = st.tuples(*[st.sampled_from("0123456789abcdefABCDEF")] * 4).map(
    lambda t: "".join(t)
)

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    # surrogate pairs (valid) and lone surrogates (rejected by parser)
    st.tuples(
        st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800"]),
        st.sampled_from(["dc00", "dfff", "0000", "ffff"]),
    ).map(lambda t: "\\u" + t[0] + "\\u" + t[1]),
    st.sampled_from(["\\ud800", "\\udfff", "\\uD800", "\\uDC00"]),
)

# Raw code points allowed inside a string: printable ASCII plus control/NUL.
_safe_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
    # raw control bytes and NUL, accepted by the parser
    st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
)

_string_pieces = st.one_of(_escapes, _safe_chars)

_strings = st.lists(_string_pieces, max_size=8).map(lambda xs: '"' + "".join(xs) + '"')

# Malformed / near-valid leaf fragments (used for fuzzing mutations).
_malformed_fragments = st.sampled_from(
    [
        '"unterminated',
        '"',
        "\\",
        "\\u12",
        "\\uZZZZ",
        "\\x41",
        "'single'",
        "01",
        "007",
        "1.",
        "-",
        "+1",
        ".5",
        "0x",
        "0xZZ",
        "NaN",
        "Infinity",
        "-Infinity",
        "1e",
        "1e+",
        "1ee5",
        "tru",
        "fals",
        "nul",
        "True",
        "False",
        "None",
        "{}",
        "[]",
        ",",
        ":",
        "\x00",
        "\ufeff",
        "1 2",
        "1abc",
        "nullnull",
    ]
)

# ---------------------------------------------------------------------------
# Recursive obj/arr construction
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])


@st.composite
def _pair(draw):
    key = draw(_strings)
    colon = draw(st.sampled_from([":", ":", ":", ": ", " : "]))
    val = draw(_value_strategy)
    return key + colon + val


# Build the recursive value strategy with a depth budget.
# Depth limit of the parser is 1000; concentrate near it.
_deep_obj = st.integers(min_value=0, max_value=4).map(
    lambda n: "{" + '"k":' * n + "null" + "}" * n
)
_deep_arr = st.integers(min_value=0, max_value=4).map(
    lambda n: "[" * n + "null" + "]" * n
)

# Near-limit depth generators (careful: keep counts modest for speed).
_near_limit_arrays = st.integers(min_value=990, max_value=1010).map(
    lambda n: "[" * n + "0" + "]" * n
)
_near_limit_objs = st.integers(min_value=990, max_value=1010).map(
    lambda n: '{"a":' * n + "0" + "}" * n
)

# Unbalanced / truncated deep nesting: stress the parser's depth handling and
# error recovery when the closing brackets never come.
_unbalanced_deep = st.integers(min_value=1, max_value=1010).map(
    lambda n: "[" * n
) | st.integers(min_value=1, max_value=1010).map(
    lambda n: '{"a":' * n
) | st.integers(min_value=2, max_value=1010).map(
    lambda n: "[" * n + "]" * (n - 1)
) | st.integers(min_value=2, max_value=1010).map(
    lambda n: '{"a":' * n + "}" * (n - 1)
)

_empty_containers = st.sampled_from(["{}", "[]", "{ }", "[ ]", "{\n}", "[\t]"])

_duplicate_key_obj = st.tuples(
    _strings,
    _strings,
).map(lambda t: "{" + t[0] + ":1," + t[0] + ":2," + t[1] + ":null}")

_obj_atoms = st.one_of(
    _empty_containers,
    _duplicate_key_obj,
    _deep_obj,
    _near_limit_objs,
)

_arr_atoms = st.one_of(
    _empty_containers,
    _deep_arr,
    _near_limit_arrays,
)

# Recursive core; use st.recursive for obj/arr nesting.
_scalar = st.one_of(
    _strings,
    _numbers,
    st.sampled_from(["true", "false", "null"]),
    _malformed_fragments,
)

_value_strategy = st.recursive(
    _scalar,
    lambda children: st.one_of(
        # arrays
        st.lists(children, min_size=0, max_size=5).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        # objects with pairs
        st.lists(_pair(), min_size=0, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        # whitespace-padded containers
        st.tuples(
            st.lists(children, min_size=1, max_size=3),
            _ws,
        ).map(lambda t: "[" + t[1] + ("," + t[1]).join(t[0]) + t[1] + "]"),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Top-level wrappers: valid, near-valid, malformed, BOM, trailing junk
# ---------------------------------------------------------------------------

_trailing_junk = st.one_of(
    st.just(""),
    st.just("\x00"),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("}"),
    st.just("]"),
    st.just("garbage"),
    st.just("\n\n"),
    st.just("\x00\x00"),
)

_bom = st.sampled_from(["", "\ufeff"])

_malformed_top = st.one_of(
    st.just(""),
    st.just("   "),
    st.just(","),
    st.just(":"),
    st.just("[1,,2]"),
    st.just('{"a":1,}'),
    st.just("[1,2,]"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just("{:1}"),
    st.just("{a:1}"),
    st.just("[1 2]"),
    st.just('"\\ud800"'),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("0x10"),
    st.just("\x00"),
    st.just("\ufeff"),
)

_valid_top = st.one_of(
    _value_strategy,
    _obj_atoms,
    _arr_atoms,
    _near_limit_arrays,
    _near_limit_objs,
)

# Structured mutation fuzzer: take a valid document and apply 1-3 small
# perturbations (delete/insert/duplicate/swap) to explore the error-recovery
# paths of the parser more densely than pure random bytes.
_mut_chars = st.sampled_from(
    [
        "{", "}", "[", "]", ",", ":", '"', "\\", "0", "1", "-", "+", ".",
        "e", "E", "t", "f", "n", "u", " ", "\t", "\n", "\r", "\x00", "\ufeff",
    ]
)


@st.composite
def _mutated(draw):
    base = draw(_valid_top)
    n = draw(st.integers(min_value=1, max_value=3))
    s = base
    for _ in range(n):
        if not s:
            s = draw(_mut_chars)
            continue
        op = draw(st.integers(min_value=0, max_value=3))
        i = draw(st.integers(min_value=0, max_value=len(s)))
        if op == 0:  # delete
            s = s[:i] + s[i + 1:]
        elif op == 1:  # insert
            s = s[:i] + draw(_mut_chars) + s[i:]
        elif op == 2:  # duplicate a slice
            j = draw(st.integers(min_value=i, max_value=len(s)))
            s = s[:i] + s[i:j] + s[i:j] + s[j:]
        else:  # swap two adjacent-ish positions
            if len(s) >= 2:
                j = draw(st.integers(min_value=0, max_value=len(s) - 1))
                k = draw(st.integers(min_value=0, max_value=len(s) - 1))
                lst = list(s)
                lst[j], lst[k] = lst[k], lst[j]
                s = "".join(lst)
    return s


# ---------------------------------------------------------------------------
# NEW: token-boundary mutation fuzzer.
# Instead of mutating raw characters (which mostly produces early-syntax
# errors), this splits a valid document into JSON tokens and then splices,
# deletes, duplicates, or reorders whole tokens. This exercises the parser's
# deeper structural error-recovery paths (unexpected token, missing comma,
# missing colon, trailing tokens) far more effectively.
# ---------------------------------------------------------------------------

_json_token_re = [
    "{", "}", "[", "]", ",", ":", "true", "false", "null",
]


@st.composite
def _token_splice(draw):
    base = draw(_valid_top)
    # Split into tokens: structural punctuation, strings, numbers, keywords.
    tokens = []
    i = 0
    n = len(base)
    while i < n:
        c = base[i]
        if c in "{}[],:":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            while j < n:
                if base[j] == "\\":
                    j += 2
                    continue
                if base[j] == '"':
                    j += 1
                    break
                j += 1
            tokens.append(base[i:j])
            i = j
        elif c in " \t\n\r":
            i += 1
        else:
            j = i
            while j < n and base[j] not in "{}[],:\" \t\n\r":
                j += 1
            tokens.append(base[i:j])
            i = j

    if not tokens:
        return draw(_mut_chars)

    n_ops = draw(st.integers(min_value=1, max_value=4))
    for _ in range(n_ops):
        if not tokens:
            break
        op = draw(st.integers(min_value=0, max_value=4))
        k = draw(st.integers(min_value=0, max_value=len(tokens) - 1))
        if op == 0:  # delete a token
            del tokens[k]
        elif op == 1:  # duplicate a token
            tokens.insert(k, tokens[k])
        elif op == 2:  # insert a random structural/leaf token
            tokens.insert(k, draw(_mut_chars))
        elif op == 3:  # swap two tokens
            m = draw(st.integers(min_value=0, max_value=len(tokens) - 1))
            tokens[k], tokens[m] = tokens[m], tokens[k]
        else:  # replace a token with a different one
            tokens[k] = draw(_mut_chars)

    # Re-join. Randomly choose tight vs. spaced joining to vary whitespace.
    if draw(st.booleans()):
        return "".join(tokens)
    sep = draw(_ws)
    return sep.join(tokens)


strategy = st.one_of(
    # valid values with optional BOM and trailing content
    st.tuples(_bom, _valid_top, _trailing_junk).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # malformed top-level inputs
    st.tuples(_bom, _malformed_top).map(lambda t: t[0] + t[1]),
    # unbalanced / truncated deep nesting
    _unbalanced_deep,
    # structured mutations of valid documents
    st.tuples(_bom, _mutated()).map(lambda t: t[0] + t[1]),
    # token-level splicing mutations (structural error recovery)
    st.tuples(_bom, _token_splice()).map(lambda t: t[0] + t[1]),
    # raw NUL / control-heavy fuzz: bias toward structural/control bytes
    st.lists(
        st.one_of(
            st.sampled_from(
                [
                    "{", "}", "[", "]", ",", ":", '"', "\\", "0", "1", "-",
                    "+", ".", "e", "E", "t", "f", "n", "u", " ", "\t", "\n",
                    "\r", "\x00", "\x01", "\x1f", "\x7f", "\ufeff",
                ]
            ),
            st.characters(min_codepoint=0, max_codepoint=0x10FFFF),
        ),
        min_size=0,
        max_size=40,
    ).map(lambda cs: "".join(cs)),
)