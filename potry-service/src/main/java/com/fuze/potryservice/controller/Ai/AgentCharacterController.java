package com.fuze.potryservice.controller.Ai;

import com.alibaba.fastjson.JSONArray;
import com.fuze.dto.DefaultPoom;
import com.fuze.dto.InteractiveRequest;
import com.fuze.potryservice.service.UserService;
import com.fuze.result.Result;
import com.fuze.utils.InteractiveUtil;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/user/AI")
@Api(tags ="AI对话相关操作,没事别用，因为要钱")
@Slf4j
public class AgentCharacterController {
    @Autowired
    private UserService userService;


    private static final String interactiveUrl = "wss://ai-character.xfyun.cn/api/open/interactivews/";
    private static final String hostUrl = "https://ai-character.xfyun.cn/api";
    private static final String appId =  "4b88e2d9";
    private static final String secret = "NDJkYWVjOTk2ODg5N2ExMDIyMWJkNGNm";
    public static List<String> preSetMessages = new ArrayList<>();




  @ApiOperation("ai对话,通过id获取角色id")
@GetMapping("/getCharacter")
    public Result<String> getCharacter(@RequestParam("id") int id,@RequestParam String name,String text111) throws Exception{
      InteractiveUtil interactiveUtil = new InteractiveUtil();
     //先获取玩家id
      String plyaid =userService.getopid(id);
      //人格id，我们已经预设好了的
      String roleid=userService.getroleid(name);
      //判断数据库是否用有该会话的id,一个角色只能有一个会话
      String ischaid=userService.ischaid(name);
      String chatId;

      if(ischaid=="1"){
          //id=2
          chatId = UUID.randomUUID().toString().substring(0, 10);
      }else{
          chatId=ischaid;
      }
      String preChatId =chatId ;//如需要连续上次会话，带上轮会话Id，否则保持和chatId一致
      List<InteractiveRequest.Text> text = new ArrayList<>();
      InteractiveRequest.Text text1 = new InteractiveRequest.Text();
      text1.setContent(text111);
      text1.setRole(name);
      text.add(text1);
      chatId = UUID.randomUUID().toString().substring(0, 10);
      if(ischaid=="1"){
          //id=2
          userService.updachatId(chatId,roleid);
      }


      System.out.println("2"+":"+ischaid);
     interactiveUtil.chat(interactiveUrl, appId, plyaid, roleid, chatId, preChatId, text, secret);

      return Result.success("s");
    }
    @ApiOperation("删除该会话，重新开始一个,通过角色的名字")
    @DeleteMapping("/deleteCharacter/{name}")
    public Result deleteCharacter(@PathVariable String name) throws Exception {
        InteractiveUtil interactiveUtil = new InteractiveUtil();
        String ischaid=userService.ischaid(name);

        ischaid = UUID.randomUUID().toString().substring(0, 10);
        interactiveUtil.clearCache(hostUrl, secret, appId,ischaid);
        userService.deleteCharacter(name);
        return Result.success("success");
    }




    @ApiOperation("创建人格，测试用，请勿使用这个接口")
    @PostMapping("/DDDDDDD")
    public Result CreateCharacter() throws Exception{

        String playerId = "8034a7835df745a86045c384d4ccd186";
        String agentId = "1111";
        AgentUtil agentUtil = new AgentUtil();
        JSONArray languag = new JSONArray();
        languag.add("文言文，古人说话");
        agentUtil.createAgentCharacter(hostUrl, appId, secret, playerId, "李白", "古风,古人", "字太白，号青莲居士，又号“谪仙人”，祖籍陇西成纪（今甘肃省秦安县），出生于蜀郡绵州昌隆县（一说出生于西域碎叶）。唐代伟大的浪漫主义诗人，被后人誉为“诗仙”，与杜甫并称为“李杜”，为了与另两位诗人李商隐与杜牧即“小李杜”区别，杜甫与李白又合称“大李杜”。据《新唐书》记载，李白为兴圣皇帝（凉武昭王李暠）九世孙，与李唐诸王同宗。其人爽朗大方，爱饮酒作诗，喜交友。李白深受黄老列庄思想影响，有《李太白集》传世，诗作中多为醉时写就，代表作有《望庐山瀑布》《行路难》《蜀道难》《将进酒》《早发白帝城》等",
                "洒脱，豪放，天真烂漫",languag,"诗人，剑客","喝酒，舞剑，写诗");
        return Result.success("success");

    }
@ApiOperation("生成古诗词，通过预设的关键字，先通过http再使用webcocket")
@PostMapping("/preset-message")
public  Result<String> receivePresetMessage(@RequestBody DefaultPoom defaultPoom) throws Exception {
      String s=String.valueOf(defaultPoom);
    BigModelNew instance = new BigModelNew("1", false);
    instance.editAgentCharacter(s);
 return Result.success("success");

}





}
