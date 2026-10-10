// Tests for one hash-pinned decoded Favorites experiment; no update container or device access.
// @category HDZero
import java.util.*;
import com.google.gson.*;

public class ReceiverCandidateTests extends ReceiverSelectionTests {
    private Map<Long,Integer> validSettings(int selection){
        Map<Long,Integer> values=new HashMap<>();
        int[] bytes={selection,0,0x88,0x56,0x8f,0x50,1,0xa5,0x1c,1};
        for(int i=0;i<bytes.length;i++)values.put(0xd85L+i,bytes[i]);
        values.put(0xd8fL,0xa5); // Must clear an old correction flag.
        return values;
    }
    protected void configure(){
        expectedHash="7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16";
        imageBytes=62398;bandCount=7;patched=true;decodeTailBytes=16;
    }
    protected void addExtraChecks(JsonArray checks,byte[] image)throws Exception{
        // Automatic analysis can classify appended opcode bytes as ASCII/data. Reclassify
        // only the hash-verified, assembler-verified 52-byte guard region as instructions.
        clearListing(toAddr(0xf38a),toAddr(0xf3bd));
        disassemble(toAddr(0xf38a));disassemble(toAddr(0xf3a4));
        int[] favorites={0x2d,0x2e,0x20,0x21,0x19,0x1b,0x26,0x27};
        for(int logical=0;logical<56;logical++){
            int effective=logical<48?logical:favorites[logical-48];
            int index=image[0xc6f0+effective]&255;
            int flag=image[0xc6c0+effective]&255;
            String label="ABEFRLP".charAt(logical>>3)+Integer.toString((logical&7)+1);
            String prefix=label+" -> stock "+effective+" ";
            checks.add(runFragment(prefix+"RF lookup",0xc74,0xc83,Map.of(),Map.of(0x36L,index),logical));
            checks.add(runFragment(prefix+"initialization lookup",0x2dac,0x2dc4,
                Map.of(0x76dL,0),Map.of(0x728L,index),logical));
            Map<Long,Integer> word=new HashMap<>();
            for(int byteIndex=0;byteIndex<4;byteIndex++)word.put(0xdafL+byteIndex,image[0xef08+4*effective+byteIndex]&255);
            checks.add(runFragment(prefix+"second tune lookup",0x5d32,0x5d61,Map.of(0x777L,logical),word,0));
            Map<Long,Integer> display=Map.of(0xfedL,(int)label.charAt(0),0xfeeL,(int)label.charAt(1));
            checks.add(runFragment(prefix+"normal label",0xb885,0xb8a9,Map.of(0xd85L,logical),display,0));
            checks.add(runFragment(prefix+"busy label",0xb7ab,0xb7cf,Map.of(0xd85L,logical),display,0));
            for(int[] range:new int[][]{{0x773,0x77b},{0x6008,0x6019},{0x6366,0x6377},{0x6466,0x6477},{0x6827,0x6838}})
                checks.add(runFragment(prefix+"capability "+Integer.toHexString(range[0]),range[0],range[1],
                    Map.of(0xd85L,logical),Map.of(),0,Map.of("ACC",flag)));
            Map<Long,Integer> rfWord=new HashMap<>();
            rfWord.put(0xd9fL,0x20);rfWord.put(0xda0L,1);
            for(int byteIndex=0;byteIndex<4;byteIndex++)rfWord.put(0xda1L+byteIndex,image[0xc720+4*index+byteIndex]&255);
            checks.add(runFragment(prefix+"RF register word A",0xebe,0xef5,Map.of(0x36L,index),rfWord,0));
            checks.add(runFragment(prefix+"RF register word B",0xfa0,0xfd8,Map.of(0x36L,index),rfWord,0));
            // Each fragment stops at the selected first peripheral call. No transaction is skipped or fabricated.
            boolean special=index==8 || index==9 || index>=12;
            int[][] profiles={
                {0xd31,0xd64,0xd88,0x44,0x35,7,0x24,0x15,0x35,7,0x64,0x0d},
                {0xdab,0xdde,0xe02,0x4c,0xa2,0x88,0x12,2,0xa2,0x88,0x22,2},
                {0xe26,0xe59,0xe9c,0x54,0x40,0x38,0x2c,0x1f,0x40,0x34,0x0c,0x1f},
                {0xf51,0xf7c,0xf9d,0x28,0x31,0x80,0,0,0x30,0x80,0,0},
                {0x111d,0x1147,0x1166,0x40,2,0,7,7,0,0,7,7}
            };
            for(int[] profile:profiles){
                Map<Long,Integer> values=new HashMap<>();
                values.put(0xd9fL,profile[3]);values.put(0xda0L,1);
                for(int b=0;b<4;b++)values.put(0xda1L+b,profile[(special?4:8)+b]);
                checks.add(runFragment(prefix+"RF profile "+Integer.toHexString(profile[3]),
                    profile[0],profile[special?1:2],Map.of(0x36L,index),values,0,Map.of(),Map.of("R7",index)));
            }
            for(int[] calibration:new int[][]{{0x1058,0x1087,0xc770,4},{0x1091,0x10c0,0xc7c0,8}}){
                Map<Long,Integer> values=new HashMap<>();
                values.put(0xd9fL,calibration[3]);values.put(0xda0L,1);
                for(int b=0;b<4;b++)values.put(0xda1L+b,image[calibration[2]+4*index+b]&255);
                checks.add(runFragment(prefix+"RF calibration "+Integer.toHexString(calibration[2]),
                    calibration[0],calibration[1],Map.of(),values,0,Map.of(),Map.of("R6",4*index)));
            }
            // Main-loop scan service executes even while idle. Verify it cannot erase a P selection
            // when neither scan-direction flag nor scan-in-progress state is set.
            Map<Long,Integer> idle=new HashMap<>();
            idle.put(0x767L,0);idle.put(0x768L,0);idle.put(0x76eL,0);
            idle.put(0xd85L,logical);idle.put(0x760L,logical);
            Map<Long,Integer> idleExpected=new HashMap<>();
            int[] scanIds={0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x10,0x18,0x19,0x1b};
            for(int b=0;b<49;b++)idleExpected.put(0x816L+b,b<12?scanIds[b]:0);
            idleExpected.put(0x852L,0);idleExpected.put(0xd85L,logical);idleExpected.put(0x760L,logical);
            checks.add(runFragment(prefix+"idle main-loop scan service",0x6d6c,0x766d,idle,idleExpected,0));
            // Stop before the real write helper. No bus call is stubbed.
            Map<Long,Integer> saved=new HashMap<>();
            for(int b=0;b<8;b++)saved.put(0x858L+b,b==2?logical:0);
            checks.add(runFragment(prefix+"settings write descriptor",0x9f32,0x9f5d,
                Map.of(0xd85L,logical),saved,0,Map.of("DPL",0x50)));
            // Read-helper return value is an explicit fixture, not a simulated bus result.
            checks.add(runFragment(prefix+"settings read value store",0x9e27,0x9e2e,
                Map.of(),Map.of(0xd85L,logical),logical));
        }
        for(int selection=0;selection<256;selection++)checks.add(runFragment("Loaded state "+selection,
            0x9d44,0x9d5f,Map.of(0xd85L,selection),Map.of(0xd85L,selection<56?selection:32,0xd8fL,selection<56?0:1),0));
        for(int selection=0;selection<256;selection++){
            Map<Long,Integer> initial=validSettings(selection),expected=new HashMap<>(initial);
            expected.put(0xd85L,selection<56?selection:32);expected.put(0xd8fL,selection<56?0:1);
            checks.add(runFragment("Complete loaded-settings validation "+selection,
                0x9d44,0x9e11,initial,expected,0,Map.of("DPL",selection<56?0:1)));
        }
        // Exhaust other persisted fields with P1 selected. Correcting an unrelated field
        // must preserve P1. Expectations use the independently recovered stock rules.
        for(int field:new int[]{0xd86,0xd87,0xd88,0xd89,0xd8a,0xd8b,0xd8d,0xd8e}){
            for(int value=0;value<256;value++){
                int corrected=value;
                switch(field){
                    case 0xd86: if(value>=2)corrected=0;break;
                    case 0xd87: if(value==255)corrected=0x88;break;
                    case 0xd88: if(value==255)corrected=0x56;break;
                    case 0xd89: if(value==255)corrected=0x8f;break;
                    case 0xd8a: if(value>=101)corrected=80;break;
                    case 0xd8b: if(value<1 || value>6)corrected=1;break;
                    case 0xd8d: if(value<28 || value>42)corrected=28;break;
                    case 0xd8e: if(value>=2)corrected=1;break;
                }
                int changed=corrected==value?0:1;
                Map<Long,Integer> initial=validSettings(48),expected=new HashMap<>(initial);
                initial.put((long)field,value);expected.put((long)field,corrected);expected.put(0xd8fL,changed);
                checks.add(runFragment("P1 with settings field "+Integer.toHexString(field)+" = "+value,
                    0x9d44,0x9e11,initial,expected,0,Map.of("DPL",changed)));
            }
        }
        // Known unresolved stock scan behavior, recorded separately from feature acceptance.
        for(int logical=48;logical<56;logical++){
            checks.add(runFragment("Known stock scan cancellation leaves P"+(logical-47),0x7646,0x766a,
                Map.of(0x816L,0x20,0xd85L,logical,0x760L,logical),
                Map.of(0x75cL,2,0x75dL,2,0xd85L,0x20,0x760L,0x20,0x727L,0),0,Map.of("DPL",0x20)));
            for(int direction=0;direction<2;direction++)checks.add(runFragment(
                "P"+(logical-47)+" release edge reaches channel step direction "+direction,
                direction==0?0x0b0e:0x0afa,direction==0?0x0b16:0x0b03,
                Map.of(direction==0?0x767L:0x768L,0,0xd85L,logical),
                Map.of(0xd85L,logical),0,Map.of("DPL",direction)));
        }
        for(int selection=0;selection<256;selection++)for(int direction=0;direction<2;direction++){
            long flag=direction==0?0x767L:0x768L;
            int active=selection>=48 && selection<56?0:1;
            Map<String,Integer> cpu=new HashMap<>();
            for(int r=0;r<8;r++)cpu.put("R"+r,0x90+r);
            int guard=direction==0?0xf38a:0xf3a4;
            Map<String,Integer> outputs=new HashMap<>(cpu);outputs.put("PSW",0);
            checks.add(runFragmentRegions("Guarded long-press selection "+selection+" direction "+direction,
                direction==0?0x0965:0x09b1,0x09cb,Map.of(flag,0,0x76dL,0,0xd85L,selection,0x765L,0,0x76eL,0),
                Map.of(flag,active,0x765L,active,0x76eL,active,0xd85L,selection),0,outputs,cpu,
                new int[][]{{guard,guard+26}}));
        }
        for(int direction=0;direction<2;direction++)checks.add(runFragment(
            "Known stock scan entry while P1 selected direction "+direction,0x6e45,0x6e62,
            Map.of(0x767L,direction==0?1:0,0x768L,direction==1?1:0,0xd85L,48),
            Map.of(0x761L,0,0x778L,0,0xd85L,48),0));
    }
}
