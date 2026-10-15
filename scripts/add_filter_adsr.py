#!/usr/bin/env python3
"""Add independent per-voice filter ADSR to extracted Freedom 2 native sources."""
import sys
from pathlib import Path
root=Path(sys.argv[1])
def patch(path, old, new):
    p=root/path
    data=p.read_text()
    if data.count(old)!=1:
        raise RuntimeError(f"Expected one anchor in {path}: {old[:100]!r}, found {data.count(old)}")
    p.write_text(data.replace(old,new,1))
patch("native/include/FreedomDSP.h",
      "float resonance=0.2f; FilterMode filterMode=FilterMode::LP12;",
      "float resonance=0.2f; FilterMode filterMode=FilterMode::LP12;\n    float filterEnvAttack=0.01f, filterEnvDecay=0.25f, filterEnvSustain=0.25f, filterEnvRelease=0.3f, filterEnvAmount=0.0f;")
patch("native/include/FreedomDSP.h",
      "float velocity = 0, envelope = 0, lowpass = 0;",
      "float velocity = 0, envelope = 0, lowpass = 0;\n    Stage filterStage=Stage::Off;\n    float filterEnvelope=0.0f, filterReleaseStep=0.0f;")
patch("native/src/FreedomDSP.cpp",
      "params_.resonance = clamp(p.resonance,0.0f,1.0f);",
      """params_.resonance = clamp(p.resonance,0.0f,1.0f);
  params_.filterEnvAttack=clamp(p.filterEnvAttack,0.001f,12.0f);
  params_.filterEnvDecay=clamp(p.filterEnvDecay,0.001f,12.0f);
  params_.filterEnvSustain=clamp(p.filterEnvSustain,0.0f,1.0f);
  params_.filterEnvRelease=clamp(p.filterEnvRelease,0.001f,12.0f);
  params_.filterEnvAmount=clamp(p.filterEnvAmount,-4.5f,4.5f);""")
patch("native/src/FreedomDSP.cpp",
      "target->stage=Stage::Attack;target->channel=channel;target->note=note;",
      "target->stage=Stage::Attack;target->filterStage=Stage::Attack;target->channel=channel;target->note=note;")
patch("native/src/FreedomDSP.cpp",
      "void FreedomDSP::releaseVoice(Voice& v) noexcept {if(v.stage!=Stage::Off) {v.stage=Stage::Release;v.heldByPedal=false;}}",
      """void FreedomDSP::releaseVoice(Voice& v) noexcept {
  if(v.stage!=Stage::Off) {
    v.stage=Stage::Release;
    v.filterStage=Stage::Release;
    v.filterReleaseStep=v.filterEnvelope/static_cast<float>(params_.filterEnvRelease*sampleRate_);
    v.heldByPedal=false;
  }
}""")
patch("native/src/FreedomDSP.cpp",
      "float cutoffMod=0,pitchMod=0,ampMod=0;",
      """// Independent filter ADSR: no impact on the amplitude envelope.
        switch(v.filterStage) {
          case Stage::Attack:
            v.filterEnvelope+=static_cast<float>(1.0/(params_.filterEnvAttack*sampleRate_));
            if(v.filterEnvelope>=1.0f){v.filterEnvelope=1.0f;v.filterStage=Stage::Decay;}
            break;
          case Stage::Decay:
            v.filterEnvelope-=static_cast<float>((1.0f-params_.filterEnvSustain)/(params_.filterEnvDecay*sampleRate_));
            if(v.filterEnvelope<=params_.filterEnvSustain){v.filterEnvelope=params_.filterEnvSustain;v.filterStage=Stage::Sustain;}
            break;
          case Stage::Sustain:v.filterEnvelope=params_.filterEnvSustain;break;
          case Stage::Release:
            v.filterEnvelope=std::max(0.0f,v.filterEnvelope-v.filterReleaseStep);
            if(v.filterEnvelope<=0.0f)v.filterStage=Stage::Off;
            break;
          case Stage::Off:break;
        }
        float cutoffMod=v.filterEnvelope*params_.filterEnvAmount,pitchMod=0,ampMod=0;""")
patch("plugin/Source/PluginProcessor.cpp",
      'f("bendRange","Bend Range",0,24,2);',
      """f("filterEnvAttack","Filter Env Attack",.001f,12,.01f);f("filterEnvDecay","Filter Env Decay",.001f,12,.25f);f("filterEnvSustain","Filter Env Sustain",0,1,.25f);f("filterEnvRelease","Filter Env Release",.001f,12,.3f);f("filterEnvAmount","Filter Env Amount",-4.5f,4.5f,0);f("bendRange","Bend Range",0,24,2);""")
patch("plugin/Source/PluginProcessor.cpp",
      'p.resonance=val("resonance");',
      'p.resonance=val("resonance");p.filterEnvAttack=val("filterEnvAttack");p.filterEnvDecay=val("filterEnvDecay");p.filterEnvSustain=val("filterEnvSustain");p.filterEnvRelease=val("filterEnvRelease");p.filterEnvAmount=val("filterEnvAmount");')
print("Filter ADSR native DSP and host parameters installed; default Amount=0 preserves existing sound.")
