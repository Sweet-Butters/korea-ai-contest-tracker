# AI 공모전 레이더

[English](README.md) · **한국어**

대한민국 AI 대회·공모전·해커톤·창업경진대회를 매일 자동으로 모아 보여주는 사이트입니다.
**사이트:** https://sweet-butters.github.io/korea-ai-contest-tracker/

수집은 GitHub Actions에서 정해진 스크립트로만 돌아서, 운영 중에 대화형 LLM 토큰을 쓰지 않습니다.
뉴스 기사에서 대회 정보를 뽑을 때는 Gemini 무료 API를, 키워드 판정을 보정할 때는 TypeSafe Jev를 선택적으로 씁니다.

## 기능

- **목록 / 분야별 / 일정표(달력)** 보기. 달력에는 마감·접수 시작·본선 일정이 표시됩니다.
- **정렬:** 마감 임박순, 상금 높은순, 새로 올라온 순, 많이 알려진 순(출처 수), Jev AI 확신도순, 이름순
- **필터:** 상태(접수중·접수예정·본선 진행중), 분야(키워드 분류), 지역, 출처, AI 관련만, 상금 있는 대회만, 미확인 숨기기
- 공유용 URL: `?view=calendar&sort=prize&cat=hackathon&q=부산`
- **키워드 관리(`/admin`)**: 키워드를 고치면 `config/keywords.json`에 커밋되고 바로 다시 수집합니다. 수집원별 상태, Jev 판정 통계, 최근 실행 기록도 봅니다.

## 구조

```
apps/web        Next.js (TypeScript) — 메인 사이트, 정적 export
apps/admin      Next.js (TypeScript) — 키워드 관리, /admin 에 배포
packages/shared 공용 타입·상금 파싱·날짜 헬퍼·테마
collector/      Python — 수집기 (GitHub Actions에서 실행, 서버 역할)
config/         keywords.json — 수집 규칙
data/           contests.json · meta.json · jev_cache.json · jev_runs.jsonl
```

```
매일 06:00 KST (또는 키워드 저장 시)  →  GitHub Actions
  collector/sources/*   각 사이트에서 목록 수집 (robots.txt 확인, 요청 간격 유지)
  collector/classify.py config/keywords.json 규칙으로 AI·대회 여부와 분야 판별
  collector/jev.py      (키가 있으면) Jev로 규칙 판정 보정
  collector/merge.py    여러 사이트의 같은 대회를 합치고 상태 계산
  → data/*.json 커밋 → web·admin 빌드 → GitHub Pages 배포
```

| 수집원 | 방식 |
|---|---|
| 씽굿, 올콘 | 목록 JSON API |
| 링커리어, 요즘것들, 콘테스트코리아, 위비티 | 서버 렌더링 페이지 파싱 |
| DACON, AIFactory | 페이지에 들어 있는 데이터 추출 |
| 이벤터스 | 공개 검색 API |
| Dev-Event | GitHub README |
| K-Startup, 스타트업레시피 | 정부·기관 창업지원사업, 보육·입주 모집 (대회가 아닌 공고) |
| 기업마당 | 공공데이터포털 오픈API: 전국 정부·지자체 지원사업 공고 (AI·창업 분야만) |
| 네이버 뉴스 | 공식 검색 API (정부·지자체·기업 보도자료용) |

온오프믹스·캠퍼스픽 API·데이커 API는 robots.txt가 수집을 막고 있어 제외했습니다.
수집기는 실행할 때마다 robots.txt를 다시 확인하고, 막힌 사이트는 자동으로 건너뜁니다.

## 설정

저장소 **Settings → Secrets and variables → Actions**에 넣습니다. 모두 없어도 동작합니다.

| 이름 | 종류 | 용도 |
|---|---|---|
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | Secret | [네이버 개발자센터](https://developers.naver.com/apps/)에서 "검색" API 앱 등록 (하루 25,000회 무료). 없으면 뉴스 수집을 건너뜁니다. |
| `GEMINI_API_KEY` | Secret | [Google AI Studio](https://aistudio.google.com/apikey) 무료 키. 새 뉴스 기사에서만 대회명·마감일을 뽑습니다. 없으면 기사 제목과 요약 속 날짜로 "미확인" 항목을 만듭니다. |
| `GEMINI_MODEL` | Variable | 기본값 `gemini-flash-lite-latest` |
| `DATA_GO_KR_KEY` | Secret | [공공데이터포털](https://www.data.go.kr) 일반 인증키. 기업마당 지원사업 공고 API(무료)에 씁니다. 없으면 이 수집원을 건너뜁니다. |
| `TYPESAFE_API_KEY` | Secret | [TypeSafe 콘솔](https://console.typesafe.ai/keys)에서 발급. 공고마다 "AI 대회인가·모집 중인 대회인가·어떤 분야인가"를 확률로 받아 규칙 판정을 보정합니다. 한 번 물은 공고는 `data/jev_cache.json`에 저장돼 새 공고만 보냅니다. 없으면 규칙만으로 판정합니다. 로컬에서는 저장소 루트의 `typesafe_api_key.txt`(git 제외)도 읽습니다. |

GitHub Pages는 **Settings → Pages → Source: GitHub Actions**로 둡니다.

## 키워드 편집

사이트의 **키워드 관리**(`/admin`)에서 편집합니다. 이 저장소에 쓰기 권한이 있는
[Fine-grained token](https://github.com/settings/personal-access-tokens/new)이 필요합니다
(Repository access: 이 저장소만, Permissions: Contents·Actions → Read and write). 토큰은 브라우저에만 저장됩니다.
`config/keywords.json`을 직접 고쳐 커밋해도 같습니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python -m collector.main              # 전체 수집 (DACON 파싱에 Node.js 필요)
python -m collector.main 씽굿 DACON    # 일부만

npm install
npm run dev:web                       # http://localhost:3000
npm run dev:admin                     # http://localhost:3001/admin (다른 포트: -- -p 3001)
npm run build && node scripts/assemble.mjs _site
```

## 주의

각 대회 정보는 요약과 원문 링크만 보여줍니다. 일정·자격은 바뀔 수 있으니 원문 공고를 확인하세요.
`sources`에 `초기조사`로 표시된 항목은 2026-09-21~22 수동 조사로 넣은 초기 데이터입니다.
