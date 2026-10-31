"""Regression checks for the imported browser validator, independent of the DOM/UI."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_demo_checks_reject_invalid_numbers_dates_and_unmapped_claims():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is optional outside browser-asset validation')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, '-e', r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes={};
const ctx={document:{querySelector:s=>nodes[s]??={innerText:'Fictional business description',innerHTML:'',textContent:''}},Intl,Date,Set};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('src/mamatch/web/teaser_demo/assets/app.js','utf8').replace(/initialise\(\);\s*$/,''),ctx);
const baseline=JSON.parse(fs.readFileSync('src/mamatch/web/teaser_demo/data/teaser.json','utf8'));
function checks(change){ctx.sample=structuredClone(baseline);change?.(ctx.sample);return vm.runInContext('runValidation(sample)',ctx);}
assert(checks().every(c=>c.status!=='fail'));
assert(checks(x=>{x.revenue_min=-40;x.revenue_max=-25}).some(c=>c.status==='fail'));
assert(checks(x=>{x.seller_confirmed_at='not-a-date'}).some(c=>c.status==='fail'));
assert(checks(x=>{x.highlights[0].source_claim_id='missing'}).some(c=>c.status==='fail'));
assert(checks(x=>{x.profit_min=-7;x.profit_max=-4}).every(c=>c.status!=='fail'));
assert(nodes['#feedback-line'].textContent.includes('does not authorise publication'));
console.log('Standalone demo validator regressions passed');
'''], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_chinese_runtime_matches_english_structure_and_stays_chinese():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is optional outside browser-asset validation')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, '-e', r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
function render(lang,file){
 const nodes={};const ctx={document:{documentElement:{lang},querySelector:s=>nodes[s]??={innerText:'虚构企业资料',innerHTML:'',textContent:''}},Intl,Date,Set};
 vm.createContext(ctx);
 vm.runInContext(fs.readFileSync('src/mamatch/web/teaser_demo/assets/app.js','utf8').replace(/initialise\(\);\s*$/,''),ctx);
 ctx.sample=JSON.parse(fs.readFileSync('src/mamatch/web/teaser_demo/data/'+file,'utf8'));
 vm.runInContext('renderTeaser(sample)',ctx);
 const checks=vm.runInContext('runValidation(sample)',ctx);assert(checks.every(c=>c.status==='pass'));
 return {ctx,nodes,html:nodes['#teaser-content'].innerHTML};
}
const en=render('en','teaser.json'),zh=render('zh-CN','teaser_zh.json');
assert.deepEqual(en.html.match(/<[^>]+>/g),zh.html.match(/<[^>]+>/g));
assert(!/[A-Za-z]/.test(zh.html.replace(/<[^>]+>/g,'')));
assert(!/[A-Za-z]/.test(zh.nodes['#feedback-line'].textContent));
assert(zh.nodes['#feedback-line'].textContent.includes('不构成对外提供授权'));
const record=vm.runInContext('JSON.stringify(displayRecord(sample))',zh.ctx);
assert(!/[A-Za-z]/.test(record));assert(record.includes('营业收入下限'));
zh.ctx.sample.highlights[0].text='保证收益';zh.nodes['#teaser-content'].innerText='保证收益';
assert(vm.runInContext('runValidation(sample)',zh.ctx).some(c=>c.status==='fail'&&c.text.includes('宣传')));
console.log('Chinese structure, copy, validation and export passed');
'''], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
