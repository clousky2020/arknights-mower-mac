"""卫戍协议导航单点验证脚本（仅本地手动运行，不属于测试套件）。

用法：在游戏已登录、设备已连接的前提下，把游戏停在终端首页，然后运行：

    ./.venv/bin/python scripts/check_spa_navigation.py

脚本打印入口来源（OCR / 模板）、页面就绪判断与导航结果。
只验证导航这一段，不启动 MAA、不改配置、不跑整套调度。
"""

from arknights_mower.solvers import navigation as nav
from arknights_mower.solvers.navigation import (
    NavigationSolver,
    find_spa_entry,
    navigate_to_spa,
    spa_page_ready,
)
from arknights_mower.utils import rapidocr


def main():
    rapidocr.initialize_ocr()
    if not rapidocr.engine:
        print("OCR 引擎未就绪，模板兜底仍可用，但特征词识别会跳过。")

    solver = NavigationSolver()
    solver.recog.update()

    ocr = nav._spa_read_ocr(solver)
    hits = [
        item for item in ocr if any(w in str(item[1]) for w in ("卫戍", "卫成", "规程"))
    ]
    print("[诊断] OCR 中卫戍/规程相关条目:")
    for item in hits:
        box = item[0]
        cx = int(sum(p[0] for p in box) / len(box))
        cy = int(sum(p[1] for p in box) / len(box))
        print(f"    {item[1]!r} 置信度 {float(item[2]):.2f} 中心 ({cx}, {cy})")

    tmpl_scope = solver.find(nav._SPA_ENTRY_RES, score=nav._SPA_TEMPLATE_SCORE)
    print("[诊断] 入口模板匹配 scope:", tmpl_scope)

    print("[1] 当前页是否为卫戍协议小游戏主界面:", spa_page_ready(solver))
    print("[2] 终端页卫戍协议入口中心坐标:", find_spa_entry(solver))
    print("    若上面入口为 None，请先把游戏停在终端首页再重跑。")
    print("[3] 开始导航（会真实点击）...")
    result = navigate_to_spa(solver, attempts=3)
    print(
        "[4] 导航结果:", "成功，已进入卫戍协议页面" if result else "失败，详见下方提示"
    )
    if not result:
        print("    失败时请确认：游戏在终端首页、分辨率 1920×1080、活动页入口可见。")


if __name__ == "__main__":
    main()
