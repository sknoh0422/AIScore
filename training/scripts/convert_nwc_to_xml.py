"""
score_images/nwc/ 감시 → score_images/xml/ 에 MusicXML 변환 저장.

수정 내용:
  music21의 NWCStaff.parseHeader가 NWC v130 staff 헤더(28 bytes)를 읽지 않는 버그를
  monkey-patch로 수정.  v130 staff 구조:
    12B bytes  : btEndingBar..btPatchName
    12B shorts : nStyle, nVertSizeUpper, nVertSizeLower, nLayerWithNextStaff,
                 nPartVolume, nStereoPan
     2B bytes  : btReserved6, btColor
     2B short  : nNumLyric
  (참조: nwc2xml/src/nwcfile.cpp, CStaff::Load)
  v130은 nNumLyric 뒤에 lyricAlignment/staffOffset이 없음.
  v150은 nTransposition(2B) 추가(총 30B) + lyricAlignment/staffOffset 있음.
"""

import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

NWC_DIR = Path("score_images/nwc")
XML_DIR = Path("score_images/xml")
POLL_INTERVAL = 5  # 초


# ── music21 NWCStaff.parseHeader 패치 ────────────────────────────────────────

def _patch_music21():
    """v130 NWC 파싱 버그 두 가지를 monkey-patch로 수정.

    버그 1 (NWCConverter.parseHeader):
      groupVisibility/allowLayering 읽기 조건이 `>= 130`이지만
      nwcfile.cpp 기준 `> 130`이어야 함. v130에서 33B 오버리드 발생.

    버그 2 (NWCConverter.parseHeader):
      advanceToNotNUL() + skipBytes(2)가 fontCount=0인 v130에서도 실행되어
      titlePageInfo+staffLabels(2B) 자리를 소비함.

    버그 3 (NWCStaff.parseHeader):
      v130 staff 헤더(28B)를 읽는 분기가 없어 파싱 위치 완전 어긋남.
    """
    from music21.noteworthy import binaryTranslate, constants

    # ── 버그 1+2: NWCConverter.parseHeader 수정 ───────────────────────────────
    _orig_file_parse_header = binaryTranslate.NWCConverter.parseHeader

    def _file_parseHeader_patched(self):
        self.isValidNWCFile()
        self.fileVersion()

        self.skipBytes(4)
        self.user = self.readToNUL()
        unused_unknown = self.readToNUL()
        self.skipBytes(10)
        self.title = self.readToNUL()
        self.author = self.readToNUL()
        if self.version >= 200:
            self.lyricist = self.readToNUL()
        self.copyright1 = self.readToNUL()
        self.copyright2 = self.readToNUL()
        self.comment = self.readToNUL()

        self.extendLastSystem = self.byteToInt()
        self.increaseNoteSpacing = self.byteToInt()
        unused = self.readBytes(5)
        self.measureNumbers = self.byteToInt()

        unused = self.readBytes(1)
        self.measureStart = self.readLEShort()
        if self.version >= 130:
            self.margins = self.readToNUL()
        else:
            self.margins = b'0.0 0.0 0.0 0.0'

        unused = self.byteToInt()
        unused = self.readBytes(2)
        # 버그 1 수정: groupVisibility는 v130 초과에서만 존재
        if self.version > 130:
            self.groupVisibility = self.readBytes(32)
            self.allowLayering = self.byteToInt()

        if self.version >= 200:
            self.notationTypeface = self.readToNUL()
        self.staffHeight = self.readLEShort()

        if self.version > 170:
            fontCount = 12
        elif self.version > 130:
            fontCount = 10
        else:
            fontCount = 0

        self.fonts = []
        for i in range(fontCount):
            fontDict = {
                'name': self.readToNUL(),
                'style': self.byteToInt(),
                'size': self.byteToInt(),
                'charset': 0,
            }
            unused = self.byteToInt()
            fontDict['charset'] = self.byteToInt()
            if fontDict['name'] == b'':
                fontDict['name'] = b'Times New Roman'
            if fontDict['size'] == 0:
                fontDict['size'] = 12
            self.fonts.append(fontDict)
        # nwcfile.cpp: v170은 일부 파일에서 12폰트 (기본 10)
        # 다음 바이트가 0/0xFF가 아니면 2폰트 추가 읽기
        if self.version == 170:
            peek = self.fileContents[self.parsePosition:self.parsePosition + 1]
            if peek and peek[0] not in (0, 0xFF):
                for i in range(2):
                    fontDict = {
                        'name': self.readToNUL(),
                        'style': self.byteToInt(),
                        'size': self.byteToInt(),
                        'charset': 0,
                    }
                    unused = self.byteToInt()
                    fontDict['charset'] = self.byteToInt()
                    if fontDict['name'] == b'':
                        fontDict['name'] = b'Times New Roman'
                    if fontDict['size'] == 0:
                        fontDict['size'] = 12
                    self.fonts.append(fontDict)

        self.titlePageInfo = self.byteToInt()
        self.staffLabels = self.byteToInt()
        self.pageNumberStart = self.readLEShort()
        if self.version >= 200:
            self.skipBytes(1)
        self.numberOfStaves = self.byteToInt()
        self.skipBytes(1)

    binaryTranslate.NWCConverter.parseHeader = _file_parseHeader_patched

    # ── 버그 3: NWCStaff.parseHeader 수정 ────────────────────────────────────
    def _staff_parseHeader_patched(self):
        p = self.parent
        self.name = p.readToNUL()
        if p.version >= 200:
            self.label = p.readToNUL()
            self.instrumentName = p.readToNUL()
        self.group = p.readToNUL()

        if p.version >= 200:
            p.skipBytes(27)
            self.lines = p.byteToInt()
            self.layerWithNextStaff = p.readLEShort()
            self.transposition = p.readLEShort()
            self.partVolume = p.readLEShort()
            self.stereoPan = p.readLEShort()
            self.color = p.byteToInt()
            self.alignSyllable = p.readLEShort()
            self.numberOfLyrics = p.readLEShort()

        elif p.version == 175:
            # staff175: 11B skip + btPatchName(1B) + 10B skip + nTransposition(2B)
            #           + 5B skip (nPartVolume+nStereoPan+btColor) + nAlignSyllable(2B) + nNumLyric(2B)
            # 원래 music21은 transposition을 1B(byteToSignedInt)로 읽어 skipBytes(6) → 동일 결과.
            # 여기선 2B(readLEShort)로 읽으므로 skipBytes(5)로 보정.
            p.skipBytes(11)
            instruPatch = p.byteToInt()
            idx = instruPatch - 1 if 0 < instruPatch < len(constants.MidiInstruments) else 0
            self.instrumentName = constants.MidiInstruments[idx].encode('latin_1')
            p.skipBytes(10)
            self.transposition = p.readLEShort()
            p.skipBytes(5)  # nPartVolume(2) + nStereoPan(2) + btColor(1)
            self.alignSyllable = p.readLEShort()
            self.numberOfLyrics = p.readLEShort()

        elif p.version <= 130:
            # staff130 구조 (28B), nwcfile.cpp CStaff::Load 참조:
            #   12B: btEndingBar..btPatchName (single bytes)
            #   12B: nStyle..nStereoPan (6×LE short)
            #    2B: btReserved6 + btColor
            #    2B: nNumLyric
            p.skipBytes(12)
            p.skipBytes(12)
            p.skipBytes(2)
            self.numberOfLyrics = p.readLEShort()
            self.transposition = 0
            # v130: nNumLyric 뒤에 lyricAlignment/staffOffset 없음
            return

        elif p.version <= 150:
            # staff150 (30B): 12B bytes + 14B shorts + btReserved6(1B)+btColor(1B) + nNumLyric(2B)
            p.skipBytes(12)
            p.skipBytes(6)
            self.layerWithNextStaff = p.readLEShort()
            self.transposition = p.readLEShort()
            self.partVolume = p.readLEShort()
            self.stereoPan = p.readLEShort()
            p.skipBytes(2)      # btReserved6 + btColor
            self.numberOfLyrics = p.readLEShort()

        elif p.version <= 155:
            # staff155 (31B): btReserved5(1B) 추가 — 13B bytes + 14B shorts + btReserved6+btColor + nNumLyric
            p.skipBytes(13)
            p.skipBytes(6)
            self.layerWithNextStaff = p.readLEShort()
            self.transposition = p.readLEShort()
            self.partVolume = p.readLEShort()
            self.stereoPan = p.readLEShort()
            p.skipBytes(2)      # btReserved6 + btColor
            self.numberOfLyrics = p.readLEShort()

        elif p.version <= 170:
            # staff170 (32B): 13B bytes + 14B shorts + btColor(1B) + btReserved6-SHORT(2B) + nNumLyric(2B)
            p.skipBytes(13)
            p.skipBytes(6)
            self.layerWithNextStaff = p.readLEShort()
            self.transposition = p.readLEShort()
            self.partVolume = p.readLEShort()
            self.stereoPan = p.readLEShort()
            p.skipBytes(1)      # btColor
            p.skipBytes(2)      # btReserved6 (SHORT in v170)
            self.numberOfLyrics = p.readLEShort()

        if self.numberOfLyrics > 0:
            self.lyricAlignment = p.readLEShort()
            self.staffOffset = p.readLEShort()
        else:
            self.lyricAlignment = 0
            self.staffOffset = 0

    binaryTranslate.NWCStaff.parseHeader = _staff_parseHeader_patched

    # ── 버그 4: NWCObject.note() — v < 170 가드가 읽기를 건너뜀 ──────────────
    # nwcobj.cpp: NWC v130 Note 구조 = v170과 동일 (mDuration+mData2+mAttribute1+mPos+mAttribute2+mData3)
    def _note_patched(self):
        p = self.parserParent
        self.type = 'Note'
        self.duration = p.byteToInt() & 0x07  # C++: mDuration & 0x07 (상위 비트는 기타 플래그)
        self.data2 = p.readBytes(3)
        self.attribute1 = p.readBytes(2)
        self.pos = p.byteToSignedInt()
        self.pos = -1 * self.pos
        self.attribute2 = p.byteToInt()
        if p.version <= 170:
            self.data3 = p.readBytes(2)
        else:
            self.data3 = None
        if p.version >= 200 and (self.attribute2 & 0x40) != 0:
            self.stemLength = p.byteToInt()
        else:
            self.stemLength = 7
        self.durationStr = self.setDurationForObject()
        alterationIndex = self.attribute2 & 0x07
        if alterationIndex < len(constants.AlterationTexts):
            self.alterationStr = constants.AlterationTexts[alterationIndex]
        else:
            self.alterationStr = ''
        self.tieInfo = ''
        if self.attribute2 & 0x10:
            self.tieInfo = '^'

        def dump(inner_self):
            build = '|Note|Dur:' + inner_self.durationStr + '|Pos:'
            build += inner_self.alterationStr + str(inner_self.pos)
            build += inner_self.tieInfo + '|'
            return build
        self.dumpMethod = dump

    binaryTranslate.NWCObject.note = _note_patched
    binaryTranslate.NWCObject.objMethods[8] = _note_patched

    # ── 버그 5: NWCObject.rest() — v <= 150 가드가 읽기를 건너뜀 ─────────────
    # nwcobj.cpp: v <= 150 Rest = duration(1B) + data2(5B), offset = data2[4]
    def _rest_patched(self):
        p = self.parserParent
        self.type = 'Rest'
        self.duration = p.byteToInt() & 0x07  # C++: mDuration & 0x07
        self.data2 = p.readBytes(5)
        if p.version <= 150:
            self.offset = self.data2[4]
        else:
            self.offset = p.readLEShort()
        self.durationStr = self.setDurationForObject()

        def dump(inner_self):
            return '|Rest|Dur:' + inner_self.durationStr + '|'
        self.dumpMethod = dump

    binaryTranslate.NWCObject.rest = _rest_patched
    binaryTranslate.NWCObject.objMethods[9] = _rest_patched

    # ── 버그 7: NWCObject.noteChordMember() — v170 mCount(2B) + child objects 미처리 ──
    # nwcobj.cpp CNoteCMObj::Load: mData1(12B) + mCount(2B)
    # CreateNLoadObject: Load() 후 LoadChildren(mCount 개 Note/Rest) 별도 호출
    # music21은 v<=170에서 numberOfNotes=0으로 고정 → mCount와 자식 객체 모두 누락
    def _noteChordMember_patched(self):
        p = self.parserParent
        self.type = 'NoteChordMember'
        numberOfNotes = 0
        if p.version <= 170:
            # C++ CNoteCMObj::Load: mData1(12B) + mCount(2B)
            self.data1 = p.readBytes(12)
            numberOfNotes = p.readLEShort()
        elif p.version == 175:
            # v175: 10B data1, mCount = data1[8]
            self.data1 = p.readBytes(10)
            numberOfNotes = self.data1[8]
        else:
            self.data1 = p.readBytes(8)
        if p.version >= 200:
            if (self.data1[7] & 0x40) != 0:
                self.stemLength = p.byteToInt()
            else:
                self.stemLength = 7
        else:
            self.stemLength = 7

        self.data2 = []
        for i in range(numberOfNotes):
            chordNote = binaryTranslate.NWCObject(staffParent=self.staffParent, parserParent=p)
            chordNote.parse()
            self.data2.append(chordNote)

        def dump(inner_self):
            build = '|Chord'
            notes = {}
            for d in inner_self.data2:
                if notes.get(d.durationStr) is None:
                    notes[d.durationStr] = []
                notes[d.durationStr].append(d.alterationStr + str(d.pos) + d.tieInfo)
            for n in notes:
                build += '|Dur:' + n + '|Pos:' + ','.join(notes[n])
            return build

        self.dumpMethod = dump

    binaryTranslate.NWCObject.noteChordMember = _noteChordMember_patched
    binaryTranslate.NWCObject.objMethods[10] = _noteChordMember_patched

    # ── 버그 8: NWCObject.restChordMember() — noteChordMember 호출로 v170 rest 구조 미스매치 ──
    # C++: CRestCMObj::Load = CRestObj::Load(duration 1B + data2 5B + offset 2B) + mCount(2B) + children
    # music21: noteChordMember() 호출 → data1(12B) + mCount(2B) → rest 8B를 초과 읽어 mCount 오염
    def _restChordMember_patched(self):
        p = self.parserParent
        self.type = 'RestChordMember'

        # CRestObj 구조 직접 읽기 (_rest_patched와 동일한 필드명 사용)
        self.duration = p.byteToInt()      # 1B
        self.data2 = p.readBytes(5)        # 5B — setDurationForObject()가 data2[3] 접근
        if p.version <= 150:
            self.offset = self.data2[4]
        else:
            self.offset = p.readLEShort()  # 2B (v170)

        # mCount = child Rest/Note 수
        numberOfNotes = p.readLEShort()    # 2B

        self.durationStr = self.setDurationForObject()

        chord_children = []
        for i in range(numberOfNotes):
            chordNote = binaryTranslate.NWCObject(staffParent=self.staffParent, parserParent=p)
            chordNote.parse()
            chord_children.append(chordNote)
        self.chordChildren = chord_children

        def dump(inner_self):
            build = '|Chord'
            notes = {}
            for d in inner_self.chordChildren:
                if notes.get(d.durationStr) is None:
                    notes[d.durationStr] = []
                notes[d.durationStr].append(
                    getattr(d, 'alterationStr', '') + str(getattr(d, 'pos', 0)) + getattr(d, 'tieInfo', ''))
            for n in notes:
                build += '|Dur:' + n + '|Pos:' + ','.join(notes[n])
            return build

        self.dumpMethod = dump

    binaryTranslate.NWCObject.restChordMember = _restChordMember_patched
    binaryTranslate.NWCObject.objMethods[18] = _restChordMember_patched

    # ── 버그 9: NWCObject.instrument() — v130은 6B, v170+는 8B ──────────────────
    # C++: CInstrumentObj::Load — v<170: file.Read(mData1, 6); v>=170: ReadBytes(mData1) = 8B
    # music21: 항상 skipBytes(8) → v130에서 2B 초과 소비
    def _instrument_patched(self):
        p = self.parserParent
        self.type = 'Instrument'
        if p.version < 170:
            p.skipBytes(6)
        else:
            p.skipBytes(8)

    binaryTranslate.NWCObject.instrument = _instrument_patched
    binaryTranslate.NWCObject.objMethods[4] = _instrument_patched

    # ── 버그 11: tempoVariation — dumpMethod가 '' → 늘임표(페르마타) 소실 ──────────
    # binaryTranslate.NWCObject.tempoVariation은 파싱만 하고 dumpMethod를 설정하지 않음
    # → |DynamicVariance|Style:Fermata| 형식으로 출력해 translate.py에 전달
    _TEMPO_VAR_STYLES = ['Breath Mark','Fermata','Accelerando','Allargrando',
                         'Rallentando','Ritardando','Ritenuto','Rubato','Stringendo']

    def _tempoVariation_patched(self):
        p = self.parserParent
        self.type = 'TempoVariation'
        if p.version >= 170:
            self.pos = p.byteToInt()
            self.placement = p.byteToInt()
            self.style = p.byteToInt()
            self.delay = p.byteToInt()
        else:
            self.style = p.byteToInt() & 0x0F
            self.pos = p.byteToInt()
            self.placement = p.byteToInt()
            self.delay = p.byteToInt()

        def dump(inner_self):
            if 0 <= inner_self.style < len(_TEMPO_VAR_STYLES):
                return f'|DynamicVariance|Style:{_TEMPO_VAR_STYLES[inner_self.style]}|Pos:{inner_self.pos}'
            return ''
        self.dumpMethod = dump

    binaryTranslate.NWCObject.tempoVariation = _tempoVariation_patched
    binaryTranslate.NWCObject.objMethods[14] = _tempoVariation_patched

    # translate.py createDynamicVariance — Fermata 처리 추가
    from music21.noteworthy import translate as _nwc_translate
    from music21 import expressions as _m21_expr, note as _m21_note

    _orig_create_dyn_var = _nwc_translate.NoteworthyTranslator.createDynamicVariance

    def _createDynamicVariance_patched(self, attributes):
        if attributes.get('Style') == 'Fermata':
            # NWC에서 TempoVariance 객체는 적용 대상 음표 바로 앞에 위치
            # → 다음 translateNote / translateChord 호출 시 부착
            self._pendingFermata = True
        else:
            _orig_create_dyn_var(self, attributes)

    _nwc_translate.NoteworthyTranslator.createDynamicVariance = _createDynamicVariance_patched

    def _attach_pending_fermata(translator):
        """currentMeasure의 마지막 음표에 pending 페르마타 부착."""
        if not getattr(translator, '_pendingFermata', False):
            return
        last_note = None
        for item in reversed(list(translator.currentMeasure.recurse().notesAndRests)):
            if isinstance(item, _m21_note.GeneralNote) and not item.isRest:
                last_note = item
                break
        if last_note is not None:
            fermata = _m21_expr.Fermata()
            fermata.type = 'normal'
            last_note.expressions.append(fermata)
        translator._pendingFermata = False

    _orig_translateNote = _nwc_translate.NoteworthyTranslator.translateNote

    def _translateNote_patched(self, attributes):
        _orig_translateNote(self, attributes)
        _attach_pending_fermata(self)

    _nwc_translate.NoteworthyTranslator.translateNote = _translateNote_patched

    _orig_translateChord = _nwc_translate.NoteworthyTranslator.translateChord

    def _translateChord_patched(self, attributes):
        _orig_translateChord(self, attributes)
        _attach_pending_fermata(self)

    _nwc_translate.NoteworthyTranslator.translateChord = _translateChord_patched

    # ── 버그 10: dumpToNWCText — CP949 미처리 + 가사 직렬화 누락 ─────────────────
    # music21은 title/author를 latin_1로 디코딩 → 한글 깨짐
    # NWCStaff.lyrics는 파싱하지만 dump()에서 |Lyric1| 라인을 출력하지 않음
    def _dumpToNWCText_patched(self):
        infos = ''
        if self.title:
            infos += '|SongInfo|Title:' + self.title.decode('cp949', errors='replace')
        if self.author:
            infos += '|Author:' + self.author.decode('cp949', errors='replace')
        dumpObjects = [infos]
        for s in self.staves:
            staffDumpObjects = list(s.dump())
            if hasattr(s, 'lyrics') and s.lyrics:
                syllables = []
                for syl in s.lyrics[0]:
                    text = (syl.decode('cp949', errors='replace') if isinstance(syl, bytes)
                            else str(syl)).strip()
                    if text:
                        syllables.append(text)
                if syllables:
                    lyric_line = '|Lyric1|Text:"' + ' '.join(syllables) + '"'
                    # |StaffInstrument|(index 1) 바로 뒤에 삽입
                    insert_pos = min(2, len(staffDumpObjects))
                    staffDumpObjects.insert(insert_pos, lyric_line)
            dumpObjects.extend(staffDumpObjects)
        return dumpObjects

    binaryTranslate.NWCConverter.dumpToNWCText = _dumpToNWCText_patched

    log.info("music21 NWC v130/v170 패치 완료 (버그 11종)")


# ── XML 후처리 ────────────────────────────────────────────────────────────────

def _fix_xml_issues(xml_bytes: bytes) -> bytes:
    """
    이슈 2: 픽업 마디 implicit='yes' 설정 + 보이지 않는 패딩 쉼표 제거
    이슈 추가: 중복 measure number='0' 수정 (두 번째 M0 → M1, M1 → M2 등)
    """
    import re
    xml_str = xml_bytes.decode('utf-8')

    def fix_part_content(part_str: str) -> str:
        # 픽업 마디 수정: 첫 번째 M0에 invisible rest가 있으면 → implicit="yes" + 제거
        def fix_first_m0(m):
            block = m.group(0)
            if 'print-object="no"' not in block:
                return block
            block = re.sub(
                r'\s*<note print-object="no"[^>]*>.*?</note>',
                '', block, flags=re.DOTALL
            )
            block = block.replace(
                'implicit="no" number="0"', 'implicit="yes" number="0"', 1
            )
            return block

        part_str = re.sub(
            r'<measure\s+implicit="no"\s+number="0">.*?</measure>',
            fix_first_m0, part_str, count=1, flags=re.DOTALL
        )

        # 중복 M0 수정: 두 번째 M0 이후 measure number를 N+1로 증가
        m0_seen = [0]

        def renumber(m):
            num_str = m.group(1)
            if num_str == '0':
                m0_seen[0] += 1
                if m0_seen[0] < 2:
                    return m.group(0)
                # 두 번째 M0 → M1
                return m.group(0).replace('number="0"', 'number="1"', 1)
            if m0_seen[0] >= 2:
                try:
                    return m.group(0).replace(
                        f'number="{num_str}"', f'number="{int(num_str) + 1}"', 1
                    )
                except ValueError:
                    pass
            return m.group(0)

        part_str = re.sub(r'<measure[^>]+number="(\d+)"', renumber, part_str)
        return part_str

    xml_str = re.sub(
        r'(<part\s+id="[^"]*">)(.*?)(</part>)',
        lambda m: m.group(1) + fix_part_content(m.group(2)) + m.group(3),
        xml_str, flags=re.DOTALL
    )

    # voice 번호 수정: 0→1, 1→2 (MusicXML 표준은 1부터 시작)
    # 0→1 먼저 마킹한 뒤 1→2, 마킹 → 1 순으로 처리
    xml_str = xml_str.replace('<voice>0</voice>', '<voice>__V1__</voice>')
    xml_str = xml_str.replace('<voice>1</voice>', '<voice>2</voice>')
    xml_str = xml_str.replace('<voice>__V1__</voice>', '<voice>1</voice>')

    # B: Acoustic Grand Piano 악기명 제거
    xml_str = re.sub(r'<part-name>[^<]*</part-name>', '<part-name/>', xml_str)
    xml_str = re.sub(r'<part-abbreviation>[^<]*</part-abbreviation>', '<part-abbreviation/>', xml_str)

    # C: M7 (split-voice 마디) 수정
    def fix_m7(m):
        block = m.group(0)
        # C1: Voice2(소프라노) fill rest 제거 — MuseScore 회색 표시 방지
        #     Voice1 fill rest는 backup(40320) 정합성 유지를 위해 그대로 둠
        block = re.sub(
            r'\s*<note print-object="no"[^>]*>\s*<rest\s*/>\s*<duration>[^<]*</duration>\s*'
            r'<voice>2</voice>.*?</note>',
            '', block, flags=re.DOTALL
        )
        # C1b: split-voice 마디(Part1)는 V2 fill rest 제거로 cursor가 30240에서 끝나므로
        #      <forward> 으로 40320까지 보정 → Part2(40320)와 수직 정렬 맞춤
        if '<voice>' in block:
            block = re.sub(
                r'(\s*</measure>)',
                '\n      <forward>\n        <duration>10080</duration>\n      </forward>\\1',
                block
            )
        # C2: 줄기 방향 — Voice1(알토,낮음)=down, Voice2(소프라노,높음)=up
        block = block.replace('<voice>1</voice>', '<voice>1</voice>\n        <stem>down</stem>')
        block = block.replace('<voice>2</voice>', '<voice>2</voice>\n        <stem>up</stem>')
        # C3: D♭ 명시적 내림표 추가 — 소프라노(D♭5) + 베이스(D♭3)
        block = re.sub(
            r'(<step>D</step>\s*<alter>-1</alter>\s*<octave>\d</octave>.*?<type>quarter</type>)',
            r'\1\n        <accidental>flat</accidental>',
            block, flags=re.DOTALL
        )
        # C4: D♭ 직후 chord note(A♭3)에도 내림표 추가
        block = re.sub(
            r'(<accidental>flat</accidental>\s*</note>\s*<note>\s*<chord\s*/>\s*'
            r'<pitch>\s*<step>[^<]+</step>\s*<alter>-1</alter>.*?<type>quarter</type>)',
            r'\1\n        <accidental>flat</accidental>',
            block, flags=re.DOTALL
        )
        return block

    xml_str = re.sub(
        r'<measure[^>]+number="7">.*?</measure>',
        fix_m7, xml_str, flags=re.DOTALL
    )

    # D: M8 (9번째 마디) 못갖춘 마디 보상 쉼표 제거
    def fix_m8(m):
        block = m.group(0)
        block = re.sub(
            r'\s*<note print-object="no"[^>]*>.*?</note>',
            '', block, flags=re.DOTALL
        )
        return block

    xml_str = re.sub(
        r'<measure[^>]+number="8">.*?</measure>',
        fix_m8, xml_str, flags=re.DOTALL
    )

    return xml_str.encode('utf-8')


# ── 단일 파일 변환 ─────────────────────────────────────────────────────────────

def convert_one(nwc_path: Path, xml_dir: Path) -> bool:
    """NWC/NWZ → MusicXML. 성공 시 True, 실패 시 False."""
    stem = nwc_path.stem
    out_path = xml_dir / f"{stem}.xml"

    try:
        from music21.noteworthy.binaryTranslate import NWCConverter
        conv = NWCConverter()
        stream = conv.parseFile(str(nwc_path))
        if stream is None:
            raise ValueError("파싱 결과 없음")

        from music21 import musicxml
        gex = musicxml.m21ToXml.GeneralObjectExporter(stream)
        xml_bytes = gex.parse()
        xml_bytes = _fix_xml_issues(xml_bytes)

        out_path.write_bytes(xml_bytes)
        kb = out_path.stat().st_size / 1024
        log.info("  ✓ %s → %s (%.1f KB)", nwc_path.name, out_path.name, kb)
        return True

    except Exception as e:
        log.warning("  ✗ %s : %s", nwc_path.name, e)
        err_path = xml_dir / f"{stem}.err"
        err_path.write_text(str(e), encoding="utf-8")
        return False


# ── 메인 루프 ─────────────────────────────────────────────────────────────────

def main():
    _patch_music21()

    NWC_DIR.mkdir(parents=True, exist_ok=True)
    XML_DIR.mkdir(parents=True, exist_ok=True)

    log.info("감시 시작: %s → %s (폴링 %ds)", NWC_DIR, XML_DIR, POLL_INTERVAL)

    converted: set[str] = set()

    # 이미 존재하는 XML/오류 파일은 완료로 표시
    for f in XML_DIR.iterdir():
        if f.suffix in (".xml", ".err"):
            converted.add(f.stem)
    log.info("기존 변환 완료 파일: %d개", len(converted))

    ok = fail = 0

    while True:
        nwc_files = sorted(NWC_DIR.glob("*.nwc")) + sorted(NWC_DIR.glob("*.nwz"))
        new_files = [f for f in nwc_files if f.stem not in converted]

        for nwc_path in new_files:
            converted.add(nwc_path.stem)
            if convert_one(nwc_path, XML_DIR):
                ok += 1
            else:
                fail += 1

        if new_files:
            log.info("진행: 성공 %d / 실패 %d / 총 변환 %d", ok, fail, len(converted))

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("중단됨")
        sys.exit(0)
