"""卫戍协议入口导航：OCR 主路径、模板兜底、页面确认与导航流程。

OCR 结果形如 ``[box, text, score]``，box 是四个 ``(x, y)`` 顶点。这里用假的
OCR 结果和 find 返回值驱动，避免依赖真机截图。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from arknights_mower.solvers import navigation  # noqa: E402
from arknights_mower.utils import rapidocr  # noqa: E402
from arknights_mower.utils.scene import Scene  # noqa: E402


def ocr_item(text, cx, cy, score=1.0):
    box = [
        (cx - 20, cy - 10),
        (cx + 20, cy - 10),
        (cx + 20, cy + 10),
        (cx - 20, cy + 10),
    ]
    return [box, text, score]


def solver_stub(scene=Scene.TERMINAL_MAIN):
    solver = SimpleNamespace()
    solver.recog = MagicMock()
    solver.scene = MagicMock(return_value=scene)
    solver.scene_graph_navigation = MagicMock()
    solver.tap_and_detect_page_move = MagicMock()
    solver.find = MagicMock(return_value=None)
    solver.sleep = MagicMock()
    return solver


def patch_ocr(monkeypatch, pages):
    """按调用顺序返回各页的 OCR 结果；耗尽后重复最后一页。"""
    state = {"n": 0}

    def fake_engine(img, **kwargs):
        result = pages[min(state["n"], len(pages) - 1)]
        state["n"] += 1
        return result, None

    monkeypatch.setattr(rapidocr, "engine", fake_engine)


def test_page_ready_needs_two_markers(monkeypatch):
    solver = solver_stub()
    patch_ocr(monkeypatch, [[ocr_item("协议数据库", 100, 100)]])
    assert navigation.spa_page_ready(solver) is False

    patch_ocr(
        monkeypatch,
        [[ocr_item("协议数据库", 100, 100), ocr_item("极速模拟", 300, 100)]],
    )
    assert navigation.spa_page_ready(solver) is True


def test_page_ready_false_without_engine(monkeypatch):
    monkeypatch.setattr(rapidocr, "engine", None)
    assert navigation.spa_page_ready(solver_stub()) is False


def test_page_ready_by_template_when_ocr_misses(monkeypatch):
    solver = solver_stub()
    patch_ocr(monkeypatch, [[]])
    solver.find.return_value = ((35, 265), (420, 385))
    assert navigation.spa_page_ready(solver) is True
    solver.find.assert_called_once_with(navigation._SPA_PAGE_RES, score=0.9)


def test_find_entry_ignores_central_banner(monkeypatch):
    solver = solver_stub()
    # x≈1080 的中间主视觉与右侧入口同名，只应命中右侧那个。
    patch_ocr(
        monkeypatch,
        [[ocr_item("卫戍协议", 1080, 330), ocr_item("卫戍协议", 1607, 499)]],
    )
    assert navigation.find_spa_entry(solver) == (1607, 499)


def test_find_entry_prefers_activity_name_over_rule(monkeypatch):
    solver = solver_stub()
    patch_ocr(
        monkeypatch,
        [[ocr_item("规程", 1592, 533), ocr_item("卫成协议", 1607, 499)]],
    )
    assert navigation.find_spa_entry(solver) == (1607, 499)


def test_find_entry_none_without_right_side_hit(monkeypatch):
    solver = solver_stub()
    patch_ocr(monkeypatch, [[ocr_item("卫戍协议", 1080, 330)]])
    assert navigation.find_spa_entry(solver) is None


def test_find_entry_by_template_when_ocr_misses(monkeypatch):
    solver = solver_stub()
    patch_ocr(monkeypatch, [[]])
    solver.find.return_value = ((1425, 465), (1885, 605))
    assert navigation.find_spa_entry(solver) == (1655, 535)
    solver.find.assert_called_once_with(navigation._SPA_ENTRY_RES, score=0.9)


def test_navigate_returns_early_when_already_on_page(monkeypatch):
    solver = solver_stub()
    patch_ocr(
        monkeypatch,
        [[ocr_item("协议数据库", 100, 100), ocr_item("极速模拟", 300, 100)]],
    )
    assert navigation.navigate_to_spa(solver) is True
    solver.scene_graph_navigation.assert_not_called()
    solver.tap_and_detect_page_move.assert_not_called()


def test_navigate_fails_when_not_on_terminal(monkeypatch):
    solver = solver_stub(scene=Scene.OPERATOR_CHOOSE_LEVEL)
    patch_ocr(monkeypatch, [[]])
    assert navigation.navigate_to_spa(solver) is False
    solver.tap_and_detect_page_move.assert_not_called()


def test_navigate_full_success(monkeypatch):
    solver = solver_stub()
    ready = [ocr_item("协议数据库", 100, 100), ocr_item("极速模拟", 300, 100)]
    # 第 1 次检测尚未进入；回终端后定位入口；点击后确认命中主界面特征词。
    patch_ocr(
        monkeypatch,
        [[], [ocr_item("卫戍协议", 1607, 499)], ready],
    )
    assert navigation.navigate_to_spa(solver, attempts=2) is True
    solver.scene_graph_navigation.assert_called_once_with(Scene.TERMINAL_MAIN)
    solver.tap_and_detect_page_move.assert_called_once_with(
        (1607, 499), "卫戍协议", record_step=False
    )
    solver.sleep.assert_not_called()


def test_navigate_confirm_retries(monkeypatch):
    solver = solver_stub()
    ready = [ocr_item("协议数据库", 100, 100), ocr_item("极速模拟", 300, 100)]
    patch_ocr(
        monkeypatch,
        [[], [ocr_item("卫戍协议", 1607, 499)], [], [], ready],
    )
    assert navigation.navigate_to_spa(solver, attempts=3) is True
    assert solver.sleep.call_count == 2
