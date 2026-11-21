"""Numerically controlled geometry of SPD(k), Gr(k,n) and diffusion manifolds.

All matrix functions use symmetric eigendecompositions. AIRM is congruence-invariant;
Log-Euclidean is not. The Gaussian kernel is applied ONLY to Log-Euclidean
coordinates, for which positive semidefiniteness is guaranteed.
"""
from __future__ import annotations
import numpy as np
from scipy.linalg import orthogonal_procrustes


def sym(a):
    x=np.asarray(a,dtype=float)
    if x.ndim!=2 or x.shape[0]!=x.shape[1] or not np.isfinite(x).all():
        raise ValueError('expected finite square matrix')
    return (x+x.T)/2


def spd(a,floor=1e-9):
    if not 0<floor<1:raise ValueError('invalid SPD eigen floor')
    x=sym(a)
    e,v=np.linalg.eigh(x)
    return sym((v*np.maximum(e,floor))@v.T)


def matrix_power(a,p,floor=1e-9):
    x=spd(a,floor)
    e,v=np.linalg.eigh(x)
    return sym((v*(e**p))@v.T)


def logm(a,floor=1e-9):
    e,v=np.linalg.eigh(spd(a,floor))
    return sym((v*np.log(e))@v.T)


def expm(a):
    e,v=np.linalg.eigh(sym(a))
    if e.max()>700:raise ValueError('matrix exponential overflow')
    return sym((v*np.exp(e))@v.T)


def logeuclidean_distance(a,b):
    return float(np.linalg.norm(logm(a)-logm(b),'fro'))


def affine_distance(a,b):
    s=matrix_power(a,-.5)
    return float(np.linalg.norm(logm(s@spd(b)@s),'fro'))


def bures_distance(a,b):
    # Tr(A+B-2(A^.5 B A^.5)^.5); guard cancellation near equality.
    x,y=spd(a),spd(b)
    s=matrix_power(x,.5)
    sq=matrix_power(s@y@s,.5)
    return float(np.sqrt(max(0,np.trace(x)+np.trace(y)-2*np.trace(sq))))


def logeuclidean_geodesic(a,b,t):
    if not 0<=t<=1:raise ValueError('interpolation requires t in [0,1]')
    return spd(expm((1-t)*logm(a)+t*logm(b)))


def affine_geodesic(a,b,t):
    if not 0<=t<=1:raise ValueError('interpolation requires t in [0,1]')
    s=matrix_power(a,.5); si=matrix_power(a,-.5)
    return spd(s@matrix_power(si@spd(b)@si,t)@s)


def bures_geodesic(a,b,t):
    if not 0<=t<=1:raise ValueError('interpolation requires t in [0,1]')
    x,y=spd(a),spd(b)
    s=matrix_power(x,.5);si=matrix_power(x,-.5)
    transport=si@matrix_power(s@y@s,.5)@si
    u=(1-t)*np.eye(len(x))+t*transport
    return spd(u@x@u)


def frechet_mean(matrices,metric='logeuclidean',weights=None,maxiter=120,tol=1e-9):
    a=np.asarray(matrices,float)
    if a.ndim!=3 or a.shape[1]!=a.shape[2] or len(a)<2:raise ValueError('mean requires 2+ SPD matrices')
    n=len(a)
    w=np.ones(n)/n if weights is None else np.asarray(weights,float)
    if w.shape!=(n,) or (w<0).any() or w.sum()<=0:raise ValueError('invalid weights')
    w=w/w.sum();a=np.stack([spd(x) for x in a])
    if metric=='logeuclidean':return expm(np.einsum('n,nij->ij',w,np.stack([logm(x) for x in a])))
    if metric not in ('affine','bures'):raise ValueError('unknown metric')
    m=frechet_mean(a,'logeuclidean',w)
    if metric=='affine':
        # Weighted Karcher mean by intrinsic Riemannian fixed-point descent.
        for it in range(maxiter):
            h=matrix_power(m,.5);hi=matrix_power(m,-.5)
            velocity=sum(wj*logm(hi@aj@hi) for wj,aj in zip(w,a))
            if np.linalg.norm(velocity,'fro')<tol:return spd(m)
            proposal=spd(h@expm(.7*velocity)@h)
            if not np.isfinite(proposal).all():raise RuntimeError('AIRM centroid diverged')
            m=proposal
        if np.linalg.norm(sum(wj*logm(matrix_power(m,-.5)@aj@matrix_power(m,-.5)) for wj,aj in zip(w,a)),'fro')>1e-5:
            raise RuntimeError('affine Fréchet mean nonconvergent')
        return spd(m)
    # Bures-Wasserstein barycenter fixed-point update (Gaussian OT).
    for it in range(maxiter):
        h=matrix_power(m,.5);hi=matrix_power(m,-.5)
        su=sum(wj*matrix_power(h@aj@h,.5) for wj,aj in zip(w,a))
        nxt=spd(hi@su@su@hi)
        rel=np.linalg.norm(nxt-m,'fro')/max(np.linalg.norm(m,'fro'),1e-12)
        m=nxt
        if rel<tol:return m
    raise RuntimeError('Bures barycenter nonconvergent')


def tangent_vector(a):
    """svec(log(A)): Frobenius inner product is preserved via sqrt(2) off-diagonals."""
    x=logm(a);idx=np.triu_indices(len(x))
    y=x[idx];y=y*np.where(idx[0]!=idx[1],np.sqrt(2),1)
    return y


def ortho_columns(x):
    a=np.asarray(x,float)
    if a.ndim!=2 or a.shape[0]<a.shape[1] or not np.isfinite(a).all():raise ValueError('invalid basis')
    q,r=np.linalg.qr(a,mode='reduced')
    if np.linalg.matrix_rank(r)<a.shape[1]:raise ValueError('rank deficient factor subspace')
    return q


def grassmann_distance(u,v,metric='geodesic'):
    a,b=ortho_columns(u),ortho_columns(v)
    if a.shape!=b.shape:raise ValueError('subspaces must have same n and k')
    sv=np.clip(np.linalg.svd(a.T@b,compute_uv=False),0,1)
    angles=np.arccos(sv)
    if metric=='geodesic':return float(np.linalg.norm(angles))
    if metric=='chordal':return float(np.linalg.norm(np.sin(angles)))
    raise ValueError('unknown Grassmann metric')


def grassmann_rotation(u,v):
    a,b=ortho_columns(u),ortho_columns(v)
    return orthogonal_procrustes(b,a)[0]


def grassmann_features(bases):
    a=list(bases)
    return np.array([grassmann_distance(a[i-1],a[i]) for i in range(1,len(a))])


def rbf_kernel_logspd(matrices1,matrices2=None,bandwidth=None):
    """Mercer RBF in the symmetric matrix-log Hilbert space, unlike general AIRM RBF."""
    a=np.stack([tangent_vector(x) for x in matrices1]);b=a if matrices2 is None else np.stack([tangent_vector(x) for x in matrices2])
    d2=np.maximum(0,(a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T)
    if bandwidth is None:
        upper=d2[np.triu_indices(len(a),1)]
        positive=upper[upper>1e-12]
        bandwidth=float(np.sqrt(np.median(positive)/2)) if len(positive) else 1.
    if not (np.isfinite(bandwidth) and bandwidth>0):raise ValueError('invalid RBF bandwidth')
    return np.exp(-d2/(2*bandwidth*bandwidth)),float(bandwidth)


class DiffusionMap:
    """Coifman-Lafon density-corrected diffusion map, honest Nyström inductive map.

    Train on earlier SPD observations only; no refit or retrospective embeddings
    after validation begins. Eigenvalue for Nyström extension is the Markov one.
    """
    def __init__(self,dimension=3,alpha=1.0,time=1,bandwidth=None):
        if dimension<1 or not 0<=alpha<=1 or time<1:raise ValueError('invalid diffusion parameters')
        self.dimension,self.alpha,self.time,self.bandwidth=dimension,alpha,time,bandwidth

    def fit(self,matrices):
        m=np.asarray(matrices,float)
        if m.ndim!=3 or len(m)<max(12,self.dimension+2):raise ValueError('insufficient SPD observations')
        self.train=np.stack([spd(x) for x in m])
        k,self.bandwidth=rbf_kernel_logspd(self.train,bandwidth=self.bandwidth)
        q=np.maximum(k.sum(1),1e-15)
        weighted=k/(q[:,None]**self.alpha*q[None,:]**self.alpha)
        degree=np.maximum(weighted.sum(1),1e-15)
        e,v=np.linalg.eigh((weighted/np.sqrt(degree[:,None]*degree[None,:])+weighted.T/np.sqrt(degree[None,:]*degree[:,None]))/2)
        ids=np.argsort(e)[::-1]
        eig=e[ids][1:self.dimension+1]
        if np.any(np.abs(eig)<1e-9):raise ValueError('embedding has degenerate eigenvalues')
        self.eigenvalues=eig
        u=v[:,ids][:,1:self.dimension+1]
        phi=u/np.sqrt(degree[:,None])
        # Canonical scale and orientation fixed on *training* data only.
        phi/=np.maximum(np.sqrt((phi*phi).mean(0)),1e-12)
        for j in range(phi.shape[1]):
            if phi[np.argmax(np.abs(phi[:,j])),j]<0:phi[:,j]*=-1
        self.phi=phi
        self.q=q
        self.degree=degree
        self.embedding=phi*self.eigenvalues[None,:]**self.time
        return self

    def transform(self,matrices):
        if not hasattr(self,'train'):raise ValueError('fit first')
        k,_=rbf_kernel_logspd(matrices,self.train,bandwidth=self.bandwidth)
        q=np.maximum(k.sum(1),1e-15)
        corrected=k/(q[:,None]**self.alpha*self.q[None,:]**self.alpha)
        p=corrected/np.maximum(corrected.sum(1,keepdims=True),1e-15)
        eigenphi=(p@self.phi)/self.eigenvalues[None,:]
        return eigenphi*self.eigenvalues[None,:]**self.time

    def fit_transform(self,matrices):return self.fit(matrices).embedding


def probability_root(p):
    """Categorical Fisher-Rao sphere map p -> sqrt(p) (radius-one chart)."""
    a=np.asarray(p,float)
    if a.ndim not in (1,2) or not np.isfinite(a).all() or (a<0).any() or (a.sum(axis=-1)<=0).any():
        raise ValueError('probabilities need nonnegative finite simplex coordinates')
    return np.sqrt(a/a.sum(axis=-1,keepdims=True))


def fisher_rao_distance(p,q):
    """Fisher-Rao geodesic distance = 2 arccos(sum_k sqrt(p_k q_k))."""
    a,b=probability_root(p),probability_root(q)
    if a.ndim!=1 or b.ndim!=1 or a.shape!=b.shape:raise ValueError('two equal simplexes required')
    return float(2*np.arccos(np.clip(a@b,0,1)))


def probability_hellinger_kernel(p,q=None,bandwidth=.5):
    """PSD Gaussian kernel in Euclidean sqrt-probability coordinates.

    A Gaussian of the squared Fisher geodesic distance is *not* guaranteed to
    be a Mercer kernel on the sphere; the Hellinger chordal one is.
    """
    x=probability_root(p)
    if x.ndim==1:x=x[None,:]
    y=x if q is None else probability_root(q)
    if y.ndim==1:y=y[None,:]
    if x.shape[1]!=y.shape[1] or bandwidth<=0:raise ValueError('probability kernel dimensions')
    d2=np.maximum(0,(x*x).sum(1)[:,None]+(y*y).sum(1)[None,:]-2*x@y.T)
    return np.exp(-d2/(2*bandwidth**2))
