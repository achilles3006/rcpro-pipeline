"""Website matching on fixed HTML, no network."""

from rcpro import websites

ENT = "1041.658.155"  # TekniSafe, from the measurement sample


def test_enterprise_number_check_digits():
    assert websites.valid_kbo("1041658155")
    assert not websites.valid_kbo("0479171293")  # a mobile number, not an enterprise number


def test_phones_normalised_and_enterprise_number_skipped():
    text = "Tel +32 (0)71 15 75 15, gsm 0479/17.12.93, BTW BE 1041.658.155"
    assert websites.phones(text) == {"+3271157515", "+32479171293"}


def test_candidates_skip_free_mail_and_legal_form():
    found = websites.candidates(["TekniSafe BV"], "www.teknisafe.be", "a@gmail.com; info@teknisafe-group.be")
    assert found["teknisafe.be"] == "kbo_web"
    assert found["teknisafe-group.be"] == "kbo_email_domain"
    assert "gmail.com" not in found and "teknisafe.com" in found
    assert "wodecka.com" in websites.candidates(["Wodecka Architecture"], None, None)
    assert "lotharmorioux.com" in websites.candidates([], "www.lotharmorioux.com.", "l.morioux@lotharmorioux.com.")


def match(html, names=("TekniSafe",)):
    page = html + " filler" * 50
    return websites.match({"https://x/": page}, ENT, list(names), "Charleroi")


def test_verified_on_own_number():
    level, emails, phones = match('<a href="mailto:expert@teknisafe.be">mail</a> BE 1041.658.155 tel 071 15 75 15')
    assert (level, emails, phones) == ("verified", {"expert@teknisafe.be"}, {"+3271157515"})


def test_probable_needs_name_and_municipality():
    assert match("TekniSafe, rue X 1, 6000 Charleroi")[0] == "probable"
    assert match("TekniSafe, gevestigd in Marcinelle-Charleroi")[0] == "probable"
    assert match("TekniSafe, rue X 1, 9000 Gent")[0] == "none"
    assert match("Charleroi office of another firm")[0] == "none"
    assert match("TekniSafe, our agentcharleroi partner")[0] == "none"  # not at a word start


def test_other_enterprise_number_means_someone_else():
    assert match("TekniSafe, 6000 Charleroi, BTW BE 0841.905.461")[0] == "none"


def test_parked_page_is_none():
    assert websites.match({"https://x/": "This domain is for sale"}, ENT, ["TekniSafe"], "Charleroi")[0] == "none"
