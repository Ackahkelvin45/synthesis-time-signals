```python
from hypothesis import strategies as st
import json

# Top-level strategy producing JSON-like text (str).
# Uses @st.composite for recursive obj/arr production and to emit many edge cases.

CAP_DEPTH = 2048  # parser's known nesting cap; we will concentrate near this

_hex_digit = "0123456789abcdefABCDEF"

def _hex4_random(draw):
    return "".join(draw(st.sampled_from(list(_hex_digit))) for _ in range(4))

@st.composite
def _string_literal(draw, allow_unterminated=False):
    """
    Produce a JSON string literal (including the quotes) or an unterminated variant.
    Includes escapes: simple escapes, \\uXXXX, surrogate halves, and embedded control
    characters (but never raw NUL \x00).
    """
    parts = []
    # choose length small usually but sometimes larger
    length = draw(st.integers(min_value=0, max_value=40))
    for i in range(length):
        kind = draw(st.integers(min_value=0, max_value=8))
        if kind == 0:
            # safe printable char excluding quote and backslash
            # pick from visible ASCII except "
            c = draw(st.sampled_from([chr(x) for x in range(0x20, 0x7f) if chr(x) not in ('"', "\\")]))
            parts.append(c)
        elif kind == 1:
            # control char except NUL
            ctrl = draw(st.sampled_from([chr(x) for x in range(1, 0x20)]))
            parts.append(ctrl)
        elif kind == 2:
            # simple escape
            esc = draw(st.sampled_from(['\\\\', '\\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']))
            parts.append(esc)
        elif kind == 3:
            # unicode escape \uXXXX
            hx = _hex4_random(draw)
            parts.append("\\u" + hx)
        elif kind == 4:
            # surrogate half: high or low
            if draw(st.booleans()):
                # high surrogate range D800-DBFF
                val = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
            else:
                # low surrogate range DC00-DFFF
                val = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
            parts.append("\\u%04X" % val)
        elif kind == 5:
            # include some UTF-8 multibyte characters directly
            parts.append(draw(st.sampled_from(["λ", "界", "😊", "𐐷"])))
        else:
            # raw backslash or quote occasionally to force escapes
            parts.append(draw(st.sampled_from(['\\', '"'])))
    body = "".join(parts)
    # sometimes produce unterminated string (missing closing quote) to fuzz
    if allow_unterminated and draw(st.booleans()):
        return '"' + body  # missing trailing quote
    return '"' + body + '"'

@st.composite
def _number_literal(draw):
    """
    Produce a number-like token; covers valid and near-valid/malformed forms:
    normal integers/floats, leading +, .5, 1., 01 (leading zero), very large exponents
    like 1e309 (likely overflow), lone '-' and '-.' etc.
    """
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        # small ints
        return draw(st.integers(min_value=-1000, max_value=1000)).__str__()
    elif kind == 1:
        # leading zero malformed like 01, 00
        n = draw(st.integers(min_value=0, max_value=99))
        return "0" + str(n)
    elif kind == 2:
        # decimal with fraction
        a = draw(st.integers(min_value=-1000, max_value=1000))
        b = draw(st.integers(min_value=0, max_value=9999999))
        return f"{a}.{b}"
    elif kind == 3:
        # exponent large
        a = draw(st.integers(min_value=1, max_value=9))
        exp = draw(st.integers(min_value=100, max_value=1200))
        return f"{a}e{exp}"
    elif kind == 4:
        # overflow-looking exponent
        return draw(st.sampled_from(["1e309", "1e9999", "-1e400", "9e999"]))
    elif kind == 5:
        # leading plus
        return draw(st.sampled_from(["+1", "+123", "+0", "+1.0", "+.5"]))
    elif kind == 6:
        # fractional without leading zero
        return draw(st.sampled_from([".5", "-.5", ".0"]))
    elif kind == 7:
        # trailing dot
        return draw(st.sampled_from(["1.", "-1.", "123."]))
    elif kind == 8:
        # lone sign or sign+dot
        return draw(st.sampled_from(["-", "-.", "+", "+."]))
    else:
        # NaN/Inf-like tokens (parser rejects non-finite)
        return draw(st.sampled_from(["NaN", "Inf", "-Inf", "nan"]))
    
@st.composite
def _primitive_value(draw):
    """
    Choose a primitive value token: string, number, true/false/null, or malformed
    tokens (unterminated string, etc.).
    """
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind == 0:
        return draw(_string_literal(allow_unterminated=True))
    elif kind == 1:
        return draw(_number_literal())
    elif kind == 2:
        return draw(st.sampled_from(["true", "false", "null"]))
    elif kind == 3:
        # some near-valid punctuation to fuzz parser leniency
        return draw(st.sampled_from(["1abc", "1 garbage", "[]xyz", "trueXYZ"]))
    elif kind == 4:
        # produce a JSON string using python's json.dumps to ensure escapes like \u0000
        sample = draw(st.text(max_size=10))
        # ensure no raw NUL in generated text
        sample = sample.replace("\x00", "")
        return json.dumps(sample)
    else:
        # unterminated string heavily
        return draw(_string_literal(allow_unterminated=True))

@st.composite
def _json_value(draw, current_depth=0, max_depth=8):
    """
    Recursively produce a JSON text value, with control over maximum depth.
    Uses recursive composition to get obj/arr productions.
    """
    # If we are at a very large max_depth, ensure we don't exceed CAP_DEPTH
    max_depth = min(max_depth, CAP_DEPTH)
    # Decide whether to produce container or primitive
    if current_depth >= max_depth:
        return draw(_primitive_value())
    choice = draw(st.integers(min_value=0, max_value=9))
    # Favor primitives at shallow depths, but allow objects/arrays
    if choice <= 3:
        return draw(_primitive_value())
    elif choice == 4:
        # produce an array; sometimes empty, sometimes with trailing commas or double commas
        kind = draw(st.integers(min_value=0, max_value=5))
        if kind == 0:
            return "[]"
        # make between 1 and 6 elements typically
        length = draw(st.integers(min_value=1, max_value=6))
        elems = [draw(_json_value(current_depth + 1, max_depth)) for _ in range(length)]
        if kind == 1:
            # normal array
            return "[" + ",".join(elems) + "]"
        elif kind == 2:
            # trailing comma
            return "[" + ",".join(elems) + ",]"
        elif kind == 3:
            # double comma inserted
            idx = draw(st.integers(min_value=0, max_value=len(elems)-1))
            # insert an extra comma between elements idx and idx+1
            return "[" + ",".join(elems[:idx+1]) + ",," + ",".join(elems[idx+1:]) + "]"
        elif kind == 4:
            # deeply nested single element array (to concentrate depth)
            # build a nested chain like [[[... value ...]]]
            depth_inc = draw(st.integers(min_value=1, max_value=max(1, max_depth - current_depth)))
            inner = draw(_json_value(current_depth + depth_inc, max_depth))
            return "[" * depth_inc + inner + "]" * depth_inc
        else:
            # include trailing garbage after the array (parser accepts trailing content)
            tail = draw(st.text(min_size=1, max_size=10))
            return "[" + ",".join(elems) + "]" + tail
    else:
        # produce an object; variations include empty, duplicate keys, missing colons, trailing commas
        kind = draw(st.integers(min_value=0, max_value=7))
        if kind == 0:
            return "{}"
        # number of pairs
        num = draw(st.integers(min_value=1, max_value=6))
        pairs = []
        for i in range(num):
            # generate key, mostly valid string literal but sometimes unterminated or unquoted to cause errors
            key_kind = draw(st.integers(min_value=0, max_value=5))
            if key_kind == 0:
                key = draw(_string_literal(allow_unterminated=True))
            elif key_kind == 1:
                # unquoted identifier-like (malformed)
                key = draw(st.text(min_size=1, max_size=8, alphabet=st.text().strategy))
                # ensure no spaces/newlines and no NUL
                key = "".join(ch for ch in key if ch != "\x00" and ch not in " \t\r\n")
            elif key_kind == 2:
                # escaped unicode key
                key = '"' + "\\u" + _hex4_random(draw) + '"'
            elif key_kind == 3:
                # same key intentionally to create duplicates (we'll handle duplication later)
                base = draw(st.text(min_size=1, max_size=6))
                base = base.replace('"', '').replace("\\", "")
                key = json.dumps(base)
            else:
                key = draw(_string_literal(allow_unterminated=True))
            val = draw(_json_value(current_depth + 1, max_depth))
            # sometimes omit colon
            if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=10)) == 0:
                pair = key + " " + val  # missing colon
            else:
                pair = key + ":" + val
            pairs.append(pair)
        if kind == 1:
            # normal object
            return "{" + ",".join(pairs) + "}"
        elif kind == 2:
            # trailing comma
            return "{" + ",".join(pairs) + ",}"
        elif kind == 3:
            # duplicate keys: replicate one key
            if pairs:
                dup_index = draw(st.integers(min_value=0, max_value=len(pairs)-1))
                dup_pair = pairs[dup_index]
                # duplicate by inserting another pair with same key but different value
                # extract key (up to first colon or space) and reuse
                keytext = dup_pair.split(":", 1)[0] if ":" in dup_pair else dup_pair.split(None,1)[0]
                new_val = draw(_json_value(current_depth + 1, max_depth))
                new_pair = keytext + ":" + new_val
                pairs.insert(draw(st.integers(min_value=0, max_value=len(pairs))), new_pair)
            return "{" + ",".join(pairs) + "}"
        elif kind == 4:
            # double comma somewhere
            idx = draw(st.integers(min_value=0, max_value=len(pairs)-1))
            return "{" + ",".join(pairs[:idx+1]) + ",," + ",".join(pairs[idx+1:]) + "}"
        elif kind == 5:
            # unterminated string as value for one pair (already possible above) but also omit closing brace
            text = "{" + ",".join(pairs)
            if draw(st.booleans()):
                return text  # missing closing brace
            else:
                return text + "}"
        elif kind == 6:
            # extremely deep single-key object chain to push nesting near CAP_DEPTH
            depth_inc = draw(st.integers(min_value=1, max_value=max(1, max_depth - current_depth)))
            inner = draw(_json_value(current_depth + depth_inc, max_depth))
            # create nested {"k": {"k": {... inner ...}}}
            k = json.dumps("deep")
            s = inner
            for _ in range(depth_inc):
                s = "{" + k + ":" + s + "}"
            return s
        else:
            # trailing garbage after object
            tail = draw(st.text(min_size=1, max_size=10))
            return "{" + ",".join(pairs) + "}" + tail

@st.composite
def _top_level(draw):
    """
    Top-level composite that selects a target max depth (often shallow, sometimes near CAP_DEPTH),
    then draws a JSON value using _json_value and optionally appends trailing data (parser allows).
    Ensures no raw NUL characters are present in the final string.
    """
    # Usually pick small max_depth, but sometimes concentrate near CAP_DEPTH
    deep_bias = draw(st.booleans())
    if deep_bias and draw(st.booleans()):
        # very deep near parser cap
        max_depth = draw(st.integers(min_value=max(1, CAP_DEPTH - 100), max_value=CAP_DEPTH))
    elif deep_bias:
        max_depth = draw(st.integers(min_value=30, max_value=200))
    else:
        max_depth = draw(st.integers(min_value=2, max_value=12))
    val = draw(_json_value(current_depth=0, max_depth=max_depth))
    # sometimes append trailing content which parser accepts
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=5)) == 0:
        tail = draw(st.text(min_size=1, max_size=10))
        val = val + tail
    # Ensure we never embed a raw NUL byte in the returned string (spec requirement).
    val = val.replace("\x00", "")
    return val

# Exported top-level strategy
strategy = _top_level()
```