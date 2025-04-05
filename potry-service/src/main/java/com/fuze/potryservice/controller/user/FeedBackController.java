package com.fuze.potryservice.controller.user;

import com.fuze.dto.FeedBackDto;
import com.fuze.dto.ReplyDto;
import com.fuze.entity.FeedBack;
import com.fuze.potryservice.service.FeedBackService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.FeedBackVo;
import com.github.pagehelper.PageInfo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/user/FeedBack")
@Api(tags ="用户留言反馈表相关接口")
@Slf4j
public class FeedBackController {
    @Autowired
    private FeedBackService feedBackService;


    @ApiOperation(value = "用户留言反馈")
    @PostMapping("/addfeedback")
    public Result<String> addfeedback(@RequestBody FeedBackDto feedBackDto)
    {
        feedBackService.addfeedback(feedBackDto);
        return Result.success("反馈成功");
    }

    @ApiOperation(value ="用户接受回复")
    @GetMapping("/getReply/{id}")
    public Result<String> getReply(@PathVariable Integer id)
{
    return Result.success(feedBackService.getReply(id));
}


//管理员对反馈的增删改查
@ApiOperation(value ="管理员查看所有用户的反馈")
@GetMapping("/getAllFeedBack")
    public Result<List<FeedBack>> getAllFeedBack()
{
    return Result.success(feedBackService.getAllFeedBack());
}

@ApiOperation("通过用户id查询留言")
    @GetMapping("/addfeedback/{id}")
    public Result<FeedBack> getFeedBack(@PathVariable Integer id)
{
    return Result.success(feedBackService.getFeedBack(id));
}

@ApiOperation("分页查询用户留言反馈,返回15条数据")
@GetMapping("/Getpage")
public Result<PageResult> SelectPageFeedBackVO(@RequestParam(defaultValue = "1") Integer pageNum, @RequestParam(defaultValue = "15") Integer pageSize){
    PageInfo<FeedBackVo> feedBackVOPageInfo = feedBackService.selectPage(pageNum, pageSize);
    PageResult pageResult = new PageResult(feedBackVOPageInfo.getTotal(), feedBackVOPageInfo.getList());
    return Result.success(pageResult);
}

    @ApiOperation("通过id删除用户留言，不看不看")
    @DeleteMapping("/deletefeedback/{id}")
    public Result<String> deletefeedback(@PathVariable Integer id)
{
    feedBackService.deletefeedback(id);
    return Result.success("删除成功");
}

@ApiOperation("管理员回复用户留言")
    @PutMapping("/updatefeedback")
public Result<String> updatefeedback(@RequestBody ReplyDto replyDto)
{
     feedBackService.addreply(replyDto);
    return Result.success("回复成功");
}


}
