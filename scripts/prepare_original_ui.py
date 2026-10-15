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
          // Host automation and project restoration win any simultaneous edit.
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
