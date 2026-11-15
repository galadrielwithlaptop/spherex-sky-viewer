"""Select a bounded sample using saved headers; never fetch pixels or headers here."""
from imaging import wavelength_probe,compatible

def select_candidates(pool,params,limit):
    ordered=sorted(pool,key=lambda r:float(r['t_min']))
    known=[];unknown=[];excluded=[]
    for row in ordered:
        try:known.append((row,wavelength_probe(row,params['ra'],params['dec'],cached_only=True)))
        except FileNotFoundError:unknown.append(row)
        except ValueError as e:excluded.append({'id':row['id'],'reason':str(e)})
    groups=[]
    for pair in known:
        group=next((g for g in groups if all(compatible(pair[1],p[1]) for p in g)),None)
        if group is None:groups.append([pair])
        else:group.append(pair)
    eligible=[g for g in groups if len(g)>1]
    if eligible:
        group=max(eligible,key=lambda g:(float(g[-1][0]['t_min'])-float(g[0][0]['t_min']),len(g)))
        source=[p[0] for p in group]
        method='Matching target wavelengths found in cached headers before time sampling'
    else:
        source=sorted([p[0] for p in known]+unknown,key=lambda r:float(r['t_min']))
        method='No cached matching pair; bounded chronological sample requires header checks'
    n=min(limit,len(source))
    selected=[source[round(i*(len(source)-1)/max(n-1,1))] for i in range(n)]
    return selected,{'pool_records':len(pool),'cached_wavelengths':len(known),'uncached_headers':len(unknown),'excluded':excluded,'selected_candidates':len(selected),'method':method,'network_requests':0}
