"""Render the project report from its editable Markdown source; no research reruns."""
from pathlib import Path
import re, html, json, hashlib
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'reports/cryo-research-report.md'
OUT=ROOT/'output/pdf/cryo-research-report.pdf'
FONT=Path('/System/Library/Fonts/Supplemental')
for name,filename in [('Arial','Arial.ttf'),('Arial-Bold','Arial Bold.ttf'),('Arial-Italic','Arial Italic.ttf'),('Arial-BoldItalic','Arial Bold Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/filename)))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic',boldItalic='Arial-BoldItalic')
NAVY=HexColor('#123046');TEAL=HexColor('#087F8C');INK=HexColor('#243640');MUTED=HexColor('#586C78')
W=504
styles={
 'body':ParagraphStyle('Body',fontName='Arial',fontSize=10.2,leading=14.0,textColor=INK,spaceAfter=9),
 'title':ParagraphStyle('Title',fontName='Arial-Bold',fontSize=31,leading=35,textColor=NAVY,spaceAfter=16),
 'h1':ParagraphStyle('Heading',fontName='Arial-Bold',fontSize=21,leading=26,textColor=NAVY,spaceAfter=16,keepWithNext=True),
 'cell':ParagraphStyle('Cell',fontName='Arial',fontSize=9.3,leading=12.5,textColor=INK),
 'th':ParagraphStyle('TableHeader',fontName='Arial-Bold',fontSize=9.3,leading=12.5,textColor=white),
 'ref':ParagraphStyle('Reference',fontName='Arial',fontSize=9.1,leading=12,textColor=INK,spaceAfter=8),
 'caption':ParagraphStyle('Caption',fontName='Arial-Italic',fontSize=8.5,leading=11,textColor=MUTED,spaceAfter=9),
}

def inline(s):
    tokens=[]
    def link(m):
        tokens.append(f'<link href="{html.escape(m.group(2),quote=True)}" color="#087F8C">{html.escape(m.group(1))}</link>')
        return f'@@LINK{len(tokens)-1}@@'
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,s)
    s=html.escape(s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'<font size="8.7">\1</font>',s)
    for i,t in enumerate(tokens):s=s.replace(f'@@LINK{i}@@',t)
    return s

def table(rows):
    n=len(rows[0]);first=rows[0][0]
    if n==2:fractions=[.31,.69] if first=='Layer' else [.39,.61]
    elif first=='Model':fractions=[.64,.18,.18]
    elif first=='Stage':fractions=[.29,.23,.48]
    else:fractions=[.24,.39,.37]
    content=[[Paragraph(inline(x),styles['th' if i==0 else 'cell']) for x in row] for i,row in enumerate(rows)]
    t=Table(content,colWidths=[W*x for x in fractions],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[HexColor('#F0F5F7'),white]),
        ('LINEBELOW',(0,-1),(-1,-1),.5,HexColor('#C7D4DB'))]))
    return t

def story_from_md(text):
    story=[];sections=text.split('<!-- page -->')
    for section_number,section in enumerate(sections):
        if section_number:story.append(PageBreak())
        lines=section.strip().splitlines();i=0;refs=section.startswith('\n\n# Sources') or '# Sources and reusable' in section
        while i<len(lines):
            line=lines[i].strip()
            if not line:i+=1;continue
            if line.startswith('# '):
                story.append(Paragraph(inline(line[2:]),styles['title' if section_number==0 else 'h1']));i+=1;continue
            if line.startswith('|'):
                rows=[]
                while i<len(lines) and lines[i].strip().startswith('|'):
                    cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r':?-+:?',x) for x in cells):rows.append(cells)
                    i+=1
                story.extend([table(rows),Spacer(1,12)]);continue
            m=re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)',line)
            if m:
                from PIL import Image as PILImage
                path=SOURCE.parent/m.group(2)
                with PILImage.open(path) as im:iw,ih=im.size
                story.append(Image(str(path),width=W,height=W*ih/iw));story.append(Spacer(1,9));i+=1;continue
            para=[line];i+=1
            while i<len(lines) and lines[i].strip() and not lines[i].startswith(('# ','|','![')):
                para.append(lines[i].strip());i+=1
            story.append(Paragraph(inline(' '.join(para)),styles['ref' if refs else 'body']))
    return story,len(sections)

def furniture(canvas,doc):
    canvas.saveState();canvas.setFillColor(TEAL);canvas.rect(0,780,612,12,fill=1,stroke=0)
    canvas.setFont('Arial-Bold',8);canvas.setFillColor(MUTED)
    canvas.drawString(54,760,'CRYO  /  RESEARCH & VALIDATION')
    canvas.setFont('Arial',8);canvas.drawRightString(558,760,'6 SEPTEMBER 2026')
    canvas.setStrokeColor(HexColor('#C7D4DB'));canvas.setLineWidth(.5);canvas.line(54,40,558,40)
    canvas.setFont('Arial',8);canvas.drawString(54,26,'Private research report | Evidence, methods and next steps')
    canvas.drawRightString(558,26,str(doc.page));canvas.restoreState()

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    story,expected=story_from_md(SOURCE.read_text())
    doc=SimpleDocTemplate(str(OUT),pagesize=(612,792),rightMargin=54,leftMargin=54,topMargin=58,bottomMargin=52,
        title='Cryo research report: evidence, methods, findings and next steps',author='Cryo Research',subject='Completed computational work and proposed laboratory validation')
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    reader=PdfReader(OUT)
    result={'pages':len(reader.pages),'planned_sections':expected,'markdown_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'pdf_bytes':OUT.stat().st_size}
    print(json.dumps(result))

if __name__=='__main__':main()
