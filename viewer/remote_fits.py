"""Read FITS headers and native row strips with bounded HTTP range requests.

Fallback when IRSA cutout workers are unavailable. No full exposure download.
"""
import io, tempfile, subprocess, re, os
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from network import download,CURL

class RemoteFile(io.RawIOBase):
    def __init__(self,url):
        self.url=url; self.pos=0; self.blocks={}
        p=subprocess.run([CURL,'--fail','--silent','--show-error','--head','--max-time','30',url],capture_output=True,text=True,timeout=35,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        sizes=re.findall(r'content-length:\s*(\d+)',p.stdout,re.I)
        if p.returncode or not sizes: raise RuntimeError('Cannot determine remote FITS size')
        self.length=int(sizes[-1])
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        if whence==0: self.pos=offset
        elif whence==1: self.pos+=offset
        else: self.pos=self.length+offset
        return self.pos
    def read(self,size=-1):
        if size<0 or size>24*1024*1024: raise OSError('Unbounded remote FITS read refused')
        if size>4*1024*1024:
            pieces=[]
            while size:
                n=min(size,4*1024*1024);pieces.append(self.read(n));size-=n
            return b''.join(pieces)
        if not size: return b''
        if self.pos>=self.length:return b''
        size=min(size,self.length-self.pos)
        start=self.pos; self.pos+=size
        # Header-sized reads share a FITS-block aligned cache.
        if size<=2880:
            block=32*2880
            base=(start//block)*block
            n=min(self.length-base,max(block,((start+size-base+block-1)//block)*block))
            key=(base,n)
        else: base,n=start,size; key=(base,n)
        if key not in self.blocks:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'range'
                download(self.url,p,max_bytes=n+2880,byte_range=(base,base+n-1))
                self.blocks[key]=p.read_bytes()
        return self.blocks[key][start-base:start-base+size]

def extract(url,ra,dec,fov,path,image_only=False):
    stream=RemoteFile(url)
    with fits.open(stream,memmap=False,lazy_load_hdus=True) as hdus:
        image=hdus['IMAGE']; wcs=WCS(image.header,naxis=2)
        x,y=wcs.all_world2pix(ra,dec,0)
        if not np.isfinite([x,y]).all(): raise ValueError('Position cannot be projected')
        # Full rows are fetched in one contiguous span per image layer.
        half=int(np.ceil(fov*60/6.15*0.75))+5
        nx,ny=image.header['NAXIS1'],image.header['NAXIS2']
        x0,x1=max(0,int(x)-half),min(nx,int(x)+half+1)
        y0,y1=max(0,int(y)-half),min(ny,int(y)+half+1)
        if x0>=x1 or y0>=y1: raise ValueError('Target outside native image')
        out=[fits.PrimaryHDU(header=hdus[0].header)]
        for name in (['IMAGE'] if image_only else ['IMAGE','FLAGS','VARIANCE','ZODI']):
            h=hdus[name]; header=h.header.copy(); bitpix=header['BITPIX']
            if isinstance(h,fits.CompImageHDU):
                # Compressed mask bytes cannot be interpreted as raw int32 pixels.
                # Fetch the encoded extension in contiguous chunks, then decode
                # locally. Remote tile-by-tile decompression is prohibitively slow.
                info=h.fileinfo();stream.seek(info['hdrLoc'])
                encoded=stream.read(info['datLoc']-info['hdrLoc']+info['datSpan'])
                buffer=io.BytesIO();fits.PrimaryHDU().writeto(buffer)
                buffer.seek(0,2);buffer.write(encoded);buffer.seek(0)
                with fits.open(buffer,memmap=False) as local:
                    data=np.asarray(local[1].data[y0:y1,x0:x1],dtype=np.float64).copy()
            else:
                dtype={-32:'>f4',-64:'>f8',16:'>i2',32:'>i4',64:'>i8',8:'u1'}[bitpix]
                offset=h.fileinfo()['datLoc']+y0*nx*(abs(bitpix)//8)
                stream.seek(offset); raw=stream.read((y1-y0)*nx*(abs(bitpix)//8))
                data=np.frombuffer(raw,dtype=dtype).reshape(y1-y0,nx)[:,x0:x1].copy()
                data=data.astype(np.float64)*header.get('BSCALE',1)+header.get('BZERO',0)
            for key in ['BSCALE','BZERO','BLANK']:
                header.remove(key,ignore_missing=True)
            # Preserve SIP and shift all pixel-reference systems.
            for key in list(header):
                if key.startswith('CRPIX1'): header[key]-=x0
                if key.startswith('CRPIX2'): header[key]-=y0
            header['ORIGX0']=x0; header['ORIGY0']=y0
            out.append(fits.ImageHDU(data=data,header=header,name=name))
        if not image_only:
            wave=hdus['WCS-WAVE'].copy()
            # Wavelength grid remains native; original pixel offsets retained above.
            out.append(wave)
        fits.HDUList(out).writeto(path,overwrite=True)
