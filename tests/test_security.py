from src.core.security import compute_signature


def test_compute_signature() -> None:
    payload = b"test-payload"
    secret = "test-secret"

    expected = "5b12467d7c448555779e70d76204105c67d27d1c991f3080c19732f9ac1988ef"

    result = compute_signature(payload, secret)
    assert result == expected
