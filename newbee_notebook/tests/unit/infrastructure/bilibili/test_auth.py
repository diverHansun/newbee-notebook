from newbee_notebook.infrastructure.bilibili.auth import BilibiliAuthManager


def test_auth_manager_reads_saved_credential(tmp_path):
    manager = BilibiliAuthManager(base_dir=tmp_path)

    manager.save_credential(
        {
            "sessdata": "abc",
            "bili_jct": "def",
            "ac_time_value": "ghi",
        }
    )

    payload = manager.load_credential()

    assert payload is not None
    assert payload["sessdata"] == "abc"
    assert payload["bili_jct"] == "def"
    assert manager.credential_path.exists()


def test_auth_manager_clear_removes_saved_credential(tmp_path):
    manager = BilibiliAuthManager(base_dir=tmp_path)
    manager.save_credential({"sessdata": "abc"})

    manager.clear_credential()

    assert manager.load_credential() is None
