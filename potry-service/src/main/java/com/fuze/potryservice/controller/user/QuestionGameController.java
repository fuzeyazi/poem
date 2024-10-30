package com.fuze.potryservice.controller.user;

import com.fuze.potryservice.service.PotryService;
import com.fuze.potryservice.service.QuestionGameService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.GameRankVo;
import com.fuze.vo.PoemDataVo;
import com.github.pagehelper.PageInfo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.CachePut;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.web.bind.annotation.*;

import javax.validation.constraints.NotNull;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/user/game")
@Api(tags ="用户游戏的相关接口")
@Slf4j
public class QuestionGameController {
    //todo 需要完成排行榜，用户查看，管理员修改
@Autowired
public RedisTemplate redisTemplate;
@Autowired
private PotryService potryService;
@Autowired
private QuestionGameService questionGameService;
         @Value("120")
         private int gameTimeoutSeconds;
         private int sum=0;
    @ApiOperation("展示题目，一次调用出现一次题目")
    @GetMapping("questions")
    public Result<String> getQuestions(HttpServletRequest request){
        HttpSession session = request.getSession(true);
        session.setAttribute("startTime", System.currentTimeMillis());// 记录开始时间
    PoemDataVo questions=potryService.GetVeryGoodPoem();
   String content =questions.getContent();
        String[] parts = content.split("。");
        List<String> line=new ArrayList<>();
        for(String part : parts){
            String trimmedPart = part.trim();
            if (!trimmedPart.isEmpty()) {
                line.add(trimmedPart);
            }
        }
        String[] part = line.get(0).split("，");
        List<String> temp = new ArrayList<>();
        for(String s : part){
            temp.add(s);
        }
        questionGameService.addQuestion(temp.get(1));
        return Result.success(temp.get(0));
    }
@ApiOperation("检验是否答对")
    @GetMapping("check")
    public Result<String> check(String answer,HttpServletRequest request) {
    HttpSession session = request.getSession(false); // 使用false避免创建新的session
    if (session == null || session.getAttribute("startTime") == null) {
        questionGameService.deleteQuestion();
        sum=0;
        return Result.error("游戏会话无效，请重新开始");
    }
    long startTime = (Long) session.getAttribute("startTime");
    long currentTime = System.currentTimeMillis();
    if (currentTime - startTime > gameTimeoutSeconds * 1000L) {
        questionGameService.deleteQuestion();
        sum=0;
        return Result.error("游戏超时，请重新开始");
    }
    try {
        String daan = questionGameService.getQuestion();
        if (daan.equals(answer)) {
            questionGameService.deleteQuestion();
            sum+=10;
            return Result.success("答对了");
        } else {
            sum = 0;
            questionGameService.deleteQuestion();
            return Result.error("答错了,答案是" + daan);
        }
    }catch (Exception e){
        session.removeAttribute("startTime");
        throw e;
    }finally {
        // 无论成功还是失败都清除 startTime
        session.removeAttribute("startTime");
    }
}
@ApiOperation("总成绩传入数据库")
    @GetMapping("score")
    public Result<String> score(@RequestParam Integer userId){
        String name = questionGameService.getusername(userId);
    String key = "user_" + userId;
    ValueOperations opsForValue = redisTemplate.opsForValue();
    opsForValue.set(key, sum);
    questionGameService.addsum(sum,userId,name);
    sum=0;
    return Result.success("答题结束");
    }


    @ApiOperation("用户查询自己的最后一次的答题记录")
    @PostMapping("/getLatest")
    public Result<Integer> getLatest(@NotNull @RequestParam Integer userid ) {
        String key = "user_" + userid;
        ValueOperations opsForValue = redisTemplate.opsForValue();
        Integer grade = (Integer) opsForValue.get(key);
        if (grade != null) {
            return Result.success(grade);
        } else {
            //无 则返回null; 代表没有答过题目;
            return Result.success();
        }}
     @ApiOperation("查看排行榜,展示前20")
     @GetMapping("/getRank/")
    public Result<List<GameRankVo>>getRank(){
        List<GameRankVo> rank=questionGameService.getRank();
        return Result.success(rank);
    }



//管理员，删除记录，查询任意用户的记录，
@ApiOperation(value = "分页查询用户答题成绩记录(一次默认获取15条数据)")
@GetMapping("/SelectPage")
public Result<PageResult> SelectPageTestVO(@RequestParam(defaultValue = "1") Integer pageNum, @RequestParam(defaultValue = "15") Integer pageSize) {
    PageInfo<GameRankVo> testVOPageInfo = questionGameService.selectPageVO(pageNum, pageSize);
    PageResult pageResult = new PageResult(testVOPageInfo.getTotal(), testVOPageInfo.getList());
    return Result.success(pageResult);

}
@ApiOperation(value = "这个id是用户id懒的改，管理员删除用户答题记录")
    @DeleteMapping("/delete/{id}")
    public Result<String> delete(@PathVariable Integer id){
    String key = "user_" + id;
    ValueOperations opsForValue = redisTemplate.opsForValue();
    redisTemplate.delete(key);
    questionGameService.delete(id);
        return Result.success("删除成功");
    }
  @ApiOperation(value ="查询一个用户的所有游戏记录")
    @GetMapping("/getAllRecord/{userid}")
    public Result<List<GameRankVo>> getAllRecord(@PathVariable Integer userid){
    List<GameRankVo> rank=questionGameService.getuserRank(userid);
    return Result.success(rank);
   }

}






