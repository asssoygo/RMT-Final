"""Reproducible RMT evaluation of recorded LLM answers, as of 2026-11-08.

One command: python evaluate.py
The script never rewrites benchmark.csv or responses.csv. It distinguishes verified
accuracy from unanswered/unresolved cases; no model response is fabricated.
"""
import csv, json, math, re, unicodedata
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
MODES = ('closed', 'open')
MODELS = ('GPT', 'Claude', 'Gemini', 'Grok')
LABELS = ('Correct', 'Partially Correct', 'Outdated', 'Incorrect', 'Uncertain')
UNRESOLVED = ('Needs Review', 'Reference Gap')

# Recognized alternative spellings/translations for a few nontrivial answers.
# Every rule remains visible here, never concealed in precomputed model scores.
ALIASES = {
 'FRESHQA_153':['nancy grace roman space telescope','roman space telescope'],
 'FRESHQA_227':['4','four'],
 'FRESHQA_471':['kishore mondal'],
 'FRESHQA_474':['heart of the beast'],
 'FRESHQA_479':['united states','usa','us'],
 'FRESHQA_155':['bulgaria','болгария'],
 'FRESHQA_157':['25 novels and novellas','25'],
 'FRESHQA_373':['kimi antonelli'],
 'FRESHQA_374':['alexia jayy'],
 'FRESHQA_393':['chick corea','christian mcbride','brian blade'],
 'FRESHQA_394':['seattle seahawks'],
 'FRESHQA_395':['sydney','atlanta','paris'],
 'FRESHQA_399':['aryna sabalenka','amanda anisimova'],
 'FRESHQA_403':['budapest'],
 'FRESHQA_407':['february 18','march 19'],
 'FRESHQA_410':['levi','stadium'],
 'FRESHQA_411':['no state of the union','no formal state of the union'],
 'FRESHQA_412':['kpop demon hunters'],
 'FRESHQA_413':['one battle after another'],
 'FRESHQA_415':['other worlds than these'],
 'FRESHQA_417':['veterans day'],
 'FRESHQA_420':['hannah harper'],
 'FRESHQA_463':['yes'],
 'FRESHQA_464':['no'],
 'FRESHQA_467':['26','khaby lame'],
 'FRESHQA_468':['27','brooklyn beckham'],
 'FRESHQA_469':['november 1 2026'],
 'FRESHQA_158':['hurry up tomorrow'],
 'FRESHQA_165':['narendra modi stadium'],
 'FRESHQA_166':['the life of a showgirl'],
 'FRESHQA_167':['sanae takaichi'],
 'FRESHQA_169':['luke littler'],
 'FRESHQA_173':['donald trump','дональд трамп'],
 'FRESHQA_174':['net 10'],
 'FRESHQA_425':['elon musk','илон маск'],
 'FRESHQA_426':['arsenal'],
 'FRESHQA_429':['macos 27 golden gate','macos golden gate','golden gate'],
 'FRESHQA_430':['marc marquez'],
 'FRESHQA_431':['anne carson'],
 'FRESHQA_432':["aja wilson"],
 'FRESHQA_434':['zootopia 2'],
 'FRESHQA_435':['clair obscur expedition 33'],
 'FRESHQA_438':['harry kane'],
 'FRESHQA_439':['the pitt'],
 'FRESHQA_440':['bremen'],
 'FRESHQA_441':['budapest'],
 'FRESHQA_442':['dito'],
 'FRESHQA_444':['the buffalo hunter hunter'],
 'FRESHQA_445':['new york knicks'],
 'FRESHQA_474':['f1'],
 'FRESHQA_482':['czech republic'],
 'FRESHQA_484':['canada'],
 'CUSTOM_001':['francis halzen'],
 'CUSTOM_002':['henri b kagan','kenso soai'],
 'CUSTOM_003':['navi pillay','navanethem pillay'],
 'CUSTOM_004':['spain','испания'],
 'CUSTOM_005':['norway','норвегия'],
 'CUSTOM_006':['alexander zverev'],
 'CUSTOM_007':['tadej pogacar'],
 'CUSTOM_008':['bulgaria','болгария'],
 'CUSTOM_009':['angel down','daniel kraus'],
 'CUSTOM_010':['mirra andreeva'],
 'FRESHQA_485':['new york knicks','carolina hurricanes','milwaukee brewers'],
}
# Sets whose ALL components must occur; most other alias sets mean ANY.
ALL_REQUIRED = {'FRESHQA_393','FRESHQA_395','FRESHQA_399','FRESHQA_407','FRESHQA_410','CUSTOM_002','CUSTOM_009','FRESHQA_485'}
# Historical names or numeric values demonstrably valid in earlier periods.
# This list is deliberately narrow. A mistaken number alone isn't proof of temporal staleness.
OUTDATED = {
 'FRESHQA_156':['5','five consumer vehicle models'],
 'FRESHQA_154':['20'], 'FRESHQA_155':['croatia','хорватия'],
 'FRESHQA_373':['max verstappen','lando norris'],
 'FRESHQA_158':['dawn fm'], 'FRESHQA_166':['the tortured poets department'],
 'FRESHQA_167':['shigeru ish iba','shigeru ishiba'],
 'FRESHQA_174':['net 9','net 8'],
 'FRESHQA_424':['android 15','android 14'],
 'FRESHQA_429':['macos tahoe','macos sequoia','sonoma'],
 'FRESHQA_431':['han kang','jon fosse'],
 'FRESHQA_435':['baldur s gate 3'],
 'FRESHQA_438':['ousmane dembele','rodri','lionel messi'],
 'FRESHQA_439':['shogun','succession'],
 'FRESHQA_445':['boston celtics'],
 'FRESHQA_173':['joe biden'],
 'FRESHQA_412':['the boy and the heron'],
 'FRESHQA_413':['oppenheimer'],
 'FRESHQA_430':['francesco bagnaia'],
 'FRESHQA_425':[],
}
VAGUE_HINTS = ['уточня','по итогам','смотрите свеж','актуальн','в зависимости от','usually','often','check ','зависит от','нужно провер','или последующ','или другой','от 2025','и т д','depending on','продолжаются','свежие результаты']


def load_csv(path):
 with path.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def save_csv(path,rows,columns):
 path.parent.mkdir(parents=True, exist_ok=True)
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)

def norm(text):
 s=unicodedata.normalize('NFKD',str(text or '').lower())
 s=''.join(c for c in s if not unicodedata.combining(c))
 s=s.replace('ё','е').replace('–','-').replace('—','-').replace('’',"'")
 return ' '.join(re.findall(r'[a-zа-я0-9]+',s))

def contains(text,needle):
 t,n=norm(text),norm(needle)
 return bool(n) and re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',t) is not None

def exact_answer(answer,gold):
 a,g=norm(answer),norm(gold)
 return bool(a and g and a==g)

def matched(answer,qid,gold):
 aliases=ALIASES.get(qid)
 if not aliases:
  base=re.split(r'\s*\(',gold)[0].strip().split(';')[0].strip()
  aliases=[base] if base else [gold]
  if len(norm(base).split())>11: aliases=[gold]
 if qid in ALL_REQUIRED:
  return all(contains(answer,a) for a in aliases)
 if any(contains(answer,a) for a in aliases):
  return True
 return exact_answer(answer,gold)

def is_numberish(qid,gold,answer):
 # Numeric questions: handle self-contained short dates/prices/years safely.
 if qid in {'FRESHQA_375','FRESHQA_376','FRESHQA_383','FRESHQA_460','FRESHQA_466','FRESHQA_468','FRESHQA_492','FRESHQA_160','FRESHQA_163','FRESHQA_421','FRESHQA_446','FRESHQA_400','FRESHQA_228','FRESHQA_229','FRESHQA_174','FRESHQA_424','FRESHQA_154','FRESHQA_157'}:
  nums=lambda s: re.findall(r'\d+(?:[.,]\d+)?',s.replace(',',''))
  gnums=nums(gold); anums=nums(answer)
  if gnums and anums:
   # Compare an answer's FIRST numeric target with gold's first, except macOS/.NET versions
   if qid in {'FRESHQA_174','FRESHQA_424'}:
    return 'Correct' if gnums[0]==anums[0] else None
   if gnums[0]==anums[0]:return 'Correct'
 return None

def classify(q,r,overrides):
 qid=r['question_id']; ans=r.get('answer','').strip();gold=q.get('ground_truth','').strip();verified=q.get('verification_status')=='SOURCE_CHECKED_2026_11_08' and bool(gold)
 key=(r['model'],r['mode'],qid)
 if key in overrides and verified:return overrides[key]
 if not ans or re.match(r'^\s*unknown\b',ans,re.I):return 'Uncertain','Explicit Unknown or empty response'
 if any(h in ans.lower() for h in VAGUE_HINTS) and not matched(ans,qid,gold):
  return 'Uncertain','Non-specific/hedged answer without an independently identified fact'
 if not verified:return 'Reference Gap','Reference fact lacks date-specific verification'
 if matched(ans,qid,gold):
  # If an answer states a correct candidate among competing alternatives, do not claim full certainty
  if re.search(r'\bor\b|\bили\b',ans.lower()) and len(ans)>len(gold)+25:return 'Partially Correct','Contains answer but also competing or hedged alternatives'
  return 'Correct','Supported match to verified reference (normalized or alias)'
 if is_numberish(qid,gold,ans)=='Correct':return 'Correct','Numeric value matches verified reference'
 if any(contains(ans,h) for h in OUTDATED.get(qid,[])):
  return 'Outdated','Names an identifiable earlier officeholder/version/award or past correct state'
 if qid in ALL_REQUIRED and any(contains(ans,h) for h in ALIASES.get(qid,[])):
  return 'Partially Correct','Only some required parts of multi-component answer found'
 if qid=='FRESHQA_375' and any(x in norm(ans) for x in ['more than 6 000','6400','6500']):return 'Partially Correct','Approximation, not precise confirmed count'
 if qid in {'FRESHQA_407','FRESHQA_396','FRESHQA_398','FRESHQA_417','FRESHQA_418','FRESHQA_419','FRESHQA_469'}:
  return 'Needs Review','Date or date range needs semantic/time-zone equivalence review'
 if re.match(r'^[\d$€£.\s,/%+–-]+$',ans):return 'Incorrect','Unambiguous different numeric answer from verified reference'
 if len(ans)<75 and ('или' not in ans.lower() and ' or ' not in ans.lower()):return 'Incorrect','Specific alternative claim differs from verified reference'
 return 'Needs Review','Semantic comparison requires human adjudication'

def wilson(k,n,z=1.96):
 if n==0:return ('','')
 den=1+z*z/n;center=(k/n+z*z/(2*n))/den
 half=z*math.sqrt((k/n)*(1-k/n)/n+z*z/(4*n*n))/den
 return (round(100*(center-half),2),round(100*(center+half),2))

def mcnemar_p(b,c):
 n=b+c
 if not n:return 1.0
 tail=sum(math.comb(n,i) for i in range(min(b,c)+1))/(2**n)
 return min(1.0,2*tail)

def plot_charts(summary):
 try:import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 except ImportError:
  print('Matplotlib not installed; CSV results are still saved. Install: python -m pip install matplotlib');return
 fig,ax=plt.subplots(figsize=(9,5))
 for j,mode in enumerate(MODES):
  vals=[next(r for r in summary if r['model']==m and r['mode']==mode)['verified_accuracy_percent'] for m in MODELS]
  ax.bar([i+(j-.5)*.38 for i in range(4)],vals,width=.38,label=mode)
 ax.set_xticks(range(4),MODELS);ax.set_ylim(0,100);ax.set_ylabel('Accuracy on independently verified and classified cases (%)');ax.set_title('Verified-subset accuracy; unresolved cases excluded');ax.legend();fig.tight_layout();fig.savefig(RESULTS/'accuracy_comparison.png',dpi=180);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,5));bottom=[0]*8
 for label in (*LABELS,*UNRESOLVED):
  vals=[r[label] for r in summary];ax.bar(range(8),vals,bottom=bottom,label=label)
  bottom=[b+v for b,v in zip(bottom,vals)]
 ax.set_xticks(range(8),[f'{r["model"]}\n{r["mode"]}' for r in summary]);ax.set_ylabel('Responses (n=100 per condition)');ax.set_title('Response classifications; unresolved shown separately');ax.legend(loc='upper center',bbox_to_anchor=(.5,-.15),ncol=4);fig.tight_layout();fig.savefig(RESULTS/'error_distribution.png',dpi=180,bbox_inches='tight');plt.close(fig)

def main():
 benchmark=load_csv(ROOT/'benchmark.csv');responses=load_csv(ROOT/'responses.csv')
 b={x['question_id']:x for x in benchmark}
 if len(b)!=100 or len(benchmark)!=100:raise ValueError('Expected 100 distinct benchmark IDs')
 if len(responses)!=800:raise ValueError(f'Expected 800 response records; found {len(responses)}')
 keys=[(x['model'],x['mode'],x['question_id']) for x in responses]
 if len(keys)!=len(set(keys)):raise ValueError('Duplicate model-mode-question records')
 if any(x['question_id'] not in b for x in responses):raise ValueError('Unknown question IDs')
 overrides={}
 ap=RESULTS/'adjudications.csv'
 if ap.exists():
  for x in load_csv(ap):
   if x.get('evaluation_label') in LABELS and x.get('evidence_url','').strip() and x.get('reason','').strip():
    overrides[(x['model'],x['mode'],x['question_id'])]=(x['evaluation_label'],'Human adjudication: '+x['reason'])
 annotated=[]
 for r in responses:
  label,reason=classify(b[r['question_id']],r,overrides)
  annotated.append({**r,'evaluation_label':label,'evaluation_notes':reason,'ground_truth':b[r['question_id']]['ground_truth'],'reference_status':b[r['question_id']]['verification_status']})
 RESULTS.mkdir(exist_ok=True)
 save_csv(RESULTS/'scored_responses.csv',annotated,list(annotated[0]))
 save_csv(RESULTS/'review_queue.csv',[{**r,'evidence_url':'','adjudicated_label':'','adjudication_reason':''} for r in annotated if r['evaluation_label'] in UNRESOLVED],list(annotated[0])+['evidence_url','adjudicated_label','adjudication_reason'])
 if not ap.exists():save_csv(ap,[],['model','mode','question_id','evaluation_label','evidence_url','reason'])
 by={(m,mo):[x for x in annotated if x['model']==m and x['mode']==mo] for m in MODELS for mo in MODES}
 summary=[]
 for m in MODELS:
  for mode in MODES:
   rr=by[m,mode];counts=Counter(x['evaluation_label'] for x in rr)
   assessed=sum(counts[l] for l in LABELS);correct=counts['Correct']
   verified_rows=[x for x in rr if x['reference_status']=='SOURCE_CHECKED_2026_11_08']
   verified_classified=[x for x in verified_rows if x['evaluation_label'] in LABELS]
   verified_correct=sum(x['evaluation_label']=='Correct' for x in verified_classified)
   nv=len(verified_classified);lo,hi=wilson(verified_correct,nv)
   summary.append(dict(model=m,mode=mode,total=100,minimum_correct_out_of_100=correct,maximum_possible_correct_out_of_100=correct+counts['Needs Review']+counts['Reference Gap'],unresolved_cases=counts['Needs Review']+counts['Reference Gap'],**{lab:counts[lab] for lab in (*LABELS,*UNRESOLVED)},assessed=assessed,reference_verified_questions=len(verified_rows),assessed_verified_questions=nv,verified_accuracy_percent=round(100*verified_correct/nv,2) if nv else '',verified_accuracy_ci_low=lo,verified_accuracy_ci_high=hi,confirmed_correct_out_of_100_percent=correct,full_benchmark_accuracy_percent=round(correct,2) if nv==100 else 'N/A'))
 save_csv(RESULTS/'model_results.csv',summary,list(summary[0]))
 comp=[];stats=[]
 for m in MODELS:
  close=next(x for x in summary if x['model']==m and x['mode']=='closed');ope=next(x for x in summary if x['model']==m and x['mode']=='open')
  comp.append({'model':m,'closed_verified_accuracy_percent':close['verified_accuracy_percent'],'open_verified_accuracy_percent':ope['verified_accuracy_percent'],'difference_pp_on_separate_assessed_subsets':round(ope['verified_accuracy_percent']-close['verified_accuracy_percent'],2) if close['assessed'] and ope['assessed'] else '', 'closed_confirmed_out_of_100':close['Correct'],'open_confirmed_out_of_100':ope['Correct'],'completeness_note':'Accuracy denominators differ if cases unresolved; comparison is descriptive, not a paired causal estimate.'})
  c={x['question_id']:x for x in by[m,'closed']};o={x['question_id']:x for x in by[m,'open']}
  common=[qid for qid in b if b[qid]['verification_status']=='SOURCE_CHECKED_2026_11_08' and c[qid]['evaluation_label'] in LABELS and o[qid]['evaluation_label'] in LABELS]
  cc=sum(c[qid]['evaluation_label']=='Correct' for qid in common)
  oc=sum(o[qid]['evaluation_label']=='Correct' for qid in common)
  b_only=sum(c[qid]['evaluation_label']=='Correct' and o[qid]['evaluation_label']!='Correct' for qid in common)
  c_only=sum(c[qid]['evaluation_label']!='Correct' and o[qid]['evaluation_label']=='Correct' for qid in common)
  stats.append({'model':m,'paired_fully_adjudicated_questions':len(common),'closed_correct_paired':cc,'open_correct_paired':oc,'closed_only_correct':b_only,'open_only_correct':c_only,'mcnemar_exact_p_value':round(mcnemar_p(b_only,c_only),6) if common else '', 'interpretation':'Only paired classified cases; not whole-benchmark inference if some cases unresolved.'})
 save_csv(RESULTS/'comparison.csv',comp,list(comp[0]));save_csv(RESULTS/'statistical_results.csv',stats,list(stats[0]))
 plot_charts(summary)
 print('\nRMT — SOURCE-REFERENCED RESPONSE EVALUATION')
 print('Questions:',len(benchmark),'| Recorded responses:',len(responses),'| Verified reference answers:',sum(bool(x['ground_truth']) and x['verification_status']=='SOURCE_CHECKED_2026_11_08' for x in benchmark))
 print('Model    Mode     Correct Partial Outdated Incorrect Uncertain Review RefGap AssessedVerified VerifiedAcc%')
 for r in summary:print(f"{r['model']:<8} {r['mode']:<8} {r['Correct']:>3} {r['Partially Correct']:>7} {r['Outdated']:>8} {r['Incorrect']:>9} {r['Uncertain']:>9} {r['Needs Review']:>6} {r['Reference Gap']:>6} {r['assessed_verified_questions']:>15} {str(r['verified_accuracy_percent']):>11}")
 print('VerifiedAcc% = Correct / classified VERIFIED cases; models may have DIFFERENT denominators. NOT final accuracy.')
 print('The minimum confirmed-correct counts across all 100 questions are lower bounds, not point estimates.')
 print('Full-benchmark Accuracy is N/A for rows with unresolved cases. See results/review_queue.csv')
 print('Output folder:',RESULTS)

if __name__=='__main__':main()
