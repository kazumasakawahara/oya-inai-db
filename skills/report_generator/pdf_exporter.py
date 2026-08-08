
import os
import sys
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import mm

# Add parent directory to path to import lib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.db_new_operations import resolve_client, run_query

FONT_NAME = "Japanese"

def get_font_name():
    """Get the registered font name or fallback"""
    font_paths = [
        # Mac
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB W3.ttc",
        # Custom/Fallback
        "./skills/report_generator/fonts/IPAexGothic.ttf"
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('Japanese', path))
                return 'Japanese'
            except Exception:
                continue
    
    # Fallback
    return "Helvetica"

def draw_header(c, width, height, client_name):
    """Draw Header Section"""
    font = get_font_name()
    c.setFillColor(colors.darkred)
    c.rect(0, height - 25*mm, width, 25*mm, fill=1, stroke=0)
    
    c.setFillColor(colors.white)
    c.setFont(font, 24)
    c.drawCentredString(width/2, height - 15*mm, f"緊急時情報シート / Emergency Sheet")
    
    c.setFont(font, 12)
    c.drawCentredString(width/2, height - 22*mm, f"Target: {client_name}")

def draw_profile(c, x, y, width, height, client):
    """Draw Profile Box"""
    font = get_font_name()
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.rect(x, y - height, width, height, fill=0)
    
    c.setFillColor(colors.black)
    c.setFont(font, 14)
    c.drawString(x + 5*mm, y - 10*mm, "【基本情報】")
    
    c.setFont(font, 12)
    info = [
        f"氏名: {client.get('name', '')}",
        f"生年月日: {client.get('dob', '')}",
        f"血液型: {client.get('bloodType', '')}",
        f"ID: {client.get('displayCode', '')}"
    ]
    
    curr_y = y - 20*mm
    for line in info:
        c.drawString(x + 5*mm, curr_y, line)
        curr_y -= 8*mm

def draw_medical_alerts(c, x, y, width, height, client_identifier):
    """Draw Red Medical Alert Box"""
    font = get_font_name()
    c.setStrokeColor(colors.red)
    c.setLineWidth(2)
    c.rect(x, y - height, width, height, fill=0)
    c.setLineWidth(1)
    
    c.setFillColor(colors.red)
    c.setFont(font, 14)
    c.drawString(x + 5*mm, y - 10*mm, "【⚠️ 禁忌事項 / Contraindications】")
    
    # Fetch NgActions
    ng_actions = run_query("""
        MATCH (c:Client)-[:MUST_AVOID]->(ng:NgAction)
        WHERE (c.name = $name OR c.clientId = $name)
        RETURN ng.action, ng.riskLevel
        ORDER BY ng.riskLevel
        LIMIT 5
    """, {"name": client_identifier})
    
    c.setFillColor(colors.black)
    c.setFont(font, 12)
    curr_y = y - 20*mm
    
    if not ng_actions:
        c.drawString(x + 5*mm, curr_y, "特になし")
    
    for ng in ng_actions:
        risk = ng['ng.riskLevel']
        prefix = "🔴" if risk == "LifeThreatening" else "🟠"
        text = f"{prefix} {ng['ng.action']}"
        c.drawString(x + 5*mm, curr_y, text)
        curr_y -= 8*mm

def draw_key_persons(c, x, y, width, height, client_identifier):
    """Draw Key Persons"""
    font = get_font_name()
    c.setStrokeColor(colors.black)
    c.rect(x, y - height, width, height, fill=0)
    
    c.setFont(font, 14)
    c.drawString(x + 5*mm, y - 10*mm, "【緊急連絡先】")
    
    kps = run_query("""
        MATCH (c:Client)-[r:HAS_KEY_PERSON]->(kp:KeyPerson)
        WHERE (c.name = $name OR c.clientId = $name)
        RETURN kp.name, kp.relationship, kp.phone
        ORDER BY r.rank
        LIMIT 3
    """, {"name": client_identifier})
    
    c.setFont(font, 12)
    curr_y = y - 20*mm
    
    for kp in kps:
        line = f"{kp['kp.name']} ({kp['kp.relationship']}) : {kp['kp.phone']}"
        c.drawString(x + 5*mm, curr_y, line)
        curr_y -= 8*mm

def generate_emergency_sheet_pdf(client_identifier: str) -> str:
    """
    Generate A4 PDF Emergency Sheet
    """
    client = resolve_client(client_identifier)
    if not client:
        raise ValueError(f"Client not found: {client_identifier}")
        
    client_name = client.get('name') or client.get('displayCode')
    
    # Paths
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"EmergencySheet_{client_name}_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    # Init PDF
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    
    # Draw logic
    draw_header(c, width, height, client_name)
    
    # Left Column: Profile
    draw_profile(c, 10*mm, height - 35*mm, 90*mm, 60*mm, client)
    
    # Right Column: Key Persons
    draw_key_persons(c, 110*mm, height - 35*mm, 90*mm, 60*mm, client_name)
    
    # Center: Medical Alerts (High Priority)
    draw_medical_alerts(c, 10*mm, height - 105*mm, 190*mm, 80*mm, client_name)
    
    # Footer
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, 10*mm, f"Generated by Parent Support DB | {datetime.now().strftime('%Y-%m-%d')}")
    
    c.save()
    return filepath

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = generate_emergency_sheet_pdf(sys.argv[1])
        print(f"Generated: {path}")
    else:
        print("Usage: python pdf_exporter.py <ClientName>")
