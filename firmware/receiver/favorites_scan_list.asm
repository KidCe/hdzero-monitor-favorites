; Scan list for a scan started in the P band (v7).
; AI assistance is disclosed in the project README.
; Entered by LJMP from 6D6C, which originally was MOV DPTR,#0x816 / MOV A,#0x20 at the
; start of the scan-list initializer (run on every main-loop pass). The whole scan
; (6F84..7629) runs inside that same call: it tunes every entry via 0C74/5D19, picks one
; and writes it to SELECTION_STATE; cancel (7646) selects entry 0. With P1..P8 selected
; the list holds the same frequencies in the same order, Favorites as P IDs 30..37, so the
; start position is the current slot and the result stays in the P band. Only A, DPTR and C.
.org FAVORITES_SCAN_LIST
  MOV DPTR,#SELECTION_STATE
  MOVX A,@DPTR
  CLR C
  SUBB A,#0x30
  JC scan_list_stock
  CLR C
  SUBB A,#8
  JNC scan_list_stock
  MOV DPTR,#0x816
  MOV A,#P_SCAN_0
  MOVX @DPTR,A
  MOV DPTR,#0x817
  MOV A,#P_SCAN_1
  MOVX @DPTR,A
  MOV DPTR,#0x818
  MOV A,#P_SCAN_2
  MOVX @DPTR,A
  MOV DPTR,#0x819
  MOV A,#P_SCAN_3
  MOVX @DPTR,A
  MOV DPTR,#0x81a
  MOV A,#P_SCAN_4
  MOVX @DPTR,A
  MOV DPTR,#0x81b
  MOV A,#P_SCAN_5
  MOVX @DPTR,A
  MOV DPTR,#0x81c
  MOV A,#P_SCAN_6
  MOVX @DPTR,A
  MOV DPTR,#0x81d
  MOV A,#P_SCAN_7
  MOVX @DPTR,A
  MOV DPTR,#0x81e
  MOV A,#P_SCAN_8
  MOVX @DPTR,A
  MOV DPTR,#0x81f
  MOV A,#P_SCAN_9
  MOVX @DPTR,A
  MOV DPTR,#0x820
  MOV A,#P_SCAN_10
  MOVX @DPTR,A
  MOV DPTR,#0x821
  MOV A,#P_SCAN_11
  MOVX @DPTR,A
  LJMP 0x6dac
scan_list_stock:
  MOV DPTR,#0x816
  MOV A,#0x20
  LJMP 0x6d71
