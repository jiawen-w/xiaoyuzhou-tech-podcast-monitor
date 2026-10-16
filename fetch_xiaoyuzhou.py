#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小宇宙科技播客监测 · 抓取脚本
抓取监测清单中各频道的小宇宙主页，解析 __NEXT_DATA__，输出最近 N 集的结构化数据。

用法:
    python fetch_xiaoyuzhou.py                # 默认每频道取最近 3 集，输出到 episodes.json
    python fetch_xiaoyuzhou.py --limit 5      # 每频道取最近 5 集
    python fetch_xiaoyuzhou.py --dry-run      # 只打印，不写文件
"""

import argparse
import json
import re
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 监测频道清单：名称 -> 小宇宙频道主页
CHANNELS = {
    "硅谷101": "https://www.xiaoyuzhoufm.com/podcast/5e5c52c9418a84a04625e6cc",
    "声动早咖啡": "https://www.xiaoyuzhoufm.com/podcast/60de7c003dd577b40d5a40f3",
    "What's Next｜科技早知道": "https://www.xiaoyuzhoufm.com/podcast/5e74b52c418a84a046ecaceb",
    "商业就是这样": "https://www.xiaoyuzhoufm.com/podcast/6022a180ef5fdaddc30bb101",
    "疯投圈": "https://www.xiaoyuzhoufm.com/podcast/5e280faf418a84a0461fbd39",
    "硬地骇客": "https://www.xiaoyuzhoufm.com/podcast/640ee2438be5d40013fe4a87",
    "晚点聊 LateTalk": "https://www.xiaoyuzhoufm.com/podcast/61933ace1b4320461e91fd55",
    "乱翻书": "https://www.xiaoyuzhoufm.com/podcast/61358d971c5d56efe5bcb5d2",
    "三五环": "https://www.xiaoyuzhoufm.com/podcast/5e280fab418a84a0461faa3c",
    "代码之外 Beyond Code": "https://www.xiaoyuzhoufm.com/podcast/6194d973c14c9a0db82de1ea",
    "OnBoard!": "https://www.xiaoyuzhoufm.com/podcast/61cbaac48bb4cd867fcabe22",
    "张小珺Jùn｜商业访谈录": "https://www.xiaoyuzhoufm.com/podcast/626b46ea9cbbf0451cf5a962",
}


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_episodes(url: str) -> list[dict]:
    html = fetch_html(url)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        raise RuntimeError(f"未找到 __NEXT_DATA__：{url}")
    data = json.loads(m.group(1))
    pod = data["props"]["pageProps"]["podcast"]
    return pod.get("episodes") or []


def shorten(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def clean_summary(desc: str) -> str:
    """去掉冠名/赞助广告段，让摘要落在真实内容上。"""
    ad_marker = re.compile(
        r"冠名播出|赞助播出|感谢.{0,60}(支持|赞助)|由.{0,30}(冠名|赞助)"
        r"|恭喜本期的咖啡豆|送出|福利时间"
    )
    ad_word = re.compile(
        r"卫生巾|棉中白金|支点壳|撞色|防摔|生理期|牙膏|香氛|羊绒般|柔软触感"
    )
    paras = [p.strip() for p in (desc or "").split("\n") if p.strip()]
    pops = 0
    # 广告段：带明确广告标记（冠名/赞助/感谢…支持/送出），或短段落里堆产品词。
    # 真实内容段通常更长且带事实。保留至少 1 段，最多剔除 6 段。
    while paras and len(paras) > 1 and pops < 6:
        p = paras[0]
        if ad_marker.search(p) or (ad_word.search(p) and len(p) < 250):
            paras.pop(0)
            pops += 1
        else:
            break
    return shorten("\n".join(paras), 180)


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取小宇宙科技播客最新单集")
    parser.add_argument("--limit", type=int, default=3, help="每频道取最近 N 集（默认 3）")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写文件")
    args = parser.parse_args()

    episodes: list[dict] = []
    errors: list[str] = []

    for channel, url in CHANNELS.items():
        print(f"正在抓取：{channel} …")
        try:
            items = parse_episodes(url)
            channel_page = url.split("?")[0]
            for ep in items[: args.limit]:
                pub = (ep.get("pubDate") or "")[:10]
                episodes.append({
                    "title": ep.get("title", "未知标题"),
                    "channel": channel,
                    "date": pub,
                    "duration_min": round((ep.get("duration") or 0) / 60),
                    "play_count": ep.get("playCount") or 0,
                    "url": f"https://www.xiaoyuzhoufm.com/episode/{ep.get('eid', '')}",
                    "summary": clean_summary(ep.get("description") or ""),
                    "source": channel_page,
                })
            if not items:
                errors.append(f"{channel}：未解析到单集（{url}）")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{channel}：{e}")

    out = {"updated_at": "", "episodes": episodes}
    if args.dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    with open("episodes.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已写入 episodes.json：{len(episodes)} 条单集（{len(CHANNELS)} 个频道）")
    if errors:
        print("⚠️ 以下频道抓取失败：")
        for e in errors:
            print("  -", e)


if __name__ == "__main__":
    main()
