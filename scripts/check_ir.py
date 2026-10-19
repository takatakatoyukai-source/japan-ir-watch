import json, re, html, urllib.request, datetime, pathlib, hashlib
from zoneinfo import ZoneInfo
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).resolve().parents[1]
JST=ZoneInfo('Asia/Tokyo')
NOW=datetime.datetime.now(JST)
CODES={'6768':'タムラ製作所','6315':'TOWA'}
KEYWORDS=('決算','業績','修正','配当','自己株式','自己株','公開買付','TOB','受注','子会社','増資','第三者割当','特別損失','上方','下方','合併','提携','新製品','半導体')
class Parser(HTMLParser):
 def __init__(self): super().__init__();self.in_row=False;self.in_cell=False;self.cell=[];self.cells=[];self.rows=[];self.href=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='tr': self.in_row=True;self.cells=[]
  if self.in_row and tag=='td':self.in_cell=True;self.cell=[];self.href=None
  if self.in_cell and tag=='a' and a.get('href'):self.href=a['href']
 def handle_data(self,data):
  if self.in_cell:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag=='td' and self.in_cell:self.cells.append((' '.join(''.join(self.cell).split()),self.href));self.in_cell=False
  if tag=='tr' and self.in_row:
   if self.cells:self.rows.append(self.cells)
   self.in_row=False

def get_day(day):
 out=[]
 for page in range(1,21):
  url=f'https://www.release.tdnet.info/inbs/I_list_{page:03d}_{day:%Y%m%d}.html'
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; PersonalIRWatch/1.0)'})
   with urllib.request.urlopen(req,timeout=18) as r: raw=r.read()
   p=Parser();p.feed(raw.decode('utf-8','replace'))
  except Exception as e:
   if page==1:raise RuntimeError(f'公式TDnetを取得できません: {url}: {e}')
   break
  if not p.rows:break
  for cells in p.rows:
   txt=' '.join(x[0] for x in cells)
   matched=[c for c in CODES if re.search(r'(?<!\d)'+c+r'(?:0)?(?!\d)',txt)]
   if not matched:continue
   title_link=next(((t,h) for t,h in cells if h and ('.pdf' in h.lower() or 'disclosure' in h.lower())),None)
   title=(title_link[0] if title_link else max((t for t,h in cells),key=len,default=''))
   link=(title_link[1] if title_link else url)
   if link.startswith('/') :link='https://www.release.tdnet.info'+link
   elif not link.startswith('http'):link='https://www.release.tdnet.info/inbs/'+link
   t=re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b',txt)
   for code in matched:
    uid=hashlib.sha256(f'{day}:{code}:{title}:{link}'.encode()).hexdigest()[:18]
    out.append(dict(id=uid,code=code,name=CODES[code],date=day.isoformat(),time=t.group(0) if t else '時刻未確認',title=title,url=link,important=any(k in title for k in KEYWORDS),source='TDnet'))
  if len(p.rows)<80:break
 return out

path=ROOT/'data'/'ir.json'
try: old=json.loads(path.read_text(encoding='utf-8'))
except (OSError,ValueError):old={'items':[]}
all_items={x['id']:x for x in old.get('items',[]) if 'id' in x}
for day in [NOW.date()-datetime.timedelta(days=1),NOW.date()]:
 for item in get_day(day):all_items[item['id']]=item
items=sorted(all_items.values(),key=lambda x:(x['date'],x['time']),reverse=True)[:300]
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps({'updated_at':NOW.isoformat(timespec='seconds'),'source':'TDnet','items':items},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Total',len(items),'recent important',sum(x['important'] for x in items))
