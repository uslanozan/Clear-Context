import asyncio

from clear_context.core.settings import PROJECT_ROOT
from clear_context.providers.meta_structured import ModelResponseFailure
from clear_context.services.language import detect_language
from clear_context.services.report_text import report_language, report_text

PROMPTS = PROJECT_ROOT / "config/prompts.yaml"


class Model:
    def __init__(self, reply):
        self.reply, self.requests = reply, []

    async def complete(self, payload, timeout):
        self.requests.append(payload)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def run(text, model):
    return asyncio.run(detect_language(text, model, "muse-spark-1.3", PROMPTS))


def answer(content):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 3},
    }


def test_clear_text_is_detected_locally_without_a_model_call():
    model = Model(answer('{"language": "en"}'))
    decision = run(
        "Kemanist fedoncular bu duyguyu bilmez. Konyalı bir kondüktör poz veriyor.", model
    )
    assert (decision.code, decision.method) == ("tr", "langdetect")
    assert model.requests == [] and decision.usage is None


def test_short_text_asks_the_model_with_minimal_effort():
    model = Model(answer('{"language": "TR"}'))
    decision = run("Bu fotoğraf 1970", model)
    assert (decision.code, decision.method) == ("tr", "model")
    request = model.requests[0]
    assert request["reasoning_effort"] == "minimal"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert decision.usage.task == "language_detection"


def test_broken_or_failed_model_answers_keep_the_local_guess():
    for reply in (
        answer("not json"),
        answer('{"language": "Turkish"}'),
        answer('{"other": "tr"}'),
        {"choices": []},
        ModelResponseFailure("transport_error"),
    ):
        decision = run("ok", Model(reply))
        # langdetect's own guess for "ok"; detection never raises.
        assert decision.method in {"langdetect", "unresolved"}
        assert decision.code != "tr"


def test_detected_language_overrides_the_letter_heuristic():
    claim = "Kemanist fedoncular bu duyguyu bilmez."
    assert report_text("needs_context", claim).startswith("Not researched")
    with report_language("tr"):
        assert report_text("needs_context", claim).startswith("Araştırılmadı")
    with report_language("de"):
        # No German messages yet; English is used.
        assert report_text("needs_context", claim).startswith("Not researched")
