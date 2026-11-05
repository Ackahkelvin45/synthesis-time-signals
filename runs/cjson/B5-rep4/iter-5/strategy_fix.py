from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Scalar fragments that are valid JSON values.
_valid_scalars = st.one_of(
    st.just("true"),
    st.just("false"),
    st.just("null"),
    # ordinary numbers
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
    st.integers(min_value=0, max_value=10**30).map(lambda n: "0" * (n % 5) + str(n)),
    # floats with extreme exponents / magnitudes
    st.sampled_from([
        "0", "-0", "1", "-1", "1.0", "-1.5", "3.141592653589793",
        "1e309", "-1e309", "1e-309", "1e1000", "-1e1000",
        "1E+400", "1e-400", "0.0", "9" * 400, "-" + "9" * 400,
        "1e308", "1.7976931348623157e308", "5e-324",
        "1.", "-1.", "01", "-01", "0x10", "0xDEADBEEF",
        "1e01", "1E-01", "123456789012345678901234567890",
    ]),
    # malformed numeric-ish junk that should be rejected as a first value
    st.sampled_from([
        "-", "+1", ".5", "-.5", "NaN", "Infinity", "-Infinity",
        "1e", "1e+", "1.e5", "--1", "1..2", "0x", "0xg",
    ]),
)

# Strings: many flavours of escaping / raw bytes.
_escapes = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u001f", "\\u007f", "\\u00e9", "\\u20ac", "\\uFFFF",
    "\\uD83D\\uDE00",          # valid surrogate pair
    "\\ud800",                 # lone surrogate -> rejected
    "\\udfff",                 # lone low surrogate -> rejected
    "\\u12", "\\uZZZZ", "\\x41", "\\",  # bad escapes
])

_raw_bytes = st.sampled_from([
    "a", "Z", "0", " ", "\t", "\n", "\r", "\x00", "\x01", "\x1f",
    "\x7f", "\u00e9", "\u20ac", "\U0001F600", "/", "'",
])

_string_body = st.one_of(_escapes, _raw_bytes, st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), min_codepoint=0x20),
    max_size=8,
))

# Build a quoted string; sometimes unterminated or with stray quotes.
def _mk_string(body_parts):
    body = "".join(body_parts)
    return '"' + body + '"'

_quoted_string = st.lists(_string_body, max_size=6).map(_mk_string)

_unterminated_string = st.lists(_string_body, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)

# Keys for pairs (valid strings and some odd ones)
_keys = st.one_of(
    _quoted_string,
    st.sampled_from(['""', '"a"', '"key"', '"dup"', '"\\u0000"', '"\\ud800"']),
)

# ---------------------------------------------------------------------------
# Recursive values
# ---------------------------------------------------------------------------

_leaf = st.one_of(_valid_scalars, _quoted_string)

def _make_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _make_arr(items):
    return "[" + ",".join(items) + "]"

# A pair strategy: key ":" value
_pair = st.tuples(_keys, _leaf).map(lambda kv: kv[0] + ":" + kv[1])

def _build_recursive():
    return st.recursive(
        _leaf,
        lambda children: st.one_of(
            # arrays
            st.lists(children, max_size=4).map(_make_arr),
            # objects
            st.lists(
                st.tuples(_keys, children).map(lambda kv: kv[0] + ":" + kv[1]),
                max_size=4,
            ).map(_make_obj),
        ),
        max_leaves=20,
    )

_value = _build_recursive()

# ---------------------------------------------------------------------------
# Depth-targeted wrappers (near the 1000-level limit)
# ---------------------------------------------------------------------------

def _nest(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

_depth = st.sampled_from([0, 1, 2, 5, 50, 500, 999, 1000, 1001, 1002, 1500])

_deep_array = st.tuples(_depth, _value).map(
    lambda t: _nest(t[0], "[", "]", t[1])
)
_deep_object = st.tuples(_depth, _value).map(
    lambda t: _nest(t[0], '{"k":', "}", t[1])
)
_deep_mixed = st.tuples(_depth, _value).map(
    lambda t: _nest(t[0] // 2, '[{"a":', "}]", t[1])
)

# ---------------------------------------------------------------------------
# Malformed-but-near-valid structures
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    st.sampled_from([
        "", " ", "\t\n\r", ",", ",,", "[,]", "[1,,2]", "[1,2,]",
        "{,}", '{"a":1,}', '{"a":1,,}', '{"a" 1}', '{"a":}',
        "{:1}", '{"a":1 "b":2}', "[1 2]", "[1:2]",
        "tru", "fals", "nul", "TRUE", "Null", "nan",
        "'x'", "{a:1}", "[}", "{]", "[1}", "]", "}",
        "1 2", "1abc", "true false", "nullx",
        "\ufeff", "\ufeff1", "\ufeff{}",
        "\x00", "1\x00", "\x00{}", '"a"\x00',
    ]),
    # unterminated strings / arrays / objects
    _unterminated_string,
    st.tuples(_quoted_string, _value).map(lambda t: t[0] + t[1]),  # missing colon
    st.tuples(_value, _value).map(lambda t: t[0] + "," + t[1]),     # top-level pair
    st.tuples(_value, _value).map(lambda t: t[0] + t[1]),           # trailing content
    st.tuples(st.lists(_value, min_size=1, max_size=3)).map(
        lambda t: "[" + ",".join(t[0]) + ","          # trailing comma
    ),
    st.tuples(st.lists(_pair, min_size=1, max_size=3)).map(
        lambda t: "{" + ",".join(t[0]) + ","          # trailing comma
    ),
    st.tuples(st.lists(_value, min_size=1, max_size=3)).map(
        lambda t: "[" + ",".join(t[0])                 # unterminated array
    ),
    st.tuples(st.lists(_pair, min_size=1, max_size=3)).map(
        lambda t: "{" + ",".join(t[0])                 # unterminated object
    ),
)

# ---------------------------------------------------------------------------
# Top-level combination
# ---------------------------------------------------------------------------

# improve_strategy: add truncation/mutation fuzzing of otherwise-valid values,
# which tends to hit parser edge cases (cut mid-token, mid-escape, mid-number)
# that the purely structural generators above rarely reach.
def _truncate(s):
    if not s:
        return s
    # bias toward cutting near the end (where partial tokens live) and at
    # interesting structural boundaries.
    n = len(s)
    positions = [0, 1, 2, 3, n // 2, n - 3, n - 2, n - 1, n]
    idx = positions[hash(s) % len(positions)] % (n + 1)
    return s[:idx]

_truncated = _value.map(_truncate)

# improve_strategy: byte-level mutation of valid values. Flip / delete / insert
# a single character at a random position. This explores the "one-edit-away"
# neighbourhood of valid JSON, which is where many parser bugs (off-by-one in
# escape handling, number parsing, delimiter detection) actually live.
_MUT_CHARS = "{}[],:\"\\0123456789.eE+-tfnul \t\n\r\x00\x1f\x7f"

def _mutate(s):
    if not s:
        return s
    n = len(s)
    op = hash(s) % 3
    pos = (hash(s) >> 3) % n
    ch = _MUT_CHARS[(hash(s) >> 7) % len(_MUT_CHARS)]
    if op == 0:  # delete
        return s[:pos] + s[pos + 1:]
    if op == 1:  # insert
        return s[:pos] + ch + s[pos:]
    # replace
    return s[:pos] + ch + s[pos + 1:]

_mutated = _value.map(_mutate)

# improve_strategy: multi-edit mutations. Apply a small number (1..4) of
# independent single-character edits to a valid value. Many parser bugs only
# manifest after several interacting edits (e.g. unbalanced brackets plus a
# broken escape), which the single-edit generator above cannot reach.
def _mutate_multi(s):
    if not s:
        return s
    out = s
    h = hash(s)
    n_edits = 1 + (h % 4)
    for i in range(n_edits):
        if not out:
            break
        m = len(out)
        op = (h >> (i * 3)) % 3
        pos = (h >> (i * 5 + 1)) % m
        ch = _MUT_CHARS[(h >> (i * 7 + 2)) % len(_MUT_CHARS)]
        if op == 0:
            out = out[:pos] + out[pos + 1:]
        elif op == 1:
            out = out[:pos] + ch + out[pos:]
        else:
            out = out[:pos] + ch + out[pos + 1:]
    return out

_mutated_multi = _value.map(_mutate_multi)

# improve_strategy: splice two valid values together at a boundary. Concatenate
# a prefix of one value with a suffix of another. This produces structurally
# plausible but semantically broken inputs (e.g. a complete object glued onto a
# partial array) that exercise delimiter/depth bookkeeping in the parser.
def _splice(a, b):
    if not a or not b:
        return a + b
    i = hash(a) % (len(a) + 1)
    j = hash(b) % (len(b) + 1)
    return a[:i] + b[j:]

_spliced = st.tuples(_value, _value).map(lambda t: _splice(t[0], t[1]))

# improve_strategy: wrap a valid value with mismatched openers/closers, or with
# extra unbalanced delimiters. Tests that the parser correctly tracks nesting
# and rejects mismatched brackets rather than crashing or reading OOB.
_MISMATCH = st.sampled_from([
    ("[", "}"), ("{", "]"), ("[", ""), ("{", ""), ("", "]"), ("", "}"),
    ("[[", "]]"), ("{{", "}}"), ("[{", "}]"), ("[{", "]"), ("[", "}]"),
])

def _wrap_mismatch(t):
    (op, cl), inner = t
    return op + inner + cl

_mismatched = st.tuples(_MISMATCH, _value).map(_wrap_mismatch)

# improve_strategy: repeat a small malformed fragment many times. Long runs of
# identical junk (deeply nested opens, repeated commas, repeated escapes) probe
# for resource-exhaustion / stack-overflow style bugs in the parser.
def _repeat(t):
    frag, count = t
    return frag * count

_repeated = st.tuples(
    st.sampled_from([
        "[", "{", "]", "}", ",", ":", '"', "\\", "\\u", "\\u0",
        "0", "-", "e", "1e", "true", "null", "\x00", " ",
    ]),
    st.sampled_from([10, 100, 1000, 5000, 10000]),
).map(_repeat)

# improve_strategy: byte-level splice of two values at arbitrary offsets,
# with an inserted delimiter. This creates "two values glued at a token
# boundary" inputs (e.g. "12" + "3" -> "123", or "true" + "false" -> "truefalse")
# that specifically stress token-boundary detection and number/keyword lexing,
# which the prefix/suffix splice above does not target.
def _byte_splice(a, b):
    if not a or not b:
        return a + b
    i = (hash(a) >> 2) % (len(a) + 1)
    j = (hash(b) >> 2) % (len(b) + 1)
    sep = _MUT_CHARS[(hash(a) ^ hash(b)) % len(_MUT_CHARS)]
    return a[:i] + sep + b[j:]

_byte_spliced = st.tuples(_value, _value).map(lambda t: _byte_splice(t[0], t[1]))

# improve_strategy: inject a NUL / control byte into the middle of a valid
# value. Parsers that use C string APIs often mishandle embedded NULs, and
# control bytes in the middle of tokens probe lexer state machines.
def _inject_control(s):
    if not s:
        return s
    n = len(s)
    pos = (hash(s) >> 1) % (n + 1)
    ch = "\x00\x01\x1f\x7f\n\r\t"[(hash(s) >> 4) % 9]
    return s[:pos] + ch + s[pos:]

_control_injected = _value.map(_inject_control)

strategy = st.one_of(
    _value,
    _deep_array,
    _deep_object,
    _deep_mixed,
    _malformed,
    _truncated,
    _mutated,
    _mutated_multi,
    _spliced,
    _mismatched,
    _repeated,
    _byte_spliced,
    _control_injected,
    # valid value followed by trailing junk (accepted by parser)
    st.tuples(_value, st.sampled_from(["x", " ", "\x00", "abc", "{}", "[]"])).map(
        lambda t: t[0] + t[1]
    ),
    # BOM-prefixed values
    st.tuples(st.just("\ufeff"), _value).map(lambda t: t[0] + t[1]),
)