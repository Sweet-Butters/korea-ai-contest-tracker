"""Read an application form's questions from the browser, then write answers for them.

    python -m apply capture <id> [page-id]   로그인해 둔 Orca 탭에서 문항을 읽어 저장
    python -m apply answers <id>             읽어온 문항에 프로필로 답 초안 작성

Most application forms are behind a login, so the questions cannot be fetched from outside.
capture reads the open page's own DOM (labels, textareas, length limits) through the Orca CLI;
answers writes one draft per question, sized to each field's limit.

Consent, eligibility and the submit button are never touched — capture only reads.
"""
import json
import re
import subprocess
from pathlib import Path

from collector import llm

from . import draft, profile as profile_mod

# Runs inside the page: collect every question-like field with its label and limit.
EXTRACT_JS = r"""
(() => {
  // A form's real question is usually a heading above the box; the box's own label is often
  // just placeholder text ("내용을 입력해주세요"), so walk up and take the nearest real text.
  const NOISE = /^(내용|담당\s*업무|내용을|값을|여기에)?\s*(입력|작성)(해\s*주세요|하세요)?\.?$/;
  const clean = (t) => (t || "").replace(/\s+/g, " ").trim();
  const question = (el) => {
    let node = el, hops = 0;
    while (node && hops++ < 6) {
      const box = node.closest("section,fieldset,div");
      if (!box) break;
      const texts = [...box.querySelectorAll("label,legend,h1,h2,h3,h4,p,strong,span")]
        .map((n) => clean(n.innerText))
        .filter((t) => t.length > 5 && t.length < 300 && !NOISE.test(t) && !/^\d+자/.test(t));
      if (texts.length) return texts.slice(0, 2).join(" — ").slice(0, 300);
      node = box.parentElement;
    }
    return clean(el.getAttribute("placeholder") || el.name || "");
  };
  const limitFrom = (el) => {
    if (el.maxLength > 0) return el.maxLength;
    const box = el.closest("section,fieldset,div");
    const m = box && /최대\s*([\d,]+)\s*자/.exec(box.innerText || "");
    return m ? +m[1].replace(/,/g, "") : null;
  };
  const out = [];
  document.querySelectorAll("textarea, input[type=text], input[type=email], input[type=tel], select, input[type=file]")
    .forEach((el) => {
      const label = question(el);
      if (!label) return;
      out.push({
        kind: el.tagName.toLowerCase() === "textarea" ? "long" : (el.type || "text"),
        label,
        name: el.name || el.id || "",
        placeholder: clean(el.getAttribute("placeholder")),
        required: el.required || /필수/.test(label),
        maxLength: limitFrom(el),
        options: el.tagName.toLowerCase() === "select" ? [...el.options].map((o) => o.text).slice(0, 20) : undefined,
      });
    });
  return JSON.stringify({ url: location.href, title: document.title, fields: out });
})()
"""


PROMPT = """너는 한국 공모전·채용 해커톤 지원서를 쓰는 것을 돕는다. 아래 지원자 정보로 각 문항의 답 초안을 써라.

분량 규칙 (가장 중요):
- 문항에 최대 글자 수가 있으면 **그 80~95%를 채워라**. 2000자 제한이면 1600~1900자다. 짧게 끝내지 마라.
- 소재가 모자라면 지원자 정보의 사례(stories)·판단(decisions)·수치를 더 끌어와 사례를 2~3개로 늘려라.

내용 규칙:
- **지원자 정보에 없는 사실을 만들지 마라.** 빠진 부분은 "[확인 필요: …]" 로 남겨라.
- 문제 → 한 일(방법·도구) → 결과(숫자) 순서로 쓴다. 각오·형용사·포부는 빼라.
- 수치는 지원자 정보에 적힌 그대로 인용한다.
- "무엇을 하지 않기로 했는지"를 최소 한 번 넣어라. 판단의 근거가 된다.
- 문항이 요구하는 초점(예: "결과물 중심")을 그대로 따른다.
- 자격·동의·개인정보·날짜 형식 칸에는 답하지 말고 "직접 확인" 이라고만 써라.

[지원자]
{profile}

[대회]
{contest}

[문항]
{questions}

JSON으로만 답하라: {{"answers":[{{"label":"문항 그대로","text":"답 초안","chars":글자수}}]}}"""


def _orca(args: list[str]) -> dict:
    r = subprocess.run(["orca", *args, "--json"], capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"orca 응답을 읽지 못했습니다: {(r.stdout or r.stderr)[:200]}")


def capture(contest_id: str, page: str | None = None) -> Path:
    args = ["eval", "--expression", EXTRACT_JS]
    if page:
        args += ["--page", page]
    res = _orca(args)
    if not res.get("ok"):
        raise RuntimeError(res.get("error", {}).get("message", "eval 실패"))
    payload = json.loads(res["result"]["result"])
    out = draft.DRAFTS / contest_id
    out.mkdir(parents=True, exist_ok=True)
    path = out / "form.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    longs = [f for f in payload["fields"] if f["kind"] == "long"]
    print(f"{payload['title'][:50]} — 입력칸 {len(payload['fields'])}개 (서술형 {len(longs)}개)")
    for f in payload["fields"]:
        limit = f" ({f['maxLength']}자)" if f.get("maxLength") else ""
        print(f"  [{f['kind']}]{' *' if f['required'] else ''} {f['label'][:70]}{limit}")
    print(f"저장: {path}")
    return path


def answers(contest_id: str, contest: dict) -> Path:
    out = draft.DRAFTS / contest_id
    form = json.loads((out / "form.json").read_text(encoding="utf-8"))
    p = profile_mod.load()
    asked = [f for f in form["fields"] if f["kind"] == "long" or (f.get("maxLength") or 0) > 80]
    if not asked:
        raise RuntimeError("서술형 문항을 찾지 못했습니다. 신청 페이지에서 다시 capture 하세요.")
    if not llm.available():
        raise RuntimeError("GEMINI_API_KEY 가 없어 초안을 쓸 수 없습니다.")
    qs = "\n".join(f"- {f['label']}" + (f" (최대 {f['maxLength']}자)" if f.get("maxLength") else "") for f in asked)
    got = llm._gemini(PROMPT.format(
        profile=profile_mod.summary(p, for_llm=True),
        contest=f"{contest.get('name')} / {contest.get('host')} / 마감 {contest.get('applyEnd')}",
        questions=qs,
    ))
    rows = (got or {}).get("answers", []) if isinstance(got, dict) else got
    body = [f"# {contest.get('name')} — 문항별 답 초안", "",
            f"출처: {form['url']}", "",
            "> 지원자 정보에 없는 것은 [확인 필요]로 두었습니다. 자격·동의 항목은 직접 확인하세요.", ""]
    limits = {f["label"]: f.get("maxLength") for f in asked}
    for r in rows or []:
        text = (r.get("text") or "").strip()
        limit = limits.get(r.get("label"))
        gauge = f"{len(text)}자" + (f" / 최대 {limit}자 ({len(text) / limit:.0%})" if limit else "")
        body += [f"## {r.get('label')}", "", text, "", f"<!-- {gauge} -->", ""]
        print(f"  {gauge}  {str(r.get('label'))[:46]}")
    path = out / "answers.md"
    path.write_text("\n".join(body), encoding="utf-8")
    print(f"문항 {len(rows or [])}개에 대한 초안 저장: {path}")
    return path
