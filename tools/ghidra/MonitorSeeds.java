// Seed bounded ARM analysis. Names and RAM boundaries are analysis hypotheses.
// @category HDZero
import java.math.BigInteger;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.symbol.SourceType;

public class MonitorSeeds extends GhidraScript {
    @Override public void run() throws Exception {
        if (!currentProgram.getLanguageID().toString().equals("ARM:LE:32:v7") ||
            currentProgram.getMinAddress().getOffset() != 0x20008000L) {
            throw new IllegalStateException("Unexpected language or import base");
        }
        setAnalysisOption(currentProgram, "Decompiler Parameter ID", "false");
        if(currentProgram.getMemory().getBlock("Analysis_RAM_hypothesis")==null)
            currentProgram.getMemory().createUninitializedBlock("Analysis_RAM_hypothesis",
                toAddr(0x20428624L), 0x21000000L - 0x20428624L, false);
        long[] seeds = {0x2008cadcL,0x2023bb40L,0x2013df9cL,0x2023b9e8L,
            0x2023b890L,0x2008cc84L,0x2013dfa0L,0x2013e098L,
            0x20075928L,0x20074420L,0x20074018L,0x202859a0L};
        Register mode = currentProgram.getRegister("TMode");
        for (long value : seeds) {
            Address address = toAddr(value);
            if(getInstructionAt(address)==null)
                currentProgram.getProgramContext().setValue(mode, address, address, BigInteger.ZERO);
            disassemble(address);
            if(getFunctionAt(address)==null)createFunction(address, null);
            currentProgram.getSymbolTable().addExternalEntryPoint(address);
        }
        long[] strings = {0x202b4c58L,0x202b4c67L,0x202b4d07L,0x202b9229L,
            0x202b9235L,0x202b9189L,0x202b9600L,0x202b9734L,
            0x202b992dL,0x202f4c02L,0x203200feL};
        String[] names = {"Channel_Switch","Channel_ID","LastChannel","Channel_F2",
            "Channel_F4","statevideofunc_path","Unknown_ch","Channel_list",
            "Channel_occupied","Frequency_format","Scan_channels"};
        for (int i=0;i<strings.length;i++) {
            Address address=toAddr(strings[i]);
            if(getDataContaining(address)==null)createAsciiString(address);
            createLabel(address,"str_"+names[i],true,SourceType.USER_DEFINED);
        }
        println("Seeded vectors/settings/string candidates; RAM range is unverified.");
    }
}
