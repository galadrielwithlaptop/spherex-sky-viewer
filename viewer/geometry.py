"""Spherical metadata-footprint matching, independent of image downloads.

SPHEREx polygons are treated as short great-circle arcs, as encoded in S_REGION.
Unsupported shapes remain conservative candidates, never false no-coverage claims.
"""
import math
import re

RAD=math.pi/180
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a):return math.sqrt(dot(a,a))
def unit(a):
    n=norm(a)
    if n<1e-14:raise ValueError('Degenerate spherical vector')
    return tuple(x/n for x in a)
def vector(ra,dec):
    ra,dec=float(ra)*RAD,float(dec)*RAD
    return (math.cos(dec)*math.cos(ra),math.cos(dec)*math.sin(ra),math.sin(dec))
def angle(a,b):return math.atan2(norm(cross(a,b)),max(-1,min(1,dot(a,b))))
def cap_bounds(center,radius):
    chord=2*math.sin(min(math.pi,radius)/2)
    return tuple(v for x in center for v in (max(-1,x-chord),min(1,x+chord)))
def on_arc(a,b,q):return angle(a,q)+angle(q,b)<=angle(a,b)+1e-9

def footprint(region):
    try:
        tokens=re.split(r'\s+',region.strip());kind=tokens.pop(0).upper()
        if tokens and tokens[0].upper() in ('ICRS','FK5','J2000'):tokens.pop(0)
        nums=list(map(float,tokens))
        if not all(map(math.isfinite,nums)):raise ValueError('Nonfinite footprint')
        if kind=='CIRCLE' and len(nums)==3 and -90<=nums[1]<=90 and 0<=nums[2]<=180:
            center=vector(*nums[:2]);radius=nums[2]*RAD
            return {'kind':'circle','center':center,'radius':radius,'supported':True}
        if kind!='POLYGON' or len(nums)<6 or len(nums)%2:raise ValueError('Unsupported footprint')
        if any(not -90<=x<=90 for x in nums[1::2]):raise ValueError('Invalid declination')
        points=[vector(*nums[i:i+2]) for i in range(0,len(nums),2)]
        if angle(points[0],points[-1])<1e-10:points.pop()
        center=unit(tuple(sum(p[i] for p in points) for i in range(3)))
        radius=max(angle(center,p) for p in points)
        if radius>=math.pi/2:raise ValueError('Nonlocal polygon')
        edges=[]
        for a,b in zip(points,points[1:]+points[:1]):
            n=unit(cross(a,b));n=tuple(x*(1 if dot(n,center)>=0 else -1) for x in n)
            if any(dot(n,p)<-1e-9 for p in points):raise ValueError('Nonconvex polygon')
            edges.append(n)
        return {'kind':'polygon','center':center,'radius':radius,'points':points,'edges':edges,'supported':True}
    except (ValueError,TypeError,AttributeError):return {'kind':'unknown','center':(0,0,1),'radius':math.pi,'supported':False}

def intersects(shape,center,radius):
    if not shape['supported']:return True
    if angle(shape['center'],center)>shape['radius']+radius+1e-9:return False
    if shape['kind']=='circle':return True
    if all(dot(n,center)>=-1e-10 for n in shape['edges']):return True
    points=shape['points']
    if any(angle(center,p)<=radius+1e-10 for p in points):return True
    for a,b,n in zip(points,points[1:]+points[:1],shape['edges']):
        projection=tuple(p-dot(center,n)*v for p,v in zip(center,n))
        if norm(projection)<1e-12:continue
        q=unit(projection)
        if on_arc(a,b,q) and angle(center,q)<=radius+1e-10:return True
    return False
