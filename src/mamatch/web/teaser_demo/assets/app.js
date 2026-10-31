const isChinese = Boolean(document.documentElement?.lang?.startsWith('zh'));
const tr = (en, zh) => isChinese ? zh : en;
const messages = {
  'Demo numeric ranges are finite and ordered; disclosed losses are permitted.': '示例数据区间为有效数值且上下限有序；允许如实披露亏损。',
  'Invalid or unordered demo numeric ranges.': '示例数据区间无效或上下限顺序错误。',
  'Illustrative dates are valid and not in the future.': '示例日期有效，且未晚于当前日期。',
  'A demo information or approval date is invalid or in the future.': '示例资料或审核日期无效，或晚于当前日期。',
  'No prohibited promotional wording detected.': '未检出禁止使用的宣传性措辞。',
  'Prohibited promotional wording detected.': '检出禁止使用的宣传性措辞。',
  'No company suffix, personal phone, email or ID number detected in public text.': '未在正文中检出公司后缀、个人手机号码、电子邮箱或身份证号码。',
  'A potential direct identifier was detected in public text.': '正文中检出可能用于直接识别主体的信息。',
  'The fictional record labels its anonymity review as passed; this is not an independent review.': '虚构记录标注为已通过匿名化审核，不代表已完成独立核查。',
  'Anonymity review has not passed.': '匿名化审核尚未通过。',
  'Illustrative seller/internal approval fields are present; no real approval is verified.': '示例卖方确认及内部审核字段完整，不代表已核实真实批准。',
  'Seller or internal approval is incomplete.': '卖方确认或内部审核信息不完整。',
  'This demo uses deterministic rendering only; no AI output is present.': '本演示仅按固定规则编排文档，不含人工智能生成内容。',
  'AI-assisted output requires model and prompt provenance review.': '人工智能辅助内容须审核模型及提示词来源记录。',
  'Demo checks passed. This does not authorise publication.': '演示核查通过，不构成对外提供授权。',
  'Teaser text copied to clipboard.': '项目简介正文已复制。',
  'Teaser text copied using the browser fallback.': '已通过浏览器备用方式复制项目简介正文。',
  'Structured teaser JSON downloaded.': '结构化项目资料已下载。',
  'Teaser rendered from structured demonstration data.': '已根据结构化虚构资料生成项目简介。',
  'Opening the browser print dialog.': '正在打开浏览器打印窗口。',
  'Teaser data failed to load.': '项目资料加载失败。'
};
const fieldLabels = {
 teaser_spec_version:'资料规范版本',listing_id:'项目编号',project_code:'项目代号',public_headline:'项目标题',industry_l1:'行业大类',industry_l2:'细分行业',region_public:'概括性地区',business_summary_public:'业务概况',service_categories_public:'服务类别',customer_mix_public:'客户结构',operating_history_public:'经营年限',transaction_type_public:'交易方式',stake_description_public:'拟转让股权',reason_for_sale_public:'出售原因',target_buyer_types:'潜在投资方类型',process_timeline_public:'流程安排',nda_required:'是否需要保密协议',next_step_text:'后续流程',financial_period_start:'报告期开始日',financial_period_end:'报告期结束日',financial_period_public:'报告期间',currency:'币种',revenue_min:'营业收入下限',revenue_max:'营业收入上限',profit_metric_type:'盈利指标',profit_min:'盈利指标下限',profit_max:'盈利指标上限',financial_basis_public:'财务数据口径',employee_count_min:'员工人数下限',employee_count_max:'员工人数上限',site_count_min:'经营网点数量下限',site_count_max:'经营网点数量上限',recurring_revenue_min_pct:'持续性服务收入占比下限',recurring_revenue_max_pct:'持续性服务收入占比上限',revenue_quality_public:'收入质量说明',margin_comment_public:'盈利情况说明',highlights:'项目要点',text:'陈述内容',source_claim_id:'来源陈述编号',information_as_of:'资料基准日',verification_label:'核查说明',checks_completed_public:'示例核查事项',reviewer_role:'审核角色',reviewer_id:'审核人编号',seller_confirmed_at:'卖方确认时间',internal_approved_at:'内部审核时间',publication_approved_by:'批准人编号',anonymity_review_status:'匿名化审核状态',ai_assisted:'是否使用人工智能',ai_disclosure_required:'是否需要人工智能使用说明',source_claim_ids:'来源陈述编号列表'
};
function localiseMessage(message) {
 if (!isChinese) return message;
 if (messages[message]) return messages[message];
 let match;
 if ((match = message.match(/^All (\d+) required demonstration fields are present\.$/))) return `全部${match[1]}项必填示例字段均已填写。`;
 if ((match = message.match(/^Missing required fields: (.+)\.$/))) return `缺少必填字段：${match[1].split(', ').map(k => fieldLabels[k] || '未识别字段').join('、')}。`;
 if ((match = message.match(/^All (\d+) highlights map to source claim IDs\.$/))) return `全部${match[1]}项项目要点均已对应来源陈述编号。`;
 if ((match = message.match(/^(\d+) highlight\(s\) do not map to illustrative claim IDs\.$/))) return `${match[1]}项项目要点未对应示例陈述编号。`;
 if ((match = message.match(/^(\d+) demo check\(s\) failed\.$/))) return `${match[1]}项演示核查未通过。`;
 if ((match = message.match(/^Demo checks passed with (\d+) warning\(s\)\.$/))) return `演示核查通过，存在${match[1]}项提示。`;
 return '请核对示例资料。';
}
function displayRecord(value) {
 if (!isChinese) return value;
 if (Array.isArray(value)) return value.map(displayRecord);
 if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [fieldLabels[k] || k, displayRecord(v)]));
 if (typeof value === 'boolean') return value ? '是' : '否';
 if (typeof value === 'string') return value.replace(/^CNY$/, '人民币').replace(/^passed$/, '已通过').replace('demo-listing-', '示例项目').replace('user-demo-', '示例人员').replace('claim-demo-', '示例陈述').replace(/^(\d{4})-(\d{2})-(\d{2})(T|$)/, '$1年$2月$3日 ').replace(/\+08:00$/, ' 北京时间').trim();
 return value;
}

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
  return new Intl.DateTimeFormat(isChinese ? 'zh-CN' : 'en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'Asia/Shanghai'
  }).format(new Date(`${value}T00:00:00+08:00`));
}

function formatMoney(value) {
  if (isChinese) return `${(value / 10000).toLocaleString('zh-CN')}万元`;
  if (value >= 1000000) {
    const millions = value / 1000000;
    return `${Number.isInteger(millions) ? millions : millions.toFixed(1)} million`;
  }
  return value.toLocaleString('en-CN');
}

function moneyRange(data) {
  return isChinese ? `人民币${formatMoney(data.revenue_min)}至${formatMoney(data.revenue_max)}` : `${data.currency === 'CNY' ? 'RMB' : data.currency} ${formatMoney(data.revenue_min)}–${formatMoney(data.revenue_max)}`;
}

function profitRange(data) {
  return isChinese ? `人民币${formatMoney(data.profit_min)}至${formatMoney(data.profit_max)}` : `${data.currency === 'CNY' ? 'RMB' : data.currency} ${formatMoney(data.profit_min)}–${formatMoney(data.profit_max)}`;
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
    <p class="teaser-subtitle">${tr('Anonymous public teaser generated from structured, source-linked demonstration data.','根据结构化虚构资料及对应来源陈述编排的匿名项目简介。')}</p>

    <section class="teaser-section" aria-labelledby="snapshot-heading">
      <h3 id="snapshot-heading">${tr('Transaction snapshot','交易概况')}</h3>
      <p>${tr(`${escapeHtml(data.project_code)} presents an established ${escapeHtml(data.industry_l2).toLowerCase()} business based in ${escapeHtml(data.region_public)}. ${escapeHtml(data.business_summary_public)}`, `${escapeHtml(data.project_code)}的标的公司为一家位于${escapeHtml(data.region_public)}的${escapeHtml(data.industry_l2)}企业。${escapeHtml(data.business_summary_public)}`)}</p>
      <p>${tr(`${escapeHtml(data.stake_description_public)}. ${escapeHtml(data.reason_for_sale_public)} The process is expected to suit ${escapeHtml(data.target_buyer_types.join(', ').toLowerCase())}s.`, `${escapeHtml(data.stake_description_public)}。${escapeHtml(data.reason_for_sale_public)}潜在投资方包括${escapeHtml(data.target_buyer_types.join('、'))}。`)}</p>
      <table class="snapshot-table">
        <tbody>
          <tr><th scope="row">${tr('Sector','所属行业')}</th><td>${escapeHtml(data.industry_l2)}</td></tr>
          <tr><th scope="row">${tr('Location','所在地区')}</th><td>${escapeHtml(data.region_public)}</td></tr>
          <tr><th scope="row">${tr('Operating history','经营年限')}</th><td>${escapeHtml(data.operating_history_public)}</td></tr>
          <tr><th scope="row">${tr('FY2025 revenue','2025年度营业收入')}</th><td>${escapeHtml(moneyRange(data))}</td></tr>
          <tr><th scope="row">${tr('FY2025 adjusted EBITDA','2025年度经调整的息税折旧及摊销前利润')}</th><td>${escapeHtml(profitRange(data))}</td></tr>
          <tr><th scope="row">${tr('Employees','员工人数')}</th><td>${escapeHtml(data.employee_count_min)}–${escapeHtml(data.employee_count_max)}</td></tr>
          <tr><th scope="row">${tr('Operating locations','经营网点数量')}</th><td>${escapeHtml(data.site_count_min)}–${escapeHtml(data.site_count_max)}</td></tr>
          <tr><th scope="row">${tr('Information as of','资料基准日')}</th><td>${formatDate(data.information_as_of)}</td></tr>
        </tbody>
      </table>
    </section>

    <section class="teaser-section" aria-labelledby="overview-heading">
      <h3 id="overview-heading">${tr('Business overview','业务概况')}</h3>
      <p>${tr(`The business provides ${escapeHtml(data.service_categories_public.join(', ').toLowerCase())} for industrial equipment used by manufacturing and warehouse operators.`, `标的公司主要面向制造业及仓储行业客户提供${escapeHtml(data.service_categories_public.join('、'))}服务。`)}</p>
      <p>${tr(`It serves ${escapeHtml(data.customer_mix_public.toLowerCase())} across ${escapeHtml(data.region_public)}. ${escapeHtml(data.revenue_quality_public)}`, `客户主要分布于${escapeHtml(data.region_public)}，包括${escapeHtml(data.customer_mix_public)}。${escapeHtml(data.revenue_quality_public)}`)}</p>
      <p>${tr(`The business operates through a regional service network with ${escapeHtml(data.site_count_min)} to ${escapeHtml(data.site_count_max)} operating locations and approximately ${escapeHtml(data.employee_count_min)} to ${escapeHtml(data.employee_count_max)} employees.`, `标的公司拥有区域性服务网络，经营网点数量为${escapeHtml(data.site_count_min)}处至${escapeHtml(data.site_count_max)}处，员工人数约为${escapeHtml(data.employee_count_min)}人至${escapeHtml(data.employee_count_max)}人。`)}</p>
    </section>

    <section class="teaser-section" aria-labelledby="highlights-heading">
      <h3 id="highlights-heading">${tr('Key highlights','项目要点')}</h3>
      <ul class="highlight-list">${highlights}</ul>
    </section>

    <section class="teaser-section" aria-labelledby="financial-heading">
      <h3 id="financial-heading">${tr('Financial profile','主要财务指标')}</h3>
      <p>${tr(`For ${escapeHtml(data.financial_period_public)}, the business reported revenue of ${escapeHtml(moneyRange(data))} and ${escapeHtml(data.profit_metric_type)} of ${escapeHtml(profitRange(data))}.`, `${escapeHtml(data.financial_period_public)}营业收入区间为${escapeHtml(moneyRange(data))}，${escapeHtml(data.profit_metric_type)}区间为${escapeHtml(profitRange(data))}。`)}</p>
      <p>${tr(`${escapeHtml(data.margin_comment_public)} Financial information is based on ${escapeHtml(data.financial_basis_public.toLowerCase())} and has not been audited by the platform.`, `${escapeHtml(data.margin_comment_public)}财务数据采用${escapeHtml(data.financial_basis_public)}，未经平台审计。`)}</p>
    </section>

    <section class="teaser-section" aria-labelledby="verification-heading">
      <h3 id="verification-heading">${tr('Verification status','资料核查情况')}</h3>
      <div class="verification-box">
        <strong>${tr(`Checked as of ${formatDate(data.information_as_of)}`, `示例核查基准日：${formatDate(data.information_as_of)}`)}</strong>
        <ul class="check-list">${checks}</ul>
        <p><b>${tr('Verification status:','核查说明：')}</b> ${escapeHtml(data.verification_label)}${tr('.', '。')}</p>
      </div>
      <p>${tr('These checks are limited to the items listed above. They are not a guarantee of the business, its financial performance or the outcome of any transaction.','核查范围仅限于上述示例事项，不构成对标的公司经营、财务表现或交易结果的保证。')}</p>
    </section>

    <section class="teaser-section" aria-labelledby="process-heading">
      <h3 id="process-heading">${tr('Process and next step','交易流程及后续安排')}</h3>
      <p>${escapeHtml(data.next_step_text)}</p>
      <p>${escapeHtml(data.process_timeline_public)}</p>
    </section>

    <section class="teaser-section" aria-labelledby="notice-heading">
      <h3 id="notice-heading">${tr('Important notice','重要提示')}</h3>
      <div class="disclaimer">
        ${tr('This teaser is provided for preliminary discussion only. It is not an offer, recommendation, valuation or guarantee. Information is seller-provided unless expressly stated otherwise and may change without notice. Recipients must conduct their own legal, financial, tax, technical and commercial due diligence before entering into any transaction.','本项目简介仅供初步讨论，不构成要约、投资建议、估值意见或任何保证。除另有明确说明外，资料由卖方提供，可能发生变更。正式交易前，接收方应自行开展法律、财务、税务、技术及商业尽职调查。')}<br><br>
        ${tr('Distribution of this teaser does not authorise onward distribution. The seller and platform reserve the right to amend, suspend or withdraw the process at any time.','取得本项目简介不代表获准转发。卖方及平台保留调整、暂停或终止交易流程的权利。')}
      </div>
    </section>
  `;
}

function checkItem(status, text) {
  return { status, text: localiseMessage(text) };
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

  const forbidden = /(guaranteed|risk[- ]free|market[- ]leading|exceptional returns|urgent sale|保本|稳赚|零风险|保证收益)/i;
  checks.push(!forbidden.test(text)
    ? checkItem('pass', 'No prohibited promotional wording detected.')
    : checkItem('fail', 'Prohibited promotional wording detected.'));

  const directIdentifier = /(有限公司|股份公司|[A-Z][\w&.,'-]+\s+(Ltd|Limited|Co\.,?\s*Ltd|LLC|Inc\.)|\b1[3-9]\d{9}\b|[\w.+-]+@[\w-]+\.[\w.]+|\b\d{17}[\dXx]\b)/;
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
  feedback.textContent = localiseMessage(message);
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
  const blob = new Blob([JSON.stringify(displayRecord(state.teaser), null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = isChinese ? '柳树项目－简介资料.json' : 'project-willow-teaser-data.json';
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
    jsonPreview.textContent = JSON.stringify(displayRecord(state.teaser), null, 2);
    renderTeaser(state.teaser);
    runValidation(state.teaser);
  } catch (error) {
    content.innerHTML = `<div class="loading-state">${isChinese ? '项目资料加载失败，请稍后重试。' : `Unable to load the teaser data. ${escapeHtml(error.message)}`}</div>`;
    jsonPreview.textContent = tr('Unable to load data/teaser.json.', '结构化资料加载失败。');
    setFeedback('Teaser data failed to load.');
  }
}

initialise();
