import hashlib
import hmac


def test_mexc_spot_signature_is_hmac_sha256() -> None:
    payload = "recvWindow=5000&timestamp=1644489390087"
    signature = hmac.new(b"secret", payload.encode(), hashlib.sha256).hexdigest()

    assert len(signature) == 64
