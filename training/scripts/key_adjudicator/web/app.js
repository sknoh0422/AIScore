// 조표 판정 UI — mismatches.json(항목 서브 인덱스)만 읽어 한 곡씩 표시.
let items = [], decisions = {}, idx = 0;

const NM = {0:'C',1:'G',2:'D',3:'A',4:'E',5:'B',6:'F#',7:'C#',
            '-1':'F','-2':'Bb','-3':'Eb','-4':'Ab','-5':'Db','-6':'Gb','-7':'Cb'};
const keyName = f => (NM[f] || '?') + '장조';
const sign = n => (n >= 0 ? '+' : '') + n;

async function boot() {
  items = (await (await fetch('/mismatches.json')).json()).items;
  decisions = await (await fetch('/decisions.json')).json();
  idx = firstUnjudged();
  render();
  document.getElementById('prev').onclick = () => { idx = Math.max(0, idx - 1); render(); };
  document.getElementById('next').onclick = () => { idx = Math.min(items.length - 1, idx + 1); render(); };
  document.getElementById('jump').onclick = () => { idx = firstUnjudged(); render(); };
  document.addEventListener('keydown', e => {
    if (e.key === '1') choose('homr');
    else if (e.key === '2') choose('gt');
    else if (e.key === 's' || e.key === 'S') choose(null);
    else if (e.key === 'ArrowLeft') document.getElementById('prev').click();
    else if (e.key === 'ArrowRight') document.getElementById('next').click();
  });
}

const firstUnjudged = () => {
  const i = items.findIndex(it => !decisions[it.hymn]);
  return i < 0 ? 0 : i;
};
const judgedCount = () => items.filter(it => decisions[it.hymn]).length;

async function save(hymn, verdict, correct) {
  await fetch('/save', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hymn, verdict, correct_fifths: correct }),
  });
}

async function choose(verdict) {
  const it = items[idx];
  const correct = verdict === 'homr' ? it.homr_fifths : verdict === 'gt' ? it.gt_fifths : null;
  await save(it.hymn, verdict, correct);
  if (verdict === null) delete decisions[it.hymn];
  else decisions[it.hymn] = { verdict, correct_fifths: correct };
  advance();
}

// ③ 둘 다 아니면 실제 조를 직접 지정 (미판정 케이스용)
async function chooseOther() {
  const it = items[idx];
  const f = parseInt(document.getElementById('okey').value, 10);
  await save(it.hymn, 'other', f);
  decisions[it.hymn] = { verdict: 'other', correct_fifths: f };
  advance();
}

function advance() {
  const n = items.findIndex((x, i) => i > idx && !decisions[x.hymn]);
  idx = n < 0 ? Math.min(items.length - 1, idx + 1) : n;
  render();
}
window.choose = choose;
window.chooseOther = chooseOther;

function render() {
  const it = items[idx];
  const dec = decisions[it.hymn];
  const f1 = it.base_f1 == null ? '-' : it.base_f1.toFixed(2);
  const img = `/img/${it.img}`;
  document.getElementById('prog').textContent = `(${judgedCount()}/${items.length} 판정)`;
  document.getElementById('pos').textContent = `${idx + 1} / ${items.length}`;
  document.getElementById('card').innerHTML = `
    <div class="meta">
      <b>새찬송가 ${it.hymn}장</b> — ${it.title}
      <span class="f1">현재 F1(F1 score) ${f1} · 오라클 최적 shift ${sign(it.shift)}반음</span>
    </div>
    <div class="hint">악보 상단 왼쪽(조표 위치)을 확대해 보여줍니다. 실제 인쇄된 조와 일치하는 쪽을 클릭하세요. (단축키 1 / 2 / s)</div>
    <div class="zoom" style="background-image:url('${img}')"></div>
    <div class="choices">
      <button class="opt ${dec && dec.verdict === 'homr' ? 'sel' : ''}" onclick="choose('homr')">
        ① homr가 읽은 조<big>${it.homr_key}</big><small>(fifths ${sign(it.homr_fifths)})</small></button>
      <button class="opt ${dec && dec.verdict === 'gt' ? 'sel' : ''}" onclick="choose('gt')">
        ② 정답지(GT) 조<big>${it.gt_key}</big><small>(fifths ${sign(it.gt_fifths)})</small></button>
      <button class="skip" onclick="choose(null)">건너뜀<br><small>(s)</small></button>
    </div>
    <div class="other">③ 둘 다 아니면 실제 조 직접 지정:
      <select id="okey">${[5,4,3,2,1,0,-1,-2,-3,-4,-5,-6,-7].map(f =>
        `<option value="${f}">${keyName(f)} (fifths ${sign(f)})</option>`).join('')}</select>
      <button onclick="chooseOther()">이 조로 저장</button>
    </div>
    <div class="status ${dec ? 'done' : ''}">${dec
      ? `✓ 판정됨: ${dec.verdict === 'homr' ? 'homr가 맞음' : dec.verdict === 'gt' ? '정답지(GT)가 맞음' : '직접 지정'} → ${keyName(dec.correct_fifths)}`
      : '미판정'}</div>
    <div class="full-label">전체 악보 — 새찬송가 ${it.hymn}장 (${it.title})</div>
    <img class="full" src="${img}" alt="새찬송가 ${it.hymn}장 악보">
  `;
}

boot();
