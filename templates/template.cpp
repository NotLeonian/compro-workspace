#define USE_AC_LIBRARY

#ifndef USE_AC_LIBRARY
#include <bits/stdc++.h>
#elif defined(ONLINE_JUDGE)
#include <bits/stdc++.h>

#include <atcoder/all>
#else
#include <precompile.hpp>
#endif

using namespace std;
using ll = long long;
using uint = unsigned int;
using ull = unsigned long long;

namespace atcoder {};
using namespace atcoder;

// for suisen-cp/cp-library-cpp
namespace suisen {};
using namespace suisen;

#ifdef ATCODER_MODINT_HPP
using mint = modint998244353;
#endif

#define rep_kind(a, b, c, d, e, ...) e
#define rep1(i, r) for (int i = 0; i < (int)(r); ++i)
#define rep2(i, l, r) for (int i = (l); i < (int)(r); ++i)
#define rep3(i, l, r, d) for (int i = (l); i < (int)(r); i += (d))
#define rep_r1(i, r) for (int i = (r) - 1; i >= 0; --i)
#define rep_r2(i, l, r) for (int i = (r) - 1; i >= (l); --i)
#define rep_r3(i, l, r, d) for (int i = (r) - 1; i >= (l); i -= (d))
#define rep(...) rep_kind(__VA_ARGS__, rep3, rep2, rep1)(__VA_ARGS__)
#define rep_r(...) rep_kind(__VA_ARGS__, rep_r3, rep_r2, rep_r1)(__VA_ARGS__)

#define rep_t_kind(a, b, c, d, e, f, ...) f
#define rep_t1(type, i, r) for (type i = 0; i < (type)(r); ++i)
#define rep_t2(type, i, l, r) for (type i = (l); i < (type)(r); ++i)
#define rep_t3(type, i, l, r, d) for (type i = (l); i < (type)(r); i += (d))
#define rep_t_r1(type, i, r) for (type i = (r) - 1; i >= 0; --i)
#define rep_t_r2(type, i, l, r) for (type i = (r) - 1; i >= (l); --i)
#define rep_t_r3(type, i, l, r, d) for (type i = (r) - 1; i >= (l); i -= (d))
#define rep_t(...) rep_t_kind(__VA_ARGS__, rep_t3, rep_t2, rep_t1)(__VA_ARGS__)
#define rep_t_r(...) \
    rep_t_kind(__VA_ARGS__, rep_t_r3, rep_t_r2, rep_t_r1)(__VA_ARGS__)

#define do_while_kind(a, b, c, ...) c
#define do_while1(cond) \
    for (bool is_first = true; is_first || (cond); is_first = false)
#define do_while2(cond, is_first) \
    for (bool is_first = true; is_first || (cond); is_first = false)
#define do_while(...) \
    do_while_kind(__VA_ARGS__, do_while2, do_while1)(__VA_ARGS__)

#ifdef ATCODER_MODINT_HPP
template <int M> istream &operator>>(istream &is, static_modint<M> &x) {
    ll val;
    is >> val;
    x = val;
    return is;
}
template <int M> ostream &operator<<(ostream &os, const static_modint<M> &x) {
    os << x.val();
    return os;
}

template <int id> istream &operator>>(istream &is, dynamic_modint<id> &x) {
    ll val;
    is >> val;
    x = val;
    return is;
}
template <int id>
ostream &operator<<(ostream &os, const dynamic_modint<id> &x) {
    os << x.val();
    return os;
}
#endif

inline int slot_index() {
    static int idx = ios_base::xalloc();
    return idx;
}
struct separator {
    string s;
};
inline separator sep(string s) { return {std::move(s)}; }
inline void cleanup(ios_base::event ev, ios_base &ios, int idx) {
    void *&slot = ios.pword(idx);
    if (ev == ios_base::erase_event) {
        delete static_cast<string *>(slot);
        slot = nullptr;
    } else if (ev == ios_base::copyfmt_event) {
        if (auto *p = static_cast<string *>(slot); p) {
            slot = new string(*p);
        }
    }
}
inline ostream &operator<<(ostream &os, const separator &m) {
    void *&slot = os.pword(slot_index());
    if (!slot) {
        slot = new string(m.s);
        os.register_callback(&cleanup, slot_index());
    } else {
        *static_cast<string *>(slot) = m.s;
    }
    return os;
}
inline const char *current_sep(ios_base &ios) {
    if (auto p = static_cast<string *>(ios.pword(slot_index())); p) {
        return p->c_str();
    }
    return " ";
}

template <class T>
concept char_range =
    ranges::input_range<T> && same_as<ranges::range_value_t<T>, char>;
template <class T>
concept nonstring_range =
    ranges::input_range<T> &&
    !is_convertible_v<remove_cvref_t<T>, string_view> && !char_range<T>;
template <class R>
concept writable_lvalue_range =
    is_lvalue_reference_v<ranges::range_reference_t<R>> &&
    !is_const_v<remove_reference_t<ranges::range_reference_t<R>>>;
template <class R>
concept proxy_writable_range =
    !is_lvalue_reference_v<ranges::range_reference_t<R>> &&
    !same_as<remove_cvref_t<ranges::range_reference_t<R>>,
             ranges::range_value_t<R>> &&
    default_initializable<ranges::range_value_t<R>> &&
    requires(ranges::range_reference_t<R> e, ranges::range_value_t<R> v) {
        e = std::move(v);
    };
template <class R>
concept inputtable_nonstring_range =
    nonstring_range<R> && (writable_lvalue_range<R> || proxy_writable_range<R>);

namespace io_detail {
template <class T>
concept tuple_like = requires { typename tuple_size<remove_cvref_t<T>>::type; };

template <class T> void read(istream &is, T &x);
template <class T> void write(ostream &os, T &&x);

template <class Tuple, class F> void for_each_tuple_element(Tuple &&t, F &&f) {
    [&]<size_t... I>(index_sequence<I...>) {
        using std::get;
        (f(get<I>(std::forward<Tuple>(t))), ...);
    }(make_index_sequence<tuple_size_v<remove_cvref_t<Tuple>>>{});
}

template <class T> void read(istream &is, T &x) {
    if constexpr (inputtable_nonstring_range<T>) {
        for (auto &&e : x) {
            if constexpr (writable_lvalue_range<T>) {
                read(is, e);
            } else {
                ranges::range_value_t<T> v{};
                read(is, v);
                e = std::move(v);
            }
        }
    } else if constexpr (tuple_like<T>) {
        for_each_tuple_element(x, [&](auto &e) { read(is, e); });
    } else {
        is >> x;
    }
}

template <class T> void write(ostream &os, T &&x) {
    if constexpr (nonstring_range<T>) {
        bool is_first = true;
        for (auto &&e : x) {
            if (is_first) {
                is_first = false;
            } else {
                os << current_sep(os);
            }
            write(os, std::forward<decltype(e)>(e));
        }
    } else if constexpr (tuple_like<T>) {
        bool is_first = true;
        for_each_tuple_element(std::forward<T>(x), [&](auto &&e) {
            if (is_first) {
                is_first = false;
            } else {
                os << current_sep(os);
            }
            write(os, std::forward<decltype(e)>(e));
        });
    } else {
        os << std::forward<T>(x);
    }
}
} // namespace io_detail

template <class T1, class T2>
istream &operator>>(istream &is, pair<T1, T2> &p) {
    io_detail::read(is, p);
    return is;
}
template <class T1, class T2>
ostream &operator<<(ostream &os, const pair<T1, T2> &p) {
    io_detail::write(os, p);
    return os;
}

template <class... Ts> istream &operator>>(istream &is, tuple<Ts...> &t) {
    io_detail::read(is, t);
    return is;
}
template <class... Ts> ostream &operator<<(ostream &os, const tuple<Ts...> &t) {
    io_detail::write(os, t);
    return os;
}

template <inputtable_nonstring_range T> istream &operator>>(istream &is, T &r) {
    io_detail::read(is, r);
    return is;
}
template <nonstring_range T> ostream &operator<<(ostream &os, T &&r) {
    io_detail::write(os, std::forward<T>(r));
    return os;
}

namespace incdec_detail {
template <class> inline constexpr bool always_false_v = false;

template <class T>
concept pre_incrementable = requires(T &x) { ++x; };
template <class T>
concept pre_decrementable = requires(T &x) { --x; };
template <class T>
concept tuple_like = requires { typename tuple_size<remove_cvref_t<T>>::type; };

template <class R>
concept mutable_lvalue_range =
    ranges::input_range<R> &&
    is_lvalue_reference_v<ranges::range_reference_t<R>> &&
    !is_const_v<remove_reference_t<ranges::range_reference_t<R>>>;
template <class R>
concept mutable_proxy_range =
    ranges::input_range<R> &&
    !is_lvalue_reference_v<ranges::range_reference_t<R>> &&
    !same_as<remove_cvref_t<ranges::range_reference_t<R>>,
             ranges::range_value_t<R>> &&
    constructible_from<ranges::range_value_t<R>,
                       ranges::range_reference_t<R>> &&
    requires(ranges::range_reference_t<R> e, ranges::range_value_t<R> v) {
        e = std::move(v);
    };

template <class T> void increment_impl(T &x);
template <class T> void decrement_impl(T &x);

template <class Tuple, class F> void for_each_tuple_element(Tuple &t, F &&f) {
    [&]<size_t... I>(index_sequence<I...>) {
        using std::get;
        (f(get<I>(t)), ...);
    }(make_index_sequence<tuple_size_v<remove_cvref_t<Tuple>>>{});
}

template <class T> void increment_impl(T &x) {
    if constexpr (mutable_lvalue_range<T>) {
        for (auto &&e : x) {
            increment_impl(e);
        }
    } else if constexpr (mutable_proxy_range<T>) {
        for (auto &&e : x) {
            ranges::range_value_t<T> v(e);
            increment_impl(v);
            e = std::move(v);
        }
    } else if constexpr (ranges::input_range<T>) {
        static_assert(always_false_v<T>);
    } else if constexpr (tuple_like<T>) {
        for_each_tuple_element(x, [](auto &e) { increment_impl(e); });
    } else if constexpr (pre_incrementable<T>) {
        ++x;
    } else {
        static_assert(always_false_v<T>);
    }
}

template <class T> void decrement_impl(T &x) {
    if constexpr (mutable_lvalue_range<T>) {
        for (auto &&e : x) {
            decrement_impl(e);
        }
    } else if constexpr (mutable_proxy_range<T>) {
        for (auto &&e : x) {
            ranges::range_value_t<T> v(e);
            decrement_impl(v);
            e = std::move(v);
        }
    } else if constexpr (ranges::input_range<T>) {
        static_assert(always_false_v<T>);
    } else if constexpr (tuple_like<T>) {
        for_each_tuple_element(x, [](auto &e) { decrement_impl(e); });
    } else if constexpr (pre_decrementable<T>) {
        --x;
    } else {
        static_assert(always_false_v<T>);
    }
}
} // namespace incdec_detail

template <class T> void increment(T &x) { incdec_detail::increment_impl(x); }
template <class T> void decrement(T &x) { incdec_detail::decrement_impl(x); }

template <class... T> void in(T &...args) { (cin >> ... >> args); }
template <class... T> void in_z(T &...args) {
    in(args...);
    (decrement(args), ...);
}
#define in_d(type, ...) \
    type __VA_ARGS__;   \
    in(__VA_ARGS__)
#define in_dz(type, ...) \
    type __VA_ARGS__;    \
    in_z(__VA_ARGS__)

template <bool do_flush = false, class Hd, class... Tl>
void out(const Hd &hd, const Tl &...tl) {
    cout << hd;
    if constexpr (sizeof...(Tl)) {
        (cout << ... << (cout << current_sep(cout), tl));
    }
#ifdef ONLINE_JUDGE
    cout << "\n";
    if constexpr (do_flush) {
        cout << flush;
    }
#else
    cout << endl;
#endif
}

template <class... T> void out_and_flush(const T &...args) {
    out<true>(args...);
}

template <class Hd, class... Tl> void err(const Hd &hd, const Tl &...tl) {
#ifndef ONLINE_JUDGE
    cerr << hd;
    if constexpr (sizeof...(Tl)) {
        (cerr << ... << (cerr << current_sep(cerr), tl));
    }
    cerr << "\n";
#endif
}

template <bool do_flush = false, class It1, class It2>
void out2(It1 first, It2 last) {
    for (; first != last; ++first) {
        out<do_flush>(*first);
    }
}
template <bool do_flush = false, class R> void out2(R &&range) {
    out2<do_flush>(begin(range), end(range));
}

template <class It1, class It2> void out2_and_flush(It1 first, It2 last) {
    out2<true>(first, last);
}
template <class R> void out2_and_flush(R &&range) { out2<true>(range); }

template <class It1, class It2> void err2(It1 first, It2 last) {
#ifndef ONLINE_JUDGE
    for (; first != last; ++first) {
        err(*first);
    }
#endif
}
template <class R> void err2(R &&range) {
#ifndef ONLINE_JUDGE
    err2(begin(range), end(range));
#endif
}

auto &change_out_sep(string s = string()) { return cout << sep(s); }
auto &change_err_sep(string s = string()) { return cerr << sep(s); }
void change_seps(string s = string()) {
    change_out_sep(s);
    change_err_sep(s);
}

constexpr array<int, 2> dx_2{1, 0}, dy_2{0, 1};
constexpr array<int, 4> dx{1, 0, -1, 0}, dy{0, 1, 0, -1};
constexpr array<int, 8> dx_8{1, 1, 0, -1, -1, -1, 0, 1},
    dy_8{0, 1, 1, 1, 0, -1, -1, -1};

namespace dir_detail {
template <size_t N>
constexpr auto zip(const array<int, N> &xs, const array<int, N> &ys) {
    array<pair<int, int>, N> res{};
    for (size_t i = 0; i < N; ++i) {
        res[i] = {xs[i], ys[i]};
    }
    return res;
}
}; // namespace dir_detail

constexpr auto dxdy_2 = dir_detail::zip(dx_2, dy_2);
constexpr auto dxdy = dir_detail::zip(dx, dy);
constexpr auto dxdy_8 = dir_detail::zip(dx_8, dy_8);

#define dir_2(dx_, dy_) for (auto [dx_, dy_] : dxdy_2)
#define dir(dx_, dy_) for (auto [dx_, dy_] : dxdy)
#define dir_8(dx_, dy_) for (auto [dx_, dy_] : dxdy_8)

#define all(v) (v).begin(), (v).end()
#define all_r(v) (v).rbegin(), (v).rend()
#define iter(v, l, r) ((v).begin() + l), ((v).begin() + r)

template <class T> void dedup(T &v) { v.erase(unique(all(v)), v.end()); }
template <class T> void sort_and_dedup(T &v) {
    sort(all(v));
    v.erase(unique(all(v)), v.end());
}

string_view yes() { return "Yes"; }
string_view no() { return "No"; }
string_view yn(bool cond) {
    if (cond) {
        return yes();
    } else {
        return no();
    }
}

template <class T1, class T2> bool chmin(T1 &l, const T2 &r) {
    if (r < l) {
        l = r;
        return true;
    }
    return false;
}
template <class T1, class T2> bool chmax(T1 &l, const T2 &r) {
    if (r > l) {
        l = r;
        return true;
    }
    return false;
}

template <class T>
using sum_type_t = typename conditional_t<is_integral_v<T>, common_type<T, ll>,
                                          type_identity<T>>::type;
template <class T, class U>
using sum_init_type_t =
    typename conditional_t<is_arithmetic_v<T> && is_arithmetic_v<U>,
                           common_type<sum_type_t<T>, U>,
                           type_identity<T>>::type;

template <class It> auto sum_of(It first, It last) {
    using T = typename iterator_traits<It>::value_type;
    return accumulate(first, last, sum_type_t<T>{});
}
template <class It, class U> auto sum_of(It first, It last, U init) {
    using T = typename iterator_traits<It>::value_type;
    using R = sum_init_type_t<T, U>;
    return accumulate(first, last, R(init));
}

template <class Hd1, class Hd2, class... Tl>
auto min_of(Hd1 hd1, Hd2 hd2, Tl... tl) {
    if constexpr (sizeof...(Tl) == 0) {
        return min(hd1, hd2);
    } else {
        return min(hd1, min_of(hd2, tl...));
    }
}
template <class Hd1, class Hd2, class... Tl>
auto max_of(Hd1 hd1, Hd2 hd2, Tl... tl) {
    if constexpr (sizeof...(Tl) == 0) {
        return max(hd1, hd2);
    } else {
        return max(hd1, max_of(hd2, tl...));
    }
}
template <class Hd1, class Hd2, class... Tl>
auto gcd_of(Hd1 hd1, Hd2 hd2, Tl... tl) {
    if constexpr (sizeof...(Tl) == 0) {
        return gcd(hd1, hd2);
    } else {
        return gcd(hd1, gcd_of(hd2, tl...));
    }
}
template <class Hd1, class Hd2, class... Tl>
auto lcm_of(Hd1 hd1, Hd2 hd2, Tl... tl) {
    if constexpr (sizeof...(Tl) == 0) {
        return lcm(hd1, hd2);
    } else {
        return lcm(hd1, lcm_of(hd2, tl...));
    }
}

namespace div_detail {
template <class T> using uncv_t = remove_cv_t<T>;

template <class T>
constexpr bool integral_non_bool_v =
    is_integral_v<uncv_t<T>> && !is_same_v<uncv_t<T>, bool>;

template <class T1, class T2>
using common_t = common_type_t<uncv_t<T1>, uncv_t<T2>>;

template <class T1, class T2>
using div_type_t =
    conditional_t<is_unsigned_v<common_t<T1, T2>> &&
                      (is_signed_v<uncv_t<T1>> || is_signed_v<uncv_t<T2>>),
                  make_signed_t<common_t<T1, T2>>, common_t<T1, T2>>;

template <class To, class From> constexpr bool fits_in_div_type(From x) {
    using F = uncv_t<From>;

    if constexpr (is_signed_v<To> && is_unsigned_v<F>) {
        using UTo = make_unsigned_t<To>;
        return x <= static_cast<UTo>(numeric_limits<To>::max());
    } else {
        return true;
    }
}
} // namespace div_detail

template <class T1, class T2>
constexpr pair<div_detail::div_type_t<T1, T2>, div_detail::div_type_t<T1, T2>>
floor_div_mod(T1 x, T2 y) {
    static_assert(div_detail::integral_non_bool_v<T1>);
    static_assert(div_detail::integral_non_bool_v<T2>);
    assert(y != 0);

    using T = div_detail::div_type_t<T1, T2>;
    assert(div_detail::fits_in_div_type<T>(x));
    assert(div_detail::fits_in_div_type<T>(y));

    T a = static_cast<T>(x), b = static_cast<T>(y);
    T q = a / b, r = a % b;

    if constexpr (is_signed_v<T>) {
        if (r != 0 && ((r < 0) != (b < 0))) {
            --q;
            r += b;
        }
    }

    return pair{q, r};
}
template <class T1, class T2>
constexpr div_detail::div_type_t<T1, T2> floor_div(T1 x, T2 y) {
    static_assert(div_detail::integral_non_bool_v<T1>);
    static_assert(div_detail::integral_non_bool_v<T2>);
    assert(y != 0);
    return floor_div_mod(x, y).first;
}
template <class T1, class T2>
constexpr div_detail::div_type_t<T1, T2> floor_mod(T1 x, T2 y) {
    static_assert(div_detail::integral_non_bool_v<T1>);
    static_assert(div_detail::integral_non_bool_v<T2>);
    assert(y != 0);
    return floor_div_mod(x, y).second;
}
template <class T1, class T2>
constexpr div_detail::div_type_t<T1, T2> ceil_div(T1 x, T2 y) {
    static_assert(div_detail::integral_non_bool_v<T1>);
    static_assert(div_detail::integral_non_bool_v<T2>);
    assert(y != 0);

    using T = div_detail::div_type_t<T1, T2>;

    auto [q, r] = floor_div_mod(x, y);
    return r == 0 ? q : static_cast<T>(q + T{1});
}

template <class T, size_t N>
auto make_vector(vector<size_t> &sizes, T const &x) {
    if constexpr (N == 1) {
        return vector(sizes[0], x);
    } else {
        size_t size = sizes[N - 1];
        sizes.pop_back();
        return vector(size, make_vector<T, N - 1>(sizes, x));
    }
}
template <class T, size_t N>
auto make_vector(size_t const (&sizes)[N], T const &x = T()) {
    vector<size_t> s(N);
    rep(i, N) { s[i] = sizes[N - i - 1]; }
    return make_vector<T, N>(s, x);
}
template <class T, size_t N> auto make_vector(vector<int> &sizes, T const &x) {
    if constexpr (N == 1) {
        return vector(sizes[0], x);
    } else {
        int size = sizes[N - 1];
        sizes.pop_back();
        return vector(size, make_vector<T, N - 1>(sizes, x));
    }
}
template <class T, size_t N>
auto make_vector(int const (&sizes)[N], T const &x = T()) {
    vector<int> s(N);
    rep(i, N) { s[i] = sizes[N - i - 1]; }
    return make_vector<T, N>(s, x);
}
template <class T, size_t Hd, size_t... Tl> auto make_array() {
    if constexpr (sizeof...(Tl) == 0) {
        return array<T, Hd>{};
    } else {
        return array<decltype(make_array<T, Tl...>()), Hd>{};
    }
}

constexpr int inf32 = 1'000'000'001;
constexpr ll inf64 = 2'000'000'000'000'000'001;

constexpr ull ten_powers[20] = {1,
                                10,
                                100,
                                1000,
                                10000,
                                100000,
                                1000000,
                                10000000,
                                100000000,
                                1000000000,
                                10000000000,
                                100000000000,
                                1000000000000,
                                10000000000000,
                                100000000000000,
                                1000000000000000,
                                10000000000000000,
                                100000000000000000,
                                1000000000000000000,
                                10000000000000000000ULL};

constexpr ull two_powers[64] = {1,
                                2,
                                4,
                                8,
                                16,
                                32,
                                64,
                                128,
                                256,
                                512,
                                1024,
                                2048,
                                4096,
                                8192,
                                16384,
                                32768,
                                65536,
                                131072,
                                262144,
                                524288,
                                1048576,
                                2097152,
                                4194304,
                                8388608,
                                16777216,
                                33554432,
                                67108864,
                                134217728,
                                268435456,
                                536870912,
                                1073741824,
                                2147483648,
                                4294967296,
                                8589934592,
                                17179869184,
                                34359738368,
                                68719476736,
                                137438953472,
                                274877906944,
                                549755813888,
                                1099511627776,
                                2199023255552,
                                4398046511104,
                                8796093022208,
                                17592186044416,
                                35184372088832,
                                70368744177664,
                                140737488355328,
                                281474976710656,
                                562949953421312,
                                1125899906842624,
                                2251799813685248,
                                4503599627370496,
                                9007199254740992,
                                18014398509481984,
                                36028797018963968,
                                72057594037927936,
                                144115188075855872,
                                288230376151711744,
                                576460752303423488,
                                1152921504606846976,
                                2305843009213693952,
                                4611686018427387904,
                                9223372036854775808ULL};

template <class T, template <class...> class Heap = priority_queue>
using min_heap = Heap<T, vector<T>, greater<>>;

template <class S, S e> constexpr S e_const() { return e; }
template <class S1, S1 e1, class S2, S2 e2>
constexpr pair<S1, S2> e_const_pair() {
    return {e1, e2};
}
template <class S> S op_min(S a, S b) { return min(a, b); }
template <class S> S op_max(S a, S b) { return max(a, b); }
template <class S> pair<S, S> op_minmax(pair<S, S> a, pair<S, S> b) {
    auto [a1, a2] = a;
    auto [b1, b2] = b;
    return {min(a1, b1), max(a2, b2)};
}
template <class S> S op_add(S a, S b) { return a + b; }
template <class S1, class S2>
pair<S1, S2> op_add_pair(pair<S1, S2> a, pair<S1, S2> b) {
    auto [a1, a2] = a;
    auto [b1, b2] = b;
    return {a1 + b1, a2 + b2};
}
template <class F1, class F2, class S> S mapping_affine(pair<F1, F2> f, S x) {
    auto [a, b] = f;
    return a * x + b;
}
template <class F1, class F2, class S>
pair<S, S> mapping_minmax_affine(pair<F1, F2> f, pair<S, S> x) {
    auto [a, b] = f;
    auto [l, r] = x;
    if (a >= 0) {
        return {a * l + b, a * r + b};
    } else {
        return {a * r + b, a * l + b};
    }
}
template <class F1, class F2, class S1, class S2>
pair<S1, S2> mapping_len_and_affine(pair<F1, F2> f, pair<S1, S2> x) {
    auto [a, b] = f;
    auto [x1, x2] = x;
    return {x1, a * x2 + b * x1};
}
template <class F1, class F2>
pair<F1, F2> composition_affine(pair<F1, F2> f, pair<F1, F2> g) {
    auto [a_f, b_f] = f;
    auto [a_g, b_g] = g;
    return {a_f * a_g, a_f * b_g + b_f};
}

template <class M, class S, S e> constexpr M mint_const() { return M(e); }
template <class M1, class S1, S1 e1, class M2, class S2, S2 e2>
constexpr pair<M1, M2> mint_pair() {
    return {M1(e1), M2(e2)};
}

#ifdef ATCODER_SEGTREE_HPP
template <class S, S e>
using segtree_min = segtree<S, op_min<S>, e_const<S, e>>;
template <class S, S e>
using segtree_max = segtree<S, op_max<S>, e_const<S, e>>;
template <class S> using segtree_add = segtree<S, op_add<S>, e_const<S, 0>>;
template <class M, class S = int>
using segtree_add_mint = segtree<M, op_add<M>, mint_const<M, S, 0>>;
#endif

#ifdef ATCODER_LAZYSEGTREE_HPP
// f の傾きが非負であることを仮定する
template <class S, S e>
using lazy_segtree_min =
    lazy_segtree<S, op_min<S>, e_const<S, e>, pair<S, S>,
                 mapping_affine<S, S, S>, composition_affine<S, S>,
                 e_const_pair<S, 1, S, 0>>;
// f の傾きが非負であることを仮定する
template <class S, S e>
using lazy_segtree_max =
    lazy_segtree<S, op_max<S>, e_const<S, e>, pair<S, S>,
                 mapping_affine<S, S, S>, composition_affine<S, S>,
                 e_const_pair<S, 1, S, 0>>;
template <class S, S e_min, S e_max>
using lazy_segtree_minmax =
    lazy_segtree<pair<S, S>, op_minmax<S>, e_const_pair<S, e_min, S, e_max>,
                 pair<S, S>, mapping_minmax_affine<S, S, S>,
                 composition_affine<S, S>, e_const_pair<S, 1, S, 0>>;
template <class S>
using lazy_segtree_add =
    lazy_segtree<pair<int, S>, op_add_pair<int, S>, e_const_pair<int, 0, S, 0>,
                 pair<S, S>, mapping_len_and_affine<S, S, int, S>,
                 composition_affine<S, S>, e_const_pair<S, 1, S, 0>>;
template <class M, class S = int>
using lazy_segtree_add_mint =
    lazy_segtree<pair<int, M>, op_add_pair<int, M>,
                 mint_pair<int, int, 0, M, S, 0>, pair<M, M>,
                 mapping_len_and_affine<M, M, int, M>, composition_affine<M, M>,
                 mint_pair<M, S, 1, M, S, 0>>;
#endif

void solve() {}

int main(void) {
    cin.tie(nullptr);
    ios::sync_with_stdio(false);
    cout << fixed << setprecision(15);
    cerr << fixed << setprecision(15);
    int t = 1;
    // in(t);
    while (t--) {
        solve();
    }
    return 0;
}
