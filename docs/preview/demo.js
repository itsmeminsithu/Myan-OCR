// Myan OCR static demo — Tesseract.js in the browser. No uploads, no server.
(function(){
  var file=null, status=document.getElementById('status'), scanBtn=document.getElementById('scanBtn'),
      out=document.getElementById('outText'), img=document.getElementById('previewImg'),
      input=document.getElementById('fileInput'), conf=document.getElementById('conf');
  function setFile(f, url){
    file=f||url; scanBtn.disabled=false;
    img.src=url||URL.createObjectURL(f); img.hidden=false;
    status.textContent='Image ready. Tap "Recognize text".';
  }
  document.getElementById('browseBtn').addEventListener('click',function(){ input.click(); });
  input.addEventListener('change',function(){ if(input.files[0]) setFile(input.files[0]); });
  document.getElementById('sampleBtn').addEventListener('click',function(){ setFile(null,'sample.png'); });
  var dz=document.querySelector('.demo-drop');
  dz.addEventListener('dragover',function(e){ e.preventDefault(); });
  dz.addEventListener('drop',function(e){ e.preventDefault(); var f=e.dataTransfer.files[0]; if(f) setFile(f); });
  scanBtn.addEventListener('click', async function(){
    if(!file) return;
    scanBtn.disabled=true; conf.textContent=''; out.value='';
    var lang=document.getElementById('langSel').value;
    try{
      status.textContent='Loading OCR engine (first run downloads the language data)…';
      var worker=await Tesseract.createWorker(lang, 1, {
        logger: function(m){ if(m.status) status.textContent=m.status+' '+Math.round((m.progress||0)*100)+'%'; }
      });
      status.textContent='Recognizing…';
      var res=await worker.recognize(file);
      await worker.terminate();
      out.value=(res.data.text||'').trim();
      conf.textContent='Confidence signal: '+Math.round(res.data.confidence)+'% — a signal, not a guarantee. Please review the text.';
      status.textContent=out.value?'Done — review the text against your image.':'No text detected. Try a clearer, brighter image.';
    }catch(e){
      status.textContent='OCR failed in this browser: '+(e.message||e);
    }
    scanBtn.disabled=false;
  });
  document.getElementById('copyBtn').addEventListener('click',function(){
    out.select(); navigator.clipboard&&navigator.clipboard.writeText(out.value);
    status.textContent='Text copied.';
  });
  document.getElementById('dlBtn').addEventListener('click',function(){
    var a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob([out.value],{type:'text/plain'}));
    a.download='myan-ocr-text.txt'; a.click();
  });
})();
