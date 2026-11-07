"""Unit tests for token metering extraction and estimation."""
from __future__ import annotations

import pytest

from foresight import metering


# ---------------------------------------------------------------- estimate

@pytest.mark.parametrize("text,expected", [
    ("", 0),
    ("x", 1),
    ("abcd", 1),
    ("abcdef", 1),
    ("abcdefgh", 2),
    ("a" * 41, 10),
    (None, 0),
])
def test_estimate_tokens(text, expected):
    assert metering.estimate_tokens(text) == expected


# ----------------------------------------------------------- message text

def test_message_text_concatenates_string_contents_with_roles():
    msgs = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    assert metering.message_text(msgs) == "be brief\nsystem\nhello\nuser\nhi\nassistant"


def test_message_text_reads_text_blocks_from_multimodal_content():
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "text", "text": "again"},
    ]}]
    assert metering.message_text(msgs) == "look\nagain\nuser"


def test_message_text_handles_missing_content_and_none():
    assert metering.message_text(None) == ""
    assert metering.message_text([]) == ""
    assert metering.message_text([{"role": "system"}]) == "system"


# -------------------------------------------------------- completion text

def test_completion_text_from_chat_choices():
    resp = {"choices": [{"message": {"role": "assistant", "content": "ok!"}}]}
    assert metering.completion_text(resp) == "ok!"


def test_completion_text_from_legacy_text_completion():
    resp = {"choices": [{"text": "legacy"}]}
    assert metering.completion_text(resp) == "legacy"


def test_completion_text_empty_payload():
    assert metering.completion_text({}) == ""


# ------------------------------------------------------------ meter pair

def test_meter_chat_request_exact_usage_reported():
    body = {"messages": [{"role": "user", "content": "x" * 100}]}
    resp = {"usage": {"prompt_tokens": 30, "completion_tokens": 7}}
    assert metering.meter_chat_request(body, resp) == (30, 7, True)


def test_meter_chat_request_input_output_token_style():
    resp = {"usage": {"input_tokens": 11, "output_tokens": 3}}
    assert metering.meter_chat_request({}, resp) == (11, 3, True)


def test_meter_chat_request_falls_back_to_estimate():
    body = {"messages": [{"role": "user", "content": "a" * 160}]}    # 160 chars + "\nuser" → 41
    resp = {"choices": [{"message": {"role": "assistant", "content": "b" * 80}}]}  # 80 chars → 20
    assert metering.meter_chat_request(body, resp) == (41, 20, False)


def test_meter_chat_request_ignores_garbage_usage():
    body = {"messages": [{"role": "user", "content": "a" * 40}]}     # 40 chars + "\nuser" → 11
    resp = {"usage": {"prompt_tokens": "many", "completion_tokens": None}}
    assert metering.meter_chat_request(body, resp) == (11, 0, False)


def test_meter_chat_request_empty_everything():
    assert metering.meter_chat_request({}, {}) == (0, 0, False)
