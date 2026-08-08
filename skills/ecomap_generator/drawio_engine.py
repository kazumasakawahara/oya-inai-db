"""
エコマップ draw.io XML 生成エンジン

Neo4jデータから draw.io (.drawio) 形式のエコマップを生成する。
Streamlit UI (pages/ecomap.py) から呼び出される。

使用例:
    from skills.ecomap_generator.drawio_engine import generate_drawio_xml, TEMPLATE_CONFIGS

    xml = generate_drawio_xml("山田健太", template="full_view")
    # → .drawio ファイルとして保存可能なXML文字列
"""

import math
import re
import sys
import os
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lib.db_new_operations import run_query, is_db_available


# =============================================================================
# テンプレート設定
# =============================================================================

@dataclass
class TemplateConfig:
    """テンプレート定義"""
    name: str
    description: str
    use_case: str
    categories: list  # 表示するカテゴリ名リスト


TEMPLATE_CONFIGS = {
    "full_view": TemplateConfig(
        name="全体像エコマップ",
        description="すべての関係者・機関を表示",
        use_case="包括的な情報確認、初回面談時の全体把握",
        categories=[
            "ngActions", "carePreferences", "keyPersons",
            "guardians", "certificates", "hospitals",
            "conditions", "supporters", "services",
        ],
    ),
    "support_meeting": TemplateConfig(
        name="支援会議用エコマップ",
        description="支援関係に焦点を当てたビュー",
        use_case="サービス担当者会議、モニタリング会議",
        categories=[
            "carePreferences", "keyPersons", "certificates",
            "supporters", "services",
        ],
    ),
    "emergency": TemplateConfig(
        name="緊急時体制エコマップ",
        description="禁忌事項最優先の緊急情報",
        use_case="緊急対応時、新規支援者への引き継ぎ初期",
        categories=[
            "ngActions", "carePreferences", "keyPersons",
            "guardians", "hospitals",
        ],
    ),
    "handover": TemplateConfig(
        name="引き継ぎ用エコマップ",
        description="担当者交代時の包括的情報",
        use_case="担当者変更、事業所変更時の引き継ぎ",
        categories=[
            "ngActions", "carePreferences", "keyPersons",
            "guardians", "certificates", "hospitals",
            "conditions", "supporters", "services",
        ],
    ),
}


# =============================================================================
# スタイル定義
# =============================================================================

CATEGORY_STYLES = {
    "ngActions": {
        "label": "⛔ 禁忌事項",
        "fill": "#FFCDD2",
        "stroke": "#C62828",
        "fontColor": "#B71C1C",
        "icon": "⛔",
        "ring": 1,
    },
    "carePreferences": {
        "label": "✅ 推奨ケア",
        "fill": "#C8E6C9",
        "stroke": "#2E7D32",
        "fontColor": "#1B5E20",
        "icon": "✅",
        "ring": 1,
    },
    "keyPersons": {
        "label": "👥 キーパーソン",
        "fill": "#FFF3E0",
        "stroke": "#E65100",
        "fontColor": "#BF360C",
        "icon": "📞",
        "ring": 2,
    },
    "guardians": {
        "label": "⚖️ 後見人",
        "fill": "#F3E5F5",
        "stroke": "#6A1B9A",
        "fontColor": "#4A148C",
        "icon": "⚖️",
        "ring": 2,
    },
    "hospitals": {
        "label": "🏥 医療機関",
        "fill": "#E3F2FD",
        "stroke": "#1565C0",
        "fontColor": "#0D47A1",
        "icon": "🏥",
        "ring": 2,
    },
    "certificates": {
        "label": "📄 手帳・受給者証",
        "fill": "#ECEFF1",
        "stroke": "#546E7A",
        "fontColor": "#37474F",
        "icon": "📄",
        "ring": 3,
    },
    "conditions": {
        "label": "🔍 特性・診断",
        "fill": "#FFF8E1",
        "stroke": "#F57F17",
        "fontColor": "#E65100",
        "icon": "🔍",
        "ring": 3,
    },
    "supporters": {
        "label": "🤝 支援者",
        "fill": "#E8EAF6",
        "stroke": "#3949AB",
        "fontColor": "#283593",
        "icon": "🤝",
        "ring": 3,
    },
    "services": {
        "label": "🏢 利用サービス",
        "fill": "#E0F2F1",
        "stroke": "#00695C",
        "fontColor": "#004D40",
        "icon": "🏢",
        "ring": 3,
    },
}

# レイアウト定数
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 900
CENTER_X = CANVAS_WIDTH // 2
CENTER_Y = CANVAS_HEIGHT // 2
RING_RADII = {1: 200, 2: 340, 3: 440}

CENTER_NODE_W = 140
CENTER_NODE_H = 60
ITEM_NODE_W = 180
ITEM_NODE_H = 50


# =============================================================================
# データ取得（lib.db_operations.run_query を使用）
# =============================================================================

def fetch_ecomap_data(client_name: str, template: str = "full_view") -> Dict:
    """
    Neo4jからエコマップ用データを取得する。

    Args:
        client_name: クライアント名
        template: テンプレート名

    Returns:
        エコマップデータのDict
    """
    config = TEMPLATE_CONFIGS.get(template, TEMPLATE_CONFIGS["full_view"])

    if not is_db_available():
        return _sample_data(client_name, template, config)

    data = {
        "client": {"name": client_name},
        "template": template,
        "template_config": config,
    }

    # 基本情報
    client_rows = run_query(
        "MATCH (c:Client {name: $name}) "
        "RETURN c.name AS name, c.dob AS dob, c.bloodType AS bloodType, "
        "       c.gender AS gender, c.address AS address",
        {"name": client_name},
    )
    if not client_rows:
        return _sample_data(client_name, template, config)

    data["client"] = client_rows[0]

    categories = config.categories

    if "ngActions" in categories:
        data["ngActions"] = run_query(
            "MATCH (c:Client {name: $name})-[:MUST_AVOID|PROHIBITED]->(ng:NgAction) "
            "RETURN ng.action AS action, ng.reason AS reason, ng.riskLevel AS riskLevel "
            "ORDER BY CASE ng.riskLevel "
            "  WHEN 'LifeThreatening' THEN 1 WHEN 'Panic' THEN 2 ELSE 3 END",
            {"name": client_name},
        )

    if "carePreferences" in categories:
        rows = run_query(
            "MATCH (c:Client {name: $name})-[:REQUIRES|PREFERS]->(cp:CarePreference) "
            "RETURN cp.category AS category, cp.instruction AS instruction, cp.priority AS priority "
            "ORDER BY CASE cp.priority "
            "  WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END",
            {"name": client_name},
        )
        if template == "emergency":
            rows = [r for r in rows if r.get("priority") == "High"]
        data["carePreferences"] = rows

    if "keyPersons" in categories:
        data["keyPersons"] = run_query(
            "MATCH (c:Client {name: $name})-[r:HAS_KEY_PERSON|EMERGENCY_CONTACT]->(kp:KeyPerson) "
            "RETURN kp.name AS name, kp.relationship AS relationship, "
            "       kp.phone AS phone, coalesce(r.rank, r.priority) AS rank "
            "ORDER BY coalesce(r.rank, r.priority, 99)",
            {"name": client_name},
        )

    if "guardians" in categories:
        data["guardians"] = run_query(
            "MATCH (c:Client {name: $name})-[:HAS_LEGAL_REP|HAS_GUARDIAN]->(g:Guardian) "
            "RETURN g.name AS name, g.type AS type, g.phone AS phone",
            {"name": client_name},
        )

    if "certificates" in categories:
        data["certificates"] = run_query(
            "MATCH (c:Client {name: $name})-[:HAS_CERTIFICATE|HOLDS]->(cert:Certificate) "
            "RETURN cert.type AS type, cert.grade AS grade, "
            "       toString(cert.nextRenewalDate) AS nextRenewalDate",
            {"name": client_name},
        )

    if "hospitals" in categories:
        data["hospitals"] = run_query(
            "MATCH (c:Client {name: $name})-[:TREATED_AT]->(h:Hospital) "
            "RETURN h.name AS name, h.specialty AS specialty, h.phone AS phone",
            {"name": client_name},
        )

    if "conditions" in categories:
        data["conditions"] = run_query(
            "MATCH (c:Client {name: $name})-[:HAS_CONDITION]->(cond:Condition) "
            "RETURN cond.name AS name, cond.description AS description",
            {"name": client_name},
        )

    if "supporters" in categories:
        data["supporters"] = run_query(
            "MATCH (s:Supporter)-[:LOGGED]->(:SupportLog)-[:ABOUT]->(c:Client {name: $name}) "
            "RETURN DISTINCT s.name AS name, s.role AS role, s.organization AS organization",
            {"name": client_name},
        )

    if "services" in categories:
        data["services"] = run_query(
            "MATCH (c:Client {name: $name})-[r:USES_SERVICE]->(sp:ServiceProvider) "
            "RETURN sp.name AS name, sp.serviceType AS type, r.status AS status",
            {"name": client_name},
        )

    for cat in categories:
        data.setdefault(cat, [])

    return data


def _sample_data(client_name: str, template: str, config: TemplateConfig) -> Dict:
    """Neo4j未接続時のサンプルデータ（デモ・テスト用）"""
    data = {
        "client": {"name": client_name, "dob": "1990-05-15", "bloodType": "A型"},
        "template": template,
        "template_config": config,
        "ngActions": [
            {"action": "後ろから急に声をかける", "reason": "パニック誘発", "riskLevel": "Panic"},
            {"action": "大きな音を出す", "reason": "聴覚過敏", "riskLevel": "Discomfort"},
        ],
        "carePreferences": [
            {"category": "パニック時", "instruction": "静かに見守り5分待つ", "priority": "High"},
            {"category": "コミュニケーション", "instruction": "ゆっくり短い文で話す", "priority": "Medium"},
        ],
        "keyPersons": [
            {"name": "山田花子", "relationship": "母", "phone": "090-1234-5678", "rank": 1},
            {"name": "山田一郎", "relationship": "叔父", "phone": "090-8765-4321", "rank": 2},
        ],
        "guardians": [
            {"name": "佐藤弁護士", "type": "成年後見人", "phone": "093-111-2222"},
        ],
        "certificates": [
            {"type": "療育手帳", "grade": "A", "nextRenewalDate": "2026-03-31"},
        ],
        "hospitals": [
            {"name": "〇〇クリニック", "specialty": "精神科", "phone": "093-333-4444"},
        ],
        "conditions": [
            {"name": "自閉スペクトラム症", "description": ""},
        ],
        "supporters": [],
        "services": [],
    }
    for key in list(data.keys()):
        if key not in ["client", "template", "template_config"] and key not in config.categories:
            data[key] = []
    return data


# =============================================================================
# レイアウトエンジン（放射状配置）
# =============================================================================

def _compute_layout(data: Dict):
    """放射状レイアウトを計算し、ノードとエッジのリストを返す"""
    nodes = []
    edges = []

    client = data.get("client", {})
    client_label = client.get("name", "クライアント")
    dob = client.get("dob", "")
    blood = client.get("bloodType", "")
    subtitle_parts = [str(dob)] if dob else []
    if blood:
        subtitle_parts.append(blood)
    subtitle = "  ".join(subtitle_parts)

    center_id = "center"
    nodes.append({
        "id": center_id,
        "x": CENTER_X - CENTER_NODE_W / 2,
        "y": CENTER_Y - CENTER_NODE_H / 2,
        "w": CENTER_NODE_W,
        "h": CENTER_NODE_H,
        "label": client_label,
        "subtitle": subtitle,
        "style": _center_style(),
        "category": "client",
        "is_center": True,
    })

    config = data.get("template_config")
    if config:
        active_categories = [c for c in config.categories if data.get(c)]
    else:
        active_categories = [c for c in CATEGORY_STYLES if data.get(c)]

    if not active_categories:
        return nodes, edges

    total_items = sum(len(data.get(cat, [])) for cat in active_categories)
    if total_items == 0:
        return nodes, edges

    MIN_SECTOR_DEG = 35
    total_min = MIN_SECTOR_DEG * len(active_categories)
    remaining_deg = max(0, 360 - total_min)

    sector_angles = {}
    for cat in active_categories:
        n = len(data.get(cat, []))
        proportion = n / total_items if total_items > 0 else 0
        sector_angles[cat] = MIN_SECTOR_DEG + remaining_deg * proportion

    current_angle = -90  # 上から開始
    node_counter = 0

    for cat in active_categories:
        items = data.get(cat, [])
        if not items:
            continue

        style_info = CATEGORY_STYLES.get(cat, {})
        sector_deg = sector_angles[cat]
        ring = style_info.get("ring", 3)
        radius = RING_RADII.get(ring, 440)
        n_items = len(items)

        if n_items == 1:
            angles = [current_angle + sector_deg / 2]
        else:
            padding = 5
            step = (sector_deg - 2 * padding) / max(1, n_items - 1)
            angles = [current_angle + padding + i * step for i in range(n_items)]

        for i, item in enumerate(items):
            node_counter += 1
            angle_rad = math.radians(angles[i])
            cx = CENTER_X + radius * math.cos(angle_rad)
            cy = CENTER_Y + radius * math.sin(angle_rad)

            label = _format_item_label(cat, item, style_info)
            node_id = f"n{node_counter}"

            nodes.append({
                "id": node_id,
                "x": cx - ITEM_NODE_W / 2,
                "y": cy - ITEM_NODE_H / 2,
                "w": ITEM_NODE_W,
                "h": ITEM_NODE_H,
                "label": label,
                "style": _item_style(style_info),
                "category": cat,
                "is_center": False,
            })
            edges.append({
                "source": center_id,
                "target": node_id,
                "style": _edge_style(style_info),
            })

        current_angle += sector_deg

    return nodes, edges


# =============================================================================
# ラベル生成
# =============================================================================

def _format_item_label(category: str, item: Dict, style_info: Dict) -> str:
    """カテゴリに応じたラベルを生成"""
    icon = style_info.get("icon", "")

    if category == "ngActions":
        risk = item.get("riskLevel", "")
        risk_mark = {"LifeThreatening": "🔴", "Panic": "🟠", "Discomfort": "🟡"}.get(risk, "")
        action = item.get("action", "")
        reason = item.get("reason", "")
        label = f"{risk_mark} {action}"
        if reason:
            label += f"\n({reason})"
        return label

    if category == "carePreferences":
        cat_name = item.get("category", "")
        instruction = item.get("instruction", "")
        priority = item.get("priority", "")
        p_mark = {"High": "★", "Medium": "◆", "Low": "◇"}.get(priority, "")
        return f"{p_mark} {cat_name}\n{instruction}"

    if category == "keyPersons":
        name = item.get("name", "")
        rel = item.get("relationship", "")
        phone = item.get("phone", "")
        rank = item.get("rank", "")
        rank_mark = f"[{rank}]" if rank else ""
        label = f"{icon}{rank_mark} {name}({rel})"
        if phone:
            label += f"\n{phone}"
        return label

    if category == "guardians":
        name = item.get("name", "")
        gtype = item.get("type", "後見人")
        phone = item.get("phone", "")
        label = f"{icon} {name}\n{gtype}"
        if phone:
            label += f" / {phone}"
        return label

    if category == "hospitals":
        name = item.get("name", "")
        spec = item.get("specialty", "")
        phone = item.get("phone", "")
        label = f"{icon} {name}"
        if spec:
            label += f"({spec})"
        if phone:
            label += f"\n{phone}"
        return label

    if category == "certificates":
        ctype = item.get("type", "")
        grade = item.get("grade", "")
        renewal = item.get("nextRenewalDate", "")
        label = f"{icon} {ctype}"
        if grade:
            label += f" {grade}"
        if renewal:
            label += f"\n期限: {renewal}"
        return label

    if category == "conditions":
        return f"{icon} {item.get('name', '')}"

    if category == "supporters":
        name = item.get("name", "")
        role = item.get("role", "")
        org = item.get("organization", "")
        label = f"{icon} {name}"
        details = [x for x in [role, org] if x]
        if details:
            label += f"\n{' / '.join(details)}"
        return label

    if category == "services":
        name = item.get("name", "")
        stype = item.get("type", "")
        status = item.get("status", "")
        label = f"{icon} {name}"
        if stype:
            label += f"({stype})"
        if status:
            label += f"\n{status}"
        return label

    return str(item)


# =============================================================================
# スタイル生成
# =============================================================================

def _center_style() -> str:
    return (
        "rounded=1;whiteSpace=wrap;html=1;"
        "fillColor=#E1F5FE;strokeColor=#01579B;strokeWidth=3;"
        "fontColor=#01579B;fontSize=16;fontStyle=1;"
        "shadow=1;arcSize=20;"
    )

def _item_style(style_info: Dict) -> str:
    fill = style_info.get("fill", "#FFFFFF")
    stroke = style_info.get("stroke", "#333333")
    font_color = style_info.get("fontColor", "#333333")
    return (
        f"rounded=1;whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=2;"
        f"fontColor={font_color};fontSize=11;"
        f"arcSize=15;"
    )

def _edge_style(style_info: Dict) -> str:
    stroke = style_info.get("stroke", "#999999")
    return (
        f"edgeStyle=orthogonalEdgeStyle;curved=1;"
        f"strokeColor={stroke};strokeWidth=1.5;"
        f"exitX=0.5;exitY=0.5;exitDx=0;exitDy=0;"
        f"entryX=0.5;entryY=0.5;entryDx=0;entryDy=0;"
        f"endArrow=none;startArrow=none;"
    )

def _legend_style(fill: str, stroke: str) -> str:
    return (
        f"rounded=1;whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=1;"
        f"fontSize=10;fontColor=#333333;align=left;spacingLeft=5;"
    )


# =============================================================================
# draw.io XML 生成
# =============================================================================

def _build_xml(nodes: list, edges: list, data: Dict) -> str:
    """ノード・エッジ情報から draw.io XML 文字列を生成する"""
    template = data.get("template", "full_view")
    config = data.get("template_config")
    template_name = config.name if config else template
    client_name = data.get("client", {}).get("name", "")
    today = date.today().isoformat()

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<mxfile host="app.diagrams.net" modified="{today}">')
    lines.append(f'  <diagram name="{_esc(client_name)} - {_esc(template_name)}">')
    lines.append(
        '    <mxGraphModel dx="1200" dy="900" grid="1" gridSize="10"'
        ' guides="1" tooltips="1" connect="1" arrows="1"'
        ' fold="1" page="1" pageScale="1"'
        f' pageWidth="{CANVAS_WIDTH}" pageHeight="{CANVAS_HEIGHT}"'
        ' math="0" shadow="0">'
    )
    lines.append('      <root>')
    lines.append('        <mxCell id="0"/>')
    lines.append('        <mxCell id="1" parent="0"/>')

    cell_id = 10

    # タイトル
    title_text = f"{client_name} エコマップ（{template_name}）"
    lines.append(
        f'        <mxCell id="{cell_id}" value="{_esc(title_text)}"'
        f' style="text;html=1;fontSize=18;fontStyle=1;fontColor=#333333;align=center;"'
        f' vertex="1" parent="1">'
        f'<mxGeometry x="10" y="10" width="{CANVAS_WIDTH - 20}" height="30" as="geometry"/>'
        f'</mxCell>'
    )
    cell_id += 1

    # 日付
    lines.append(
        f'        <mxCell id="{cell_id}" value="作成日: {today}"'
        f' style="text;html=1;fontSize=10;fontColor=#999999;align=right;"'
        f' vertex="1" parent="1">'
        f'<mxGeometry x="{CANVAS_WIDTH - 210}" y="40" width="200" height="20" as="geometry"/>'
        f'</mxCell>'
    )
    cell_id += 1

    id_map = {}

    for node in nodes:
        id_map[node["id"]] = str(cell_id)

        if node.get("is_center"):
            # 中心ノード: HTML書式付きラベル
            # draw.io html=1 では value 属性に HTML を格納する。
            # HTML タグ自体を XML 属性値としてエスケープする必要がある。
            subtitle = node.get("subtitle", "")
            # 1) テキスト部分だけ HTML-safe に（&, <, >, " をエスケープ）
            name_safe = _esc(node["label"])
            if subtitle:
                sub_safe = _esc(subtitle)
                html = (
                    f'<b style="font-size:16px">{name_safe}</b>'
                    f'<br/><span style="font-size:10px">{sub_safe}</span>'
                )
            else:
                html = f'<b>{name_safe}</b>'
            # 2) HTML 全体を XML 属性値としてエスケープ
            label = _esc_attr(html)
        else:
            # 通常ノード: テキスト→HTMLエスケープ→改行を<br/>に→XML属性エスケープ
            # ステップ1: テキスト中の & < > " をエスケープ
            text_safe = _esc(node["label"])
            # ステップ2: 改行を HTML <br/> に変換
            html = text_safe.replace("\n", "<br/>")
            # ステップ3: HTML 全体を XML 属性値としてエスケープ
            label = _esc_attr(html)

        # style もエスケープ（通常は安全な値だが念のため）
        style_safe = _esc_attr(node["style"])

        lines.append(
            f'        <mxCell id="{cell_id}" value="{label}"'
            f' style="{style_safe}"'
            f' vertex="1" parent="1">'
            f'<mxGeometry x="{node["x"]:.0f}" y="{node["y"]:.0f}"'
            f' width="{node["w"]:.0f}" height="{node["h"]:.0f}" as="geometry"/>'
            f'</mxCell>'
        )
        cell_id += 1

    for edge in edges:
        src = id_map.get(edge["source"], "")
        tgt = id_map.get(edge["target"], "")
        if src and tgt:
            edge_style_safe = _esc_attr(edge["style"])
            lines.append(
                f'        <mxCell id="{cell_id}" value=""'
                f' style="{edge_style_safe}"'
                f' edge="1" parent="1" source="{src}" target="{tgt}">'
                f'<mxGeometry relative="1" as="geometry"/>'
                f'</mxCell>'
            )
            cell_id += 1

    cell_id = _add_legend(lines, cell_id, data)

    lines.append('      </root>')
    lines.append('    </mxGraphModel>')
    lines.append('  </diagram>')
    lines.append('</mxfile>')

    return "\n".join(lines)


def _add_legend(lines: list, cell_id: int, data: Dict) -> int:
    """凡例を追加"""
    config = data.get("template_config")
    if config:
        active = [c for c in config.categories if data.get(c)]
    else:
        active = [c for c in CATEGORY_STYLES if data.get(c)]

    if not active:
        return cell_id

    legend_x = 10
    legend_y = CANVAS_HEIGHT - 30 * len(active) - 40
    legend_w = 160

    lines.append(
        f'        <mxCell id="{cell_id}" value="【凡例】"'
        f' style="text;html=1;fontSize=11;fontStyle=1;fontColor=#666666;"'
        f' vertex="1" parent="1">'
        f'<mxGeometry x="{legend_x}" y="{legend_y}" width="{legend_w}" height="25" as="geometry"/>'
        f'</mxCell>'
    )
    cell_id += 1
    legend_y += 28

    for cat in active:
        info = CATEGORY_STYLES.get(cat, {})
        label = info.get("label", cat)
        fill = info.get("fill", "#FFF")
        stroke = info.get("stroke", "#999")
        style = _legend_style(fill, stroke)

        lines.append(
            f'        <mxCell id="{cell_id}" value="{_esc_attr(label)}"'
            f' style="{_esc_attr(style)}"'
            f' vertex="1" parent="1">'
            f'<mxGeometry x="{legend_x}" y="{legend_y}" width="{legend_w}" height="24" as="geometry"/>'
            f'</mxCell>'
        )
        cell_id += 1
        legend_y += 28

    return cell_id


def _strip_invalid_xml_chars(text: str) -> str:
    """XML 1.0 で許可されていない文字を除去する。

    XML 1.0 仕様で許可されている文字:
    #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    """
    return re.sub(
        r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]",
        "",
        str(text),
    )


def _esc(text: str) -> str:
    """XML用エスケープ（無効文字の除去を含む）"""
    if not text:
        return ""
    s = _strip_invalid_xml_chars(str(text))
    return (
        s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _esc_attr(text: str) -> str:
    """XML属性値としてエスケープ済みの文字列を返す。

    draw.io の html=1 ノードでは value 属性に HTML を含めるが、
    XML 属性値として正しくエスケープされている必要がある。
    この関数は _esc() と同一だが、意図を明確にするために分離。
    """
    return _esc(text)


# =============================================================================
# 公開 API
# =============================================================================

def generate_drawio_xml(client_name: str, template: str = "full_view") -> str:
    """
    クライアント名から draw.io XML を生成する。

    Args:
        client_name: クライアント名
        template: テンプレート名 (full_view, support_meeting, emergency, handover)

    Returns:
        draw.io XML 文字列（.drawio ファイルに保存可能）

    Raises:
        ValueError: 生成されたXMLが不正な場合
    """
    data = fetch_ecomap_data(client_name, template)
    nodes, edges = _compute_layout(data)
    xml = _build_xml(nodes, edges, data)

    # XML 妥当性を検証（draw.io で開けないファイルの生成を防止）
    try:
        ET.fromstring(xml)
    except ET.ParseError as e:
        import logging
        logging.error("エコマップ XML 検証エラー: %s", e)
        raise ValueError(f"生成されたエコマップ XML が不正です: {e}") from e

    return xml


def generate_drawio_bytes(client_name: str, template: str = "full_view") -> bytes:
    """
    Streamlitのダウンロードボタン用にbytesを返す。

    Returns:
        UTF-8エンコードされた .drawio ファイルの内容
    """
    xml = generate_drawio_xml(client_name, template)
    return xml.encode("utf-8")
