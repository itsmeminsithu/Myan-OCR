/* Myan OCR v0.1.3 — client-side camera, image preview, edits and export. */
'use strict';
const el = id => document.getElementById(id);
const state = {file:null, objectUrl:null, result:null, camera:null, config:null, busy:false, toastTimeout:null, locale:'en',cropping:false,cropStart:null,cropRect:null};
const MAX_UPLOAD = 12*1024*1024;
const HISTORY_KEY='myanocr-v012-text-history';
let currentPdf=null;
let batchFiles=[];

function toast(message){const box=el('toast');box.textContent=message;box.classList.add('visible');clearTimeout(state.toastTimeout);state.toastTimeout=setTimeout(()=>box.classList.remove('visible'),2800)}
function error(id,message){const box=el(id);box.textContent=message;box.hidden=!message}
function markBusy(active){state.busy=active;el('scanButton').disabled=active||!(state.file||currentPdf||batchFiles.length);el('scanButtonLabel').textContent=active?'Recognizing…':'Recognize text';el('translateButton').disabled=active}
async function checkHealth(){try{const response=await fetch('/api/health',{cache:'no-store'});if(!response.ok)throw Error('Server unavailable');const cfg=await response.json();state.config=cfg;el('engineStatus').textContent=cfg.ocr_available?'Local OCR ready':'OCR models missing';if(cfg.ocr_available)el('statusPill').classList.add('ready');el('translationHint').textContent=cfg.translation_configured?(cfg.translation_provider==='ollama'?'Local Ollama translation configured (not tested). Results need review.':'Google translation configured (not tested). Text is sent to Google only when you tap Translate.'):'Translation needs an optional Ollama model or Google Cloud credentials. OCR and text editing work without them.';if(!cfg.cloud_ocr_configured){el('ocrEngine').options[1].disabled=true;el('ocrEngine').options[1].textContent='Google Cloud Vision (setup required)'}}catch(e){el('engineStatus').textContent='Backend offline';error('scanError','Could not connect to OCR backend. Start the server and reload.')}}
function resetCrop(){state.cropping=false;state.cropStart=null;state.cropRect=null;const sel=el('cropSelection');if(sel)sel.hidden=true;const stage=el('imageStage');if(stage)stage.classList.remove('crop-mode');if(el('applyCrop'))el('applyCrop').hidden=true;if(el('cancelCrop'))el('cancelCrop').hidden=true}
function enableCrop(){if(!state.file||state.busy)return;resetCrop();clearOCR();state.cropping=true;el('imageStage').classList.add('crop-mode');el('applyCrop').hidden=false;el('cancelCrop').hidden=false;toast('Drag across the image to select the text area')}
function cropPoint(e){const b=el('previewImg').getBoundingClientRect();if(!b.width||!b.height)throw Error('Image preview not ready');return {x:Math.max(0,Math.min(1,(e.clientX-b.left)/b.width)),y:Math.max(0,Math.min(1,(e.clientY-b.top)/b.height))}}
function drawCropRect(){const r=state.cropRect;if(!r)return;const box=el('cropSelection');box.hidden=false;const im=el('previewImg').getBoundingClientRect(),stage=el('imageStage').getBoundingClientRect();box.style.left=(im.left-stage.left+r.x*im.width)+'px';box.style.top=(im.top-stage.top+r.y*im.height)+'px';box.style.width=(r.width*im.width)+'px';box.style.height=(r.height*im.height)+'px'}
function cropDown(e){if(!state.cropping||e.button!==0)return;e.preventDefault();const point=cropPoint(e);state.cropStart=point;state.cropRect={x:point.x,y:point.y,width:0,height:0};el('imageStage').setPointerCapture(e.pointerId);drawCropRect()}
function cropMove(e){if(!state.cropping||!state.cropStart)return;const now=cropPoint(e),start=state.cropStart;state.cropRect={x:Math.min(start.x,now.x),y:Math.min(start.y,now.y),width:Math.abs(start.x-now.x),height:Math.abs(start.y-now.y)};drawCropRect()}
function cropEnd(){state.cropStart=null}
async function applyCrop(){const r=state.cropRect;if(!state.file||!r||r.width<0.02||r.height<0.02){toast('Select a larger area of the image');return}try{const img=new Image(),source=URL.createObjectURL(state.file);try{await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=source});const sx=Math.floor(r.x*img.naturalWidth),sy=Math.floor(r.y*img.naturalHeight),sw=Math.max(1,Math.floor(r.width*img.naturalWidth)),sh=Math.max(1,Math.floor(r.height*img.naturalHeight));if(sw*sh>16000000)throw Error('Crop exceeds 16 megapixels');const canvas=document.createElement('canvas');canvas.width=sw;canvas.height=sh;const ctx=canvas.getContext('2d');if(!ctx)throw Error('Canvas not supported');ctx.drawImage(img,sx,sy,sw,sh,0,0,sw,sh);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error('Image crop failed');await setFile(new File([blob],'cropped.png',{type:'image/png'}))}finally{URL.revokeObjectURL(source)}}catch(e){error('scanError',e.message)}}
function clearOCR(){state.result=null;el('resultBody').hidden=true;el('resultPlaceholder').hidden=false;el('resultBadge').textContent='Not scanned';el('resultBadge').classList.remove('active');el('ocrOverlay').replaceChildren();error('scanError','');error('translationError','')}
async function normalizeCameraImage(file){
 // Browser-decoded image is drawn into a new, orientation-free PNG pixel buffer.
 // Do not normalize large images that already meet this property.
 if(file.type!=='image/jpeg')return file;
 let bitmap=null;
 try{
  if(!window.createImageBitmap)return file;
  bitmap=await createImageBitmap(file,{imageOrientation:'from-image'});
  if(bitmap.width*bitmap.height>16000000)throw Error('Image exceeds 16 megapixels.');
  const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;
  const ctx=canvas.getContext('2d');if(!ctx)throw Error('Canvas not supported');ctx.drawImage(bitmap,0,0);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
  if(!blob||blob.size>MAX_UPLOAD)return file;
  return new File([blob],file.name.replace(/\.jpe?g$/i,'.png'),{type:'image/png'});
 }catch(e){return file}finally{bitmap?.close()}
}
async function setFile(file){if(!file)return;currentPdf=null;const allowed=['image/jpeg','image/png','image/webp'];if(!allowed.includes(file.type)){error('scanError','Choose a JPG, PNG or WebP image.');return}if(file.size>MAX_UPLOAD){error('scanError','The image is too large. Maximum size is 12 MB.');return}file=await normalizeCameraImage(file);if(state.objectUrl)URL.revokeObjectURL(state.objectUrl);state.file=file;state.objectUrl=URL.createObjectURL(file);el('previewImg').src=state.objectUrl;el('dropEmpty').hidden=true;el('preview').hidden=false;el('imageBadge').textContent=`${file.name || 'Camera image'} · ${(file.size/1024/1024).toFixed(2)} MB`;el('rotateButton').disabled=false;el('cropButton').disabled=false;el('replaceButton').disabled=false;resetCrop();el('scanButton').disabled=false;clearOCR();toast('Image ready to recognize')}
function selectFile(){el('filePicker').click()}
async function rotateImage(){if(!state.file||state.busy)return;try{const img=new Image();const source=URL.createObjectURL(state.file);try{await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=source});const canvas=document.createElement('canvas');canvas.width=img.naturalHeight;canvas.height=img.naturalWidth;const ctx=canvas.getContext('2d');if(!ctx)throw Error('Canvas not supported');ctx.translate(canvas.width,0);ctx.rotate(Math.PI/2);ctx.drawImage(img,0,0);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error('Could not rotate image');if(blob.size>MAX_UPLOAD)throw Error('Rotated image exceeds 12 MB');await setFile(new File([blob], 'rotated.png',{type:'image/png'}))}finally{URL.revokeObjectURL(source)}}catch(e){error('scanError',e.message)}}
async function beginCamera(){if(state.busy)return;try{if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera preview requires localhost or HTTPS. Use Take photo instead.');state.camera=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:1080}},audio:false});el('video').srcObject=state.camera;el('cameraModal').hidden=false;await el('video').play()}catch(e){closeCamera();if(e.name==='NotAllowedError')toast('Camera permission denied. You can upload an image instead.');else{toast('Live camera unavailable. Choose Take photo.');el('cameraPicker').click()}}}
function closeCamera(){if(state.camera){state.camera.getTracks().forEach(track=>track.stop());state.camera=null}el('video').srcObject=null;el('cameraModal').hidden=true}
async function takePhoto(){const video=el('video');if(!video.videoWidth){toast('Camera is still starting');return}const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.getContext('2d').drawImage(video,0,0);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.94));if(blob){closeCamera();await setFile(new File([blob],`capture-${Date.now()}.jpg`,{type:'image/jpeg'}))}}
function renderBoxes(){const overlay=el('ocrOverlay');overlay.replaceChildren();if((currentPdf||batchFiles.length)||!state.result||!el('showBoxes').checked)return;for(const line of state.result.lines||[]){const b=line.box;if(!b)continue;const rect=document.createElement('div');rect.className='ocr-box';rect.style.left=`${Math.min(100,Math.max(0,b.x*100))}%`;rect.style.top=`${Math.min(100,Math.max(0,b.y*100))}%`;rect.style.width=`${Math.max(0,Math.min(100-b.x*100,b.width*100))}%`;rect.style.height=`${Math.max(0,Math.min(100-b.y*100,b.height*100))}%`;rect.title=line.text;overlay.append(rect)}}
function setResults(data){state.result=data;el('resultPlaceholder').hidden=true;el('resultBody').hidden=false;el('resultBadge').textContent=data.text?'Ready to review':'No text detected';el('resultBadge').classList.add('active');el('detectedLanguage').textContent=({'my':'Myanmar','en':'English','my+en':'Mixed','undetermined':'Unknown'})[data.detected_language]||data.detected_language;el('confidenceValue').textContent=data.confidence===null?'—':`${data.confidence}%*`;el('confidenceValue').title='Provider recognition confidence — not verified character accuracy';el('variantValue').textContent=data.variant;el('extractedText').value=data.text||'';el('translatedText').value='';countCharacters();const alt=(data.alternatives||[]).filter(a=>a.text&&a.text!==data.text);el('alternativesWrap').hidden=!alt.length;el('alternativesSelect').replaceChildren();alt.forEach((a,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=`${a.variant} — signal ${a.confidence}%`;el('alternativesSelect').append(option)});state.alternatives=alt;syncTranslationDirection();renderBoxes();el('resultsTop')?.scrollIntoView({behavior:'smooth'})}
async function scan(){if(!(state.file||currentPdf||batchFiles.length)||state.busy)return;markBusy(true);clearOCR();error('scanError','');try{const form=new FormData();if(batchFiles.length){for(const f of batchFiles)form.append('files',f)}else form.append('file',currentPdf||state.file);form.append('language',el('sourceLanguage').value);form.append('mode',el('accuracyMode').value);form.append('engine',el('ocrEngine').value);form.append('rotate','0');const r=await fetch(batchFiles.length?'/api/batch':currentPdf?'/api/pdf':'/api/ocr',{method:'POST',body:form});const body=await r.json().catch(()=>({}));if(!r.ok)throw Error(body.detail||`OCR failed (${r.status})`);setResults(body);toast(body.text?'OCR finished — review the text':'No text detected. Try a brighter image.');if(window.innerWidth<730)el('resultBadge').scrollIntoView({behavior:'smooth',block:'center'})}catch(e){error('scanError',e.message||'OCR failed. Please try again.')}finally{markBusy(false)}}
function translationDirection(){
 const source=el('translateSource').value, target=el('translateTarget').value;
 el('translationTitle').textContent=target==='my'?'Myanmar translation':'English translation';
 const button=el('translateButton');
 button.textContent=`Translate ${source==='my'?'Myanmar':'English'} → ${target==='my'?'Myanmar':'English'} ↗`;
 return {source,target};
}
function syncTranslationDirection(){
 const selected=el('sourceLanguage').value;
 const detected=state.result?.detected_language;
 const source=selected==='my'||selected==='en'?selected:(detected==='en'?'en':'my');
 el('translateSource').value=source;
 el('translateTarget').value=source==='my'?'en':'my';
 translationDirection();
}
async function translateNow(){
 const input=el('extractedText').value.trim();
 if(!input){error('translationError','Extract or enter text before translating.');return}
 if(state.busy)return;
 const {source,target}=translationDirection();
 if(source===target){error('translationError','Select different source and target languages.');return}
 error('translationError','');el('translateButton').disabled=true;el('translateButton').textContent='Translating…';
 try{const r=await fetch('/api/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:input,source,target})});const data=await r.json().catch(()=>({}));if(!r.ok)throw Error(data.detail||'Translation failed');el('translatedText').value=data.translated_text;el('translatedText').lang=target;toast('Translation ready — review before sharing')}
 catch(e){error('translationError',e.message||'Translation failed')}
 finally{el('translateButton').disabled=false;translationDirection()}
}
async function copyText(source){const text=el(source).value;if(!text.trim())return toast('There is no text to copy');try{await navigator.clipboard.writeText(text);toast('Copied to clipboard')}catch{const input=el(source);input.focus();input.select();toast('Select and copy the highlighted text')}}
function download(name,text){if(!text.trim())return toast('Nothing to save yet');const blob=new Blob(['\ufeff',text],{type:'text/plain;charset=utf-8'});const link=document.createElement('a');const url=URL.createObjectURL(blob);link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),2000)}
function countCharacters(){el('textCount').textContent=`${el('extractedText').value.length.toLocaleString()} characters`}
const translationsMM = {
 'Scan a document':'စာရွက်စာတမ်း ဖတ်ရန်', 'Source image':'မူရင်းဓာတ်ပုံ',
 'OCR SETTINGS':'OCR ဆက်တင်များ', 'Text language':'စာသားဘာသာစကား',
 'Recognition mode':'စာဖတ်နည်း', 'Recognition engine':'OCR စနစ်',
 'Show detected text boxes':'စာသားနေရာများ ပြရန်', 'RECOGNITION RESULTS':'OCR ရလဒ်',
 'Extracted text':'ထုတ်ယူထားသောစာသား', 'Recognized text · editable':'စာသားကို ပြင်ဆင်နိုင်သည်',
 'Review before using':'အသုံးမပြုမီ စစ်ဆေးပါ', 'From':'မှ', 'To':'သို့',
 'Copy text ⧉':'စာသားကူးယူရန် ⧉', 'English translation':'အင်္ဂလိပ်ဘာသာပြန်',
 'Capture':'ဓာတ်ပုံရိုက်ရန်', 'Recognize & review':'ဖတ်ပြီးစစ်ဆေးရန်',
 'Translate & export':'ဘာသာပြန်ပြီး သိမ်းရန်', 'Privacy by design':'ကိုယ်ရေးအချက်အလက် ကာကွယ်မှု',
 'HOW IT WORKS':'အသုံးပြုပုံ', 'Three simple steps.':'အဆင့် ၃ ဆင့်',
 'YOUR WORKSPACE':'အလုပ်လုပ်ရန်', 'Not scanned':'မဖတ်ရသေး',
 'No text detected':'စာသားမတွေ့ပါ', 'Ready to review':'စစ်ဆေးရန်',
 'Recognize text':'စာသားဖတ်ရန်', 'Swap':'ဘာသာစကားလဲရန်',
};
const localizableNodes = [];
function setupLocalization(){
 for(const node of document.querySelectorAll('h1,h2,h3,p,label,button,span,strong,small')){
  if(node.children.length||!node.textContent.trim())continue;
  const english=node.textContent.trim();
  if(translationsMM[english])localizableNodes.push({node,english});
 }
}
function applyLocale(){
 document.documentElement.lang=state.locale==='my'?'my':'en';
 for(const {node,english} of localizableNodes)node.textContent=state.locale==='my'?translationsMM[english]:english;
 el('languageToggle').textContent=state.locale==='my'?'English':'မြန်မာ';
 if(!state.busy)el('scanButtonLabel').textContent=state.locale==='my'?'စာသားဖတ်ရန်':'Recognize text';
}
async function setBatch(files){
 if(!files||!files.length)return;
 const selected=Array.from(files);
 if(selected.length>4||selected.some(f=>!['image/jpeg','image/png','image/webp'].includes(f.type))||selected.reduce((n,f)=>n+f.size,0)>MAX_UPLOAD){error('scanError','Choose up to 4 JPG/PNG/WebP images, 12 MB total.');return}
 if(state.objectUrl)URL.revokeObjectURL(state.objectUrl);
 state.file=null;state.objectUrl=null;currentPdf=null;batchFiles=selected;
 resetCrop();clearOCR();el('preview').hidden=true;el('dropEmpty').hidden=false;
 for(const id of ['rotateButton','cropButton','replaceButton'])el(id).disabled=true;
 el('scanButton').disabled=false;
 toast(`${selected.length} images selected for OCR`);
}
async function setPdf(file){
 if(!file)return;
 if(file.size>MAX_UPLOAD||!file.name.toLowerCase().endsWith('.pdf')){
  error('scanError','Choose a PDF document up to 12 MB.');return;
 }
 if(state.objectUrl)URL.revokeObjectURL(state.objectUrl);
 state.objectUrl=null;state.file=null;batchFiles=[];currentPdf=file;
 resetCrop();clearOCR();el('preview').hidden=true;el('dropEmpty').hidden=false;
 for(const id of ['rotateButton','cropButton','replaceButton'])el(id).disabled=true;
 el('scanButton').disabled=false;
 toast('PDF ready: '+file.name+' (maximum 8 pages)');
}
function getHistory(){try{const items=JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]');return Array.isArray(items)?items.filter(x=>x&&typeof x.text==='string'&&typeof x.date==='string').slice(0,12):[]}catch{return []}}
function renderHistory(){const list=el('historyList');list.replaceChildren();const items=getHistory();if(!items.length){const p=document.createElement('small');p.textContent='No saved texts yet.';list.append(p)}for(const item of items){const button=document.createElement('button');button.type='button';const title=document.createElement('span');title.textContent=item.text.slice(0,85)||'Empty';const date=document.createElement('small');date.textContent=new Date(item.date).toLocaleString();button.append(title,date);button.addEventListener('click',()=>{el('resultBody').hidden=false;el('resultPlaceholder').hidden=true;el('extractedText').value=item.text;el('translatedText').value=item.translation||'';countCharacters();toast('Saved text loaded for editing')});list.append(button)}}
function saveHistory(){const text=el('extractedText').value.trim();if(!text)return toast('Nothing to save');const history=getHistory();history.unshift({date:new Date().toISOString(),text:text.slice(0,20000),translation:el('translatedText').value.slice(0,20000)});try{localStorage.setItem(HISTORY_KEY,JSON.stringify(history.slice(0,12)));renderHistory();toast('Saved locally on this browser')}catch{toast('Storage unavailable. Copy or download text instead.')}}
function clearHistory(){if(!window.confirm('Delete saved text history from this browser?'))return;try{localStorage.removeItem(HISTORY_KEY)}catch{}renderHistory()}
function connectUI(){el('batchPicker').addEventListener('change',e=>setBatch(e.target.files));el('batchButton').addEventListener('click',()=>el('batchPicker').click());el('pdfPicker').addEventListener('change',e=>setPdf(e.target.files?.[0]));el('pdfButton').addEventListener('click',()=>el('pdfPicker').click());el('saveHistory').addEventListener('click',saveHistory);el('clearHistory').addEventListener('click',clearHistory);
el('filePicker').addEventListener('change',e=>setFile(e.target.files?.[0]));el('cameraPicker').addEventListener('change',e=>setFile(e.target.files?.[0]));el('browseButton').addEventListener('click',e=>{e.stopPropagation();selectFile()});el('dropzone').addEventListener('click',e=>{if(e.target.closest('button')||state.file)return;selectFile()});el('dropzone').addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&!state.file){e.preventDefault();selectFile()}});el('dropzone').addEventListener('dragover',e=>{e.preventDefault();el('dropzone').classList.add('dragging')});el('dropzone').addEventListener('dragleave',()=>el('dropzone').classList.remove('dragging'));el('dropzone').addEventListener('drop',e=>{e.preventDefault();el('dropzone').classList.remove('dragging');setFile(e.dataTransfer.files[0])});window.addEventListener('paste',e=>{const file=[...(e.clipboardData?.files||[])].find(f=>f.type.startsWith('image/'));if(file)setFile(file)});el('cameraButton').addEventListener('click',beginCamera);el('mobileCapture').addEventListener('click',()=>el('cameraPicker').click());el('closeCamera').addEventListener('click',closeCamera);el('takePhoto').addEventListener('click',takePhoto);el('cameraModal').addEventListener('click',e=>{if(e.target===el('cameraModal'))closeCamera()});window.addEventListener('keydown',e=>{if(e.key==='Escape')closeCamera()});el('rotateButton').addEventListener('click',rotateImage);el('cropButton').addEventListener('click',enableCrop);el('applyCrop').addEventListener('click',applyCrop);el('cancelCrop').addEventListener('click',resetCrop);el('imageStage').addEventListener('pointerdown',cropDown);el('imageStage').addEventListener('pointermove',cropMove);el('imageStage').addEventListener('pointerup',cropEnd);el('imageStage').addEventListener('pointercancel',cropEnd);el('replaceButton').addEventListener('click',selectFile);el('scanButton').addEventListener('click',scan);el('showBoxes').addEventListener('change',renderBoxes);el('translateButton').addEventListener('click',translateNow);el('translateSource').addEventListener('change',()=>{el('translateTarget').value=el('translateSource').value==='my'?'en':'my';translationDirection()});el('translateTarget').addEventListener('change',translationDirection);el('swapLanguages').addEventListener('click',()=>{const a=el('translateSource').value;el('translateSource').value=el('translateTarget').value;el('translateTarget').value=a;translationDirection()});el('sourceLanguage').addEventListener('change',()=>{if(state.result)syncTranslationDirection()});el('extractedText').addEventListener('input',countCharacters);el('copyMyanmar').addEventListener('click',()=>copyText('extractedText'));el('copyEnglish').addEventListener('click',()=>copyText('translatedText'));el('downloadText').addEventListener('click',()=>download('myan-ocr-extracted.txt',el('extractedText').value));el('saveBilingual').addEventListener('click',()=>download('myan-ocr-bilingual.txt',`MYANMAR / SOURCE\n${el('extractedText').value}\n\nENGLISH TRANSLATION\n${el('translatedText').value}`));el('useAlternative').addEventListener('click',()=>{const candidate=state.alternatives?.[Number(el('alternativesSelect').value)];if(candidate){el('extractedText').value=candidate.text;el('variantValue').textContent=candidate.variant;el('ocrOverlay').replaceChildren();countCharacters();toast('Alternate result loaded; boxes hidden for this version')}});el('languageToggle').addEventListener('click',()=>{state.locale=state.locale==='en'?'my':'en';applyLocale();toast(state.locale==='my'?'မြန်မာစာ OCR အသုံးပြုနိုင်ပါသည်။':'English interface selected')})}
document.addEventListener('DOMContentLoaded',()=>{setupLocalization();connectUI();translationDirection();checkHealth();renderHistory()});
