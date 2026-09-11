from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:180]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/sao_mcp/runtime/gm_observation.py",
    '''    def _messages(self, observer_id: str) -> list[dict[str, Any]]:\n        if not hasattr(self.runtime, "message_inbox"):\n            return []\n        return [\n            {\n                "message_id": message.message_id,\n                "sender_id": message.sender_id,\n                "channel": message.channel.value,\n                "text": message.text,\n                "sent_at_ms": message.sent_at_ms,\n                "read_at_ms": message.read_at_ms,\n            }\n            for message in self.runtime.message_inbox(observer_id)\n        ]\n''',
    '''    def _messages(self, observer_id: str) -> list[dict[str, Any]]:\n        if not hasattr(self.runtime, "message_inbox"):\n            return []\n        rows = []\n        for message in self.runtime.message_inbox(observer_id):\n            row = {\n                "message_id": message.message_id,\n                "sender_id": message.sender_id,\n                "channel": message.channel.value,\n                "sent_at_ms": message.sent_at_ms,\n                "read_at_ms": message.read_at_ms,\n                "unread": message.read_at_ms is None,\n            }\n            if message.read_at_ms is not None:\n                row["text"] = message.text\n            rows.append(row)\n        return rows\n''',
)

path = ROOT / "tests/test_gm_observation_gate.py"
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_unread_message_content_is_not_visible_to_gm_until_the_player_reads_it():\n    runtime = SocialCommunicationAincradRuntime(seed=1707)\n    sender = runtime.create_character("Sender")\n    observer = runtime.create_character("Observer")\n    request = runtime.request_friend(sender.actor_id, observer.actor_id)\n    runtime.accept_friend(request.request_id, observer.actor_id)\n    message = runtime.send_short_message(sender.actor_id, observer.actor_id, "Secret route at dawn")\n\n    before = GMObservationGate(runtime).observe([observer.actor_id])\n    row = next(\n        item for item in before["viewpoints"][observer.actor_id]["messages"]\n        if item["message_id"] == message.message_id\n    )\n    assert row["unread"] is True\n    assert "text" not in row\n    assert "Secret route at dawn" not in repr(before)\n\n    runtime.read_message(observer.actor_id, message.message_id)\n    after = GMObservationGate(runtime).observe([observer.actor_id])\n    row = next(\n        item for item in after["viewpoints"][observer.actor_id]["messages"]\n        if item["message_id"] == message.message_id\n    )\n    assert row["unread"] is False\n    assert row["text"] == "Secret route at dawn"\n'''
path.write_text(text, encoding="utf-8")
