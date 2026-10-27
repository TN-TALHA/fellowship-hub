# FellowshipHub

A working demo that showcases **11 modern engineering practices** in one small project.

## Run it

```bash
pip install -r requirements.txt
python app.py
# open http://localhost:5000
```

Run with Docker:
```bash
docker build -t fellowship-hub .
docker run --rm -p 5000:5000 fellowship-hub
# open http://localhost:5000
```

Run with Docker Compose:
```bash
docker compose up --build -d
# open http://localhost:5000
docker compose down
```

---

## Tests & CI/CD

Install the dev tooling (pytest, pytest-cov, ruff) and run the same gates the
pipeline runs:

```bash
pip install -r requirements-dev.txt

ruff check .                            # Gate 1 — lint
pytest                                  # Gate 2 — 88 tests
pytest --cov --cov-report=term-missing  # Gate 2 — coverage, must stay >= 85%
```

Auto-fix most lint complaints:

```bash
ruff check . --fix
```

### The pipeline

`.github/workflows/ci.yml` runs on every push to `main` and every pull request:

| # | Job | What it checks | Goes RED when |
|---|-----|----------------|---------------|
| 1 | `lint` | ruff — style, import order, likely bugs | any lint error |
| 2 | `test` | pytest + coverage | a test fails, or coverage drops below 85% |
| 3 | `docker` | image builds, container answers HTTP 200 | build fails or app doesn't boot |
| 4 | `ci-passed` | all three above | any gate failed — **this is the required status check** |

Jobs 1 and 2 run in parallel. Job 3 only starts if both are green.

### BDD coverage

The scenarios in `features/fellowship.feature.txt` are asserted in
`tests/test_services.py` — see `TestScenarioCriticalOutranksLow` and
`TestScenarioAnonymousFeedback`. The tests are the living documentation.

---

## Topic to Code Mapping

| # | Topic | File / Feature | How to explain |
|---|-------|----------------|----------------|
| 1 | Introduction + Fellowship Policy | `services.register_fellow()` + `/api/fellows` | Jab fellow register hota hai, event publish hota hai. Policy: sirf active fellows ko task milte hain. UI tab **Dashboard → Fellows**. |
| 2 | Constitution & Priority Policy | `services.CONSTITUTION`, `compute_priority_score()` | Har task ka score = priority × 10 + aging_bonus + story_points. Weights live dikhte hain **Dashboard → Constitution** me. |
| 3 | Agile Principles & Manifesto | `TaskStatus` enum + `sprint_board()` | Kanban board: Backlog → In Progress → Review → Done. Working software > documentation. |
| 4 | AI Era Product Thinking | `ai_suggest()` | Task title ke hisaab se AI product suggestion deta hai (e.g., "validate with 3 users"). UI tab **AI Pairing**. |
| 5 | AI-Engineer Pairing & Boy Scout Rule | `ai_suggest().pair_with`, `boy_scout_report()` | AI ek pair partner suggest karta hai. Boy Scout before → after metrics dikhata hai. |
| 6 | Psychological Safety | `submit_feedback()` | Anonymous feedback — author store nahi hota. Sirf mood broadcast hota hai. UI tab **Safety**. |
| 7 | Governance Tools & Orientation | `events.audit_subscriber()`, `/api/governance` | Har publish() call auto audit_log me likhi jati hai. UI tab **Governance → Audit Log**. |
| 8 | DDD | `domain.py` | Aggregates (Fellow, Task), Value Objects (Policy), Entities (Feedback). Koi framework code nahi. |
| 9 | BDD | `features/fellowship.feature.txt` + `tests/test_services.py` | Scenarios plain English me, phir `TestScenario*` classes me assert hote hain. Tests living documentation hain. |
| 10 | API-First Design | `openapi.yml` + `app.py` | Contract pehle likha, phir Flask routes. Sab match karte hain. |
| 11 | Integration Patterns | `events.py` EventBus | Pub/sub. Naya listener add karne ke liye services change karne ki zarurat nahi. |

---

## One-line Summary of Each Topic

- **Fellowship Policy** – Kaun join kar sakta, kya rules hain.
- **Constitution & Priority Policy** – Transparent, weighted prioritization.
- **Agile** – Iterative, small slices, working software.
- **AI-Era Product Thinking** – AI product decisions ko amplify karta hai.
- **AI-Engineer Pairing** – Engineer + AI + peer = best code.
- **Boy Scout Rule** – Code ko pehle se behtar chhod ke jao.
- **Psychological Safety** – Anonymous voice > fear.
- **Governance Tools** – Immutable audit trails.
- **DDD** – Business ko model karo, database ko nahi.
- **BDD** – Behavior first, tests as documentation.
- **API-First** – Contract before code.
- **Integration Patterns** – Pub/sub, event-driven.

---

## 3-Minute Demo Script

1. Open http://localhost:5000
2. Add fellow → create task ("Fix login bug", CRITICAL)
3. Dekho Agile Sprint Board pe high score ke saath appear hota hai
4. **AI Pairing** tab → task select karo → AI suggestion + pair partner
5. **Safety** tab → anonymous feedback submit karo
6. **Governance** tab → audit log + event bus live update
7. **Metrics** tab → Boy Scout before/after
8. Conclusion: "Ye ek project me DDD, BDD, API-First, Event-Driven, AI pairing, safety, governance, Agile — sab covered hai."

---

## VS Code File Creation Tips

- **Folder banane ke liye:** Explorer me right-click → New Folder
- **File banane ke liye:** Folder pe right-click → New File → sirf naam likho (jaise `app.py`)
- Agar `.yml` ya `.yaml` na bane to `.yml.txt` use karo
- Agar `.feature` na bane to `.feature.txt` use karo