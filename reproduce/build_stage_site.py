"""Publish an independent progression experiment; never modify the original site."""
from pathlib import Path
import bisect,gzip,hashlib,json,math,shutil,zipfile
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'publish'/'bms-98-table'
SITE=ROOT/'publish'/'bms-score-stages'
BASE='https://sehun-joo.github.io/bms-score-stages/'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def stage_groups(rows):
    values=[r['difficulty'] for r in rows]
    # Fixed ability increments through the main distribution. Above its 90th
    # percentile, smoothly widen steps rather than making a long sparse ladder.
    tail=values[int(.9*(len(values)-1))]
    start=math.floor(values[0]/.155)*.155
    edges=[start]; nominal=start
    while nominal<=values[-1]:
        width=.155*(1+.6*max(0,nominal-tail))
        nominal+=width
        # Snap within 20% of a step to the largest adjacent-score gap. Only
        # adjust for a meaningful gap; never split identical score estimates.
        lo,hi=nominal-.2*width,nominal+.2*width
        gaps=[(b-a,(a+b)/2) for a,b in zip(values,values[1:]) if lo<=(a+b)/2<=hi and b-a>=.01]
        edge=max(gaps,key=lambda g:(g[0],-abs(g[1]-nominal)))[1] if gaps else nominal
        edges.append(round(edge,8))
    if edges[-1]<=values[-1]:edges.append(round(values[-1]+.155,8))
    groups=[]
    for lo,hi in zip(edges,edges[1:]):
        group=rows[bisect.bisect_left(values,lo):bisect.bisect_left(values,hi)]
        if group:groups.append((lo,hi,group))
    return groups,tail

SITE.mkdir(exist_ok=True)
targets=read(SOURCE/'targets.json')
for slug,t in targets.items():
    path=t['path'];dest=SITE/path;dest.mkdir(exist_ok=True)
    rows=read(SOURCE/path/'rankings.json')
    for r in rows:
        if slug=='98':r.update(difficulty=r['difficulty98'],achieved=r['achieved98'])
    entries={r['md5']:r for r in read(SOURCE/path/'data.json')}
    groups,tail=stage_groups(rows);folders=[];data=[];native=[]
    for i,(lo,hi,group) in enumerate(groups,1):
        key=f'{i:03}';label=f'{key} | {lo:.3f}–{hi:.3f}'
        folders.append(dict(id=key,label=label,lower_inclusive=lo,upper_exclusive=hi,count=len(group),provisional=sum(r['status']=='provisional' for r in group)))
        songs=[]
        for r in group:
            r.update(folder=key,folder_range=label)
            e=dict(entries[r['md5']],level=label);data.append(e)
            songs.append({k:e[k] for k in ['md5','sha256','title','artist'] if k in e})
        native.append(dict(name=f'{t["code"]} Stage {label} ({len(group)})',songs=songs))
    header=dict(name=f'Insane {t["label"]} — progression stages',symbol=t['code']+'S ',data_url='data.json',level_order=[f['label'] for f in folders])
    for filename,value in [('header.json',header),('data.json',data),('rankings.json',rows),('folders.json',folders)]:dump(dest/filename,value)
    t.update(folders=folders,rows=rows,base_band_width=.155,tail_start=tail)
    with gzip.open(dest/t['native'],'wt',encoding='utf-8') as f:json.dump(dict(name=header['name'],url=BASE+path,tag=t['code']+'S',folder=native,course=[]),f,ensure_ascii=False)
    shutil.copy2(SOURCE/path/t['validation'],dest/t['validation'])
    print(slug,len(folders),'stages; counts', [f['count'] for f in folders],flush=True)

# Reuse the proven UI, with its embedded data and copy replaced for this site.
payload=json.dumps(targets,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
for slug,t in targets.items():
    page=(SOURCE/t['path']/'index.html').read_text(encoding='utf-8')
    start=page.index('const targets=');end=page.index(', defaultTarget=',start)
    page=page[:start]+'const targets='+payload+page[end:]
    page=page.replace('https://sehun-joo.github.io/bms-98-table/',BASE).replace('https://github.com/Sehun-Joo/bms-98-table','https://github.com/Sehun-Joo/bms-score-stages')
    page=page.replace('Pick a score goal. Find your next chart.','Build your next difficulty stage.').replace('range folders','difficulty stages')
    page=page.replace('Folders group nearby difficulty values toward an average of 15 charts; they are not forced to equal size.', 'Stages follow approximately equal ability steps, with boundaries nudged toward nearby gaps. The sparse upper tail uses gradually wider steps. There is no chart-count target and no A/B subdivision.')
    page=page.replace('The original root URL still imports the 98% table;', 'This site’s root URL imports its 98% stages;')
    page=page.replace('<div class="eyebrow">','<p><a href="https://sehun-joo.github.io/bms-98-table/">Original compact-folder tables ↗</a> · You are viewing the separate progression edition.</p><div class="eyebrow">',1)
    page=page.replace('Folder ${f.id}', 'Stage ${f.id}')
    (SITE/t['path']/'index.html').write_text(page,encoding='utf-8')

dump(SITE/'targets.json',{k:{a:b for a,b in t.items() if a not in ['rows','folders']} for k,t in targets.items()})
notes='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Progression stages: method</title><style>body{font:17px/1.6 system-ui;max-width:900px;margin:40px auto;padding:0 22px;background:#10151e;color:#e7ebf2}a{color:#87c5ff}</style><a href="index.html">← Progression tables</a><h1>Practice stages, without a song quota</h1><p>This is a separate edition of the <a href="https://sehun-joo.github.io/bms-98-table/">original compact-folder tables</a>. Its ratings and chart order are identical. Only folder boundaries and names change. Each goal contains all 1,035 charts. Stage numbers are relative to that goal, not comparable across AAA, MAX− and 98%.</p><p>The main range uses steps of 0.155 on the fitted player-ability scale. A boundary can move by up to 20% of its nominal step toward the largest adjacent-chart gap (at least 0.01 ability units) in that window. This favors grouping nearby ratings without allowing arbitrary difficulty jumps. Identical ratings always stay together; any finite grouping can still separate some similar charts.</p><p>Above each goal’s 90th percentile of chart difficulty, nominal step width grows smoothly as 0.155 × [1 + 0.6 × (lower boundary − tail start)]. This makes the sparse upper range coarser without forcing a chart quota or combining all outliers into one enormous range. Empty ranges are omitted; isolated extremes can still produce small stages. Bounds are inclusive below and exclusive above; displayed range bounds are rounded to three decimals.</p><p>These are deliberate practice-design settings, not a learned human training curve. Equal ability increments do not imply equal practice time. Weak-evidence upper-tail estimates may be extrapolated, and one player’s personal ordering can differ. The table does not enforce a completion percentage or remove provisional charts.</p><p>AAA = 8/9 EX; MAX− = 17/18 EX; 98% = 98/100 EX. Rankings use the same player-adjusted target models and held-out-player validation as the original site. Practice volume and age of personal bests remain uncorrected. See the <a href="https://sehun-joo.github.io/bms-98-table/score-targets.html">original model methods and validation</a>.</p><p><a href="insane-score-stages.zip">Download the complete progression edition</a>. Each top link opens its own importable table page. Native .bmt downloads are also available there.</p></html>'''
(SITE/'score-targets.html').write_text(notes,encoding='utf-8')
(SITE/'README.md').write_text('''# Insane BMS progression stages

[Open progression tables](https://sehun-joo.github.io/bms-score-stages/)

Separate AAA, MAX− and 98% tables with approximately equal ability steps, gap-adjusted boundaries, and gradually wider upper-tail steps. No song-count target or A/B subdivisions. All 1,035 charts and fitted difficulty orders are preserved.

The original compact-folder site remains at https://sehun-joo.github.io/bms-98-table/ with unchanged folders. See score-targets.html for the exact algorithm and limitations. Stage sizes vary intentionally. This is a practice-design heuristic, not a validated human learning curve.

Import URLs:
- https://sehun-joo.github.io/bms-score-stages/aaa/
- https://sehun-joo.github.io/bms-score-stages/max-minus/
- https://sehun-joo.github.io/bms-score-stages/

The reproduce folder includes the stage builder; it expects the original published table files in its documented workspace layout. Original score-model reproduction scripts are in the original repository. Source data: https://github.com/zkldi/lr2ir-dataset . No song files included; original chart identifiers and links retained.
''',encoding='utf-8')
(SITE/'.nojekyll').write_text('')
(SITE/'.gitattributes').write_text('* -text\n')
(SITE/'reproduce').mkdir(exist_ok=True)
shutil.copy2(__file__,SITE/'reproduce'/'build_stage_site.py')
files=[p for p in SITE.rglob('*') if p.is_file() and '.git' not in p.parts and p.suffix!='.zip' and p.name!='checksums.json']
dump(SITE/'checksums.json',{p.relative_to(SITE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
with zipfile.ZipFile(SITE/'insane-score-stages.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[SITE/'checksums.json']:z.write(p,Path('insane-score-stages')/p.relative_to(SITE))
shutil.copy2(SITE/'insane-score-stages.zip',ROOT.parent/'outputs'/'insane-score-stages.zip')
