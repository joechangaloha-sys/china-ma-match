"""Kimi's original standalone teaser prototype, under the demo gate only."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config

router = APIRouter()
ROOT = Path(__file__).parent / 'teaser_demo'
FILES = {'index.html', 'assets/app.js', 'assets/styles.css', 'assets/favicon.svg', 'data/teaser.json'}


def asset(name):
    if not config.DEMO_MODE or name not in FILES:
        raise HTTPException(404)
    return FileResponse(ROOT / name, headers={'Cache-Control': 'no-store',
                         'X-Robots-Tag': 'noindex, nofollow, noarchive'})


@router.get('/teaser-demo/', response_class=FileResponse)
def standalone_teaser():
    return asset('index.html')


@router.get('/teaser-demo/{asset_path:path}', response_class=FileResponse)
def standalone_teaser_asset(asset_path: str):
    return asset(asset_path)
