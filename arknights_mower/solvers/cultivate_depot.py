import datetime
import json
from time import time

from arknights_mower.utils import config
from arknights_mower.utils.config import atomic_write
from arknights_mower.utils.log import logger
from arknights_mower.utils.path import get_path
from arknights_mower.utils.skland import (
    get_binding_list,
    get_cred_by_token,
    get_sign_header,
    header,
    log,
    request_with_retry,
    restore_cached_session,
    skland_cache,
)
from arknights_mower.utils.workshop_data import parse_roster


class cultivate:
    def __init__(self):
        self.record_path = get_path("@app/tmp/cultivate.json")
        self.reward = []
        self.sign_token = ""
        self.all_recorded = True

    def start(self):
        if not config.conf.skland_info:
            return False
        updated = False
        item = config.conf.skland_info[0]

        # 凭据必须成对取用：sign_token 与 header["cred"] 恒来自同一账号。
        # `header` 是全程序共用的（见 utils/skland.py），先点「测试设置」会把它刷成
        # 最后那个账号的 cred；若此处只补 sign_token 而不换 cred，就会出现「按第一个
        # 账号取数、却带着另一个账号的身份」，森空岛按 cred 认人，于是返回了另一个
        # 账号的数据并被原样写入 cultivate.json。参照 player_info._ensure_session。
        account = getattr(item, "account", "") or ""
        session = restore_cached_session(account) if account else None
        if session:
            self.sign_token = session["sign_token"]
            header["cred"] = session["cred"]
            logger.debug("cultivate: reusing cached session of %s", account)
        else:
            # 缓存缺失/过期时走真正的重新登录，避免用空 sign_token 或旧 cred 发起请求
            cred_resp = get_cred_by_token(log(item))
            self.save_param(cred_resp)
            # Share credential so PlayerInfoClient can reuse via skland_cache
            if account:
                skland_cache[account] = {
                    "cred": cred_resp["cred"],
                    "sign_token": cred_resp["token"],
                    "updated_at": datetime.datetime.now(datetime.timezone.utc),
                }

        for i in get_binding_list(self.sign_token):
            if i.get("gameId") == 1 and item.cultivate_select == i.get("isOfficial"):
                body = {"gameId": 1, "uid": i.get("uid")}
                ingame = f"https://zonai.skland.com/api/v1/game/cultivate/player?uid={i.get('uid')}"
                observed_at = time()
                resp = request_with_retry(
                    "get",
                    ingame,
                    headers=get_sign_header(ingame, "get", body, self.sign_token),
                ).json()

                if isinstance(resp, dict) and resp.get("code") != 0:
                    raise ValueError(resp.get("message") or "森空岛返回的干员数据无效")
                parse_roster(resp)
                items = resp.get("data", {}).get("items")
                if items is not None:
                    if not isinstance(items, list) or any(
                        not isinstance(entry, dict)
                        or not isinstance(entry.get("id"), str)
                        or not str(entry.get("count", "")).isdigit()
                        for entry in items
                    ):
                        raise ValueError("森空岛返回的库存数据无效")
                    # Use request start, not completion: a concurrent craft must win.
                    resp = {**resp, "_mower_inventory_observed_at": observed_at}

                def dump(file):
                    json.dump(resp, file, ensure_ascii=False, indent=4)

                # web 线程（views/mastery.py 刷新）与调度线程共用本写点，原子写防撕裂
                atomic_write(self.record_path, dump)
                if items is not None:
                    from arknights_mower.solvers.record import save_inventory_counts
                    from arknights_mower.utils.depot import cloud_inventory_snapshot

                    counts, timestamp = cloud_inventory_snapshot(resp)
                    save_inventory_counts(
                        counts,
                        scanned_counts={},
                        cloud_counts=counts,
                        cloud_at=timestamp,
                    )
                updated = True
                # 只取第一个匹配的绑定：否则同账号下多个绑定会逐个请求并反复覆写
                # cultivate.json，最终留下数组里最后那个的数据，且写盘次数不可控。
                break
        return updated

    def save_param(self, cred_resp):
        header["cred"] = cred_resp["cred"]
        self.sign_token = cred_resp["token"]
