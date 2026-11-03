# ==========================================
# COMPANY DISCOVERY EVAL (paste into a new cell BELOW the main cell and run it; offline, ~2s, no API calls)
# Checks the 3rd search agent: batch rotation (>= 70-80% new companies), stage mix, hot carry-overs,
# 2-3 roles per company, freshness badges, "two similar roles at one company are NOT merged as duplicates",
# Hacker News 'Who is hiring' parsing + companies, and a full mocked run of the three parallel search branches.
# The live part (real careers pages) can only run on your machine: run the agent with search mode 'discover'.
# ==========================================
import tempfile as _tf
import requests as _rq
from unittest import mock as _mock
from datetime import datetime as _dt, timedelta as _td
from langgraph.graph import StateGraph as _SG, START as _START, END as _END


def _fake_pool(n_per_stage=40, hot=(), old=(), dead=()):
    out, today = [], _dt.now()
    for s_i, stage in enumerate(COMPANY_STAGES):
        for i in range(n_per_stage):
            key = f"co{s_i}-{i}.com"
            c = {"name": f"Co {s_i}-{i}", "website": f"https://{key}", "key": key, "stage": stage}
            if key in hot:
                c.update(matches=2, recent_posts=5, newest_post=(today - _td(days=1)).strftime("%Y-%m-%d"))
            if key in old:
                c.update(matches=2, recent_posts=5, newest_post=(today - _td(days=40)).strftime("%Y-%m-%d"))
            if key in dead:
                c["no_source"] = 2
            out.append(c)
    return out


def _days_ago(d):
    return (_dt.now() - _td(days=d)).strftime("%Y-%m-%d")


class _R:   # Exa result stand-in
    def __init__(self, title, url):
        self.title, self.url = title, url


def run_company_discovery_eval():
    fails, total = [], 0

    def check(ok, label):
        nonlocal total
        total += 1
        if not ok:
            fails.append(label)

    # 1. Rotation: batch 2 is >= 75% new; carry-overs are only last batch's HOT companies, capped at 25%
    pool = _fake_pool()
    b1 = select_company_batch(pool, [], 60, new_share=0.75, seed=1)
    check(len(b1) == 60, f"batch 1 size {len(b1)}, want 60")
    keys1 = [c["key"] for c in b1]
    hot = set(keys1[:30])                                   # 30 of batch 1 posted recently
    pool = _fake_pool(hot=hot)
    picked = {k: _days_ago(0) for k in keys1}
    b2 = select_company_batch(pool, keys1, 60, new_share=0.75, picked=picked, seed=2)
    overlap = len(set(keys1) & {c["key"] for c in b2})
    check(len(b2) == 60, f"batch 2 size {len(b2)}, want 60")
    check(overlap <= 15, f"batch 2 repeats {overlap}/60 companies from batch 1 (max 15 = 25%)")
    check(overlap == 15, f"batch 2 should recheck 15 hot companies, got {overlap}")
    check(all(c["key"] in hot for c in b2 if c["key"] in keys1), "a non-hot company was carried over")
    for share, max_rep in ((0.7, 18), (0.8, 12)):
        b = select_company_batch(pool, keys1, 60, new_share=share, picked=picked, seed=3)
        rep = len(set(keys1) & {c["key"] for c in b})
        check(rep <= max_rep, f"new_share={share}: {rep} repeats, max {max_rep}")

    # 2. No hot companies -> zero repeats; never-picked companies come before already-picked ones
    pool = _fake_pool()
    b2 = select_company_batch(pool, keys1, 60, picked=picked, seed=4)
    check(not set(keys1) & {c["key"] for c in b2}, "repeats without any recent postings")
    keys2 = [c["key"] for c in b2]
    picked.update({k: _days_ago(0) for k in keys2})
    b3 = select_company_batch(pool, keys2, 60, picked=picked, seed=5)
    never = {c["key"] for c in pool} - set(keys1) - set(keys2)        # 40 companies never picked yet
    check(never <= {c["key"] for c in b3}, f"batch 3 skipped {len(never - {c['key'] for c in b3})} never-picked companies")

    # 3. Stage mix: every stage present roughly in its share (seed 20%, A-B 25%, growth 25%, large 30%)
    counts = {s: sum(1 for c in b1 if c["stage"] == s) for s in COMPANY_STAGES}
    for s, (share, _) in COMPANY_STAGES.items():
        check(abs(counts[s] - round(60 * share)) <= 1, f"stage {s}: {counts[s]} in batch, want ~{round(60 * share)}")

    # 4. Hot = recent; a company whose last posting is 40 days old is not 'hot'; dead careers pages are skipped
    pool = _fake_pool(old=set(keys1[:30]), dead={"co0-39.com", "co1-39.com"})
    b = select_company_batch(pool, keys1, 60, picked=picked, seed=6)
    check(not set(keys1) & {c["key"] for c in b}, "a company with only 40-day-old postings was carried over as hot")
    check(not {"co0-39.com", "co1-39.com"} & {c["key"] for c in b}, "company with no careers page (2 tries) was picked again")
    # Small pool: fewer companies rather than breaking the overlap rule
    tiny = _fake_pool(n_per_stage=5)
    b = select_company_batch(tiny, [c["key"] for c in tiny[:10]], 60)
    check(len(b) == 10 and not {c["key"] for c in tiny[:10]} & {c["key"] for c in b}, f"tiny pool: {len(b)} picked")

    # 5. 2-3 roles per company: the closest titles are kept, newest first on ties
    jobs = [{"Job Profile": t, "Date Posted": _days_ago(d), "Job Link": f"https://x/{i}"} for i, (t, d) in enumerate([
        ("Senior Product Manager, Payments", 2), ("Product Manager", 1), ("Product Manager - Lending", 20),
        ("Senior Product Manager", 5), ("Product Manager", 9), ("Product Operations Manager", 1)])]
    best = pick_best_roles(jobs, ["product manager"], 3)
    check(len(best) == 3, f"roles per company: {len(best)}, want 3")
    check([j["Job Profile"] for j in best[:2]] == ["Product Manager", "Product Manager"] and best[0]["Date Posted"] == _days_ago(1),
          f"role order: {[(j['Job Profile'], j['Date Posted']) for j in best]}")

    # 6. Freshness badges
    check(posting_freshness(_days_ago(0)).startswith("🔥"), "today should be 🔥")
    check(posting_freshness(_days_ago(5)).startswith("🆕"), "5 days should be 🆕")
    check(posting_freshness(_days_ago(20)) == "" and posting_freshness("Not listed") == "", "old/undated should have no badge")

    # 7. Two similar roles at ONE company share boilerplate JD text but are two openings (not merged).
    #    The same job on two different boards is still merged (existing cross-site rule).
    boiler = "We are a fast growing fintech building payments for millions of small businesses across India. " * 6
    jd_a = boiler + "You will own the merchant onboarding roadmap and partner with risk."
    jd_b = boiler + "You will own the lending product roadmap and partner with credit."
    a = {"Job Profile": "Senior Product Manager, Onboarding", "Target Company": "Acme", "Job Link": "https://boards.greenhouse.io/acme/jobs/111"}
    b = {"Job Profile": "Senior Product Manager, Lending", "Target Company": "Acme", "Job Link": "https://boards.greenhouse.io/acme/jobs/222"}
    c = {"Job Profile": "Senior Product Manager, Onboarding", "Target Company": "Jobgether", "Job Link": "https://jobs.lever.co/jobgether/abc-123"}
    _POSTING_INFO.clear(); _JD_FP.clear()
    _POSTING_INFO.update({a["Job Link"]: {"jd": jd_a}, b["Job Link"]: {"jd": jd_b}, c["Job Link"]: {"jd": jd_a}})
    kept, _ = dedupe_across_sites([dict(a), dict(b)])
    check(len(kept) == 2, f"two roles at one company merged into {len(kept)}")
    kept, _ = dedupe_across_sites([dict(a), dict(b), dict(c)])
    check(len(kept) == 2 and any("Also Posted At" in k for k in kept), f"cross-site copy not merged: {len(kept)} kept")
    _POSTING_INFO.clear(); _JD_FP.clear()

    # 8. Agent switches
    for mode, want in (("both", (1, 1, 1)), ("linkedin", (1, 0, 0)), ("career", (0, 1, 0)), ("discover", (0, 0, 1))):
        got = tuple(int(agent_on({"search_mode": mode}, a)) for a in ("linkedin", "web", "discover"))
        check(got == want, f"search_mode={mode}: agents {got}, want {want}")

    # 9. Pool building: Exa + LLM results merged by website; job boards / ATS hosts never become 'companies'
    llm_json = ('[{"name": "Razorpay", "website": "https://razorpay.com", "stage": "Growth (Series C+)"},'
                ' {"name": "Naukri", "website": "https://www.naukri.com", "stage": "Large / Public"},'
                ' {"name": "Tiny", "website": "https://tiny.in/about", "stage": "Seed / Pre-seed"}]')
    exa_hits = [_R("Razorpay - Payments", "https://www.razorpay.com/"), _R("Lever", "https://jobs.lever.co/foo"),
                _R("Paytm | Payments", "https://paytm.com")]
    with _tf.TemporaryDirectory() as tmp, \
            _mock.patch.dict(globals(), {"COMPANY_POOL_FILE": os.path.join(tmp, "pool.json"), "GEMINI_API_KEY": "x",
                                         "gemini_text": lambda p: llm_json}), \
            _mock.patch.object(exa, "search", create=True, side_effect=lambda **k: _mock.Mock(results=exa_hits)):
        data = load_company_pool()
        cos = ensure_company_pool(data, "Fintech", "Delhi", 10)
        keys = sorted(c["key"] for c in cos)
        check(keys == ["paytm.com", "razorpay.com", "tiny.in"], f"pool keys {keys}")
        check(next(c for c in cos if c["key"] == "razorpay.com")["stage"] == "Growth (Series C+)", "LLM stage lost on merge")

        # 10. Full mocked run: 3 branches in parallel -> merge. Discovery adds badges, stage, max 3 roles/company.
        today = _dt.now()
        def fake_ats(ats, slug, roles):
            n = 5 if slug[0] == "razorpay" else 1
            return [{"title": f"Product Manager {i}", "location": "Delhi, India", "url": f"https://boards.greenhouse.io/{slug[0]}/jobs/{i}",
                     "posted": today - _td(days=i)} for i in range(n)]
        patches = {"derive_domain_from_resume": lambda *a: "Fintech", "expand_role_variants_cached": lambda r: ["product manager"],
                   "detect_career_source": lambda site: ("Greenhouse", [_site_key(site).split(".")[0]], site),
                   "fetch_ats_jobs": fake_ats, "fetch_live_linkedin_jobs": lambda *a, **k: [
                       {"Job Profile": "Product Manager 0", "Target Company": "Razorpay", "Location": "Delhi",
                        "Job Link": "https://boards.greenhouse.io/razorpay/jobs/0", "Platform Name": "LinkedIn", "Date Posted": "Past 7 days"}],
                   "search_job_boards_node": lambda s: {"board_jobs": []}, "shortlist_companies_node": lambda s: {},
                   "search_career_pages_node": lambda s: {"career_jobs": []}}
        with _mock.patch.dict(globals(), patches):
            g = _SG(PipelineState)
            for name, fn in [("start_search", start_search_node), ("search_jobs", search_jobs_node),
                             ("shortlist_companies", globals()["shortlist_companies_node"]),
                             ("search_career_pages", globals()["search_career_pages_node"]),
                             ("search_job_boards", globals()["search_job_boards_node"]),
                             ("discover_companies", discover_companies_node),
                             ("search_discovered_careers", search_discovered_careers_node), ("merge_results", merge_search_results_node)]:
                g.add_node(name, fn)
            g.add_edge(_START, "start_search")
            for a_, b_ in [("start_search", "search_jobs"), ("start_search", "shortlist_companies"), ("start_search", "discover_companies"),
                           ("shortlist_companies", "search_career_pages"), ("search_career_pages", "search_job_boards"),
                           ("discover_companies", "search_discovered_careers")]:
                g.add_edge(a_, b_)
            g.add_edge(["search_jobs", "search_job_boards", "search_discovered_careers"], "merge_results")
            g.add_edge("merge_results", _END)
            out = g.compile().invoke({"roles": ["Product Manager"], "target_geos": ["Delhi"], "job_duration_days": 7,
                                      "search_mode": "both", "target_domain": "", "discovery_company_count": 10,
                                      "candidate_name": "t", "resume_summary": "", "search_iteration": 1})
        jobs = out["raw_jobs"]
        rz = [j for j in jobs if j["Target Company"] == "Razorpay"]
        check(len(rz) == 3, f"Razorpay roles kept: {len(rz)}, want 3 (5 open, max 3)")
        check(any(j.get("Freshness", "").startswith("🔥") for j in rz), "no 🔥 badge on a 0-day-old posting")
        li = next((j for j in jobs if j["Job Link"].endswith("/razorpay/jobs/0")), {})
        check(li.get("Platform Name") == "LinkedIn" and li.get("Company Stage") == "Growth (Series C+)",
              f"same job from LinkedIn + discovery should keep LinkedIn and gain the stage: {li.get('Platform Name')}, {li.get('Company Stage')}")
        saved = load_company_pool()["pools"][pool_key("Fintech", "Delhi")]["companies"]["razorpay.com"]
        check(saved.get("ats") == "Greenhouse" and saved.get("matches") == 3 and saved.get("recent_posts") == 5,
              f"pool not updated after the scan: {saved}")
        hist = load_company_pool()["history"][pool_key("Fintech", "Delhi")]
        check(len(hist["last_batch"]) == 3, f"last batch saved: {hist['last_batch']}")

    # 11. Hacker News 'Who is hiring': parsing real-looking posts
    now_i = int(_dt.now().timestamp())
    hn_items = [
        {"id": 901, "author": "a", "created_at_i": now_i - 2 * 86400,
         "text": 'Acme Pay (YC W21) | Senior Product Manager | Bangalore, India (Hybrid) | <a href="https:&#x2F;&#x2F;jobs.lever.co&#x2F;acmepay">https://jobs.lever.co/acmepay</a><p>We build payments for SMBs.'},
        {"id": 902, "author": "b", "created_at_i": now_i - 1 * 86400,
         "text": 'Ledgerly | Bengaluru | ONSITE<p>Roles:<p>- Backend Engineer<p>- Product Manager, Lending<p>Apply: <a href="https://ledgerly.io/jobs">https://ledgerly.io/jobs</a>'},
        {"id": 903, "author": "c", "created_at_i": now_i - 3 * 86400,
         "text": 'Faraway Inc | Product Manager | San Francisco, CA | ONSITE | <a href="https://faraway.com">faraway.com</a>'},
        {"id": 904, "author": "d", "created_at_i": now_i - 3 * 86400,
         "text": 'GPU Co | Senior Backend Engineer | Bangalore | <a href="https://gpu.co/careers">gpu.co</a>'},
        {"id": 905, "author": "e", "created_at_i": now_i - 20 * 86400,
         "text": 'OldCo | Product Manager | Bangalore | <a href="https://oldco.in/careers">oldco.in</a>'},
        {"id": 906, "author": None, "text": None},   # deleted comment
    ]
    p1 = parse_hn_post(hn_items[0])
    check(p1["company"] == "Acme Pay", f"HN company: '{p1['company']}' (want 'Acme Pay', YC tag removed)")
    check(p1["ats"] == "Lever" and p1["slug"][0] == "acmepay", f"HN ATS link: {p1['ats']} {p1['slug']}")
    check(hn_role_title(p1, ["product manager"]) == "Senior Product Manager", f"HN header role: {hn_role_title(p1, ['product manager'])}")
    p2 = parse_hn_post(hn_items[1])
    check(hn_role_title(p2, ["product manager"]) == "Product Manager, Lending", f"HN body role: '{hn_role_title(p2, ['product manager'])}'")
    check(p2["website"] == "https://ledgerly.io", f"HN website: {p2['website']}")
    check(not is_listing_url(p1["hn_link"]), "an HN post link is treated as a listing page")

    def hn_get(url, params=None, **kw):
        if "search_by_date" in url:
            return _mock.Mock(status_code=200, json=lambda: {"hits": [
                {"objectID": "900", "title": "Ask HN: Who is hiring? (November 2026)", "created_at_i": now_i - 3 * 86400},
                {"objectID": "800", "title": "Ask HN: Who wants to be hired? (November 2026)", "created_at_i": now_i}]})
        if url.endswith("/items/900"):
            return _mock.Mock(status_code=200, json=lambda: {"id": 900, "children": hn_items})
        raise _rq.exceptions.ConnectionError("no route in test")
    with _mock.patch.object(_rq, "get", side_effect=hn_get), _mock.patch.dict(globals(), {"_HN_CACHE": {}}):
        names = [p["company"] for p in hn_matching_posts(["product manager"], "Bangalore")]
        check(names == ["Ledgerly", "Acme Pay", "OldCo"], f"HN matches for Bangalore PM: {names} (SF / engineer-only / deleted out)")
        check(len(hn_hiring_threads()) == 1, "'Who wants to be hired' thread was read as a hiring thread")

        # 12. HN companies join the batch: careers board read first; HN post is the job only when the board has nothing
        with _tf.TemporaryDirectory() as tmp, _mock.patch.dict(globals(), {
                "COMPANY_POOL_FILE": os.path.join(tmp, "pool.json"), "GEMINI_API_KEY": "", "HN_ENABLED": True,
                "derive_domain_from_resume": lambda *a: "Fintech", "expand_role_variants_cached": lambda r: ["product manager"],
                "ensure_company_pool": lambda data, d, g, n: list(data["pools"].setdefault(pool_key(d, g), {"built": "", "companies": {}})["companies"].values()),
                "detect_career_source": lambda site: (None, None, None), "guess_ats_from_name": lambda n, w: (None, None),
                "fetch_ats_jobs": lambda ats, slug, roles: [{"title": "Senior Product Manager", "location": "Bangalore, India",
                                                            "url": "https://jobs.lever.co/acmepay/1111-aaaa", "posted": _dt.now() - _td(days=1)}]}):
            st = {"roles": ["Product Manager"], "target_geos": ["Bangalore"], "job_duration_days": 7, "search_mode": "discover",
                  "target_domain": "", "discovery_company_count": 10, "candidate_name": "t", "resume_summary": ""}
            b = discover_companies_node(st)["discovery_batch"]
            check(sorted(c["name"] for c in b) == ["Acme Pay", "Ledgerly", "OldCo"], f"HN batch: {[c['name'] for c in b]}")
            jobs = search_discovered_careers_node({**st, "discovery_batch": b})["discovery_jobs"]
            got = sorted((j["Target Company"], j["Platform Name"].split(" (")[0]) for j in jobs)
            check(got == [("Acme Pay", "Company Discovery"), ("Ledgerly", "Hacker News")],
                  f"HN jobs: {got} (Acme from its Lever board, Ledgerly from the HN post, OldCo too old for 7 days)")
            led = next((j for j in jobs if j["Target Company"] == "Ledgerly"), {})
            check(led.get("Job Link", "").startswith("https://news.ycombinator.com/item?id=902") and "ledgerly.io" in led.get("Also Posted At", ""),
                  f"HN job links: {led.get('Job Link')} / {led.get('Also Posted At')}")
            b2 = discover_companies_node(st)["discovery_batch"]
            check(sorted(c["name"] for c in b2) == ["Acme Pay", "Ledgerly"],   # hot ones are rechecked, OldCo (no fit) is not
                  f"next batch after HN: {[c['name'] for c in b2]} (want only the 2 hot companies)")

    print(f"\n🧪 Company discovery eval: {total - len(fails)}/{total} checks passed")
    for f in fails:
        print(f"   ✗ {f}")
    return not fails


run_company_discovery_eval()
