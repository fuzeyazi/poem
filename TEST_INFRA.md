# Testing Infrastructure & Methodology Specification (Phase 1)

## 1. Overview & Testing Philosophy

The testing infrastructure for Phase 1 Cultural Showcase & Interactive Feature Matrix (`poetry-spring2`) is architected as a **requirement-driven, opaque-box automated test suite**.

Rather than testing implementation internals, the test suite strictly enforces the interface contracts and functional requirements specified in `ORIGINAL_REQUEST.md` and `PROJECT.md`. The design adheres to a **4-Tier Test Design Methodology**, guaranteeing feature coverage, resilience against boundary conditions, cross-module cohesion, and realistic real-world user flows.

---

## 2. Test Environment & Toolchain

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Test Runner** | Vitest | `^2.1.9` | ESM-native fast test execution with multi-threading and watch mode |
| **DOM Environment** | jsdom | `^25.0.1` | Headless W3C DOM & HTML5 environment for component testing |
| **Component Testing** | `@vue/test-utils` | `^2.5.1` | Mounting, event triggers, slot validation, and DOM inspection |
| **State Management** | Pinia | `^3.0.0` | Store instantiation and state persistence lifecycle verification |
| **Type Verification** | TypeScript + vue-tsc | `^5.6.2` | Static type checking and interface contract conformance |
| **Audio Synthesis Polyfill** | Custom Web Audio Mock | Synthetic | Headless AudioContext, GainNode, Oscillator, and BiquadFilter emulation |
| **Export & Canvas Polyfill** | Custom Fonts & Image Mock | Synthetic | `document.fonts.ready` and foreignObject / SVG rasterization stubs |

---

## 3. Directory Layout

```
E:\javatexts\poetry-spring2\
├── TEST_INFRA.md                      # Testing infrastructure & framework architecture (this file)
├── TEST_READY.md                      # Test suite readiness, execution instructions, & coverage checklist
├── frontend/
│   ├── tests/
│   │   ├── e2e/
│   │   │   └── phase1_e2e.spec.ts    # Comprehensive 4-Tier E2E test suite (Tiers 1-4)
│   │   ├── card/                     # M1 Unit tests (ClassicalSeal, PoemCardRenderer, etc.)
│   │   ├── soundscape/               # M2 Unit tests (SoundscapeEngine, store, widget)
│   │   ├── allusion/                 # M3 Unit tests (Allusion matcher, micro-card, seeds)
│   │   ├── components/               # Base UI component unit tests
│   │   ├── router/                   # Route guard unit tests
│   │   └── store/                    # Pinia user store unit tests
```

---

## 4. 4-Tier Test Design Methodology

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 4: Real-World Application Workloads                    │
│ Full scholar journey: Reading, Audio, Allusions, Seal & Card │
├─────────────────────────────────────────────────────────────┤
│ Tier 3: Cross-Feature Interactions                          │
│ Soundscape + Card Modal, Tokenized Verses + Card Renderer   │
├─────────────────────────────────────────────────────────────┤
│ Tier 2: Boundary & Corner Cases                             │
│ Zero/Max volume, empty strings, 1/2/4 char seals, rapid hops│
├─────────────────────────────────────────────────────────────┤
│ Tier 1: Feature Coverage (>=5 test cases per feature)       │
│ R1 Card & Seal, R2 Soundscapes, R3 Allusions, R4 API / Store│
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Tier 1: Feature Coverage (>= 5 cases per feature)
- **R1.1 Card Vertical Typography & Punctuation**:
  - CSS `writing-mode: vertical-rl` and `text-orientation: mixed` structural adherence.
  - Classical punctuation stripping (removing `，。！？；：“”‘’（）《》`).
  - Traditional vs. Simplified conversion (s2t dictionary integration).
  - Four-layer古籍 layout sequence: Title column -> Poem stanzas -> Colophon -> Seal placement.
  - Three distinct classical themes (`澄素宣纸`, `墨夜泥金`, `朱丝阑格`).
- **R1.2 Classical Seal Generation**:
  - Square vs. Oval seal boundary generation.
  - 朱文 (阳刻 / Yang carving, red strokes on transparent/paper background) vs. 白文 (阴刻 / Yin carving, white strokes on solid cinnabar background).
  - 1-character, 2-character, 3-character, and 4-character layouts.
  - Classical 2x2 counter-clockwise order: Top-Right (char 1) -> Bottom-Right (char 2) -> Top-Left (char 3) -> Bottom-Left (char 4).
  - Stone erosion filter (`<feTurbulence>`, `<feDisplacementMap>`) and cinnabar gradient (`#b83828` -> `#8f2417`).
- **R1.3 High-DPI Export Pipeline**:
  - `exportCardImage` execution contract with `pixelRatio: 3`.
  - `document.fonts.ready` asynchronous gate execution prior to rasterization.
  - Generated image filename format matching `诗词卡片-{author}-{title}.png`.
  - Clean error handling during canvas failure or DOM detach.
- **R2.1 Soundscape Player Controls & 3 Scenes**:
  - Procedural synthesis for 3 scenes: "雨打芭蕉" (Rain on Banana Leaves), "深山古寺暮钟" (Mountain Temple Evening Bell), and "小桥流水" (Flowing Creek Stream).
  - Play, pause, volume (0.0 to 1.0 / 0% to 100%), and mute/unmute toggling.
  - Smooth 1.2s cross-fading parameter ramp between scenes.
  - Master gain attenuation and node disconnection cleanup.
- **R3.1 Allusion Keyword Recognition & Tokenization**:
  - Tokenization of poem text into structured `VerseToken[]` (`text`, `isAllusion`, `allusion`).
  - Preservation of letter spacing, line height, and line break structure.
  - Accurate extraction of classical allusion metadata: name, origin document, origin quote, story background, sentiment, and related quotes.
  - Scholar gold dashed underline visual demarcation (`.allusion-mark`).
- **R4.1 Backend Allusion REST API Endpoints**:
  - `GET /user/allusion/list` returning `Result<List<Allusion>>` with HTTP 200 and standard response wrapper (`code === 200` or `1`).
  - `GET /user/allusion/{id}` returning individual allusion details.
  - Non-existent ID returning 404 or gracefully handled empty/error result.
  - Caching headers and resilient error fallback data.

### 4.2 Tier 2: Boundary & Corner Cases (>= 5 cases per feature)
- **Extreme Text Lengths**:
  - Single-line short rhesis / aphorism (5~7 characters).
  - Long narrative songs (50+ lines, e.g. "春江花月夜", "长恨歌").
  - Empty or null poem title / author / dynasty / verse content fallback without crashes.
- **Seal Character Count Extremes**:
  - Single character (centered, padded border).
  - Two characters (vertical column).
  - Three characters (custom classical balance).
  - Four characters (2x2 counter-clockwise square matrix).
  - String overflow (>4 chars, clamped or truncated gracefully).
- **Audio Control Extremes**:
  - Zero volume (volume = 0, silent without node error).
  - Max volume (volume = 100, clamped without clipping).
  - Rapid play/pause toggling (preventing overlapping audio contexts or unhandled Promise rejections).
  - Rapid scene switching (preventing cross-fade memory leaks and node accumulation).
- **Allusion Punctuation & Boundary Parsing**:
  - Allusion at the very beginning of a line.
  - Allusion at the very end of a line followed immediately by comma/period.
  - Allusions wrapped in quotes (`“折柳”`).
  - Overlapping keywords (longest match priority, e.g. "折柳枝" over "折柳").
- **Cold-Start Autoplay Policy Adherence**:
  - Pinia store initialized with `isPlaying: false` on cold load regardless of previous session state.
  - No `AudioContext` autoplay attempt before user-initiated interaction.

### 4.3 Tier 3: Cross-Feature Interactions
- **Soundscape + Card Modal Interaction**:
  - Continuous ambient soundscape playback while opening, configuring, and previewing Poem Card Modal.
  - Zero audio glitching or frame drop during modal render and theme switching.
- **Allusions + Card Generator Interaction**:
  - Loading a poem containing allusions into PoemCardRenderer; card correctly renders verses with or without allusion marks based on export settings.
- **Route Switching + Audio Continuity**:
  - Soundscape player mounted in root `App.vue` persisting across simulated route transitions (`/poem/:id` -> `/rhesis` -> `/review`).

### 4.4 Tier 4: Real-World Application Workloads
- **Full Scholar Journey**:
  - Scholar opens "春江花月夜", activates "雨打芭蕉" ambient rain soundscape, adjusts volume to 45%.
  - Hovers over "沧海" and "折柳" cultural allusions to study their origin and quotes.
  - Opens Card Generator, selects "墨夜泥金" midnight theme, customizes seal with name "东坡居士" in 朱文/阳刻.
  - Triggers 300DPI export pipeline, generating the high-res card artifact.

---

## 5. Authoritative Expected Output Derivation

All expected values are derived from explicit specifications in `ORIGINAL_REQUEST.md` and `PROJECT.md`:
1. **Seal Counter-Clockwise Matrix**:
   - For input `[c0, c1, c2, c3]`:
     - Top-Right: `c0`
     - Bottom-Right: `c1`
     - Top-Left: `c2`
     - Bottom-Left: `c3`
2. **Punctuation Filtering**:
   - Regex: `/[，。；：？！、,.!?;:："'“”‘’（）()《》〈〉·—…\-—\s]/g`
   - All punctuation characters removed while preserving Chinese glyphs and stanza separation.
3. **Soundscape Scenes**:
   - `rain` ("雨打芭蕉"), `temple` ("古寺暮钟"), `creek` ("小桥流水").
4. **Allusion Tokens**:
   - Non-allusion segments produce `{ type: 'text', content: string }`.
   - Matched segments produce `{ type: 'allusion', content: string, allusion: Allusion }`.

---

## 6. Execution Commands

```bash
# Execute the full Phase 1 E2E test suite
cmd /c "cd /d E:\javatexts\poetry-spring2\frontend && npm test -- tests/e2e/phase1_e2e.spec.ts"

# Run all frontend tests
cmd /c "cd /d E:\javatexts\poetry-spring2\frontend && npm test"

# Run vitest in watch mode for development
cmd /c "cd /d E:\javatexts\poetry-spring2\frontend && npm run test:watch"
```
