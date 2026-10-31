#!/usr/bin/env python3
"""Root-only local PostgreSQL/files backup and isolated restore rehearsal. No live restore."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time
import uuid

DB='mamatch-lighthouse-db-1'
WEB='mamatch-lighthouse-web-1'
ROOT=Path('/opt/mamatch/backups')
COMPOSE=['docker','compose','--env-file','/opt/mamatch/.env','-f','deploy/lighthouse/compose.lighthouse.yaml','-f','deploy/lighthouse/compose.git.yaml']


def run(args, **kw):
    # Child Docker commands must never consume the SSH deployment script's stdin.
    if 'stdin' not in kw and 'input' not in kw:kw['stdin']=subprocess.DEVNULL
    return subprocess.run(args,check=True,**kw)


def db_command(command, args=()):
    # Credentials remain inside the existing DB container; never interpolate or print them.
    script='exec '+command+' -U "$POSTGRES_USER" '+(' -d "$POSTGRES_DB" ' if command in ('psql','pg_dump') else ' ')+' "$@"'
    return ['docker','exec','-i',DB,'sh','-c',script,'sh',*args]


class Snapshot:
    def __init__(self,database=None):
        args=['-X','-qAt','-v','ON_ERROR_STOP=1']
        if database:args+=['-d',database]
        self.process=subprocess.Popen(db_command('psql',args),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.query("SET timezone='UTC'; SET search_path=public; BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;")
    def query(self,sql):
        marker='end_'+uuid.uuid4().hex
        self.process.stdin.write(sql+"\nSELECT '"+marker+"';\n");self.process.stdin.flush()
        lines=[]
        for line in self.process.stdout:
            if line.strip()==marker:return lines
            if line.strip():lines.append(line.strip())
        raise RuntimeError('Database snapshot command failed')
    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write('ROLLBACK;\n\\q\n');self.process.stdin.flush()
            self.process.communicate(timeout=15)


def identifier(value):
    if not re.fullmatch(r'[a-z][a-z0-9_]*',value):raise RuntimeError('Unexpected database identifier')
    return '"'+value+'"'


def inventory(snapshot,tables):
    rows={}
    for table in tables:
        sql=f'''SELECT json_build_object('count',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex')) FROM
        (SELECT encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex') h FROM {identifier(table)} t) hashes;'''
        rows[table]=json.loads(snapshot.query(sql)[0])
    return rows


def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def verify_artifacts(bundle,manifest):
    for name,digest in manifest['artifacts'].items():
        if name not in ('database.dump','uploads.tar') or checksum(bundle/name)!=digest:
            raise RuntimeError('Backup artifact checksum mismatch')


def verify_files(archive,refs,destination):
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:
                raise RuntimeError('Unsafe upload archive member')
        tar.extractall(destination,filter='data')
    for ref in refs:
        relative=Path(ref['relative'])
        if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('Unsafe document manifest path')
        path=destination/relative
        if not path.is_file() or checksum(path)!=ref['sha256']:
            raise RuntimeError('Restored document bytes do not match the database')


def main():
    if os.geteuid()!=0:raise RuntimeError('Run as root on the existing Lighthouse server')
    os.umask(0o077);ROOT.mkdir(parents=True,exist_ok=True);ROOT.chmod(0o700)
    bundle=ROOT/(time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8])
    bundle.mkdir(mode=0o700)
    scratch='mamatch_restore_'+uuid.uuid4().hex[:16]
    source=Snapshot();restored=None;created=False
    started=time.monotonic()
    try:
        production=source.query('SELECT current_database();')[0]
        if scratch==production:raise RuntimeError('Scratch database equals live database')
        snapshot=source.query('SELECT pg_export_snapshot();')[0]
        tables=[json.loads(row) for row in source.query("SELECT to_json(tablename) FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")]
        manifest={'format':1,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),'tables':inventory(source,tables),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        refs=json.loads(source.query("SELECT coalesce(json_agg(json_build_object('path',stored_path,'sha256',sha256)),'[]'::json) FROM documents;")[0])
        with (bundle/'database.dump').open('xb') as output:
            run(db_command('pg_dump',['-Fc','--snapshot='+snapshot]),stdout=output,stderr=subprocess.PIPE)
        # Archive only snapshot-referenced immutable uploads. Copying unrelated/uncommitted uploads is unnecessary.
        with (bundle/'uploads.tar').open('xb') as output:
            run([*COMPOSE,'run','--rm','--no-deps','-T','web','python','-m','mamatch.recovery_files'],input=json.dumps(refs).encode(),stdout=output,stderr=subprocess.PIPE)
        # Paths in the DB use /app/data/uploads; archive names are relative to that configured root.
        root=subprocess.check_output(['docker','exec',WEB,'python','-c','from pathlib import Path;from mamatch import config;print(Path(config.UPLOAD_DIR).resolve())'],text=True).strip().rstrip('/')+'/'
        if any(not r['path'].startswith(root) for r in refs):raise RuntimeError('Document path outside configured uploads')
        manifest['documents']=[{'relative':r['path'].removeprefix(root),'sha256':r['sha256']} for r in refs]
        source.close();source=None
        manifest['artifacts']={name:checksum(bundle/name) for name in ('database.dump','uploads.tar')}
        verify_artifacts(bundle,manifest)
        # Negative check: a corrupt archive must be rejected before any restore is attempted.
        corrupt=bundle/'corruption-check';corrupt.mkdir()
        shutil.copyfile(bundle/'database.dump',corrupt/'database.dump');shutil.copyfile(bundle/'uploads.tar',corrupt/'uploads.tar')
        with (corrupt/'database.dump').open('ab') as stream:stream.write(b'corruption-test')
        try:
            verify_artifacts(corrupt,manifest)
            raise AssertionError('Corrupt backup was accepted')
        except RuntimeError:pass
        shutil.rmtree(corrupt)
        run(db_command('createdb',[scratch]),stdout=subprocess.PIPE,stderr=subprocess.PIPE);created=True
        with (bundle/'database.dump').open('rb') as stream:
            run(db_command('pg_restore',['--exit-on-error','--single-transaction','--no-owner','--no-privileges','-d',scratch]),stdin=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        restored=Snapshot(scratch)
        if inventory(restored,tables)!=manifest['tables']:raise RuntimeError('Restored database content mismatch')
        restored.close();restored=None
        workspace=bundle/'restored-files';workspace.mkdir()
        verify_files(bundle/'uploads.tar',manifest['documents'],workspace)
        shutil.rmtree(workspace)
        probe=run([*COMPOSE,'run','--rm','--no-deps','web','python','-m','mamatch.recovery_probe',scratch],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        manifest['migration_verification']=probe.stdout.decode('utf-8').strip()
        restored=Snapshot(scratch)
        business=[table for table in tables if table!='alembic_version']
        if inventory(restored,business)!={t:manifest['tables'][t] for t in business}:
            raise RuntimeError('Migration changed restored business records')
        restored.close();restored=None
        manifest['result']='passed'
        manifest['checks']=['snapshot_row_counts_and_sha256','archive_sha256','document_sha256','corruption_rejected','isolated_upgrade','constraints','sequences','ddl_rollback','synthetic_file_roundtrip','post_upgrade_data_unchanged']
        manifest['duration_seconds']=round(time.monotonic()-started,2)
        (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(f'Backup/restore rehearsal passed: {len(tables)} tables, {len(refs)} documents; {bundle}')
    except Exception:
        (bundle/'FAILED').write_text('Backup/restore verification did not complete. Do not use this bundle for recovery.\n')
        raise
    finally:
        if source:source.close()
        if restored:restored.close()
        if created:
            # Only this invocation's generated scratch database can ever be removed.
            if not re.fullmatch(r'mamatch_restore_[a-f0-9]{16}',scratch) or scratch==production:raise RuntimeError('Cleanup guard failed')
            run(db_command('dropdb',['--force',scratch]),stdout=subprocess.PIPE,stderr=subprocess.PIPE)


if __name__=='__main__':main()
