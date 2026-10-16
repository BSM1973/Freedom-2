#!/usr/bin/env python3
"""Prepare the original Freedom 2 v8.8 HTML UI as a JUCE WebView resource.
This does not yet connect all controls to the native audio processor.
"""
from pathlib import Path
import re
import sys

root=Path(sys.argv[1])
plugin=root/"plugin"
cmake=plugin/"CMakeLists.txt"
editor_h=plugin/"Source/PluginEditor.h"
editor_cpp=plugin/"Source/PluginEditor.cpp"
html=root/"index.html"
assert all(p.is_file() for p in (cmake,editor_h,editor_cpp,html))
# Use JUCE's binary resources: the original HTML bytes are embedded without
# regenerating or approximating the design.
assets=plugin/"WebUI"
assets.mkdir(exist_ok=True)
# The UI's LibertyFreedomUI API exposes parameter keys used by the native
# AudioProcessorValueTreeState. Check the oscillator contract before building.
source_html=html.read_text()
# Hide the first uncleaned paint until the synchronous cleanup finishes.
source_html=source_html.replace("<html",'<html class="liberty-ui-initializing"',1)
native_params=(plugin/"Source/PluginProcessor.cpp").read_text()
for oscillator in (1,2,3):
    for suffix in ("On","Wave","Octave","Semitone","Fine","Volume","Pan","Phase","Pulse_Width"):
        key=f"Osc_{oscillator}_{suffix}"
        if key not in source_html:
            raise RuntimeError(f"Original HTML missing oscillator control: {key}")
if 'getParameters' not in source_html or 'onParameterChange' not in source_html:
    raise RuntimeError("Original HTML parameter-change API not found")
if 'id("On")' not in native_params or 'id("Wave")' not in native_params or 'addFloat' not in native_params:
    raise RuntimeError("Native oscillator parameter factory not found")
print("Oscillator HTML controls and native parameter family identified (bridge pending).")
# Nonvisual OSC1 bridge. It observes the existing UI state without altering
# controls, layout, styles, or the original HTML source archive.
bridge = ""  # Legacy bidirectional polling disabled: it overwrote preset values with host defaults.\n# Visual-only cleanup requested for Freedom 2. Keep native DSP and preset logic intact.
browser_audio_guard = """
<script id="liberty-disable-browser-audio">
(() => {
  // The native JUCE DSP is the only audible engine. The original HTML
  // preview may still synthesize for visualization, but must never feed
  // the system audio output when a waveform button is clicked.
  if(typeof AudioNode==='undefined'||!AudioNode.prototype.connect)return;
  const original=AudioNode.prototype.connect;
  AudioNode.prototype.connect=function(destination,...args){
    if(typeof AudioDestinationNode!=='undefined' &&
       destination instanceof AudioDestinationNode)return destination;
    return original.call(this,destination,...args);
  };
})();
</script>
"""
ui_cleanup = """
<style id="liberty-ui-cleanup-style">
/* Prevent a transient frame of uncleaned controls on initial render. */
html.liberty-ui-initializing body { visibility:hidden!important; }
</style>
<script id="liberty-ui-cleanup">
(() => {
  const normalize = value => (value || '').replace(/\s+/g,' ').trim().toUpperCase();
  const nodes = () => [...document.querySelectorAll('button, a, [role="button"], div, span, section, header, small, strong, p')];
  const exact = label => nodes().find(el => normalize(el.textContent) === label &&
    ![...el.children].some(child => normalize(child.textContent) === label));
  const containing = label => nodes().filter(el => normalize(el.textContent).includes(label));
  const hide = el => { if (el) { el.hidden=true; el.style.setProperty('display','none','important'); } };
  const hideButton = label => {
    const leaf = exact(label);
    hide(leaf?.closest('button, a, [role="button"]') || leaf);
  };
  function removeStrip(labels) {
    // The shortest common ancestor of two independent labels is their toolbar.
    const first = containing(labels[0]).filter(el =>
      ![...el.children].some(c => normalize(c.textContent).includes(labels[0])))[0];
    const second = containing(labels[1]).filter(el =>
      ![...el.children].some(c => normalize(c.textContent).includes(labels[1])))[0];
    if (!first || !second) return;
    let common=first;
    while(common && !common.contains(second)) common=common.parentElement;
    if (!common) return;
    // Never remove a large parent containing the oscillator cards or presets.
    const text=normalize(common.textContent);
    if (text.includes('OSCILLATOR 01') || text.includes('NOM DU PRESET PERSONNEL')) return;
    hide(common);
  }
  function cleanup() {
    hideButton('EXPORT JSON');
    hideButton('IMPORT JSON');
    hideButton('PARAM API');
    // Exact button matching even when an icon is nested inside the button.
    for (const button of document.querySelectorAll('button,[role="button"]')) {
      if (normalize(button.textContent).includes('PARAM API')) hide(button);
    }
    // Remove oscillator header metadata without removing the actual OSCILLATOR title.
    const oscillatorMetadata = /^(ANALOG\s+ENGINE\s*·?\s*OSC\s*0?[123]|LIBERTY\s+SYNTHESIS|OSC\s*0?[123]\s*·\s*ACTIVE)$/;
    for (const el of nodes()) {
      if (el.children.length !== 0) continue;
      if (oscillatorMetadata.test(normalize(el.textContent))) hide(el);
    }
    // Some header metadata uses nested spans. Hide the smallest matching element,
    // never a card or a container containing the OSCILLATOR title.
    for (const label of ['ANALOG ENGINE', 'LIBERTY SYNTHESIS', 'OSC 01 · ACTIVE',
                         'OSC 02 · ACTIVE', 'OSC 03 · ACTIVE']) {
      const matches=nodes().filter(el=>normalize(el.textContent).includes(label) &&
        ![...el.children].some(child=>normalize(child.textContent).includes(label)));
      for(const el of matches) {
        const text=normalize(el.textContent);
        if (!text.includes('OSCILLATOR 0')) hide(el);
      }
    }
    // Original decorative signal monitor removed. The master volume control
    // is installed once by liberty-compact-layout below.
    for(const el of nodes()){
      if(el.children.length===0 && normalize(el.textContent)==='LIBERTY · SIGNAL MONITOR'){
        const strip=el.parentElement;
        if(strip && !strip.querySelector('#liberty-master-volume'))hide(strip);
      }
    }
    for(const button of document.querySelectorAll('button,[role="button"]')){
      if(normalize(button.textContent).startsWith('DENSITÉ'))hide(button);
    }
    // Idempotent cleanup: always preserve the largest SINE/SAW/PULSE/TRI
    // selector in each oscillator card and hide every smaller duplicate.
    const waveNames=['SINE','SAW','PULSE','TRI'];
    const allElements=[...document.querySelectorAll('*')];
    const waveformRows=allElements.filter(parent=>
      parent.children.length===4 && waveNames.every((name,index)=>
        normalize(parent.children[index].textContent)===name));
    for(let number=1;number<=3;number++){
      const heading=allElements.find(el=>el.children.length===0 &&
        normalize(el.textContent)==='OSCILLATOR 0'+number);
      if(!heading)continue;
      let card=heading.parentElement;
      while(card && waveformRows.filter(row=>card.contains(row)).length<2)
        card=card.parentElement;
      if(!card)continue;
      const rows=waveformRows.filter(row=>card.contains(row));
      if(rows.length<2)continue;
      // DOM order is stable even when hidden elements have zero dimensions.
      const primary=rows[0];
      primary.hidden=false;
      primary.style.removeProperty('display');
      primary.dataset.libertyPrimaryWave='true';
      for(const duplicate of rows.slice(1))hide(duplicate);
    }
    // Remove the original WAVE rotary control itself (knob, label and value).
    // Its numeric parameter remains accessible through the large waveform row.
    for(let number=1;number<=3;number++){
      const heading=allElements.find(el=>el.children.length===0 &&
        normalize(el.textContent)==='OSCILLATOR 0'+number);
      if(!heading)continue;
      let card=heading.parentElement;
      while(card && !card.querySelector('[data-liberty-primary-wave]'))card=card.parentElement;
      if(!card)continue;
      const waveLabels=[...card.querySelectorAll('label,span,div,small')].filter(el=>
        el.children.length===0 && normalize(el.textContent)==='WAVE');
      for(const label of waveLabels){
        let control=label;
        while(control.parentElement && control.parentElement!==card){
          const next=control.parentElement;
          const rect=next.getBoundingClientRect();
          if(rect.width>150 || rect.height>270)break;
          control=next;
          if(control.querySelector('input,[role="slider"],.v49-knob'))break;
        }
        if(control!==label && !control.querySelector('[data-liberty-primary-wave]'))hide(control);
      }
    }
    // Retain the four large waveform choices. Remove only a separate WAVE
    // parameter control, never the primary SINE/SAW/PULSE/TRI selector.
    for(let osc=1;osc<=3;osc++){
      const key='Osc_'+osc+'_Wave';
      const candidates=[...document.querySelectorAll('[data-param],[data-parameter],input,select')];
      for(const node of candidates){
        const bound=node.getAttribute('data-param')||node.getAttribute('data-parameter')||node.name||node.id||'';
        if(bound!==key)continue;
        const container=node.closest('label,.param-row,.parameter-row,.control-row')||node.parentElement;
        if(container && !container.querySelector('[data-liberty-primary-wave]') &&
           !['BUTTON'].includes(node.tagName))hide(container);
      }
    }
    // Make the existing oscillator enable buttons look and behave like
    // accessible on/off switches without creating a second parameter.
    for(let osc=1;osc<=3;osc++){
      const key='Osc_'+osc+'_On';
      for(const node of document.querySelectorAll('[data-param],[data-parameter],button')){
        const bound=node.getAttribute('data-param')||node.getAttribute('data-parameter')||'';
        if(bound!==key)continue;
        node.setAttribute('role','switch');
        node.setAttribute('aria-label','Oscillateur '+osc+' activé');
        const sync=()=>{
          const enabled=Number(window.LibertyFreedomUI?.getParameters?.()[key])>=0.5;
          node.setAttribute('aria-checked',String(enabled));
          node.style.borderRadius='999px';
          node.style.background=enabled?'#247f6b':'#343b48';
          node.style.border='1px solid '+(enabled?'#4ad6a8':'#717988');
        };
        sync();
        if(!node.dataset.libertySwitch){node.dataset.libertySwitch='1';setInterval(sync,300);}
      }
    }
    // Remove only the secondary waveform-monitor captions.
    for(const el of allElements){
      if(el.children.length===0 && normalize(el.textContent).includes('WAVEFORM MONITOR') &&
         normalize(el.textContent).includes('VISUAL ONLY')) hide(el);
    }



    // Lower-page cleanup: anchored to actual on-screen geometry and the
    // GLOBAL PLAY KEYBOARD, never to assumed component/class names.
    const normalizeText = el => normalize(el?.textContent || '');
    const exactTextNode = phrase => {
      const wanted=normalize(phrase);
      return [...document.querySelectorAll('div,span,p,small,strong,header,footer,section,label')]
        .find(el=>normalizeText(el).includes(wanted) &&
          ![...el.children].some(child=>normalizeText(child).includes(wanted)));
    };
    const keyboardAnchor=exactTextNode('GLOBAL PLAY KEYBOARD');
    const keyboardTop=keyboardAnchor?.getBoundingClientRect().top ?? Infinity;
    const protectedKeyboard = el => keyboardAnchor && el.contains(keyboardAnchor);
    const hideSafe=el=>{
      if(!el || el===document.body || el===document.documentElement ||
         protectedKeyboard(el)) return false;
      hide(el);
      return true;
    };
    const hideBannerText=phrase=>{
      const leaf=exactTextNode(phrase);
      if(!leaf) return;
      let best=leaf;
      for(let el=leaf;el && el!==document.body;el=el.parentElement){
        if(protectedKeyboard(el)) break;
        const rect=el.getBoundingClientRect();
        if(rect.width>=document.documentElement.clientWidth*0.7 &&
           rect.height>12 && rect.height<110 &&
           rect.top<keyboardTop) best=el;
      }
      hideSafe(best);
    };
    hideBannerText('DESIGN SYSTEM 1.0');
    hideBannerText('VISUAL PARAMETER PREVIEW');
    hideSafe(exactTextNode('GRAPHITE TITANIUM · EXPRESSION'));
    hideSafe(exactTextNode('PITCH REVIENT AU CENTRE AU RELÂCHEMENT'));
    // Remove the complete post-keyboard subtree, not just its title.
    // Find text using DOM text nodes (works with nested headings/spans).
    const findTextElement = phrase => {
      const wanted=normalize(phrase);
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      let textNode;
      while((textNode=walker.nextNode())){
        if(normalize(textNode.nodeValue).includes(wanted))
          return textNode.parentElement;
      }
      return null;
    };
    const keyboardNode=findTextElement('GLOBAL PLAY KEYBOARD');
    const midiNode=findTextElement('MIDI PERFORMANCE');
    if(keyboardNode && midiNode){
      // Lowest common ancestor of keyboard and MIDI content.
      let ancestor=keyboardNode;
      while(ancestor && !ancestor.contains(midiNode)) ancestor=ancestor.parentElement;
      if(ancestor && ancestor!==document.body && ancestor!==document.documentElement){
        // Find the branch immediately beneath the common parent that owns MIDI.
        let midiBranch=midiNode;
        while(midiBranch.parentElement!==ancestor && midiBranch.parentElement)
          midiBranch=midiBranch.parentElement;
        let keyboardBranch=keyboardNode;
        while(keyboardBranch.parentElement!==ancestor && keyboardBranch.parentElement)
          keyboardBranch=keyboardBranch.parentElement;
        if(midiBranch!==keyboardBranch &&
           (keyboardBranch.compareDocumentPosition(midiBranch)&Node.DOCUMENT_POSITION_FOLLOWING)){
          // MIDI and all subsequent sibling sections are below the keyboard.
          for(let section=midiBranch;section;){
            const next=section.nextElementSibling;
            hide(section);
            section=next;
          }
        }
      }
    }
    hideButton('ACTUALISER LES ONDES');
    // Hide diagnostic copy only, without hiding its containing toolbar.
    for (const el of nodes()) {
      if (el.children.length !== 0) continue;
      const label=normalize(el.textContent);
      if (label === 'DEMO / NO AUDIO' ||
          (label.includes('PARAMÈTRES CARTOGRAPHIÉS') &&
           label.includes('PRESETS DE RÉFÉRENCE'))) hide(el);
    }
    const history=nodes().find(el => el.children.length===0 &&
      /^HISTORIQUE\s+\d+\s*\/\s*\d+$/i.test((el.textContent||'').trim()));
    hide(history);
    removeStrip(['FREEDOM 2 · UI V1.6','GRAPHITE TITANIUM · DESIGN PASS']);
    removeStrip(['UI QUALITY CHECK V1.7','VÉRIFIER LES 4 ONGLETS']);
    removeStrip(['FREEDOM 2 · UI V2.0','CONTRÔLER LES COMMANDES']);
    // Keep the shortcuts button in the presets toolbar.
    hideButton('AUDIT UI');
    hideButton('WEB AUDIO EXPERIMENTAL');
    removeStrip(['ENGINE · FREEDOM 2','AUDIOWORKLET EXPERIMENTAL']);
  }
  let cleaning=false;
  const observer=new MutationObserver(changes=>{
    if(cleaning||!changes.some(c=>c.type==='childList'&&c.addedNodes.length))return;
    runCleanup(); // MutationObserver runs before the next browser paint.
  });
  function runCleanup(){
    if(cleaning)return;
    cleaning=true;
    observer.disconnect();
    try{cleanup();}catch(error){console.warn('Liberty UI cleanup:',error);}
    finally{
      document.documentElement.classList.remove('liberty-ui-initializing');
      cleaning=false;
      observer.observe(document.documentElement,{childList:true,subtree:true});
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',runCleanup,{once:true});
  else runCleanup();
  window.addEventListener('load',runCleanup,{once:true});

})();
</script>
"""
# Synchronize the rest of the native engine, including preset recalls.
# The existing OSC and filter bridges retain their specialized mappings.
native_api_shim = """
<script id="liberty-juce-native-api-shim">
(() => {
  // JUCE injects __JUCE__.postMessage, but getNativeFunction lives in
  // the optional frontend JS bundle. Provide the tiny supported protocol
  // directly so an embedded local HTML file can invoke C++ native functions.
  const juce=window.__JUCE__;
  if(!juce || typeof juce.postMessage!=='function')return;
  const backend=juce.backend||(juce.backend={});
  if(typeof backend.getNativeFunction==='function')return;
  const listeners=new Map();
  let serial=0;
  const previous=typeof backend.emitByBackend==='function'
    ?backend.emitByBackend.bind(backend):null;
  backend.emitByBackend=function(eventId,payload){
    if(eventId==='__juce__complete'){
      let result=payload;
      try{if(typeof payload==='string')result=JSON.parse(payload);}catch(_){}
      const entry=listeners.get(result?.promiseId);
      if(entry){listeners.delete(result.promiseId);entry.resolve(result.result);}
    }
    if(previous)previous(eventId,payload);
  };
  backend.getNativeFunction=function(name){
    return (...args)=>new Promise((resolve,reject)=>{
      const resultId=serial++;
      listeners.set(resultId,{resolve,reject});
      juce.postMessage(JSON.stringify({
        eventId:'__juce__invoke',
        payload:{name,params:args,resultId}
      }));
    });
  };
})();
</script>
"""
full_bridge = """
<script id="liberty-native-full-parameter-bridge">
(() => {
  const mapping = {
    // UI uses ADSR_Amp_* and Effects_* names in several original versions.
    Amp_Envelope_Attack:'attack', Amp_Envelope_Decay:'decay',
    Amp_Envelope_Sustain:'sustain', Amp_Envelope_Release:'release',
    ADSR_Amp_Attack:'attack', ADSR_Amp_Decay:'decay',
    ADSR_Amp_Sustain:'sustain', ADSR_Amp_Release:'release',
    Performance_Master_Volume:'master', Performance_Volume:'master',
    Global_Master_Volume:'master', Global_Volume:'master',
    Amp_Attack:'attack', Amp_Decay:'decay', Amp_Sustain:'sustain', Amp_Release:'release',
    Master_Volume:'master', Master_Gain:'master', Master_Level:'master',
    Osc_1_On:'osc1On', Osc_1_Wave:'osc1Wave', Osc_1_Volume:'osc1Level',
    Osc_1_Octave:'osc1Octave', Osc_1_Semitone:'osc1Semitone', Osc_1_Fine:'osc1Fine',
    Osc_2_On:'osc2On', Osc_2_Wave:'osc2Wave', Osc_2_Volume:'osc2Level',
    Osc_2_Octave:'osc2Octave', Osc_2_Semitone:'osc2Semitone', Osc_2_Fine:'osc2Fine',
    Osc_3_On:'osc3On', Osc_3_Wave:'osc3Wave', Osc_3_Volume:'osc3Level',
    Osc_3_Octave:'osc3Octave', Osc_3_Semitone:'osc3Semitone', Osc_3_Fine:'osc3Fine',
    Filter_Cutoff:'cutoff', Filter_Resonance:'resonance', Filter_Type:'filterMode',
    Filter_Envelope_Attack:'filterEnvAttack', Filter_Envelope_Decay:'filterEnvDecay',
    Filter_Envelope_Sustain:'filterEnvSustain', Filter_Envelope_Release:'filterEnvRelease',
    Filter_Envelope_Amount:'filterEnvAmount',
    Sync_2:'sync2', Sync_3:'sync3',
    Chorus_On:'chorusOn', Chorus_Rate:'chorusRate', Chorus_Mix:'chorusMix',
    Drive_On:'driveOn', Drive_Amount:'driveAmount', Drive_Tone:'driveTone', Drive_Mix:'driveMix'
  };
  for(let i=1;i<=3;i++) {
    for(const [ui,native] of Object.entries({Rate:'Rate',Depth:'Depth',Wave:'Wave'}))
      mapping['LFO_'+i+'_'+ui]='lfo'+i+native;
  }
  for(let i=1;i<=8;i++) {
    mapping['Matrix_'+i+'_Source']='route'+i+'Source';
    mapping['Matrix_'+i+'_Destination']='route'+i+'Dest';
    mapping['Matrix_'+i+'_Amount']='route'+i+'Amount';
  }
  // Automatically map controls whose names differ only in punctuation/case.
  // The JUCE side rejects unknown IDs; never silently treat them as connected.
  const aliases = {
    master:['mastervolume','mastergain','outputvolume','globalvolume'],
    attack:['ampattack','ampenvattack','ampenvelopeattack'],
    decay:['ampdecay','ampenvdecay','ampenvelopedecay'],
    sustain:['ampsustain','ampenvsustain','ampenvelopesustain'],
    release:['amprelease','ampenvrelease','ampenveloperelease']
  };
  // Visible native-link telemetry: a green build cannot validate an embedded WebView.
  let applied=0, rejected=0, missing=0, lastError='';
  function status(message,ok) {
    let el=document.getElementById('liberty-native-status');
    if(!el){
      el=document.createElement('div');el.id='liberty-native-status';
      el.style.cssText='position:fixed;bottom:8px;right:12px;z-index:2147483647;padding:7px 12px;border-radius:7px;font:12px system-ui;background:#17212b;color:#fff;border:1px solid #65717d;pointer-events:none';
      document.body.appendChild(el);
    }
    el.style.borderColor=ok?'#30c89c':'#ef765c';
    el.textContent='JUCE DSP: '+message;
  }
  let last = new Map(), pending = false;
  async function push() {
    if(pending)return;
    const ui=window.LibertyFreedomUI;
    const backend=window.__JUCE__?.backend;
    const set=backend?.getNativeFunction?.('freedomSetParameter');
    const get=backend?.getNativeFunction?.('freedomGetParameter');
    if(!ui?.getParameters){status('interface non prête',false);return;}
    if(!set||!get){status('liaison native INACTIVE',false);return;}
    pending=true;
    try {
      const values=ui.getParameters();
      for(const key of Object.keys(values)) {
        if(key in mapping)continue;
        const normalized=key.toLowerCase().replace(/[^a-z0-9]/g,'');
        for(const [id,names] of Object.entries(aliases))
          if(names.includes(normalized))mapping[key]=id;
      }
      for(const [key,id] of Object.entries(mapping)) {
        if(!(key in values))continue;
        const v=Number(values[key]);
        if(!Number.isFinite(v)||last.get(key)===v)continue;
        const ok=await set(id,v);
        if(ok) {
          const actual=Number(await get(id));
          // Do not report synchronization until the native parameter
          // confirms the requested physical value (after range clamping).
          if(Number.isFinite(actual)){
            last.set(key,v);applied++;
            if(Math.abs(actual-v)>0.02)lastError=key+': demandé '+v+', natif '+actual.toFixed(3);
          }
        } else {rejected++;lastError=key+' refusé par JUCE';}
      }
      status('écritures '+applied+' | refus '+rejected+(lastError?' | '+lastError:''),applied>0&&rejected===0);
    } catch(e) { lastError=String(e);status('ERREUR '+lastError,false);console.error('Freedom 2 native parameter sync failed:',e); }
    finally {pending=false;}
  }
  // Preset loads often mutate many fields without dispatching DOM change.
  // Intercept the public UI API and synchronize immediately after a batch.
  function install() {
    const ui=window.LibertyFreedomUI;
    if(!ui?.setParameter||ui.__libertyNativeWrapped)return;
    const original=ui.setParameter.bind(ui);
    ui.setParameter=function(key,value){
      const result=original(key,value);
      if(result)queueMicrotask(push);
      return result;
    };
    ui.__libertyNativeWrapped=true;
  }
  setInterval(()=>{install();push();},100);
})();
</script>
"""
compact_layout = """
<style id="liberty-compact-layout-css">
#liberty-master-volume{display:inline-flex;align-items:center;gap:9px;flex-shrink:0;color:#dce9f2;font:600 12px system-ui}
#liberty-master-volume input{width:118px;accent-color:#53c4e3;cursor:pointer}
#liberty-master-volume output{min-width:35px;text-align:right;font-variant-numeric:tabular-nums}
#liberty-keyboard-toggle{flex-shrink:0;background:#142635;color:#dce9f2;border:1px solid #54788c;border-radius:7px;padding:9px 13px;font:600 12px system-ui;cursor:pointer}
#liberty-keyboard-toggle[aria-expanded="true"]{border-color:#53c4e3}
</style>
<script id="liberty-compact-layout-js">
(() => {
 let keyboardOpen=false;
 const norm=e=>(e?.textContent||'').replace(/\\s+/g,' ').trim().toUpperCase();
 const native=()=>window.__JUCE__?.backend?.getNativeFunction?.('freedomSetParameter');
 function toolbar(){
   const search=[...document.querySelectorAll('input')].find(e=>/Trouver un paramètre/i.test(e.placeholder||''));
   if(search)return search.parentElement?.parentElement;
   const title=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&norm(e)==='LIBERTY · SIGNAL MONITOR');
   return title?.parentElement?.parentElement||null;
 }
 function keyboardSection(){
   const title=[...document.querySelectorAll('div,span,h2,h3,h4')].find(e=>e.children.length===0&&norm(e).includes('GLOBAL PLAY KEYBOARD'));
   if(!title)return null;
   let el=title;
   for(let i=0;i<7&&el.parentElement;i++,el=el.parentElement){
     const count=el.querySelectorAll('[data-note],[data-midi-note],.piano-key,.keyboard-key,.white-key,.black-key').length;
     if(count>=12&&count<=100)return el;
   }
   return title.parentElement;
 }
 function install(){
   const bar=toolbar();
   if(bar&&!document.getElementById('liberty-master-volume')){
     const control=document.createElement('label');
     control.id='liberty-master-volume';
     control.innerHTML='MASTER <input type="range" min="0" max="100" step="1" value="80" aria-label="Volume général"><output>80 %</output>';
     const slider=control.querySelector('input'),output=control.querySelector('output');
     slider.addEventListener('input',()=>{
       output.textContent=slider.value+' %';
       const value=Number(slider.value)/100;
       const ui=window.LibertyFreedomUI;
       const values=ui?.getParameters?.()||{};
       const key=['Performance_Master_Volume','Performance_Volume','Global_Master_Volume','Global_Volume','Master_Volume','Master_Gain','Master_Level'].find(k=>k in values);
       if(key&&ui?.setParameter)ui.setParameter(key,value);
       else {const fn=native();if(fn)Promise.resolve(fn('master',value)).catch(console.warn);}
     });
     bar.prepend(control);
     // Match actual preset master when available, without triggering audio changes.
     setInterval(()=>{
       if(document.activeElement===slider)return;
       const values=window.LibertyFreedomUI?.getParameters?.()||{};
       const key=['Performance_Master_Volume','Performance_Volume','Global_Master_Volume','Global_Volume','Master_Volume','Master_Gain','Master_Level'].find(k=>k in values);
       if(key&&Number.isFinite(Number(values[key]))){
         const n=Math.round(Math.max(0,Math.min(1,Number(values[key])))*100);
         slider.value=String(n);output.textContent=n+' %';
       }
     },500);
   }
   if(bar&&!document.getElementById('liberty-keyboard-toggle')){
     const toggle=document.createElement('button');
     toggle.id='liberty-keyboard-toggle';toggle.type='button';
     toggle.addEventListener('click',()=>{keyboardOpen=!keyboardOpen;updateKeyboard();});
     bar.appendChild(toggle);
   }
   updateKeyboard();
 }
 function updateKeyboard(){
   const section=keyboardSection();
   if(section)section.style.setProperty('display',keyboardOpen?'':'none',keyboardOpen?'':'important');
   const toggle=document.getElementById('liberty-keyboard-toggle');
   if(toggle){toggle.textContent=keyboardOpen?'⌃ FERMER CLAVIER':'⌄ AFFICHER CLAVIER';toggle.setAttribute('aria-expanded',String(keyboardOpen));}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
 else install();
 window.addEventListener('load',install,{once:true});
 const observer=new MutationObserver(changes=>{
   if(changes.some(c=>c.addedNodes.length))install();
 });
 observer.observe(document.documentElement,{childList:true,subtree:true});
})();
</script>
"""
keyboard_bridge = """
<script id="liberty-native-keyboard">
(() => {
  const notes=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  const getSend=()=>window.__JUCE__?.backend?.getNativeFunction?.('freedomKeyboardNote');
  const active=new Map();
  function locate(){
    const all=[...document.querySelectorAll('h1,h2,h3,h4,div,span,p')];
    const title=all.find(e=>e.children.length===0&&e.textContent.trim().toUpperCase().includes('GLOBAL PLAY KEYBOARD'));
    if(!title)return null;
    let root=title.parentElement;
    for(let i=0;i<5&&root;i++,root=root.parentElement){
      const keys=[...root.querySelectorAll('[data-note],[data-midi-note],.piano-key,.keyboard-key,.white-key,.black-key')];
      if(keys.length>=12&&keys.length<=100)return keys;
    }
    return null;
  }
  function noteOf(el,index){
    const raw=el.getAttribute('data-midi-note')||el.getAttribute('data-note');
    if(raw!==null&&/^\\d+$/.test(raw))return Number(raw);
    const match=String(raw||el.getAttribute('aria-label')||'').match(/([A-G])(#|b)?\\s*(-?\\d+)/i);
    if(match){const name=match[1].toUpperCase()+(match[2]||'');const offset=notes.indexOf(name);if(offset>=0)return (Number(match[3])+1)*12+offset;}
    return 48+index;
  }
  function setup(){
    const keys=locate();if(!keys)return;
    keys.forEach((el,index)=>{
      if(el.dataset.libertyNativeKey==='1')return;
      el.dataset.libertyNativeKey='1';
      const note=noteOf(el,index);if(note<0||note>127)return;
      const send=(on)=>{const fn=getSend();if(fn)Promise.resolve(fn(note,100,on)).catch(console.warn);};
      el.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();active.set(e.pointerId,note);send(true);el.setPointerCapture?.(e.pointerId);});
      const off=e=>{if(active.get(e.pointerId)!==note)return;active.delete(e.pointerId);send(false);};
      el.addEventListener('pointerup',off);el.addEventListener('pointercancel',off);
      el.addEventListener('lostpointercapture',off);
    });
  }
  setInterval(setup,500);
})();
</script>
"""
if "</body>" not in source_html:
    raise RuntimeError("Original HTML has no body closing tag")
(assets/"index.html").write_text(source_html.replace("<head>","<head>"+browser_audio_guard,1).replace("</body>",ui_cleanup+bridge+native_api_shim+full_bridge+keyboard_bridge+compact_layout+"</body>",1))

s=cmake.read_text()
s=s.replace("JUCE_WEB_BROWSER=0", "JUCE_WEB_BROWSER=1")
if "juce_add_binary_data(Freedom2WebUI" not in s:
    s += """
juce_add_binary_data(Freedom2WebUI SOURCES WebUI/index.html)
target_link_libraries(Freedom2 PRIVATE Freedom2WebUI)
"""
cmake.write_text(s)
# Initialize native DSP parameters when the host prepares audio.
processor_cpp=plugin/"Source/PluginProcessor.cpp"
processor_source=processor_cpp.read_text()
old_prepare='scratchR.resize((size_t)std::max(1,block));dsp.panic();'
new_prepare='scratchR.resize((size_t)std::max(1,block));syncParameters();dsp.panic();'
if old_prepare not in processor_source and new_prepare not in processor_source:
    raise RuntimeError("Unexpected native prepareToPlay implementation")
if old_prepare in processor_source:
    processor_cpp.write_text(processor_source.replace(old_prepare,new_prepare,1))
# Diagnostic for host MIDI event dispatch and block rendering; retained only
# while the native audio regression is failing. No UI changes.
processor_source=processor_cpp.read_text()
if 'LIBERTY_MIDI_TRACE' not in processor_source:
    target='for(const auto meta:midi){'
    if target not in processor_source:
        raise RuntimeError("Native processBlock MIDI loop not found")
    processor_source=processor_source.replace(target,
        'for(const auto meta:midi){ '
        'std::fprintf(stderr,"LIBERTY_MIDI_TRACE noteOn=%d note=%d velocity=%.3f\\n", '
        '(int)meta.getMessage().isNoteOn(), meta.getMessage().getNoteNumber(), '
        'meta.getMessage().getVelocity()); ',1)
    if '#include <cstdio>' not in processor_source:
        processor_source='#include <cstdio>\\n'.replace('\\n','\\n')+processor_source
    processor_cpp.write_text(processor_source)
# JUCE MidiMessage::getVelocity() already returns MIDI velocity 0..127.
# Multiplying by 127 makes noteOn reject every normal key press as invalid.
processor_source=processor_cpp.read_text()
wrong='juce::roundToInt(m.getVelocity()*127.f)'
correct='static_cast<int>(m.getVelocity())'
if wrong in processor_source:
    processor_source=processor_source.replace(wrong,correct)
elif correct not in processor_source:
    raise RuntimeError("Expected MIDI velocity conversion missing")
# Remove the temporary printf trace, whose %f specifier was not type-safe.
processor_source=re.sub(r'std::fprintf\(stderr,"LIBERTY_MIDI_TRACE.*?;\s*', '', processor_source)
processor_cpp.write_text(processor_source)
processor_h=plugin/"Source/PluginProcessor.h"
header=processor_h.read_text()
if "getValueTreeState()" not in header:
    header=header.replace("public:", "public:\n  juce::AudioProcessorValueTreeState& getValueTreeState() noexcept { return apvts; }",1)
    processor_h.write_text(header)

if "getKeyboardState()" not in header:
    header=processor_h.read_text()
    header=header.replace("public:", "public:" + chr(10) + "  juce::MidiKeyboardState& getKeyboardState() noexcept { return keyboardState; }",1)
    processor_h.write_text(header)

editor_h.write_text("""#pragma once
#include <JuceHeader.h>
#include "PluginProcessor.h"
class Freedom2Editor final : public juce::AudioProcessorEditor {
public:
 explicit Freedom2Editor(Freedom2Processor&);
 void resized() override;
private:
 Freedom2Processor& processor;
 juce::WebBrowserComponent browser;
 JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(Freedom2Editor)
};
""")
editor_cpp.write_text("""#include "PluginEditor.h"
#include <BinaryData.h>
#include <cmath>
Freedom2Editor::Freedom2Editor(Freedom2Processor& p)
  : juce::AudioProcessorEditor(&p), processor(p),
    browser(juce::WebBrowserComponent::Options()
      .withNativeIntegrationEnabled()
      .withNativeFunction("freedomGetOscillators",
        [&p](const juce::Array<juce::var>&,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          juce::Array<juce::var> values;
          const juce::StringArray fields{"On","Wave","Level","Octave","Semitone","Fine"};
          for (int osc = 1; osc <= 3; ++osc) {
            for (const auto& field : fields) {
              const auto id = "osc" + juce::String(osc) + field;
              auto* param = p.getValueTreeState().getParameter(id);
              values.add(param != nullptr ? juce::var(param->convertFrom0to1(param->getValue()))
                                          : juce::var());
            }
          }
          complete(juce::var(values));
        })
      .withNativeFunction("freedomGetFilter",
        [&p](const juce::Array<juce::var>&,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          juce::Array<juce::var> values;
          for (const auto& id : juce::StringArray{"cutoff","resonance","filterMode"}) {
            auto* parameter = p.getValueTreeState().getParameter(id);
            values.add(parameter != nullptr
              ? juce::var(parameter->convertFrom0to1(parameter->getValue()))
              : juce::var());
          }
          complete(juce::var(values));
        })
      .withNativeFunction("freedomGetFilterEnvelope",
        [&p](const juce::Array<juce::var>&,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          juce::Array<juce::var> values;
          for (const auto& id : juce::StringArray{"filterEnvAttack","filterEnvDecay",
              "filterEnvSustain","filterEnvRelease","filterEnvAmount"}) {
            auto* parameter=p.getValueTreeState().getParameter(id);
            values.add(parameter != nullptr
              ? juce::var(parameter->convertFrom0to1(parameter->getValue()))
              : juce::var());
          }
          complete(juce::var(values));
        })
      .withNativeFunction("freedomSetFilterEnvelope",
        [&p](const juce::Array<juce::var>& args,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          if(args.size()!=2 || !args[0].isString()){complete(false);return;}
          const auto id=args[0].toString();
          if(id!="filterEnvAttack" && id!="filterEnvDecay" &&
             id!="filterEnvSustain" && id!="filterEnvRelease" &&
             id!="filterEnvAmount"){complete(false);return;}
          auto* parameter=p.getValueTreeState().getParameter(id);
          if(parameter==nullptr){complete(false);return;}
          const float value=static_cast<float>(static_cast<double>(args[1]));
          if(!std::isfinite(value)){complete(false);return;}
          parameter->setValueNotifyingHost(parameter->convertTo0to1(value));
          complete(true);
        })
      .withNativeFunction("freedomSetFilter",
        [&p](const juce::Array<juce::var>& args,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          if (args.size()!=2 || !args[0].isString()) {complete(false);return;}
          const auto id=args[0].toString();
          if (id!="cutoff" && id!="resonance" && id!="filterMode") {complete(false);return;}
          auto* parameter=p.getValueTreeState().getParameter(id);
          if (parameter==nullptr) {complete(false);return;}
          const float value=static_cast<float>(static_cast<double>(args[1]));
          if (!std::isfinite(value)) {complete(false);return;}
          if (id=="filterMode" && (value<0.0f || value>5.0f
              || std::floor(value)!=value)) {complete(false);return;}
          parameter->setValueNotifyingHost(parameter->convertTo0to1(value));
          complete(true);
        })
      .withNativeFunction("freedomKeyboardNote",
        [&p](const juce::Array<juce::var>& args,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          if(args.size()!=3) {complete(false);return;}
          const int note=static_cast<int>(args[0]);
          const int velocity=static_cast<int>(args[1]);
          const bool on=static_cast<bool>(args[2]);
          if(note<0||note>127||velocity<0||velocity>127) {complete(false);return;}
          if(on) p.getKeyboardState().noteOn(1,note,static_cast<float>(velocity)/127.0f);
          else p.getKeyboardState().noteOff(1,note,0.0f);
          complete(true);
        })
      .withNativeFunction("freedomGetParameter",
        [&p](const juce::Array<juce::var>& args,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          if(args.size()!=1 || !args[0].isString()) {complete(juce::var());return;}
          auto* parameter=p.getValueTreeState().getParameter(args[0].toString());
          complete(parameter ? juce::var(parameter->convertFrom0to1(parameter->getValue())) : juce::var());
        })
      .withNativeFunction("freedomSetParameter",
        [&p](const juce::Array<juce::var>& args,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          if(args.size()!=2 || !args[0].isString()) {complete(false);return;}
          auto* parameter=p.getValueTreeState().getParameter(args[0].toString());
          if(parameter==nullptr) {complete(false);return;}
          const float value=static_cast<float>(static_cast<double>(args[1]));
          if(!std::isfinite(value)) {complete(false);return;}
          parameter->setValueNotifyingHost(parameter->convertTo0to1(value));
          complete(true);
        })
      .withNativeFunction("freedomSetOscillator",
        [&p](const juce::Array<juce::var>& args,
             juce::WebBrowserComponent::NativeFunctionCompletion complete) {
          if (args.size() != 3 || !args[1].isString()) { complete(false); return; }
          const int oscillator = static_cast<int>(args[0]);
          if (oscillator < 1 || oscillator > 3) { complete(false); return; }
          const auto suffix = args[1].toString();
          if (suffix != "On" && suffix != "Wave" && suffix != "Volume"
              && suffix != "Octave" && suffix != "Semitone" && suffix != "Fine") {
            complete(false);
            return;
          }
          const auto prefix = juce::String("osc") + juce::String(oscillator);
          const auto id = suffix == "Volume" ? prefix + "Level" : prefix + suffix;
          auto* parameter = p.getValueTreeState().getParameter(id);
          if (parameter == nullptr) { complete(false); return; }
          const float value = static_cast<float>(static_cast<double>(args[2]));
          if (!std::isfinite(value)) { complete(false); return; }
          // Host automation receives the physical value converted to the
          // normalized [0,1] range required by JUCE parameters.
          parameter->setValueNotifyingHost(parameter->convertTo0to1(value));
          complete(true);
        })) {
 addAndMakeVisible(browser);
 setSize(1400, 920);
 // A giant percent-encoded data: URL is not reliable in embedded WebKit.
 // Load the original HTML as a real local document instead.
 const auto folder = juce::File::getSpecialLocation(juce::File::tempDirectory)
                       .getChildFile("Liberty-Freedom2-WebUI");
 if (!folder.createDirectory().wasOk()) {
   jassertfalse;
   return;
 }
 // Each plugin instance owns a separate document: no collisions between
 // AU, VST3, Standalone or multiple instances in the same host.
 const auto page = folder.getNonexistentChildFile("freedom2-ui", ".html", false);
 const juce::MemoryBlock bytes(BinaryData::index_html,
                               static_cast<size_t>(BinaryData::index_htmlSize));
 if (!page.replaceWithData(bytes.getData(), bytes.getSize())) {
   jassertfalse;
   return;
 }
 browser.goToURL(juce::URL(page).toString(true));
}
void Freedom2Editor::resized() { browser.setBounds(getLocalBounds()); }
""")
print("Original HTML embedded; OSC1-3 native bridge enabled.")
