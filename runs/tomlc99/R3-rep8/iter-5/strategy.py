from hypothesis import strategies as st
import json

# ---------- helpers ----------

_BARE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
_CTRL = [chr(i) for i in range(0x01, 0x20) if i not in (0x0a, 0x0d)] + ["\t", "\r"]
_NONASCII = [chr(c) for c in (0x00e9, 0x4e2d, 0x1f600, 0x03b1, 0x0416, 0x2603)]


def _join(*parts):
    return "".join(parts)


# ---------- keys ----------

def _bare_key():
    return st.text(alphabet=_BARE, min_size=1, max_size=12)


_esc_short = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])


def _unicode_escape():
    return st.sampled_from(["\\u0041", "\\u00e9", "\\u0000", "\\uFFFF", "\\U0001F600",
                            "\\U00000000", "\\u4e2d"])


def _basic_string_char():
    return st.one_of(
        st.text(alphabet="abcXYZ 019!@#$%^&*()[]{}.,;:<>?|~`'", min_size=1, max_size=4),
        _esc_short,
        _unicode_escape(),
        st.sampled_from(_CTRL),
        st.sampled_from(_NONASCII),
    )


def _basic_string():
    return st.lists(_basic_string_char(), max_size=4).map(lambda xs: '"' + "".join(xs) + '"')


def _literal_string():
    return st.lists(
        st.one_of(
            st.text(alphabet="abcXYZ 019!@#$%^&*()[]{}.,;:<>?|~`\"\\", min_size=0, max_size=4),
            st.sampled_from(_CTRL),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map(lambda xs: "'" + "".join(xs) + "'")


def _ml_basic_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet="abc 0123\n\t\"'", min_size=0, max_size=6),
            _esc_short,
            _unicode_escape(),
            st.sampled_from(["\\\n", "\\\r\n"]),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map("".join)
    return body.map(lambda b: '"""' + b + '"""')


def _ml_literal_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet="abc 0123\n\t\"'\\", min_size=0, max_size=6),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map("".join)
    return body.map(lambda b: "'''" + b + "'''")


def _simple_key():
    return st.one_of(
        _bare_key(),
        _basic_string(),
        _literal_string(),
        st.just('""'),
    )


def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=3).map(lambda ps: ".".join(ps))


def _key():
    return st.one_of(_simple_key(), _dotted_key())


# ---------- scalars ----------

def _dec_int():
    return st.one_of(
        st.integers(min_value=-(10 ** 30), max_value=10 ** 30).map(str),
        st.sampled_from(["0", "-0", "+0", "007", "00", "1_000", "1_2_3",
                         "99999999999999999999999999999999999999",
                         "-99999999999999999999999999999999999999"]),
    )


def _hex_int():
    return st.one_of(
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=10).map(lambda s: "0x" + s),
        st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFFFFFF"]),
    )


def _oct_int():
    return st.one_of(
        st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda s: "0o" + s),
        st.sampled_from(["0o0", "0o777", "0o1_2_3"]),
    )


def _bin_int():
    return st.one_of(
        st.text(alphabet="01", min_size=1, max_size=12).map(lambda s: "0b" + s),
        st.sampled_from(["0b0", "0b1", "0b1_0_1", "0b" + "1" * 64]),
    )


def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())


def _float():
    return st.one_of(
        st.sampled_from(["1.0", "-1.5", "+3.25", "1.", ".5", "0.0", "-0.0",
                         "1e10", "1E-10", "1.5e+300", "1e309", "-1e309",
                         "6.626e-34", "1_000.0", "1.0_0", "3.14e1_0"]),
        st.tuples(
            st.integers(min_value=-10 ** 6, max_value=10 ** 6).map(str),
            st.sampled_from([".0", ".5", "."]),
            st.one_of(st.just(""), st.sampled_from(["e1", "E-2", "e+10", "e309"])),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )


def _inf_nan():
    return st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])


def _bool():
    return st.sampled_from(["true", "false"])


def _date_time():
    return st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27 07:32:00Z",
        "1979-05-27t07:32:00z",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27T07:32:00",
        "1979-05-27T07:32:00.5",
        "1979-05-27",
        "1979-02-30",
        "0000-00-00",
        "9999-99-99",
        "07:32:00",
        "07:32:00.999",
        "23:59:59.999999999",
    ])


def _string():
    return st.one_of(_basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string())


# ---------- recursive values ----------

def _scalar():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _inf_nan(),
        _bool(),
        _date_time(),
    )


def _array_body(depth):
    inner = _value(depth)
    elems = st.lists(
        st.tuples(
            inner,
            st.one_of(st.just(""), st.just(" "), st.just("\n"), st.just(" # c\n")),
        ).map(lambda t: t[0] + t[1]),
        max_size=4,
    )
    return elems


def _array(depth):
    def build(elems):
        sep = st.sampled_from([",", ", ", ",\n", " , "])
        return sep, elems

    return st.builds(
        lambda elems: _render_array(elems),
        _array_body(depth),
    )


def _render_array(elems):
    if not elems:
        return st.just("[]").example() if False else "[]"
    return "[" + ", ".join(elems) + "]"


def _inline_table(depth):
    inner = _value(depth)

    def kv():
        return st.tuples(_key(), inner).map(lambda t: t[0] + " = " + t[1])

    def render(pairs):
        if not pairs:
            return "{}"
        return "{" + ", ".join(pairs) + "}"

    return st.lists(kv(), max_size=3).map(render)


def _value(depth):
    if depth <= 0:
        return _scalar()
    return st.one_of(
        _scalar(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )


def _deep_array(n):
    return st.just("[" * n + "]" * n)


def _deep_inline(n):
    # {a={a={a=...}}} nested inline tables
    return st.just("{a=" * n + "1" + "}" * n)


# ---------- documents ----------

def _comment():
    return st.lists(
        st.one_of(
            st.text(alphabet="abc 0123!@#$%^&*()[]{}.,;:<>?|~`'\"\\", min_size=0, max_size=8),
            st.sampled_from(_CTRL),
            st.sampled_from(_NONASCII),
        ),
        max_size=3,
    ).map(lambda xs: "#" + "".join(xs))


def _keyval_line(depth):
    return st.tuples(_key(), _value(depth), st.one_of(st.just(""), _comment())).map(
        lambda t: t[0] + " = " + t[1] + (" " + t[2] if t[2] else "")
    )


def _table_line():
    return st.tuples(_key(), st.one_of(st.just(""), _comment())).map(
        lambda t: "[" + t[0] + "]" + (" " + t[1] if t[1] else "")
    )


def _array_table_line():
    return st.tuples(_key(), st.one_of(st.just(""), _comment())).map(
        lambda t: "[[" + t[0] + "]]" + (" " + t[1] if t[1] else "")
    )


def _line(depth):
    return st.one_of(
        _keyval_line(depth),
        _table_line(),
        _array_table_line(),
        _comment(),
        st.just(""),
    )


def _document():
    return st.lists(_line(2), max_size=6).map(lambda ls: "\n".join(ls))


# ---------- malformed near-valid ----------

def _malformed():
    base = st.one_of(
        _keyval_line(1),
        _table_line(),
        _array_table_line(),
    )

    def drop_last(s):
        return s[:-1] if s else s

    def dup_last(s):
        return s + (s[-1] if s else "x")

    return st.one_of(
        base.map(drop_last),
        base.map(dup_last),
        st.tuples(_key(), _basic_string()).map(lambda t: t[0] + " = " + t[1][:-1]),
        st.tuples(_key(), _literal_string()).map(lambda t: t[0] + " = " + t[1][:-1]),
        st.tuples(_key(), st.just("[1, 2")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("{a = 1")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("1 2")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("true false")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _value(1)).map(lambda t: t[0] + " = " + t[1] + " stray"),
        st.tuples(_key(), st.just('"\\q"')).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("{a = 1\nb = 2}")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _value(1)).map(lambda t: t[0] + " =\n" + t[1]),
        st.tuples(_key(), st.just("1")).map(lambda t: t[0] + " = " + t[1]).map(
            lambda s: s + "\n" + s
        ),
        st.just("[]"),
        st.just("=1"),
        st.just("[["),
        st.just("]]"),
        st.just("{"),
        st.just("}"),
        st.just("."),
        st.just(","),
        st.just("[a"),
        st.just("[[a]"),
        st.just("a ="),
        st.just("a = ]"),
    )


# ---------- top-level strategy ----------

def _deep_document():
    n = st.integers(min_value=1500, max_value=2048)
    return st.one_of(
        n.map(lambda k: "a = " + "[" * k + "]" * k),
        n.map(lambda k: "a = " + "[" * k + "1" + "]" * k),
        st.integers(min_value=1, max_value=40).map(lambda k: "a = " + "{b=" * k + "1" + "}" * k),
        st.integers(min_value=1, max_value=40).map(
            lambda k: "a = " + "[" * k + "{b=1}" + "]" * k
        ),
    )


def _duplicate_doc():
    return st.tuples(_key(), _value(1)).map(
        lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]
    )


def _full_doc():
    return st.one_of(
        _document(),
        _malformed(),
        _deep_document(),
        _duplicate_doc(),
        st.just(""),
        st.just("\n"),
        st.just("\r\n"),
        st.just("# only comment"),
        st.just("# only comment\n"),
        st.just("[t]"),
        st.just("[[a]]"),
        st.just("[[a]]\n[[a]]"),
        st.just('"" = 1'),
        st.just("a = {b = 1,}"),
        st.just("a = [1, 2,]"),
        st.just("a = [\n  1,\n  2, # c\n]"),
        st.just("a = 1\r\nb = 2\r\n"),
        st.just("a = 1"),
        st.just("\t[a]\n\tb = 1"),
    )


def _no_nul(s):
    return s.replace("\x00", "")


# ---------- utf8 / string-conversion exercises (targets toml_utf8_to_ucs,
# toml_rtots, toml_rtod_ex, norm_lit_str) ----------

_UTF8_SCALARS = [
    0x000000, 0x00007F, 0x000080, 0x0007FF, 0x000800, 0x00FFFF,
    0x010000, 0x10FFFF, 0x0000E9, 0x004E2D, 0x01F600, 0x0003B1,
    0x000416, 0x002603, 0x00FFFD, 0x00007E, 0x0000A0,
]


def _utf8_escape():
    return st.sampled_from(_UTF8_SCALARS).map(lambda c: "\\u%04X" % c if c <= 0xFFFF
                                              else "\\U%08X" % c)


def _utf8_string():
    # basic strings carrying raw and escaped unicode to exercise utf8->ucs
    raw = st.sampled_from(_NONASCII)
    esc = _utf8_escape()
    body = st.lists(st.one_of(
        st.text(alphabet="abcXYZ019 _-", min_size=0, max_size=4),
        raw,
        esc,
        _esc_short,
    ), max_size=5).map("".join)
    return body.map(lambda b: '"' + b + '"')


def _utf8_literal_string():
    body = st.lists(st.one_of(
        st.text(alphabet="abcXYZ019 _-", min_size=0, max_size=4),
        st.sampled_from(_NONASCII),
    ), max_size=5).map("".join)
    return body.map(lambda b: "'" + b + "'")


def _utf8_ml_string():
    body = st.lists(st.one_of(
        st.text(alphabet="abcXYZ019 \n\t_-", min_size=0, max_size=6),
        st.sampled_from(_NONASCII),
        _utf8_escape(),
        _esc_short,
    ), max_size=5).map("".join)
    return body.map(lambda b: '"""' + b + '"""')


def _utf8_doc():
    val = st.one_of(_utf8_string(), _utf8_literal_string(), _utf8_ml_string())
    return st.tuples(_bare_key(), val).map(lambda t: t[0] + " = " + t[1])


def _datetime_doc():
    # exercise toml_rtots across edge temporal forms
    ts = st.one_of(
        _date_time(),
        st.sampled_from([
            "1979-05-27T07:32:00.000000Z",
            "1979-05-27T07:32:00+00:00",
            "1979-05-27T07:32:00-00:00",
            "1979-05-27T23:59:60Z",
            "1979-05-27T07:32",
            "1979-05-27T07",
            "1979-05",
            "1979",
            "1979-05-27T07:32:00.123456789+14:00",
            "1979-05-27T07:32:00.123456789-14:00",
            "0001-01-01T00:00:00Z",
            "9999-12-31T23:59:59.999999Z",
            "1979-05-27T07:32:00.999999999999Z",
            "1979-05-27t07:32:00",
        ]),
    )
    return st.tuples(_bare_key(), ts).map(lambda t: t[0] + " = " + t[1])


def _float_doc():
    # exercise toml_rtod_ex with tricky float shapes
    fl = st.one_of(
        _float(),
        st.sampled_from([
            "0e0", "0e+0", "0e-0", "1e0", "1E0", "1e+000", "1e-000",
            "1.0e0", "-0.0e0", "1e308", "1e-308", "1.7976931348623157e308",
            "2.2250738585072014e-308", "4.9e-324", "1e-400", "1e400",
            "123456789012345678901234567890.0",
            "0.00000000000000000000000001",
            "1_0.0_1e1_0",
            "0.0", "-0.0", "+0.0",
        ]),
    )
    return st.tuples(_bare_key(), fl).map(lambda t: t[0] + " = " + t[1])


def _norm_lit_doc():
    # exercise norm_lit_str: literal strings with quotes, backslashes, newlines
    body = st.lists(st.one_of(
        st.text(alphabet="abc\"'\\ \n\t0123", min_size=0, max_size=6),
        st.sampled_from(_NONASCII),
        st.sampled_from(["''", '""', "\\", "\\\\", "'", '"']),
    ), max_size=6).map("".join)
    lit = body.map(lambda b: "'" + b + "'")
    mlit = body.map(lambda b: "'''" + b + "'''")
    val = st.one_of(lit, mlit)
    return st.tuples(_bare_key(), val).map(lambda t: t[0] + " = " + t[1])


def _full_doc_extra():
    return st.one_of(
        _utf8_doc(),
        _datetime_doc(),
        _float_doc(),
        _norm_lit_doc(),
    )


def _no_nul(s):
    return s.replace("\x00", "")


# ---------- improved strategy ----------

def _improve_strategy():
    # Feedback: toml_utf8_to_ucs, toml_parse_file, norm_lit_str, toml_rtos
    # and toml_timestamp_at all sit at 0% branch coverage. These are only
    # reached when the parser actually descends into a *string* value and
    # calls the conversion helpers, or when a whole document is parsed via
    # toml_parse_file. So we (a) emit strings far more often than the
    # general document pool, (b) make those strings carry the exact shapes
    # that trigger the conversion helpers (raw/escaped unicode, literal
    # string normalization, temporal forms that hit toml_rtos /
    # toml_timestamp_at), and (c) emit many structurally valid multi-line
    # documents so toml_parse_file runs end-to-end.

    # --- toml_utf8_to_ucs: escaped unicode in basic strings, alone and as
    #     the entire value, plus multi-escape and truncated sequences. ---
    ucs_escape = st.one_of(
        _utf8_escape(),
        st.sampled_from(["\\u0000", "\\u007F", "\\u0080", "\\u07FF",
                         "\\u0800", "\\uD800", "\\uDFFF", "\\uFFFE",
                         "\\U0010FFFF", "\\U00110000", "\\u12", "\\u",
                         "\\U0000004", "\\uZZZZ"]),
    )
    ucs_body = st.lists(
        st.one_of(
            ucs_escape,
            _esc_short,
            st.sampled_from(_NONASCII),
            st.text(alphabet="abc019 _-", min_size=0, max_size=3),
        ),
        min_size=1, max_size=6,
    ).map("".join)
    ucs_string = ucs_body.map(lambda b: '"' + b + '"')
    ucs_ml = ucs_body.map(lambda b: '"""' + b + '"""')
    unicode_heavy = st.one_of(
        st.tuples(_bare_key(), ucs_string).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_bare_key(), ucs_ml).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_bare_key(), ucs_string).map(
            lambda t: "[t]\n" + t[0] + " = [" + t[1] + ", " + t[1] + "]"
        ),
        st.lists(
            st.tuples(_bare_key(), ucs_string).map(lambda t: t[0] + " = " + t[1]),
            min_size=1, max_size=4,
        ).map(lambda ls: "\n".join(ls)),
        _utf8_doc(),
    )

    # --- norm_lit_str: literal strings with backslashes/quotes/newlines. ---
    lit_piece = st.one_of(
        st.text(alphabet="abc\"'\\ \n\t0123", min_size=0, max_size=6),
        st.sampled_from(_NONASCII),
        st.sampled_from(["''", '""', "\\", "\\\\", "'", '"', "\\n", "\\t"]),
    )
    lit_body = st.lists(lit_piece, min_size=0, max_size=8).map("".join)
    lit = lit_body.map(lambda b: "'" + b + "'")
    mlit = lit_body.map(lambda b: "'''" + b + "'''")
    norm_lit_heavy = st.one_of(
        st.tuples(_bare_key(), lit).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_bare_key(), mlit).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_bare_key(), lit).map(
            lambda t: t[0] + " = [" + t[1] + ", " + t[1] + "]"
        ),
        st.lists(
            st.tuples(_bare_key(), st.one_of(lit, mlit)).map(
                lambda t: t[0] + " = " + t[1]
            ),
            min_size=1, max_size=4,
        ).map(lambda ls: "\n".join(ls)),
        _norm_lit_doc(),
    )

    # --- toml_rtos / toml_timestamp_at: temporal forms. Emit them as the
    #     whole value (and inside arrays) so the conversion is exercised. ---
    ts_atom = st.one_of(
        _date_time(),
        st.sampled_from([
            "1979-05-27T07:32:00Z",
            "1979-05-27T07:32:00.000000Z",
            "1979-05-27T07:32:00+00:00",
            "1979-05-27T07:32:00-00:00",
            "1979-05-27T07:32:00.123456789+14:00",
            "1979-05-27T23:59:60Z",
            "1979-05-27T07:32",
            "1979-05-27T07",
            "1979-05-27",
            "1979-05",
            "1979",
            "07:32:00",
            "07:32:00.999999999",
            "23:59:59.999999999",
            "0001-01-01T00:00:00Z",
            "9999-12-31T23:59:59.999999Z",
            "1979-05-27t07:32:00",
            "1979-05-27 07:32:00Z",
        ]),
    )
    datetime_heavy = st.one_of(
        st.tuples(_bare_key(), ts_atom).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_bare_key(), ts_atom).map(
            lambda t: "[t]\n" + t[0] + " = [" + t[1] + ", " + t[1] + "]"
        ),
        st.lists(
            st.tuples(_bare_key(), ts_atom).map(lambda t: t[0] + " = " + t[1]),
            min_size=1, max_size=4,
        ).map(lambda ls: "\n".join(ls)),
        _datetime_doc(),
    )

    # --- toml_rtod_ex: float forms. ---
    float_heavy = st.one_of(
        _float_doc(),
        st.tuples(_bare_key(), _float()).map(
            lambda t: t[0] + " = [" + t[1] + ", " + t[1] + "]"
        ),
        st.lists(_float_doc(), min_size=1, max_size=4).map(lambda ls: "\n".join(ls)),
    )

    # --- toml_parse_file: full, structurally valid documents that exercise
    #     the whole parse pipeline (tables, arrays-of-tables, arrays, inline
    #     tables, comments, string values) rather than just a single line.
    #     Build these so they *contain* string/temporal values, which is
    #     where the conversion helpers live. ---
    _string_value = st.one_of(ucs_string, ucs_ml, lit, mlit, _basic_string(),
                              _literal_string(), _ml_basic_string(), _ml_literal_string())
    _rich_kv = st.tuples(_bare_key(), _string_value).map(lambda t: t[0] + " = " + t[1])
    _rich_table = st.tuples(_bare_key(), st.lists(_rich_kv, min_size=1, max_size=4)).map(
        lambda t: "[" + t[0] + "]\n" + "\n".join(t[1])
    )
    _rich_arraytable = st.tuples(
        _bare_key(),
        st.lists(_rich_kv, min_size=1, max_size=3),
    ).map(lambda t: "[[%s]]\n%s" % (t[0], "\n".join(t[1])))
    _rich_doc = st.lists(
        st.one_of(_rich_kv, _rich_table, _rich_arraytable, _comment(), st.just("")),
        min_size=1, max_size=8,
    ).map(lambda ls: "\n".join(ls))

    full_file = st.one_of(
        _rich_doc,
        _rich_doc,
        _document(),
        _full_doc(),
        st.lists(_line(2), min_size=1, max_size=8).map(lambda ls: "\n".join(ls)),
        st.lists(
            st.one_of(_keyval_line(2), _table_line(), _array_table_line()),
            min_size=1, max_size=6,
        ).map(lambda ls: "\n".join(ls)),
    )

    return st.one_of(
        # weight the previously-uncovered conversion paths heavily
        unicode_heavy,
        unicode_heavy,
        unicode_heavy,
        norm_lit_heavy,
        norm_lit_heavy,
        norm_lit_heavy,
        datetime_heavy,
        datetime_heavy,
        datetime_heavy,
        # whole-file parsing (toml_parse_file) and float conversion
        full_file,
        full_file,
        full_file,
        float_heavy,
        _full_doc_extra(),
    )


strategy = _improve_strategy().map(_no_nul)