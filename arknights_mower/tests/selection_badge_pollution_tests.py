"""右上角徽章污染选中蓝框判定的离线回归。

现象：未选中且带右上角徽章的卡片（如古米），徽章的青蓝色
落入检测窗口的上/下条带，密度落在 0.20 与 0.45 之间，
agent_card_selected 返回 None，调用方无限重读。
"""

from pathlib import Path

import cv2
import pytest

from arknights_mower.solvers.base_mixin import agent_card_selected

pytestmark = pytest.mark.usefixtures("legacy_selection_conf")


@pytest.fixture
def badge_frame():
    """2026-10-02 现场放弃画面：第一列裁剪，古米未选带徽章、安比尔选中带徽章。

    原图为 1920x1080 全屏；这里裁剪 (540,60)-(1480,1010) 保留前三列，
    scope 为该帧上 operator_list 返回的姓名框坐标减去裁剪偏移。
    """
    path = Path(__file__).parent / "fixtures/selection/badge_gumi_column_20261002.png"
    return cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB)


def test_badge_on_unselected_card_is_false_not_none(badge_frame):
    gumi = ((91, 428), (280, 460))
    assert agent_card_selected(badge_frame, gumi) is False


def test_badge_on_selected_card_stays_true(badge_frame):
    # 同列下一张：同样带徽章，但真正被选中，必须仍判为 True
    anbier = ((91, 849), (280, 881))
    assert agent_card_selected(badge_frame, anbier) is True


def test_neighbor_selected_card_in_adjacent_column_stays_true(badge_frame):
    # 右列第一张：芬，被选中且带徽章
    fen = ((307, 428), (497, 460))
    assert agent_card_selected(badge_frame, fen) is True


def test_unselected_badgeless_cards_stay_false(badge_frame):
    # 同帧无徽章卡片：深巡（上行第三列）、维娜·维多利亚（下行第二列）
    assert agent_card_selected(badge_frame, ((523, 428), (712, 460))) is False
    assert agent_card_selected(badge_frame, ((307, 849), (497, 881))) is False
