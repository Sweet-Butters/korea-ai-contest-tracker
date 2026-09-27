// GitHub Contents API helpers for the admin. The token never leaves this browser except as the
// Authorization header to api.github.com.

import { PRIVATE_REPO } from "@radar/shared";

export type Api = (path: string, init?: RequestInit) => Promise<Response>;

export const b64decode = (s: string) =>
  new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), (c) => c.charCodeAt(0)));

export const b64encode = (s: string) => {
  let bin = "";
  for (const byte of new TextEncoder().encode(s)) bin += String.fromCharCode(byte);
  return btoa(bin);
};

export function makeApi(repo: { owner: string; repo: string }, token: string): Api {
  return (path, init = {}) =>
    fetch(`https://api.github.com/repos/${repo.owner}/${repo.repo}${path ? `/${path}` : ""}`, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/vnd.github+json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
}

export const PRIVATE_REPO_NAME = `${PRIVATE_REPO.owner}/${PRIVATE_REPO.repo}`;

/**
 * Result of reading a JSON file from the private repo. "no-token" and "no-access" never carry
 * data: the admin must not fall back to any public copy.
 */
export type ReadResult<T> =
  | { kind: "ok"; data: T; sha: string }
  | { kind: "missing" }
  | { kind: "no-token" }
  | { kind: "no-access"; status: number }
  | { kind: "error"; status: number };

export async function readPrivateJson<T>(api: Api, token: string, path: string): Promise<ReadResult<T>> {
  if (!token) return { kind: "no-token" };
  let r: Response;
  try {
    r = await api(`contents/${path}?ref=${PRIVATE_REPO.branch}`);
  } catch {
    return { kind: "error", status: 0 };
  }
  if (r.ok) {
    const j = await r.json();
    return { kind: "ok", data: JSON.parse(b64decode(j.content)) as T, sha: j.sha };
  }
  if (r.status === 401 || r.status === 403) return { kind: "no-access", status: r.status };
  if (r.status === 404) {
    // 404 is both "file not there" and "repo not visible to this token"; the repo call tells which.
    const repo = await api("").catch(() => null);
    return repo?.ok ? { kind: "missing" } : { kind: "no-access", status: 404 };
  }
  return { kind: "error", status: r.status };
}

/** Commit a JSON file to the private repo. Returns the new sha, or a Korean error message. */
export async function writePrivateJson(
  api: Api, path: string, body: unknown, sha: string | null, message: string, indent = 2,
): Promise<{ ok: true; sha: string } | { ok: false; error: string }> {
  let r: Response;
  try {
    r = await api(`contents/${path}`, {
      method: "PUT",
      body: JSON.stringify({
        message,
        content: b64encode(JSON.stringify(body, null, indent) + "\n"),
        ...(sha ? { sha } : {}),
        branch: PRIVATE_REPO.branch,
      }),
    });
  } catch {
    return { ok: false, error: "네트워크 오류로 저장하지 못했습니다." };
  }
  if (r.ok) return { ok: true, sha: (await r.json()).content.sha };
  return { ok: false, error: saveError(r.status) };
}

export function saveError(status: number): string {
  switch (status) {
    case 409:
    case 422:
      return `다른 곳에서 먼저 바뀌었습니다 (${status}). 내 수정 내용을 복사해 두고 다시 불러오세요.`;
    case 401:
      return "토큰이 만료됐거나 잘못됐습니다 (401). 새 토큰을 넣어 주세요.";
    case 403:
      return `이 토큰에 ${PRIVATE_REPO_NAME} 쓰기 권한(Contents: Read and write)이 없습니다 (403).`;
    case 404:
      return `이 토큰으로 ${PRIVATE_REPO_NAME} 저장소가 보이지 않습니다 (404). 토큰의 저장소 목록에 추가하세요.`;
    default:
      return `저장 실패 (${status})`;
  }
}

export function readErrorText(r: ReadResult<unknown>): string {
  switch (r.kind) {
    case "no-token":
      return `비공개 저장소 ${PRIVATE_REPO_NAME}에 접근할 수 있는 GitHub 토큰이 필요합니다. 위의 토큰 칸에 넣어 주세요.`;
    case "no-access":
      return r.status === 401
        ? "토큰이 만료됐거나 잘못됐습니다 (401). 새 토큰을 넣어 주세요."
        : `이 토큰으로는 비공개 저장소 ${PRIVATE_REPO_NAME}를 읽을 수 없습니다 (${r.status}). 토큰의 저장소 목록에 ${PRIVATE_REPO_NAME}를 추가하고 Contents 권한을 주세요.`;
    case "error":
      return r.status ? `불러오기 실패 (${r.status})` : "네트워크 오류로 불러오지 못했습니다.";
    default:
      return "";
  }
}
