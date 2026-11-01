"""LLM 호출: 1단계 분석(JSON) / 2단계 댓글 작성. provider 는 config.yaml 의 llm.provider."""
import json

import anthropic
import httpx

from .config import env, settings

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "worry": {"type": "string"},
        "key_moments": {"type": "array", "items": {"type": "string"}},
        "viewer_persona": {"type": "string"},
    },
    "required": ["worry", "key_moments", "viewer_persona"],
    "additionalProperties": False,
}


class LLMError(RuntimeError):
    pass


_client = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    return _client


def _call(system: str, user: str, schema: dict | None = None) -> str:
    cfg = settings["llm"]
    if cfg["provider"] == "anthropic":
        output_config = {"effort": "low"}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        try:
            resp = _anthropic().beta.messages.create(
                model=cfg["model"], max_tokens=4000, system=system,
                messages=[{"role": "user", "content": user}],
                output_config=output_config,
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
        except anthropic.AuthenticationError:
            raise LLMError("Anthropic API 키가 올바르지 않습니다 (.env 확인).")
        except anthropic.RateLimitError:
            raise LLMError("Anthropic API 사용량 한도에 걸렸습니다. 잠시 후 다시 시도하세요.")
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic API 오류 {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            raise LLMError("Anthropic API에 연결하지 못했습니다 (네트워크 확인).")
        if resp.stop_reason == "refusal":
            raise LLMError("LLM이 요청을 거절했습니다.")
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    if cfg["provider"] == "openai":
        body = {"model": cfg["model"],
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if schema:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "out", "schema": schema, "strict": True}}
        r = httpx.post("https://api.openai.com/v1/chat/completions", json=body, timeout=60,
                       headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"})
        if r.status_code != 200:
            raise LLMError(f"OpenAI API 오류 {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"].strip()

    raise LLMError(f"지원하지 않는 llm.provider: {cfg['provider']}")


def analyze(video: dict, transcript: str | None, comments: list[str]) -> dict:
    system = ("너는 유튜브 연애 콘텐츠 분석가다. 영상 자료를 읽고 영상이 다루는 연애 고민과 "
              "시청자가 기억할 구체적 장면/발언을 뽑는다. 자료에 없는 내용은 지어내지 않는다.")
    body = transcript or f"(자막 없음 — 제목·설명으로 판단)\n설명: {video['description'][:2000]}"
    top = "\n".join(f"- {c[:200]}" for c in comments[:20]) or "(댓글 없음)"
    user = (f"제목: {video['title']}\n채널: {video['channel']}\n\n[영상 내용]\n{body}\n\n[인기 댓글]\n{top}\n\n"
            "worry: 영상이 다루는 연애 고민 한 줄 (40자 이내)\n"
            "key_moments: 영상 속 구체적 장면/발언 2~3개 (각 30자 이내). 자막이 없으면 제목·설명·인기 댓글에 "
            "나온 구체적 내용(사연, 상황, 인물의 말)으로 채운다. '자막 없음', '확인 불가' 같은 자료 상태 설명은 절대 넣지 않는다.\n"
            "viewer_persona: 이 영상을 볼 법한 시청자 상 한 줄")
    return json.loads(_call(system, user, ANALYSIS_SCHEMA))


def write_comment(video: dict, analysis: dict, feedback: list[str] | None = None) -> str:
    c = settings["comment"]
    system = (
        f"너는 '{analysis['viewer_persona']}' 인 유튜브 시청자다. 영상을 보고 댓글 하나를 쓴다.\n"
        f"- {c['min_chars']}~{c['max_chars']}자 (공백 포함)\n"
        "- key_moments 중 최소 1개를 구체적으로 언급\n"
        f"- 흐름: 공감 → 자기 경험/감정 한 줄 → '{c['brand']} 연애사주가 잘 본다던데 나도 한번 보고 싶다'류의 궁금함/바람 톤\n"
        f"- 금지: 링크, 해시태그(#), {c['brand']}을(를) 이미 이용해 본 것 같은 후기 표현(봤는데, 받았는데, 소름 등), 광고 문구 티\n"
        "- 구어체, 'ㅠㅠ', '...' 정도는 자연스럽게. 댓글 본문만 출력.\n"
        "예시: 근데 진짜 남자심리는 알다가도 모르겠다...ㅠㅠ 맨날 연애하면 차이기만 했던 1인. "
        f"{c['brand']} 연애사주가 그렇게 잘 본다던데 나도 언제 짝 만나는지 한번 보고 싶다."
    )
    user = (f"영상 제목: {video['title']}\n고민: {analysis['worry']}\n"
            f"key_moments: {json.dumps(analysis['key_moments'], ensure_ascii=False)}")
    if feedback:
        user += "\n\n이전 초안이 다음 이유로 탈락했다. 고쳐서 다시 써라:\n- " + "\n- ".join(feedback)
    text = _call(system, user).strip()
    # 댓글 전체를 감싼 따옴표만 벗긴다 (발언 인용으로 시작·끝나는 따옴표는 남김)
    if len(text) >= 2 and text[0] == text[-1] == '"' and text.count('"') == 2:
        text = text[1:-1].strip()
    return text
