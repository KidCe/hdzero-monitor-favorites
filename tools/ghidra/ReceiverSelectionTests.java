// Execute stock selection prefixes only; stop before persistence/peripheral calls.
// @category HDZero
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.*;
import ghidra.pcode.memstate.MemoryFaultHandler;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.*;

@SuppressWarnings("removal")
public class ReceiverSelectionTests extends GhidraScript {
    private AddressSpace code, external;
    private static final String HASH="ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652";
    protected String expectedHash=HASH;
    protected int imageBytes=62003,bandCount=6,decodeTailBytes=0;
    protected boolean patched=false;
    protected void configure(){}
    protected void addExtraChecks(JsonArray checks,byte[] image)throws Exception{}
    private void initializeDecodeTail(EmulatorHelper helper){
        // Sleigh's pseudo-block decoder may fetch beyond the final LJMP. Blank array
        // bytes are read-only lookahead, never an allowed execution range.
        if(decodeTailBytes>0){
            if(imageBytes+decodeTailBytes>65536)throw new IllegalStateException("Decode lookahead exceeds CODE space");
            byte[] tail=new byte[decodeTailBytes];Arrays.fill(tail,(byte)0xff);
            helper.writeMemory(at(code,imageBytes),tail);
        }
    }
    private void supportCpuNop(EmulatorHelper helper){
        // 8051 Sleigh emits a userop for opcode 00 instead of an empty p-code body.
        // Implement only that architectural no-op; all other userops remain unsupported.
        helper.registerCallOtherCallback("nop",new BreakCallBack(){
            public boolean pcodeCallback(PcodeOpRaw op){
                if(helper.readMemoryByte(helper.getExecutionAddress())!=0)
                    throw new IllegalStateException("NOP callback requires exact opcode 00");
                return true;
            }
        });
    }
    private Address at(AddressSpace space,long offset){return space.getAddress(offset);}
    private class Guard extends MemoryAccessFilter {
        final Set<Long> allowed;
        final EmulatorHelper helper;
        final int stackBase,stackEnd;
        final JsonArray writes=new JsonArray();
        Guard(Set<Long> allowed,EmulatorHelper helper){this(allowed,helper,0,0);}
        Guard(Set<Long> allowed,EmulatorHelper helper,int stackBase,int stackEnd){
            this.allowed=allowed;this.helper=helper;this.stackBase=stackBase;this.stackEnd=stackEnd;
        }
        void check(AddressSpace space,long offset,int size,boolean write){
            String name=space.getName();
            if(space.isRegisterSpace() || space.isUniqueSpace())return;
            if(name.equals("INTMEM") && offset>=0 && offset+size<=8)return;
            if(name.equals("INTMEM") && stackEnd>stackBase && offset>stackBase && offset+size<=stackEnd+1)return;
            if(name.equals("CODE") && !write && offset>=0 && offset+size<=imageBytes+decodeTailBytes)return;
            if(name.equals("EXTMEM")){
                for(int i=0;i<size;i++)if(!allowed.contains(offset+i))
                    throw new IllegalStateException("Unmodeled EXTMEM access at "+Long.toHexString(offset+i));
                return;
            }
            throw new IllegalStateException("Unmodeled "+name+" "+(write?"write":"read")+" at "+Long.toHexString(offset));
        }
        protected void processRead(AddressSpace space,long offset,int size,byte[] bytes){
            check(space,offset,size,false);
            // Sleigh separates Rn register varnodes from directly addressed bank RAM.
            // Alias bank zero explicitly, as on the CPU, rather than accepting two copies.
            if(space.getName().equals("INTMEM") && offset+size<=8)for(int i=0;i<size;i++)
                bytes[i]=(byte)helper.readRegister("R"+(offset+i)).intValue();
        }
        protected void processWrite(AddressSpace space,long offset,int size,byte[] bytes){
            check(space,offset,size,true);
            if(space.getName().equals("INTMEM") && offset+size<=8)for(int i=0;i<size;i++)
                helper.writeRegister("R"+(offset+i),bytes[i]&255);
            if(space.equals(external)){
                JsonObject event=new JsonObject();event.addProperty("offset",String.format("0x%04x",offset));
                event.addProperty("value",bytes[0]&255);writes.add(event);
            }
        }
    }
    protected static class Stage {
        final String name;final int entry,stop,dpl,sp,maxSp;final int[][] ranges;
        final Map<Long,Integer> expected,stack;
        Stage(String name,int entry,int stop,int dpl,int sp,int maxSp,int[][] ranges,
              Map<Long,Integer> expected,Map<Long,Integer> stack){
            this.name=name;this.entry=entry;this.stop=stop;this.dpl=dpl;this.sp=sp;this.maxSp=maxSp;
            this.ranges=ranges;this.expected=expected;this.stack=stack;
        }
    }
    protected JsonObject runConnected(String name,Map<Long,Integer> initial,List<Stage> stages)throws Exception{
        // One emulator instance and RAM snapshot across all stages. Stage dispatch models
        // the caller scheduling only; all LCALL/RET instructions run through Sleigh.
        EmulatorHelper emulator=new EmulatorHelper(currentProgram);initializeDecodeTail(emulator);
        AddressSpace internal=currentProgram.getAddressFactory().getAddressSpace("INTMEM");
        Set<Long> allowed=new HashSet<>(initial.keySet());
        for(Stage stage:stages)allowed.addAll(stage.expected.keySet());
        Guard guard=new Guard(allowed,emulator,0x40,0x48);
        try{
            for(String reg:new String[]{"R0","R1","R2","R3","R4","R5","R6","R7","ACC","B","SP","DPTR","PSW"})
                emulator.writeRegister(reg,0);
            emulator.writeRegister("SP",0x40); // Observed startup MOV 81,#40 at CODE:0039.
            emulator.writeMemory(at(internal,0),new byte[8]);
            byte[] stack=new byte[8];Arrays.fill(stack,(byte)0xa5);
            emulator.writeMemory(at(internal,0x41),stack);
            for(long offset:allowed)emulator.writeMemory(at(external,offset),new byte[]{(byte)(int)initial.getOrDefault(offset,0)});
            emulator.setMemoryFaultHandler(new MemoryFaultHandler(){
                public boolean unknownAddress(Address address,boolean write){throw new IllegalStateException("Unknown address "+address);}
                public boolean uninitializedRead(Address address,int size,byte[] buffer,int offset){
                    throw new IllegalStateException("Uninitialized memory at "+address);
                }
            });
            emulator.getEmulator().addMemoryAccessFilter(guard);supportCpuNop(emulator);
            JsonArray checkpoints=new JsonArray();
            for(Stage stage:stages){
                emulator.writeRegister("PC",stage.entry);
                if(stage.dpl>=0)emulator.writeRegister("DPL",stage.dpl);
                JsonArray trace=new JsonArray(),calls=new JsonArray();int maxSp=emulator.readRegister("SP").intValue();
                boolean reached=false;
                for(int step=0;step<1000;step++){
                    Address pc=emulator.getExecutionAddress();long offset=pc.getOffset();
                    int sp=emulator.readRegister("SP").intValue();maxSp=Math.max(maxSp,sp);
                    if(sp<0x40 || sp>0x48)throw new IllegalStateException("Stack escaped modeled arena");
                    if((emulator.readRegister("PSW").intValue()&0x18)!=0)throw new IllegalStateException("Only bank zero is modeled");
                    if(offset==stage.stop){reached=true;break;}
                    boolean inRange=false;
                    for(int[] range:stage.ranges)if(offset>=range[0] && offset<range[1])inRange=true;
                    if(!inRange)throw new IllegalStateException("Escaped connected stage "+stage.name+" at "+pc);
                    trace.add(pc.toString());
                    if((emulator.readMemoryByte(pc)&255)==0x12){
                        JsonObject call=new JsonObject();call.addProperty("pc",pc.toString());call.addProperty("sp_before",sp);calls.add(call);
                    }
                    if(!emulator.step(monitor))throw new IllegalStateException(name+" / "+stage.name+": "+emulator.getLastError());
                }
                if(!reached)throw new IllegalStateException("Connected-stage instruction budget exhausted");
                if(emulator.readRegister("SP").intValue()!=stage.sp || maxSp!=stage.maxSp)
                    throw new IllegalStateException(name+" / "+stage.name+": unexpected live or maximum stack depth");
                JsonObject checkpoint=new JsonObject();checkpoint.addProperty("stage",stage.name);
                checkpoint.addProperty("stop_pc",String.format("0x%04x",stage.stop));
                checkpoint.addProperty("sp",stage.sp);checkpoint.addProperty("maximum_sp",maxSp);
                JsonObject outputs=new JsonObject();
                for(Map.Entry<Long,Integer> item:stage.expected.entrySet()){
                    int value=emulator.readMemoryByte(at(external,item.getKey()))&255;
                    if(value!=item.getValue())throw new IllegalStateException(name+" / "+stage.name+": RAM mismatch at "+Long.toHexString(item.getKey()));
                    outputs.addProperty(String.format("0x%04x",item.getKey()),value);
                }
                for(Map.Entry<Long,Integer> item:stage.stack.entrySet()){
                    int value=emulator.readMemoryByte(at(internal,item.getKey()))&255;
                    if(value!=item.getValue())throw new IllegalStateException(name+" / "+stage.name+": return-address mismatch");
                }
                checkpoint.add("outputs",outputs);checkpoint.add("trace",trace);checkpoint.add("calls",calls);
                checkpoints.add(checkpoint);
            }
            JsonObject row=new JsonObject();row.addProperty("kind","connected_session");row.addProperty("name",name);
            row.addProperty("passed",true);row.add("checkpoints",checkpoints);row.add("external_writes",guard.writes);
            row.addProperty("boundary","Caller scheduling is explicit; nested CPU calls execute; no hardware or delay/tuning success is fabricated");
            return row;
        }finally{emulator.dispose();}
    }
    private JsonObject runPrefix(int entry,int selection,int direction,boolean includeSelection)throws Exception{
        EmulatorHelper emulator=new EmulatorHelper(currentProgram);
        initializeDecodeTail(emulator);
        Set<Long> allowed=new HashSet<>();
        int scratch=entry==0x674?6:8;
        allowed.add((long)scratch);allowed.add((long)scratch+1);
        if(includeSelection)allowed.add(0xd85L);
        Guard guard=new Guard(allowed,emulator);
        JsonObject row=new JsonObject();row.addProperty("entry",String.format("0x%04x",entry));
        row.addProperty("selection",selection);row.addProperty("direction",direction);
        try{
            for(String reg:new String[]{"R0","R1","R2","R3","R4","R5","R6","R7","ACC","B","SP","DPTR","PSW"})
                emulator.writeRegister(reg,0);
            for(long offset:allowed)emulator.writeMemory(at(external,offset),new byte[]{0});
            emulator.writeMemory(at(currentProgram.getAddressFactory().getAddressSpace("INTMEM"),0),new byte[8]);
            if(includeSelection)emulator.writeMemory(at(external,0xd85),new byte[]{(byte)selection});
            emulator.writeRegister("DPL",direction);emulator.writeRegister("PC",entry);
            emulator.setMemoryFaultHandler(new MemoryFaultHandler(){
                public boolean unknownAddress(Address address,boolean write){throw new IllegalStateException("Unknown address "+address);}
                public boolean uninitializedRead(Address address,int size,byte[] buffer,int offset){
                    throw new IllegalStateException("Uninitialized memory at "+address);
                }
            });
            emulator.getEmulator().addMemoryAccessFilter(guard);
            supportCpuNop(emulator);
            JsonArray trace=new JsonArray();
            for(int step=0;step<200;step++){
                Address pc=emulator.getExecutionAddress();
                if((emulator.readRegister("PSW").intValue()&0x18)!=0)
                    throw new IllegalStateException("Only register bank zero is modeled");
                if(pc.getOffset()==(entry==0x674?0x6c0:0x70f)){
                    int actual=emulator.readMemoryByte(at(external,0xd85))&255;
                    int band=selection>>3,channel=selection&7;
                    int expected=entry==0x674?(((band+(direction==0?bandCount-1:1))%bandCount)<<3)|channel:
                        (selection&0xf8)|((channel+(direction==0?7:1))&7);
                    if(!includeSelection || actual!=expected)throw new IllegalStateException("Selection mismatch: "+actual+" != "+expected);
                    row.addProperty("result",actual);row.addProperty("expected",expected);
                    row.addProperty("stop_pc",pc.toString());
                    row.addProperty("stop_before_call_target","0x9f29");row.addProperty("passed",true);
                    row.add("trace",trace);row.add("external_writes",guard.writes);return row;
                }
                if(pc.getOffset()<entry || pc.getOffset()>=(entry==0x674?0x6c0:0x70f))
                    throw new IllegalStateException("Execution outside selection prefix: "+pc);
                trace.add(pc.toString());
                if(!emulator.step(monitor))throw new IllegalStateException(emulator.getLastError());
            }
            throw new IllegalStateException("Instruction budget exhausted");
        }catch(Exception error){
            if(includeSelection)throw error;
            String detail=error.toString()+" "+emulator.getLastError();
            if(!detail.contains("Uninitialized memory at EXTMEM:0d85") ||
                emulator.getExecutionAddress().getOffset()!=0x6df)throw error;
            row.addProperty("passed",true);row.addProperty("expected_block",detail);return row;
        }finally{emulator.dispose();}
    }
    protected JsonObject runFragment(String name,int entry,int stop,Map<Long,Integer> initial,
                                   Map<Long,Integer> expected,int dpl)throws Exception{
        return runFragment(name,entry,stop,initial,expected,dpl,Map.of());
    }
    protected JsonObject runFragment(String name,int entry,int stop,Map<Long,Integer> initial,
                                   Map<Long,Integer> expected,int dpl,Map<String,Integer> registers)throws Exception{
        return runFragment(name,entry,stop,initial,expected,dpl,registers,Map.of());
    }
    protected JsonObject runFragment(String name,int entry,int stop,Map<Long,Integer> initial,
                                   Map<Long,Integer> expected,int dpl,Map<String,Integer> registers,
                                   Map<String,Integer> initialRegisters)throws Exception{
        return runFragmentRegions(name,entry,stop,initial,expected,dpl,registers,initialRegisters,new int[0][]);
    }
    protected JsonObject runFragmentRegions(String name,int entry,int stop,Map<Long,Integer> initial,
                                   Map<Long,Integer> expected,int dpl,Map<String,Integer> registers,
                                   Map<String,Integer> initialRegisters,int[][] extraRanges)throws Exception{
        EmulatorHelper emulator=new EmulatorHelper(currentProgram);
        initializeDecodeTail(emulator);
        Set<Long> allowed=new HashSet<>(initial.keySet());allowed.addAll(expected.keySet());
        Guard guard=new Guard(allowed,emulator);
        try{
            for(String reg:new String[]{"R0","R1","R2","R3","R4","R5","R6","R7","ACC","B","SP","DPTR","PSW"})
                emulator.writeRegister(reg,0);
            emulator.writeMemory(at(currentProgram.getAddressFactory().getAddressSpace("INTMEM"),0),new byte[8]);
            for(long offset:allowed)emulator.writeMemory(at(external,offset),new byte[]{(byte)(int)initial.getOrDefault(offset,0)});
            emulator.writeRegister("DPL",dpl);emulator.writeRegister("PC",entry);
            for(Map.Entry<String,Integer> item:initialRegisters.entrySet()){
                if(!item.getKey().matches("R[0-7]"))throw new IllegalStateException("Only bank-zero register inputs are accepted");
                emulator.writeRegister(item.getKey(),item.getValue());
            }
            emulator.setMemoryFaultHandler(new MemoryFaultHandler(){
                public boolean unknownAddress(Address address,boolean write){throw new IllegalStateException("Unknown address "+address);}
                public boolean uninitializedRead(Address address,int size,byte[] buffer,int offset){
                    throw new IllegalStateException("Uninitialized memory at "+address);
                }
            });
            emulator.getEmulator().addMemoryAccessFilter(guard);
            supportCpuNop(emulator);
            JsonArray trace=new JsonArray();
            boolean reached=false;
            for(int step=0;step<200;step++){
                Address pc=emulator.getExecutionAddress();
                if((emulator.readRegister("PSW").intValue()&0x18)!=0)
                    throw new IllegalStateException("Only register bank zero is modeled");
                if(pc.getOffset()==stop){reached=true;break;}
                boolean inRange=pc.getOffset()>=entry && pc.getOffset()<=stop;
                for(int[] range:extraRanges)if(pc.getOffset()>=range[0] && pc.getOffset()<range[1])inRange=true;
                if(!inRange)throw new IllegalStateException("Escaped fragment "+pc);
                trace.add(pc.toString());
                if(!emulator.step(monitor))throw new IllegalStateException(emulator.getLastError());
            }
            if(!reached)throw new IllegalStateException("Instruction budget exhausted");
            JsonObject row=new JsonObject();row.addProperty("name",name);
            row.addProperty("entry",String.format("0x%04x",entry));row.addProperty("stop_pc",String.format("0x%04x",stop));
            JsonObject outputs=new JsonObject();
            for(Map.Entry<Long,Integer> item:expected.entrySet()){
                int value=emulator.readMemoryByte(at(external,item.getKey()))&255;
                if(value!=item.getValue())throw new IllegalStateException(name+" mismatch at "+Long.toHexString(item.getKey()));
                outputs.addProperty(String.format("0x%04x",item.getKey()),value);
            }
            row.add("outputs",outputs);row.add("trace",trace);row.add("external_writes",guard.writes);
            JsonObject cpu=new JsonObject();
            for(Map.Entry<String,Integer> item:registers.entrySet()){
                int value=emulator.readRegister(item.getKey()).intValue();
                if(value!=item.getValue())throw new IllegalStateException(name+" register mismatch "+item.getKey());
                cpu.addProperty(item.getKey(),value);
            }
            row.add("register_outputs",cpu);
            row.addProperty("passed",true);return row;
        }finally{emulator.dispose();}
    }
    public void run()throws Exception{
        configure();
        if(!currentProgram.getLanguageID().toString().equals("8051:BE:16:default"))throw new IllegalStateException("Unexpected language");
        code=currentProgram.getAddressFactory().getAddressSpace("CODE");
        external=currentProgram.getAddressFactory().getAddressSpace("EXTMEM");
        byte[] image=new byte[imageBytes];currentProgram.getMemory().getBytes(at(code,0),image);
        String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(image));
        if(!hash.equals(expectedHash))throw new IllegalStateException("Only the explicitly pinned receiver fixture is accepted");
        Path output=Paths.get(getScriptArgs()[0]);if(Files.exists(output))throw new IllegalStateException("Report already exists");
        JsonObject report=new JsonObject();report.addProperty("image_sha256",hash);
        report.addProperty("backend","Ghidra 12.1.4 EmulatorHelper / 8051 Sleigh p-code");
        report.addProperty("hardware_access",false);report.addProperty("patched_image",patched);
        report.addProperty("analysis_only",true);report.addProperty("band_count",bandCount);
        report.addProperty("blank_code_decode_lookahead_bytes",decodeTailBytes);
        report.addProperty("boundary","Bounded actual-instruction fragments; peripheral calls are never executed or stubbed as successful");
        JsonArray checks=new JsonArray();
        for(int entry:new int[]{0x674,0x6d6})for(int selection=0;selection<bandCount*8;selection++)for(int direction=0;direction<2;direction++)
            checks.add(runPrefix(entry,selection,direction,true));
        checks.add(runPrefix(0x6d6,0,1,false));
        String[] labels={"L6","L7","R1","R2","F2","F4","R7","R8"};
        int[] identities={0x2d,0x2e,0x20,0x21,0x19,0x1b,0x26,0x27};
        int[] rfIndices={17,18,0,1,10,11,6,7};
        int[] words={0x2786,0x2798,0x281d,0x2890,0x2910,0x2984,0x2a0c,0x2a1f};
        Map<Long,Integer> letters=new HashMap<>();
        for(int i=0;i<6;i++)letters.put(0xfe7L+i,(int)"ABEFRL".charAt(i));
        checks.add(runFragment("Stock band-letter initialization",0xb576,0xb59e,Map.of(0xfe6L,0),letters,1));
        for(int i=0;i<8;i++){
            checks.add(runFragment(labels[i]+" RF-index lookup prefix",0xc74,0xc83,Map.of(),Map.of(0x36L,rfIndices[i]),identities[i]));
            checks.add(runFragment(labels[i]+" second tune-table lookup fragment",0x5d32,0x5d61,
                Map.of(0x777L,identities[i]),Map.of(0xdafL,words[i]&255,0xdb0L,words[i]>>8,0xdb1L,0,0xdb2L,0),0));
            Map<Long,Integer> initial=new HashMap<>(letters);initial.put(0xd85L,identities[i]);
            checks.add(runFragment(labels[i]+" OSD label fragment",0xb885,0xb8a9,initial,
                Map.of(0xfedL,(int)labels[i].charAt(0),0xfeeL,(int)labels[i].charAt(1)),0));
        }
        for(int invalid:new int[]{bandCount*8,bandCount*8+7,0xff})checks.add(runFragment("Invalid selection "+invalid,
            0x9d44,0x9d5f,Map.of(0xd85L,invalid),Map.of(0xd85L,0x20,0xd8fL,1),0));
        addExtraChecks(checks,image);
        report.add("checks",checks);
        report.addProperty("fragment_limits","Independent fragments and explicitly scheduled bounded sessions; no integrated boot, bus persistence, RF transactions or display rendering");
        int connected=0;for(JsonElement check:checks)if(check.getAsJsonObject().has("kind") &&
            check.getAsJsonObject().get("kind").getAsString().equals("connected_session"))connected++;
        report.addProperty("connected_session_checks",connected);
        if(patched){
            report.addProperty("feature_acceptance",false);
            report.addProperty("scan_boundary","P long-press activation is guarded; forced internal scan flags still reach the original 12-channel scan");
        }
        report.addProperty("passed",checks.size());
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardCharsets.UTF_8);
        println("Passed "+checks.size()+" receiver selection-prefix checks.");
    }
}
