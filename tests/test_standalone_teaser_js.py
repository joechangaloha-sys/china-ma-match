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
