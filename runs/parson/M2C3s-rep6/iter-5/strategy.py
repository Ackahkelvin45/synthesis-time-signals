from hypothesis import strategies as st
import json

# Helper strategies for string generation (never emit a raw NUL '\x00')
_safe_text = st.text(
    alphabet=(
        # printable characters excluding quote and backslash to avoid accidental escapes;
        # keep it simple and safe for json.dumps which will add quotes/escapes as needed.
        ''.join(chr(c) for c in range(0x20, 0x7F) if chr(c) not in {'"', '\\'})
    ),
    min_size=0,
    max_size=30,
)

# valid JSON quoted strings produced via json.dumps (will escape control chars)
_valid_quoted = _safe_text.map(json.dumps)

# explicit special string forms to cover edge-cases:
_explicit_escapes = st.one_of(
    st.just('"\\u0000"'),        # explicit six-character NUL escape inside string
    st.just('"\\uD800"'),        # surrogate half
    st.just('"' + '\\n' + '"'),  # explicit newline escape
    st.just('"' + '\\t' + '"'),  # explicit tab escape
    st.just('"\\"quoted\\""'),   # embedded escaped quotes
)

# raw control inside a quoted string (invalid per grammar but deliberately tested)
_raw_control_inside = st.text(
    alphabet=''.join(chr(c) for c in range(1, 0x20) if c != 0),
    min_size=1,
    max_size=6,
).map(lambda s: '"' + s + '"')  # includes control characters but never \x00

# unterminated string: starts with a quote, may include stuff, but no ending quote
_unterminated_string = st.one_of(
    st.just('"'),
    st.text(alphabet=''.join(chr(c) for c in range(1, 0x7F) if chr(c) != '"'), max_size=20).map(lambda s: '"' + s),
)

string_prim = st.one_of(
    _valid_quoted,
    _explicit_escapes,
    _raw_control_inside,
    _unterminated_string,
)

# Numeric strategies: valid and malformed variants
# Valid NUMBER per grammar (no leading zeros unless single '0')
@st.composite
def valid_number(draw):
    neg = draw(st.booleans())
    use_zero = draw(st.booleans())  # sometimes produce 0
    if use_zero:
        intpart = "0"
    else:
        first = draw(st.sampled_from([str(i) for i in range(1, 10)]))
        rest = draw(st.text(alphabet='0123456789', min_size=0, max_size=8))
        intpart = first + rest
    frac = ""
    if draw(st.booleans()):
        # fraction: '.' followed by 1+ digits
        frac = "." + draw(st.text(alphabet='0123456789', min_size=1, max_size=6))
    exp = ""
    if draw(st.booleans()):
        sign = draw(st.sampled_from(['', '+', '-']))
        expnum = draw(st.text(alphabet='0123456789', min_size=1, max_size=4))
        exp = "e" + sign + expnum
    s = ("-" if neg else "") + intpart + frac + exp
    return s

# Malformed/edge-case numbers (leading +, .5, 1., 01, extreme exponents, lone '-' and '-.')
_malformed_number = st.one_of(
    st.just('-'),                 # accepted by parser as 0 (per notes)
    st.just('-.'),
    st.just('+1'),                # leading plus (near-valid)
    st.just('.5'),                # leading dot
    st.just('1.'),                # trailing dot
    st.just('01'),                # leading zero with extra digit (invalid per grammar)
    st.sampled_from(['1e309', '-1e400', '1e9999', '9e99999']),  # extreme exponents (likely overflow)
    st.sampled_from(['+1e10', '-+1', '00.1']),
)

number_prim = st.one_of(valid_number(), _malformed_number)

# Literal tokens
literal_prim = st.sampled_from(['true', 'false', 'null'])

# Combine primitives into a strategy
primitive_value = st.one_of(string_prim, number_prim, literal_prim)


# Composite builder for JSON text, using recursion (allows arrays/objects)
@st.composite
def build_value(draw, max_depth):
    """
    Recursively build a JSON (or near-JSON) text string.  max_depth bounds nesting.
    This purposely injects malformed variants with some probability.
    """
    # If depth is exhausted, force primitive
    if max_depth <= 0:
        return draw(primitive_value)

    # Choose whether to produce primitive or container; bias toward containers when depth remains
    choose_container = draw(st.booleans()) and max_depth > 0
    if not choose_container:
        return draw(primitive_value)

    # Decide between array and object
    is_array = draw(st.booleans())

    # choose sizes small to moderate
    n = draw(st.integers(min_value=0, max_value=5))
    # Sometimes choose empty explicitly to cover {} and []
    if n == 0:
        if is_array:
            base = "[]"
        else:
            base = "{}"
        # Also sometimes produce an unterminated container
        if draw(st.booleans()):  # 50% chance to return proper empty, 50% malformed
            if draw(st.booleans()):
                # missing closing bracket
                return base[:-1]  # '[' or '{'
            else:
                # trailing comma inside empty: "{,}" or "[,]"
                return base[0] + "," + base[-1]
        return base

    # Build elements/pairs
    elements = []
    keys = []
    for i in range(n):
        if is_array:
            # recursively build element
            elem = draw(build_value(max_depth - 1))
            elements.append(elem)
        else:
            # object: build key and value; sometimes reuse keys to create duplicates
            # key: sometimes valid quoted, sometimes unterminated or raw
            key_choice = draw(st.integers(min_value=0, max_value=10))
            if key_choice < 6:
                key = draw(_valid_quoted)
            elif key_choice < 8:
                key = draw(_explicit_escapes)
            else:
                key = draw(_unterminated_string)
            # duplicate keys injection: with some probability, reuse a prior key
            if draw(st.booleans()) and keys:
                if draw(st.booleans()):
                    # reuse last key to create duplicate
                    key = keys[-1]
            keys.append(key)
            # value
            val = draw(build_value(max_depth - 1))
            # sometimes omit colon or use missing/extra commas
            if draw(st.integers(min_value=0, max_value=20)) == 0:
                # missing colon
                pair = key + " " + val
            else:
                pair = key + ":" + val
            elements.append(pair)

    # join with commas, but sometimes inject double commas or trailing comma or missing comma
    joiner = ","
    join_text = joiner.join(elements)
    malformed_roll = draw(st.integers(min_value=0, max_value=20))
    if malformed_roll == 0:
        # double comma somewhere
        if len(elements) >= 2:
            idx = draw(st.integers(min_value=0, max_value=len(elements) - 2))
            parts = elements[:]
            parts[idx] = parts[idx] + ","
            join_text = ",".join(parts)
        else:
            join_text = join_text + ","
    elif malformed_roll == 1:
        # trailing comma
        join_text = join_text + ","
    elif malformed_roll == 2:
        # missing comma: concatenate two elements with no comma
        if len(elements) >= 2:
            idx = draw(st.integers(min_value=0, max_value=len(elements) - 2))
            parts = elements[:]
            parts[idx] = parts[idx] + parts[idx + 1]
            parts.pop(idx + 1)
            join_text = ",".join(parts)
        else:
            # no-op
            pass

    if is_array:
        result = "[" + join_text + "]"
        # sometimes omit closing bracket or opening bracket to be malformed
        if draw(st.integers(min_value=0, max_value=30)) == 0:
            # omit closing
            return result[:-1]
        if draw(st.integers(min_value=0, max_value=100)) == 0:
            # add extra trailing comma-like sequences
            return result + ",,"
        return result
    else:
        result = "{" + join_text + "}"
        # sometimes omit closing brace
        if draw(st.integers(min_value=0, max_value=30)) == 0:
            return result[:-1]
        # sometimes introduce duplicate-key explicit extra pair at front
        if draw(st.integers(min_value=0, max_value=50)) == 0 and keys:
            # prepend duplicate first key
            result = "{" + keys[0] + ":" + elements[0] + "," + join_text + "}"
        return result


# Special deep nesting generator to concentrate near parser depth limits (~2048)
@st.composite
def deep_nesting(draw):
    # Bias toward very deep depths near 2048, but allow some shallower cases
    depth_choice = draw(st.one_of(
        st.integers(min_value=0, max_value=16),               # small
        st.integers(min_value=100, max_value=400),            # medium
        st.integers(min_value=1900, max_value=2050),          # near parser cap
    ))
    # Cap to a safe ceiling to avoid extremely huge strings in normal runs
    max_cap = 2050
    depth = min(depth_choice, max_cap)
    # choose array or object nesting
    use_array = draw(st.booleans())
    inner = draw(st.one_of(primitive_value, st.just("0"), st.just("null")))
    if use_array:
        # Build "[" * depth + inner + "]" * depth
        return ("[" * depth) + inner + ("]" * depth)
    else:
        # For objects, embed as {"k": ...} repeated
        # choose a simple key (valid quoted)
        key = draw(_valid_quoted)
        pair = key + ":" + inner
        return ("{" + pair) * depth + ("}" * depth)


# Optional trailing content appended to a complete value (parser accepts trailing content)
_trailing_garbage = st.one_of(
    st.just(""),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789<>!@#$%^&*()", min_size=1, max_size=20).map(lambda s: " " + s),
    st.sampled_from([
        "\ngarbage",
        "XYZ",
        "][",
        "a}}",
        "/*comment*/",
        "#include <stdio.h>\nint main(){printf(\"hi\\n\");return 0;}\n",
        "/* unclosed comment",
        "// line comment\nint x=0;\n",
        "#define X 1\nint x=X;\n",
        "char s[] = \"text\\n\";",
    ]),  # may include characters accepted as trailing
    st.just("\ufeff"),
)

# Top-level strategy: mix deep nesting, recursive builder, and primitives; sometimes append trailing garbage
@st.composite
def json_text(draw):
    mode = draw(st.integers(min_value=0, max_value=20))
    if mode == 0:
        # extremely likely to pick a deep nesting occasionally
        core = draw(deep_nesting())
    elif mode <= 6:
        # structured recursive generation with larger allowed depth
        core = draw(build_value(max_depth=60))
    else:
        # shallow recursive generation
        core = draw(build_value(max_depth=10))

    # With some probability, append trailing content (parser accepts trailing)
    if draw(st.integers(min_value=0, max_value=1)) == 0:
        core = draw(_trailing_garbage) + core

    return core

# The required top-level name
strategy = json_text()