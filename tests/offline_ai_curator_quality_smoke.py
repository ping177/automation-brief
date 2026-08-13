from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_ai_curator_quality import (  # noqa: E402
    _has_attribution,
    evaluate_snapshot_response,
    load_gold_reference,
)


GOLD_PATH = PROJECT_ROOT / "tests" / "fixtures" / "ai_curator" / "phase4_20260812_gold.json"


def current_failed_response() -> dict[str, object]:
    return {
        "events": [
            {
                "event_id": "evt_001",
                "canonical_title": "C919首次执飞国际商业航线",
                "summary": "C919首次执飞国际商业航班。",
                "importance": "important",
                "evidence_article_ids": [
                    "art_8d58769d5e4f5daaaceb64a9",
                    "art_4364e7b746dd79104c316359",
                ],
                "confidence": "high",
                "uncertainties": [],
            },
            {
                "event_id": "evt_002",
                "canonical_title": "哥伦比亚7.4级强震已致超200人死亡",
                "summary": "两份报道分别给出188人和超200人的伤亡数字。",
                "importance": "must_know",
                "evidence_article_ids": [
                    "art_175572351a9c7c6d80e67c97",
                    "art_2c188a8fa9aba053befdbdb8",
                ],
                "confidence": "high",
                "uncertainties": [],
            },
            {
                "event_id": "evt_003",
                "canonical_title": "美国宣布完全控制霍尔木兹海峡，伊朗强硬回应",
                "summary": "特朗普声称美国已完全控制海峡。",
                "importance": "must_know",
                "evidence_article_ids": [
                    "art_ce092dfbeb45c4aa0d80a994",
                    "art_9ba5a9e894cb34babac3386e",
                    "art_54fc02743e09fbbb74624fb9",
                    "art_aac68036a949ecb463b8f79d",
                    "art_6a4d28c8dd9d5035c7736cf7",
                ],
                "confidence": "high",
                "uncertainties": [],
            },
            {
                "event_id": "evt_004",
                "canonical_title": "OpenAI高管离职",
                "summary": "一名长期高管宣布离职。",
                "importance": "background",
                "evidence_article_ids": [
                    "art_e7b498edd36cca954174202b",
                    "art_36ec146a508b050912e1ab2d",
                ],
                "confidence": "high",
                "uncertainties": [],
            },
            {
                "event_id": "evt_005",
                "canonical_title": "Anthropic推出文本水印技术",
                "summary": "Anthropic宣布文本水印功能。",
                "importance": "background",
                "evidence_article_ids": [
                    "art_3add5494ad956124930ece02",
                    "art_d0c4adaadc8418ea80ed64be",
                ],
                "confidence": "high",
                "uncertainties": [],
            },
        ]
    }


def passing_response() -> dict[str, object]:
    return {
        "events": [
            {
                "event_id": "evt_hormuz",
                "canonical_title": "特朗普声称美国已控制霍尔木兹海峡",
                "summary": "特朗普声称美方已控制海峡，伊朗官员则表示开放取决于伊方条件。",
                "importance": "must_know",
                "evidence_article_ids": [
                    "art_ce092dfbeb45c4aa0d80a994",
                    "art_9ba5a9e894cb34babac3386e",
                ],
                "confidence": "medium",
                "uncertainties": ["双方说法均为当事方声明，尚缺独立确认。"],
            },
            {
                "event_id": "evt_quake",
                "canonical_title": "哥伦比亚7.4级强震伤亡数字继续更新",
                "summary": "不同报道给出的死亡数字为188人和超过200人。",
                "importance": "must_know",
                "evidence_article_ids": [
                    "art_175572351a9c7c6d80e67c97",
                    "art_2c188a8fa9aba053befdbdb8",
                ],
                "confidence": "medium",
                "uncertainties": ["死亡人数仍在更新，现有来源口径不同。"],
            },
            {
                "event_id": "evt_henan",
                "canonical_title": "河南防汛应急响应提升至三级",
                "summary": "河南部分地区出现特大暴雨，防汛应急响应提升。",
                "importance": "must_know",
                "evidence_article_ids": ["art_2ffaa77ef560ebd0c82c0999"],
                "confidence": "medium",
                "uncertainties": ["后续降雨范围和强度仍取决于天气发展。"],
            },
            {
                "event_id": "evt_golan",
                "canonical_title": "据报道，多国反对哥伦比亚承认以色列对戈兰高地的主权",
                "summary": "报道援引多国声明，称其反对哥伦比亚政府的决定。",
                "importance": "important",
                "evidence_article_ids": ["art_aa8ef36ed3a0353bf728e35b"],
                "confidence": "medium",
                "uncertainties": [],
            },
            {
                "event_id": "evt_market",
                "canonical_title": "A股三大指数集体收涨",
                "summary": "超过4100只个股上涨。",
                "importance": "important",
                "evidence_article_ids": ["art_0a111c88cf170afdcfd89d06"],
                "confidence": "high",
                "uncertainties": [],
            },
            {
                "event_id": "evt_mandeb",
                "canonical_title": "也门海岸警卫队声明称一艘货船遇袭致6人死亡",
                "summary": "据报道，也门海岸警卫队表示袭击造成6人死亡。",
                "importance": "must_know",
                "evidence_article_ids": ["art_10ccfc18b3177e8825a664b5"],
                "confidence": "medium",
                "uncertainties": ["伤亡与责任归属来自当事机构声明，尚待独立确认。"],
            },
            {
                "event_id": "evt_ads",
                "canonical_title": "OpenAI宣布在ChatGPT中测试广告",
                "summary": "OpenAI表示广告测试将支持免费访问。",
                "importance": "important",
                "evidence_article_ids": ["art_d433301b0dcaebb93e8f5c81"],
                "confidence": "high",
                "uncertainties": [],
            },
            {
                "event_id": "evt_manus",
                "canonical_title": "报道称Manus将在Meta交易撤销后恢复独立",
                "summary": "据报道，相关交易已被要求撤销，具体后续安排仍待确认。",
                "importance": "important",
                "evidence_article_ids": ["art_442cf6b601dea899a8ff861b"],
                "confidence": "medium",
                "uncertainties": ["交易撤销和公司安排来自单一媒体报道。"],
            },
        ]
    }


def main() -> None:
    gold = load_gold_reference(GOLD_PATH)
    assert gold["snapshot_sha256"] == "2cbb32a286f12c26bd963ea20100463bcce053561376945f5b90bef01a6d9def"
    assert gold["reference_max_events"] == 10
    assert {event["tier"] for event in gold["events"]} == {
        "must_include_at_10",
        "strong_candidate",
    }
    assert gold["representative_omit_article_ids"]

    failed = evaluate_snapshot_response(current_failed_response(), gold)
    assert failed["must_include_missing"] == [
        "henan_flood_response",
        "golan_heights_diplomatic_change",
        "mandeb_shipping_attack",
        "china_equity_market_rally",
        "chatgpt_ads_test",
        "manus_meta_transaction_unwind",
    ]
    assert failed["background_over_priority"] == ["evt_004", "evt_005"]
    assert failed["forbidden_evidence_binding"] == {
        "hormuz_access_dispute": [
            "art_aac68036a949ecb463b8f79d",
            "art_6a4d28c8dd9d5035c7736cf7",
        ]
    }
    assert failed["attribution_required_missing"] == ["hormuz_access_dispute"]
    assert failed["uncertainty_expected_missing"] == [
        "hormuz_access_dispute",
        "colombia_earthquake",
    ]

    assert not _has_attribution("数据显示市场上涨")
    assert not _has_attribution("公司名称变更")
    assert _has_attribution("据报道，谈判仍在继续")
    assert _has_attribution("官员表示谈判仍在继续")
    assert _has_attribution("特朗普称美方已控制海峡")

    passed = evaluate_snapshot_response(passing_response(), gold)
    assert passed == {
        "must_include_missing": [],
        "background_over_priority": [],
        "forbidden_evidence_binding": {},
        "attribution_required_missing": [],
        "uncertainty_expected_missing": [],
    }
    json.dumps(passed, ensure_ascii=False, sort_keys=True)
    print("offline ai curator quality smoke passed")


if __name__ == "__main__":
    main()
