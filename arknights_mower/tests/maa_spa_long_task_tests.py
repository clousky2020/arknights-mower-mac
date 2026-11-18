"""卫戍协议作为第 8 种 MAA 长任务：配置开关、Custom 派发与导航衔接。"""

from unittest.mock import MagicMock

import pytest

from arknights_mower.solvers import base_schedule, navigation  # noqa: E402
from arknights_mower.tests import maa_copilot_tests as helpers  # noqa: E402
from arknights_mower.utils.config.conf import Conf  # noqa: E402

scheduler = helpers.scheduler
files = helpers.files  # noqa: F401  — scheduler fixture 依赖同名的 files fixture


@pytest.fixture
def spa_ready(monkeypatch):
    """让入口导航成功，使这些用例专注于长任务派发本身。"""
    nav = MagicMock(return_value=True)
    monkeypatch.setattr(navigation, "navigate_to_spa", nav)
    return nav


def test_spa_property_gated_by_enable_and_type():
    assert Conf(maa_rg_enable=1, maa_long_task_type="spa").SPA is True
    assert Conf(maa_rg_enable=0, maa_long_task_type="spa").SPA is False
    assert Conf(maa_rg_enable=1, maa_long_task_type="rogue").SPA is False


def test_spa_counts_as_maa_task(monkeypatch):
    monkeypatch.setattr(Conf, "has_maa_daily_tasks", property(lambda self: False))
    assert Conf(maa_rg_enable=1, maa_long_task_type="spa").has_maa_tasks is True
    assert Conf(maa_rg_enable=1, maa_long_task_type="sf").has_maa_tasks is False


def test_spa_submits_custom_pipeline_after_navigation(scheduler, spa_ready):
    base_schedule.config.conf.maa_long_task_type = "spa"
    order = MagicMock()
    order.attach_mock(scheduler.MAA.append_task, "append")
    order.attach_mock(scheduler.MAA.start, "start")

    scheduler.maa_plan_solver([], long_task="spa")

    spa_ready.assert_called_once_with(scheduler)
    append_calls = [c for c in order.mock_calls if c[0] == "append"]
    assert len(append_calls) == 1
    assert append_calls[0].args[0] == "Custom"
    assert append_calls[0].args[1]["task_names"] == ["MiniGame@SPA@Begin"]
    assert append_calls[0].args[1]["params"] == {}
    assert append_calls[0] == order.mock_calls[0]
    assert any(c[0] == "start" for c in order.mock_calls)


def test_spa_skips_maa_when_navigation_fails(scheduler, monkeypatch):
    monkeypatch.setattr(navigation, "navigate_to_spa", lambda solver: False)
    base_schedule.config.conf.maa_long_task_type = "spa"

    scheduler.maa_plan_solver([], long_task="spa")

    scheduler.MAA.append_task.assert_not_called()
    scheduler.MAA.start.assert_not_called()


def test_spa_flag_selected_from_config_without_explicit_long_task(scheduler, spa_ready):
    base_schedule.config.conf.maa_long_task_type = "spa"
    scheduler.maa_plan_solver([])
    kinds = [c.args[0] for c in scheduler.MAA.append_task.call_args_list]
    assert "Custom" in kinds
