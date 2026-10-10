; HISTORICAL: used in v4/v5 only. Removed in v6, where long press starts the stock scan in every band
; and the scan list contains the Favorites. No longer included by tools/monitor_receiver_source.py.
; New guards at the two recovered long-press scan activation sites, 0971/09BD.
; AI assistance is disclosed in the project README.
; Busy/active guards have already executed. Preserve all existing stock bands.
; P1..P8 skip activation: the stock scan excludes Lowband and could leave P mode.
; No added RAM or stack usage. Restore carry=0: both original entry paths follow
; an equal CJNE against 1. R0..R7, scan flags and selection are intact.
.org SCAN_UP_GUARD
  MOV DPTR,#SELECTION_STATE
  MOVX A,@DPTR
  CLR C
  SUBB A,#0x30
  JC scan_up_stock
  CLR C
  SUBB A,#8
  JNC scan_up_stock
  CLR C
  LJMP 0x09cb
scan_up_stock:
  CLR C
  CLR A
  MOV DPTR,#0x767
  LJMP 0x0974

.org SCAN_DOWN_GUARD
  MOV DPTR,#SELECTION_STATE
  MOVX A,@DPTR
  CLR C
  SUBB A,#0x30
  JC scan_down_stock
  CLR C
  SUBB A,#8
  JNC scan_down_stock
  CLR C
  LJMP 0x09cb
scan_down_stock:
  CLR C
  CLR A
  MOV DPTR,#0x768
  LJMP 0x09c0
