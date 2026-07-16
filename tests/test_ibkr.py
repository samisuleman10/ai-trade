from pathlib import Path

from ai_trade.ibkr import save_snapshot


def test_save_snapshot_creates_json(tmp_path: Path) -> None:
    path = save_snapshot({"positions": [], "accounts": {}}, tmp_path)

    assert path.parent == tmp_path
    assert path.suffix == ".json"
    assert '"positions": []' in path.read_text(encoding="utf-8")
