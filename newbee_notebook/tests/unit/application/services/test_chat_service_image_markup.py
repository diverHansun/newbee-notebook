from newbee_notebook.application.services.chat_service import ChatService


def test_strip_generated_image_markup_removes_non_http_markdown_placeholder():
    content = (
        "已为您生成一张软萌小猫插画：\n\n"
        "![软萌小猫插画](generated_image_url)\n\n"
        "这只小猫有着圆润可爱的外形。"
    )

    cleaned = ChatService._strip_generated_image_markup(content, images=["img-1"])

    assert "generated_image_url" not in cleaned
    assert "![软萌小猫插画]" not in cleaned
    assert "已为您生成一张软萌小猫插画：" in cleaned
    assert "这只小猫有着圆润可爱的外形。" in cleaned


def test_strip_generated_image_markup_removes_html_img_with_local_source():
    content = (
        "图片如下：\n"
        "<img src=\"/api/v1/generated-images/demo/data\" alt=\"软萌小猫插画\" />\n"
        "请继续说明。"
    )

    cleaned = ChatService._strip_generated_image_markup(content, images=["img-2"])

    assert "<img" not in cleaned
    assert "图片如下：" in cleaned
    assert "请继续说明。" in cleaned


def test_strip_generated_image_markup_keeps_content_unchanged_without_images():
    content = "![软萌小猫插画](generated_image_url)"

    cleaned = ChatService._strip_generated_image_markup(content, images=None)

    assert cleaned == content
