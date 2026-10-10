; Recovered Monitor 1.1.1 routine at CODE:06D6.
; Input DPL: zero decreases channel, nonzero increases channel.
; Wrap channel within its current band, then use the stock save/refresh path.
.org 0x06d6
rx_channel_step:
  MOV A,DPL
  MOV DPTR,#0x8
  MOVX @DPTR,A
  MOV DPTR,#SELECTION_STATE
  MOVX A,@DPTR
  MOV R7,A
  MOV A,#0x7
  ANL A,R7
  MOV R6,A
  MOV DPTR,#0x8
  MOVX A,@DPTR
  JZ rx_channel_down
  MOV DPTR,#0x9
  MOV A,R6
  INC A
  MOVX @DPTR,A
  SJMP rx_channel_merge
rx_channel_down:
  MOV A,R6
  DEC A
  MOV DPTR,#0x9
  MOVX @DPTR,A
rx_channel_merge:
  MOV DPTR,#0x9
  MOVX A,@DPTR
  ANL 0xe0,#0x7 ; Direct ACC form is three bytes in the original routine.
  MOVX @DPTR,A
  ANL 0x07,#0xf8
  MOV DPTR,#0x9
  MOVX A,@DPTR
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
