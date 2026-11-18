# tests/ms2_fixture.py
"""One synthetic MovieLens fixture for every Milestone 2 proof (A.350).

Each proof wrote its own copy, and one lacked the rating that falls in the validation window,
so the same notebook passed one proof and failed the other. One copy cannot drift.
"""

USERS = ("1::F::1::10::48067", "2::M::56::16::70072")
MOVIES = (
    "1193::One Flew Over the Cuckoo's Nest (1975)::Drama",
    "661::James and the Giant Peach (1996)::Animation|Children's|Musical",
    "1357::Shine (1996)::Drama|Romance",
    "2355::A Bug's Life (1998)::Animation|Children's|Comedy",
)
RATINGS = (
    "1::1193::5::978300760",
    "1::661::3::978302109",
    "1::1357::4::978300100",
    "2::1357::5::978298709",
    "2::1193::4::978299000",
    "2::661::2::978301000",
    "1::2355::4::978302150",
)
