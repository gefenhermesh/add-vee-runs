#!/usr/bin/env python3
"""Jobs for the sponsor: remote SEO roles he can apply to from Costa Rica. Part of the daily jobs run (SCOUT.md ->
Daily SEO-jobs route, step 0). Deterministic fetch + screening; the jobs-scout session makes the final call.

Sponsor's request (2026-11-24): every day, the last 24 hours of
  - LinkedIn, "search engine optimization", remote, Latin America;
  - LinkedIn, same, remote, United States: only posts that don't need US work authorization;
  - LinkedIn, same, remote, Europe: only posts that might work with someone in Costa Rica;
  - seojobs.com, last 24 hours, same rules (US posts without work authorization; open to LATAM);
  - no Asia. A daily message with the posts worth applying to and links to apply.

  python campaign/scout/seeker.py fetch            -> campaign/scout/seeker/<date>.json (+ coverage lines)
  python campaign/scout/seeker.py digest <date>    -> campaign/scout/seeker/<date>.md, from the session's verdicts

How a post is screened (`screen()`): the description is read from LinkedIn's public job page (free, no login) and
checked for (a) phrases that require US or EU work authorization or residence, (b) phrases that open the role to
LATAM, the Americas, anywhere, or contractors, (c) Asia locations, (d) junior/intern seniority. The result is a
`lean` (apply / maybe / skip) with the matched sentences quoted, so the session can confirm or overturn it.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "seeker"
SEEN = OUT / "seen.jsonl"
FEEDBACK = HERE / "seeker_feedback.json"   # the sponsor's corrections, applied to every later day
sys.path.insert(0, str(HERE))
import jobs  # noqa: E402  (LinkedIn card parser, paid Web Unlocker fetch with cap + log)
import readers as R  # noqa: E402  (page text)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
QUERY = "search engine optimization"
REGIONS = {"latam": "Latin America", "us": "United States", "europe": "Europe"}
SEOJOBS = False   # sponsor, 2026-11-25: seojobs.com dropped from the daily run (paid pages; its posts reach LinkedIn,
#                    where his own LinkedIn posts search finds them). Set True to read it again.
MAX_DETAILS = 200          # 3 searches x 60 cards, before de-duplication

LATAM = r"latin america|latam|south america|central america|costa rica|the americas|americas|north and south america"
POS = re.compile(rf"\b({LATAM}|worldwide|anywhere in the world|work from anywhere|globally remote|remote[- ]first,? global|"
                 r"any (country|location)|independent contractor|as an? contractor|contractor (role|position|basis|agreement)|"
                 r"type of contract: contractor|via deel|remote\.com|(us|u\.s\.|american|est|pst|cst) time ?zones?|"
                 r"overlap with (est|pst|cst|us|north american))\b", re.I)
NEG_US = re.compile(r"\b(authori[sz]ed to work in the (united states|u\.?s\.?a?)|(u\.?s\.?|united states) work authori[sz]ation|"
                    r"(u\.?s\.?|united states) citizen|green card|w-?2\b|eligible to work in the (united states|u\.?s\.?)|"
                    r"security clearance|(not|unable to|cannot|can't|won't) (provide |offer )?(visa )?sponsor|"
                    r"without (the need for )?(visa )?sponsorship|no (visa )?sponsorship|"
                    r"(must|need to|required to) (reside|live|be located|be based) (in|within) the (united states|u\.?s\.?)|"
                    r"(us|u\.s\.)-based( candidates)?( only)?|remote \(u\.?s\.?( only| based)?\)|"
                    r"within the (united states|u\.?s\.?|continental us))\b", re.I)
NEG_EU = re.compile(r"\b((right|eligib\w*|authori[sz]ed|permit) to work in (the )?(uk|eu|european union|europe|eea|[A-Z][a-z]+)|"
                    r"(must|need to|required to) (reside|live|be located|be based) in (the )?(uk|eu|europe|[A-Z][a-z]+)|"
                    r"eu (citizens?|work permit)|based in (the )?(uk|eu|europe) only|(uk|eu|cet|cest|gmt) (hours|time ?zone) only)\b", re.I)
ASIA = re.compile(r"\b(india|philippines|pakistan|bangladesh|vietnam|indonesia|malaysia|singapore|china|hong kong|japan|"
                  r"korea|thailand|sri lanka|nepal|taiwan|cambodia|myanmar|apac|asia|"
                  r"australia|new zealand|oceania|anz|sydney|melbourne|brisbane|perth|auckland|"   # no Oceania either
                  r"bangalore|bengaluru|mumbai|delhi|gurgaon|gurugram|noida|hyderabad|pune|chennai|kolkata|ahmedabad|"
                  r"karachi|lahore|islamabad|dhaka|manila|cebu|jakarta|kuala lumpur|ho chi minh|hanoi|bangkok|tokyo|"
                  r"seoul|shanghai|beijing|shenzhen|kathmandu|colombo)\b", re.I)
# Asia / Oceania working hours or an India-based employer stated in the description (sponsor, 2026-11-25: "no Asia, no
# India, no Australia"). "IST" alone could be Israel time, so it counts only next to a clock time or India.
ASIA_TEXT = re.compile(r"\b(\d{1,2}(:\d{2})? ?(am|pm) ist|ist (hours|time ?zone|shift)|indian standard time|aest|aedt|"
                       r"sgt|pkt|(india|philippines|pakistan|australia)[- ]based|based in (india|the philippines|pakistan|"
                       r"australia|singapore|malaysia)|apac (hours|time ?zone))\b", re.I)
# A broad word ("worldwide", "Americas", "anywhere") only counts in a sentence about where the person can work;
# company boilerplate ("customers worldwide", "the world's leading network") doesn't.
WORK_CONTEXT = re.compile(r"\b(remote|candidates?|applicants?|hire|hiring|work(ing)? from|based|reside|located|location|"
                          r"time ?zones?|contract(or)?s?|position|role is open|open to)\b", re.I)
STRONG_LATAM = re.compile(r"\b(latin america|latam|south america|central america|costa rica)\b", re.I)
ONSITE = re.compile(r"\b(in[- ]office|on[- ]?site|onsite|hybrid|in[- ]person|presencial|h[ií]brido)\b", re.I)
# Low-end execution roles count as junior (sponsor, 2026-11-26: "they probably pay 1000 per month and you do stuff
# people don't do anymore", on Amalga Group's SEO Implementation Specialist (WordPress)).
# Only the kind of task marks a role low-end, never the word "specialist", "executive" or "associate" (sponsor,
# 2026-11-26: specialist roles are wanted; executive and associate may be fine).
LOW_END_SKIP = False
# Sponsor, 2026-11-27: "don't bloat the maybe list": irrelevant posts (low pay, foreign language...) are dropped, not
# kept as maybes. Pay this low is a skip even while low-end jobs are allowed.
LOW_PAY = re.compile(r"(?:usd|us\$|\$)\s?(\d{1,2})(?:\.\d+)?\s?(?:[–-]\s?\$?\s?(\d{1,2})(?:\.\d+)?)?\s?(?:usd\s?)?"
                     r"(?:/|per |an |a )\s?(?:hour|hr)\b", re.I)
LOW_PAY_MAX_HOURLY = 12
REMOTE_SAID = re.compile(r"\b(remote|remoto|work from home|wfh|fully distributed|distributed team|anywhere)\b", re.I)
LOW_END = re.compile(r"\b(implementation|wordpress|link ?build(er|ing)|outreach|backlinks?|citations?|seo va|"
                     r"virtual assistant|data entry|content upload)\b", re.I)
JUNIOR = re.compile(r"\b(intern(ship)?|junior|jr\.?|entry[- ]level|trainee|assistant|graduate|practicante|pasante|"
                    r"est[aá]gi\w*|assistente|asistente|auxiliar|aprendiz)\b", re.I)
SEO_ROLE = re.compile(r"(?<!non-)(?<!non )\b(seo|geo|aeo|search|organic|b\u00fasqueda|busca org\u00e2nica)\b", re.I)  # an SEO title
# Growth/marketing titles whose description is really SEO / GEO / AEO work count too (sponsor, 2026-11-25: worth applying
# even a little outside his experience). Their description is read; SEO_TERMS must carry the post (SEO_CORE_MIN mentions).
GROWTH_ROLE = re.compile(r"\b(growth|marketing|marketer|content|demand gen\w*|acquisition|inbound|discoverability|"
                         r"visibility|digital|web(site)?|crecimiento|mercadeo|conte[uú]do|contenido)\b", re.I)
SEO_TERMS = re.compile(r"\b(seo|aeo|geo|search engine optimi[sz]ation|generative engine optimi[sz]ation|"
                       r"answer engine optimi[sz]ation|ai search|llm (search|visibility)|ai visibility|organic search|"
                       r"organic (traffic|growth)|search console|keyword research|technical seo)\b", re.I)
SEO_CORE_MIN = 3
# US businesses that, by the sponsor's experience, hire only locally (sponsor, 2026-11-25): stores, local services,
# health systems, schools, dealerships, real estate, construction, law firms, restaurants, manufacturers; and US
# staffing / W-2 contract shops.
TRADITIONAL_US = re.compile(r"\b(our (stores|locations|showrooms|branches|clinics|restaurants|dealerships|franchisees?)|"
                            r"brick[- ]and[- ]mortar|retail(er| stores)|department store|in[- ]store|franchise|dealerships?|"
                            r"hospitals?|health ?system|patients|clinics?|campus|universit(y|ies)|college|school district|"
                            r"restaurants?|hospitality|resorts?|real estate|brokerage|home ?builders?|construction|"
                            r"contractors? (like|such as)|hvac|plumbing|roofing|law firms?|attorneys|manufactur(er|ing)|"
                            r"warehouse|distribution centers?|w-?2|contract to hire|c2h|staffing (agency|firm|company))\b", re.I)
TRADITIONAL_CO = re.compile(r"\b(staffing|talent solutions|recruit(ing|ment)|health|hospital|university|college|resort|"
                            r"realty|homes|construction|motors|dealer\w*|bank|credit union|insurance|"
                            r"bloomingdale|macy|nordstrom|walmart|target|kohl|finish line)\b", re.I)
AGENCY_TEXT = re.compile(r"\b((digital|marketing|seo|search|growth|creative|performance|advertising) agency|"
                         r"agency (that|which|helping|serving|focused)|our (agency|clients' (sites|websites)))\b", re.I)


_STOP = {
    "en": "the and to of a in for with you our we are is will on as be this your have at or from that by",
    "de": "und der die das mit für wir sie ist ein eine zu von auf im bei dein deine unsere unser als oder auch",
    "fr": "et le la les des une un pour avec vous nous est dans sur au aux du votre notre en sont ou ans chez",
    "nl": "en de het een van voor met je jij wij we zijn op aan bij ons onze ook als",
    "it": "e il la le di per con che una un sono nel della dei delle nostro nostra",
    "pt": "e o a os as de do da para com você nós uma um em no na nossa nosso são",
    "es": "y el la los las de del para con usted nosotros una un en es son nuestra nuestro tu",
    "pl": "i w z na do się jest oraz dla że nie od po jak",
    "cs": "a v na se je pro s do že od jsou",
    "sv": "och att det som en för med är på av vi du till",
    "da": "og at det som en for med er på af vi du til",
}
_STOP = {k: set(v.split()) for k, v in _STOP.items()}
FOREIGN_TITLE = re.compile(r"\((m/w/d|w/m/d|m/f/d|h/f|f/h|all genders|w/m/x|m/w/x)\)|\b(fachleitung|referent|leiter|"
                           r"spezialist|chef de projet|consultant\(e\)|responsable|especialista|specialista|medior)\b", re.I)


OTHER_LANG_REQ = re.compile(r"\b(german|french|dutch|italian|portuguese|polish|chinese|mandarin|japanese|korean|"
                            r"nordic|swedish|danish|norwegian|finnish|czech|greek|turkish|arabic|hebrew|russian|ukrainian)"
                            r"[- ]?(speaking|speaker|native|fluent|market)\b", re.I)
OWN_LANGUAGES = ("en", "es")   # the sponsor works in English and Spanish; Portuguese is foreign to him (2026-11-26)


def foreign_language(title, desc=""):
    """True when the post is written in a language he doesn't work in: anything but English or Spanish (sponsor,
    2026-11-26: that's a no, in every region)."""
    words = re.findall(r"[a-zà-ÿąćęłńóśźżčďěňřšťůž]+", (desc or "").lower())
    if len(words) >= 5:
        counts = {k: sum(w in s for w in words) for k, s in _STOP.items()}
        best = max(counts, key=counts.get)
        return best not in OWN_LANGUAGES and counts[best] > max(counts[k] for k in OWN_LANGUAGES)
    return bool(FOREIGN_TITLE.search(title or ""))


def company_kind(company, desc=""):
    """startup / agency / enterprise / recruiter / other, or None when unknown. Uses the jobs route's classification
    (jobs_companies.json, filled daily from the same LinkedIn searches), then the post's own words."""
    try:
        cos = json.loads((HERE / "jobs_companies.json").read_text())
    except (OSError, ValueError):
        cos = {}
    n = re.sub(r"[^a-z0-9]+", "", (company or "").lower())
    for v in cos.values():
        if re.sub(r"[^a-z0-9]+", "", (v.get("name") or "").lower()) == n and v.get("class") not in (None, "unknown"):
            return v["class"]
    # an agency's own words come first: an agency serving construction or real-estate firms is still an agency
    # (Siana Marketing, sponsor 2026-11-25: "these kind of posts might work")
    if AGENCY_TEXT.search(desc or "") or re.search(r"\b(agency|marketing|digital|media|seo)\b", company or "", re.I):
        return "agency"
    if TRADITIONAL_CO.search(company or "") or TRADITIONAL_US.search(desc or ""):
        return "other"
    return None


US_CITY = re.compile(r"^[A-Z][A-Za-z .'-]+, (A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|"
                     r"O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\b")


def get(url, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def search_url(region, window_s=86400):
    return "https://www.linkedin.com/jobs/search?" + urllib.parse.urlencode(
        {"keywords": QUERY, "location": REGIONS[region], "f_TPR": f"r{int(window_s)}", "f_WT": "2"})


def description(page):
    m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', page, re.S)
    if not m:
        return ""
    t = re.sub(r"<(br|li|p)[^>]*>", "\n", m.group(1))
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def seojobs_detail(page):
    """(employer description, apply link) from a seojobs.com job page. The page header (Location, Salary, Job Type)
    is filled by seojobs' collecting bot and can be wrong, so only the employer's text after "Job Description" is
    screened; the apply link is seojobs' click-through to the employer's form."""
    i = page.find('class="entry-content')
    text = re.sub(r"[ \t]+", " ", R.text_of(page[i:i + 60000] if i >= 0 else page))
    j = text.find("Job Description")
    desc = text[j + len("Job Description"):] if j >= 0 else ""
    # the employer's text ends where seojobs' own boxes begin ("Related / How to Apply for this SEO Job / Browse SEO
    # Jobs", a sidebar with a "Job location: Remote" filter menu); cut there so site navigation isn't read as the post
    ends = [k for k in (desc.find(m) for m in ("How to Apply for this SEO Job", "Browse SEO Jobs", "Want SEO jobs delivered",
                                                "Browse jobs Type of organization")) if k >= 0]
    desc = desc[:min(ends)] if ends else desc
    m = re.search(r'href="(https://www\.seojobs\.com/wp-json/seojobs/v1/apply-click/[^"]+)"', page)
    return desc.strip()[:8000], (html.unescape(m.group(1)) if m else None)


def sentences_with(rx, text, n=2):
    out = []
    for s in re.split(r"(?<=[.!?])\s+|\n", text):
        if rx.search(s) and s.strip() not in out:
            out.append(s.strip()[:220])
        if len(out) >= n:
            break
    return out


def feedback():
    return json.loads(FEEDBACK.read_text()) if FEEDBACK.exists() else {}


WRITER = re.compile(r"\b(content writer|copy ?writer|copywriting|writer|redactor|redactora|escritor|escritora|"
                    r"content (creator|editor)|blog(ger)? writer|ghost ?writer)\b", re.I)


def screen(post, desc):
    r = _screen(post, desc)
    if r["lean"] != "skip" and not SEO_ROLE.search(post.get("title", "")):
        n = len(SEO_TERMS.findall(desc or ""))
        r["why"] = [f"growth/marketing title; SEO/GEO/AEO is the core of the description ({n} mentions)"] + r["why"]
        r["growth_title"] = True
    return r


def _screen(post, desc):
    """lean: apply / maybe / skip, with reasons and the quoted sentences behind them."""
    fb = feedback()
    for c in fb.get("not_eligible_companies", []):
        if c["company"].lower() in post.get("company", "").lower():
            return {"lean": "skip", "why": [f"sponsor: {c['why']}"], "quotes": []}
    where = f"{post.get('location', '')} {post.get('title', '')}"
    text = f"{post.get('title', '')}\n{desc}"
    why, quotes = [], []
    if ASIA.search(where):
        return {"lean": "skip", "why": ["located in Asia or Oceania"], "quotes": []}
    if ASIA_TEXT.search(desc or ""):
        return {"lean": "skip", "why": ["Asia / Oceania hours or employer"], "quotes": sentences_with(ASIA_TEXT, desc)}
    if JUNIOR.search(post.get("title", "")):
        return {"lean": "skip", "why": ["junior or intern role"], "quotes": []}
    # Low-end execution roles (WordPress, link building...) are OK for now (sponsor, 2026-11-26: "I need any job I can
    # find"); LOW_END stays defined so it can be switched back on with LOW_END_SKIP = True.
    if LOW_END_SKIP and LOW_END.search(post.get("title", "")) and not re.search(r"\b(head|lead|director|manager|strateg\w*)\b", post.get("title", ""), re.I):
        return {"lean": "skip", "why": ["low-end execution role (implementation, link building, outreach)"], "quotes": []}
    if foreign_language(post.get("title", ""), desc):
        return {"lean": "skip", "why": ["post not in English or Spanish"], "quotes": []}
    if OTHER_LANG_REQ.search(post.get("title", "")) or re.search(r"[\u0400-\u04ff\u0370-\u03ff\u4e00-\u9fff]", post.get("title", "")):
        return {"lean": "skip", "why": ["needs a language other than English or Spanish"], "quotes": []}
    # Sponsor, 2026-11-26: "avoid content writer jobs, I'm not a content writer" (elev8.io's Content Writer had come
    # through as an SEO-heavy growth role).
    if WRITER.search(post.get("title", "")):
        return {"lean": "skip", "why": ["content writing role (not for the sponsor)"], "quotes": []}
    pay = LOW_PAY.search(text)
    if pay and int(pay.group(2) or pay.group(1)) <= LOW_PAY_MAX_HOURLY:
        return {"lean": "skip", "why": ["pay too low"], "quotes": [pay.group(0)]}
    if not SEO_ROLE.search(post.get("title", "")):
        hits = SEO_TERMS.findall(desc or "")
        if not (GROWTH_ROLE.search(post.get("title", "")) and len(hits) >= SEO_CORE_MIN):
            return {"lean": "skip", "why": ["not an SEO role"], "quotes": []}
    onsite = sentences_with(ONSITE, text)
    if onsite and not re.search(r"\b(fully remote|100% remote|remote[- ]first)\b", text, re.I):
        return {"lean": "skip", "why": ["not fully remote (in-office, on-site or hybrid)"], "quotes": onsite}
    neg = NEG_US if post["region"] in ("us", "seojobs") else NEG_EU if post["region"] == "europe" else re.compile(
        NEG_US.pattern + "|" + NEG_EU.pattern, re.I)
    pos_q = [q for q in sentences_with(POS, text, n=6) if STRONG_LATAM.search(q) or WORK_CONTEXT.search(q)][:2]
    neg_q = sentences_with(neg, text)
    if neg_q and not re.search(LATAM, " ".join(neg_q), re.I):
        return {"lean": "skip", "why": ["requires local work authorization or residence"], "quotes": neg_q}
    if pos_q:
        return {"lean": "apply", "why": ["open to LATAM, the Americas, anywhere, or contractors"], "quotes": pos_q}
    if post["region"] == "latam":
        return {"lean": "apply", "why": ["remote, listed for Latin America, no residence limit stated"], "quotes": []}
    if post["region"] == "seojobs" and desc and not re.search(r"\b(remote|work from home|wfh|distributed team|fully distributed)\b", text, re.I):
        # seojobs isn't a remote-only search (LinkedIn's searches are filtered to remote): the employer must say it
        return {"lean": "skip", "why": ["the post doesn't say the role is remote"], "quotes": []}
    if post["region"] in ("us", "seojobs"):
        # sponsor, 2026-11-24: a remote US post that doesn't ask about work authorization, sponsorship, citizenship
        # or US residence is worth applying to; some US companies will hire him as a contractor.
        # Refined twice (sponsor, 2026-11-25). The work-authorization question usually comes in the application form,
        # not the post, so a post's silence means nothing. US employers that aren't startups or agencies (stores,
        # department stores, health systems, IT staffing, enterprises) rarely hire from abroad: skip them unless the
        # post says so (positive signs are handled above). Startups and agencies sometimes do: a maybe.
        kind = company_kind(post.get("company", ""), desc)
        if kind in ("startup", "agency"):
            # sponsor, 2026-11-25 (Siana Marketing): agencies and startups may ask about US authorization in the form,
            # but they might make an exception: worth applying.
            return {"lean": "apply", "why": [f"US {kind}: the form may ask for US work authorization, but worth trying"],
                    "quotes": []}
        if kind:
            return {"lean": "skip", "why": [f"US {kind}, not a startup or agency: rarely hires from abroad"],
                    "quotes": sentences_with(TRADITIONAL_US, text, n=1)}
        return {"lean": "maybe", "why": ["US company of unknown type: the scout decides (startup or agency: maybe; "
                                         "anything else: skip)"], "quotes": [], "needs_kind": True}
    # Europe, refined (sponsor, 2026-11-26): posts never say "we hire outside X"; that's judged from experience. A post
    # written in a language other than English is a no; an English remote post has a chance and is worth trying.
    # Sponsor, 2026-11-27 ("don't bloat the maybe list"): LinkedIn's remote label alone isn't enough; a European post
    # that never says it's remote (on-site-looking UK/EU roles, recruiters' local clients) is dropped.
    if desc and not REMOTE_SAID.search(text):
        return {"lean": "skip", "why": ["European post that never says the role is remote"], "quotes": []}
    return {"lean": "maybe", "why": ["European remote post in English: nothing rules you out, worth trying"], "quotes": []}


def role_key(p):
    return re.sub(r"\(.*?\)", "", p["title"]).strip().lower() + " @ " + p["company"].lower()


def seen():
    """Job ids and roles (title @ company) seen on earlier days: a role re-posted under new ids isn't new."""
    ids, roles = set(), set()
    if SEEN.exists():
        for l in SEEN.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                ids.add(r["job_id"])
                roles.add(r.get("role", ""))
    return ids, roles


def fetch(now=None, fetcher=get, detail_fetcher=get, paid=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    OUT.mkdir(exist_ok=True)
    known, keyset = seen()
    coverage, posts, all_ids = [], [], []
    for region in REGIONS:
        got, last = None, None
        for attempt in range(3):  # LinkedIn answers 429 to bursts; wait and try again
            try:
                got = jobs.parse(fetcher(search_url(region)), region)
                break
            except Exception as e:
                last = e
                time.sleep(30 * (attempt + 1))
        if got is None:
            coverage.append(f"linkedin_{region}_remote: FAILED ({type(last).__name__}: {last})")
            continue
        coverage.append(f"linkedin_{region}_remote: {len(got)} posts")
        time.sleep(5)
        for p in got:
            all_ids.append((p["job_id"], role_key(p)))
            if p["job_id"] in known or role_key(p) in keyset:  # the same role re-posted for many cities counts once
                continue
            keyset.add(role_key(p))
            posts.append({**p, "region": region})
    if not SEOJOBS:
        coverage.append("seojobs: not read (sponsor, 2026-11-25: the LinkedIn posts search covers it)")
    try:  # seojobs.com refuses plain requests; it goes through the capped Web Unlocker
        if not SEOJOBS:
            raise StopIteration
        page, err = (paid or jobs.paid_fetch)("https://www.seojobs.com/jobs/")
        got = [] if err else jobs.parse_seojobs(page, max_age_days=1, now=now)
        coverage.append(f"seojobs: {len(got)} posts (last 24 h)" if not err else f"seojobs: FAILED ({err})")
        for p in got:
            p["seojobs_page"] = True
            # the job's own stretch of the list page: from its link to the next job's link (one block can hold
            # several jobs, e.g. "spotlight" ones, so the whole block would mix their labels)
            i = page.find(f'href="{p.get("url")}"') if p.get("url") and not err else -1
            j = page.find("<h3><a href=", i + 10) if i >= 0 else -1
            seg = R.text_of(page[i:j if j > 0 else i + 3000]) if i >= 0 else ""
            m = re.search(r"\b(In-Office|Hybrid|Remote(?: [A-Z]{2,3}| US| Worldwide| Anywhere)?)\b", seg)
            p["work_type"] = m.group(1).strip() if m else ""
            all_ids.append((p["job_id"], role_key(p)))
            if p["job_id"] not in known and role_key(p) not in keyset:
                keyset.add(role_key(p))
                posts.append({**p, "region": "seojobs"})
    except StopIteration:
        pass
    except Exception as e:
        coverage.append(f"seojobs: FAILED ({type(e).__name__}: {str(e)[:120]})")
    for i, p in enumerate(posts):
        desc = ""
        relevant = ((SEO_ROLE.search(p["title"]) or GROWTH_ROLE.search(p["title"])) and not JUNIOR.search(p["title"])
                    and not ASIA.search(p.get("location", "")))
        if p["region"] == "seojobs" and not SEO_ROLE.search(p["title"]):
            relevant = False  # seojobs pages are paid: growth titles there aren't opened
        if p["region"] != "seojobs" and relevant and i < MAX_DETAILS:
            for attempt in range(3):  # LinkedIn rate-limits bursts; back off and retry
                try:
                    desc = description(detail_fetcher(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{p['job_id']}"))
                    p.pop("detail_error", None)
                    break
                except Exception as e:
                    p["detail_error"] = str(e)[:80]
                    time.sleep(5 * (attempt + 1))
            time.sleep(1.5)
        elif p["region"] != "seojobs" and relevant:
            p["detail_error"] = "over the daily detail-page limit"
        # seojobs' Remote / Hybrid / In-Office label is filled by a collecting bot and can be wrong (a "full-time,
        # remote" post was labelled In-Office on 2026-11-24): never skip on it; read every relevant post itself
        # (sponsor, 2026-11-24). The label is kept in work_type for reference only.
        if p["region"] == "seojobs" and relevant and p.get("url"):
            try:  # seojobs job pages also refuse plain requests: one capped Web Unlocker request per relevant post
                page, err = (paid or jobs.paid_fetch)(p["url"])
                if not err:
                    desc, apply_link = seojobs_detail(page)
                    p["apply_link"] = apply_link
            except Exception as e:
                p["detail_error"] = str(e)[:80]
        p["screen"] = screen(p, desc)
        p["apply_url"] = p.get("apply_link") or p.get("url")
        p["excerpt"] = desc[:600]
    day = now.date().isoformat()
    path = OUT / f"{day}.json"
    if path.exists():  # a second run the same day adds to that day's list instead of replacing it
        old = json.loads(path.read_text())
        posts_all, coverage_all = old["posts"] + posts, old["coverage"] + coverage
    else:
        posts_all, coverage_all = posts, coverage
    path.write_text(json.dumps({"date": day, "coverage": coverage_all, "posts": posts_all}, indent=1,
                               ensure_ascii=False) + "\n")
    with SEEN.open("a") as f:
        for jid, role in dict(all_ids).items():
            if jid not in known:
                f.write(json.dumps({"job_id": jid, "role": role, "seen_at": now.isoformat(timespec="seconds")}) + "\n")
    return coverage, posts


BOARD_REGIONS = {"wellfound", "accel", "general_catalyst", "berlinstartupjobs", "telegram_il", "nextplay"}
BOARD_SEO = re.compile(r"(?<!non-)\b(seo|geo|aeo|ai search|organic (search|growth|traffic))\b", re.I)  # board titles: no
# bare "search" (paid search, search engineers) or "organic social"
OPEN_LOCATION = re.compile(rf"\b(remote|anywhere|worldwide|global|{LATAM})\b", re.I)


def board_posts(day, seeker_posts):
    """The startup boards read by jobs.py (SCOUT.md step 1) also feed his own list (sponsor, 2026-11-25): their posts
    first seen on `day`, SEO or growth titles, not junior, not Asia, not an excluded company, and remote or with no
    location stated. Titles only (those boards' pages aren't opened), so they're listed as "check the post"."""
    seen_file = HERE / "jobs_seen.jsonl"
    if not seen_file.exists():
        return [], 0
    excluded = [c["company"].lower() for c in feedback().get("not_eligible_companies", [])]
    have = {role_key(p) for p in seeker_posts}
    keep, left_out = [], 0
    for line in seen_file.read_text().splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        if p.get("region") not in BOARD_REGIONS or not (p.get("seen_at") or "").startswith(day) or p.get("baseline"):
            continue
        title, loc = p.get("title", ""), p.get("location") or ""
        if (not BOARD_SEO.search(title) or JUNIOR.search(title) or ASIA.search(loc)
                or any(e in p.get("company", "").lower() for e in excluded) or role_key(p) in have
                or (loc and not OPEN_LOCATION.search(loc))):
            left_out += 1
            continue
        if p.get("company", "").strip().lower() in ("remote", ""):
            p = {**p, "company": "a startup (name on the post)"}  # Getro lists remote.com-hosted jobs under "Remote"
        if role_key(p) in have:
            continue
        have.add(role_key(p))
        keep.append(p)
    return keep, left_out


def digest(day):
    """The daily message, from the session's verdicts in <day>.json (`final`: apply / maybe / skip, `note`)."""
    d = json.loads((OUT / f"{day}.json").read_text())
    rows = {"apply": [], "maybe": []}
    for p in d["posts"]:
        v = p.get("final") or p["screen"]["lean"]
        if v in rows:
            rows[v].append(p)
    lines = [f"SEO jobs for you, {day} (remote, last 24 hours; LinkedIn LATAM, US and Europe)", ""]
    for v, head in (("apply", "Worth applying"), ("maybe", "Maybe: check the location terms")):
        if rows[v]:
            lines.append(f"{head}:")
            for p in rows[v]:
                note = p.get("note") or "; ".join(p["screen"]["why"])
                lines.append(f"- {p['title']} at {p['company']} ({p['location'] or 'remote'}): {note}. Apply: {p['apply_url']}")
            lines.append("")
    boards, board_skipped = board_posts(day, d["posts"])
    if boards:
        lines.append("From startup job boards (Wellfound, Accel and General Catalyst boards, Berlin Startup Jobs, "
                     "Israeli marketing-jobs channel; new today, remote or location not stated; open the post to check):")
        for p in boards:
            lines.append(f"- {p['title']} at {p['company']} ({p.get('location') or 'location not stated'}). Post: {p['url']}")
        lines.append("")
    if board_skipped:
        lines.append(f"Startup-board posts left out: {board_skipped} (not SEO, junior, Asia, or a stated non-remote location).")
    skipped = sum(1 for p in d["posts"] if (p.get("final") or p["screen"]["lean"]) == "skip")
    lines.append(f"Skipped {skipped} (not SEO, junior, Asia, local work authorization, or Europe-only). Sources: "
                 + "; ".join(d["coverage"]))
    md = "\n".join(lines) + "\n"
    (OUT / f"{day}.md").write_text(md)
    return md


def main(argv=None):
    a = argparse.ArgumentParser()
    sub = a.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    g = sub.add_parser("digest")
    g.add_argument("day")
    a = a.parse_args(argv)
    if a.cmd == "fetch":
        coverage, posts = fetch()
        from collections import Counter
        print("\n".join(coverage))
        print(f"{len(posts)} new posts; lean: {dict(Counter(p['screen']['lean'] for p in posts))}")
    else:
        print(digest(a.day))


if __name__ == "__main__":
    main()
