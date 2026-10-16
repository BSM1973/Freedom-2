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
ui_cleanup = """
<style id="liberty-ui-cleanup-style">
/* Cleanup-only styling: the oscillator and preset layouts remain untouched. */
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
    // Relocate the existing signal monitor (including animated level LEDs) to
    // the former version-label position, and remove its now-empty dedicated row.
    const version=nodes().find(el=>el.children.length===0 &&
      normalize(el.textContent).includes('FREEDOM 2 · PREMIUM UI V0.9'));
    const signal=nodes().find(el=>el.children.length===0 &&
      normalize(el.textContent)==='LIBERTY · SIGNAL MONITOR');
    if(version && signal && !document.getElementById('liberty-relocated-signal')) {
      const strip=signal.parentElement;
      const level=strip && [...strip.querySelectorAll('div,span')].find(el=>
        el !== signal && el.children.length >= 6 && el.children.length <= 32 &&
        el.querySelectorAll('span,div').length >= 6 &&
        el.getBoundingClientRect().width < 320);
      const newTitle=document.createElement('span');
      newTitle.id='liberty-relocated-signal';
      newTitle.textContent='LIBERTY · SIGNAL MONITOR';
      version.replaceWith(newTitle);
      if(level) {
        newTitle.style.display='inline-flex';
        newTitle.style.alignItems='center';
        newTitle.style.gap='12px';
        newTitle.appendChild(level);
      }
      // Preserve the density control by placing it beside the relocated monitor.
      const density=strip?.querySelector('button');
      if(density && normalize(density.textContent).includes('DENSITÉ')) newTitle.appendChild(density);
      if(strip && !normalize(strip.textContent).includes('OSCILLATOR')) {
        const row=strip.parentElement;
        if(row && row.getBoundingClientRect().height < 90 &&
           !normalize(row.textContent).includes('NOM DU PRESET PERSONNEL')) hide(row);
        else hide(strip);
      }
    }


    // The density control is not part of the new compact signal monitor.
    for(const button of document.querySelectorAll('button,[role="button"]')) {
      if(normalize(button.textContent).startsWith('DENSITÉ')) hide(button);
    }
    // Restore the *live* meter DOM from the hidden original signal strip.
    const relocated=document.getElementById('liberty-relocated-signal');
    if(relocated && !relocated.querySelector('[data-liberty-live-meter]')) {
      const oldLabel=nodes().find(el=>el.children.length===0 &&
        normalize(el.textContent)==='LIBERTY · SIGNAL MONITOR' && el!==relocated);
      const oldRow=oldLabel?.parentElement?.parentElement;
      if(oldRow) {
        const candidates=[...oldRow.querySelectorAll('div,span')].filter(el=>{
          const children=[...el.children];
          if(children.length<8 || children.length>40) return false;
          if(children.some(c=>c.matches('button,input,select'))) return false;
          return children.every(c=>c.children.length<=1);
        });
        const meter=candidates.sort((a,b)=>{
          const score=el=>/meter|level|led|bar|signal|vu/i.test(String(el.className))?1:0;
          return score(b)-score(a);
        })[0];
        if(meter) {
          meter.dataset.libertyLiveMeter='true';
          meter.style.setProperty('display','inline-flex','important');
          meter.style.alignItems='center';
          meter.style.flexShrink='0';
          relocated.appendChild(meter);
        }
      }
      relocated.style.display='inline-flex';
      relocated.style.alignItems='center';
      relocated.style.gap='12px';
      relocated.style.whiteSpace='nowrap';
      relocated.style.flexShrink='0';
      // Allow the parameter search and adjacent actions to shift right.
      const toolbar=relocated.parentElement;
      if(toolbar) {toolbar.style.display='flex';toolbar.style.alignItems='center';toolbar.style.gap='10px';}
    }
    // Select waveform rows by their four visible labels, regardless of whether
    // the original UI uses <button>, <div> or <span> for its controls.
    // The first row below each oscillator preview is the LARGE primary selector.
    // The second is the SMALL duplicate and must be removed.
    const waveNames=['SINE','SAW','PULSE','TRI'];
    const allElements=[...document.querySelectorAll('*')];
    const waveformRows=allElements.filter(parent=>{
      if(parent.children.length!==4) return false;
      return waveNames.every((name,index)=>
        normalize(parent.children[index].textContent)===name);
    }).filter(parent=>!parent.querySelector('[data-liberty-primary-wave]'));
    // Scope to each oscillator by its exact heading, then use DOM order
    // (not dimensions or fragile CSS classes) to distinguish the two rows.
    for(let number=1;number<=3;number++){
      const heading=allElements.find(el=>el.children.length===0 &&
        normalize(el.textContent)==='OSCILLATOR 0'+number);
      if(!heading) continue;
      let card=heading.parentElement;
      while(card && waveformRows.filter(row=>card.contains(row)).length<2)
        card=card.parentElement;
      if(!card) continue;
      const matched=waveformRows.filter(row=>card.contains(row));
      if(matched.length!==2) continue; // fail safely, never remove the primary
      const [primary,duplicate]=matched.sort((x,y)=>
        x.compareDocumentPosition(y)&Node.DOCUMENT_POSITION_FOLLOWING?-1:1);
      primary.hidden=false;
      primary.style.removeProperty('display');
      primary.dataset.libertyPrimaryWave='true';
      hide(duplicate);
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
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',cleanup,{once:true});
  else cleanup();
  window.addEventListener('load',cleanup,{once:true});
  // React/embedded UI may paint the bottom panels after DOMContentLoaded.
  // Bounded rechecks (no MutationObserver and no infinite render loop).
  [150,650,1800].forEach(delay=>setTimeout(()=>{
    try { cleanup(); } catch(error) { console.warn('Liberty UI cleanup:',error); }
  },delay));

})();
</script>
"""
# Synchronize the rest of the native engine, including preset recalls.
# The existing OSC and filter bridges retain their specialized mappings.
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
  let last = new Map(), pending = false;
  async function push() {
    if(pending)return;
    const ui=window.LibertyFreedomUI;
    const backend=window.__JUCE__?.backend;
    const set=backend?.getNativeFunction?.('freedomSetParameter');
    const get=backend?.getNativeFunction?.('freedomGetParameter');
    if(!ui?.getParameters||!set||!get)return;
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
          if(Number.isFinite(actual))last.set(key,v);
        }
      }
    } catch(e) { console.error('Freedom 2 native parameter sync failed:',e); }
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
(assets/"index.html").write_text(source_html.replace("</body>",ui_cleanup+bridge+full_bridge+keyboard_bridge+"</body>",1))

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
