// Export references and decompilation candidates from the offline Ghidra project.
// @category HDZero
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class MonitorExport extends GhidraScript {
    private final LinkedHashSet<Function> candidates = new LinkedHashSet<>();
    @Override public void run() throws Exception {
        Path root=Paths.get(getScriptArgs()[0]); Files.createDirectories(root);
        JsonObject report=new JsonObject(); report.addProperty("program",currentProgram.getName());
        report.addProperty("language",currentProgram.getLanguageID().toString());
        report.addProperty("mapping_is_hypothesis",true);
        report.addProperty("functions",currentProgram.getFunctionManager().getFunctionCount());
        JsonArray refs=new JsonArray();
        for (Symbol symbol:currentProgram.getSymbolTable().getAllSymbols(true)) {
            if (!symbol.getName().startsWith("str_")) continue;
            JsonObject entry=new JsonObject();entry.addProperty("symbol",symbol.getName());
            entry.addProperty("address",symbol.getAddress().toString());JsonArray locations=new JsonArray();
            for (Reference ref:getReferencesTo(symbol.getAddress())) {
                JsonObject item=new JsonObject();item.addProperty("from",ref.getFromAddress().toString());
                item.addProperty("type",ref.getReferenceType().toString());
                Function f=getFunctionContaining(ref.getFromAddress());
                if(f!=null){item.addProperty("function",f.getEntryPoint().toString());candidates.add(f);}
                locations.add(item);
            }
            entry.add("references",locations);refs.add(entry);
        }
        report.add("strings",refs);
        for(long a:new long[]{0x20075928L,0x20074420L,0x20074018L,0x202859a0L}){
            Function f=getFunctionAt(toAddr(a));if(f!=null)candidates.add(f);
        }
        String[] args=getScriptArgs();
        JsonArray focusRefs=new JsonArray();
        for(int i=1;i<args.length;i++){
            if(args[i].startsWith("@")){
                Address target=toAddr(Long.decode(args[i].substring(1)));
                LinkedHashSet<Address> frontier=new LinkedHashSet<>();frontier.add(target);
                HashSet<Address> visited=new HashSet<>();
                for(int depth=0;depth<3;depth++){
                    LinkedHashSet<Address> next=new LinkedHashSet<>();
                    for(Address node:frontier){
                        if(!visited.add(node))continue;
                        for(Reference ref:getReferencesTo(node)){
                            JsonObject edge=new JsonObject();edge.addProperty("target",node.toString());
                            edge.addProperty("from",ref.getFromAddress().toString());
                            edge.addProperty("type",ref.getReferenceType().toString());
                            Function caller=getFunctionContaining(ref.getFromAddress());
                            if(caller!=null){candidates.add(caller);edge.addProperty("function",caller.getEntryPoint().toString());}
                            else next.add(ref.getFromAddress());
                            focusRefs.add(edge);
                        }
                    }
                    frontier=next;
                }
                continue;
            }
            Address address=toAddr(Long.decode(args[i]));
            Function f=getFunctionContaining(address);
            if(f==null){disassemble(address);f=createFunction(address,null);}
            if(f!=null)candidates.add(f);
        }
        report.add("focus_references",focusRefs);
        LinkedHashSet<Function> extra=new LinkedHashSet<>();
        for(Function f:candidates) {
            if(f.getEntryPoint().getOffset()==0x202859a0L)continue;
            for(Reference r:getReferencesTo(f.getEntryPoint())){
            Function caller=getFunctionContaining(r.getFromAddress());if(caller!=null)extra.add(caller);
            }
        }
        candidates.addAll(extra);
        DecompInterface decompiler=new DecompInterface();decompiler.openProgram(currentProgram);
        JsonArray functions=new JsonArray(); int count=0;
        for(Function f:candidates){
            if(count++>=100)break;
            JsonObject item=new JsonObject();item.addProperty("address",f.getEntryPoint().toString());
            item.addProperty("name",f.getName());JsonArray callers=new JsonArray();
            for(Reference r:getReferencesTo(f.getEntryPoint())){
                JsonObject caller=new JsonObject();caller.addProperty("from",r.getFromAddress().toString());
                caller.addProperty("type",r.getReferenceType().toString());Function cf=getFunctionContaining(r.getFromAddress());
                if(cf!=null)caller.addProperty("function",cf.getEntryPoint().toString());callers.add(caller);
            }
            item.add("incoming",callers);
            DecompileResults result=decompiler.decompileFunction(f,30,monitor);
            item.addProperty("decompiled",result.decompileCompleted());
            if(result.decompileCompleted()){
                Files.writeString(root.resolve(f.getEntryPoint()+".c"),result.getDecompiledFunction().getC(),StandardCharsets.UTF_8);
            }else item.addProperty("error",result.getErrorMessage());functions.add(item);
        }
        decompiler.dispose();report.add("candidate_functions",functions);
        Files.writeString(root.resolve("report.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardCharsets.UTF_8);
        println("Exported "+functions.size()+" candidate functions to "+root);
    }
}
