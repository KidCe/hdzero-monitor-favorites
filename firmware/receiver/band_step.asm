; Recovered Monitor 1.1.1 routine at CODE:0674.
; Input DPL: zero decreases band, nonzero increases band.
; Selection is EXTMEM:(band << 3) | channel. Bank-zero R7 aliases direct byte 07.
; All addresses/call boundaries are preserved; settings/display calls remain stock.
.org 0x0674
rx_band_step:
  MOV A,DPL
  MOV DPTR,#0x6
  MOVX @DPTR,A
  MOV DPTR,#SELECTION_STATE
  MOVX A,@DPTR
  MOV R7,A
  SWAP A
  RL A
  ANL A,#0x1f
  MOV R6,A
  MOV DPTR,#0x6
  MOVX A,@DPTR
  JZ rx_band_down
  MOV A,R6
  INC A
  MOV R5,A
  MOV DPTR,#0x7
  MOVX @DPTR,A
  CJNE R5,#BAND_COUNT,rx_band_merge
  MOV DPTR,#0x7
  CLR A
  MOVX @DPTR,A
  SJMP rx_band_merge
rx_band_down:
  DEC R6
  MOV DPTR,#0x7
  MOV A,R6
  MOVX @DPTR,A
  MOV A,R6
  ADD A,#BAND_DOWN_ADJUST
  JNC rx_band_merge
  MOV DPTR,#0x7
  MOV A,#LAST_BAND
  MOVX @DPTR,A
rx_band_merge:
  MOV DPTR,#0x7
  MOVX A,@DPTR
  SWAP A
  RR A
  ANL A,#0xf8
  MOV R6,A
  ANL 0x07,#0x7
  MOV A,R6
  ORL 0x07,A
  MOV DPTR,#SELECTION_STATE
  MOV A,R7
  MOVX @DPTR,A
  LCALL SETTINGS_SAVE
  MOV DPTR,#0x762
  CLR A
  MOVX @DPTR,A
  MOV DPTR,#0x761
  MOVX @DPTR,A
  MOV DPTR,#0x778
  MOVX @DPTR,A
  MOV DPL,#0x1
  LJMP RECEIVER_REFRESH
