from hypothesis import strategies as st
import json

# Safe printable characters for constructing raw string contents (exclude " and \ and NUL)
_SAFE_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " \t\n\r"
    "!@#$%^&*()-_=+[]{};:'<>,.?/`~"
)

# JSON-escaped string generator (valid)
_valid_text = st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=40).map(json.dumps)

# Insert explicit \uXXXX sequences (including surrogates) into otherwise-safe text and then ensure JSON quoting
_surrogate_escape = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda cp: "\\u%04X" % cp)
_unicode_escape = st.integers(min_value=0x0, max_value=0x10FFFF).map(lambda cp: "\\u%04X" % (cp & 0xFFFF))

@st.composite
def unicode_aware_string(draw):
    piece1 = draw(st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=20))
    esc = draw(st.one_of(_surrogate_escape, _unicode_escape, st.just("\\u0000")))
    piece2 = draw(st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=20))
    # embed explicit escape sequences (they are literal backslash-u sequences inside the JSON string)
    combined = piece1 + esc + piece2
    return json.dumps(combined)

# Unterminated / malformed string variants (e.g., missing closing quote)
@st.composite
def unterminated_string(draw):
    # produce a valid json.dumps then remove the trailing quote (making it unterminated)
    s = draw(_valid_text)
    if len(s) >= 1:
        return s[:-1]  # drop final quote -> unterminated
    return s  # degenerate

# String that includes explicit backslash escapes (e.g., \n, \t) but as raw sequences
@st.composite
def raw_escape_string(draw):
    base = draw(st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=30))
    escapes = draw(st.lists(st.sampled_from(["\\n", "\\t", "\\b", "\\r", "\\f", "\\\"", "\\\\"]), min_size=0, max_size=4))
    # weave escapes into the text
    pieces = [base]
    for e in escapes:
        pieces.append(e)
        pieces.append(draw(st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=10)))
    combined = "".join(pieces)
    return json.dumps(combined)

# String strategy includes valid, unicode-escaped, and malformed variants
string_value = st.one_of(
    _valid_text,
    unicode_aware_string(),
    raw_escape_string(),
    unterminated_string(),
)

# NUMBER-like tokens: valid and malformed numeric forms, including large exponents and lone signs
def make_valid_number():
    int_part = st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str)
    )
    frac = st.one_of(st.just(""), st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=10)))
    exp = st.one_of(
        st.just(""),
        st.builds(lambda s, e: s + e, st.sampled_from(["e", "E"]), st.builds(lambda sign, digs: sign + digs, st.sampled_from(["+", "-", ""]), st.text(alphabet="0123456789", min_size=1, max_size=5)))
    )
    return st.builds(lambda i, f, ex: i + f + ex, int_part, frac, exp)

# Malformed or edge-case number tokens per adaptation notes
number_value = st.one_of(
    make_valid_number(),
    # Leading plus
    st.builds(lambda n: "+" + n, make_valid_number()),
    # Bare fractional like `.5`
    st.one_of(st.just(".5"), st.just(".123"), st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=6))),
    # Trailing dot `1.`
    st.builds(lambda n: n + ".", st.integers(min_value=0, max_value=9999).map(str)),
    # Leading zero with extra digit `01`
    st.builds(lambda d: "0" + d, st.text(alphabet="0123456789", min_size=1, max_size=5)),
    # Extreme exponents / overflow candidates
    st.sampled_from(["1e309", "-1e400", "2.5E1000", "1e9999", "-9E9999"]),
    # Lone sign or sign with dot (parser treats lone '-' as 0)
    st.sampled_from(["-", "-.", "+", "+."]),
)

# Literal tokens
literals = st.sampled_from(["true", "false", "null"])

# Base value strategy (non-recursive)
base_value = st.one_of(string_value, number_value, literals)

# Helper: produce a JSON key (must be a string). Use valid JSON string for keys mostly, but allow duplicate keys by strategy later.
key_string = st.one_of(_valid_text, unicode_aware_string(), raw_escape_string())

# Recursive construction for arrays and objects using st.recursive
def extend(inner):
    # Arrays: empty, normal, trailing-comma (malformed), double-commas
    arr_normal = st.lists(inner, min_size=0, max_size=6).map(lambda items: "[" + ",".join(items) + "]")
    arr_trailing = st.lists(inner, min_size=0, max_size=6).map(lambda items: "[" + (",".join(items) + ("," if items else "")) + "]")
    # Insert double commas: e.g., [a,,b]
    @st.composite
    def arr_double_comma(draw):
        items = draw(st.lists(inner, min_size=0, max_size=5))
        if not items:
            return "[,]"
        # pick a position to inject an extra comma
        pos = draw(st.integers(min_value=0, max_value=max(0, len(items)-1)))
        left = items[:pos+1]
        right = items[pos+1:]
        return "[" + ",".join(left) + "," + ("" if not right else "," + ",".join(right)) + "]"
    # Objects: empty, normal, trailing-comma, duplicate keys, missing colon, double-commas, missing-brace
    obj_normal = st.lists(st.tuples(key_string, inner), min_size=0, max_size=6).map(
        lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs) + "}"
    )
    obj_trailing = st.lists(st.tuples(key_string, inner), min_size=0, max_size=6).map(
        lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs) + ("," if pairs else "") + "}"
    )
    @st.composite
    def obj_duplicate_keys(draw):
        # create small set of keys, then duplicate some
        n = draw(st.integers(min_value=1, max_value=6))
        keys = [draw(key_string) for _ in range(max(1, n // 2))]
        # ensure duplicates by sampling keys
        pairs = []
        for _ in range(n):
            k = draw(st.sampled_from(keys))
            v = draw(inner)
            pairs.append((k, v))
        return "{" + ",".join(k + ":" + v for (k, v) in pairs) + "}"
    @st.composite
    def obj_missing_colon(draw):
        pairs = draw(st.lists(st.tuples(key_string, inner), min_size=1, max_size=5))
        # replace one colon with a space or nothing
        i = draw(st.integers(min_value=0, max_value=len(pairs)-1))
        out = []
        for idx, (k, v) in enumerate(pairs):
            if idx == i:
                sep = draw(st.sampled_from([" ", ""]))  # missing colon
            else:
                sep = ":"
            out.append(k + sep + v)
        return "{" + ",".join(out) + "}"
    @st.composite
    def obj_double_commas(draw):
        pairs = draw(st.lists(st.tuples(key_string, inner), min_size=0, max_size=5))
        if not pairs:
            return "{,}"
        # inject an extra comma between two entries or at start
        pos = draw(st.integers(min_value=0, max_value=len(pairs)))
        left = pairs[:pos]
        right = pairs[pos:]
        left_s = ",".join(k + ":" + v for (k, v) in left)
        right_s = ",".join(k + ":" + v for (k, v) in right)
        middle = ","  # extra comma
        body = ",".join(filter(None, [left_s, middle, right_s]))
        return "{" + body + "}"
    @st.composite
    def obj_unclosed(draw):
        pairs = draw(st.lists(st.tuples(key_string, inner), min_size=0, max_size=4))
        return "{" + ",".join(k + ":" + v for (k, v) in pairs)  # missing closing brace

    return st.one_of(
        arr_normal,
        arr_trailing,
        arr_double_comma(),
        obj_normal,
        obj_trailing,
        obj_duplicate_keys(),
        obj_missing_colon(),
        obj_double_commas(),
        obj_unclosed(),
    )

# Use st.recursive to wire base_value -> nested arrays/objects
recursive_values = st.recursive(base_value, extend, max_leaves=200)

# Additionally craft very deep nesting near parser limit using a composite generator
@st.composite
def deep_nesting(draw):
    # Choose either shallow or extremely-deep. Bias towards shallow but allow deep near 2048.
    mode = draw(st.one_of(st.just("shallow"), st.just("deep")))
    if mode == "shallow":
        depth = draw(st.integers(min_value=0, max_value=20))
    else:
        # concentrate around the parser limit ~2048 but avoid too-far values
        depth = draw(st.integers(min_value=1900, max_value=2050))
    kind = draw(st.sampled_from(["array", "object"]))
    inner_value = draw(st.one_of(st.just("0"), st.just("null"), st.just("true")))
    if kind == "array":
        return "[" * depth + inner_value + "]" * depth
    else:
        # construct nested objects like {"k":{...}} using a simple key "k" repeated
        # Note: keys must be JSON strings
        key = json.dumps("k")
        body = inner_value
        for _ in range(depth):
            body = "{" + key + ":" + body + "}"
        return body

# Combine recursive strategy and deep nesting; also allow trailing-content cases by appending garbage
@st.composite
def final_strategy(draw):
    core = draw(st.one_of(recursive_values, deep_nesting(), st.builds(lambda a, b: a + b, recursive_values, recursive_values)))
    # Occasionally append trailing content (parser accepts trailing content)
    if draw(st.booleans()):
        trailer = draw(st.one_of(
            st.just(""),
            st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=20),
            st.sampled_from([" garbage", "xyz", "123abc", "\n/*comment*/"])
        ))
        core = core + trailer
    # Ensure no raw NUL ('\x00') characters in output (harness cannot test raw NUL)
    if "\x00" in core:
        core = core.replace("\x00", "")  # never emit raw NUL
    return core

# Top-level strategy: produce str candidates, filtered to avoid raw NUL (defensive)
strategy = final_strategy().filter(lambda s: "\x00" not in s)