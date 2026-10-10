// Bounded connected v4 receiver paths with actual nested 8051 LCALL/RET.
// @category HDZero
import java.util.*;
import com.google.gson.*;

public class ReceiverConnectedTests extends ReceiverCandidateTests {
    private Map<Long,Integer> settings(int selection,boolean erased){
        Map<Long,Integer> values=new HashMap<>();
        int[] bytes={selection,0,0x88,0x56,0x8f,80,1,0xa5,28,1};
        for(int i=0;i<bytes.length;i++)values.put(0xd85L+i,erased && i!=0 && i!=7?255:bytes[i]);
        values.put(0xd8fL,0xa5);return values;
    }
    private Map<Long,Integer> validated(int selection,boolean erased){
        Map<Long,Integer> values=settings(selection,false);values.put(0xd8fL,erased?1:0);return values;
    }
    protected void addExtraChecks(JsonArray checks,byte[] image)throws Exception{
        super.addExtraChecks(checks,image);
        int[][] saveRanges={{0x9f29,0x9f2f},{0x9d44,0x9e12}};
        for(int selection=0;selection<56;selection++)for(boolean erased:new boolean[]{false,true})
            for(int entry:new int[]{0x674,0x6d6})for(int direction=0;direction<2;direction++){
                int result=entry==0x674?(((selection/8+(direction==0?6:1))%7)*8+(selection&7)):
                    ((selection&0xf8)|((selection+(direction==0?7:1))&7));
                Map<Long,Integer> initial=settings(selection,erased);
                initial.put(6L,0);initial.put(7L,0);initial.put(8L,0);initial.put(9L,0);
                int returnAddress=entry==0x674?0x6c3:0x712;
                checks.add(runConnected("Selection -> nested save validation "+selection+" / "+Integer.toHexString(entry)+
                    " direction "+direction+" erased fields "+erased,initial,List.of(new Stage(
                        "selection and real validator call",entry,0x9f2f,direction,0x42,0x44,
                        new int[][]{{entry,entry==0x674?0x6c3:0x712},saveRanges[0],saveRanges[1]},validated(result,erased),
                        Map.of(0x41L,returnAddress&255,0x42L,returnAddress>>8,0x43L,0x2c,0x44L,0x9f)))));
            }
        for(int selection=48;selection<56;selection++)for(int direction=0;direction<2;direction++)
            for(boolean erased:new boolean[]{false,true}){
                Map<Long,Integer> initial=settings(selection,erased);
                for(long offset:new long[]{8,9,0x767,0x768,0x765,0x76d,0x76e})initial.put(offset,0);
                initial.put(0x760L,selection);
                Map<Long,Integer> unchanged=Map.of(0xd85L,selection,0x760L,selection,0x767L,0,0x768L,0,0x765L,0,0x76eL,0);
                int guard=direction==0?0xf38a:0xf3a4;
                Stage held=new Stage("classified long press",direction==0?0x965:0x9b1,0x9cb,-1,0x40,0x40,
                    new int[][]{{direction==0?0x965:0x9b1,0x9cb},{guard,guard+26}},unchanged,Map.of());
                Map<Long,Integer> idleExpected=new HashMap<>(unchanged);
                int[] scanIds={0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x10,0x18,0x19,0x1b};
                for(int i=0;i<49;i++)idleExpected.put(0x816L+i,i<12?scanIds[i]:0);
                idleExpected.put(0x852L,0);
                Stage idle=new Stage("main-loop idle scan service",0x6d6c,0x766d,-1,0x40,0x40,
                    new int[][]{{0x6d6c,0x766d}},idleExpected,Map.of());
                int result=(selection&0xf8)|((selection+(direction==0?7:1))&7);
                Map<Long,Integer> finalState=validated(result,erased);
                finalState.put(0x760L,selection);finalState.put(0x767L,0);finalState.put(0x768L,0);finalState.put(0x76eL,0);
                int returnAddress=direction==0?0xb19:0xb06;
                Stage release=new Stage("release -> channel -> save -> validator",direction==0?0xb0e:0xafa,0x9f2f,-1,0x44,0x46,
                    new int[][]{{direction==0?0xb0e:0xafa,direction==0?0xb19:0xb06},{0x6d6,0x712},saveRanges[0],saveRanges[1]},
                    finalState,Map.of(0x41L,returnAddress&255,0x42L,returnAddress>>8,0x43L,0x12,0x44L,7,0x45L,0x2c,0x46L,0x9f));
                checks.add(runConnected("Held P"+(selection-47)+" direction "+direction+" erased fields "+erased,
                    initial,List.of(held,idle,release)));
            }
        for(int selection=0;selection<56;selection++)for(int mode=0;mode<2;mode++)
            for(boolean same:new boolean[]{false,true})for(int scan=0;scan<3;scan++){
                int cached=same?selection:(selection+1)%56;
                Map<Long,Integer> initial=Map.of(0xd85L,selection,0x760L,cached,0xd86L,mode,
                    0x767L,scan==1?1:0,0x768L,scan==2?1:0);
                Map<Long,Integer> expected=new HashMap<>(initial);int stop=mode==1?0x67ef:scan!=0?0x67fc:same?0x680b:0xc83;
                boolean tune=stop==0xc83;int effective=selection<48?selection:new int[]{0x2d,0x2e,0x20,0x21,0x19,0x1b,0x26,0x27}[selection-48];
                if(tune)expected.put(0x36L,image[0xc6f0+effective]&255);
                checks.add(runConnected("Mode gate selection "+selection+" input mode "+mode+" same cache "+same+" scan "+scan,
                    initial,List.of(new Stage("service gate and optional real RF-index call",0x67e7,stop,-1,tune?0x42:0x40,tune?0x42:0x40,
                        new int[][]{{0x67e7,0x6811},{0xc74,0xc83}},expected,tune?Map.of(0x41L,0x11,0x42L,0x68):Map.of()))));
            }
    }
}
