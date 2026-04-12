"""Tests for ErrorClassifier and message modifiers."""

from taim.errors import LLMTransportError
from taim.models.router import LLMErrorType, RetryAction
from taim.router.failover import classify_error, _soften_messages, _add_format_reminder


class TestClassifyError:
    def test_rate_limit_retries_same(self) -> None:
        err = LLMTransportError(LLMErrorType.RATE_LIMIT, "429")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME
        assert decision.backoff_seconds > 0

    def test_rate_limit_backoff_increases(self) -> None:
        err = LLMTransportError(LLMErrorType.RATE_LIMIT, "429")
        d1 = classify_error(err, attempt_number=0, same_provider_attempts=1)
        d2 = classify_error(err, attempt_number=1, same_provider_attempts=2)
        assert d2.backoff_seconds > d1.backoff_seconds

    def test_timeout_first_retries_same(self) -> None:
        err = LLMTransportError(LLMErrorType.TIMEOUT, "timeout")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME

    def test_timeout_second_failover(self) -> None:
        err = LLMTransportError(LLMErrorType.TIMEOUT, "timeout")
        decision = classify_error(err, attempt_number=1, same_provider_attempts=2)
        assert decision.action == RetryAction.FAILOVER

    def test_safety_filter_first_softens(self) -> None:
        err = LLMTransportError(LLMErrorType.SAFETY_FILTER, "blocked")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME
        assert decision.modify_messages is not None

    def test_safety_filter_second_failover(self) -> None:
        err = LLMTransportError(LLMErrorType.SAFETY_FILTER, "blocked")
        decision = classify_error(err, attempt_number=1, same_provider_attempts=2)
        assert decision.action == RetryAction.FAILOVER

    def test_bad_format_first_adds_reminder(self) -> None:
        err = LLMTransportError(LLMErrorType.BAD_FORMAT, "not json")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME
        assert decision.modify_messages is not None

    def test_provider_down_immediate_failover(self) -> None:
        err = LLMTransportError(LLMErrorType.PROVIDER_DOWN, "refused")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.FAILOVER

    def test_auth_error_skips(self) -> None:
        err = LLMTransportError(LLMErrorType.AUTH_ERROR, "401")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.SKIP


class TestMessageModifiers:
    def test_soften_prepends_system_message(self) -> None:
        original = [{"role": "user", "content": "hello"}]
        softened = _soften_messages(original)
        assert len(softened) == 2
        assert softened[0]["role"] == "system"
        assert original == [{"role": "user", "content": "hello"}]

    def test_format_reminder_appends(self) -> None:
        original = [{"role": "user", "content": "classify"}]
        reminded = _add_format_reminder(original)
        assert len(reminded) == 2
        assert reminded[-1]["role"] == "system"
        assert "json" in reminded[-1]["content"].lower()
        assert original == [{"role": "user", "content": "classify"}]
