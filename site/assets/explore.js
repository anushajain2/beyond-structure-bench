// Evidence explorer: one material x one property (x one thermal comparison), read from data/evidence.json.
(async function () {
  const root = document.getElementById('explorer-out');
  let ev;
  try {
    ev = await (await fetch('data/evidence.json')).json();
  } catch (e) {
    root.innerHTML = '<p class="empty">The evidence file could not be loaded. Try reloading the page.</p>';
    return;
  }
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const PROPS = {
    lattice: 'Lattice constant', bulk_modulus: 'Bulk modulus', thermal_expansion: 'Thermal expansion',
  };
  const STEP = { lattice: 'lattice', bulk_modulus: 'elastic', thermal_expansion: 'thermal_qha' };
  const CSV = { lattice: 'lattice.csv', bulk_modulus: 'bulk_modulus.csv', thermal_expansion: 'thermal_expansion.csv' };
  const ROUTE = { 'mace-mpa-0': 'CuspAI JAX export, run through kUPS', 'orb-v3': 'CuspAI JAX export, run through kUPS',
    'mattersim-5m-native': "Microsoft's official package (its kUPS export is broken)" };
  const TAG = 'v' + ev.version;
  const blob = (p) => `${ev.repo}/blob/${TAG}/${p}`;
  const mats = Object.fromEntries(ev.materials.map((m) => [m.id, m]));

  const SUB = '₀₁₂₃₄₅₆₇₈₉';
  const uni = (f) => String(f).replace(/\d/g, (d) => SUB[d]);           // for <option> text
  const sub = (f) => esc(f).replace(/(\d+)/g, '<sub>$1</sub>');         // for HTML
  // controls
  const sel = $('material');
  const groups = {};
  ev.materials.forEach((m) => (groups[m.class_label] ||= []).push(m));
  sel.innerHTML = Object.entries(groups).map(([g, ms]) =>
    `<optgroup label="${esc(g)}">${ms.map((m) => `<option value="${esc(m.id)}">${esc(label(m))}</option>`).join('')}</optgroup>`).join('');

  function label(m) { return `${uni(m.formula)} (${m.phase})`; }
  const fmt = (v, d = 2) => (v == null || Number.isNaN(v) ? '–' : Number(v).toFixed(d));
  const pct = (v, d = 1) => (v == null ? '–' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)} %`);

  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    return { m: mats[h.get('m')] ? h.get('m') : 'Ta', p: PROPS[h.get('p')] ? h.get('p') : 'thermal_expansion',
      c: h.get('c') === 'window' ? 'window' : '300K' };
  }
  let st = readHash();
  function write() {
    const h = `m=${encodeURIComponent(st.m)}&p=${st.p}` + (st.p === 'thermal_expansion' ? `&c=${st.c}` : '');
    history.replaceState(null, '', '#' + h);
  }
  function sync() {
    sel.value = st.m;
    document.querySelector(`input[name=prop][value="${st.p}"]`).checked = true;
    document.querySelector(`input[name=cmp][value="${st.c}"]`).checked = true;
    document.querySelectorAll('input[name=cmp]').forEach((i) => (i.disabled = st.p !== 'thermal_expansion'));
    $('cmp-hint').textContent = st.p === 'thermal_expansion' ? '' : 'Only for thermal expansion';
  }
  sel.addEventListener('change', () => { st.m = sel.value; go(); });
  document.querySelectorAll('input[name=prop]').forEach((i) => i.addEventListener('change', () => { st.p = i.value; go(); }));
  document.querySelectorAll('input[name=cmp]').forEach((i) => i.addEventListener('change', () => { st.c = i.value; go(); }));
  document.querySelectorAll('[data-example]').forEach((b) => b.addEventListener('click', () => {
    const [m, p, c] = b.dataset.example.split('/'); st = { m, p, c: c || '300K' }; go();
    root.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
  window.addEventListener('hashchange', () => { st = readHash(); go(false); });

  // one model's result -> {status, cls, reason, err, errDft, rows}
  function judge(prop, r, cmp, model, mat) {
    if (!r || r.stale) {
      if (prop === 'thermal_expansion' && model === 'orb-v3') {
        const s = ev.study[`orb-v3|${mat}`];
        return { status: 'Not computed in this release', cls: 'none',
          reason: "Orb v3's benchmark-wide thermal expansion is not part of this release." +
            (s ? ` Its six-case-study value is shown below: ${pct(100 * (s.alpha300_qha / s.exp_alpha_V - 1), 0)} at 300 K.`
               : ' Orb appears only in the six-case study (Si, GaAs, InP, Cu, Ta, HfO₂).') };
      }
      return { status: 'Not computed in this release', cls: 'none',
        reason: r ? 'This result was computed with older code or settings and is not used.'
                  : 'No result for this model and material in v' + ev.version + '.' };
    }
    const th = ev.thresholds[prop];
    let err, exc, val, ref, dft, errDft;
    if (prop === 'lattice') { err = r.err_lin_exp_pct; errDft = r.err_lin_dft_pct; exc = r.excluded; }
    else if (prop === 'bulk_modulus') { err = r.err_exp_pct; errDft = r.err_dft_pct; exc = r.excluded; }
    else if (cmp === '300K') { err = r.err_300K_pct; exc = r.excluded_300K; }
    else { err = r.err_exp_pct; exc = r.excluded; }
    if (exc) return { status: 'Excluded', cls: 'none', reason: explain(exc), err: null, errDft };
    if (err == null) return { status: 'No experimental reference', cls: 'none', errDft,
      reason: prop !== 'thermal_expansion'
        ? 'No sourced experimental value for this property, so only the DFT comparison is shown.'
        : cmp === 'window' ? 'No sourced experimental value covers this temperature window. Try the 300 K comparison.'
        : 'No sourced experimental value spans 300 K for this material. Try the window comparison.' };
    const a = Math.abs(err);
    const g = a <= th.good ? ['Good', 'good'] : a <= th.okay ? ['Okay', 'okay'] : ['Poor', 'poor'];
    return { status: g[0], cls: g[1], err, errDft, reason: '' };
  }
  function explain(e) {
    if (e.startsWith('dynamically unstable')) return `The model predicts an unstable vibration at its own relaxed volume (${e.replace(/^dynamically unstable \(|\)$/g, '').replace('-', '−')}), so quasi-harmonic expansion cannot be computed.`;
    if (e.startsWith('failed: volume_inside_scan')) return 'The quasi-harmonic method breaks down in this temperature range: the predicted volume leaves the range of volumes that was scanned.';
    if (e.startsWith('layered')) return 'Layered material: a uniform volume scan cannot represent expansion that happens almost entirely between layers, so it is computed but not graded.';
    if (e.startsWith('relaxed to a different crystal form')) return `On relaxation the model changes the crystal into a different form (${(e.split('(')[1] || 'different space group').replace(')', '').replace('->', '→')}), so its values are not comparable.`;
    if (e.startsWith('elastic tensor not positive definite')) return 'The model predicts a mechanically unstable crystal (its elastic tensor is not positive definite).';
    return e.charAt(0).toUpperCase() + e.slice(1) + '.';
  }

  function values(prop, r, cmp) {
    if (!r || r.stale) return [];
    if (prop === 'lattice') {
      const rows = [['a, model', fmt(r.a, 3) + ' Å'], ['a, experiment', fmt(r.a_exp, 3) + ' Å'], ['a, DFT (PBE)', fmt(r.a_dft, 3) + ' Å']];
      if (r.c_exp) rows.push(['c, model', fmt(r.c, 3) + ' Å'], ['c, experiment', fmt(r.c_exp, 3) + ' Å']);
      rows.push(['Volume per atom', fmt(r.V_atom, 2) + ' Å³'], ['Error vs DFT', pct(r.err_lin_dft_pct, 2)]);
      return rows;
    }
    if (prop === 'bulk_modulus') {
      const which = r.exp_definition && r.exp_definition.toLowerCase().includes('reuss') ? 'Reuss' : 'VRH';
      return [[`K, model (${which})`, fmt(r.K_for_exp, 1) + ' GPa'], ['K, experiment', fmt(r.B_exp, 1) + ' GPa'],
        ['K_VRH, model', fmt(r.K_vrh, 1) + ' GPa'], ['K_VRH, DFT (PBE)', fmt(r.K_vrh_dft, 1) + ' GPa'],
        ['Error vs DFT', pct(r.err_dft_pct)]];
    }
    if (cmp === '300K') return [['α_V at 300 K, model', fmt(r.alpha_V_300K, 1)], ['α_V at 300 K, experiment', fmt(r.alpha_V_300K_exp, 1)]];
    return [[`α_V ${fmt(r.T_low, 0)}–${fmt(r.T_high, 0)} K, model`, fmt(r.alpha_V, 1)],
      [`α_V ${fmt(r.T_low, 0)}–${fmt(r.T_high, 0)} K, experiment`, fmt(r.alpha_V_exp, 1)]];
  }

  function checks(model, prop, mat) {
    const want = {
      lattice: ['lattice: fingerprint', 'relaxation converged', 'space group unchanged'],
      bulk_modulus: ['bulk modulus: fingerprint', 'relaxation converged', 'space group unchanged', 'elastic tensor', 'elastic fit', 'Birch', 'cubic: EOS'],
      thermal_expansion: ['thermal expansion: fingerprint', 'relaxation converged', 'space group unchanged', 'thermal:'],
    }[prop];
    return (ev.checks[`${model}|${mat}`] || []).filter(([c]) => want.some((w) => c.startsWith(w)));
  }

  function render() {
    const m = mats[st.m], prop = st.p, cmp = st.c;
    const res = (ev.results[prop] || {})[m.id] || {};
    const inStudy = ev.study_materials.includes(m.id);
    const judged = ev.models.map((md) => ({ md, r: res[md.key], j: judge(prop, res[md.key], cmp, md.key, m.id) }));
    const graded = judged.filter((x) => x.j.err != null);
    const best = graded.length >= 2 ? graded.reduce((a, b) => (Math.abs(a.j.err) <= Math.abs(b.j.err) ? a : b)) : null;
    const def = {
      lattice: 'Error is the effective linear error, (V<sub>model</sub>/V<sub>ref</sub>)<sup>1/3</sup> − 1, with V the volume per atom: one number for any crystal system. Experiment is at room temperature, models at 0 K, which accounts for about 0.1–0.3 % of the difference.',
      bulk_modulus: 'Bulk modulus K, how hard the crystal is to compress. Compared like for like: the model’s Reuss value against hydrostatic (compression) measurements, its Voigt–Reuss–Hill (VRH) value against elastic-constant measurements.',
      thermal_expansion: cmp === '300K'
        ? 'Volumetric thermal expansion α<sub>V</sub>, in 10⁻⁶ per K, from the quasi-harmonic approximation, compared with experiment at 300 K. This comparison was added after the method changed; the window comparison is the one fixed in advance.'
        : 'Volumetric thermal expansion α<sub>V</sub>, in 10⁻⁶ per K, from the quasi-harmonic approximation, averaged over a temperature window fixed in advance for each material and compared with experiment averaged over the same window.',
    }[prop];
    const th = ev.thresholds[prop];
    const ref = (m.ref || {})[prop];
    const cards = judged.map(({ md, r, j }) => {
      const vals = values(prop, r, cmp);
      const ck = r && !r.stale ? checks(md.key, prop, m.id) : [];
      return `<article class="mcard" data-model="${md.key}" aria-label="${esc(md.short)}">
        ${best && best.md.key === md.key ? '<p class="lowest">Lowest observed error in this comparison</p>' : ''}
        <h3>${esc(md.short)}${md.via_kups ? '' : '*'}</h3>
        <p class="route">${esc(ROUTE[md.key])}</p>
        <span class="status ${j.cls}">${esc(j.status)}</span>
        ${j.err != null ? `<p class="err">${pct(j.err)}</p><p class="err-label">error against experiment</p>` : ''}
        ${vals.length ? `<dl>${vals.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>` : ''}
        ${j.reason ? `<p class="reason">${esc(j.reason)}</p>` : ''}
        ${ck.length ? `<details class="checks"><summary>${ck.filter((c) => c[1]).length} of ${ck.length} self-checks passed</summary><ul>${ck.map(([c, ok]) => `<li><span class="${ok ? 'ok' : 'bad'}">${ok ? '✓' : '✗'}</span> ${esc(c)}</li>`).join('')}</ul></details>` : ''}
      </article>`;
    }).join('');

    const refKey = prop === 'thermal_expansion' ? (cmp === '300K' ? 'thermal_expansion_300K' : 'thermal_expansion') : prop;
    const cls = ev.models.map((md) => [md, ev.classes[`${refKey}|experiment|${m.class}|${md.key}`]]).filter((x) => x[1]);
    const classPanel = cls.length ? `<section class="panel"><h3>Context: the ${esc(m.class_label.toLowerCase())} class</h3>
      <p>Mean absolute error against experiment over the class's graded materials. Each model is averaged over its own graded materials, so n can differ when a result is excluded.</p>
      <div class="table-wrap"><table><thead><tr><th>Model</th><th class="num">Mean abs. error</th><th class="num">Mean signed error</th><th class="num">n</th></tr></thead><tbody>
      ${cls.map(([md, c]) => `<tr><td>${esc(md.short)}</td><td class="num">${c.MAPE.toFixed(1)} %</td><td class="num">${pct(c.signed)}</td><td class="num">${c.n}</td></tr>`).join('')}
      </tbody></table></div></section>` : '';

    const refPanel = `<section class="panel"><h3>Experimental reference</h3>${ref
      ? `<p>${esc(ref.citation || '')}${ref.T_K ? ` · measured at ${esc(ref.T_K)} K` : ''}</p>
         ${ref.quote ? `<blockquote>“${esc(ref.quote)}”</blockquote>` : ''}
         ${ref.method ? `<p>${esc(ref.method)}</p>` : ''}
         ${ref.source ? `<p><a href="${esc(ref.source)}">Open the source</a></p>` : ''}`
      : '<p class="empty">No sourced experimental value for this property.</p>'}
      ${m.notes ? `<p class="muted">Notes on this material’s references: ${esc(m.notes)}</p>` : ''}</section>`;

    let studyPanel = '';
    if (prop === 'thermal_expansion' && inStudy) {
      const rows = ev.models.map((md) => [md, ev.study[`${md.key}|${m.id}`]]).filter((x) => x[1]);
      studyPanel = `<section class="panel"><h3>Six-case study: what drives this error <span class="tag study">selected case</span></h3>
        <p>${sub(m.formula)} is one of six materials studied in detail after the benchmark showed where models fail, so it is not a random sample. Values are at 300 K with the benchmark’s settings. The ratios split the model’s error into ingredients of α<sub>V</sub> ≈ γ C<sub>V</sub> / (K<sub>T</sub> V): a ratio above 1 pushes the predicted expansion up (for K<sub>T</sub>, a ratio below 1, a softer crystal, pushes it up).</p>
        <div class="table-wrap"><table><thead><tr><th>Model</th><th class="num">α<sub>V</sub> model</th><th class="num">α<sub>V</sub> exp.</th><th class="num">Volume-scan range</th><th class="num">γ model / exp.</th><th class="num">K<sub>T</sub> model / exp.</th><th class="num">C<sub>V</sub> ratio</th></tr></thead><tbody>
        ${rows.map(([md, s]) => `<tr><td>${esc(md.short)}</td><td class="num">${fmt(s.alpha300_qha, 1)}</td><td class="num">${fmt(s.exp_alpha_V, 1)}</td><td class="num">${fmt(s.alpha300_scan_min, 1)}–${fmt(s.alpha300_scan_max, 1)}</td><td class="num">${fmt(s.gamma, 2)} / ${fmt(s.exp_gamma, 2)}</td><td class="num">${fmt(s.KT300_GPa, 0)} / ${fmt(s.exp_KT_GPa, 0)} GPa</td><td class="num">${fmt(s.r_Cv, 2)}</td></tr>`).join('')}
        </tbody></table></div>
        ${judged.every((x) => x.j.err == null) && cmp === '300K' ? '<p class="muted">The study compares against its own reference for this material (for HfO₂, a provisional 293–400 K average), which the benchmark does not accept as a 300 K value. See the technical write-up.</p>' : ''}
        <p class="muted">The experimental γ is inferred from measured α, K and C<sub>V</sub> with the same relation, so it is not an independent measurement. The volume-scan range is a sensitivity range across three scan settings, not a confidence interval. Study values can differ slightly from the benchmark’s because each comes from its own run.</p>
        <p><a href="study.html">Read the study</a> · <a href="${blob('docs/thermal_failure_study.md')}">full technical write-up</a></p></section>`;
    }

    const dataPanel = `<section class="panel"><h3>Data and reproduction</h3><div class="links">
      ${ev.models.map((md) => `<a href="${blob(`results/raw/${md.key}/${STEP[prop]}.json`)}">${esc(md.short)} raw result</a>`).join('')}
      <a href="${blob('results/' + CSV[prop])}">Merged table (CSV)</a>
      <a href="${blob('configs/benchmark.yaml')}">Settings</a>
      <a href="reproduce.html">How to rerun it</a></div>
      <pre><code>chipff ${prop === 'thermal_expansion' ? 'qha' : 'static'} -m mace-mpa-0 --materials ${esc(m.id)} --force</code></pre></section>`;

    root.innerHTML = `<div class="mat-head"><h2>${sub(m.formula)}</h2><span class="muted">${esc(m.phase)} · ${esc(m.class_label)}</span>
        ${inStudy ? '<span class="tag study">In the six-case study</span>' : ''}</div>
      <p class="mat-meta">Role in a device: ${esc(m.role)}${m.mp_id ? ` · Materials Project <a href="https://next-gen.materialsproject.org/materials/${esc(m.mp_id)}">${esc(m.mp_id)}</a>` : ''}</p>
      <p class="def"><strong>${PROPS[prop]}${prop === 'thermal_expansion' ? (cmp === '300K' ? ', 300 K' : ', temperature window') : ''}.</strong> ${def}
        Grades use thresholds fixed before any result was compared: good ≤ ${th.good} %, okay ≤ ${th.okay} %.</p>
      <div class="model-cards">${cards}</div>
      ${best ? '<p class="muted" style="margin-top:12px">The lowest observed error here describes this one comparison. It is not a recommendation: across the benchmark, against experiment, no difference between the models is resolved for any of the three properties.</p>' : ''}
      ${studyPanel}${classPanel}${refPanel}${dataPanel}`;
    document.title = `${uni(m.formula)}, ${PROPS[prop].toLowerCase()} · Explore evidence · BeyondStructure Bench`;
  }
  function go(push = true) { sync(); if (push) write(); render(); }
  go();
})();
