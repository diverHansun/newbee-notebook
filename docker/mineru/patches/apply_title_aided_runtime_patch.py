"""Patch MinerU hybrid title aided config lookup to read runtime config per parse.

The hybrid/GPU module caches the config at import time, so Newbee's local GPU
service would otherwise require a mineru-api restart after changing the shared
runtime JSON. The patch reads a Newbee-specific runtime file and leaves
MinerU's own tools config path untouched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


IMPORT_BLOCK = """import os
import time
"""

DYNAMIC_IMPORT_BLOCK = """import json
import os
import time
"""

STATIC_HYBRID_BLOCK = """from mineru.utils.llm_aided import llm_aided_title
title_aided_enable = False
llm_aided_config = get_llm_aided_config()
if llm_aided_config:
    title_aided_config = llm_aided_config.get('title_aided', {})
    title_aided_enable = title_aided_config.get('enable', False)
"""

DYNAMIC_HYBRID_BLOCK = """from mineru.utils.llm_aided import llm_aided_title


def _get_runtime_title_aided_config():
    runtime_config_file = os.getenv('NEWBEE_MINERU_TITLE_AIDED_CONFIG_JSON')
    if runtime_config_file:
        try:
            with open(runtime_config_file, 'r', encoding='utf-8') as f:
                runtime_config = json.load(f)
        except Exception as e:
            logger.warning(f'Failed to read Newbee title aided runtime config: {e}')
            return False, {}
        title_aided_config = runtime_config.get('llm-aided-config', {}).get('title_aided', {})
        return title_aided_config.get('enable', False), title_aided_config

    llm_aided_config = get_llm_aided_config()
    if not llm_aided_config:
        return False, {}
    title_aided_config = llm_aided_config.get('title_aided', {})
    return title_aided_config.get('enable', False), title_aided_config
"""

LINE_HEIGHT_GUARD = """    # 如果有标题优化需求，计算标题的平均行高
    if title_aided_enable:
"""

DYNAMIC_LINE_HEIGHT_GUARD = """    # 如果有标题优化需求，计算标题的平均行高
    title_aided_enable, _ = _get_runtime_title_aided_config()
    if title_aided_enable:
"""

FINALIZE_GUARD = """    if title_aided_enable:
        llm_aided_title_start_time = time.time()
        llm_aided_title(pdf_info_list, title_aided_config)
"""

DYNAMIC_FINALIZE_GUARD = """    title_aided_enable, title_aided_config = _get_runtime_title_aided_config()
    if title_aided_enable:
        llm_aided_title_start_time = time.time()
        llm_aided_title(pdf_info_list, title_aided_config)
"""


def _find_hybrid_module() -> Path:
    spec = importlib.util.find_spec("mineru.backend.hybrid.hybrid_model_output_to_middle_json")
    if spec is None or spec.origin is None:
        raise RuntimeError("Cannot locate MinerU hybrid_model_output_to_middle_json module")
    return Path(spec.origin)


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Cannot apply MinerU title aided patch: missing {label}")
    return text.replace(old, new, 1)


def main() -> None:
    module_path = _find_hybrid_module()
    text = module_path.read_text(encoding="utf-8")
    text = _replace_once(text, IMPORT_BLOCK, DYNAMIC_IMPORT_BLOCK, "import block")
    text = _replace_once(text, STATIC_HYBRID_BLOCK, DYNAMIC_HYBRID_BLOCK, "static config block")
    text = _replace_once(text, LINE_HEIGHT_GUARD, DYNAMIC_LINE_HEIGHT_GUARD, "line-height guard")
    text = _replace_once(text, FINALIZE_GUARD, DYNAMIC_FINALIZE_GUARD, "finalize guard")
    module_path.write_text(text, encoding="utf-8")
    print(f"Applied Newbee MinerU title aided runtime patch: {module_path}")


if __name__ == "__main__":
    main()
