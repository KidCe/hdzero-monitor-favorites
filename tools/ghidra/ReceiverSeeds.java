// Seed the decoded, unchanged Monitor DM5680 image. Register names are generic 8051 names.
// @category HDZero
import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.SourceType;

public class ReceiverSeeds extends GhidraScript {
    @Override public void run() throws Exception {
        if(!currentProgram.getLanguageID().toString().equals("8051:BE:16:default") ||
           currentProgram.getMinAddress().getOffset()!=0)
            throw new IllegalStateException("Unexpected receiver language/base");
        setAnalysisOption(currentProgram,"Decompiler Parameter ID","false");
        for(long value:new long[]{0,3,0xb,0x13,0x1b,0x23,0x33,0x39,0x8bbd,0x8b36,0x8bbe,0x8bbc,0x8bbf,0x8bf7}){
            disassemble(toAddr(value));
            if(getFunctionAt(toAddr(value))==null)createFunction(toAddr(value),null);
            currentProgram.getSymbolTable().addExternalEntryPoint(toAddr(value));
        }
        long[] strings={0xf1ca,0xf1d2,0xf201,0xf209};
        String[] names={"RF_AUTO","AV_IN","ANALOG","HDZERO"};
        for(int i=0;i<strings.length;i++){
            if(getDataContaining(toAddr(strings[i]))==null)createAsciiString(toAddr(strings[i]));
            createLabel(toAddr(strings[i]),"str_rx_"+names[i],true,SourceType.USER_DEFINED);
        }
        println("Seeded decoded 8051 vectors and receiver OSD strings.");
    }
}
