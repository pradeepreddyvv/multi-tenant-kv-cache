"""Experimental arrival-based controllers; independent from frozen V1."""
from collections import OrderedDict
from fractions import Fraction
from policy.allocation import equal_allocation, proportional_allocation
from policy.controller import _transfer


class Candidate:
    def __init__(self, name, tenants, budget, unit):
        if budget % unit: raise ValueError('budget must contain whole allocation units')
        self.name,self.tenants,self.unit=name,tuple(tenants),unit
        self.units=budget//unit
        self.quotas=equal_allocation(tenants,self.units)
        self.counts={t:0 for t in tenants};self.demand={t:Fraction(0) for t in tenants}
        self.ghosts={t:OrderedDict() for t in tenants}
        self.n=0;self.last=0.0

    def arrival(self,tenant,prefix):
        ghost=self.ghosts[tenant];seen=prefix in ghost
        ghost[prefix]=None;ghost.move_to_end(prefix)
        if len(ghost)>self.units:ghost.popitem(last=False)
        if self.name=='slow' or seen:self.counts[tenant]+=1
        self.n+=1

    def decide(self,now):
        if now-self.last<30 or self.n<20:return None
        elapsed=now-self.last
        for t in self.tenants:
            # Normalize variable-duration observation windows to arrivals/second.
            self.demand[t]=Fraction(3,10)*Fraction(self.counts[t],1)/Fraction(str(elapsed))+Fraction(7,10)*self.demand[t]
        fraction=Fraction(1,2) if self.name=='v3' else Fraction(1,5)
        floor_units=int(self.units*fraction)
        floors=equal_allocation(self.tenants,floor_units)
        weights=dict(self.demand)
        if self.name=='v3':
            # Fixed equal-share prior in arrivals/second, frozen for this pilot.
            weights={t:v+Fraction(1,20) for t,v in weights.items()}
        extra=proportional_allocation(weights,self.units-floor_units)
        target={t:floors[t]+extra[t] for t in floors}
        movement=sum(max(0,target[t]-self.quotas[t]) for t in target)
        self.counts={t:0 for t in self.tenants};self.n=0;self.last=now
        if movement*20<self.units:return None
        updated,_=_transfer(self.quotas,target,max(1,self.units//10))
        if updated==self.quotas:return None
        self.quotas=updated
        return {t:v*self.unit for t,v in updated.items()}
