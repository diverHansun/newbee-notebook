from newbee_notebook.infrastructure.storage.local_storage import _decode_filename


CN_PDF_NAME = "\u4e2d\u6587.pdf"


def test_decode_filename_keeps_ascii():
    assert _decode_filename("report_2026.pdf") == "report_2026.pdf"


def test_decode_filename_utf8_mojibake():
    # Chinese filename encoded as utf-8 bytes then incorrectly decoded as latin-1.
    mojibake = CN_PDF_NAME.encode("utf-8").decode("latin1")
    assert _decode_filename(mojibake) == CN_PDF_NAME


def test_decode_filename_gbk_mojibake():
    # Chinese filename encoded as GBK bytes then incorrectly decoded as latin-1.
    mojibake = CN_PDF_NAME.encode("gbk").decode("latin1")
    assert _decode_filename(mojibake) == CN_PDF_NAME


def test_decode_filename_percent_encoded_utf8():
    assert _decode_filename("%E4%B8%AD%E6%96%87.pdf") == CN_PDF_NAME


def test_decode_filename_sanitizes_path_separators():
    input_name = f"..\\folder/{CN_PDF_NAME}"
    assert _decode_filename(input_name) == f".._folder_{CN_PDF_NAME}"
