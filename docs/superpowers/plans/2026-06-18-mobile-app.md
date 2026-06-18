# AIScore 모바일 앱 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** iOS/Android 공통 모바일 앱으로 SATB 찬송가 악보를 촬영·업로드하고, 4성부 음원을 파트별로 선택해 악보와 동기화하여 재생한다.

**Architecture:** FastAPI 백엔드(기존)에 성부별 WAV + timing.json API를 추가하고, React Native + Expo 모바일 앱 3개 화면(홈·처리중·플레이어)으로 구성한다. 악보 렌더링은 WebView + OSMD, 오디오는 expo-av 멀티트랙, 성부→타임라인 동기화는 postMessage 채널로 연결한다.

**Tech Stack:** FastAPI(백엔드, 기존) · React Native 0.74 + Expo SDK 51 · expo-router v3 · expo-av · expo-image-picker · React Native WebView · OSMD(OpenSheetMusicDisplay) · TypeScript 5

## Global Constraints

- Python: conda 환경 `aiscore` (py3.10), `/opt/miniconda3/envs/aiscore/bin/python`
- 의존성 단방향: domain → stages → orchestration → api
- 새 외부 모델/엔진 = 새 어댑터 파일 추가 (기존 파일 최소 수정)
- 외부 입력 경로(업로드 포함) 변경 시 security-reviewer 필수
- 응답·주석은 한국어 기본
- 1단계 스코프: 음표→"우"→믹싱 (가사 관련 YAGNI)
- `data/`, 모델, WAV 파일 git 커밋 금지

---

## 화면 흐름

```
[HomeScreen]
  악보 촬영 / 갤러리 선택
  업로드 버튼
       ↓ createJob(image)
[ProcessingScreen]
  단계별 진행 바 (omr → parsing → synth → mixing)
  2초 폴링
       ↓ status == "done"
[PlayerScreen]
  ┌─────────────────────────┐
  │  ScoreViewer (악보)      │  ← WebView + OSMD
  │  (재생 위치 하이라이팅)   │
  ├─────────────────────────┤
  │  [ S ] [ A ] [ T ] [ B ]│  ← PartSelector
  ├─────────────────────────┤
  │  ◀  ▶  ──●──────  00:18 │  ← PlaybackControls
  └─────────────────────────┘
```

---

## 파일 구조

### 백엔드 변경 (최소)

```
backend/app/
  orchestration/
    job.py              ← voice_paths, timing_path 필드 추가
    orchestrator.py     ← 성부별 WAV 저장 경로 + timing.json 생성
  api/
    schemas.py          ← voice_paths, timing_path 스키마 추가
    routes/jobs.py      ← GET /jobs/{id}/audio/{voice}, GET /jobs/{id}/timing
  stages/svs/
    vowel_synth_adapter.py  ← timing 메타데이터 반환 (부수효과 없는 추가)
backend/tests/
  test_timing_api.py    ← timing 엔드포인트 단위 테스트
```

### 모바일 앱 (신규)

```
mobile/
  app/
    _layout.tsx             ← Expo Router 루트 레이아웃
    index.tsx               ← HomeScreen
    processing/[id].tsx     ← ProcessingScreen
    player/[id].tsx         ← PlayerScreen
  components/
    PartSelector.tsx        ← S/A/T/B 토글 버튼
    AudioMixer.tsx          ← expo-av 멀티트랙 관리
    ScoreViewer.tsx         ← WebView + OSMD 래퍼
    PlaybackControls.tsx    ← 재생/정지/시크바
  lib/
    api.ts                  ← FastAPI 클라이언트
    timing.ts               ← 타이밍 계산 유틸
  assets/
    score-viewer.html       ← WebView에서 로드할 OSMD 호스트 페이지
  package.json
  app.json
  tsconfig.json
```

---

## Task 1: 백엔드 — 성부별 WAV 경로 저장 + API

**Files:**
- Modify: `backend/app/orchestration/job.py`
- Modify: `backend/app/orchestration/orchestrator.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes/jobs.py`
- Test: `backend/tests/test_voice_api.py`

**Interfaces:**
- Produces: `GET /jobs/{id}/audio/{voice}` → FileResponse (WAV)
- voice 값: `soprano | alto | tenor | bass`

- [ ] **Step 1: job.py에 voice_paths 필드 추가**

```python
# backend/app/orchestration/job.py
@dataclass
class Job:
    id: str
    status: str = "queued"
    failed_stage: str | None = None
    error: str | None = None
    result_path: str | None = None       # choir.wav (기존)
    score_path: str | None = None        # MusicXML (기존)
    voice_paths: dict[str, str] = field(default_factory=dict)  # 신규
    timing_path: str | None = None       # 신규
```

- [ ] **Step 2: 테스트 작성**

```python
# backend/tests/test_voice_api.py
from fastapi.testclient import TestClient
from app.main import app
from app.storage.store import store
from app.orchestration.job import Job

def test_audio_voice_not_found(tmp_path, isolate_store):
    client = TestClient(app)
    store._jobs["j1"] = Job(id="j1", status="done")
    resp = client.get("/jobs/j1/audio/soprano")
    assert resp.status_code == 404

def test_audio_voice_returns_wav(tmp_path, isolate_store):
    client = TestClient(app)
    wav = tmp_path / "soprano.wav"
    wav.write_bytes(b"RIFF")
    store._jobs["j1"] = Job(
        id="j1", status="done",
        voice_paths={"soprano": str(wav)}
    )
    resp = client.get("/jobs/j1/audio/soprano")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_voice_api.py -v
```
Expected: FAIL (엔드포인트 없음)

- [ ] **Step 4: routes/jobs.py에 엔드포인트 추가**

```python
# backend/app/api/routes/jobs.py 에 추가
from fastapi import Path as FPath

VOICE_NAMES = {"soprano", "alto", "tenor", "bass"}

@router.get("/{job_id}/audio/{voice}")
async def get_voice_audio(
    job_id: str,
    voice: str = FPath(..., pattern="^(soprano|alto|tenor|bass)$"),
):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    path = job.voice_paths.get(voice)
    if not path or not Path(path).exists():
        raise HTTPException(404, f"{voice} not ready")
    return FileResponse(path, media_type="audio/wav")
```

- [ ] **Step 5: schemas.py 업데이트**

```python
# backend/app/api/schemas.py JobState에 추가
class JobState(BaseModel):
    id: str
    status: str
    failed_stage: str | None = None
    error: str | None = None
    result_path: str | None = None
    score_path: str | None = None
    voice_paths: dict[str, str] = {}   # 신규
    timing_path: str | None = None     # 신규
```

- [ ] **Step 6: orchestrator.py — 성부별 WAV 경로 저장**

```python
# backend/app/orchestration/orchestrator.py
# synth 단계 완료 후 voice_paths 저장
async def _run_synth(self, job: Job, score: Score, job_dir: Path) -> dict[str, Path]:
    voice_wavs: dict[str, Path] = {}
    tasks = []
    for voice_name, voice in score.voices.items():
        out = job_dir / f"{voice_name.value}.wav"
        tasks.append((voice_name, out))
    # 기존 병렬 synth 로직 유지, 완료 후:
    for vn, path in zip(...):
        voice_wavs[vn.value] = path
    job.voice_paths = {k: str(v) for k, v in voice_wavs.items()}
    return voice_wavs
```

- [ ] **Step 7: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_voice_api.py -v
```
Expected: 2 PASSED

- [ ] **Step 8: 전체 테스트 회귀 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest -v
```
Expected: 모두 PASSED (기존 테스트 영향 없음)

- [ ] **Step 9: 커밋**

```bash
git add backend/app/orchestration/job.py \
        backend/app/orchestration/orchestrator.py \
        backend/app/api/schemas.py \
        backend/app/api/routes/jobs.py \
        backend/tests/test_voice_api.py
git commit -m "feat(api): 성부별 WAV 엔드포인트 + voice_paths 저장"
```

---

## Task 2: 백엔드 — timing.json 생성 + API

**Files:**
- Create: `backend/app/stages/svs/timing.py`
- Modify: `backend/app/orchestration/orchestrator.py`
- Modify: `backend/app/api/routes/jobs.py`
- Test: `backend/tests/test_timing.py`

**Interfaces:**
- Produces: `GET /jobs/{id}/timing` → JSON
- timing.json 구조:
```json
{
  "bpm": 80,
  "voices": {
    "soprano": [
      {"pitch": "F4", "start_sec": 0.0, "end_sec": 0.75, "index": 0},
      {"pitch": "A4", "start_sec": 0.75, "end_sec": 1.5,  "index": 1}
    ]
  }
}
```

- [ ] **Step 1: timing.py 작성**

```python
# backend/app/stages/svs/timing.py
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from app.domain.score import Score, VoiceName

DEFAULT_BPM = 80

@dataclass
class NoteEvent:
    pitch: str | None   # None = 쉼표
    start_sec: float
    end_sec: float
    index: int

def build_timing(score: Score, bpm: int = DEFAULT_BPM) -> dict:
    sec_per_quarter = 60.0 / bpm
    voices: dict[str, list[dict]] = {}
    for vname, voice in score.voices.items():
        events = []
        t = 0.0
        for i, note in enumerate(voice.notes):
            dur = note.quarter_length * sec_per_quarter
            events.append({
                "pitch": note.pitch,
                "start_sec": round(t, 4),
                "end_sec": round(t + dur, 4),
                "index": i,
            })
            t += dur
        voices[vname.value] = events
    return {"bpm": bpm, "voices": voices}

def write_timing(score: Score, out_path: Path, bpm: int = DEFAULT_BPM) -> Path:
    data = build_timing(score, bpm)
    out_path.write_text(json.dumps(data, ensure_ascii=False))
    return out_path
```

- [ ] **Step 2: 테스트 작성**

```python
# backend/tests/test_timing.py
from app.domain.score import Score, Voice, Note, VoiceName
from app.stages.svs.timing import build_timing

def _score():
    return Score(voices={
        VoiceName.SOPRANO: Voice(
            name=VoiceName.SOPRANO,
            notes=[Note(pitch="F4", quarter_length=1.0),
                   Note(pitch="A4", quarter_length=2.0)],
        )
    })

def test_timing_start_end():
    t = build_timing(_score(), bpm=60)
    notes = t["voices"]["soprano"]
    assert notes[0]["start_sec"] == 0.0
    assert notes[0]["end_sec"] == 1.0    # 1박 @ 60BPM = 1초
    assert notes[1]["start_sec"] == 1.0
    assert notes[1]["end_sec"] == 3.0    # 2박

def test_timing_pitch():
    t = build_timing(_score(), bpm=60)
    assert t["voices"]["soprano"][0]["pitch"] == "F4"

def test_timing_api(isolate_store, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.storage.store import store
    from app.orchestration.job import Job
    import json
    tj = tmp_path / "timing.json"
    tj.write_text(json.dumps({"bpm": 80, "voices": {}}))
    store._jobs["j1"] = Job(id="j1", status="done", timing_path=str(tj))
    resp = TestClient(app).get("/jobs/j1/timing")
    assert resp.status_code == 200
    assert resp.json()["bpm"] == 80
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_timing.py -v
```
Expected: FAIL

- [ ] **Step 4: /timing 엔드포인트 추가**

```python
# backend/app/api/routes/jobs.py 에 추가
@router.get("/{job_id}/timing")
async def get_timing(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if not job.timing_path or not Path(job.timing_path).exists():
        raise HTTPException(404, "timing not ready")
    return JSONResponse(json.loads(Path(job.timing_path).read_text()))
```

- [ ] **Step 5: orchestrator.py에 timing.json 생성 추가**

```python
# backend/app/orchestration/orchestrator.py
# synth 완료 후 timing.json 생성
from app.stages.svs.timing import write_timing

timing_path = job_dir / "timing.json"
write_timing(score, timing_path, bpm=DEFAULT_BPM)
job.timing_path = str(timing_path)
```

- [ ] **Step 6: 테스트 통과 + 회귀 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest -v
```
Expected: 모두 PASSED

- [ ] **Step 7: 커밋**

```bash
git add backend/app/stages/svs/timing.py \
        backend/app/orchestration/orchestrator.py \
        backend/app/api/routes/jobs.py \
        backend/tests/test_timing.py
git commit -m "feat(api): timing.json 생성 + GET /timing 엔드포인트"
```

---

## Task 3: Expo 프로젝트 스캐폴딩 + API 클라이언트

**Files:**
- Create: `mobile/package.json`
- Create: `mobile/app.json`
- Create: `mobile/tsconfig.json`
- Create: `mobile/lib/api.ts`
- Create: `mobile/lib/timing.ts`

**Interfaces:**
- Produces: `createJob(uri)`, `getJob(id)`, `voiceAudioUrl(id, voice)`, `timingUrl(id)`, `scoreUrl(id)`

- [ ] **Step 1: Expo 프로젝트 초기화**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
npx create-expo-app mobile --template blank-typescript
cd mobile
npx expo install expo-router expo-av expo-image-picker react-native-webview
npx expo install expo-status-bar react-native-safe-area-context react-native-screens
```

- [ ] **Step 2: app.json 설정**

```json
{
  "expo": {
    "name": "AIScore",
    "slug": "aiscore",
    "version": "1.0.0",
    "scheme": "aiscore",
    "platforms": ["ios", "android"],
    "plugins": [
      "expo-router",
      ["expo-image-picker", {
        "photosPermission": "악보 이미지를 선택하기 위해 갤러리 접근이 필요합니다.",
        "cameraPermission": "악보를 촬영하기 위해 카메라 접근이 필요합니다."
      }]
    ],
    "android": { "package": "kr.re.etri.aiscore" },
    "ios": { "bundleIdentifier": "kr.re.etri.aiscore" }
  }
}
```

- [ ] **Step 3: lib/api.ts 작성**

```typescript
// mobile/lib/api.ts
const API = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export type VoiceName = "soprano" | "alto" | "tenor" | "bass";
export type JobStatus = "queued" | "omr" | "parsing" | "synth" | "mixing" | "done" | "failed";

export interface JobState {
  id: string;
  status: JobStatus;
  failed_stage?: string;
  error?: string;
  result_path?: string;
  score_path?: string;
  voice_paths: Partial<Record<VoiceName, string>>;
  timing_path?: string;
}

export async function createJob(imageUri: string): Promise<{ id: string }> {
  const form = new FormData();
  const filename = imageUri.split("/").pop() ?? "score.jpg";
  form.append("file", { uri: imageUri, name: filename, type: "image/jpeg" } as any);
  const res = await fetch(`${API}/jobs`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
  return res.json();
}

export async function getJob(id: string): Promise<JobState> {
  const res = await fetch(`${API}/jobs/${id}`);
  if (!res.ok) throw new Error(`getJob failed: ${res.status}`);
  return res.json();
}

export const voiceAudioUrl = (id: string, voice: VoiceName) =>
  `${API}/jobs/${id}/audio/${voice}`;

export const scoreUrl = (id: string) => `${API}/jobs/${id}/score`;
export const timingUrl = (id: string) => `${API}/jobs/${id}/timing`;
```

- [ ] **Step 4: lib/timing.ts 작성**

```typescript
// mobile/lib/timing.ts
export interface NoteEvent {
  pitch: string | null;
  start_sec: number;
  end_sec: number;
  index: number;
}

export interface TimingData {
  bpm: number;
  voices: Record<string, NoteEvent[]>;
}

/** currentTime(초)에 해당하는 음표 인덱스 반환. 없으면 -1 */
export function findNoteIndex(
  notes: NoteEvent[],
  currentTime: number
): number {
  for (let i = 0; i < notes.length; i++) {
    if (currentTime >= notes[i].start_sec && currentTime < notes[i].end_sec) {
      return i;
    }
  }
  return -1;
}
```

- [ ] **Step 5: 커밋**

```bash
cd mobile
git add .
git commit -m "feat(mobile): Expo 스캐폴딩 + API 클라이언트"
```

---

## Task 4: HomeScreen — 악보 선택 + 업로드

**Files:**
- Create: `mobile/app/index.tsx`
- Create: `mobile/app/_layout.tsx`

**Interfaces:**
- Consumes: `createJob(imageUri)` from `lib/api.ts`
- Produces: jobId → `router.push('/processing/' + id)`

- [ ] **Step 1: _layout.tsx 작성**

```tsx
// mobile/app/_layout.tsx
import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: "AIScore" }} />
      <Stack.Screen name="processing/[id]" options={{ title: "처리 중..." }} />
      <Stack.Screen name="player/[id]" options={{ title: "악보 플레이어" }} />
    </Stack>
  );
}
```

- [ ] **Step 2: index.tsx 작성**

```tsx
// mobile/app/index.tsx
import { useState } from "react";
import { View, Text, TouchableOpacity, Image, StyleSheet, Alert } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { router } from "expo-router";
import { createJob } from "../lib/api";

export default function HomeScreen() {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function pickImage(source: "camera" | "gallery") {
    const fn =
      source === "camera"
        ? ImagePicker.launchCameraAsync
        : ImagePicker.launchImageLibraryAsync;
    const result = await fn({ mediaTypes: ImagePicker.MediaTypeOptions.Images });
    if (!result.canceled) setImageUri(result.assets[0].uri);
  }

  async function upload() {
    if (!imageUri) return;
    setUploading(true);
    try {
      const { id } = await createJob(imageUri);
      router.push(`/processing/${id}`);
    } catch (e: any) {
      Alert.alert("업로드 실패", e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>AIScore</Text>
      <Text style={styles.subtitle}>SATB 찬송가 악보 → 합창 음원</Text>

      {imageUri && (
        <Image source={{ uri: imageUri }} style={styles.preview} />
      )}

      <TouchableOpacity style={styles.btn} onPress={() => pickImage("camera")}>
        <Text style={styles.btnText}>📷 악보 촬영</Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.btn} onPress={() => pickImage("gallery")}>
        <Text style={styles.btnText}>🖼️ 갤러리에서 선택</Text>
      </TouchableOpacity>

      {imageUri && (
        <TouchableOpacity
          style={[styles.btn, styles.btnPrimary, uploading && styles.btnDisabled]}
          onPress={upload}
          disabled={uploading}
        >
          <Text style={styles.btnText}>
            {uploading ? "업로드 중..." : "▶ 음원 추출 시작"}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  title:    { fontSize: 32, fontWeight: "bold", marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#666", marginBottom: 24 },
  preview:  { width: 280, height: 180, resizeMode: "contain", marginBottom: 16, borderRadius: 8 },
  btn:      { width: 240, padding: 14, borderRadius: 8, backgroundColor: "#ddd", marginVertical: 6, alignItems: "center" },
  btnPrimary:  { backgroundColor: "#3b82f6" },
  btnDisabled: { backgroundColor: "#93c5fd" },
  btnText:  { color: "#222", fontSize: 16, fontWeight: "600" },
});
```

- [ ] **Step 3: 커밋**

```bash
git add mobile/app/_layout.tsx mobile/app/index.tsx
git commit -m "feat(mobile): HomeScreen — 악보 선택 + 업로드"
```

---

## Task 5: ProcessingScreen — 처리 진행 폴링

**Files:**
- Create: `mobile/app/processing/[id].tsx`

**Interfaces:**
- Consumes: `getJob(id)` → status
- Produces: status=="done" → `router.replace('/player/' + id)`

- [ ] **Step 1: processing/[id].tsx 작성**

```tsx
// mobile/app/processing/[id].tsx
import { useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { getJob, JobStatus } from "../../lib/api";

const STAGES: JobStatus[] = ["queued", "omr", "parsing", "synth", "mixing", "done"];
const STAGE_LABEL: Record<string, string> = {
  queued: "대기 중",
  omr: "악보 인식 (OMR)",
  parsing: "음표 파싱",
  synth: "성부별 음원 합성",
  mixing: "최종 믹싱",
  done: "완료",
};

export default function ProcessingScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [status, setStatus] = useState<JobStatus>("queued");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const job = await getJob(id);
        setStatus(job.status);
        if (job.status === "done") {
          clearInterval(timer);
          router.replace(`/player/${id}`);
        } else if (job.status === "failed") {
          clearInterval(timer);
          setError(job.error ?? "알 수 없는 오류");
        }
      } catch (e: any) {
        setError(e.message);
        clearInterval(timer);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [id]);

  const stageIdx = STAGES.indexOf(status);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>음원 추출 중...</Text>
      {STAGES.slice(1).map((stage, i) => (
        <View key={stage} style={styles.stageRow}>
          <Text style={[styles.dot, i < stageIdx ? styles.done : i === stageIdx - 1 ? styles.active : styles.pending]}>
            {i < stageIdx ? "✅" : i === stageIdx - 1 ? "⏳" : "○"}
          </Text>
          <Text style={styles.stageLabel}>{STAGE_LABEL[stage]}</Text>
        </View>
      ))}
      {error && <Text style={styles.error}>오류: {error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container:  { flex: 1, padding: 32, justifyContent: "center" },
  title:      { fontSize: 22, fontWeight: "bold", marginBottom: 24 },
  stageRow:   { flexDirection: "row", alignItems: "center", marginVertical: 8 },
  dot:        { fontSize: 20, marginRight: 12, width: 28 },
  stageLabel: { fontSize: 16 },
  done:       {},
  active:     {},
  pending:    { color: "#aaa" },
  error:      { color: "red", marginTop: 20 },
});
```

- [ ] **Step 2: 커밋**

```bash
git add mobile/app/processing/
git commit -m "feat(mobile): ProcessingScreen — 처리 단계 폴링"
```

---

## Task 6: PartSelector 컴포넌트

**Files:**
- Create: `mobile/components/PartSelector.tsx`

**Interfaces:**
- Props: `selected: Set<VoiceName>`, `onToggle: (v: VoiceName) => void`

- [ ] **Step 1: PartSelector.tsx 작성**

```tsx
// mobile/components/PartSelector.tsx
import { View, TouchableOpacity, Text, StyleSheet } from "react-native";
import { VoiceName } from "../lib/api";

const VOICES: { key: VoiceName; label: string; color: string }[] = [
  { key: "soprano", label: "S", color: "#ef4444" },
  { key: "alto",    label: "A", color: "#f97316" },
  { key: "tenor",   label: "T", color: "#3b82f6" },
  { key: "bass",    label: "B", color: "#8b5cf6" },
];

interface Props {
  selected: Set<VoiceName>;
  onToggle: (v: VoiceName) => void;
}

export function PartSelector({ selected, onToggle }: Props) {
  return (
    <View style={styles.row}>
      {VOICES.map(({ key, label, color }) => {
        const active = selected.has(key);
        return (
          <TouchableOpacity
            key={key}
            style={[styles.btn, active && { backgroundColor: color }]}
            onPress={() => onToggle(key)}
          >
            <Text style={[styles.label, active && styles.labelActive]}>
              {label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row:         { flexDirection: "row", justifyContent: "center", gap: 12, padding: 12 },
  btn:         { width: 56, height: 56, borderRadius: 28, borderWidth: 2, borderColor: "#ccc",
                 alignItems: "center", justifyContent: "center" },
  label:       { fontSize: 20, fontWeight: "bold", color: "#666" },
  labelActive: { color: "#fff" },
});
```

- [ ] **Step 2: 커밋**

```bash
git add mobile/components/PartSelector.tsx
git commit -m "feat(mobile): PartSelector — S/A/T/B 파트 토글"
```

---

## Task 7: AudioMixer — expo-av 멀티트랙

**Files:**
- Create: `mobile/components/AudioMixer.tsx`

**Interfaces:**
- Props: `jobId: string`, `selected: Set<VoiceName>`
- Exposes ref: `{ play(), pause(), seek(sec), currentTime: number }`

- [ ] **Step 1: AudioMixer.tsx 작성**

```tsx
// mobile/components/AudioMixer.tsx
import { useEffect, useRef, useImperativeHandle, forwardRef, useState } from "react";
import { Audio } from "expo-av";
import { VoiceName, voiceAudioUrl } from "../lib/api";

const ALL_VOICES: VoiceName[] = ["soprano", "alto", "tenor", "bass"];

export interface AudioMixerHandle {
  play: () => Promise<void>;
  pause: () => Promise<void>;
  seek: (sec: number) => Promise<void>;
  currentTime: number;
  duration: number;
}

interface Props {
  jobId: string;
  selected: Set<VoiceName>;
  onTimeUpdate?: (sec: number) => void;
}

export const AudioMixer = forwardRef<AudioMixerHandle, Props>(
  ({ jobId, selected, onTimeUpdate }, ref) => {
    const sounds = useRef<Partial<Record<VoiceName, Audio.Sound>>>({});
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);

    // 4성부 WAV 로드
    useEffect(() => {
      let cancelled = false;
      async function load() {
        await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
        for (const voice of ALL_VOICES) {
          const { sound } = await Audio.Sound.createAsync(
            { uri: voiceAudioUrl(jobId, voice) },
            { volume: selected.has(voice) ? 1.0 : 0.0 }
          );
          if (!cancelled) {
            sounds.current[voice] = sound;
            const status = await sound.getStatusAsync();
            if (status.isLoaded) setDuration(status.durationMillis! / 1000);
          }
        }
      }
      load();
      return () => {
        cancelled = true;
        Object.values(sounds.current).forEach((s) => s?.unloadAsync());
      };
    }, [jobId]);

    // 파트 선택 변경 시 볼륨 on/off
    useEffect(() => {
      for (const voice of ALL_VOICES) {
        sounds.current[voice]?.setVolumeAsync(selected.has(voice) ? 1.0 : 0.0);
      }
    }, [selected]);

    // 재생 위치 추적 (100ms 간격)
    useEffect(() => {
      const interval = setInterval(async () => {
        const ref = sounds.current["soprano"];
        if (!ref) return;
        const status = await ref.getStatusAsync();
        if (status.isLoaded) {
          const t = status.positionMillis / 1000;
          setCurrentTime(t);
          onTimeUpdate?.(t);
        }
      }, 100);
      return () => clearInterval(interval);
    }, [onTimeUpdate]);

    useImperativeHandle(ref, () => ({
      currentTime,
      duration,
      async play() {
        for (const s of Object.values(sounds.current)) await s?.playAsync();
      },
      async pause() {
        for (const s of Object.values(sounds.current)) await s?.pauseAsync();
      },
      async seek(sec: number) {
        const ms = sec * 1000;
        for (const s of Object.values(sounds.current))
          await s?.setPositionAsync(ms);
      },
    }));

    return null; // UI 없음 — PlayerScreen에서 렌더
  }
);
```

- [ ] **Step 2: 커밋**

```bash
git add mobile/components/AudioMixer.tsx
git commit -m "feat(mobile): AudioMixer — expo-av 4성부 멀티트랙"
```

---

## Task 8: ScoreViewer — WebView + OSMD + 하이라이팅

**Files:**
- Create: `mobile/assets/score-viewer.html`
- Create: `mobile/components/ScoreViewer.tsx`

**Interfaces:**
- Props: `scoreUrl: string`, `timingData: TimingData | null`, `currentTime: number`, `activeVoice: VoiceName`
- WebView ← postMessage: `{type:"load", scoreUrl, timing}` | `{type:"seek", currentTime, voice}`

- [ ] **Step 1: score-viewer.html 작성**

```html
<!-- mobile/assets/score-viewer.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <script src="https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.8.6/build/opensheetmusicdisplay.min.js"></script>
  <style>
    body { margin: 0; background: #fff; overflow-x: hidden; }
    #score { width: 100%; }
    .highlight { fill: #ef4444 !important; color: #ef4444 !important; }
  </style>
</head>
<body>
  <div id="score"></div>
  <script>
    const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay("score", {
      autoResize: true,
      followCursor: true,
    });
    let timingData = null;
    let lastIndex = -1;

    // React Native → WebView
    window.addEventListener("message", handleMessage);
    document.addEventListener("message", handleMessage); // Android

    function handleMessage(event) {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "load") {
          timingData = msg.timing;
          osmd.load(msg.scoreUrl).then(() => {
            osmd.render();
            osmd.cursor.show();
          });
        } else if (msg.type === "seek") {
          updateHighlight(msg.currentTime, msg.voice);
        }
      } catch (e) {}
    }

    function updateHighlight(currentTime, voice) {
      if (!timingData || !timingData.voices[voice]) return;
      const notes = timingData.voices[voice];
      let idx = -1;
      for (let i = 0; i < notes.length; i++) {
        if (currentTime >= notes[i].start_sec && currentTime < notes[i].end_sec) {
          idx = i; break;
        }
      }
      if (idx === lastIndex || idx < 0) return;
      lastIndex = idx;
      // cursor를 해당 인덱스로 이동
      osmd.cursor.reset();
      for (let i = 0; i < idx; i++) osmd.cursor.next();
      // cursor 위치의 SVG 요소 하이라이팅
      document.querySelectorAll(".highlight").forEach(el => el.classList.remove("highlight"));
      const el = osmd.cursor.cursorElement;
      if (el) el.classList.add("highlight");
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: ScoreViewer.tsx 작성**

```tsx
// mobile/components/ScoreViewer.tsx
import { useRef, useEffect } from "react";
import { StyleSheet } from "react-native";
import WebView from "react-native-webview";
import { VoiceName } from "../lib/api";
import { TimingData } from "../lib/timing";

interface Props {
  scoreUrl: string;
  timingData: TimingData | null;
  currentTime: number;
  activeVoice: VoiceName;
}

export function ScoreViewer({ scoreUrl, timingData, currentTime, activeVoice }: Props) {
  const webRef = useRef<WebView>(null);

  // 악보 로드
  useEffect(() => {
    if (!timingData) return;
    webRef.current?.postMessage(JSON.stringify({
      type: "load",
      scoreUrl,
      timing: timingData,
    }));
  }, [scoreUrl, timingData]);

  // 재생 위치 동기화 (100ms마다 prop 변화 → postMessage)
  useEffect(() => {
    webRef.current?.postMessage(JSON.stringify({
      type: "seek",
      currentTime,
      voice: activeVoice,
    }));
  }, [currentTime, activeVoice]);

  return (
    <WebView
      ref={webRef}
      source={require("../assets/score-viewer.html")}
      style={styles.webview}
      originWhitelist={["*"]}
      allowFileAccess
      mixedContentMode="always"
    />
  );
}

const styles = StyleSheet.create({
  webview: { flex: 1, backgroundColor: "#fff" },
});
```

- [ ] **Step 3: 커밋**

```bash
git add mobile/assets/score-viewer.html mobile/components/ScoreViewer.tsx
git commit -m "feat(mobile): ScoreViewer — WebView+OSMD+실시간 하이라이팅"
```

---

## Task 9: PlaybackControls 컴포넌트

**Files:**
- Create: `mobile/components/PlaybackControls.tsx`

**Interfaces:**
- Props: `playing: boolean`, `currentTime: number`, `duration: number`, `onPlay()`, `onPause()`, `onSeek(sec)`

- [ ] **Step 1: PlaybackControls.tsx 작성**

```tsx
// mobile/components/PlaybackControls.tsx
import { View, TouchableOpacity, Text, StyleSheet } from "react-native";
import Slider from "@react-native-community/slider";

interface Props {
  playing: boolean;
  currentTime: number;
  duration: number;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (sec: number) => void;
}

function fmt(sec: number) {
  const m = Math.floor(sec / 60).toString().padStart(2, "0");
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export function PlaybackControls({ playing, currentTime, duration, onPlay, onPause, onSeek }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <Text style={styles.time}>{fmt(currentTime)}</Text>
        <Slider
          style={styles.slider}
          minimumValue={0}
          maximumValue={duration || 1}
          value={currentTime}
          onSlidingComplete={onSeek}
          minimumTrackTintColor="#3b82f6"
        />
        <Text style={styles.time}>{fmt(duration)}</Text>
      </View>
      <TouchableOpacity style={styles.playBtn} onPress={playing ? onPause : onPlay}>
        <Text style={styles.playIcon}>{playing ? "⏸" : "▶"}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 12, backgroundColor: "#f8f8f8" },
  row:       { flexDirection: "row", alignItems: "center" },
  slider:    { flex: 1, marginHorizontal: 8 },
  time:      { fontSize: 12, color: "#666", width: 40, textAlign: "center" },
  playBtn:   { alignItems: "center", marginTop: 8 },
  playIcon:  { fontSize: 36 },
});
```

- [ ] **Step 2: @react-native-community/slider 설치**

```bash
cd mobile && npx expo install @react-native-community/slider
```

- [ ] **Step 3: 커밋**

```bash
git add mobile/components/PlaybackControls.tsx
git commit -m "feat(mobile): PlaybackControls — 재생/정지/시크바"
```

---

## Task 10: PlayerScreen — 전체 통합

**Files:**
- Create: `mobile/app/player/[id].tsx`

**Interfaces:**
- Consumes: 모든 컴포넌트 + `getJob`, `timingUrl`, `scoreUrl`
- 완성 화면:
  ```
  ┌─────────────────────────┐
  │      ScoreViewer        │  (flex: 1)
  ├─────────────────────────┤
  │  [ S ] [ A ] [ T ] [ B ]│
  ├─────────────────────────┤
  │  ▶  ──●──────  00:18   │
  └─────────────────────────┘
  ```

- [ ] **Step 1: player/[id].tsx 작성**

```tsx
// mobile/app/player/[id].tsx
import { useEffect, useRef, useState, useCallback } from "react";
import { View, StyleSheet, Alert } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { getJob, scoreUrl, timingUrl, VoiceName } from "../../lib/api";
import { TimingData } from "../../lib/timing";
import { ScoreViewer } from "../../components/ScoreViewer";
import { PartSelector } from "../../components/PartSelector";
import { AudioMixer, AudioMixerHandle } from "../../components/AudioMixer";
import { PlaybackControls } from "../../components/PlaybackControls";

export default function PlayerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [selected, setSelected] = useState<Set<VoiceName>>(
    new Set(["soprano", "alto", "tenor", "bass"])
  );
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [timingData, setTimingData] = useState<TimingData | null>(null);
  const mixerRef = useRef<AudioMixerHandle>(null);

  // timing.json 로드
  useEffect(() => {
    fetch(timingUrl(id))
      .then((r) => r.json())
      .then(setTimingData)
      .catch((e) => Alert.alert("타이밍 로드 실패", e.message));
  }, [id]);

  function toggleVoice(voice: VoiceName) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(voice) ? next.delete(voice) : next.add(voice);
      return next;
    });
  }

  async function handlePlay() {
    await mixerRef.current?.play();
    setPlaying(true);
  }
  async function handlePause() {
    await mixerRef.current?.pause();
    setPlaying(false);
  }
  async function handleSeek(sec: number) {
    await mixerRef.current?.seek(sec);
  }

  const handleTimeUpdate = useCallback((t: number) => setCurrentTime(t), []);

  // 활성 파트: 선택된 것 중 첫 번째 (악보 하이라이팅 기준)
  const activeVoice: VoiceName =
    (["soprano", "alto", "tenor", "bass"] as VoiceName[]).find((v) =>
      selected.has(v)
    ) ?? "soprano";

  return (
    <View style={styles.container}>
      <ScoreViewer
        scoreUrl={scoreUrl(id)}
        timingData={timingData}
        currentTime={currentTime}
        activeVoice={activeVoice}
      />
      <PartSelector selected={selected} onToggle={toggleVoice} />
      <PlaybackControls
        playing={playing}
        currentTime={currentTime}
        duration={mixerRef.current?.duration ?? 0}
        onPlay={handlePlay}
        onPause={handlePause}
        onSeek={handleSeek}
      />
      <AudioMixer
        ref={mixerRef}
        jobId={id}
        selected={selected}
        onTimeUpdate={handleTimeUpdate}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
});
```

- [ ] **Step 2: 빌드 확인**

```bash
cd mobile && npx expo export --platform ios 2>&1 | tail -20
```
Expected: 빌드 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add mobile/app/player/
git commit -m "feat(mobile): PlayerScreen — 악보+파트선택+동기화 재생 통합"
```

---

## Task 11: 브랜치 머지 + 문서 갱신

- [ ] **Step 1: feat/vocal-quality → main 머지**

```bash
git checkout main
git merge --squash feat/vocal-quality
git commit -m "feat: 4성부 분리+성악합성+모바일 앱 설계"
```

- [ ] **Step 2: ROADMAP.md + ARCHITECTURE.md 갱신**
  - ✅ 완료 항목에 "모바일 앱 설계 (Task 1~11)" 추가
  - ARCHITECTURE.md: 모바일 레이어(Expo), 화면 흐름, timing.json 구조 반영

---

## 자기 검토

**스펙 커버리지:**
- [x] 악보 선택 (카메라/갤러리) → Task 4
- [x] 음원 추출 진행 표시 → Task 5
- [x] 파트 선택 (S/A/T/B) → Task 6
- [x] 악보 + 소리 동기화 출력 → Task 7, 8, 10
- [x] iOS/Android 공통 → Expo SDK
- [x] 백엔드 API 확장 (개별 WAV + timing) → Task 1, 2

**미비 사항:**
- Expo Go 에서의 react-native-webview 테스트는 Expo Dev Build 필요 (`npx expo run:ios`)
- 실제 기기 테스트 전에 백엔드 URL을 로컬 IP로 변경 필요 (`EXPO_PUBLIC_API_URL=http://192.168.x.x:8000`)
- OSMD CDN 로드는 오프라인 환경에서 실패 → 추후 로컬 번들 필요
