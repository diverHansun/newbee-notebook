from newbee_notebook.infrastructure.bilibili.payloads import (
    normalize_ai_conclusion,
    normalize_search_results,
    normalize_subtitle_items,
    normalize_video_info,
)


def test_normalize_video_info_maps_owner_and_stats():
    payload = normalize_video_info(
        {
            "bvid": "BV1xx411c7mD",
            "pic": "https://example.com/cover.jpg",
            "title": "Demo",
            "duration": 95,
            "owner": {"mid": 42, "name": "UP"},
            "stat": {"view": 12, "like": 3},
        }
    )

    assert payload["video_id"] == "BV1xx411c7mD"
    assert payload["source_url"] == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert payload["uploader_name"] == "UP"
    assert payload["uploader_id"] == "42"
    assert payload["stats"]["view"] == 12
    assert payload["stats"]["like"] == 3


def test_normalize_subtitle_items_preserves_timeline_shape():
    payload = normalize_subtitle_items(
        [
            {"from": 0.0, "to": 1.2, "content": "hello"},
            {"from": 1.2, "to": 2.0, "content": "world"},
        ]
    )

    assert payload == [
        {"from": 0.0, "to": 1.2, "content": "hello"},
        {"from": 1.2, "to": 2.0, "content": "world"},
    ]


def test_normalize_search_results_strips_markup_and_parses_duration():
    payload = normalize_search_results(
        [
            {
                "bvid": "BV1xx411c7mD",
                "title": "<em class=\"keyword\">Demo</em> Video",
                "arcurl": "https://www.bilibili.com/video/BV1xx411c7mD",
                "author": "UP",
                "duration": "01:05",
                "play": "1200",
                "description": "<em>demo</em> description",
            }
        ]
    )

    assert payload == [
        {
            "video_id": "BV1xx411c7mD",
            "title": "Demo Video",
            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "author": "UP",
            "duration": 65,
            "play_count": 1200,
            "description": "demo description",
        }
    ]


def test_normalize_ai_conclusion_returns_empty_string_for_unknown_shape():
    assert normalize_ai_conclusion({"model_result": {"summary": "Quick AI summary"}}) == "Quick AI summary"
    assert (
        normalize_ai_conclusion(
            {"model_result": {"result": [{"summary": "Nested AI summary"}]}}
        )
        == "Nested AI summary"
    )
    assert normalize_ai_conclusion({"unexpected": True}) == ""
