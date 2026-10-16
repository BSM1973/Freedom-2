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
bridge = """
<script id="liberty-native-oscillators-bridge">
(() => {
  const fields = ['On','Wave','Volume','Octave','Semitone','Fine'];
  let lastUI = new Map();
  let lastNative = new Map();
  let initialized = false;
  let busy = false;
  async function sync() {
    if (busy) return;
    const backend = window.__JUCE__?.backend;
    const ui = window.LibertyFreedomUI;
    const get = backend?.getNativeFunction?.('freedomGetOscillators');
    const set = backend?.getNativeFunction?.('freedomSetOscillator');
    if (!get || !set || !ui?.getParameters || !ui?.setParameter) return;
    busy = true;
    try {
      const native = await get();
      if (!Array.isArray(native) || native.length !== 18) return;
      const state = ui.getParameters();
      for (let osc = 1; osc <= 3; osc++) {
        for (let i = 0; i < fields.length; i++) {
          const key = 'Osc_' + osc + '_' + fields[i];
          const current = Number(state[key]);
          const host = Number(native[(osc-1)*fields.length+i]);
          if (!Number.isFinite(current) || !Number.isFinite(host)) continue;
          const previousUI = lastUI.get(key);
          const previousNative = lastNative.get(key);
          const uiChanged = previousUI !== undefined
            && Math.abs(current-previousUI)>0.00001;
          const hostChanged = previousNative !== undefined
            && Math.abs(host-previousNative)>0.00001;
          // Host automation wins simultaneous edits.
          if (!initialized || hostChanged || !uiChanged) {
            if (Math.abs(current-host)>0.00001) ui.setParameter(key,host);
            lastUI.set(key,host);
            lastNative.set(key,host);
          } else if (Math.abs(current-host)>0.00001) {
            const ok = await set(osc,fields[i],current);
            if (ok) {
              lastUI.set(key,current);
              lastNative.set(key,current);
            }
          } else {
            lastUI.set(key,current);
            lastNative.set(key,host);
          }
        }
      }
      initialized = true;
    } catch (_) {
      // Keep the original UI usable if a host does not expose native functions.
    } finally { busy = false; }
  }
  setInterval(sync, 150);
  // Filter controls: preserve original HTML and synchronize existing
  // native cutoff/resonance values without introducing visual elements.
  const filterKeys = [['Filter_Cutoff','cutoff'],['Filter_Resonance','resonance'],['Filter_Type','filterMode']];
  let filterReady = false;
  let filterBusy = false;
  const filterUI = new Map(), filterHost = new Map();
  async function syncFilter() {
    if (filterBusy) return;
    const ui = window.LibertyFreedomUI;
    const backend = window.__JUCE__?.backend;
    const get = backend?.getNativeFunction?.('freedomGetFilter');
    const set = backend?.getNativeFunction?.('freedomSetFilter');
    if (!get || !set || !ui?.getParameters || !ui?.setParameter) return;
    filterBusy = true;
    try {
      const native = await get();
      if (!Array.isArray(native) || native.length !== 3) return;
      const state = ui.getParameters();
      for (let i=0;i<filterKeys.length;i++) {
        const [key,id] = filterKeys[i];
        const current = Number(state[key]), host = Number(native[i]);
        if (!Number.isFinite(current) || !Number.isFinite(host)) continue;
        const uiChanged = filterUI.has(key) && Math.abs(current-filterUI.get(key))>0.00001;
        const hostChanged = filterHost.has(key) && Math.abs(host-filterHost.get(key))>0.00001;
        if (!filterReady || hostChanged || !uiChanged) {
          if (Math.abs(current-host)>0.00001) ui.setParameter(key,host);
          filterUI.set(key,host);
          filterHost.set(key,host);
        } else if (Math.abs(current-host)>0.00001) {
          if (await set(id,current)) {filterUI.set(key,current);filterHost.set(key,current);}
        } else {filterUI.set(key,current);filterHost.set(key,host);}
      }
      filterReady=true;
    } catch (_) {
      // Keep the original UI operational if native integration is unavailable.
    } finally {filterBusy=false;}
  }
  setInterval(syncFilter,150);
  // Dedicated filter ADSR bridge; original controls and CSS remain untouched.
  const envKeys = [
    ['Filter_Envelope_Attack','filterEnvAttack'],
    ['Filter_Envelope_Decay','filterEnvDecay'],
    ['Filter_Envelope_Sustain','filterEnvSustain'],
    ['Filter_Envelope_Release','filterEnvRelease'],
    ['Filter_Envelope_Amount','filterEnvAmount']
  ];
  const envUI = new Map(), envHost = new Map();
  let envReady=false, envBusy=false;
  async function syncFilterEnvelope() {
    if(envBusy)return;
    const ui=window.LibertyFreedomUI;
    const backend=window.__JUCE__?.backend;
    const get=backend?.getNativeFunction?.('freedomGetFilterEnvelope');
    const set=backend?.getNativeFunction?.('freedomSetFilterEnvelope');
    if(!get||!set||!ui?.getParameters||!ui?.setParameter)return;
    envBusy=true;
    try {
      const values=await get();
      if(!Array.isArray(values)||values.length!==envKeys.length)return;
      const state=ui.getParameters();
      for(let i=0;i<envKeys.length;i++){
        const [key,id]=envKeys[i];
        const current=Number(state[key]),host=Number(values[i]);
        if(!Number.isFinite(current)||!Number.isFinite(host))continue;
        const uiChanged=envUI.has(key)&&Math.abs(current-envUI.get(key))>0.00001;
        const hostChanged=envHost.has(key)&&Math.abs(host-envHost.get(key))>0.00001;
        if(!envReady||hostChanged||!uiChanged){
          if(Math.abs(current-host)>0.00001)ui.setParameter(key,host);
          envUI.set(key,host);envHost.set(key,host);
        }else if(Math.abs(current-host)>0.00001){
          if(await set(id,current)){envUI.set(key,current);envHost.set(key,current);}
        }else{envUI.set(key,current);envHost.set(key,host);}
      }
      envReady=true;
    }catch(_){/* Native bridge optional in browser preview. */}
    finally{envBusy=false;}
  }
  setInterval(syncFilterEnvelope,150);
})();
</script>
"""
# Visual-only cleanup requested for Freedom 2. Keep native DSP and preset logic intact.
ui_cleanup = """
<script id="liberty-ui-cleanup">
(() => {
  const norm = text => (text || '').replace(/\\s+/g, ' ').trim().toUpperCase();
  const findLabel = (label) => [...document.querySelectorAll('button, [role="button"], a, span, div, small')]
    .find(el => el.children.length === 0 && norm(el.textContent) === label);
  const closestButton = el => el?.closest('button, [role="button"], a') || el;
  const hideControl = label => {
    const el = findLabel(label);
    if (el) closestButton(el).style.setProperty('display', 'none', 'important');
  };
  function removeBand(label, otherLabel) {
    const el = findLabel(label);
    if (!el) return;
    let node = el;
    // Find the narrowest full-width strip containing this label, but do not
    // ascend into the main tab content or the synthesizer's oscillator panels.
    for (let i=0; i<7 && node.parentElement; i++) {
      const parent=node.parentElement;
      const rect=parent.getBoundingClientRect();
      const viewport=document.documentElement.clientWidth || innerWidth;
      if (rect.width >= viewport*0.70 && rect.height > 20 && rect.height < 125) {
        if (!otherLabel || norm(parent.textContent).includes(otherLabel)) {
          parent.style.setProperty('display','none','important');
          return;
        }
      }
      node=parent;
    }
  }
  function cleanup() {
    const shortcuts = closestButton(findLabel('? RACCOURCIS') || findLabel('RACCOURCIS'));
    const audit = closestButton(findLabel('AUDIT UI'));
    if (shortcuts && audit && shortcuts !== audit) {
      // Replace AUDIT UI in its existing toolbar without changing its listeners.
      audit.replaceWith(shortcuts);
    } else if (audit) {
      audit.style.setProperty('display','none','important');
    }
    hideControl('WEB AUDIO EXPERIMENTAL');
    removeBand('FREEDOM 2 · UI V1.6', 'RACCOURCIS');
    removeBand('UI QUALITY CHECK V1.7', 'VÉRIFIER LES 4 ONGLETS');
    removeBand('FREEDOM 2 · UI V2.0', 'CONTRÔLER LES COMMANDES');
    removeBand('ENGINE · FREEDOM 2', 'AUDIOWORKLET EXPERIMENTAL');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', cleanup, {once:true});
  else cleanup();
  // Apply once more if the UI constructs its toolbars asynchronously.
  window.addEventListener('load', cleanup, {once:true});
})();
</script>
"""
if "</body>" not in source_html:
    raise RuntimeError("Original HTML has no body closing tag")
(assets/"index.html").write_text(source_html.replace("</body>",ui_cleanup+bridge+"</body>",1))

s=cmake.read_text()
s=s.replace("JUCE_WEB_BROWSER=0", "JUCE_WEB_BROWSER=1")
if "juce_add_binary_data(Freedom2WebUI" not in s:
    s += """
juce_add_binary_data(Freedom2WebUI SOURCES WebUI/index.html)
target_link_libraries(Freedom2 PRIVATE Freedom2WebUI)
"""
cmake.write_text(s)
processor_h=plugin/"Source/PluginProcessor.h"
header=processor_h.read_text()
if "getValueTreeState()" not in header:
    header=header.replace("public:", "public:\n  juce::AudioProcessorValueTreeState& getValueTreeState() noexcept { return apvts; }",1)
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
