#!/usr/bin/env python3
"""从 MaaAssistantArknights/MaaResource 同步缺失物品数据到 arknights-mower。

MAA 的 item_index.json 更新比 arknights-mower 的 key_mapping.json 快，
本脚本把 key_mapping 中缺失的物品 ID 合并进去，并转换对应图标。

用法:
    python sync_maa_resource.py            # git pull MaaResource + 同步
    python sync_maa_resource.py --no-pull  # 跳过 git pull，仅用本地 MaaResource

依赖: cwebp (brew install webp)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

from arknights_mower.utils.path import get_path  # noqa: F401  (仅用于参考，路径直接基于仓库根)

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
MAA_REPO = os.path.expanduser("~/software_project/MaaResource")
KEY_MAPPING_PATH = os.path.join(REPO_ROOT, "arknights_mower", "data", "key_mapping.json")
UI_DEPOT_PATH = os.path.join(REPO_ROOT, "ui", "public", "depot")
MAA_ITEM_INDEX = os.path.join(MAA_REPO, "resource", "item_index.json")
MAA_ITEMS_DIR = os.path.join(MAA_REPO, "resource", "template", "items")

# git pull 需要代理时设置
PROXY_ENV = {
    "https_proxy": "http://127.0.0.1:7890",
    "http_proxy": "http://127.0.0.1:7890",
    "all_proxy": "socks5://127.0.0.1:7890",
}


def git_pull():
    """拉取 MaaResource 仓库最新资源。"""
    if not os.path.isdir(os.path.join(MAA_REPO, ".git")):
        print(f"[!] 未找到 MaaResource 仓库: {MAA_REPO}")
        return False
    env = {**os.environ, **PROXY_ENV}
    try:
        result = subprocess.run(
            ["git", "-C", MAA_REPO, "pull", "--ff-only"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        print(result.stdout.strip())
        if result.returncode != 0:
            print(f"[!] git pull 失败: {result.stderr.strip()}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("[!] git pull 超时")
        return False


def merge_key_mapping():
    """把 item_index 中 key_mapping 缺失的条目合并进去，返回新增 ID 列表。"""
    with open(KEY_MAPPING_PATH, encoding="utf-8") as f:
        key_mapping = json.load(f)
    with open(MAA_ITEM_INDEX, encoding="utf-8") as f:
        item_index = json.load(f)

    known_ids = {
        v[0] for v in key_mapping.values() if isinstance(v, list)
    }
    new_ids = []
    for item_id, info in item_index.items():
        if item_id in known_ids:
            continue
        name = info["name"]
        icon = os.path.splitext(info["icon"])[0] if info.get("icon") else item_id
        entry = [item_id, icon, name, info["classifyType"], info["sortId"]]
        # 与现有格式一致：id 和中文名双键
        key_mapping[item_id] = entry
        key_mapping[name] = entry
        known_ids.add(item_id)
        new_ids.append(item_id)

    if new_ids:
        with open(KEY_MAPPING_PATH, "w", encoding="utf-8") as f:
            json.dump(key_mapping, f, ensure_ascii=False, indent=4)
        print(f"[+] 已合并 {len(new_ids)} 条到 key_mapping.json")
        for item_id in sorted(new_ids):
            print(f"    {item_id}: {item_index[item_id]['name']}")
    else:
        print("[=] key_mapping.json 无新增条目")
    return new_ids


def safe_name(name):
    """文件名安全化：去掉路径分隔符等非法字符。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def sync_icons(new_ids):
    """把新增 ID 的 MAA 图标转成 webp 放进 ui/public/depot/。

    图标按中文名命名（与现有 UI 引用方式一致），同名覆盖无害。
    """
    if not new_ids:
        return
    with open(MAA_ITEM_INDEX, encoding="utf-8") as f:
        item_index = json.load(f)
    converted = skipped = 0
    for item_id in new_ids:
        info = item_index[item_id]
        name = info["name"]
        icon_file = os.path.join(MAA_ITEMS_DIR, info["icon"])
        if not os.path.exists(icon_file):
            skipped += 1
            continue
        dest = os.path.join(UI_DEPOT_PATH, f"{safe_name(name)}.webp")
        result = subprocess.run(
            ["cwebp", "-quiet", icon_file, "-o", dest],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and os.path.exists(dest):
            converted += 1
        else:
            print(f"[!] 图标转换失败 {item_id}: {result.stderr.strip()[:100]}")
            skipped += 1
    print(f"[+] 图标转换 {converted} 个, 跳过 {skipped} 个 -> {UI_DEPOT_PATH}")


def main():
    parser = argparse.ArgumentParser(description="同步 MaaResource 物品数据")
    parser.add_argument("--no-pull", action="store_true", help="跳过 git pull")
    args = parser.parse_args()

    if not args.no_pull:
        if not git_pull():
            print("[!] git pull 失败，尝试用本地数据继续...")
    if not os.path.exists(MAA_ITEM_INDEX):
        print(f"[x] 找不到 {MAA_ITEM_INDEX}")
        sys.exit(1)

    new_ids = merge_key_mapping()
    if new_ids and shutil.which("cwebp"):
        sync_icons(new_ids)
    elif new_ids:
        print("[!] 未安装 cwebp (brew install webp)，跳过图标转换")
    print("[✓] 同步完成")


if __name__ == "__main__":
    main()
