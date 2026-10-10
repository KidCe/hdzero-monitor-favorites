// Export receiver analysis candidates and actual assembly for manual cross-checking.
// @category HDZero
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class ReceiverExport extends GhidraScript {
    @Override public void run() throws Exception {
        Path root=Paths.get(getScriptArgs()[0]);Files.createDirectories(root);
        JsonObject report=new JsonObject();report.addProperty("program",currentProgram.getName());
        report.addProperty("language",currentProgram.getLanguageID().toString());
        report.addProperty("functions",currentProgram.getFunctionManager().getFunctionCount());
        report.addProperty("hardware_access",false);
        JsonArray functions=new JsonArray();
        DecompInterface decompiler=new DecompInterface();decompiler.openProgram(currentProgram);
        int count=0;
        for(Function function:currentProgram.getFunctionManager().getFunctions(true)){
            if(count++>=1200)break;
            JsonObject entry=new JsonObject();entry.addProperty("address",function.getEntryPoint().toString());
            entry.addProperty("name",function.getName());entry.addProperty("bytes",function.getBody().getNumAddresses());
            JsonArray incoming=new JsonArray();
            for(Reference ref:getReferencesTo(function.getEntryPoint())){
                JsonObject item=new JsonObject();item.addProperty("from",ref.getFromAddress().toString());
                item.addProperty("type",ref.getReferenceType().toString());
                Function caller=getFunctionContaining(ref.getFromAddress());
                if(caller!=null)item.addProperty("function",caller.getEntryPoint().toString());incoming.add(item);
            }
            entry.add("incoming",incoming);
            JsonArray outgoing=new JsonArray();StringBuilder listing=new StringBuilder();
            for(Instruction instruction:currentProgram.getListing().getInstructions(function.getBody(),true)){
                listing.append(instruction.getAddress()).append("  ").append(instruction).append("\n");
                for(Reference ref:instruction.getReferencesFrom()){
                    JsonObject item=new JsonObject();item.addProperty("from",ref.getFromAddress().toString());
                    item.addProperty("to",ref.getToAddress().toString());item.addProperty("type",ref.getReferenceType().toString());
                    outgoing.add(item);
                }
            }
            entry.add("outgoing",outgoing);
            String filename=function.getEntryPoint().toString().replace(':','_');
            Files.writeString(root.resolve(filename+".asm"),listing.toString(),StandardCharsets.UTF_8);
            DecompileResults result=decompiler.decompileFunction(function,15,monitor);
            entry.addProperty("decompiled",result.decompileCompleted());
            if(result.decompileCompleted())Files.writeString(root.resolve(filename+".c"),
                result.getDecompiledFunction().getC(),StandardCharsets.UTF_8);
            else entry.addProperty("error",result.getErrorMessage());
            functions.add(entry);
        }
        decompiler.dispose();report.add("candidate_functions",functions);
        Files.writeString(root.resolve("report.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardCharsets.UTF_8);
        println("Exported "+functions.size()+" decoded receiver candidates.");
    }
}
