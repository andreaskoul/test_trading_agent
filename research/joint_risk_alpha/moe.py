"""Torch conditional MASTER efficacy mixture-of-experts, genuinely nonlinear.

No new stock-selection alpha is injected: prediction is restricted to a
state-dependent calibration of the existing frozen MASTER rank score.
Train/validation grouping is chronological by DATE, not randomly by stock.
Labels are five-session forward results available only after a six-session
maturity/entry delay; training rows are purged accordingly.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


def _torch():
    try:import torch
    except ImportError as e:raise RuntimeError('Install torch to run the nonlinear MoE track') from e
    return torch

class ConditionalMoE:
    def __init__(self,environment_dim,character_dim,experts=3,hidden=64,dropout=.15):
        torch=_torch()
        self.torch=torch
        nn=torch.nn
        if experts<2 or experts>8:raise ValueError('experts must be 2..8')
        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.gate=nn.Sequential(nn.Linear(environment_dim,hidden),nn.GELU(),nn.Linear(hidden,experts))
                self.experts=nn.ModuleList([nn.Sequential(nn.Linear(character_dim+1,hidden),nn.GELU(),
                       nn.Dropout(dropout),nn.Linear(hidden,hidden//2),nn.GELU(),nn.Linear(hidden//2,1))
                       for _ in range(experts)])
                self.reference=nn.Linear(1,1,bias=False)
            def forward(self,s,z,e):
                probs=torch.softmax(self.gate(e),-1)
                u=torch.cat([s,z],-1)
                conditional=torch.cat([net(u) for net in self.experts],-1)
                # Preserve original score sign/scale as the input. Residual calibration
                # cannot be interpreted as an independent new signal.
                result=self.reference(s)+(probs*conditional).sum(-1,keepdim=True)*s
                return result,probs
        self.net=Net()

    def fit(self,score,character,environment,target,week_index,train_mask,val_mask,
            epochs=250,lr=2e-3,weight_decay=.01,batch_weeks=16,patience=25,
            seed=20261121,device='cpu',n_threads=2):
        """Fit on completed labels, with validation strictly AFTER train origins.

        Inputs are per name: score (n,1), chars (n,p), market info (n,e).
        week_index contains decision session integer; val week first > train last+6.
        Caller is responsible for precomputed time-causal features and train-only
        feature standardisation, which is implemented here.
        """
        torch=self.torch
        torch.manual_seed(seed);torch.set_num_threads(n_threads)
        score=np.asarray(score,float).reshape(-1,1);character=np.asarray(character,float)
        environment=np.asarray(environment,float);target=np.asarray(target,float).reshape(-1,1)
        week_index=np.asarray(week_index,int)
        a=np.asarray(train_mask,bool);b=np.asarray(val_mask,bool)
        if np.any(a&b) or not a.any() or not b.any():raise ValueError('train/validation disjoint nonempty')
        if week_index[a].max()+6>=week_index[b].min():raise ValueError('labels are not mature before validation')
        X=np.hstack([score,character,environment,target]);ok=np.isfinite(X).all(1)
        a&=ok;b&=ok
        if a.sum()<3000 or b.sum()<300:raise ValueError('too few PIT labels')
        norm=[]
        for x in (character,environment):
            mu=x[a].mean(0);sd=np.maximum(x[a].std(0),1e-4)
            norm.append((mu,sd))
        self.scaling=norm
        char=(character-norm[0][0])/norm[0][1];env=(environment-norm[1][0])/norm[1][1]
        arrays=[score,char,env,target]
        T=[torch.tensor(k,dtype=torch.float32,device=device) for k in arrays]
        self.net.to(device)
        optimizer=torch.optim.AdamW(self.net.parameters(),lr=lr,weight_decay=weight_decay)
        tr_weeks=np.unique(week_index[a]);rng=np.random.default_rng(seed)
        best=float('inf');params=None;stale=0;history=[]
        for epoch in range(epochs):
            self.net.train();rng.shuffle(tr_weeks)
            for w0 in range(0,len(tr_weeks),batch_weeks):
                ix=np.flatnonzero(a&np.isin(week_index,tr_weeks[w0:w0+batch_weeks]))
                if not len(ix):continue
                pred,gate=self.net(*(t[ix] for t in T[:3]))
                # Weight each week equally, not each security independently.
                counts={int(k):int(np.sum(week_index[ix]==k)) for k in np.unique(week_index[ix])}
                weights=torch.tensor([1/counts[int(week_index[i])] for i in ix],device=device)
                weights=weights/weights.sum()
                err=(pred-T[3][ix]).square().ravel()
                loss=(err*weights).sum()+.0001*(gate*torch.log(gate+1e-9)).sum()/len(ix)
                optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(self.net.parameters(),2.0);optimizer.step()
            self.net.eval()
            with torch.no_grad():
                ix=np.flatnonzero(b)
                p,_=self.net(*(t[ix] for t in T[:3]))
                err=(p-T[3][ix]).square().ravel().cpu().numpy()
                # Time-block validation: mean of per-week MSEs.
                score_val=float(np.mean([err[week_index[ix]==k].mean() for k in np.unique(week_index[ix])]))
            history.append(score_val)
            if score_val<best-1e-9:
                best=score_val;params={k:v.detach().cpu().clone() for k,v in self.net.state_dict().items()};stale=0
            else:stale+=1
            if stale>=patience:break
        self.net.load_state_dict(params)
        return {'best_validation_mse':best,'epochs_run':len(history),'last_validation_mse':history[-1],
                'n_train':int(a.sum()),'n_val':int(b.sum()),'n_train_weeks':len(np.unique(week_index[a]))}

    def predict(self,score,character,environment,mc_dropout=20,device='cpu',seed=20261121):
        torch=self.torch
        score=np.asarray(score,float).reshape(-1,1)
        z=np.asarray(character,float);e=np.asarray(environment,float)
        z=(z-self.scaling[0][0])/self.scaling[0][1];e=(e-self.scaling[1][0])/self.scaling[1][1]
        arrays=[torch.tensor(x,dtype=torch.float32,device=device) for x in (score,z,e)]
        self.net.to(device)
        samples=[];gate=[]
        for i in range(mc_dropout):
            torch.manual_seed(seed+i);self.net.train() # MC dropout for parameter uncertainty proxy
            with torch.no_grad():
                mu,pi=self.net(*arrays)
                samples.append(mu.cpu().numpy().ravel());gate.append(pi.cpu().numpy())
        return {'mean':np.mean(samples,axis=0),'std':np.std(samples,axis=0),
                'state_prob':np.mean(gate,axis=0)}
