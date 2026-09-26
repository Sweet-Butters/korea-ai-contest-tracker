"""Turn a contest plus the applicant's profile into a draft application pack.

Writes drafts/<contest-id>/ (git-ignored):
  checklist.md   what to submit, how, by when
  application.md 지원서 초안 (LLM if a key is set, otherwise a filled template)
  email.md       접수 메일 초안 — only when the notice takes email

The applicant never auto-agrees to anything: eligibility and consent boxes are listed as
"직접 확인" items, and nothing is sent from here.
"""
import json
from pathlib import Path

from collector import llm

from . import profile as profile_mod

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"

PROMPT = """너는 한국 공모전·지원사업 지원서를 돕는다. 아래 지원자 정보와 공고 정보를 바탕으로 지원서 초안을 써라.

규칙:
- 지원자 정보에 없는 경력·수상·수치를 지어내지 마라. 모르면 [확인 필요] 로 표시하라.
- 과장 없이 담백하게. 한국어. 문단마다 소제목.
- 공고가 요구하는 항목이 있으면 그 항목 순서를 따르라.
- 분량은 900~1400자.

[지원자]
{profile}

[공고]
이름: {name}
주최: {host}
분야: {category}
접수: {period}
대상: {eligibility}
상금: {prize}
요건 요약: {requirements}
공고 발췌: {excerpt}

출력 형식(그대로):
## 지원 동기
...
## 무엇을 만들/제안할 것인가
...
## 준비된 역량과 근거
...
## 일정 계획
...
"""


CODE_WORDS = ("모델", "알고리즘", "코드", "predict", "리더보드", "데이터셋", "정확도", "제출물은 zip",
              "베이스라인", "ipynb", "학습", "추론")


def is_code_contest(contest: dict, req: dict) -> bool:
    """Code/leaderboard contests are judged on a submitted model, not on a written application."""
    text = f"{contest.get('name','')} {req.get('excerpt','')} {' '.join(req.get('documents') or [])}"
    hits = sum(w in text for w in CODE_WORDS)
    return contest.get("category") == "data" and hits >= 2 or hits >= 4


QUESTIONS = """# {name} — 먼저 정할 것

지원서를 쓰기 전에 아래를 직접 정하세요. 여기에 답하면 초안을 그 내용으로 다시 씁니다.

1. 이 대회에서 **무엇을 만들/제안할 것인가** (한 문장)
2. 왜 그것이 이 대회 주제에 맞는가
3. 내가 이미 해본 것 중 **근거가 되는 것** (프로젝트·수치)
4. 혼자인가 팀인가, 팀이면 역할 분담
5. 마감까지 남은 기간에 실제로 할 수 있는 범위

답을 정한 뒤: `python -m apply prep {id} --answers "..."` (또는 Claude에게 답을 주고 다시 써 달라고 하세요)
"""


def _fallback(p: dict, contest: dict) -> str:
    projects = "\n".join(f"- {x.get('name')}: {x.get('summary')} (역할 {x.get('role')}, 결과 {x.get('result')})"
                         for x in p.get("projects", []))
    return f"""## 지원 동기
[직접 작성] {contest.get('name')}에 지원하려는 이유를 2~3문장으로 씁니다.
참고: {p.get('intro', '')}

## 무엇을 만들/제안할 것인가
[직접 작성] 공고가 요구하는 주제에 맞춰 만들 것을 씁니다.

## 준비된 역량과 근거
{projects or '[프로필에 프로젝트를 채우면 자동으로 들어갑니다]'}
강점: {', '.join(p.get('strengths', [])) or '[확인 필요]'}

## 일정 계획
[직접 작성] 접수 마감 {contest.get('applyEnd') or '[확인 필요]'} 까지의 준비 일정.

---
※ GEMINI_API_KEY 를 설정하면 이 초안을 공고에 맞춰 자동으로 써 줍니다.
"""


def _application(p: dict, contest: dict, req: dict) -> str:
    if not llm.available():
        return _fallback(p, contest)
    prompt = PROMPT.format(
        profile=profile_mod.summary(p, for_llm=True),  # 이름·연락처는 보내지 않는다
        name=contest.get("name", ""), host=contest.get("host") or "",
        category=contest.get("category") or "", prize=contest.get("prize") or "",
        period=f"{contest.get('applyStart') or ''} ~ {contest.get('applyEnd') or ''}",
        eligibility=contest.get("eligibility") or req.get("eligibility") or "",
        requirements=json.dumps({k: req.get(k) for k in ("applyMethod", "documents", "formats", "steps")}, ensure_ascii=False),
        excerpt=req.get("excerpt", ""),
    )
    try:
        out = llm._gemini(prompt + '\n\nJSON 형식이 아니라 위 출력 형식 그대로의 마크다운 문자열 하나를 "text" 키에 담아 반환하라: {"text":"..."}')
        return out.get("text") if isinstance(out, dict) else str(out)
    except Exception as e:
        return _fallback(p, contest) + f"\n<!-- LLM 실패: {str(e)[:120]} -->\n"


def _checklist(contest: dict, req: dict) -> str:
    guessed = set(req.get("guessed") or []) if not req.get("byLlm") else set()

    def line(label, value, key=None):
        if not value:
            return f"- **{label}**: [확인 필요]"
        mark = " *(규칙으로 추정 — 원문 확인)*" if key in guessed else ""
        return f"- **{label}**: {value}{mark}"

    docs = "\n".join(f"  - [ ] {d}" for d in req.get("documents") or []) or "  - [ ] [공고에서 확인]"
    steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(req.get("steps") or [], 1)) or "  1. [공고에서 확인]"
    cautions = "\n".join(f"  - {c}" for c in req.get("cautions") or []) or "  - 원문 공고를 반드시 확인하세요."
    return f"""# {contest.get('name')}

{line('주최', contest.get('host'))}
{line('접수 기간', f"{contest.get('applyStart') or ''} ~ {contest.get('applyEnd') or ''}".strip(' ~'))}
{line('마감 시각', req.get('deadlineTime'))}
{line('참가 자격', contest.get('eligibility') or req.get('eligibility'))}
{line('상금', contest.get('prize'))}
{line('접수 방법', req.get('applyMethod'), 'applyMethod')}
{line('접수처', req.get('applyUrl') or req.get('email'), 'email')}
{line('문의처', req.get('contactEmail'))}
{line('원문 공고', contest.get('url'))}

## 제출물
{docs}

## 형식
{', '.join(req.get('formats') or []) or '[확인 필요]'}

> 제출물·형식은 공고 본문에서 단어를 찾아 추린 것입니다. GEMINI_API_KEY 를 설정하면 공고를 읽어 정확히 정리합니다.

## 절차
{steps}

## 직접 확인해야 하는 것 (대신 체크하지 않습니다)
  - [ ] 참가 자격을 충족하는가
  - [ ] 개인정보 수집·이용 동의
  - [ ] 저작권·중복 출품 관련 서약
  - [ ] 최종 제출 버튼

## 주의
{cautions}
"""


def _email(p: dict, contest: dict, req: dict) -> str:
    return f"""받는 사람: {req.get('email')}
제목: [{contest.get('name')}] 참가 신청 - {p.get('name', '')}

안녕하세요.
{contest.get('name')}에 참가 신청드립니다.

- 이름: {p.get('name', '')}
- 소속: {' '.join(x for x in (p.get('school'), p.get('major'), p.get('grade')) if x)}
- 연락처: {p.get('email', '')} / {p.get('phone', '')}
- 포트폴리오: {(p.get('links') or {}).get('portfolio', '')}

첨부: {', '.join(req.get('documents') or ['[제출 서류]'])}

확인 부탁드립니다. 감사합니다.
{p.get('name', '')} 드림
"""


def build(contest: dict, req: dict, p: dict | None = None) -> Path:
    p = p or profile_mod.load()
    out = DRAFTS / contest["id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "checklist.md").write_text(_checklist(contest, req), encoding="utf-8")
    if is_code_contest(contest, req):
        # Judged on the submission itself; a motivation essay would be invented filler.
        (out / "questions.md").write_text(QUESTIONS.format(name=contest.get("name"), id=contest["id"]), encoding="utf-8")
    else:
        (out / "application.md").write_text(_application(p, contest, req), encoding="utf-8")
    # Only for genuine email submission: a support address is not where an entry is sent.
    if req.get("applyMethod") == "이메일" and req.get("email") and req["email"] != req.get("contactEmail"):
        (out / "email.md").write_text(_email(p, contest, req), encoding="utf-8")
    (out / "requirements.json").write_text(json.dumps(req, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
