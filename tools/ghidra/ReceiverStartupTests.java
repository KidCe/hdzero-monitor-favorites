// Bounded C-runtime initialization, stopping before receiver hardware setup.
// @category HDZero
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.*;
import ghidra.pcode.memstate.MemoryFaultHandler;
import ghidra.program.model.address.*;

public class ReceiverStartupTests extends GhidraScript {
    private AddressSpace code,external,internal,sfr,bits;
    private int imageBytes;
    private Address at(AddressSpace space,long offset){return space.getAddress(offset);}
    private String hash(byte[] bytes)throws Exception{
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    private class CpuMemory extends MemoryAccessFilter {
        final EmulatorHelper helper;
        int externalWrites=0;
        CpuMemory(EmulatorHelper helper){this.helper=helper;}
        void check(AddressSpace space,long offset,int size,boolean write){
            if(space.isRegisterSpace() || space.isUniqueSpace())return;
            if(space.equals(code) && !write && offset>=0 && offset+size<=imageBytes)return;
            if(space.equals(external) && offset>=0 && offset+size<=0x1100)return;
            if(space.equals(internal) && offset>=0 && offset+size<=256)return;
            if(space.equals(sfr) && size==1 && (offset==0x81 || offset==0xa0))return;
            if(space.equals(bits) && size==1 && (offset==4 || offset==5 || offset==8 || offset==9))return;
            throw new IllegalStateException("Startup accessed unmodeled "+space.getName()+":"+Long.toHexString(offset));
        }
        protected void processRead(AddressSpace space,long offset,int size,byte[] bytes){
            check(space,offset,size,false);
            if(space.equals(internal))for(int i=0;i<size && offset+i<8;i++)
                bytes[i]=(byte)helper.readRegister("R"+(offset+i)).intValue();
            if(space.equals(sfr) && offset==0x81)bytes[0]=(byte)helper.readRegister("SP").intValue();
            if(space.equals(bits))bytes[0]=(byte)((helper.readMemoryByte(at(internal,0x20+(offset>>3)))>>(offset&7))&1);
        }
        protected void processWrite(AddressSpace space,long offset,int size,byte[] bytes){
            check(space,offset,size,true);
            if(space.equals(internal))for(int i=0;i<size && offset+i<8;i++)
                helper.writeRegister("R"+(offset+i),bytes[i]&255);
            if(space.equals(sfr) && offset==0x81)helper.writeRegister("SP",bytes[0]&255);
            if(space.equals(bits)){
                if(bytes[0]!=0 && bytes[0]!=1)throw new IllegalStateException("Invalid bit value");
                Address address=at(internal,0x20+(offset>>3));int mask=1<<(offset&7);
                int value=(helper.readMemoryByte(address)&255)&~mask;
                helper.writeMemory(address,new byte[]{(byte)(value|(bytes[0]==0?0:mask))});
            }
            if(space.equals(external))externalWrites+=size;
        }
    }
    private JsonObject execute(byte[] image,int fill)throws Exception{
        EmulatorHelper helper=new EmulatorHelper(currentProgram);
        CpuMemory memory=new CpuMemory(helper);
        try{
            for(String reg:new String[]{"R0","R1","R2","R3","R4","R5","R6","R7","ACC","B","SP","DPTR","PSW"})
                helper.writeRegister(reg,0);
            byte[] ram=new byte[0x1100];Arrays.fill(ram,(byte)fill);
            helper.writeMemory(at(external,0),ram);
            byte[] iram=new byte[256];Arrays.fill(iram,(byte)fill);
            helper.writeMemory(at(internal,0),iram);
            helper.writeMemory(at(sfr,0x81),new byte[]{0});
            helper.writeMemory(at(sfr,0xa0),new byte[]{(byte)0xff});
            for(long bit:new long[]{4,5,8,9})helper.writeMemory(at(bits,bit),new byte[]{0});
            helper.setMemoryFaultHandler(new MemoryFaultHandler(){
                public boolean unknownAddress(Address address,boolean write){throw new IllegalStateException("Unknown startup address "+address);}
                public boolean uninitializedRead(Address address,int size,byte[] buffer,int offset){
                    throw new IllegalStateException("Uninitialized startup address "+address);
                }
            });
            helper.getEmulator().addMemoryAccessFilter(memory);
            helper.writeRegister("PC",0);
            int steps=0,pagedWrites=0,maxSp=0;
            for(;steps<20000;steps++){
                long pc=helper.getExecutionAddress().getOffset();
                int sp=helper.readRegister("SP").intValue();maxSp=Math.max(maxSp,sp);
                if(pc==0x8c2f)break; // First instruction calls hardware init 7A76; do not execute it.
                if(!(pc==0 || (pc>=0x36 && pc<0x2a9) || (pc>=0xc683 && pc<0xc687)))
                    throw new IllegalStateException("Startup escaped bounded CODE at "+Long.toHexString(pc));
                if((helper.readRegister("PSW").intValue()&0x18)!=0 || sp>0x42)
                    throw new IllegalStateException("Startup changed register bank or exceeded observed stack");
                if(pc==0x59){
                    // The generic Sleigh RiX operand drops the P2 high byte. Implement
                    // this exact standard CPU instruction, rather than allowing a wrong
                    // low-page write and fabricating the missing initializer afterwards.
                    if((helper.readMemoryByte(at(code,pc))&255)!=0xf2)
                        throw new IllegalStateException("Paged adapter requires opcode F2");
                    int target=((helper.readMemoryByte(at(sfr,0xa0))&255)<<8)|helper.readRegister("R0").intValue();
                    if(target!=0x10da+pagedWrites || pagedWrites>=34)
                        throw new IllegalStateException("Unexpected paged startup destination");
                    helper.writeMemory(at(external,target),new byte[]{(byte)helper.readRegister("ACC").intValue()});
                    helper.writeRegister("PC",pc+1);pagedWrites++;
                }else if(!helper.step(monitor))throw new IllegalStateException(helper.getLastError());
            }
            if(steps==20000 || pagedWrites!=34 || maxSp!=0x42 || helper.readRegister("SP").intValue()!=0x40)
                throw new IllegalStateException("Startup failed to reach the hardware boundary with expected stack/copy");
            byte[] expected=new byte[0x1100];
            expected[0]=(byte)fill;
            Arrays.fill(expected,0x10fc,0x1100,(byte)fill);
            for(int address:new int[]{0x10,0x11,0x12,0x13,0xd2f,0xffc})expected[address]=1;
            for(int address:new int[]{0xd30,0xfe4,0xff7,0x1000,0x1001,0x1011})expected[address]=(byte)0xff;
            System.arraycopy(image,0xf211,expected,0x10da,34);
            byte[] actual=helper.readMemory(at(external,0),0x1100);
            if(!Arrays.equals(expected,actual)){
                for(int i=0;i<actual.length;i++)if(actual[i]!=expected[i])
                    throw new IllegalStateException("Startup EXTMEM mismatch at "+Integer.toHexString(i));
            }
            byte[] expectedInternal=new byte[256];expectedInternal[0x20]=0x30;
            byte[] actualInternal=helper.readMemory(at(internal,0),256);
            // Host snapshot reads bypass execution filters. Bank-zero CPU registers
            // are the authoritative bytes, just as they are for execution reads.
            for(int i=0;i<8;i++)actualInternal[i]=(byte)helper.readRegister("R"+i).intValue();
            if(!Arrays.equals(expectedInternal,actualInternal)){
                for(int i=0;i<actualInternal.length;i++)if(actualInternal[i]!=expectedInternal[i])
                    throw new IllegalStateException("Startup INTMEM mismatch at "+Integer.toHexString(i)+
                        ": "+(actualInternal[i]&255)+" != "+(expectedInternal[i]&255));
            }
            if((helper.readMemoryByte(at(sfr,0xa0))&255)!=255)
                throw new IllegalStateException("P2 page register was not restored");
            JsonObject row=new JsonObject();row.addProperty("passed",true);row.addProperty("initial_ram_fill",fill);
            row.addProperty("instructions",steps);row.addProperty("paged_movx_adapter_instructions",pagedWrites);
            row.addProperty("external_write_bytes",memory.externalWrites);row.addProperty("maximum_sp",maxSp);
            row.addProperty("final_sp",0x40);row.addProperty("stop_pc","0x8c2f");
            row.addProperty("external_ram_sha256",hash(actual));row.addProperty("internal_ram_sha256",hash(actualInternal));
            return row;
        }finally{helper.dispose();}
    }
    public void run()throws Exception{
        if(!currentProgram.getLanguageID().toString().equals("8051:BE:16:default"))throw new IllegalStateException("Unexpected language");
        code=currentProgram.getAddressFactory().getAddressSpace("CODE");
        external=currentProgram.getAddressFactory().getAddressSpace("EXTMEM");
        internal=currentProgram.getAddressFactory().getAddressSpace("INTMEM");
        sfr=currentProgram.getAddressFactory().getAddressSpace("SFR");
        bits=currentProgram.getAddressFactory().getAddressSpace("BITS");
        String[] arguments=getScriptArgs();
        imageBytes=Integer.parseInt(arguments[1]);
        if(imageBytes!=62003 && imageBytes!=62398)throw new IllegalStateException("Unexpected image size");
        byte[] image=new byte[imageBytes];currentProgram.getMemory().getBytes(at(code,0),image);
        String digest=hash(image);
        String pin=imageBytes==62003?"ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652":
            "7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16";
        if(!digest.equals(pin))throw new IllegalStateException("Unpinned startup image");
        Path output=Paths.get(arguments[0]);if(Files.exists(output))throw new IllegalStateException("Report already exists");
        JsonArray checks=new JsonArray();for(int fill:new int[]{0xa5,0x5a})checks.add(execute(image,fill));
        JsonObject report=new JsonObject();report.addProperty("image_sha256",digest);report.addProperty("passed",checks.size());
        report.addProperty("hardware_access",false);report.addProperty("feature_acceptance",false);
        report.addProperty("boundary","C-runtime startup only; stops before hardware init. Exact opcode F2 at 0059 uses an explicit P2:R0 CPU adapter; bank-zero and SP aliases are modeled. No RF/display, boot-ROM CODE loading or bus persistence.");
        report.add("checks",checks);Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report));
        println("Passed "+checks.size()+" bounded receiver startup checks.");
    }
}
