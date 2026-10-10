; Favorites status-bar label: "P1 L6 HDZ" instead of "P1 HDZERO".
; AI assistance is disclosed in the project README.
; Entered by LJMP from the two final label draws (B87F busy, B8F8 normal), which
; originally were MOV DPL,#0x15 / LJMP 0xB1DF. Stock code has just rebuilt the
; label buffer 0FED..: band letter, slot digit, then " HDZERO", " ANALOG" or
; "   " plus progress dots. Stock bands fall through unchanged. For P1..P8 the
; buffer becomes "Pn" + " " + underlying letter/digit + " " + the first three
; suffix characters (NUL shown as space), drawn with length 9 at column 21.
; Writes stay inside 0FED..0FF5, below the 0FF7 display cache. No added stack.
.org FAVORITES_LABEL
  MOV DPTR,#SELECTION_STATE
  MOVX A,@DPTR
  CLR C
  SUBB A,#0x30
  JC label_draw
  MOV R7,A                ; slot 0..7
  CLR C
  SUBB A,#8
  JNC label_draw
  ; Move suffix characters 3..5 to 6..8, highest first (ranges do not overlap).
  MOV DPTR,#0xff2
  MOVX A,@DPTR
  JNZ label_c5
  MOV A,#0x20
label_c5:
  MOV DPTR,#0xff5
  MOVX @DPTR,A
  MOV DPTR,#0xff1
  MOVX A,@DPTR
  JNZ label_c4
  MOV A,#0x20
label_c4:
  MOV DPTR,#0xff4
  MOVX @DPTR,A
  MOV DPTR,#0xff0
  MOVX A,@DPTR
  JNZ label_c3
  MOV A,#0x20
label_c3:
  MOV DPTR,#0xff3
  MOVX @DPTR,A
  ; Separators at 2 and 5.
  MOV A,#0x20
  MOV DPTR,#0xfef
  MOVX @DPTR,A
  MOV DPTR,#0xff2
  MOVX @DPTR,A
  ; Underlying stock ID: digit at 4, band letter at 3.
  MOV A,R7
  MOV DPTR,#FAVORITES_LABEL_IDS
  MOVC A,@A+DPTR
  MOV R7,A
  ANL A,#7
  ADD A,#0x31
  MOV DPTR,#0xff1
  MOVX @DPTR,A
  MOV A,R7
  SWAP A
  RL A
  ANL A,#0x1f
  MOV DPTR,#BAND_LETTERS
  MOVC A,@A+DPTR
  MOV DPTR,#0xff0
  MOVX @DPTR,A
  ; Draw nine characters (busy path originally drew six).
  MOV DPTR,#0xfc6
  MOV A,#9
  MOVX @DPTR,A
label_draw:
  MOV DPL,#0x15
  LJMP 0xb1df
