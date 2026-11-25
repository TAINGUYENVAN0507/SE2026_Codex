import statistics, sys, time, httpx
base = sys.argv[1]
c = httpx.Client(base_url=base, timeout=30)
for _ in range(60):
    try:
        if c.get("/api/v1/health").status_code == 200: break
    except Exception: time.sleep(0.5)
assert c.post("/api/v1/auth/login", json={"email": "load@example.com", "password": "LoadTest!2026"}).status_code == 200
out = {}
for name, params in [("list", {}), ("q_title", {"q": "Tải 1"}), ("q_wildcard", {"q": "%"})]:
    for _ in range(20): c.get("/api/v1/meetings", params=params)
    ts = []
    for _ in range(300):
        t = time.perf_counter(); r = c.get("/api/v1/meetings", params=params); ts.append(time.perf_counter() - t)
        assert r.status_code == 200
    out[name] = (round(statistics.median(ts) * 1000, 2), round(sorted(ts)[284] * 1000, 2), len(r.json()["items"]))
print(out)
