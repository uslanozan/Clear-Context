"""Place extraction rules in the system role without rewriting source data."""

from copy import deepcopy


def move_rules_to_system(messages: list[dict], rules: str) -> list[dict]:
    if not rules.strip():
        raise ValueError("Extraction rules must not be empty")
    updated = deepcopy(messages)
    users = [message for message in updated if message.get("role") == "user"]
    systems = [message for message in updated if message.get("role") == "system"]
    if len(users) != 1 or len(systems) > 1:
        raise ValueError("Expected one LangExtract user message and at most one system")
    content = users[0].get("content")
    if not isinstance(content, str) or not content.startswith(rules):
        raise ValueError("Extraction rules are not the expected prompt prefix")
    users[0]["content"] = content[len(rules) :]
    if systems:
        systems[0]["content"] = systems[0]["content"] + "\n\n" + rules
    else:
        updated.insert(0, {"role": "system", "content": rules})
    return updated


def create_system_instruction_model(*, extraction_rules: str, **kwargs):
    """Adapt the installed provider; never modify LangExtract package files."""
    from langextract.providers.openai import OpenAILanguageModel

    class SystemInstructionModel(OpenAILanguageModel):
        def _build_chat_completions_params(self, prompt, config):
            params = super()._build_chat_completions_params(prompt, config)
            params["messages"] = move_rules_to_system(
                params["messages"], extraction_rules
            )
            return params

    return SystemInstructionModel(**kwargs)
