from hypothesis import strategies as st
import json

# ---------- scalar building blocks ----------

_hex = "0123456789abcdefABCDEF"

def _esc():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    uni = st.tuples(st.just("\\u"),
                    st.lists(st.sampled_from(_hex), min_size=4, max_size=4)).map(lambda t: t[0] + "".join(t[1]))
    return st.one_of(simple, uni)

def _safe_char():
    # printable ASCII minus quote and backslash
    return st.characters(min_codepoint=0x20, max_codepoint=0x7e).filter(
        lambda c: c not in '"\\'
    )

def _raw_control():
    # raw control bytes / NUL allowed by the parser inside strings
    return st.sampled_from(['\x00', '\x01', '\x07', '\x08', '\x09', '\x0a', '\x0b',
                            '\x0c', '\x0d', '\x1f', '\x7f'])

def _unicode_raw():
    # non-ASCII raw chars, including astral plane
    return st.characters(min_codepoint=0x80, max_codepoint=0x10ffff,
                         blacklist_categories=('Cs',))

def _string_body_piece():
    return st.one_of(
        _safe_char(),
        _esc(),
        _raw_control(),
        _unicode_raw(),
        st.just(""),  # allows empty
    )

def _string():
    inner = st.lists(_string_body_piece(), max_size=12).map("".join)
    return inner.map(lambda s: '"' + s + '"')

# Malformed / edge strings (unterminated, bad escapes, lone surrogate)
def _bad_string():
    return st.one_of(
        # unterminated
        st.lists(_string_body_piece(), max_size=8).map(lambda p: '"' + "".join(p)),
        # lone surrogate escape
        st.tuples(st.just('"\\u'), st.sampled_from(['d800', 'dfff', 'DC00', 'dbff']),
                  st.just('"')).map(lambda t: t[0] + t[1] + t[2]),
        # invalid escape
        st.tuples(st.just('"\\'), st.sampled_from(['x', 'q', 'z', 'U1234', '']),
                  st.just('"')).map(lambda t: t[0] + t[1] + t[2]),
        st.just('"'),
        st.just(''),
    )

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.from_regex(r"[1-9][0-9]{0,20}", fullmatch=True),
        # leading zeros (accepted by parser)
        st.from_regex(r"0[0-9]{1,10}", fullmatch=True),
    )

def _frac():
    return st.one_of(
        st.from_regex(r"\.[0-9]{1,20}", fullmatch=True),
        st.just("."),  # trailing dot accepted
    )

def _exp():
    return st.tuples(
        st.sampled_from(['e', 'E']),
        st.sampled_from(['', '+', '-']),
        st.from_regex(r"[0-9]{1,4}", fullmatch=True),
    ).map(lambda t: t[0] + t[1] + t[2])

def _number():
    base = st.tuples(
        st.sampled_from(['', '-']),
        _int_part(),
        st.one_of(st.just(""), _frac()),
        st.one_of(st.just(""), _exp()),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])
    extremes = st.sampled_from([
        "0", "-0", "1e309", "-1e309", "1e-400", "1e400",
        "1.7976931348623157e308", "5e-324", "123456789012345678901234567890",
        "0x10", "0XFF", "0xdeadBEEF", "1.", "-1.", "1e01", "1E+01",
        "01", "-007", "1e999999999",
    ])
    bad = st.sampled_from(["+1", ".5", "-", "NaN", "Infinity", "-Infinity", "--1", "1..2"])
    return st.one_of(base, extremes, bad)

# ---------- malformed structural bits ----------

def _malformed_fragment():
    return st.sampled_from([
        ",", ",,", ":", "::", ",]", ",}", "{}", "[]", "{\"a\"}", "[,]", "{,}",
        "'x'", "a", "truex", "nul", "tru", "fals", "  ", "\n", "\t",
    ])

# ---------- recursive value ----------

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _bad_string(),
        _malformed_fragment(),
    )

def _ws():
    return st.sampled_from(["", "", "", " ", "\t", "\n", "\r\n", "  "])

def _pair(value_strategy):
    key = st.one_of(_string(), _bad_string())
    colon = st.sampled_from([":", ":", ":", "", "::", " "])
    ws1 = _ws()
    ws2 = _ws()
    return st.tuples(key, ws1, colon, ws2, value_strategy).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

def _obj(value_strategy):
    ws = _ws()
    pairs = st.lists(_pair(value_strategy), max_size=4)
    comma = st.sampled_from([",", ",", ",", ",,", "", " ,"])
    def build(t):
        ws1, ps, ws2, cm = t
        if not ps:
            return "{" + ws1 + ws2 + "}"
        joined = ""
        for i, p in enumerate(ps):
            if i:
                joined += cm
            joined += p
        return "{" + ws1 + joined + ws2 + "}"
    return st.tuples(ws, pairs, ws, comma).map(build)

def _arr(value_strategy):
    ws = _ws()
    vals = st.lists(value_strategy, max_size=4)
    comma = st.sampled_from([",", ",", ",", ",,", "", " ,"])
    def build(t):
        ws1, vs, ws2, cm = t
        if not vs:
            return "[" + ws1 + ws2 + "]"
        joined = ""
        for i, v in enumerate(vs):
            if i:
                joined += cm
            joined += v
        return "[" + ws1 + joined + ws2 + "]"
    return st.tuples(ws, vals, ws, comma).map(build)

_value = st.recursive(
    _leaf(),
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=20,
)

# ---------- deep nesting near the 1000 limit ----------

def _deep(depth, opener, closer):
    # produce exactly `depth` nested arrays or objects
    def gen(d):
        if d <= 0:
            return "0"
        return opener + gen(d - 1) + closer
    return gen(depth)

def _deep_arrays():
    return st.integers(min_value=1, max_value=1001).map(lambda d: _deep(d, "[", "]"))

def _deep_objects():
    return st.integers(min_value=1, max_value=1001).map(lambda d: _deep(d, '{"a":', "}"))

# ---------- top-level assembly ----------

def _bom():
    return st.sampled_from(["", "", "", "\ufeff"])

def _trailing():
    return st.sampled_from(["", "", "", "x", " ", "\x00", "1 2", "abc", "//"])

def _assemble(t):
    bom, val, trail = t
    return bom + val + trail

def _top():
    val = st.one_of(
        _value,
        _deep_arrays(),
        _deep_objects(),
        _leaf(),
    )
    return st.tuples(_bom(), val, _trailing()).map(_assemble)

# ---------- round-trip oriented inputs (exercise print/compare) ----------

def _rt_string():
    # strings that must parse cleanly and then be printed/compared
    body = st.lists(
        st.one_of(
            _safe_char(),
            st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
            st.tuples(st.just("\\u"),
                      st.lists(st.sampled_from(_hex), min_size=4, max_size=4)
                      ).map(lambda t: t[0] + "".join(t[1])),
        ),
        max_size=8,
    ).map("".join)
    return body.map(lambda s: '"' + s + '"')

def _rt_number():
    return st.one_of(
        st.from_regex(r"-?(0|[1-9][0-9]{0,6})(\.[0-9]{1,6})?([eE][+-]?[0-9]{1,3})?",
                      fullmatch=True),
        st.sampled_from(["0", "-0", "1", "-1", "1.5", "1e10", "1E-10",
                         "1.7976931348623157e308", "5e-324"]),
    )

def _rt_leaf():
    return st.one_of(
        _rt_string(),
        _rt_number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _rt_pair(vs):
    return st.tuples(_rt_string(), vs).map(lambda t: t[0] + ":" + t[1])

def _rt_obj(vs):
    pairs = st.lists(_rt_pair(vs), max_size=4)
    return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

def _rt_arr(vs):
    vals = st.lists(vs, max_size=4)
    return vals.map(lambda xs: "[" + ",".join(xs) + "]")

_rt_value = st.recursive(
    _rt_leaf(),
    lambda children: st.one_of(_rt_obj(children), _rt_arr(children)),
    max_leaves=12,
)

def _rt_top():
    return _rt_value

# ---------- print / compare exercisers ----------
# Freshly built objects that exercise print_value, print_string_ptr,
# print_number, print_object, and cJSON_Compare (via round-trip pairs).

def _pc_string():
    # strings with characters that force escaping in print_string_ptr
    body = st.lists(
        st.one_of(
            st.sampled_from(list('abcXYZ019 _-./') ),
            st.sampled_from(['"', '\\', '\n', '\t', '\r', '\b', '\f', '/']),
            st.sampled_from(['\x00', '\x01', '\x1f']),
            st.sampled_from(['\u00e9', '\u20ac', '\U0001f600']),
        ),
        min_size=0, max_size=10,
    ).map("".join)
    return body.map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

def _pc_number():
    return st.one_of(
        st.sampled_from([
            "0", "-0", "1", "-1", "1.5", "-1.5", "1e10", "1E-10",
            "1.7976931348623157e308", "5e-324", "123456789012345678",
            "0.0", "-0.0", "1e0", "100000000000000000000",
        ]),
        st.from_regex(r"-?(0|[1-9][0-9]{0,8})(\.[0-9]{1,8})?([eE][+-]?[0-9]{1,3})?",
                      fullmatch=True),
    )

def _pc_leaf():
    return st.one_of(
        _pc_string(),
        _pc_number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _pc_pair(vs):
    return st.tuples(_rt_string(), vs).map(lambda t: t[0] + ":" + t[1])

def _pc_obj(vs):
    pairs = st.lists(_pc_pair(vs), max_size=5)
    return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

def _pc_arr(vs):
    vals = st.lists(vs, max_size=5)
    return vals.map(lambda xs: "[" + ",".join(xs) + "]")

_pc_value = st.recursive(
    _pc_leaf(),
    lambda children: st.one_of(_pc_obj(children), _pc_arr(children)),
    max_leaves=16,
)

def _pc_top():
    return _pc_value

# Compare-exercising pairs: same value printed twice, or near-miss pairs.
def _compare_pair():
    same = st.tuples(_pc_value, _pc_value).map(lambda t: (t[0], t[0]))
    near = st.tuples(_pc_value, _pc_value)
    return st.one_of(same, near).map(lambda t: t[0] + "\n" + t[1])

# ---------- NEW: dedicated print/compare exercisers ----------
# The run feedback showed print_value, print_string_ptr, print_number,
# print_object, and cJSON_Compare were never reached. These strategies
# build valid documents that, when parsed and re-printed, traverse the
# printer and comparator code paths.

def _pr_string_piece():
    return st.one_of(
        st.sampled_from(list('abcXYZ019 _-./')),
        st.sampled_from(['"', '\\', '\n', '\t', '\r', '\b', '\f', '/',
                         '\x00', '\x01', '\x1f', '\x7f']),
        st.sampled_from(['\u00e9', '\u20ac', '\U0001f600', '\u4e2d']),
    )

def _pr_string():
    body = st.lists(_pr_string_piece(), min_size=0, max_size=8).map("".join)
    def esc(s):
        out = []
        for ch in s:
            if ch == '"':
                out.append('\\"')
            elif ch == '\\':
                out.append('\\\\')
            elif ch == '\n':
                out.append('\\n')
            elif ch == '\t':
                out.append('\\t')
            elif ch == '\r':
                out.append('\\r')
            elif ch == '\b':
                out.append('\\b')
            elif ch == '\f':
                out.append('\\f')
            elif ch == '/':
                out.append('\\/')
            elif ord(ch) < 0x20 or ord(ch) == 0x7f:
                out.append('\\u%04x' % ord(ch))
            else:
                out.append(ch)
        return '"' + "".join(out) + '"'
    return body.map(esc)

def _pr_number():
    return st.one_of(
        st.sampled_from([
            "0", "-0", "1", "-1", "1.5", "-1.5", "1e10", "1E-10",
            "1.7976931348623157e308", "5e-324", "0.0", "-0.0",
            "1e0", "100000000000000000000", "123456789012345678",
        ]),
        st.from_regex(r"-?(0|[1-9][0-9]{0,8})(\.[0-9]{1,8})?([eE][+-]?[0-9]{1,3})?",
                      fullmatch=True),
    )

def _pr_leaf():
    return st.one_of(
        _pr_string(),
        _pr_number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _pr_pair(vs):
    return st.tuples(_pr_string(), vs).map(lambda t: t[0] + ":" + t[1])

def _pr_obj(vs):
    pairs = st.lists(_pr_pair(vs), min_size=0, max_size=5)
    return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

def _pr_arr(vs):
    vals = st.lists(vs, min_size=0, max_size=5)
    return vals.map(lambda xs: "[" + ",".join(xs) + "]")

_pr_value = st.recursive(
    _pr_leaf(),
    lambda children: st.one_of(_pr_obj(children), _pr_arr(children)),
    max_leaves=18,
)

def _print_exercise():
    # A valid document that forces print_value/print_string_ptr/print_number/
    # print_object. Wrapped so the harness can parse and re-print.
    return _pr_value

def _compare_exercise():
    # Two documents separated by a newline: either identical (exercises the
    # equal branch of cJSON_Compare) or a near-miss (exercises the unequal
    # branch), covering number/string/array/object comparisons.
    same = st.tuples(_pr_value, _pr_value).map(lambda t: (t[0], t[0]))
    near = st.tuples(_pr_value, _pr_value)
    return st.one_of(same, near).map(lambda t: t[0] + "\n" + t[1])

# ---------- NEW: self-contained print/compare harnesses ----------
# The previous run still showed 0% on print_value, print_string_ptr,
# print_number, print_object and cJSON_Compare. These strategies embed the
# document(s) in an explicit, self-describing envelope so the harness can
# reliably locate and exercise the printer and comparator regardless of how
# it splits input. Each envelope is still valid text for the parser.

def _harness_print():
    # "PRINT\n<doc>" — harness prints <doc>.
    return _pr_value.map(lambda d: "PRINT\n" + d)

def _harness_compare_same():
    # "CMP\n<doc>\n<doc>" identical documents -> equal branch.
    return _pr_value.map(lambda d: "CMP\n" + d + "\n" + d)

def _harness_compare_near():
    # "CMP\n<doc>\n<doc>" distinct documents -> unequal branch.
    return st.tuples(_pr_value, _pr_value).map(
        lambda t: "CMP\n" + t[0] + "\n" + t[1]
    )

def _harness_compare_typed():
    # Force comparisons across each type category with matched/opposed pairs.
    def mk(kind):
        if kind == "num":
            return st.tuples(_pr_number(), _pr_number()).map(
                lambda t: "CMP\n" + t[0] + "\n" + t[1])
        if kind == "str":
            return st.tuples(_pr_string(), _pr_string()).map(
                lambda t: "CMP\n" + t[0] + "\n" + t[1])
        if kind == "bool":
            return st.tuples(
                st.sampled_from(["true", "false"]),
                st.sampled_from(["true", "false"]),
            ).map(lambda t: "CMP\n" + t[0] + "\n" + t[1])
        if kind == "null":
            return st.just("CMP\nnull\nnull")
        if kind == "arr":
            return st.tuples(_pr_arr(_pr_leaf()), _pr_arr(_pr_leaf())).map(
                lambda t: "CMP\n" + t[0] + "\n" + t[1])
        # obj
        return st.tuples(_pr_obj(_pr_leaf()), _pr_obj(_pr_leaf())).map(
            lambda t: "CMP\n" + t[0] + "\n" + t[1])
    return st.one_of(st.sampled_from(
        ["num", "str", "bool", "null", "arr", "obj"]).flatmap(mk))

def _harness_compare_mixed():
    # Cross-type comparisons -> exercises the type-mismatch early return.
    return st.tuples(_pr_value, _pr_value).map(
        lambda t: "CMP\n" + t[0] + "\n" + t[1]
    )

def _harness_roundtrip():
    # "RT\n<doc>" — harness parses, prints, re-parses, compares.
    return _pr_value.map(lambda d: "RT\n" + d)

def _harness_print_string():
    # Force print_string_ptr on a variety of tricky strings.
    return _pr_string().map(lambda s: "PRINT\n" + s)

def _harness_print_number():
    # Force print_number on tricky numeric forms.
    return _pr_number().map(lambda n: "PRINT\n" + n)

def _harness_print_object():
    # Force print_object on non-trivial objects.
    return _pr_obj(_pr_value).map(lambda o: "PRINT\n" + o)

def _harness_print_array():
    return _pr_arr(_pr_value).map(lambda a: "PRINT\n" + a)

strategy = st.one_of(
    _top(),
    _rt_top(),
    _pc_top(),
    _compare_pair(),
    _print_exercise(),
    _compare_exercise(),
    _harness_print(),
    _harness_compare_same(),
    _harness_compare_near(),
    _harness_compare_typed(),
    _harness_compare_mixed(),
    _harness_roundtrip(),
    _harness_print_string(),
    _harness_print_number(),
    _harness_print_object(),
    _harness_print_array(),
    st.just(""),
    st.just(" "),
    st.just("\ufeff"),
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("01"),
    st.just("1."),
    st.just("0x10"),
    st.just("1e309"),
    st.just('"\\ud800"'),
    st.just("[1,]"),
    st.just('{"a":1,}'),
    st.just("[1 2]"),
    st.just('{"a" 1}'),
    st.just('"abc'),
    st.just("+1"),
    st.just(".5"),
    st.just("-"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just('"\x00"'),
    st.just('"\x01\x1f"'),
    st.just('[1,2,3]'),
    st.just('{"a":1,"b":2}'),
    st.just('{"a":[1,2,{"b":"c"}]}'),
    st.just('"a\\u00e9b"'),
    st.just('"\\t\\n\\r\\b\\f\\/\\\\\\""'),
    _deep_arrays(),
    _deep_objects(),
)