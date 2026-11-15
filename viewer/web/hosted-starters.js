/* Metadata-driven shortcuts; adding prepared fields requires no site rebuild. */
(async()=>{
  const panel=document.createElement('section');panel.className='notes';
  const title=document.createElement('h2');title.textContent='Open a prepared 5′ field';
  const note=document.createElement('p');note.textContent='Cached archive IMAGE observations for each target. No new image downloads when opening these links. Different wavelengths are exploratory.';
  const links=document.createElement('div');links.className='controls';
  panel.append(title,note,links);
  try{
    const response=await fetch('/products/starter/index.json',{cache:'no-store'});
    if(!response.ok)return;
    const data=await response.json();
    for(const target of data.targets||[]){
      if(!target.viewer_url)continue;
      const url=new URL(target.viewer_url,location.origin);
      if(url.origin!==location.origin||url.pathname!=='/')continue;
      const link=document.createElement('a');link.href=url.href;link.className='secondary';link.textContent=target.name;links.append(link);
    }
    if(links.childElementCount)document.querySelector('.getting-started').after(panel);
  }catch{}
})();
