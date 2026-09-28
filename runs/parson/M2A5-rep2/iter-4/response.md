```python
from hypothesis import strategies as st
import json

# Top-level strategy must be named `strategy` and produce str values.
# We use a @st.composite strategy that recursively builds JSON-ish text,
# deliberately including both well-formed and near-valid-but-malformed cases,
# and concentrating some depth choices near the parser's MAX_NESTING (~2048).
#
# Never emit a raw NUL character '\x00' in the produced Python string.
# We do emit the six-character escape sequence '\u0000' when desired.

# Small helper alphabets (no raw NUL, no raw quote/backslash in safe pieces).
_SAFE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \t\n\r-_:;,.?()[]<>@#%&*+=^$"
_HEX = "0123456789abcdef"
_SURROGATE_SAMPLES = ["\\uD800", "\\uDFFF", "\\uDC00", "\\uDBFF"]

@st.composite
def _json_value(draw):
    # Bias depth choices towards interesting zones (shallow, medium, and near-limit).
    depth_choice = draw(
        st.one_of(
            st.integers(min_value=0, max_value=20),        # shallow
            st.integers(min_value=100, max_value=300),     # moderate
            st.integers(min_value=2020, max_value=2050),   # near and slightly beyond limit
            st.integers(min_value=2040, max_value=2048),   # right at the enforced cap
        )
    )

    # Local recursive generator using the same `draw`.
    def gen_value(remaining_depth):
        # Base (non-recursive) primitives and malformed variants
        def json_string_token():
            # Build string contents from a mixture of safe fragments and escapes.
            pieces = draw(
                st.lists(
                    st.one_of(
                        st.text(_SAFE_CHARS, min_size=1, max_size=6).filter(lambda s: "\x00" not in s),
                        st.sampled_from(['\\n', '\\r', '\\t', '\\b', '\\f', '\\\\"', '\\\\', '\\/']),
                        # Unicode escapes like \u00A9 or surrogate halves
                        st.builds(lambda h: "\\u" + h, st.text(_HEX, min_size=4, max_size=4)),
                        st.sampled_from(_SURROGATE_SAMPLES),
                    ),
                    min_size=0,
                    max_size=6,
                )
            )
            content = "".join(pieces)
            # Occasionally inject raw control characters other than NUL to exercise malformed inputs
            if draw(st.booleans()):
                # choose a few control codepoints (but never \x00)
                ctrl_count = draw(st.integers(0, 3))
                for _ in range(ctrl_count):
                    cp = draw(st.sampled_from([chr(1), chr(2), chr(3), chr(7), chr(11), chr(12), chr(14), chr(31)]))
                    insert_at = draw(st.integers(0, len(content)))
                    content = content[:insert_at] + cp + content[insert_at:]
            # Well-formed string usually has both quotes; sometimes produce unterminated/malformed forms
            malformed = draw(st.booleans())
            if malformed:
                mode = draw(st.sampled_from(["unterminated_end", "no_open", "raw_quote_unescaped"]))
                if mode == "unterminated_end":
                    return '"' + content  # starts quote but no closing
                if mode == "no_open":
                    return content + '"'  # missing opening quote (malformed)
                if mode == "raw_quote_unescaped":
                    # inject an unescaped quote inside the content to break the string
                    pos = draw(st.integers(0, max(0, len(content))))
                    return '"' + content[:pos] + '"' + content[pos:] + '"'  # an extra internal quote
            return '"' + content + '"'

        def json_number_token():
            # Generate a variety of numbers and near-number malformed variants.
            choice = draw(
                st.one_of(
                    # canonical integers/floats
                    st.sampled_from(["0", "1", "-1", "123", "-123", "10", "9999999999999999999999"]),
                    # leading zero illegal case
                    st.sampled_from(["01", "00", "-01"]),
                    # fractional and dot variants
                    st.sampled_from([".5", "1.", "0.0", "-.5"]),
                    # leading plus
                    st.sampled_from(["+1", "+0", "+.5"]),
                    # exponent extreme magnitudes (overflowing, non-finite)
                    st.sampled_from(["1e309", "-1e309", "1e4000", "1E+9999", "1e-9999"]),
                    # exponent with leading zeros
                    st.sampled_from(["1e01", "1E09"]),
                    # a lone minus (parser accepts as zero)
                    st.just("-"),
                )
            )
            return choice

        def json_literal_token():
            return draw(st.sampled_from(["true", "false", "null", "True", "FALSE", "nul"]))  # include malformed casing/typos

        base_choice = draw(st.integers(min_value=0, max_value=9))
        if remaining_depth <= 0 or base_choice < 6:
            # Choose among base primitives
            if base_choice <= 2:
                return json_string_token()
            elif base_choice <= 5:
                return json_number_token()
            else:
                return json_literal_token()
        else:
            # Recursive constructions: arrays/objects with possible malformed variants
            kind = draw(st.sampled_from(["array", "object", "deep_array", "deep_object"]))
            if kind == "deep_array":
                # single-element nesting to reach deep depths efficiently
                inner = gen_value(remaining_depth - 1)
                arr = "[" + inner + "]"
                # occasionally add trailing comma or double comma etc
                mal = draw(st.one_of(st.just(None), st.just("trailing_comma"), st.just("double_comma")))
                if mal == "trailing_comma":
                    return arr[:-1] + "," + "]"  # e.g., [x,]
                if mal == "double_comma":
                    return "[" + inner + ",," + inner + "]"
                return arr
            if kind == "deep_object":
                # produce a single-key nested object (possibly duplicate keys)
                key = draw(st.text(_SAFE_CHARS, min_size=1, max_size=6).filter(lambda s: '\x00' not in s and '"' not in s and "\\" not in s))
                # ensure key is a JSON string token
                key_tok = '"' + key + '"'
                inner = gen_value(remaining_depth - 1)
                obj = "{" + key_tok + ":" + inner + "}"
                # sometimes duplicate keys
                if draw(st.booleans()):
                    return "{" + key_tok + ":" + inner + "," + key_tok + ":" + inner + "}"
                # sometimes missing colon or trailing comma or double commas
                malformed = draw(st.one_of(st.just(None), st.just("missing_colon"), st.just("trailing_comma"), st.just("double_comma")))
                if malformed == "missing_colon":
                    return "{" + key_tok + " " + inner + "}"  # missing colon
                if malformed == "trailing_comma":
                    return "{" + key_tok + ":" + inner + ",}"
                if malformed == "double_comma":
                    return "{" + key_tok + ":" + inner + ",," + key_tok + ":" + inner + "}"
                return obj

            if kind == "array":
                # produce 0..4 elements
                n = draw(st.integers(min_value=0, max_value=4))
                elems = []
                for i in range(n):
                    # for distribution, sometimes recurse less deep on non-critical branches
                    child_depth = remaining_depth - 1 if draw(st.booleans()) else max(0, remaining_depth - draw(st.integers(min_value=1, max_value=3)))
                    elems.append(gen_value(child_depth))
                # join, sometimes insert malformed separators
                joiner = ","
                arr_text = "[" + (joiner.join(elems)) + "]"
                if draw(st.booleans()):
                    # malformed variants: trailing garbage after closing bracket, trailing comma, double commas
                    variant = draw(st.sampled_from(["trailing_garbage", "trailing_comma", "double_comma", None]))
                    if variant == "trailing_garbage":
                        extra = draw(st.text(_SAFE_CHARS, min_size=1, max_size=6).filter(lambda s: '\x00' not in s))
                        return arr_text + extra
                    if variant == "trailing_comma":
                        if elems:
                            return arr_text[:-1] + "," + "]"
                        else:
                            return "[,]"
                    if variant == "double_comma":
                        if len(elems) >= 2:
                            # insert a double comma between first two
                            parts = elems[:]
                            parts.insert(1, "")
                            return "[" + ",".join(parts) + "]"
                        else:
                            return "[" + ",".join(elems) + ",,]"
                return arr_text

            if kind == "object":
                # produce 0..4 pairs
                n = draw(st.integers(min_value=0, max_value=4))
                pairs = []
                keys_seen = []
                for i in range(n):
                    key = draw(st.text(_SAFE_CHARS, min_size=1, max_size=6).filter(lambda s: '\x00' not in s and '"' not in s and "\\" not in s))
                    key_tok = '"' + key + '"'
                    # sometimes reuse a key to deliberately create duplicate-key objects
                    if draw(st.booleans()) and keys_seen:
                        key_tok = '"' + draw(st.sampled_from(keys_seen)) + '"'
                    else:
                        keys_seen.append(key)
                    value_depth = remaining_depth - 1 if draw(st.booleans()) else max(0, remaining_depth - draw(st.integers(min_value=1, max_value=3)))
                    val = gen_value(value_depth)
                    # sometimes omit colon or create malformed pair
                    if draw(st.booleans()):
                        pair_text = key_tok + ":" + val
                    else:
                        # missing colon or space-only, or extra colon
                        malformed_pair = draw(st.sampled_from(["missing_colon", "extra_colon", "space_only"]))
                        if malformed_pair == "missing_colon":
                            pair_text = key_tok + " " + val
                        elif malformed_pair == "extra_colon":
                            pair_text = key_tok + "::" + val
                        else:
                            pair_text = key_tok + " " + val
                    pairs.append(pair_text)
                obj_text = "{" + ",".join(pairs) + "}"
                # sometimes append trailing garbage or trailing comma
                variant = draw(st.one_of(st.just(None), st.just("trailing_comma"), st.just("trailing_garbage")))
                if variant == "trailing_comma":
                    if pairs:
                        return obj_text[:-1] + "," + "}"
                    else:
                        return "{,}"
                if variant == "trailing_garbage":
                    extra = draw(st.text(_SAFE_CHARS, min_size=1, max_size=6).filter(lambda s: '\x00' not in s))
                    return obj_text + extra
                return obj_text

        # Fallback (should not be reached)
        return json_literal_token()

    return gen_value(depth_choice)

# Top-level strategy that sometimes appends trailing content to exploit the parser's
# "trailing content after a complete value is IGNORED" leniency.
@st.composite
def _top_level(draw):
    core = draw(_json_value())
    # Occasionally append trailing non-JSON garbage or another JSON value
    if draw(st.booleans()):
        suffix_choice = draw(st.one_of(
            st.just(""),  # no suffix
            st.text(_SAFE_CHARS, min_size=1, max_size=10).filter(lambda s: '\x00' not in s),
            st.sampled_from([" ", " xyz", "garbage", "\n\rTRAIL", "/*comment*/", "/* unterminated", "//comment\n", ";int x=0;", "#define X 1"]),
            st.just("nullgarbage"),
            st.just("123abc"),
        ))
        return core + suffix_choice
    return core

# Expose the required top-level name `strategy`.
# Improved: include a broader random-text arm alongside the structured generator so the fuzzer
# can also exercise raw C-like fragments, preprocessor and punctuation-heavy inputs.
strategy = st.one_of(
    _top_level(),
    st.text(_SAFE_CHARS + "{}[]()<>;=+-*/&|!~^%:,#\"'\\", min_size=1, max_size=200).filter(lambda s: '\x00' not in s),
)
```