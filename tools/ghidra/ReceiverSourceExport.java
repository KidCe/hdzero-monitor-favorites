// Export machine-readable recovered instructions, without treating decompiler guesses as source.
// @category HDZero
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;

public class ReceiverSourceExport extends GhidraScript {
    public void run()throws Exception{
        if(!currentProgram.getLanguageID().toString().equals("8051:BE:16:default"))
            throw new IllegalStateException("Unexpected receiver language");
        byte[] image=new byte[62003];currentProgram.getMemory().getBytes(toAddr(0),image);
        String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(image));
        if(!hash.equals("ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652"))
            throw new IllegalStateException("Only pinned stock receiver export is supported");
        for(long entry:new long[]{0x725,0x6426}){
            disassemble(toAddr(entry));
            if(getFunctionAt(toAddr(entry))==null)createFunction(toAddr(entry),null);
        }
        JsonArray rows=new JsonArray();int end=0,total=0;
        for(Instruction instruction:currentProgram.getListing().getInstructions(true)){
            if(!instruction.getAddress().getAddressSpace().getName().equals("CODE"))continue;
            int start=(int)instruction.getAddress().getOffset();byte[] bytes=instruction.getBytes();
            if(start<end || start+bytes.length>image.length ||
               !Arrays.equals(bytes,Arrays.copyOfRange(image,start,start+bytes.length)))
                throw new IllegalStateException("Overlapping or unexpected instruction bytes");
            JsonObject row=new JsonObject();row.addProperty("offset",start);
            row.addProperty("bytes_hex",HexFormat.of().formatHex(bytes));
            row.addProperty("assembly",instruction.toString());
            Function function=getFunctionContaining(instruction.getAddress());
            if(function!=null)row.addProperty("function",function.getEntryPoint().getOffset());
            rows.add(row);end=start+bytes.length;total+=bytes.length;
        }
        JsonObject report=new JsonObject();report.addProperty("format","hdzero-recovered-instructions-v1");
        report.addProperty("image_sha256",hash);report.addProperty("image_bytes",image.length);
        report.addProperty("language",currentProgram.getLanguageID().toString());
        report.addProperty("instruction_count",rows.size());report.addProperty("instruction_bytes",total);
        report.addProperty("hardware_access",false);report.add("instructions",rows);
        report.addProperty("limits","Analyzed instruction interpretation, not recovered original C or complete semantic understanding");
        Path output=Paths.get(getScriptArgs()[0]);if(Files.exists(output))throw new IllegalStateException("Export already exists");
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardCharsets.UTF_8);
        println("Exported "+rows.size()+" source instructions covering "+total+" bytes.");
    }
}
