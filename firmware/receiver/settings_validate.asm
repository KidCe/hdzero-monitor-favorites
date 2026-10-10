; Reconstructed from hash-pinned installed Monitor 1.1.1, CODE:9D44..9E11.
; AI assistance is disclosed in the project README.
; Fixed addresses, exact instruction widths and stock defaults are intentional.
; This pure validator makes no peripheral calls. Field names beyond selection/mode
; remain address-based until independently identified; this is not original C.
.org 0x9d44

; Clear the correction flag before validating this saved-state snapshot.
  MOV DPTR,#0xd8f ; CODE:9D44
  CLR A ; CODE:9D47
  MOVX @DPTR,A ; CODE:9D48

; Selection is a packed band/channel ID. Keep all 48 stock IDs; Favorites adds 48..55.
  MOV DPTR,#0xd85 ; CODE:9D49
  MOVX A,@DPTR ; CODE:9D4C
  MOV R7,A ; CODE:9D4D
  CJNE R7,#SELECTION_COUNT,0x9d51 ; CODE:9D4E
  JC 0x9d5f ; CODE:9D51
  MOV DPTR,#0xd85 ; CODE:9D53
  MOV A,#0x20 ; CODE:9D56
  MOVX @DPTR,A ; CODE:9D58
  MOV DPTR,#0xd8f ; CODE:9D59
  MOV A,#0x1 ; CODE:9D5C
  MOVX @DPTR,A ; CODE:9D5E

; Input-mode state at D86: accept 0 or 1, otherwise default to 0.
  MOV DPTR,#0xd86 ; CODE:9D5F
  MOVX A,@DPTR ; CODE:9D62
  MOV R7,A ; CODE:9D63
  CJNE R7,#0x2,0x9d67 ; CODE:9D64
  JC 0x9d73 ; CODE:9D67
  MOV DPTR,#0xd86 ; CODE:9D69
  CLR A ; CODE:9D6C
  MOVX @DPTR,A ; CODE:9D6D
  MOV DPTR,#0xd8f ; CODE:9D6E
  INC A ; CODE:9D71
  MOVX @DPTR,A ; CODE:9D72

; D87: only the erased byte FF is invalid; default 88.
  MOV DPTR,#0xd87 ; CODE:9D73
  MOVX A,@DPTR ; CODE:9D76
  MOV R7,A ; CODE:9D77
  ADD A,#0x1 ; CODE:9D78
  JNC 0x9d88 ; CODE:9D7A
  MOV DPTR,#0xd87 ; CODE:9D7C
  MOV A,#0x88 ; CODE:9D7F
  MOVX @DPTR,A ; CODE:9D81
  MOV DPTR,#0xd8f ; CODE:9D82
  MOV A,#0x1 ; CODE:9D85
  MOVX @DPTR,A ; CODE:9D87

; D88: only FF is invalid; default 56.
  MOV DPTR,#0xd88 ; CODE:9D88
  MOVX A,@DPTR ; CODE:9D8B
  MOV R7,A ; CODE:9D8C
  ADD A,#0x1 ; CODE:9D8D
  JNC 0x9d9d ; CODE:9D8F
  MOV DPTR,#0xd88 ; CODE:9D91
  MOV A,#0x56 ; CODE:9D94
  MOVX @DPTR,A ; CODE:9D96
  MOV DPTR,#0xd8f ; CODE:9D97
  MOV A,#0x1 ; CODE:9D9A
  MOVX @DPTR,A ; CODE:9D9C

; D89: only FF is invalid; default 8F.
  MOV DPTR,#0xd89 ; CODE:9D9D
  MOVX A,@DPTR ; CODE:9DA0
  MOV R7,A ; CODE:9DA1
  ADD A,#0x1 ; CODE:9DA2
  JNC 0x9db2 ; CODE:9DA4
  MOV DPTR,#0xd89 ; CODE:9DA6
  MOV A,#0x8f ; CODE:9DA9
  MOVX @DPTR,A ; CODE:9DAB
  MOV DPTR,#0xd8f ; CODE:9DAC
  MOV A,#0x1 ; CODE:9DAF
  MOVX @DPTR,A ; CODE:9DB1

; D8A: accept 0..100 inclusive; default 80. Preserve the original ADD/carry check.
  MOV DPTR,#0xd8a ; CODE:9DB2
  MOVX A,@DPTR ; CODE:9DB5
  MOV R7,A ; CODE:9DB6
  ADD A,#0x9b ; CODE:9DB7
  JNC 0x9dc7 ; CODE:9DB9
  MOV DPTR,#0xd8a ; CODE:9DBB
  MOV A,#0x50 ; CODE:9DBE
  MOVX @DPTR,A ; CODE:9DC0
  MOV DPTR,#0xd8f ; CODE:9DC1
  MOV A,#0x1 ; CODE:9DC4
  MOVX @DPTR,A ; CODE:9DC6

; D8B: accept 1..6 inclusive; default 1.
  MOV DPTR,#0xd8b ; CODE:9DC7
  MOVX A,@DPTR ; CODE:9DCA
  MOV R7,A ; CODE:9DCB
  ADD A,#0xf9 ; CODE:9DCC
  JC 0x9dd5 ; CODE:9DCE
  CJNE R7,#0x1,0x9dd3 ; CODE:9DD0
  JNC 0x9ddf ; CODE:9DD3
  MOV DPTR,#0xd8b ; CODE:9DD5
  MOV A,#0x1 ; CODE:9DD8
  MOVX @DPTR,A ; CODE:9DDA
  MOV DPTR,#0xd8f ; CODE:9DDB
  MOVX @DPTR,A ; CODE:9DDE

; D8D: accept 28..42 inclusive; default 28. D8C is not touched by this function.
  MOV DPTR,#0xd8d ; CODE:9DDF
  MOVX A,@DPTR ; CODE:9DE2
  MOV R7,A ; CODE:9DE3
  ADD A,#0xd5 ; CODE:9DE4
  JC 0x9ded ; CODE:9DE6
  CJNE R7,#0x1c,0x9deb ; CODE:9DE8
  JNC 0x9df9 ; CODE:9DEB
  MOV DPTR,#0xd8d ; CODE:9DED
  MOV A,#0x1c ; CODE:9DF0
  MOVX @DPTR,A ; CODE:9DF2
  MOV DPTR,#0xd8f ; CODE:9DF3
  MOV A,#0x1 ; CODE:9DF6
  MOVX @DPTR,A ; CODE:9DF8

; D8E: accept 0 or 1; default 1.
  MOV DPTR,#0xd8e ; CODE:9DF9
  MOVX A,@DPTR ; CODE:9DFC
  ADD A,#0xfe ; CODE:9DFD
  JNC 0x9e0b ; CODE:9DFF
  MOV DPTR,#0xd8e ; CODE:9E01
  MOV A,#0x1 ; CODE:9E04
  MOVX @DPTR,A ; CODE:9E06
  MOV DPTR,#0xd8f ; CODE:9E07
  MOVX @DPTR,A ; CODE:9E0A

; Return 1 in DPL when any field was corrected, otherwise 0. Callers can re-save.
  MOV DPTR,#0xd8f ; CODE:9E0B
  MOVX A,@DPTR ; CODE:9E0E
  MOV DPL,A ; CODE:9E0F
  RET ; CODE:9E11
