// ason_py.cpp — C++ pybind11 extension (optimized v2)
//   encode, decode, encodePretty, encodeBinary, decodeBinary
//
// Optimisations over v1:
//   - Schema parsed & cached globally; field keys interned once (PyUnicode_InternInPlace)
//   - No py::str in global cache → no crash on interpreter shutdown
//   - Float via snprintf, LE via memcpy, dicts via _PyDict_NewPresized + PyDict_SetItem
//   - Output buffers pre-reserved; binary decode zero-copy (PyBytes_AsStringAndSize)
//
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
[[noreturn]] static void ason_throw(const char* msg) {
    throw std::runtime_error(std::string("ason: ") + msg);
}
[[noreturn]] static void ason_throw(const std::string& msg) {
    throw std::runtime_error("ason: " + msg);
}

// ---------------------------------------------------------------------------
// Field types
// ---------------------------------------------------------------------------
enum class FieldType : uint8_t {
    Int, Uint, Float_, Bool, Str,
    IntOpt, UintOpt, FloatOpt, BoolOpt, StrOpt
};
static constexpr bool is_optional(FieldType t) noexcept { return (uint8_t)t >= 5; }
static constexpr FieldType base_type(FieldType t) noexcept {
    return is_optional(t) ? (FieldType)((uint8_t)t - 5) : t;
}

// ---------------------------------------------------------------------------
// CachedSchema — interned PyObject* keys, no py::str (no Py_DECREF at exit)
// ---------------------------------------------------------------------------
struct CachedField {
    std::string name;
    FieldType   type;
    PyObject*   key;   // interned Python str; owned by Python's interning table
};

struct CachedSchema {
    std::vector<CachedField> fields;
    bool                     is_slice{false};
    std::string              header;
};

// ---------------------------------------------------------------------------
// Schema parser
// ---------------------------------------------------------------------------
static CachedSchema parse_schema(const std::string& s) {
    const char* p   = s.c_str();
    const char* end = p + s.size();
    CachedSchema sc;

    while (p < end && (unsigned char)*p <= ' ') ++p;
    if (p < end && *p == '[') { sc.is_slice = true; ++p; }
    while (p < end && (unsigned char)*p <= ' ') ++p;
    if (p >= end || *p != '{') ason_throw("schema must start with '{'");
    ++p;

    while (p < end) {
        while (p < end && (unsigned char)*p <= ' ') ++p;
        if (p >= end || *p == '}') { if (p < end) ++p; break; }

        const char* ns = p;
        while (p < end && *p != ':' && *p != '}' && (unsigned char)*p > ' ') ++p;
        std::string name(ns, p - ns);

        while (p < end && (unsigned char)*p <= ' ') ++p;
        if (p >= end || *p != ':') ason_throw("expected ':' after field name");
        ++p;
        while (p < end && (unsigned char)*p <= ' ') ++p;

        const char* ts = p;
        while (p < end && *p != ',' && *p != '}' && (unsigned char)*p > ' ') ++p;
        std::string tname(ts, p - ts);
        bool opt = !tname.empty() && tname.back() == '?';
        if (opt) tname.pop_back();

        FieldType ft;
        if      (tname == "int")   ft = opt ? FieldType::IntOpt   : FieldType::Int;
        else if (tname == "uint")  ft = opt ? FieldType::UintOpt  : FieldType::Uint;
        else if (tname == "float") ft = opt ? FieldType::FloatOpt : FieldType::Float_;
        else if (tname == "bool")  ft = opt ? FieldType::BoolOpt  : FieldType::Bool;
        else if (tname == "str")   ft = opt ? FieldType::StrOpt   : FieldType::Str;
        else ason_throw("unknown type '" + tname + "' for field '" + name + "'");

        // Intern the key: Python's interning table holds the reference; no DECREF needed
        PyObject* key = PyUnicode_FromStringAndSize(name.data(), (Py_ssize_t)name.size());
        if (!key) throw std::bad_alloc();
        PyUnicode_InternInPlace(&key);
        Py_DECREF(key);  // release our ref; interning table still holds it

        sc.fields.push_back({std::move(name), ft, key});

        while (p < end && (unsigned char)*p <= ' ') ++p;
        if (p < end && *p == ',') ++p;
    }
    if (sc.is_slice) {
        while (p < end && (unsigned char)*p <= ' ') ++p;
        if (p >= end || *p != ']') ason_throw("expected ']'");
        ++p;
    }

    std::string hdr;
    hdr.reserve(sc.fields.size() * 12 + 4);
    if (sc.is_slice) hdr += '[';
    hdr += '{';
    for (size_t i = 0; i < sc.fields.size(); ++i) {
        if (i) hdr += ", ";
        hdr += sc.fields[i].name; hdr += ':';
        switch (sc.fields[i].type) {
            case FieldType::Int:      hdr += "int";    break;
            case FieldType::Uint:     hdr += "uint";   break;
            case FieldType::Float_:   hdr += "float";  break;
            case FieldType::Bool:     hdr += "bool";   break;
            case FieldType::Str:      hdr += "str";    break;
            case FieldType::IntOpt:   hdr += "int?";   break;
            case FieldType::UintOpt:  hdr += "uint?";  break;
            case FieldType::FloatOpt: hdr += "float?"; break;
            case FieldType::BoolOpt:  hdr += "bool?";  break;
            case FieldType::StrOpt:   hdr += "str?";   break;
        }
    }
    hdr += '}';
    if (sc.is_slice) hdr += ']';
    sc.header = std::move(hdr);
    return sc;
}

// ---------------------------------------------------------------------------
// Global schema cache
// ---------------------------------------------------------------------------
static std::mutex                                    g_schema_mutex;
static std::unordered_map<std::string, CachedSchema> g_schema_cache;

static const CachedSchema& get_schema(const std::string& s) {
    std::lock_guard<std::mutex> lk(g_schema_mutex);
    auto it = g_schema_cache.find(s);
    if (it != g_schema_cache.end()) return it->second;
    auto [ins, ok] = g_schema_cache.emplace(s, parse_schema(s));
    return ins->second;
}

// ---------------------------------------------------------------------------
// Float formatting (snprintf, no heap)
// ---------------------------------------------------------------------------
static void append_float(std::string& out, double v) {
    if (std::isnan(v))  { out += "nan"; return; }
    if (std::isinf(v))  { out += (v > 0 ? "inf" : "-inf"); return; }
    char buf[32];
    double intpart;
    if (std::modf(v, &intpart) == 0.0 && v >= -1e15 && v <= 1e15) {
        int len = std::snprintf(buf, sizeof(buf), "%.1f", v);
        out.append(buf, len);
        return;
    }
    int len = std::snprintf(buf, sizeof(buf), "%.17g", v);
    std::string_view sv(buf, len);
    if (sv.find('.') == std::string_view::npos && sv.find('e') == std::string_view::npos)
        out.append(buf, len), out += ".0";
    else
        out.append(buf, len);
}

// ---------------------------------------------------------------------------
// String quoting
// ---------------------------------------------------------------------------
static bool needs_quoting(const char* s, size_t n) noexcept {
    if (n == 0) return true;
    if ((unsigned char)s[0] <= ' ' || (unsigned char)s[n-1] <= ' ') return true;
    bool all_num = true;
    size_t ni = (s[0] == '-') ? 1 : 0;
    if (ni >= n) all_num = false;
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)s[i];
        if (c < 32 || c == ',' || c == '(' || c == ')' ||
            c == '[' || c == ']' || c == '"' || c == '\\') return true;
        if (all_num && i >= ni && !(c >= '0' && c <= '9') && c != '.') all_num = false;
    }
    if (all_num && n > ni) return true;
    if (n == 4 && s[0]=='t'&&s[1]=='r'&&s[2]=='u'&&s[3]=='e') return true;
    if (n == 5 && s[0]=='f'&&s[1]=='a'&&s[2]=='l'&&s[3]=='s') return true;
    return false;
}

static void append_escaped(std::string& out, const char* s, size_t n) {
    if (!needs_quoting(s, n)) { out.append(s, n); return; }
    out += '"';
    for (size_t i = 0; i < n; ++i) {
        char c = s[i];
        if      (c == '"')  out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\t') out += "\\t";
        else                out += c;
    }
    out += '"';
}

// ---------------------------------------------------------------------------
// LE helpers (memcpy = single instruction on x86/arm)
// ---------------------------------------------------------------------------
static inline void push_le32(std::vector<uint8_t>& b, uint32_t v) {
    size_t pos = b.size(); b.resize(pos + 4);
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    std::memcpy(b.data() + pos, &v, 4);
#else
    uint8_t* d = b.data()+pos; d[0]=v;d[1]=v>>8;d[2]=v>>16;d[3]=v>>24;
#endif
}
static inline void push_le64(std::vector<uint8_t>& b, uint64_t v) {
    size_t pos = b.size(); b.resize(pos + 8);
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    std::memcpy(b.data() + pos, &v, 8);
#else
    uint8_t* d = b.data()+pos; for(int i=0;i<8;i++) d[i]=(v>>(8*i))&0xFF;
#endif
}
static inline uint32_t read_le32(const uint8_t*& p, const uint8_t* end) {
    if (end - p < 4) ason_throw("binary: need 4 bytes");
    uint32_t v; std::memcpy(&v, p, 4); p += 4;
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
    v = __builtin_bswap32(v);
#endif
    return v;
}
static inline uint64_t read_le64(const uint8_t*& p, const uint8_t* end) {
    if (end - p < 8) ason_throw("binary: need 8 bytes");
    uint64_t v; std::memcpy(&v, p, 8); p += 8;
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
    v = __builtin_bswap64(v);
#endif
    return v;
}

// ---------------------------------------------------------------------------
// Text encode — raw CPython API (no pybind11 wrappers in hot path)
// ---------------------------------------------------------------------------
static void encode_value(std::string& out, PyObject* val, FieldType ft) {
    if (is_optional(ft)) {
        if (val == Py_None) return;
        ft = base_type(ft);
    }
    switch (ft) {
        case FieldType::Int:
            out += std::to_string(PyLong_AsLongLong(val)); break;
        case FieldType::Uint:
            out += std::to_string(PyLong_AsUnsignedLongLong(val)); break;
        case FieldType::Float_:
            append_float(out, PyFloat_AsDouble(val)); break;
        case FieldType::Bool:
            out += (val == Py_True) ? "true" : "false"; break;
        case FieldType::Str: {
            Py_ssize_t sz;
            const char* s = PyUnicode_AsUTF8AndSize(val, &sz);
            if (!s) ason_throw("str encode failed");
            append_escaped(out, s, (size_t)sz);
            break;
        }
        default: break;
    }
}

// ---------------------------------------------------------------------------
// Binary encode
// ---------------------------------------------------------------------------
static void encode_bin_value(std::vector<uint8_t>& buf, PyObject* val, FieldType ft) {
    if (is_optional(ft)) {
        if (val == Py_None) { buf.push_back(0); return; }
        buf.push_back(1);
        ft = base_type(ft);
    }
    switch (ft) {
        case FieldType::Int:    push_le64(buf, (uint64_t)PyLong_AsLongLong(val)); break;
        case FieldType::Uint:   push_le64(buf, PyLong_AsUnsignedLongLong(val));   break;
        case FieldType::Float_: {
            double d = PyFloat_AsDouble(val);
            uint64_t b; std::memcpy(&b, &d, 8);
            push_le64(buf, b); break;
        }
        case FieldType::Bool:
            buf.push_back(val == Py_True ? 1 : 0); break;
        case FieldType::Str: {
            Py_ssize_t sz;
            const char* s = PyUnicode_AsUTF8AndSize(val, &sz);
            if (!s) ason_throw("str encode failed");
            push_le32(buf, (uint32_t)sz);
            const uint8_t* u = (const uint8_t*)s;
            buf.insert(buf.end(), u, u + sz);
            break;
        }
        default: break;
    }
}

// ---------------------------------------------------------------------------
// encode(obj, schema) → str
// ---------------------------------------------------------------------------
static std::string ason_encode(py::object obj, const std::string& schema_str) {
    const CachedSchema& sc = get_schema(schema_str);
    std::string out;
    size_t nf = sc.fields.size();

    if (sc.is_slice) {
        PyObject* lst = obj.ptr();
        Py_ssize_t n  = PyList_GET_SIZE(lst);
        out.reserve(sc.header.size() + 2 + (size_t)n * (nf * 12 + 6));
        out += sc.header; out += ":\n";
        for (Py_ssize_t i = 0; i < n; ++i) {
            PyObject* rec = PyList_GET_ITEM(lst, i);
            out += '(';
            for (size_t j = 0; j < nf; ++j) {
                if (j) out += ',';
                PyObject* val = PyDict_GetItem(rec, sc.fields[j].key);
                encode_value(out, val ? val : Py_None, sc.fields[j].type);
            }
            out += ')';
            if (i + 1 < n) out += ',';
            out += '\n';
        }
    } else {
        PyObject* rec = obj.ptr();
        out.reserve(sc.header.size() + 2 + nf * 16);
        out += sc.header; out += ":\n(";
        for (size_t j = 0; j < nf; ++j) {
            if (j) out += ',';
            PyObject* val = PyDict_GetItem(rec, sc.fields[j].key);
            encode_value(out, val ? val : Py_None, sc.fields[j].type);
        }
        out += ")\n";
    }
    return out;
}

// ---------------------------------------------------------------------------
// encodePretty(obj, schema) → str
// ---------------------------------------------------------------------------
static std::string ason_encode_pretty(py::object obj, const std::string& schema_str) {
    const CachedSchema& sc = get_schema(schema_str);
    std::string out;
    size_t nf = sc.fields.size();

    if (sc.is_slice) {
        PyObject* lst = obj.ptr();
        Py_ssize_t n  = PyList_GET_SIZE(lst);
        out.reserve(sc.header.size() + 2 + (size_t)n * (nf * 14 + 10));
        out += sc.header; out += ":\n";
        for (Py_ssize_t i = 0; i < n; ++i) {
            PyObject* rec = PyList_GET_ITEM(lst, i);
            out += "    (";
            for (size_t j = 0; j < nf; ++j) {
                if (j) out += ", ";
                PyObject* val = PyDict_GetItem(rec, sc.fields[j].key);
                encode_value(out, val ? val : Py_None, sc.fields[j].type);
            }
            out += ')';
            if (i + 1 < n) out += ',';
            out += '\n';
        }
    } else {
        PyObject* rec = obj.ptr();
        out.reserve(sc.header.size() + 2 + nf * 18);
        out += sc.header; out += ":\n    (";
        for (size_t j = 0; j < nf; ++j) {
            if (j) out += ", ";
            PyObject* val = PyDict_GetItem(rec, sc.fields[j].key);
            encode_value(out, val ? val : Py_None, sc.fields[j].type);
        }
        out += ")\n";
    }
    return out;
}

// ---------------------------------------------------------------------------
// Text decode helpers
// ---------------------------------------------------------------------------
static inline void skip_ws(const char*& p, const char* end) noexcept {
    while (p < end && (unsigned char)*p <= ' ') ++p;
}

// Returns new reference (always)
static PyObject* decode_value(const char*& p, const char* end, FieldType ft, std::string& tmp) {
    skip_ws(p, end);
    if (is_optional(ft)) {
        if (p >= end || *p == ',' || *p == ')') { Py_INCREF(Py_None); return Py_None; }
        ft = base_type(ft);
    }
    switch (ft) {
        case FieldType::Int: {
            char* ep; long long v = std::strtoll(p, &ep, 10);
            if (ep == p) ason_throw("expected int");
            p = ep; return PyLong_FromLongLong(v);
        }
        case FieldType::Uint: {
            char* ep; unsigned long long v = std::strtoull(p, &ep, 10);
            if (ep == p) ason_throw("expected uint");
            p = ep; return PyLong_FromUnsignedLongLong(v);
        }
        case FieldType::Float_: {
            if (end-p>=3&&p[0]=='n'&&p[1]=='a'&&p[2]=='n') { p+=3; return PyFloat_FromDouble(std::numeric_limits<double>::quiet_NaN()); }
            if (end-p>=3&&p[0]=='i'&&p[1]=='n'&&p[2]=='f') { p+=3; return PyFloat_FromDouble( std::numeric_limits<double>::infinity()); }
            if (end-p>=4&&p[0]=='-'&&p[1]=='i'&&p[2]=='n'&&p[3]=='f') { p+=4; return PyFloat_FromDouble(-std::numeric_limits<double>::infinity()); }
            char* ep; double v = std::strtod(p, &ep);
            if (ep == p) ason_throw("expected float");
            p = ep; return PyFloat_FromDouble(v);
        }
        case FieldType::Bool:
            if (end-p>=4&&p[0]=='t'&&p[1]=='r'&&p[2]=='u'&&p[3]=='e')  { p+=4; Py_INCREF(Py_True);  return Py_True;  }
            if (end-p>=5&&p[0]=='f'&&p[1]=='a'&&p[2]=='l'&&p[3]=='s')  { p+=5; Py_INCREF(Py_False); return Py_False; }
            ason_throw("expected bool");
        case FieldType::Str: {
            if (p < end && *p == '"') {
                ++p; tmp.clear();
                while (p < end && *p != '"') {
                    if (*p == '\\') {
                        ++p; if (p >= end) ason_throw("unexpected end in escape");
                        switch (*p) {
                            case '"': tmp+='"'; break; case '\\': tmp+='\\'; break;
                            case 'n': tmp+='\n'; break; case 't': tmp+='\t'; break;
                            default:  tmp+=*p;
                        }
                    } else tmp += *p;
                    ++p;
                }
                if (p >= end) ason_throw("unterminated string");
                ++p;
                return PyUnicode_FromStringAndSize(tmp.data(), (Py_ssize_t)tmp.size());
            } else {
                const char* s = p;
                while (p < end && *p != ',' && *p != ')' && *p != '\n' && *p != '\r') ++p;
                return PyUnicode_FromStringAndSize(s, (Py_ssize_t)(p - s));
            }
        }
        default: ason_throw("internal error");
    }
}

// Returns new dict reference
static PyObject* decode_tuple(const char*& p, const char* end, const CachedSchema& sc, std::string& tmp) {
    skip_ws(p, end);
    if (p >= end || *p != '(') ason_throw("expected '('");
    ++p;

    PyObject* rec = _PyDict_NewPresized((Py_ssize_t)sc.fields.size());
    if (!rec) throw std::bad_alloc();

    for (size_t i = 0; i < sc.fields.size(); ++i) {
        if (i) {
            skip_ws(p, end);
            if (p >= end || *p != ',') { Py_DECREF(rec); ason_throw("expected ','"); }
            ++p;
        }
        PyObject* val = decode_value(p, end, sc.fields[i].type, tmp);
        if (!val) { Py_DECREF(rec); throw py::error_already_set(); }
        PyDict_SetItem(rec, sc.fields[i].key, val);
        Py_DECREF(val);  // dict now owns it
    }
    skip_ws(p, end);
    if (p >= end || *p != ')') { Py_DECREF(rec); ason_throw("expected ')'"); }
    ++p;
    return rec;
}

// ---------------------------------------------------------------------------
// decode(text) → dict | list[dict]
// ---------------------------------------------------------------------------
static py::object ason_decode(const std::string& text) {
    const char* p   = text.c_str();
    const char* end = p + text.size();

    skip_ws(p, end);
    const char* sc_start = p;
    int depth = 0;
    while (p < end) {
        char c = *p++;
        if (c == '{' || c == '[') ++depth;
        else if ((c == '}' || c == ']') && --depth == 0) break;
    }
    std::string sc_str(sc_start, p - sc_start);
    const CachedSchema& schema = get_schema(sc_str);

    skip_ws(p, end);
    if (p >= end || *p != ':') ason_throw("expected ':'");
    ++p;

    std::string tmp;  // buffer for string unescaping

    if (schema.is_slice) {
        PyObject* lst = PyList_New(0);
        if (!lst) throw std::bad_alloc();
        while (true) {
            while (p < end && ((unsigned char)*p <= ' ' || *p == ',')) ++p;
            if (p >= end || *p != '(') break;
            PyObject* rec = decode_tuple(p, end, schema, tmp);
            PyList_Append(lst, rec);
            Py_DECREF(rec);
        }
        return py::reinterpret_steal<py::object>(lst);
    } else {
        skip_ws(p, end);
        PyObject* rec = decode_tuple(p, end, schema, tmp);
        if (!rec) throw py::error_already_set();
        // Reject trailing rows after a single-struct schema
        const char* tp = p;
        while (tp < end && ((unsigned char)*tp <= ' ' || *tp == ',')) ++tp;
        if (tp < end && *tp == '(') { Py_DECREF(rec); ason_throw("trailing rows not allowed for struct schema"); }
        return py::reinterpret_steal<py::object>(rec);
    }
}

// ---------------------------------------------------------------------------
// encodeBinary(obj, schema) → bytes
// ---------------------------------------------------------------------------
static py::bytes ason_encode_binary(py::object obj, const std::string& schema_str) {
    const CachedSchema& sc = get_schema(schema_str);
    std::vector<uint8_t> buf;

    if (sc.is_slice) {
        PyObject* lst = obj.ptr();
        Py_ssize_t n  = PyList_GET_SIZE(lst);
        buf.reserve(4 + (size_t)n * sc.fields.size() * 10);
        push_le32(buf, (uint32_t)n);
        for (Py_ssize_t i = 0; i < n; ++i) {
            PyObject* rec = PyList_GET_ITEM(lst, i);
            for (auto& f : sc.fields) {
                PyObject* val = PyDict_GetItem(rec, f.key);
                encode_bin_value(buf, val ? val : Py_None, f.type);
            }
        }
    } else {
        PyObject* rec = obj.ptr();
        buf.reserve(sc.fields.size() * 10);
        for (auto& f : sc.fields) {
            PyObject* val = PyDict_GetItem(rec, f.key);
            encode_bin_value(buf, val ? val : Py_None, f.type);
        }
    }
    return py::bytes((const char*)buf.data(), buf.size());
}

// ---------------------------------------------------------------------------
// Binary decode — decode one record into pre-allocated dict
// ---------------------------------------------------------------------------
static inline PyObject* decode_bin_field(const uint8_t*& p, const uint8_t* end, FieldType ft) {
    if (is_optional(ft)) {
        uint8_t tag = *p++;
        if (tag == 0) { Py_INCREF(Py_None); return Py_None; }
        ft = base_type(ft);
    }
    switch (ft) {
        case FieldType::Int: {
            uint64_t b = read_le64(p, end); int64_t v; std::memcpy(&v, &b, 8);
            return PyLong_FromLongLong(v);
        }
        case FieldType::Uint:
            return PyLong_FromUnsignedLongLong(read_le64(p, end));
        case FieldType::Float_: {
            uint64_t b = read_le64(p, end); double v; std::memcpy(&v, &b, 8);
            return PyFloat_FromDouble(v);
        }
        case FieldType::Bool: {
            PyObject* r = (*p++ != 0) ? Py_True : Py_False;
            Py_INCREF(r); return r;
        }
        case FieldType::Str: {
            uint32_t l = read_le32(p, end);
            if ((size_t)(end - p) < l) ason_throw("binary short read");
            PyObject* r = PyUnicode_FromStringAndSize((const char*)p, l);
            p += l; return r;
        }
        default: Py_INCREF(Py_None); return Py_None;
    }
}

static py::object ason_decode_binary(py::bytes data, const std::string& schema_str) {
    const CachedSchema& sc = get_schema(schema_str);

    char* raw_ptr; Py_ssize_t raw_len;
    if (PyBytes_AsStringAndSize(data.ptr(), &raw_ptr, &raw_len) < 0)
        ason_throw("invalid bytes object");

    const uint8_t* p   = (const uint8_t*)raw_ptr;
    const uint8_t* end = p + raw_len;

    if (sc.is_slice) {
        uint32_t count = read_le32(p, end);
        PyObject* lst = PyList_New((Py_ssize_t)count);
        if (!lst) throw std::bad_alloc();
        for (uint32_t i = 0; i < count; ++i) {
            PyObject* rec = _PyDict_NewPresized((Py_ssize_t)sc.fields.size());
            if (!rec) { Py_DECREF(lst); throw std::bad_alloc(); }
            for (auto& f : sc.fields) {
                PyObject* val = decode_bin_field(p, end, f.type);
                PyDict_SetItem(rec, f.key, val);
                Py_DECREF(val);
            }
            PyList_SET_ITEM(lst, (Py_ssize_t)i, rec);  // steals ref
        }
        if (p != end) { Py_DECREF(lst); ason_throw("trailing binary data"); }
        return py::reinterpret_steal<py::object>(lst);
    } else {
        PyObject* rec = _PyDict_NewPresized((Py_ssize_t)sc.fields.size());
        if (!rec) throw std::bad_alloc();
        for (auto& f : sc.fields) {
            PyObject* val = decode_bin_field(p, end, f.type);
            PyDict_SetItem(rec, f.key, val);
            Py_DECREF(val);
        }
        if (p != end) { Py_DECREF(rec); ason_throw("trailing binary data"); }
        return py::reinterpret_steal<py::object>(rec);
    }
}

// ---------------------------------------------------------------------------
// Module
// ---------------------------------------------------------------------------
PYBIND11_MODULE(ason, m) {
    m.doc() = "ASON — Array-Schema Object Notation (optimized C++ pybind11 extension).";
    py::register_exception<std::runtime_error>(m, "AsonError");

    m.def("encode",       &ason_encode,        py::arg("obj"), py::arg("schema"));
    m.def("decode",       &ason_decode,        py::arg("text"));
    m.def("encodePretty", &ason_encode_pretty, py::arg("obj"), py::arg("schema"));
    m.def("encodeBinary", &ason_encode_binary, py::arg("obj"), py::arg("schema"));
    m.def("decodeBinary", &ason_decode_binary, py::arg("data"), py::arg("schema"));
}
