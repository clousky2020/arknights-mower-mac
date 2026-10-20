"""右上角徽章污染选中蓝框判定的离线回归。

徽章是青蓝色圆角矩形，落在检测窗口上沿的右半，把上沿密度从约 0
抬到 0.2 出头：未达 0.45 的选中阈值，却足以越过「一条横边缺失」
所需的 0.20 以下。因此同一帧里会出现两种结果——徽章本身由「两条
竖边及下沿前段均缺失」兜成未选中（另一枚现场帧见
selection_border_geometry_tests），而右邻同时被选中时，右邻的蓝色
左边框会擦进本卡窗口最右 8 列，该判定要求两条竖边都干净，于是只剩
None。调用方把 None 当「边框不清晰」：记 debug 后抛
AgentSelectionNotReady 返回房间重试，不会误点。
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


def test_badge_with_selected_right_neighbor_stays_unknown(badge_frame):
    # 古米未选中、右上角带徽章，且右邻芬被选中：窗口 69..294，
    # 芬的蓝框左边落在 285，于是本卡窗口最右 8 列被邻框占满。
    # 上沿（0.214）与下沿（0.254）都被徽章和下排选中卡抬离 0，
    # 右竖边（0.875）来自邻框，可用证据既不足以判未选中，也不能
    # 判选中，因此返回 None 交由调用方重读。
    gumi = ((91, 428), (280, 460))
    assert agent_card_selected(badge_frame, gumi) is None


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
