const state = {
  teaser: null,
  checksRun: false
};

const content = document.querySelector('#teaser-content');
const jsonPreview = document.querySelector('#json-preview');
const checkResults = document.querySelector('#check-results');
const feedback = document.querySelector('#feedback-line');

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatDate(value) {
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'Asia/Shanghai'
  }).format(new Date(`${value}T00:00:00+08:00`));
}

function formatMoney(value) {
  if (value >= 1000000) {
    const millions = value / 1000000;
    return `${Number.isInteger(millions) ? millions : millions.toFixed(1)} million`;
  }
  return value.toLocaleString('en-CN');
}

function moneyRange(data) {
  return `${data.currency === 'CNY' ? 'RMB' : data.currency} ${formatMoney(data.revenue_min)}–${formatMoney(data.revenue_max)}`;
}

function profitRange(data) {
  return `${data.currency === 'CNY' ? 'RMB' : data.currency} ${formatMoney(data.profit_min)}–${formatMoney(data.profit_max)}`;
}

function renderTeaser(data) {
  const highlights = data.highlights.map(item => `<li>${escapeHtml(item.text)}</li>`).join('');
  const checks = data.checks_completed_public.map(item => `<li>${escapeHtml(item)}</li>`).join('');

  content.innerHTML = `
    <div class="teaser-kicker">
      <span class="tag yellow">${escapeHtml(data.project_code)}</span>
      <span class="tag">${escapeHtml(data.industry_l1)}</span>
      <span class="tag">${escapeHtml(data.region_public)}</span>
      <span class="tag">${escapeHtml(data.transaction_type_public)}</span>
    </div>

    <h2 class="teaser-title" id="teaser-title">${escapeHtml(data.public_headline)}</h2>
    <p class="teaser-subtitle">Anonymous public teaser generated from structured, source-linked demonstration data.</p>

    <section class="teaser-section" aria-labelledby="snapshot-heading">
      <h3 id="snapshot-heading">Transaction snapshot</h3>
      <p>${escapeHtml(data.project_code)} presents an established ${escapeHtml(data.industry_l2).toLowerCase()} business based in ${escapeHtml(data.region_public)}. ${escapeHtml(data.business_summary_public)}</p>
      <p>${escapeHtml(data.stake_description_public)}. ${escapeHtml(data.reason_for_sale_public)} The process is expected to suit ${escapeHtml(data.target_buyer_types.join(', ').toLowerCase())}s.</p>
      <table class="snapshot-table">
        <tbody>
          <tr><th scope="row">Sector</th><td>${escapeHtml(data.industry_l2)}</td></tr>
          <tr><th scope="row">Location</th><td>${escapeHtml(data.region_public)}</td></tr>
          <tr><th scope="row">Operating history</th><td>${escapeHtml(data.operating_history_public)}</td></tr>
          <tr><th scope="row">FY2025 revenue</th><td>${escapeHtml(moneyRange(data))}</td></tr>
          <tr><th scope="row">FY2025 adjusted EBITDA</th><td>${escapeHtml(profitRange(data))}</td></tr>
          <tr><th scope="row">Employees</th><td>${escapeHtml(data.employee_count_min)}–${escapeHtml(data.employee_count_max)}</td></tr>
          <tr><th scope="row">Operating locations</th><td>${escapeHtml(data.site_count_min)}–${escapeHtml(data.site_count_max)}</td></tr>
          <tr><th scope="row">Information as of</th><td>${formatDate(data.information_as_of)}</td></tr>
        </tbody>
      </table>
    </section>

    <section class="teaser-section" aria-labelledby="overview-heading">
      <h3 id="overview-heading">Business overview</h3>
      <p>The business provides ${escapeHtml(data.service_categories_public.join(', ').toLowerCase())} for industrial equipment used by manufacturing and warehouse operators.</p>
      <p>It serves ${escapeHtml(data.customer_mix_public.toLowerCase())} across ${escapeHtml(data.region_public)}. ${escapeHtml(data.revenue_quality_public)}</p>
      <p>The business operates through a regional service network with ${escapeHtml(data.site_count_min)} to ${escapeHtml(data.site_count_max)} operating locations and approximately ${escapeHtml(data.employee_count_min)} to ${escapeHtml(data.employee_count_max)} employees.</p>
    </section>

    <section class="teaser-section" aria-labelledby="highlights-heading">
      <h3 id="highlights-heading">Key highlights</h3>
      <ul class="highlight-list">${highlights}</ul>
    </section>

    <section class="teaser-section" aria-labelledby="financial-heading">
      <h3 id="financial-heading">Financial profile</h3>
      <p>For ${escapeHtml(data.financial_period_public)}, the business reported revenue of ${escapeHtml(moneyRange(data))} and ${escapeHtml(data.profit_metric_type)} of ${escapeHtml(profitRange(data))}.</p>
      <p>${escapeHtml(data.margin_comment_public)} Financial information is based on ${escapeHtml(data.financial_basis_public.toLowerCase())} and has not been audited by the platform.</p>
    </section>

    <section class="teaser-section" aria-labelledby="verification-heading">
      <h3 id="verification-heading">Verification status</h3>
      <div class="verification-box">
        <strong>Checked as of ${formatDate(data.information_as_of)}</strong>
        <ul class="check-list">${checks}</ul>
        <p><b>Verification status:</b> ${escapeHtml(data.verification_label)}.</p>
      </div>
      <p>These checks are limited to the items listed above. They are not a guarantee of the business, its financial performance or the outcome of any transaction.</p>
    </section>

    <section class="teaser-section" aria-labelledby="process-heading">
      <h3 id="process-heading">Process and next step</h3>
      <p>${escapeHtml(data.next_step_text)}</p>
      <p>${escapeHtml(data.process_timeline_public)}</p>
    </section>

    <section class="teaser-section" aria-labelledby="notice-heading">
      <h3 id="notice-heading">Important notice</h3>
      <div class="disclaimer">
        This teaser is provided for preliminary discussion only. It is not an offer, recommendation, valuation or guarantee. Information is seller-provided unless expressly stated otherwise and may change without notice. Recipients must conduct their own legal, financial, tax, technical and commercial due diligence before entering into any transaction.<br><br>
        Distribution of this teaser does not authorise onward distribution. The seller and platform reserve the right to amend, suspend or withdraw the process at any time.
      </div>
    </section>
  `;
}

function checkItem(status, text) {
  return { status, text };
}

function runValidation(data) {
  const text = content.innerText;
  const checks = [];

  const required = [
    'project_code', 'public_headline', 'industry_l1', 'region_public',
    'transaction_type_public', 'financial_period_public', 'currency',
    'verification_label', 'information_as_of', 'seller_confirmed_at',
    'internal_approved_at', 'publication_approved_by'
  ];
  const missing = required.filter(key => data[key] === undefined || data[key] === null || data[key] === '');
  checks.push(missing.length === 0
    ? checkItem('pass', `All ${required.length} required demonstration fields are present.`)
    : checkItem('fail', `Missing required fields: ${missing.join(', ')}.`));

  const numeric = ['revenue_min', 'revenue_max', 'profit_min', 'profit_max',
    'employee_count_min', 'employee_count_max', 'site_count_min', 'site_count_max'];
  const finite = numeric.every(key => typeof data[key] === 'number' && Number.isFinite(data[key]));
  const ordered = finite && data.revenue_min >= 0 && data.revenue_min < data.revenue_max
    && data.profit_min < data.profit_max && data.employee_count_min >= 0
    && data.employee_count_min <= data.employee_count_max && data.site_count_min >= 0
    && data.site_count_min <= data.site_count_max;
  checks.push(ordered
    ? checkItem('pass', 'Demo numeric ranges are finite and ordered; disclosed losses are permitted.')
    : checkItem('fail', 'Invalid or unordered demo numeric ranges.'));
  const dateFields = ['information_as_of', 'seller_confirmed_at', 'internal_approved_at'];
  const datesValid = dateFields.every(key => typeof data[key] === 'string'
    && /^\d{4}-\d{2}-\d{2}(T.*)?$/.test(data[key]) && Number.isFinite(Date.parse(data[key]))
    && Date.parse(data[key]) <= Date.now());
  checks.push(datesValid
    ? checkItem('pass', 'Illustrative dates are valid and not in the future.')
    : checkItem('fail', 'A demo information or approval date is invalid or in the future.'));

  const claimSet = new Set(data.source_claim_ids);
  const unmapped = data.highlights.filter(item => !claimSet.has(item.source_claim_id));
  checks.push(unmapped.length === 0
    ? checkItem('pass', `All ${data.highlights.length} highlights map to source claim IDs.`)
    : checkItem('fail', `${unmapped.length} highlight(s) do not map to illustrative claim IDs.`));

  const forbidden = /(guaranteed|risk[- ]free|market[- ]leading|exceptional returns|urgent sale)/i;
  checks.push(!forbidden.test(text)
    ? checkItem('pass', 'No prohibited promotional wording detected.')
    : checkItem('fail', 'Prohibited promotional wording detected.'));

  const directIdentifier = /([A-Z][\w&.,'-]+\s+(Ltd|Limited|Co\.,?\s*Ltd|LLC|Inc\.)|\b1[3-9]\d{9}\b|[\w.+-]+@[\w-]+\.[\w.]+|\b\d{17}[\dXx]\b)/;
  checks.push(!directIdentifier.test(text)
    ? checkItem('pass', 'No company suffix, personal phone, email or ID number detected in public text.')
    : checkItem('fail', 'A potential direct identifier was detected in public text.'));

  checks.push(data.anonymity_review_status === 'passed'
    ? checkItem('pass', 'The fictional record labels its anonymity review as passed; this is not an independent review.')
    : checkItem('fail', 'Anonymity review has not passed.'));

  const approved = Boolean(data.seller_confirmed_at && data.internal_approved_at && data.publication_approved_by);
  checks.push(approved
    ? checkItem('pass', 'Illustrative seller/internal approval fields are present; no real approval is verified.')
    : checkItem('fail', 'Seller or internal approval is incomplete.'));

  checks.push(data.ai_assisted === false
    ? checkItem('pass', 'This demo uses deterministic rendering only; no AI output is present.')
    : checkItem('warn', 'AI-assisted output requires model and prompt provenance review.'));

  checkResults.innerHTML = checks.map(item => `
    <div class="check-item ${item.status}">
      <span aria-hidden="true"></span>
      <div>${escapeHtml(item.text)}</div>
    </div>
  `).join('');

  state.checksRun = true;
  const failures = checks.filter(item => item.status === 'fail').length;
  const warnings = checks.filter(item => item.status === 'warn').length;
  setFeedback(failures ? `${failures} demo check(s) failed.` : warnings ? `Demo checks passed with ${warnings} warning(s).` : 'Demo checks passed. This does not authorise publication.');
  return checks;
}

function setFeedback(message) {
  feedback.textContent = message;
}

async function copyTeaser() {
  const text = content.innerText;
  try {
    await navigator.clipboard.writeText(text);
    setFeedback('Teaser text copied to clipboard.');
  } catch (error) {
    const helper = document.createElement('textarea');
    helper.value = text;
    document.body.append(helper);
    helper.select();
    document.execCommand('copy');
    helper.remove();
    setFeedback('Teaser text copied using the browser fallback.');
  }
}

function downloadJson() {
  if (!state.teaser) return;
  const blob = new Blob([JSON.stringify(state.teaser, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'project-willow-teaser-data.json';
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setFeedback('Structured teaser JSON downloaded.');
}

function bindTabs() {
  document.querySelectorAll('[data-tab]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-tab]').forEach(tab => tab.setAttribute('aria-selected', 'false'));
      document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('is-hidden'));
      button.setAttribute('aria-selected', 'true');
      document.querySelector(`#${button.dataset.tab}`).classList.remove('is-hidden');
    });
  });
}

async function initialise() {
  bindTabs();

  document.querySelector('#render-button').addEventListener('click', () => {
    if (!state.teaser) return;
    renderTeaser(state.teaser);
    setFeedback('Teaser rendered from structured demonstration data.');
  });
  document.querySelector('#checks-button').addEventListener('click', () => {
    if (!state.teaser) return;
    runValidation(state.teaser);
  });
  document.querySelector('#copy-button').addEventListener('click', copyTeaser);
  document.querySelector('#download-button').addEventListener('click', downloadJson);
  document.querySelector('#print-button').addEventListener('click', () => {
    setFeedback('Opening the browser print dialog.');
    window.print();
  });

  try {
    const response = await fetch('data/teaser.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.teaser = await response.json();
    jsonPreview.textContent = JSON.stringify(state.teaser, null, 2);
    renderTeaser(state.teaser);
    runValidation(state.teaser);
  } catch (error) {
    content.innerHTML = `<div class="loading-state">Unable to load the teaser data. ${escapeHtml(error.message)}</div>`;
    jsonPreview.textContent = 'Unable to load data/teaser.json.';
    setFeedback('Teaser data failed to load.');
  }
}

initialise();
