from hypothesis import strategies as st
import json

# -- primitive pieces --

# text content for safe JSON strings (never contains raw NUL)
_safe_text = st.text(min_size=0, max_size=20).filter(lambda s: '\x00' not in s)

# valid JSON string token via json.dumps (ensures proper escaping, uses \uXXXX for surrogates)
valid_json_string = _safe_text.map(lambda s: json.dumps(s))

# crafted explicit escape sequences as raw JSON string tokens (six-character \uXXXX forms)
explicit_escapes = st.sampled_from([
    '"\\u0000"',     # explicit NUL escape (safe)
    '"\\u0001"',     # control escape
    '"\\uD800"',     # high surrogate escape
    '"\\uDC00"',     # low surrogate escape
    '"\\ud83d\\ude00"',  # surrogate pair for 😀
    '"\\uFFFF"'      # noncharacter escape
])

# unterminated string (missing closing quote) - near-valid-but-malformed
unterminated_string = _safe_text.map(lambda s: '"' + s)

# keys in objects: usually valid JSON strings, sometimes unquoted (malformed)
key_token = st.one_of(
    valid_json_string,
    explicit_escapes,
    # unquoted identifier-like keys (malformed)
    _safe_text.filter(lambda s: s != "").map(lambda s: s.replace('"', '').replace(" ", ""))  # e.g. bareword
)

# numeric tokens: valid and malformed variants
valid_integer = st.one_of(st.just("0"), st.integers(min_value=1, max_value=10**12).map(str))
valid_fraction = st.integers(min_value=0, max_value=10**6).map(str).map(lambda i: i + "." + "0")  # simple decimal
valid_exponent = st.integers(min_value=1, max_value=9).map(str).map(lambda d: d + "e" + str(308))  # large but maybe finite
valid_number = st.one_of(valid_integer, valid_fraction, valid_exponent, st.floats(allow_infinity=False, allow_nan=False).map(lambda f: repr(f)))

# explicitly extreme/exponent-overflowing forms (non-finite likely)
extreme_numbers = st.sampled_from([
    "1e309", "9e9999", "-1E+400", "1e10000",   # likely overflow to inf (parser rejects non-finite)
    "1e308", "1e307", "2.5e308"  # near-limits
])

# malformed numbers: leading +, .5, 1., leading zeros
malformed_numbers = st.sampled_from(["+1", "+0.5", ".5", "1.", "01", "-.5", "+.5"])

# lone-signs and near-empty-number forms (parser accepts '-' as 0)
lone_signs = st.sampled_from(["-", "-.", "+", "+."])

# literals
literals = st.sampled_from(["true", "false", "null", "null", "null"])

# trailing-content after a valid value (parser accepts trailing content)
def trailing_after(value_token_strategy):
    # take a base token and append arbitrary trailing junk (could be letters, punctuation)
    junk = st.text(min_size=1, max_size=10).filter(lambda s: '\x00' not in s)
    return st.tuples(value_token_strategy, junk).map(lambda t: t[0] + t[1])

# base (non-recursive) values: valid and many near-valid/malformed options
base_value = st.one_of(
    valid_json_string,
    explicit_escapes,
    unterminated_string,
    valid_number,
    extreme_numbers,
    malformed_numbers,
    literals,
    lone_signs,
    trailing_after(valid_integer),   # e.g. "1abc" (accepted by parser)
)

# -- composite strategy to build recursive obj/arr productions (and deep nesting) --

@st.composite
def _strategy(draw):
    # Start with a base token
    current = draw(base_value)

    # Choose whether to create a deep nesting instance or iterative wrapping
    deep_choice = draw(st.booleans())

    if deep_choice:
        # Produce either shallow or very deep nesting concentrated near parser cap (~2048)
        depth_choice = draw(st.one_of(
            st.integers(min_value=0, max_value=6),          # common small depths
            st.integers(min_value=1500, max_value=2048)     # target near the parser's MAX_NESTING
        ))
        # build deep nesting by repeatedly wrapping the current token. Randomly choose array/object.
        for i in range(depth_choice):
            wrap_type = draw(st.sampled_from(["array", "object"]))
            if wrap_type == "array":
                # array may hold multiple elements: include current among them
                elems = draw(st.lists(base_value, min_size=0, max_size=3))
                # insert current somewhere
                if elems:
                    pos = draw(st.integers(min_value=0, max_value=len(elems)))
                    elems.insert(pos, current)
                else:
                    elems = [current]
                # occasionally inject double commas or trailing commas for malformed variants
                malformed = draw(st.booleans())
                if malformed and len(elems) >= 1:
                    # insert an empty gap to produce a double comma like [a,,b]
                    if len(elems) >= 2:
                        # build with a double-comma by inserting empty placeholder
                        parts = elems[:1] + [""] + elems[1:]
                    else:
                        parts = elems + [""]
                    current = "[" + ",".join(parts) + "]"
                else:
                    # maybe trailing comma
                    if draw(st.booleans()):
                        current = "[" + ",".join(elems) + ",]"
                    else:
                        current = "[" + ",".join(elems) + "]"
            else:
                # object wrapper: create pairs; may include duplicate keys and malformed colons
                n_pairs = draw(st.integers(min_value=0, max_value=3))
                # to encourage duplicates, sample a small pool of key tokens
                key_pool = draw(st.lists(key_token, min_size=1, max_size=3))
                pairs = []
                for j in range(n_pairs):
                    k = draw(st.sampled_from(key_pool))
                    v = draw(base_value)
                    # sometimes omit colon (malformed) or create normal pair
                    if draw(st.booleans()):
                        pair = k + ":" + v
                    else:
                        pair = k + " " + v  # missing colon variant
                    pairs.append(pair)
                # ensure current is included as one of the values
                if draw(st.booleans()):
                    # include current as a value in one of the pairs (add an extra pair)
                    k = draw(st.sampled_from(key_pool))
                    pairs.append(k + ":" + current)
                # possibly create duplicate keys explicitly by repeating a key
                if pairs and draw(st.booleans()):
                    if len(pairs) >= 1:
                        # duplicate the first key
                        first_key = pairs[0].split(":", 1)[0]
                        pairs.append(first_key + ":" + draw(st.just(current)) if draw(st.booleans()) else first_key + ":" + draw(st.just("null")))
                # maybe trailing comma or double commas
                if draw(st.booleans()):
                    # double comma example: {"a":1,, "b":2}
                    if len(pairs) >= 2 and draw(st.booleans()):
                        # inject extra empty between some commas
                        idx = 1
                        parts = pairs[:idx] + [""] + pairs[idx:]
                        current = "{" + ",".join(parts) + "}"
                    else:
                        current = "{" + ",".join(pairs) + ",}"
                else:
                    current = "{" + ",".join(pairs) + "}"

        return current

    else:
        # Iterative but limited-depth wrapping using recursive object/array productions
        wraps = draw(st.integers(min_value=0, max_value=8))
        for _ in range(wraps):
            kind = draw(st.sampled_from(["array", "object", "broken_array", "broken_object"]))
            if kind in ("array", "broken_array"):
                # create small arrays from drawn elements (recursive composition)
                elems = draw(st.lists(base_value, min_size=0, max_size=4))
                # include current among elements sometimes
                if draw(st.booleans()):
                    pos = draw(st.integers(min_value=0, max_value=len(elems)))
                    elems.insert(pos, current)
                else:
                    elems.append(current)
                if kind == "broken_array" and draw(st.booleans()):
                    # produce a malformed array with double commas or missing closing bracket
                    if draw(st.booleans()):
                        parts = elems[:1] + [""] + elems[1:]
                        current = "[" + ",".join(parts) + "]"
                    else:
                        current = "[" + ",".join(elems)  # missing closing bracket (unterminated)
                else:
                    # sometimes trailing comma
                    if draw(st.booleans()):
                        current = "[" + ",".join(elems) + ",]"
                    else:
                        current = "[" + ",".join(elems) + "]"
            else:
                # object / broken_object
                n_pairs = draw(st.integers(min_value=0, max_value=4))
                # make pairs; intentionally allow duplicate keys by sampling from small pool
                pool = draw(st.lists(key_token, min_size=1, max_size=3))
                pairs = []
                for i in range(n_pairs):
                    k = draw(st.sampled_from(pool))
                    v = draw(base_value)
                    # sometimes omit colon
                    if draw(st.booleans()):
                        pair = k + ":" + v
                    else:
                        pair = k + " " + v
                    pairs.append(pair)
                # include current
                if draw(st.booleans()):
                    k = draw(st.sampled_from(pool))
                    pairs.append(k + ":" + current)
                # broken object: maybe missing brace or double comma
                if kind == "broken_object" and draw(st.booleans()):
                    if draw(st.booleans()):
                        parts = pairs[:1] + [""] + pairs[1:]
                        current = "{" + ",".join(parts) + "}"
                    else:
                        current = "{" + ",".join(pairs)  # missing closing brace
                else:
                    # maybe trailing comma
                    if draw(st.booleans()):
                        current = "{" + ",".join(pairs) + ",}"
                    else:
                        current = "{" + ",".join(pairs) + "}"

        # also occasionally produce a standalone deep-bracketed structure directly
        if draw(st.booleans()):
            # small chance to produce an explicit deep nesting in a single token (still avoids raw NUL)
            d = draw(st.one_of(st.integers(0, 6), st.integers(2000, 2050)))
            # choose brackets or braces
            if draw(st.booleans()):
                current = "[" * d + current + "]" * d
            else:
                # construct nested objects like {"k":{"k":... current ...}}
                k = draw(_safe_text.map(lambda s: json.dumps(s) if s != "" else '"k"'))
                nested = current
                for _ in range(d):
                    nested = "{" + k + ":" + nested + "}"
                current = nested

        return current

# Expose the top-level strategy
strategy = _strategy()