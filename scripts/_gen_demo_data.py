#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从真实实验 run 生成演示数据 data.json。
独立脚本，供 demo_record.sh 在缺数据时调用，也可单独运行重新生成。

用法：python3 scripts/_gen_demo_data.py
"""
from __future__ import annotations
import json, os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(d):
    p = os.path.join(PROJ, "runs", d, "result.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def main():
    data = {}

    # HotpotQA
    r = load("hotpot_20260724_214352")
    if r:
        res = r["result"]; t, s = res["text"], res["synapse"]
        tf1 = res.get("text_f1_per_item", []); sf1 = res.get("synapse_f1_per_item", [])
        data["hotpot"] = {
            "text_input_tokens": t["llm_input_tokens"],
            "syn_input_tokens": s["llm_input_tokens"],
            "text_wire": t["wire_bytes"], "syn_wire": s["wire_bytes"],
            "llm_token_saved_pct": round((t["llm_input_tokens"]-s["llm_input_tokens"])/t["llm_input_tokens"]*100, 2),
            "wire_saved_pct": round((t["wire_bytes"]-s["wire_bytes"])/t["wire_bytes"]*100, 2),
            "text_f1": round(sum(tf1)/len(tf1), 3) if tf1 else 0,
            "syn_f1": round(sum(sf1)/len(sf1), 3) if sf1 else 0,
            "gold_recall": res.get("gold_recall"), "n_items": res.get("n_items"),
        }

    # MuSiQue
    r = load("musique_20260724_203011")
    if r:
        res = r["result"]; t, s = res["text"], res["synapse"]
        tf1 = res.get("text_f1_per_item", []); sf1 = res.get("synapse_f1_per_item", [])
        data["musique"] = {
            "llm_token_saved_pct": round((t["llm_input_tokens"]-s["llm_input_tokens"])/t["llm_input_tokens"]*100, 2),
            "text_f1": round(sum(tf1)/len(tf1), 3) if tf1 else 0,
            "syn_f1": round(sum(sf1)/len(sf1), 3) if sf1 else 0,
            "gold_recall": res.get("gold_recall"), "n_items": res.get("n_items"),
        }

    # CoQA
    r = load("coqa_20260724_211318")
    if r:
        res = r["result"]; pcs = res["per_conversation"]
        tot_t = sum(pc["text"]["llm_total_tokens"] for pc in pcs)
        tot_s = sum(pc["synapse"]["llm_total_tokens"] for pc in pcs)
        all_tf = []; all_sf = []; gaps = []
        for pc in pcs:
            all_tf += pc.get("text_f1_per_turn", [])
            all_sf += pc.get("synapse_f1_per_turn", [])
            tc = pc.get("text_cum_tokens", []); sc = pc.get("synapse_cum_tokens", [])
            if tc and sc:
                gaps.append({"turns": pc.get("turns"), "gap": tc[-1]-sc[-1]})
        data["coqa"] = {
            "llm_token_saved_pct": round((tot_t-tot_s)/tot_t*100, 2),
            "text_f1": round(sum(all_tf)/len(all_tf), 3) if all_tf else 0,
            "syn_f1": round(sum(all_sf)/len(all_sf), 3) if all_sf else 0,
            "hit_rate": res["synapse_total"]["hit_rate"],
            "memory_hits": res["synapse_total"]["memory_hits"],
            "n_convs": len(pcs), "gaps": gaps,
        }

    # signal B1 vs B3
    for key, d in [("b1", "signal_20260724_191435"), ("b3", "signal_20260724_193555")]:
        r = load(d)
        if r:
            lk = r["linked"]; neg = r["negative"]
            cb_l = lk["contraction_bytes"]; cb_n = neg["contraction_bytes"]
            # 累加三档协议计数
            tiers = {"tier_residual": 0, "tier_embedding": 0, "tier_text": 0}
            frozen = spill = fb = 0
            for tr in lk.get("synapse_trajectory", []):
                for k in tiers: tiers[k] += tr.get(k, 0)
                frozen += tr.get("frozen_snapshot_injections", 0)
                spill += tr.get("result_spills", 0)
                fb += tr.get("fallbacks", 0)
            data[key] = {
                "contraction": cb_l,
                "drop_pct": round((cb_l[0]-cb_l[-1])/cb_l[0]*100, 1),
                "hit_rate": lk.get("hit_rate") or (lk.get("improvement", {}) or {}).get("synapse_hit_rate"),
                "neg_contraction": cb_n,
                "neg_drop_pct": round((cb_n[0]-cb_n[-1])/cb_n[0]*100, 1),
                "tiers": tiers, "frozen_injections": frozen, "fallbacks": fb,
            }
    if "b1" in data:
        data["attribution_976"] = round((data["b1"]["drop_pct"]-data["b3"]["drop_pct"])/data["b1"]["drop_pct"]*100, 1)

    # m7
    r = load("m7_20260620_214354")
    if r:
        data["m7"] = {"wire_saved_pct": round(r["result"]["improvement"]["wire_bytes_saved_pct"], 2)}

    # 元信息
    real_runs = sum(
        1 for d in os.listdir(os.path.join(PROJ, "runs"))
        if os.path.isfile(os.path.join(PROJ, "runs", d, "result.json"))
    )
    data["_meta"] = {
        "real_runs": real_runs, "datasets": 3,
        "os": "openEuler 24.03-LTS-SP3",
        "model": "qwen3-235b-a22b-instruct-2507",
        "slogan": "协作即压缩 / 越用越省、越用越聪明",
    }

    out = os.path.join(PROJ, "dashboard", "data.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已生成 {out}")
    print(f"   真实实验数：{real_runs}")

if __name__ == "__main__":
    main()
