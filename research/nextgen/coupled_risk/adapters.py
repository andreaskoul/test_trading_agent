"""Independent strict, offline readers for the existing riskfield and MASTER dev NPZ schema."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from .models import pdmat

END=np.datetime64('2019-12-31','D')

@dataclass(frozen=True)
class Risk:
    dates:np.ndarray
    names:np.ndarray
    intraday:np.ndarray
    daily:np.ndarray
    sha256:str
    survivorship:str='UNVERIFIED_CURRENT_CONSTITUENTS'

@dataclass(frozen=True)
class Alpha:
    dates:np.ndarray
    names:np.ndarray
    score:np.ndarray
    eligible:np.ndarray
    sha256:str

@dataclass
class Factors:
    loading:np.ndarray
    factor:np.ndarray
    resid:np.ndarray
    stocks:np.ndarray
    n_dropped:int


def hashfile(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def dates_ok(x):
    d=np.asarray(x).astype('datetime64[D]')
    if d.ndim!=1 or len(d)<100 or np.isnat(d).any() or not np.all(d[1:]>d[:-1]):
        raise ValueError('invalid dates')
    return d


def names_ok(x):
    a=np.asarray([str(v) for v in x])
    if len(a)!=len(set(a)) or not set(a):raise ValueError('duplicate/empty names')
    return a


def load_risk(path,dev_only=True,n_names=None):
    p=Path(path)
    if not p.is_file():raise FileNotFoundError(p)
    with np.load(p,allow_pickle=False) as z:
        if not {'S','names','R','rv'}<=set(z.files):raise ValueError('missing risk columns')
        d=dates_ok(z['S']); names=names_ok(z['names']); R=np.asarray(z['R'],float);rv=np.asarray(z['rv'],float)
    if R.shape!=(len(d),14,len(names)) or rv.shape!=(len(d),len(names)) or 'SPY' not in names:
        raise ValueError('riskfield schema mismatch')
    if dev_only:
        m=d<=END;d,R,rv=d[m],R[m],rv[m]
    if n_names:
        si=int(np.flatnonzero(names=='SPY')[0]); idx=[si]+[i for i,v in enumerate(names) if i!=si][:n_names-1]
        names,R,rv=names[idx],R[:,:,idx],rv[:,idx]
    if len(d)<252 or np.nanmin(rv)<0:raise ValueError('invalid risk history')
    si=int(np.flatnonzero(names=='SPY')[0]);coverage=np.isfinite(R[:,:,si]).all(1).mean()
    if coverage<.85:raise ValueError('SPY intraday coverage too low')
    daily=np.where(np.isfinite(R).all(1),R.sum(1),np.nan)
    return Risk(d,names,R,daily,hashfile(p))


def load_alpha(path,dev_only=True):
    p=Path(path)
    if not p.is_file():raise FileNotFoundError(p)
    with np.load(p,allow_pickle=False) as z:
        if not {'S','names','master_h5_ref','elig'}<=set(z.files):raise ValueError('missing alpha columns')
        d=dates_ok(z['S']); names=names_ok(z['names']); score=np.asarray(z['master_h5_ref'],float);e=np.asarray(z['elig'])
    if dev_only and d[-1]>END:raise ValueError('alpha dev cache includes reused post-2019 rows')
    if score.shape!=(len(d),len(names)) or e.shape!=score.shape or e.dtype.kind not in 'biu':
        raise ValueError('alpha schema mismatch')
    return Alpha(d,names,score,e.astype(bool),hashfile(p))


def factor_window(d,origin,lookback=252,factors=3,mincoverage=.95):
    if origin<lookback or origin>=len(d.dates):raise ValueError('origin outside window')
    raw=d.daily[origin-lookback:origin];z=d.intraday[origin-lookback:origin]
    cov=np.isfinite(raw).mean(0)>=mincoverage
    cov &=np.isfinite(z).all(1).mean(0)>=mincoverage
    idx=np.flatnonzero(cov)
    if 'SPY' not in d.names[idx] or len(idx)<factors+2:raise ValueError('insufficient PIT intraday coverage')
    x=raw[:,idx].copy();inp=z[:,:,idx]
    means=np.nanmean(x,axis=0)
    x=np.where(np.isfinite(x),x,means);x-=x.mean(0)
    _,_,vt=np.linalg.svd(x,full_matrices=False)
    L=vt[:factors].T
    f=x@L;resid=x-f@L.T
    return Factors(L,f,resid,idx,len(d.names)-len(idx))


def poe_residual(e,threshold=1.5):
    x=np.asarray(e,float)
    if x.ndim!=2 or len(x)<30 or not np.isfinite(x).all():raise ValueError('invalid residual matrix')
    n=len(x);cov=np.cov(x,rowvar=False)
    diag=np.maximum(np.diag(cov),1e-9);scale=np.sqrt(np.outer(diag,diag))
    cut=threshold*np.sqrt(np.log(x.shape[1])/n)*scale
    out=np.sign(cov)*np.maximum(np.abs(cov)-cut,0)
    np.fill_diagonal(out,diag)
    return pdmat(out)


def qlike(real,pred):
    if not(real>0 and pred>0 and np.isfinite(real+pred)):raise ValueError('invalid target/forecast')
    x=real/pred
    return float(x-np.log(x)-1)


def safe_new_dir(target,inputs):
    p=Path(target).expanduser().resolve()
    if p.exists():raise FileExistsError(p)
    for v in inputs:
        q=Path(v).expanduser().resolve()
        if p==q or p in q.parents or q in p.parents:raise ValueError('output collides with protected input/root')
    p.mkdir(parents=True,exist_ok=False)
    return p


def write_json(folder,name,data):
    if name!='RESULT.json':raise ValueError('unapproved output name')
    (folder/name).write_text(json.dumps(data,indent=2,allow_nan=False,default=lambda x:float(x) if isinstance(x,np.floating) else str(x))+'\n')
