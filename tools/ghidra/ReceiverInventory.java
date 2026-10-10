// Review literal selection references, including code not reached by initial analysis.
// @category HDZero
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class ReceiverInventory extends GhidraScript {
    public void run()throws Exception{
        for(long entry:new long[]{0x725,0x6426}){
            disassemble(toAddr(entry));
            if(getFunctionAt(toAddr(entry))==null)createFunction(toAddr(entry),null);
        }
        byte[] image=new byte[62003];currentProgram.getMemory().getBytes(toAddr(0),image);
        JsonArray literals=new JsonArray();
        for(int i=0;i<image.length-2;i++)if((image[i]&255)==0x90){
            int target=((image[i+1]&255)<<8)|(image[i+2]&255);
            if(target!=0xd85 && target!=0xc6c0 && target!=0xc6f0)continue;
            Address address=toAddr(i);Instruction instruction=getInstructionAt(address);
            JsonObject row=new JsonObject();row.addProperty("address",address.toString());
            row.addProperty("literal",String.format("0x%04x",target));
            row.addProperty("instruction",instruction==null?"unresolved":instruction.toString());
            Function function=getFunctionContaining(address);
            row.addProperty("function",function==null?"unresolved":function.getEntryPoint().toString());
            JsonArray context=new JsonArray();Instruction next=instruction;
            for(int j=0;j<10 && next!=null;j++){
                context.add(next.getAddress()+" "+next.toString());next=currentProgram.getListing().getInstructionAfter(next.getAddress());
            }
            row.add("context",context);
            literals.add(row);
        }
        JsonArray interior=new JsonArray();
        for(Instruction instruction:currentProgram.getListing().getInstructions(true)){
            for(Reference ref:instruction.getReferencesFrom()){
                long target=ref.getToAddress().getOffset();
                if(ref.getToAddress().getAddressSpace().equals(currentProgram.getAddressFactory().getDefaultAddressSpace()) &&
                    ((target>0xb7ab && target<0xb7c1)||(target>0xb885 && target<0xb89b))){
                    JsonObject row=new JsonObject();row.addProperty("from",ref.getFromAddress().toString());
                    row.addProperty("to",ref.getToAddress().toString());row.addProperty("type",ref.getReferenceType().toString());
                    interior.add(row);
                }
            }
        }
        JsonObject report=new JsonObject();report.add("literal_references",literals);
        StringBuilder listing=new StringBuilder();
        for(Instruction instruction:currentProgram.getListing().getInstructions(true))
            listing.append(instruction.getAddress()).append("  ").append(instruction).append("\n");
        Files.writeString(Paths.get(getScriptArgs()[0]+".asm"),listing.toString(),StandardCharsets.UTF_8);
        report.add("references_into_label_rewrite_interiors",interior);
        report.addProperty("limits","Literal scan and analyzed instruction references; indirect aliases and computed targets are not excluded");
        Files.writeString(Paths.get(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardCharsets.UTF_8);
        println("Receiver reference inventory exported.");
    }
}
